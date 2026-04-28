class Controller:
    def __init__(self, system):
        self.system = system
        self.state = {
            "pv_to_rede": 0.0,
            "pv_to_eletrolisador": 0.0,
            "pv_to_bateria": 0.0,
            "fc_to_rede": 0.0,
            "fc_to_bateria": 0.0,
            "battery_to_rede": 0.0,
            "bottling": 0.0,
            "unserved_load": 0.0
        }

    def reset_state(self):
        for key in self.state:
            self.state[key] = 0.0

    def step(self, dt):
        self.reset_state()

        painel = self.system["painel_fotovoltaico"]
        eletrolisador = self.system["eletrolisador"]
        tanque = self.system["tanque"]
        celula = self.system["celula_combustivel"]
        bateria = self.system["bateria"]
        rede = self.system["rede"]

        voltage = rede.inputs["tensao"].value or 48.0
        demand_current = rede.inputs["corrente"].value or 0.0
        demand_power = voltage * demand_current

        pv_power = painel.outputs["potencia"]
        remaining_demand = demand_power

        bateria.mode = "idle"
        bateria.outputs["corrente"] = 0.0

        celula.inputs["caudal_hidrogenio"].value = 0.0
        eletrolisador.inputs["potencia"].value = 0.0
        tanque.outflow_request = 0.0
        tanque.bottling_flow = 0.0

        # 1. PV priority: rede elétrica
        pv_to_rede = min(pv_power, remaining_demand)
        self.state["pv_to_rede"] = pv_to_rede
        remaining_demand -= pv_to_rede
        excess_pv = pv_power - pv_to_rede

        # 2. If load still needs power, use fuel cell
        if remaining_demand > 0 and not tanque.is_empty():
            efficiency = 0.60
            lhv_h2 = 120e6
            h2_kg_s_needed = remaining_demand / (lhv_h2 * efficiency)
            h2_mol_s_needed = h2_kg_s_needed / 0.002016

            actual_h2_mol_s = tanque.remove_h2(h2_mol_s_needed, dt)
            tanque.outflow_request = actual_h2_mol_s

            celula.inputs["caudal_hidrogenio"].value = actual_h2_mol_s
            celula.compute(dt)

            fc_power = celula.outputs["potencia"]
            fc_to_rede = min(fc_power, remaining_demand)

            self.state["fc_to_rede"] = fc_to_rede
            remaining_demand -= fc_to_rede

        # 3. If still needed, use battery
        if remaining_demand > 0 and bateria.soc > 0:
            delivered = bateria.discharge(remaining_demand, dt)
            bateria.mode = "discharge"
            bateria.outputs["corrente"] = delivered / 48.0

            self.state["battery_to_rede"] = delivered
            remaining_demand -= delivered

        self.state["unserved_load"] = max(0.0, remaining_demand)

        # 4. Excess PV: electrolyzer first if tank not full
        if excess_pv > 0 and not tanque.is_full():
            eletrolisador.inputs["potencia"].value = excess_pv
            eletrolisador.compute(dt)

            h2_mol_s = eletrolisador.outputs["hidrogenio"]
            free_capacity = tanque.capacity_mol - tanque.h2_mol
            accepted_mol_s = min(h2_mol_s, free_capacity / dt)

            tanque.add_h2(accepted_mol_s, dt)

            used_fraction = accepted_mol_s / h2_mol_s if h2_mol_s > 0 else 0
            used_power = excess_pv * used_fraction

            self.state["pv_to_eletrolisador"] = used_power
            excess_pv -= used_power

        # 5. If electrolyzer/tank does not need it, charge battery
        if excess_pv > 0 and bateria.soc < 1.0:
            accepted = bateria.charge(excess_pv, dt)
            bateria.mode = "charge"
            bateria.outputs["corrente"] = accepted / 48.0

            self.state["pv_to_bateria"] = accepted
            excess_pv -= accepted

        # 6. Tank full and no use: bottling
        if excess_pv > 0 and tanque.is_full():
            eletrolisador.inputs["potencia"].value = excess_pv
            eletrolisador.compute(dt)
            bottling = eletrolisador.outputs["hidrogenio"]
            tanque.bottling_flow = bottling
            self.state["bottling"] = bottling

        # 7. Consumption = 0, battery full, tank full -> bottling
        if demand_power == 0 and bateria.soc >= 1.0 and tanque.is_full() and pv_power > 0:
            eletrolisador.inputs["potencia"].value = pv_power
            eletrolisador.compute(dt)
            bottling = eletrolisador.outputs["hidrogenio"]
            tanque.bottling_flow = bottling
            self.state["bottling"] = bottling