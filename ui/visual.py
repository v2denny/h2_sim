import math
import pygame

from ui.widgets import TextBox, Button


EDITABLES = {
    "Environment": {
        "Solar radiation": ("environment.solar_radiation_w_m2", "W/m²"),
        "Ambient temp": ("environment.ambient_temperature_c", "°C"),
        "Grid demand": ("environment.grid_demand_w", "W")
    },

    "Live state": {
        "Tank level": ("state.tank_level_percent", "%"),
        "Battery SOC": ("state.battery_soc_percent", "%")
    },

    "PV specs": {
        "Panel area": ("specs.pv.area_m2", "m²"),
        "PV efficiency": ("specs.pv.efficiency_ref", "0-1"),
        "PV temp coeff": ("specs.pv.temperature_coefficient_per_c", "1/°C"),
        "PV voltage": ("specs.pv.nominal_voltage_v", "V"),
        "DC efficiency": ("specs.pv.dc_system_efficiency", "0-1")
    },

    "Electrolyzer specs": {
        "Efficiency": ("specs.electrolyzer.efficiency", "0-1"),
        "H2 prod.": ("specs.electrolyzer.h2_production_mol_s", "mol/s"),
        "Min power": ("specs.electrolyzer.min_power_w", "W"),
        "Max power": ("specs.electrolyzer.max_power_w", "W"),
        "Voltage": ("specs.electrolyzer.nominal_voltage_v", "V"),
        "Startup delay": ("specs.electrolyzer.startup_delay_s", "s")
    },

    "Tank specs": {
        "Tank capacity": ("specs.tank.capacity_mol", "mol"),
        "Max pressure": ("specs.tank.max_pressure_bar", "bar"),
        "High stop": ("specs.tank.high_stop_percent", "%"),
        "Low warning": ("specs.tank.low_warning_percent", "%")
    },

    "Fuel cell specs": {
        "Efficiency": ("specs.fuel_cell.efficiency", "0-1"),
        "Max power": ("specs.fuel_cell.max_power_w", "W"),
        "Voltage": ("specs.fuel_cell.nominal_voltage_v", "V"),
        "Min tank pressure": ("specs.fuel_cell.min_tank_pressure_bar", "bar"),
        "Startup delay": ("specs.fuel_cell.startup_delay_s", "s")
    },

    "Battery specs": {
        "Capacity": ("specs.battery.capacity_kwh", "kWh"),
        "Max charge": ("specs.battery.max_charge_power_w", "W"),
        "Max discharge": ("specs.battery.max_discharge_power_w", "W"),
        "Charge eff.": ("specs.battery.charge_efficiency", "0-1"),
        "Discharge eff.": ("specs.battery.discharge_efficiency", "0-1"),
        "Min SOC": ("specs.battery.min_soc_percent", "%"),
        "Max SOC": ("specs.battery.max_soc_percent", "%")
    },

    "Bottling specs": {
        "Flow": ("specs.bottling.flow_mol_s", "mol/s")
    }
}


CARDS = [
    ("PV", [
        ("pv_power_w", "Power", "W"),
        ("pv_to_grid_w", "To grid", "W"),
        ("pv_to_electrolyzer_w", "To electrolyzer", "W"),
        ("pv_to_battery_w", "To battery", "W")
    ]),

    ("Electrolyzer", [
        ("electrolyzer_power_w", "Power", "W"),
        ("electrolyzer_running", "Running", ""),
        ("h2_production_mol_s", "H2 prod", "mol/s"),
        ("electrolyzer_h2_setpoint_mol_s", "H2 set", "mol/s")
    ]),

    ("Tank", [
        ("tank_h2_mol", "H2 stored", "mol"),
        ("tank_level_percent", "Level", "%"),
        ("tank_pressure_bar", "Pressure", "bar"),
        ("tank_volume_m3", "Volume", "m³")
    ]),

    ("Fuel Cell", [
        ("fuel_cell_power_w", "Power", "W"),
        ("fuel_cell_to_grid_w", "To grid", "W"),
        ("fuel_cell_to_battery_w", "To battery", "W"),
        ("h2_consumption_mol_s", "H2 used", "mol/s")
    ]),

    ("Battery", [
        ("battery_soc_percent", "SOC", "%"),
        ("battery_charge_power_w", "Charge", "W"),
        ("battery_to_grid_w", "To grid", "W"),
        ("battery_min_limit", "Min lock", "")
    ]),

    ("Grid", [
        ("grid_demand_w", "Demand", "W"),
        ("grid_supplied_w", "Supplied", "W"),
        ("unmet_demand_w", "Unmet", "W"),
        ("unused_power_w", "Unused", "W")
    ]),

    ("Bottling", [
        ("bottling_mol_s", "Flow", "mol/s"),
        ("bottling_auto", "Auto", ""),
        ("tank_h2_mol", "Tank H2", "mol"),
        ("tank_level_percent", "Tank level", "%")
    ])
]


GRAPHS = [
    ("pv_power_w", "PV Power", "W"),
    ("pv_to_grid_w", "PV → Grid", "W"),
    ("pv_to_electrolyzer_w", "PV → Electrolyzer", "W"),
    ("pv_to_battery_w", "PV → Battery", "W"),
    ("grid_supplied_w", "Grid Supplied", "W"),
    ("unmet_demand_w", "Unmet Demand", "W"),
    ("h2_production_mol_s", "H2 Production", "mol/s"),
    ("h2_consumption_mol_s", "H2 Consumption", "mol/s"),
    ("tank_level_percent", "Tank Level", "%"),
    ("battery_soc_percent", "Battery SOC", "%"),
    ("fuel_cell_to_battery_w", "Fuel Cell → Battery", "W"),
    ("bottling_mol_s", "Bottling", "mol/s")
]


MACHINE_LABELS = {
    "pv": "PV",
    "electrolyzer": "ELET",
    "tank": "TANK",
    "fuel_cell": "FC",
    "battery": "BAT",
    "grid": "GRID",
    "bottling": "BOT"
}


ACTIVE_KEYS = {
    "pv": "pv_active",
    "electrolyzer": "electrolyzer_active",
    "tank": "tank_active",
    "fuel_cell": "fuel_cell_active",
    "battery": "battery_active",
    "grid": "grid_active",
    "bottling": "bottling_active"
}


class Visual:
    def __init__(self, twin):
        pygame.init()

        self.twin = twin
        self.width = 1200
        self.height = 750

        self.screen = pygame.display.set_mode((self.width, self.height), pygame.RESIZABLE)
        pygame.display.set_caption("Hydrogen Digital Twin")

        self.font = pygame.font.SysFont(None, 17)
        self.big_font = pygame.font.SysFont(None, 22)
        self.small_font = pygame.font.SysFont(None, 14)

        self.scroll = 0
        self.textboxes = {}
        self.machine_rects = {}

        self.reset_button = Button(1030, 10, 120, 30, "RESET")
        self.reset_requested = False

        self.create_textboxes()

    def create_textboxes(self):
        for section, fields in EDITABLES.items():
            for _, (path, _) in fields.items():
                self.textboxes[path] = TextBox(0, 0, 82, 20, self.twin.get_value(path))

    def sync_textboxes(self):
        for path, tb in self.textboxes.items():
            tb.set_text(self.fmt(self.twin.get_value(path)))

    def handle_events(self, events):
        mouse_x, _ = pygame.mouse.get_pos()
        self.reset_requested = False

        self.reset_button.rect.x = self.width - 145
        self.reset_button.rect.y = 10

        for event in events:
            if event.type == pygame.VIDEORESIZE:
                self.width = max(1020, event.w)
                self.height = max(650, event.h)
                self.screen = pygame.display.set_mode((self.width, self.height), pygame.RESIZABLE)

            if event.type == pygame.MOUSEWHEEL and mouse_x < 310:
                self.scroll += event.y * 22
                self.scroll = min(0, self.scroll)

            self.reset_button.handle_event(event)

            if self.reset_button.clicked:
                self.reset_requested = True

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                for machine_name, rect in self.machine_rects.items():
                    if rect.collidepoint(event.pos):
                        self.twin.toggle_machine(machine_name)

            for tb in self.textboxes.values():
                tb.handle_event(event)

    def apply_inputs(self):
        for path, tb in self.textboxes.items():
            if not tb.consume_dirty():
                continue

            val = tb.value()
            if val is not None:
                self.twin.set_value(path, val)

    def fmt(self, value):
        try:
            value = float(value)
        except Exception:
            return str(value)

        if abs(value) >= 100000:
            return f"{value:.2e}"
        if abs(value) >= 1000:
            return f"{value:.0f}"
        if abs(value) >= 100:
            return f"{value:.1f}"
        if abs(value) >= 10:
            return f"{value:.2f}"
        return f"{value:.3f}"

    def draw_header(self, paused):
        status = "PAUSED" if paused else "RUNNING"
        color = (255, 210, 80) if paused else (80, 255, 100)

        title = self.big_font.render(
            f"Hydrogen Energy Digital Twin | elapsed = {self.twin.time_s:.0f} s | {status} | SPACE = pause",
            True,
            color
        )
        self.screen.blit(title, (20, 12))

        self.reset_button.draw(self.screen, self.font)

    def draw_inputs(self):
        panel = pygame.Rect(10, 45, 300, self.height - 55)

        pygame.draw.rect(self.screen, (35, 35, 35), panel)
        pygame.draw.rect(self.screen, (150, 150, 150), panel, 2)

        y = 60 + self.scroll

        for section, fields in EDITABLES.items():
            if 40 < y < self.height - 20:
                self.screen.blit(self.big_font.render(section, True, (255, 255, 255)), (22, y))

            y += 27

            for label, (path, unit) in fields.items():
                if 40 < y < self.height - 20:
                    self.screen.blit(self.font.render(label, True, (230, 230, 230)), (22, y + 4))

                    tb = self.textboxes[path]
                    tb.rect.x = 145
                    tb.rect.y = y
                    tb.draw(self.screen, self.font)

                    self.screen.blit(self.small_font.render(unit, True, (180, 180, 180)), (232, y + 6))

                y += 25

            y += 10

    def draw_cards(self):
        x = 325
        y = 50
        w = 190
        h = 105
        gap = 8

        for i, (title, items) in enumerate(CARDS):
            col = i % 2
            row = i // 2

            bx = x + col * (w + gap)
            by = y + row * (h + gap)

            pygame.draw.rect(self.screen, (200, 200, 200), (bx, by, w, h))
            pygame.draw.rect(self.screen, (255, 255, 255), (bx, by, w, h), 2)

            self.screen.blit(self.big_font.render(title, True, (0, 0, 0)), (bx + 6, by + 5))

            yy = by + 27
            for key, label, unit in items:
                val = self.twin.latest.get(key, 0)

                if key.endswith("_running") or key.endswith("_limit") or key.endswith("_auto"):
                    val_txt = "YES" if val >= 0.5 else "NO"
                else:
                    val_txt = self.fmt(val)

                txt = f"{label}: {val_txt} {unit}"
                color = (0, 100, 0) if isinstance(val, (int, float)) and val > 0 else (0, 0, 0)

                self.screen.blit(self.font.render(txt, True, color), (bx + 6, yy))
                yy += 15

    def machine_is_active(self, machine):
        active_key = ACTIVE_KEYS[machine]

        if not self.twin.machine_enabled(machine):
            return False

        return self.twin.latest.get(active_key, 0.0) >= 0.5

    def node_color(self, machine):
        return (60, 190, 80) if self.machine_is_active(machine) else (190, 60, 60)

    def draw_node(self, machine, x, y, w=88, h=50):
        rect = pygame.Rect(x, y, w, h)
        self.machine_rects[machine] = rect

        pygame.draw.rect(self.screen, self.node_color(machine), rect, border_radius=9)
        pygame.draw.rect(self.screen, (240, 240, 240), rect, 2, border_radius=9)

        label = MACHINE_LABELS[machine]
        text = self.big_font.render(label, True, (255, 255, 255))
        self.screen.blit(text, (x + 16, y + 11))

        status = "ON" if self.machine_is_active(machine) else "OFF"
        status_text = self.small_font.render(status, True, (255, 255, 255))
        self.screen.blit(status_text, (x + 28, y + 32))

    def draw_arrow(self, start, end):
        pygame.draw.line(self.screen, (210, 210, 210), start, end, 3)

        sx, sy = start
        ex, ey = end

        if abs(ex - sx) >= abs(ey - sy):
            if ex >= sx:
                points = [(ex, ey), (ex - 10, ey - 6), (ex - 10, ey + 6)]
            else:
                points = [(ex, ey), (ex + 10, ey - 6), (ex + 10, ey + 6)]
        else:
            if ey >= sy:
                points = [(ex, ey), (ex - 6, ey - 10), (ex + 6, ey - 10)]
            else:
                points = [(ex, ey), (ex - 6, ey + 10), (ex + 6, ey + 10)]

        pygame.draw.polygon(self.screen, (210, 210, 210), points)

    def draw_system_diagram(self):
        self.machine_rects = {}

        x = max(745, self.width - 430)
        y = 50

        panel = pygame.Rect(x - 14, y - 12, 405, 330)
        pygame.draw.rect(self.screen, (40, 40, 40), panel)
        pygame.draw.rect(self.screen, (150, 150, 150), panel, 2)

        self.screen.blit(
            self.big_font.render("System ON/OFF + Auto Status", True, (255, 255, 255)),
            (x, y - 2)
        )
        self.screen.blit(
            self.small_font.render(
                "click machine to toggle | green = active, red = off/idle/safety-stop",
                True,
                (190, 190, 190)
            ),
            (x, y + 22)
        )

        pv = (x, y + 65)
        grid = (x + 285, y + 65)
        elet = (x, y + 155)
        tank = (x + 140, y + 155)
        bot = (x + 285, y + 155)
        fc = (x + 140, y + 245)
        bat = (x + 285, y + 245)

        self.draw_arrow((pv[0] + 88, pv[1] + 14), (grid[0], grid[1] + 14))
        self.draw_arrow((pv[0] + 44, pv[1] + 50), (elet[0] + 44, elet[1]))
        self.draw_arrow((pv[0] + 88, pv[1] + 40), (bat[0], bat[1] + 12))

        self.draw_arrow((elet[0] + 88, elet[1] + 25), (tank[0], tank[1] + 25))
        self.draw_arrow((tank[0] + 44, tank[1] + 50), (fc[0] + 44, fc[1]))
        self.draw_arrow((tank[0] + 88, tank[1] + 25), (bot[0], bot[1] + 25))

        self.draw_arrow((fc[0] + 88, fc[1] + 13), (grid[0], grid[1] + 40))
        self.draw_arrow((fc[0] + 88, fc[1] + 34), (bat[0], bat[1] + 34))
        self.draw_arrow((bat[0] + 44, bat[1]), (grid[0] + 44, grid[1] + 50))

        self.draw_node("pv", *pv)
        self.draw_node("grid", *grid)
        self.draw_node("electrolyzer", *elet)
        self.draw_node("tank", *tank)
        self.draw_node("bottling", *bot)
        self.draw_node("fuel_cell", *fc)
        self.draw_node("battery", *bat)

    def draw_graph(self, key, x, y, w, h, label, unit):
        data = self.twin.history.get(key, [])

        pygame.draw.rect(self.screen, (50, 50, 50), (x, y, w, h))
        pygame.draw.rect(self.screen, (150, 150, 150), (x, y, w, h), 1)

        self.screen.blit(self.small_font.render(label, True, (255, 255, 255)), (x + 4, y + 3))

        if len(data) < 2:
            return

        min_v = min(data)
        max_v = max(data)

        if math.isclose(min_v, max_v):
            max_v = min_v + 1

        points = []

        for i, value in enumerate(data):
            px = x + int(i * (w - 8) / max(1, len(data) - 1)) + 4
            py = y + h - 6 - int((value - min_v) / (max_v - min_v) * (h - 24))
            points.append((px, py))

        pygame.draw.lines(self.screen, (0, 230, 0), False, points, 2)

        latest = data[-1]
        self.screen.blit(
            self.small_font.render(f"{self.fmt(latest)} {unit}", True, (255, 255, 255)),
            (x + w - 90, y + 3)
        )

    def draw_graphs(self):
        x = 325
        y = 510

        available_w = self.width - x - 20
        w = max(210, (available_w - 24) // 3)
        h = 52
        gap_x = 12
        gap_y = 6

        for i, (key, label, unit) in enumerate(GRAPHS):
            col = i % 3
            row = i // 3

            gx = x + col * (w + gap_x)
            gy = y + row * (h + gap_y)

            if gy + h < self.height - 10:
                self.draw_graph(key, gx, gy, w, h, label, unit)

    def update(self, events, paused=False):
        self.handle_events(events)
        self.apply_inputs()

        self.screen.fill((30, 30, 30))

        self.draw_header(paused)
        self.draw_inputs()
        self.draw_cards()
        self.draw_system_diagram()
        self.draw_graphs()

        pygame.display.flip()

        return self.reset_requested