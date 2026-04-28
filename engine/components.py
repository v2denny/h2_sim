from engine.utils import Variable


class Component:
    def __init__(self, name, config):
        self.name = name
        self.inputs = {k: Variable(v) for k, v in config["inputs"].items()}
        self.outputs = {k: 0.0 for k in config["outputs"]}
        self.sensors = {k: 0.0 for k in config["sensores"]}
        self.connections = config["ligacoes"]
        self.manual_inputs = set()

    def update_inputs(self, t):
        for key, var in self.inputs.items():
            if key not in self.manual_inputs:
                var.update(t)

    def set_input(self, key, value):
        if key in self.inputs:
            self.inputs[key].set_manual(value)
            self.manual_inputs.add(key)

    def compute(self, dt):
        pass


class Painel(Component):
    def compute(self, dt):
        G = self.inputs["radiacao"].value
        T = self.inputs["temperatura"].value
        inclinacao = self.inputs["inclinacao"].value

        area = 5.0
        eta_ref = 0.20
        temp_coeff = -0.004
        T_ref = 25.0

        efficiency = eta_ref * (1 + temp_coeff * (T - T_ref))
        efficiency = max(0, efficiency)

        power = max(G * area * efficiency, 0)

        voltage = 48.0
        current = power / voltage if voltage > 0 else 0.0

        self.outputs.update({
            "tensao": voltage,
            "corrente": current,
            "potencia": power
        })

        self.sensors.update({
            "tensao": voltage,
            "corrente": current,
            "potencia": power,
            "temperatura": T,
            "radiacao": G,
            "inclinacao": inclinacao
        })


class Eletrolisador(Component):
    def compute(self, dt):
        power = self.inputs["potencia"].value or 0.0
        voltage = self.inputs["tensao"].value or 48.0
        current_density = self.inputs["densidade_corrente"].value or 0.0
        water_flow = self.inputs["caudal_agua"].value or 0.0
        pressure = self.inputs["pressao_funcionamento"].value or 0.0
        temperature = self.inputs["temperatura_trabalho"].value or 25.0

        efficiency = 0.70
        lhv_h2 = 120e6

        h2_kg_s = (power * efficiency) / lhv_h2 if power > 0 else 0.0
        h2_mol_s = h2_kg_s / 0.002016 if h2_kg_s > 0 else 0.0

        current = power / voltage if voltage > 0 else 0.0

        self.outputs.update({
            "hidrogenio": h2_mol_s,
            "qualidade_hidrogenio": 99.9 if h2_mol_s > 0 else 0.0,
            "pressao_hidrogenio": pressure
        })

        self.sensors.update({
            "tensao": voltage,
            "corrente": current,
            "densidade_corrente": current_density,
            "temperatura": temperature,
            "caudal_H2": h2_mol_s,
            "caudal_H2O": water_flow,
            "pressao": pressure,
            "potencia": power
        })


class Tanque(Component):
    def __init__(self, name, config):
        super().__init__(name, config)
        self.h2_mol = 0.0
        self.capacity_mol = 500.0
        self.volume_m3 = 1.0
        self.R = 8.314462618
        self.outflow_request = 0.0
        self.bottling_flow = 0.0

    def add_h2(self, mol_s, dt):
        self.h2_mol += max(0.0, mol_s) * dt

    def remove_h2(self, mol_s, dt):
        requested = max(0.0, mol_s) * dt
        removed = min(self.h2_mol, requested)
        self.h2_mol -= removed
        return removed / dt if dt > 0 else 0.0

    def is_full(self):
        return self.h2_mol >= self.capacity_mol

    def is_empty(self):
        return self.h2_mol <= 0.001

    def compute(self, dt):
        temperature_c = self.inputs["temperatura"].value or 25.0
        temperature_k = temperature_c + 273.15

        pressure_pa = (self.h2_mol * self.R * temperature_k) / self.volume_m3

        self.outputs.update({
            "hidrogenio_saida": self.outflow_request,
            "pressao_saida": pressure_pa,
            "temperatura_saida": temperature_c,
            "caudal_saida": self.outflow_request
        })

        self.sensors.update({
            "pressao": pressure_pa,
            "volume": self.h2_mol,
            "temperatura": temperature_c
        })


class CelulaCombustivel(Component):
    def compute(self, dt):
        h2_mol_s = self.inputs["caudal_hidrogenio"].value or 0.0
        pressure = self.inputs["pressao"].value or 0.0
        temperature = self.inputs["temperatura"].value or 25.0

        h2_kg_s = h2_mol_s * 0.002016
        efficiency = 0.60
        lhv_h2 = 120e6

        power = h2_kg_s * lhv_h2 * efficiency
        voltage = 48.0
        current = power / voltage if voltage > 0 else 0.0

        water_mol_s = h2_mol_s

        self.outputs.update({
            "caudal_H2O": water_mol_s,
            "corrente": current,
            "tensao": voltage,
            "potencia": power
        })

        self.sensors.update({
            "tensao": voltage,
            "corrente": current,
            "temperatura": temperature,
            "caudal_H2": h2_mol_s,
            "caudal_H2O": water_mol_s,
            "pressao": pressure,
            "potencia": power
        })


class Bateria(Component):
    def __init__(self, name, config):
        super().__init__(name, config)
        self.capacity_kwh = 10.0
        self.soc = 0.50
        self.max_charge_power = 2500.0
        self.max_discharge_power = 2500.0
        self.mode = "idle"

    def charge(self, power_w, dt):
        power_w = min(max(0.0, power_w), self.max_charge_power)
        energy_kwh = power_w * dt / 3600 / 1000
        available = self.capacity_kwh * (1 - self.soc)
        accepted = min(energy_kwh, available)

        self.soc += accepted / self.capacity_kwh
        return accepted * 1000 * 3600 / dt if dt > 0 else 0.0

    def discharge(self, power_w, dt):
        power_w = min(max(0.0, power_w), self.max_discharge_power)
        energy_kwh = power_w * dt / 3600 / 1000
        available = self.capacity_kwh * self.soc
        delivered = min(energy_kwh, available)

        self.soc -= delivered / self.capacity_kwh
        return delivered * 1000 * 3600 / dt if dt > 0 else 0.0

    def compute(self, dt):
        temperature = self.inputs["temperatura"].value or 25.0
        voltage = 48.0

        if self.mode == "charge":
            current = self.outputs.get("corrente", 0.0)
        elif self.mode == "discharge":
            current = -abs(self.outputs.get("corrente", 0.0))
        else:
            current = 0.0

        self.outputs.update({
            "tensao": voltage,
            "corrente": current
        })

        self.sensors.update({
            "tensao": voltage,
            "corrente": current,
            "temperatura": temperature,
            "soc": self.soc * 100
        })


class Rede(Component):
    def compute(self, dt):
        voltage = self.inputs["tensao"].value or 48.0
        current = self.inputs["corrente"].value or 0.0

        self.outputs.update({
            "tensao": voltage,
            "corrente": current
        })

        self.sensors.update({
            "tensao": voltage,
            "corrente": current,
            "potencia": voltage * current
        })