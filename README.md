# Joulia EV Charging for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/v/release/elenhinan/joulia-homeassistant?include_prereleases&color=blue)](https://github.com/elenhinan/joulia-homeassistant/releases)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

A Home Assistant integration for **Joulia EV Chargers** (formerly **Aneo Mobility** and **Elaway**), connecting directly with the Joulia Cloud API.

---

## Features

- **Real-Time Status**: View socket and charger states (`Available`, `Charging`, `Preparing`, `SuspendedEV`, etc.).
- **Live Charging Power (kW)**: Automatically reports or calculates charging power during active sessions.
- **Session Energy (kWh)**: Tracks cumulative energy delivered during the current or most recent charging session.
- **Permanent Cable Lock**: Switch to lock or unlock the charging cable on the wallbox.
- **Charging Controls**: Remotely start or stop charging transactions.
- **Diagnostic Sensors**: Wallbox cellular RSSI signal strength, parking lot number, and facility name.
- **Hardware Reboot**: Remotely reboot the charger hardware if needed.
- **Automatic Token Management**: Automatically handles 90-day rolling refresh tokens.

---

## Installation via HACS (Custom Repository)

1. Make sure [HACS](https://hacs.xyz/) is installed in your Home Assistant instance.
2. In Home Assistant, open **HACS** $\rightarrow$ Click the **3 dots** in the top right corner $\rightarrow$ Select **Custom repositories**.
3. Fill in the fields:
   - **Repository**: `https://github.com/elenhinan/joulia-homeassistant`
   - **Category**: `Integration`
4. Click **Add**.
5. Find **Joulia EV Charging** in HACS, click **Download**, and restart Home Assistant.

---

## Manual Installation

1. Download the `custom_components/joulia` folder from this repository.
2. Copy the `joulia` folder into your Home Assistant directory under `/config/custom_components/`.
3. Restart Home Assistant.

---

## Configuration

1. In Home Assistant, navigate to **Settings** $\rightarrow$ **Devices & Services** $\rightarrow$ **+ Add Integration**.
2. Search for **Joulia EV Charging**.
3. Enter your Joulia (or Aneo Mobility) account credentials:
   - **Email address**
   - **Password**
4. Click **Submit**. Your chargers and parking facilities will be discovered automatically.

---

## Entities

| Entity | Domain | Description |
| :--- | :---: | :--- |
| `sensor.joulia_<id>_status` | Sensor | Socket status (`Charging`, `Available`, etc.) |
| `sensor.joulia_<id>_charging_power` | Sensor (`kW`) | Real-time charging power draw |
| `sensor.joulia_<id>_session_energy` | Sensor (`kWh`) | Energy delivered in current charging session |
| `sensor.joulia_<id>_cellular_signal` | Sensor (`dBm`) | Wallbox cellular signal strength |
| `switch.joulia_<id>_cable_lock` | Switch | Permanently lock or unlock cable |
| `switch.joulia_<id>_charging` | Switch | Start / stop charging session |
| `button.joulia_<id>_reboot` | Button | Remote hardware reboot command |

---

## Disclaimer

This is a community-developed custom integration. It is not affiliated with or endorsed by Joulia or Aneo Mobility.

