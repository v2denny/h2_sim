# Hydrogen Energy Digital Twin Simulator

This project is a Python-based **digital twin simulator** for a hybrid renewable energy and hydrogen production system.

It simulates a system composed of:

* Photovoltaic solar panel
* Electrolyzer
* Hydrogen storage tank
* Fuel cell
* Battery storage
* Electrical grid/load
* Hydrogen bottling output

The simulator includes a real-time visual interface built with **Pygame**, where the user can:

* Turn machines ON/OFF by clicking them
* Change machine specifications
* Change environmental conditions
* Change starting tank and battery levels
* Watch calculated values update automatically
* View real-time graphs
* Pause, resume, and reset the simulation

---

## System Overview

The simulated system follows this architecture:

```text
Solar Panel ───────► Grid
     │
     ├─────────────► Electrolyzer ─────► Hydrogen Tank ─────► Fuel Cell ─────► Grid
     │                                      │                    │
     │                                      │                    └────────────► Battery
     │                                      │
     │                                      └────────────► Bottling
     │
     └─────────────► Battery ─────────────► Grid
```

The intended object relationships are:

```text
PV panel supplies: grid, electrolyzer, battery
Electrolyzer supplies: hydrogen tank
Hydrogen tank supplies: fuel cell
Hydrogen tank supplies: bottling when fuel cell is OFF
Fuel cell supplies: grid and battery
Battery supplies: grid
```

---

## Main Idea

This is not just a visual animation. It is intended to behave like a simplified **digital twin** of a hydrogen energy plant.

The user does not manually control every internal variable. Instead, the user controls:

* Environment values
* Machine specifications
* Starting storage levels
* Machine ON/OFF states

The simulator then calculates:

* Solar production
* Hydrogen production
* Tank pressure
* Tank level
* Fuel cell output
* Battery charge/discharge
* Grid supply
* Bottling flow
* Unmet demand

---

## Current Control Logic

### Scenario 1 — Solar production mode

If everything is OFF and the user turns ON the solar panel:

```text
PV ON
```

The simulator automatically turns ON:

```text
Electrolyzer
Tank
```

The solar panel feeds the electrolyzer and hydrogen is stored in the tank.

When the tank reaches its maximum level, bottling can start automatically, but only if the fuel cell is OFF.

---

### Scenario 2 — Grid demand with solar available

If the grid is ON and the solar panel is ON:

```text
Grid ON
PV ON
```

The solar panel first supplies the grid.

If PV power is not enough, the simulator can automatically start:

```text
Tank
Fuel Cell
Electrolyzer
```

The fuel cell uses hydrogen from the tank to help supply the grid.

If PV + fuel cell production is greater than the grid demand, the remaining power can be used to charge the battery.

---

### Scenario 3 — Grid demand with PV OFF and hydrogen available

If the grid is ON, PV is OFF, and the tank has hydrogen:

```text
Grid ON
PV OFF
Tank has H2
```

The simulator automatically starts:

```text
Tank
Fuel Cell
```

The fuel cell supplies the grid using hydrogen from the tank.

When the tank reaches the configured `low_warning_percent`, the system stops using the tank and shuts down everything except the grid.

If `low_warning_percent` is set to `0`, the tank will be used almost completely before stopping.

---

### Scenario 4 — Grid demand with PV OFF and tank empty

If the grid is ON, PV is OFF, and the tank is empty:

```text
Grid ON
PV OFF
Tank empty
```

The simulator automatically starts the battery if it has charge available.

```text
Battery → Grid
```

---

## User Interface

The interface has four main areas.

### 1. Left sidebar

The left sidebar contains editable parameters. It is scrollable.

You can change:

* Solar radiation
* Ambient temperature
* Grid demand
* Tank starting level
* Battery starting SOC
* PV panel specifications
* Electrolyzer specifications
* Tank specifications
* Fuel cell specifications
* Battery specifications
* Bottling flow

Important: the **Live state** values for tank and battery are meant to set starting or test values. They are not locked forever. Once the simulation starts running, the model updates them automatically.

---

### 2. Machine status diagram

The system diagram shows the plant components.

Each block can be clicked:

```text
Green = active/running
Red = off, idle, or stopped by control/safety logic
```

The machine blocks are:

* PV
* Electrolyzer
* Tank
* Fuel Cell
* Battery
* Grid
* Bottling

Clicking a block toggles the machine manually.

Some components can also be started automatically by the controller depending on the scenario.

---

### 3. Data cards

The dashboard cards show live calculated values for each subsystem:

* PV
* Electrolyzer
* Tank
* Fuel Cell
* Battery
* Grid
* Bottling

---

### 4. Graphs

The graphs show production, storage, and energy-flow trends over time.

Examples:

* PV power
* PV to grid
* PV to electrolyzer
* PV to battery
* Grid supplied
* Unmet demand
* Hydrogen production
* Hydrogen consumption
* Tank level
* Battery SOC
* Fuel cell to battery
* Bottling flow

---

## Reset and Pause

The simulation starts paused.

Controls:

```text
SPACE = pause / resume
RESET button = reset simulation
```

The reset button:

* Pauses the simulation
* Turns all machines OFF
* Sets tank level to 0
* Sets battery SOC to 0
* Resets starting tank and battery values to 0
* Clears history
* Resets elapsed simulation time to 0 seconds

---

## Project Structure

Recommended folder structure:

```text
backup_system_sim/
│
├── main.py
├── config.json
│
├── engine/
│   ├── __init__.py
│   ├── digital_twin.py
│   └── logger.py
│
└── ui/
    ├── __init__.py
    ├── visual.py
    └── widgets.py
```

---

## File Descriptions

### `main.py`

Entry point of the simulator.

It:

* Creates the digital twin object
* Creates the Pygame visual interface
* Runs the simulation loop
* Handles pause/resume
* Handles reset

Run this file to start the simulator:

```bash
python main.py
```

---

### `config.json`

Main configuration file.

This is where you define the initial system state and default specs.

It contains:

* Simulation settings
* Initial machine states
* Environment values
* PV specs
* Electrolyzer specs
* Tank specs
* Fuel cell specs
* Battery specs
* Bottling specs
* Controller options

---

### `engine/digital_twin.py`

Main simulation engine.

This file contains:

* Physical calculations
* Energy dispatch logic
* Hydrogen production logic
* Tank pressure/level calculations
* Fuel cell behavior
* Battery charging/discharging
* Automatic startup rules
* Safety and low-level shutdown logic

Most model behavior is controlled here.

---

### `engine/logger.py`

CSV logger.

It writes simulation values to a CSV file, usually:

```text
simulation_log.csv
```

This is useful for later analysis.

---

### `ui/visual.py`

Main Pygame interface.

This file controls:

* The sidebar
* Textboxes
* Data cards
* Graphs
* Machine diagram
* Reset button
* Machine clicking/toggling

---

### `ui/widgets.py`

Reusable UI elements.

Currently includes:

* `TextBox`
* `Button`

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/YOUR_REPOSITORY.git
cd YOUR_REPOSITORY
```

Replace `YOUR_USERNAME` and `YOUR_REPOSITORY` with your real GitHub details.

---

## Creating a Conda Environment

Create a new Conda environment:

```bash
conda create -n h2_sim python=3.11
```

Activate it:

```bash
conda activate h2_sim
```

Install dependencies:

```bash
pip install pygame
```

Optional but useful for future analysis:

```bash
pip install numpy pandas matplotlib
```

---

## Running the Simulator

From the project root:

```bash
python main.py
```

A Pygame window should open.

The simulation starts paused. Press:

```text
SPACE
```

to start running.

---

## Configuration Guide

All default settings are in `config.json`.

### Simulation section

```json
"simulation": {
  "time_step_s": 1,
  "max_history": 600,
  "log_file": "simulation_log.csv"
}
```

Meaning:

| Key           | Meaning                            |
| ------------- | ---------------------------------- |
| `time_step_s` | Simulated seconds per step         |
| `max_history` | Number of points stored for graphs |
| `log_file`    | CSV output filename                |

---

### Machines section

```json
"machines": {
  "pv": false,
  "electrolyzer": false,
  "tank": false,
  "fuel_cell": false,
  "battery": false,
  "grid": false,
  "bottling": false
}
```

These are the initial ON/OFF states.

The current version starts with everything OFF.

Some machines may be turned ON automatically by the controller depending on system conditions.

---

### Environment section

```json
"environment": {
  "solar_radiation_w_m2": 800,
  "ambient_temperature_c": 25,
  "grid_demand_w": 1500
}
```

| Key                     | Unit | Meaning                          |
| ----------------------- | ---: | -------------------------------- |
| `solar_radiation_w_m2`  | W/m² | Solar irradiance                 |
| `ambient_temperature_c` |   °C | Ambient temperature              |
| `grid_demand_w`         |    W | Electrical load demanded by grid |

---

### PV specs

```json
"pv": {
  "area_m2": 20,
  "efficiency_ref": 0.2,
  "temperature_coefficient_per_c": -0.004,
  "reference_temperature_c": 25,
  "nominal_voltage_v": 48,
  "dc_system_efficiency": 0.96
}
```

PV power is calculated approximately as:

```text
PV power = radiation × area × efficiency × system efficiency
```

Temperature correction is also applied using the temperature coefficient.

---

### Electrolyzer specs

```json
"electrolyzer": {
  "efficiency": 0.7,
  "h2_production_mol_s": 0.015,
  "min_power_w": 50,
  "max_power_w": 4000,
  "nominal_voltage_v": 48,
  "water_per_h2_mol": 1,
  "startup_delay_s": 0
}
```

Important: `h2_production_mol_s` is used directly.

Example:

```json
"h2_production_mol_s": 18
```

means:

```text
Electrolyzer produces 18 mol/s while active
```

The mathematical conversion from power to hydrogen is ignored for the setpoint. Electrical power is still used as an operating condition and display metric.

---

### Tank specs

```json
"tank": {
  "capacity_mol": 1000,
  "max_pressure_bar": 700,
  "initial_h2_mol": 0,
  "high_stop_percent": 100,
  "low_warning_percent": 0
}
```

| Key                   | Unit | Meaning                  |
| --------------------- | ---: | ------------------------ |
| `capacity_mol`        |  mol | Maximum hydrogen amount  |
| `max_pressure_bar`    |  bar | Maximum pressure         |
| `initial_h2_mol`      |  mol | Initial hydrogen amount  |
| `high_stop_percent`   |    % | Tank full threshold      |
| `low_warning_percent` |    % | Fuel cell stop threshold |

Tank volume is calculated automatically from:

```text
PV = nRT
```

Rearranged:

```text
V = nRT / P
```

So tank capacity, temperature, and maximum pressure determine the tank volume.

---

### Fuel cell specs

```json
"fuel_cell": {
  "efficiency": 0.6,
  "max_power_w": 3000,
  "nominal_voltage_v": 48,
  "min_tank_pressure_bar": 5,
  "startup_delay_s": 0
}
```

The fuel cell converts hydrogen into electricity.

It is limited by:

* Available hydrogen in the tank
* Maximum fuel cell power
* Fuel cell efficiency
* Tank low warning threshold
* Minimum tank pressure

---

### Battery specs

```json
"battery": {
  "capacity_kwh": 10,
  "initial_soc_percent": 0,
  "max_charge_power_w": 3000,
  "max_discharge_power_w": 3000,
  "charge_efficiency": 0.95,
  "discharge_efficiency": 0.95,
  "nominal_voltage_v": 48,
  "min_soc_percent": 0,
  "max_soc_percent": 100
}
```

The battery charges when there is excess power and discharges when the grid needs energy and other sources are unavailable.

---

### Bottling specs

```json
"bottling": {
  "flow_mol_s": 0.05
}
```

This defines hydrogen bottling flow rate in mol/s.

Bottling is only allowed when the fuel cell is OFF.

---

### Controller specs

```json
"controller": {
  "fuel_cell_can_charge_battery_when_no_grid_demand": true,
  "auto_start_dependencies": true
}
```

| Key                                                | Meaning                                                        |
| -------------------------------------------------- | -------------------------------------------------------------- |
| `fuel_cell_can_charge_battery_when_no_grid_demand` | Allows fuel cell to charge battery when grid demand is zero    |
| `auto_start_dependencies`                          | Allows controller to automatically turn on required components |

---

## How to Test Scenarios

### Test 1 — Fill the tank from solar

1. Start the simulation.
2. Click `PV` ON.
3. The system should automatically turn on `ELET` and `TANK`.
4. Tank level should rise.
5. When tank is full, bottling can start if fuel cell is OFF.

---

### Test 2 — Grid demand with PV

1. Set grid demand to a positive value.
2. Click `GRID` ON.
3. Click `PV` ON.
4. PV should supply the grid first.
5. If PV is insufficient, the fuel cell can start if hydrogen is available.

---

### Test 3 — Grid demand with tank only

1. Set tank level to a positive value in the sidebar.
2. Keep PV OFF.
3. Click `GRID` ON.
4. The controller should turn on `TANK` and `FC`.
5. The fuel cell should supply the grid.
6. When tank reaches `low_warning_percent`, the system shuts down everything except grid.

---

### Test 4 — Grid demand with battery only

1. Set battery SOC to a positive value.
2. Keep PV OFF.
3. Keep tank at 0%.
4. Click `GRID` ON.
5. Battery should supply the grid.

---

## CSV Logging

The simulator writes values to:

```text
simulation_log.csv
```

This file can be opened in Excel, LibreOffice, Python, or pandas.

Example with pandas:

```python
import pandas as pd

log = pd.read_csv("simulation_log.csv")
print(log.head())
```

---

## Troubleshooting

### Pygame window is too large

The window is resizable. Drag the window edge to resize it.

If needed, adjust this in `ui/visual.py`:

```python
self.width = 1200
self.height = 750
```

---

### Pygame is not installed

Run:

```bash
pip install pygame
```

---

### Conda environment not active

Run:

```bash
conda activate h2_sim
```

---

### Simulation is not moving

The simulation starts paused.

Press:

```text
SPACE
```

---

### Tank or battery value is not changing

The sidebar `Live state` values are only starting/test values. After you edit them and press Enter, the simulation will update them naturally.

---

## Possible Future Improvements

Ideas for future versions:

* More realistic PV I-V curve
* Real electrolyzer polarization curve
* Compressor model
* Heat model
* Tank thermal dynamics
* Fuel cell degradation
* Battery aging
* Fault injection
* Web dashboard
* Export graph images
* Scenario presets
* PID or MPC controller
* MQTT/real sensor integration

---

## Disclaimer

This simulator is a simplified educational and prototyping tool. It is not validated for engineering certification, safety design, or real plant operation.

Use it to understand system behavior, test control logic, and visualize energy/hydrogen flows.
