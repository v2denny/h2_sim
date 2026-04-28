import json
import random

from engine.components import (
    Painel,
    Eletrolisador,
    Tanque,
    CelulaCombustivel,
    Bateria,
    Rede
)
from engine.controller import Controller
from engine.logger import Logger


class Simulation:
    def __init__(self, config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = json.load(f)

        sim_cfg = self.config.get("simulation", {})

        self.time = 0.0
        self.dt = sim_cfg.get("time_step", 1.0)
        self.duration = sim_cfg.get("duration", 3600)
        self.max_history = sim_cfg.get("max_history", 500)

        seed = sim_cfg.get("random_seed", None)
        if seed is not None:
            random.seed(seed)

        c = self.config["components"]

        self.components = {
            "painel_fotovoltaico": Painel("painel_fotovoltaico", c["painel_fotovoltaico"]),
            "eletrolisador": Eletrolisador("eletrolisador", c["eletrolisador"]),
            "tanque": Tanque("tanque", c["tanque"]),
            "celula_combustivel": CelulaCombustivel("celula_combustivel", c["celula_combustivel"]),
            "bateria": Bateria("bateria", c["bateria"]),
            "rede": Rede("rede", c["rede"])
        }

        self.controller = Controller(self.components)
        self.logger = Logger(sim_cfg.get("log_file", "simulation_log.csv"))

        self.history = {
            "pv_power": [],
            "electrolyzer_power": [],
            "fuel_cell_power": [],
            "battery_soc": [],
            "battery_current": [],
            "tank_pressure": [],
            "tank_h2": [],
            "consumption_power": [],
            "h2_production": [],
            "h2_consumption": [],
            "bottling": [],
            "unserved_load": [],
            "pv_to_rede": [],
            "pv_to_eletrolisador": [],
            "pv_to_bateria": [],
            "fc_to_rede": [],
            "battery_to_rede": []
        }

    def step(self):
        dt = self.dt

        for comp in self.components.values():
            comp.update_inputs(self.time)

        self.components["painel_fotovoltaico"].compute(dt)
        self.components["rede"].compute(dt)
        self.components["bateria"].compute(dt)
        self.components["tanque"].compute(dt)
        self.components["celula_combustivel"].compute(dt)
        self.components["eletrolisador"].compute(dt)

        self.controller.step(dt)

        self.components["tanque"].compute(dt)
        self.components["bateria"].compute(dt)
        self.components["rede"].compute(dt)

        self.store_history()
        self.logger.log(self.time, self.components, self.controller.state)

        self.time += dt

    def store_history(self):
        c = self.components
        s = self.controller.state

        values = {
            "pv_power": c["painel_fotovoltaico"].outputs["potencia"],
            "electrolyzer_power": c["eletrolisador"].sensors["potencia"],
            "fuel_cell_power": c["celula_combustivel"].outputs["potencia"],
            "battery_soc": c["bateria"].soc * 100,
            "battery_current": c["bateria"].outputs["corrente"],
            "tank_pressure": c["tanque"].sensors["pressao"],
            "tank_h2": c["tanque"].h2_mol,
            "consumption_power": c["rede"].sensors["potencia"],
            "h2_production": c["eletrolisador"].outputs["hidrogenio"],
            "h2_consumption": c["celula_combustivel"].inputs["caudal_hidrogenio"].value,
            "bottling": s["bottling"],
            "unserved_load": s["unserved_load"],
            "pv_to_rede": s["pv_to_rede"],
            "pv_to_eletrolisador": s["pv_to_eletrolisador"],
            "pv_to_bateria": s["pv_to_bateria"],
            "fc_to_rede": s["fc_to_rede"],
            "battery_to_rede": s["battery_to_rede"]
        }

        for key, value in values.items():
            self.history[key].append(value)
            if len(self.history[key]) > self.max_history:
                self.history[key].pop(0)