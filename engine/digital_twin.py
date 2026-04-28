import json
from engine.logger import Logger


R_IDEAL_GAS = 8.314462618
H2_LHV_J_PER_KG = 120_000_000
H2_MOLAR_MASS_KG_PER_MOL = 0.002016
BAR_TO_PA = 100000


class DigitalTwin:
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.load_config()
        self.reset()

    def load_config(self):
        with open(self.config_path, "r", encoding="utf-8") as f:
            self.config = json.load(f)

        self.sim_cfg = self.config["simulation"]
        self.env = self.config["environment"]
        self.specs = self.config["specs"]
        self.machines = self.config["machines"]

        self.dt = float(self.sim_cfg["time_step_s"])
        self.max_history = int(self.sim_cfg.get("max_history", 600))
        self.logger = Logger(self.sim_cfg.get("log_file", "simulation_log.csv"))

    def reset(self):
        for name in self.machines:
            self.machines[name] = False

        self.time_s = 0.0
        self.tank_h2_mol = 0.0
        self.battery_soc = 0.0

        self.specs["tank"]["initial_h2_mol"] = 0
        self.specs["battery"]["initial_soc_percent"] = 0

        self.runtime = {
            "electrolyzer_on_timer_s": 0.0,
            "fuel_cell_on_timer_s": 0.0
        }

        self.grid_tank_depleted_lockout = False
        self.latest = {}
        self.history = {}

    # ------------------------------------------------------------
    # UI/control interface
    # ------------------------------------------------------------
    def set_value(self, path: str, value: float):
        if path == "state.tank_level_percent":
            percent = max(0.0, min(100.0, float(value)))
            self.tank_h2_mol = self.tank_capacity_mol() * percent / 100.0
            self.specs["tank"]["initial_h2_mol"] = self.tank_h2_mol

            if self.tank_h2_mol > 0:
                self.grid_tank_depleted_lockout = False

            self.clamp_states()
            return

        if path == "state.battery_soc_percent":
            percent = max(0.0, min(100.0, float(value)))
            self.battery_soc = percent / 100.0
            self.specs["battery"]["initial_soc_percent"] = percent
            self.clamp_states()
            return

        parts = path.split(".")
        target = self.config

        for p in parts[:-1]:
            target = target[p]

        target[parts[-1]] = value

        self.env = self.config["environment"]
        self.specs = self.config["specs"]
        self.machines = self.config["machines"]

        self.clamp_states()

        if self.tank_h2_mol > 0:
            self.grid_tank_depleted_lockout = False

    def get_value(self, path: str):
        if path == "state.tank_level_percent":
            return self.tank_level_percent()

        if path == "state.battery_soc_percent":
            return self.battery_soc * 100.0

        parts = path.split(".")
        target = self.config

        for p in parts:
            target = target[p]

        return target

    def toggle_machine(self, machine_name: str):
        if machine_name in self.machines:
            self.machines[machine_name] = not self.machines[machine_name]

            if machine_name == "electrolyzer" and not self.machines[machine_name]:
                self.runtime["electrolyzer_on_timer_s"] = 0.0

            if machine_name == "fuel_cell" and not self.machines[machine_name]:
                self.runtime["fuel_cell_on_timer_s"] = 0.0

            if machine_name == "grid":
                self.grid_tank_depleted_lockout = False

    def machine_enabled(self, name: str):
        return bool(self.machines.get(name, False))

    def auto_on(self, name: str):
        if bool(self.specs.get("controller", {}).get("auto_start_dependencies", True)):
            self.machines[name] = True

    def auto_off_all_except_grid(self):
        for name in self.machines:
            self.machines[name] = (name == "grid")

        self.runtime["electrolyzer_on_timer_s"] = 0.0
        self.runtime["fuel_cell_on_timer_s"] = 0.0

    # ------------------------------------------------------------
    # State helpers
    # ------------------------------------------------------------
    def clamp_states(self):
        tank_capacity = self.tank_capacity_mol()

        min_soc = max(0.0, float(self.specs["battery"].get("min_soc_percent", 0.0)) / 100.0)
        max_soc = min(1.0, float(self.specs["battery"].get("max_soc_percent", 100.0)) / 100.0)

        self.tank_h2_mol = max(0.0, min(self.tank_h2_mol, tank_capacity))
        self.battery_soc = max(0.0, min(self.battery_soc, max_soc))

        if self.battery_soc < min_soc:
            self.battery_soc = min_soc

    def tank_capacity_mol(self):
        return max(0.001, float(self.specs["tank"]["capacity_mol"]))

    def tank_level_percent(self):
        return 100.0 * self.tank_h2_mol / self.tank_capacity_mol()

    def computed_tank_volume_m3(self):
        capacity_mol = self.tank_capacity_mol()
        max_pressure_bar = max(0.001, float(self.specs["tank"]["max_pressure_bar"]))
        max_pressure_pa = max_pressure_bar * BAR_TO_PA
        temperature_k = float(self.env["ambient_temperature_c"]) + 273.15

        return capacity_mol * R_IDEAL_GAS * temperature_k / max_pressure_pa

    def tank_pressure_bar(self):
        if not self.machine_enabled("tank"):
            return 0.0

        volume_m3 = self.computed_tank_volume_m3()
        temperature_k = float(self.env["ambient_temperature_c"]) + 273.15

        pressure_pa = self.tank_h2_mol * R_IDEAL_GAS * temperature_k / volume_m3
        pressure_bar = pressure_pa / BAR_TO_PA

        max_pressure_bar = float(self.specs["tank"]["max_pressure_bar"])
        return min(max(0.0, pressure_bar), max_pressure_bar)

    def tank_is_full(self):
        if not self.machine_enabled("tank"):
            return False

        capacity = self.tank_capacity_mol()
        high_stop_percent = float(self.specs["tank"].get("high_stop_percent", 100.0))
        high_stop_mol = capacity * high_stop_percent / 100.0

        pressure_bar = self.tank_pressure_bar()
        max_pressure_bar = float(self.specs["tank"]["max_pressure_bar"])

        return (
            self.tank_h2_mol >= high_stop_mol
            or self.tank_h2_mol >= capacity
            or pressure_bar >= max_pressure_bar * 0.999
        )

    def tank_can_store(self):
        if not self.machine_enabled("tank"):
            return False

        return not self.tank_is_full()

    def tank_available_for_fuel_cell(self):
        if not self.machine_enabled("tank"):
            return False

        if self.tank_h2_mol <= 0:
            return False

        min_pressure = float(self.specs["fuel_cell"].get("min_tank_pressure_bar", 5.0))
        low_warning_percent = float(self.specs["tank"].get("low_warning_percent", 5.0))

        if self.tank_pressure_bar() < min_pressure:
            return False

        if self.tank_level_percent() <= low_warning_percent:
            return False

        return True

    def battery_can_charge(self):
        if not self.machine_enabled("battery"):
            return False

        max_soc = float(self.specs["battery"].get("max_soc_percent", 100.0)) / 100.0
        return self.battery_soc < max_soc

    def battery_can_discharge(self):
        if not self.machine_enabled("battery"):
            return False

        min_soc = float(self.specs["battery"].get("min_soc_percent", 0.0)) / 100.0
        return self.battery_soc > min_soc

    # ------------------------------------------------------------
    # Physical models
    # ------------------------------------------------------------
    def pv_power(self):
        if not self.machine_enabled("pv"):
            return 0.0, 0.0, 0.0, 0.0

        pv = self.specs["pv"]

        radiation = max(0.0, float(self.env["solar_radiation_w_m2"]))
        ambient_temp = float(self.env["ambient_temperature_c"])

        area = max(0.0, float(pv["area_m2"]))
        efficiency_ref = max(0.0, float(pv["efficiency_ref"]))
        temp_coeff = float(pv["temperature_coefficient_per_c"])
        t_ref = float(pv["reference_temperature_c"])
        system_eff = max(0.0, min(1.0, float(pv.get("dc_system_efficiency", 1.0))))

        efficiency = efficiency_ref * (1 + temp_coeff * (ambient_temp - t_ref))
        efficiency = max(0.0, efficiency)

        power = radiation * area * efficiency * system_eff
        voltage = max(0.001, float(pv["nominal_voltage_v"]))
        current = power / voltage

        return power, voltage, current, efficiency * system_eff

    def electrolyzer_h2_production(self, available_power_w):
        if not self.machine_enabled("electrolyzer"):
            self.runtime["electrolyzer_on_timer_s"] = 0.0
            return 0.0, 0.0, 0.0, 0.0, False

        el = self.specs["electrolyzer"]

        min_power = max(0.0, float(el["min_power_w"]))
        max_power = max(0.0, float(el["max_power_w"]))
        voltage = max(0.001, float(el["nominal_voltage_v"]))
        startup_delay = max(0.0, float(el.get("startup_delay_s", 0.0)))
        h2_setpoint = max(0.0, float(el.get("h2_production_mol_s", 0.0)))

        if available_power_w < min_power or h2_setpoint <= 0:
            self.runtime["electrolyzer_on_timer_s"] = 0.0
            return 0.0, 0.0, 0.0, 0.0, False

        self.runtime["electrolyzer_on_timer_s"] += self.dt

        if self.runtime["electrolyzer_on_timer_s"] < startup_delay:
            return 0.0, 0.0, 0.0, 0.0, True

        used_power = min(available_power_w, max_power)
        h2_mol_s = h2_setpoint
        current = used_power / voltage
        water_mol_s = h2_mol_s * float(el.get("water_per_h2_mol", 1.0))

        return used_power, h2_mol_s, water_mol_s, current, True

    def fuel_cell_from_requested_power(self, requested_power_w):
        if not self.machine_enabled("fuel_cell"):
            self.runtime["fuel_cell_on_timer_s"] = 0.0
            return 0.0, 0.0, 0.0, 0.0, False

        if not self.tank_available_for_fuel_cell():
            self.runtime["fuel_cell_on_timer_s"] = 0.0
            return 0.0, 0.0, 0.0, 0.0, False

        fc = self.specs["fuel_cell"]

        efficiency = max(0.0, min(1.0, float(fc["efficiency"])))
        max_power = max(0.0, float(fc["max_power_w"]))
        voltage = max(0.001, float(fc["nominal_voltage_v"]))
        startup_delay = max(0.0, float(fc.get("startup_delay_s", 0.0)))

        target_power = min(max(0.0, requested_power_w), max_power)

        if target_power <= 0:
            self.runtime["fuel_cell_on_timer_s"] = 0.0
            return 0.0, 0.0, 0.0, 0.0, False

        self.runtime["fuel_cell_on_timer_s"] += self.dt

        if self.runtime["fuel_cell_on_timer_s"] < startup_delay:
            return 0.0, 0.0, 0.0, 0.0, True

        if efficiency <= 0:
            return 0.0, 0.0, 0.0, 0.0, False

        h2_kg_s_needed = target_power / (H2_LHV_J_PER_KG * efficiency)
        h2_mol_s_needed = h2_kg_s_needed / H2_MOLAR_MASS_KG_PER_MOL

        available_h2_mol_s = self.tank_h2_mol / self.dt
        actual_h2_mol_s = min(h2_mol_s_needed, available_h2_mol_s)

        actual_h2_kg_s = actual_h2_mol_s * H2_MOLAR_MASS_KG_PER_MOL
        power = actual_h2_kg_s * H2_LHV_J_PER_KG * efficiency

        self.tank_h2_mol -= actual_h2_mol_s * self.dt
        self.tank_h2_mol = max(0.0, self.tank_h2_mol)

        current = power / voltage
        water_mol_s = actual_h2_mol_s

        return power, actual_h2_mol_s, water_mol_s, current, True

    def charge_battery(self, available_power_w):
        if not self.battery_can_charge():
            return 0.0

        b = self.specs["battery"]

        capacity_kwh = max(0.001, float(b["capacity_kwh"]))
        max_charge = max(0.0, float(b["max_charge_power_w"]))
        efficiency = max(0.0, min(1.0, float(b["charge_efficiency"])))
        max_soc = min(1.0, float(b.get("max_soc_percent", 100.0)) / 100.0)

        power_in = min(max(0.0, available_power_w), max_charge)

        energy_in_kwh = power_in * self.dt / 3600.0 / 1000.0
        stored_energy_kwh = energy_in_kwh * efficiency

        remaining_capacity_kwh = capacity_kwh * (max_soc - self.battery_soc)
        actual_stored_kwh = min(stored_energy_kwh, remaining_capacity_kwh)

        self.battery_soc += actual_stored_kwh / capacity_kwh

        if efficiency <= 0:
            return 0.0

        actual_input_power = actual_stored_kwh / efficiency * 1000.0 * 3600.0 / self.dt
        return actual_input_power

    def discharge_battery(self, requested_power_w):
        if not self.battery_can_discharge():
            return 0.0

        b = self.specs["battery"]

        capacity_kwh = max(0.001, float(b["capacity_kwh"]))
        max_discharge = max(0.0, float(b["max_discharge_power_w"]))
        efficiency = max(0.0, min(1.0, float(b["discharge_efficiency"])))
        min_soc = max(0.0, float(b.get("min_soc_percent", 0.0)) / 100.0)

        requested = min(max(0.0, requested_power_w), max_discharge)

        usable_stored_kwh = capacity_kwh * max(0.0, self.battery_soc - min_soc)
        required_stored_kwh = requested * self.dt / 3600.0 / 1000.0 / efficiency

        actual_used_stored_kwh = min(required_stored_kwh, usable_stored_kwh)
        self.battery_soc -= actual_used_stored_kwh / capacity_kwh

        delivered_power = actual_used_stored_kwh * efficiency * 1000.0 * 3600.0 / self.dt
        return delivered_power

    # ------------------------------------------------------------
    # Main plant logic
    # ------------------------------------------------------------
    def step(self):
        self.clamp_states()

        if self.tank_h2_mol > 0:
            self.grid_tank_depleted_lockout = False

        demand_w = max(0.0, float(self.env["grid_demand_w"])) if self.machine_enabled("grid") else 0.0

        if self.machine_enabled("pv"):
            self.auto_on("tank")
            self.auto_on("electrolyzer")

        if self.machine_enabled("grid"):
            if self.machine_enabled("pv"):
                self.auto_on("tank")
                self.auto_on("electrolyzer")

            else:
                if self.tank_h2_mol > 0 and not self.grid_tank_depleted_lockout:
                    self.auto_on("tank")
                    self.auto_on("fuel_cell")
                elif self.tank_h2_mol <= 0 and not self.grid_tank_depleted_lockout:
                    self.auto_on("battery")

        pv_power, pv_voltage, pv_current, pv_eff = self.pv_power()

        pv_to_grid = 0.0
        pv_to_electrolyzer = 0.0
        pv_to_battery = 0.0
        fuel_cell_to_grid = 0.0
        fuel_cell_to_battery = 0.0
        battery_to_grid = 0.0
        unused_power = 0.0

        electrolyzer_power = 0.0
        h2_production_mol_s = 0.0
        electrolyzer_water_mol_s = 0.0
        electrolyzer_current = 0.0
        electrolyzer_running = False

        fuel_cell_power = 0.0
        fuel_cell_current = 0.0
        h2_consumption_mol_s = 0.0
        fuel_cell_water_mol_s = 0.0
        fuel_cell_running = False

        bottling_mol_s = 0.0
        auto_bottling = False

        remaining_demand = demand_w

        pv_to_grid = min(pv_power, remaining_demand)
        remaining_demand -= pv_to_grid
        excess_pv = pv_power - pv_to_grid

        if self.machine_enabled("grid") and remaining_demand > 0:
            if self.machine_enabled("pv"):
                self.auto_on("tank")
                self.auto_on("electrolyzer")
                if self.tank_h2_mol > 0:
                    self.auto_on("fuel_cell")

            elif self.tank_h2_mol > 0 and not self.grid_tank_depleted_lockout:
                self.auto_on("tank")
                self.auto_on("fuel_cell")

            elif self.tank_h2_mol <= 0 and not self.grid_tank_depleted_lockout:
                self.auto_on("battery")

        if excess_pv > 0 and self.machine_enabled("electrolyzer"):
            if self.tank_can_store():
                used_power, produced_h2, water, current, running = self.electrolyzer_h2_production(excess_pv)

                produced_mol = produced_h2 * self.dt
                free_capacity = max(0.0, self.tank_capacity_mol() - self.tank_h2_mol)
                stored_mol = min(produced_mol, free_capacity)

                self.tank_h2_mol += stored_mol

                overflow_mol = max(0.0, produced_mol - stored_mol)

                if overflow_mol > 0 and self.machine_enabled("bottling") and not self.machine_enabled("fuel_cell"):
                    bottling_mol_s += overflow_mol / self.dt

                electrolyzer_power += used_power
                pv_to_electrolyzer += used_power
                h2_production_mol_s += produced_h2
                electrolyzer_water_mol_s += water
                electrolyzer_current += current
                electrolyzer_running = running and used_power > 0 and stored_mol > 0

                excess_pv -= used_power

            elif self.tank_is_full():
                self.auto_on("bottling")

                if self.machine_enabled("bottling") and not self.machine_enabled("fuel_cell"):
                    used_power, produced_h2, water, current, running = self.electrolyzer_h2_production(excess_pv)

                    bottling_mol_s += produced_h2

                    electrolyzer_power += used_power
                    pv_to_electrolyzer += used_power
                    h2_production_mol_s += produced_h2
                    electrolyzer_water_mol_s += water
                    electrolyzer_current += current
                    electrolyzer_running = running and used_power > 0

                    excess_pv -= used_power
                else:
                    self.runtime["electrolyzer_on_timer_s"] = 0.0
                    electrolyzer_running = False
            else:
                self.runtime["electrolyzer_on_timer_s"] = 0.0
                electrolyzer_running = False
        else:
            self.runtime["electrolyzer_on_timer_s"] = 0.0

        if excess_pv > 0:
            self.auto_on("battery")

        if excess_pv > 0 and self.machine_enabled("battery"):
            pv_to_battery = self.charge_battery(excess_pv)
            excess_pv -= pv_to_battery

        tank_h2_before_fc = self.tank_h2_mol

        if remaining_demand > 0:
            if self.tank_h2_mol > 0 and not self.grid_tank_depleted_lockout:
                self.auto_on("tank")
                self.auto_on("fuel_cell")

            (
                fuel_cell_power,
                h2_consumption_mol_s,
                fuel_cell_water_mol_s,
                fuel_cell_current,
                fuel_cell_running
            ) = self.fuel_cell_from_requested_power(remaining_demand)

            fuel_cell_to_grid = min(fuel_cell_power, remaining_demand)
            remaining_demand -= fuel_cell_to_grid

            extra_fc_power = max(0.0, fuel_cell_power - fuel_cell_to_grid)

            if extra_fc_power > 0:
                self.auto_on("battery")

            if extra_fc_power > 0 and self.machine_enabled("battery"):
                fuel_cell_to_battery = self.charge_battery(extra_fc_power)

        else:
            self.runtime["fuel_cell_on_timer_s"] = 0.0

            allow_fc_charge = bool(
                self.specs["controller"].get("fuel_cell_can_charge_battery_when_no_grid_demand", True)
            )

            if (
                allow_fc_charge
                and self.machine_enabled("fuel_cell")
                and self.machine_enabled("battery")
                and self.battery_can_charge()
                and self.tank_available_for_fuel_cell()
            ):
                target_power = min(
                    float(self.specs["fuel_cell"]["max_power_w"]),
                    float(self.specs["battery"]["max_charge_power_w"])
                )

                (
                    fuel_cell_power,
                    h2_consumption_mol_s,
                    fuel_cell_water_mol_s,
                    fuel_cell_current,
                    fuel_cell_running
                ) = self.fuel_cell_from_requested_power(target_power)

                if fuel_cell_power > 0:
                    fuel_cell_to_battery = self.charge_battery(fuel_cell_power)
                    fuel_cell_running = fuel_cell_to_battery > 0
                else:
                    fuel_cell_running = False

        low_warning_percent = float(self.specs["tank"].get("low_warning_percent", 5.0))
        tank_hit_low_warning = self.tank_level_percent() <= low_warning_percent

        tank_depleted_this_step = (
            self.machine_enabled("grid")
            and not self.machine_enabled("pv")
            and tank_h2_before_fc > 0
            and tank_hit_low_warning
        )

        if tank_depleted_this_step:
            self.grid_tank_depleted_lockout = True
            self.auto_off_all_except_grid()
            remaining_demand = max(0.0, demand_w - fuel_cell_to_grid)

        if remaining_demand > 0 and not self.grid_tank_depleted_lockout:
            self.auto_on("battery")

        if remaining_demand > 0 and self.machine_enabled("battery") and not self.grid_tank_depleted_lockout:
            battery_to_grid = self.discharge_battery(remaining_demand)
            remaining_demand -= battery_to_grid

        unused_power = max(0.0, excess_pv)

        self.clamp_states()

        if self.machine_enabled("fuel_cell"):
            bottling_mol_s = 0.0
            auto_bottling = False

        tank_pressure_bar = self.tank_pressure_bar()
        tank_volume_m3 = self.computed_tank_volume_m3()
        tank_level = self.tank_level_percent()

        tank_high_stop = self.tank_is_full()
        tank_pressure_limit = tank_pressure_bar >= float(self.specs["tank"]["max_pressure_bar"]) * 0.999

        battery_min_limit = self.battery_soc <= float(self.specs["battery"].get("min_soc_percent", 0.0)) / 100.0
        battery_max_limit = self.battery_soc >= float(self.specs["battery"].get("max_soc_percent", 100.0)) / 100.0

        grid_supplied_w = pv_to_grid + fuel_cell_to_grid + battery_to_grid
        unmet_demand_w = max(0.0, demand_w - grid_supplied_w)

        pv_active = self.machine_enabled("pv") and pv_power > 0
        electrolyzer_active = self.machine_enabled("electrolyzer") and electrolyzer_running and electrolyzer_power > 0
        tank_active = self.machine_enabled("tank")
        fuel_cell_active = self.machine_enabled("fuel_cell") and fuel_cell_running and fuel_cell_power > 0
        battery_active = self.machine_enabled("battery") and (fuel_cell_to_battery > 0 or pv_to_battery > 0 or battery_to_grid > 0)
        grid_active = self.machine_enabled("grid") and (demand_w > 0 or grid_supplied_w > 0)
        bottling_active = self.machine_enabled("bottling") and bottling_mol_s > 0

        self.latest = {
            "time_s": self.time_s,

            "pv_enabled": float(self.machine_enabled("pv")),
            "electrolyzer_enabled": float(self.machine_enabled("electrolyzer")),
            "tank_enabled": float(self.machine_enabled("tank")),
            "fuel_cell_enabled": float(self.machine_enabled("fuel_cell")),
            "battery_enabled": float(self.machine_enabled("battery")),
            "grid_enabled": float(self.machine_enabled("grid")),
            "bottling_enabled": float(self.machine_enabled("bottling")),

            "pv_active": float(pv_active),
            "electrolyzer_active": float(electrolyzer_active),
            "tank_active": float(tank_active),
            "fuel_cell_active": float(fuel_cell_active),
            "battery_active": float(battery_active),
            "grid_active": float(grid_active),
            "bottling_active": float(bottling_active),

            "solar_radiation_w_m2": self.env["solar_radiation_w_m2"],
            "ambient_temperature_c": self.env["ambient_temperature_c"],
            "grid_demand_w": demand_w,

            "pv_power_w": pv_power,
            "pv_voltage_v": pv_voltage,
            "pv_current_a": pv_current,
            "pv_efficiency_percent": pv_eff * 100.0,

            "pv_to_grid_w": pv_to_grid,
            "pv_to_electrolyzer_w": pv_to_electrolyzer,
            "pv_to_battery_w": pv_to_battery,
            "unused_power_w": unused_power,

            "electrolyzer_power_w": electrolyzer_power,
            "electrolyzer_running": float(electrolyzer_active),
            "h2_production_mol_s": h2_production_mol_s,
            "electrolyzer_h2_setpoint_mol_s": float(self.specs["electrolyzer"].get("h2_production_mol_s", 0.0)),
            "electrolyzer_water_mol_s": electrolyzer_water_mol_s,
            "electrolyzer_current_a": electrolyzer_current,

            "tank_h2_mol": self.tank_h2_mol,
            "tank_level_percent": tank_level,
            "tank_pressure_bar": tank_pressure_bar,
            "tank_volume_m3": tank_volume_m3,
            "tank_high_stop": float(tank_high_stop),
            "tank_pressure_limit": float(tank_pressure_limit),

            "fuel_cell_power_w": fuel_cell_power,
            "fuel_cell_running": float(fuel_cell_active),
            "fuel_cell_to_grid_w": fuel_cell_to_grid,
            "fuel_cell_to_battery_w": fuel_cell_to_battery,
            "fuel_cell_current_a": fuel_cell_current,
            "h2_consumption_mol_s": h2_consumption_mol_s,
            "fuel_cell_water_mol_s": fuel_cell_water_mol_s,

            "battery_soc_percent": self.battery_soc * 100.0,
            "battery_to_grid_w": battery_to_grid,
            "battery_charge_power_w": pv_to_battery + fuel_cell_to_battery,
            "battery_min_limit": float(battery_min_limit),
            "battery_max_limit": float(battery_max_limit),

            "grid_supplied_w": grid_supplied_w,
            "unmet_demand_w": unmet_demand_w,

            "bottling_mol_s": bottling_mol_s,
            "bottling_auto": float(auto_bottling)
        }

        self.store_history()
        self.logger.log(self.latest)

        self.time_s += self.dt

    def store_history(self):
        for key, value in self.latest.items():
            if isinstance(value, (int, float)):
                self.history.setdefault(key, [])
                self.history[key].append(value)

                if len(self.history[key]) > self.max_history:
                    self.history[key].pop(0)