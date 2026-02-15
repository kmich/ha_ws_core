# Weather Station Core (HACS)

A **UI-first** Home Assistant custom integration that turns your *existing* weather-station entities (Ecowitt, BTHome, Ambient, Davis via gateways, etc.) into a clean set of **derived / normalized sensors**, a **data-quality banner**, simple **local alerts**, and an optional **Open‑Meteo forecast** (including a real **weather.* entity**).

**v1.0.0 is the first public release.** Keep the version at **1.0.0** until you decide to publish it.

---

## What you get

### Core normalized sensors (always created)

- `sensor.ws_core_norm_temperature` (°C)
- `sensor.ws_core_norm_humidity` (%)
- `sensor.ws_core_norm_pressure` (hPa) — station pressure
- `sensor.ws_core_sea_level_pressure` (hPa) — reduced to sea level (approx.)
- `sensor.ws_core_norm_wind_speed` (m/s)
- `sensor.ws_core_norm_wind_gust` (m/s)
- `sensor.ws_core_norm_wind_dir` (°)
- `sensor.ws_core_norm_rain_total` (mm)
- `sensor.ws_core_rain_rate_raw` (mm/h)
- `sensor.ws_core_rain_rate_filtered` (mm/h)
- `sensor.ws_core_dew_point` (°C) *(computed if you don’t provide a dew-point sensor)*

### Status / UX / Diagnostics

- `sensor.ws_core_data_quality_banner` — **OK / WARN / ERROR** with actionable text
- `binary_sensor.ws_core_package_ok`
- `sensor.ws_core_package_status` — details about missing/stale sources
- `sensor.ws_core_alert_state` + `sensor.ws_core_alert_message` — simple local thresholds
- `sensor.ws_core_pressure_trend` (hPa/h, averaged over a rolling window — default 3h)
- `sensor.ws_core_pressure_change_window` (hPa change over the same window)

### Forecast + native weather entity

- `sensor.ws_core_forecast_daily` — Open‑Meteo payload in attributes
- `weather.ws_core` — a real `weather.*` entity (works with HA’s native weather cards)

> `ws_core` is the default prefix. If you change it (e.g., `ws` or `lagonisi`), all entity IDs will use that prefix.

### Optional sensors (only if you map them)

- `sensor.ws_core_illuminance` (lx)
- `sensor.ws_core_uv_index`
- `sensor.ws_core_battery` (%)

### Optional activity proxy scores (disabled by default)

- `sensor.ws_core_laundry_drying_score`
- `sensor.ws_core_stargazing_quality`
- `sensor.ws_core_fire_weather_proxy`

These are **heuristics** and are **disabled by default** (enable them in **Entity settings** and/or via the Options toggle).

---

## Important disclaimers

- **Fire Weather Proxy** is a simple heuristic (temperature + humidity + wind) and is **not** a calibrated Fire Weather Index (FWI). Do **not** use it for safety decisions.
- Alerts are local thresholds for convenience, **not** official warnings.

---

## Installation (HACS)

1) Install **HACS**.
2) Add this repo as a **Custom repository** in HACS:
   - HACS → Integrations → 3‑dot menu → **Custom repositories**
   - URL: `https://github.com/kmich/ha-weather-station`
   - Category: **Integration**
3) Install **Weather Station Core**.
4) Restart Home Assistant.

---

## Setup wizard (step-by-step)

Go to **Settings → Devices & services → Add integration → Weather Station Core**.

### Step 1 — Station identity
- Station name
- Entity prefix (default `ws`)

### Step 2 — Required source sensors
- Temperature, humidity, pressure, wind speed, wind gust, wind direction, rain total

The wizard validates that each selected entity exists and currently reports a numeric value.

### Step 3 — Optional source sensors
- Illuminance, UV index, dew point, battery

### Step 4 — Settings
- Units mode (`auto` / `metric` / `imperial`)
- Elevation (used for sea-level pressure reduction)
- Staleness threshold (default 900s)
- Forecast enable + interval + coordinates

### Step 5 — Alerts & heuristics
- Wind gust, rain rate, freeze thresholds
- Rain-rate filter smoothing (alpha)
- Pressure-trend window (default 3h)
- Optional activity proxy scores (toggle)

---

## Options flow (reconfigure later)

Settings → Devices & services → Weather Station Core → **Configure**

You can change:
- Prefix, units mode, elevation, staleness
- Forecast settings
- Thresholds + heuristics (including rain filter alpha and pressure-trend window)

Changes apply immediately (the integration reloads on options update).

---

## Dashboard (vanilla Lovelace)

This repo includes a dashboard YAML you can import:

- `dashboards/weather_dashboard.yaml`

How to use it:
1) Settings → Dashboards → **Add dashboard**
2) Choose **YAML mode** dashboard, paste the YAML

This dashboard intentionally uses **standard HA cards** (no custom-card dependencies).

---

## Services

### `ws_core.reset_rain_baseline`
Resets the internal baseline used to compute rain rate.

Optional field:
- `entry_id` — if provided, only resets that specific Weather Station Core config entry; if omitted, resets all Weather Station Core entries.

---

## Troubleshooting

### Data quality banner shows ERROR / WARN
- Open the Weather Station Core integration → **Configure**
- Fix missing mappings or staleness threshold.

### Forecast shows errors
Check `sensor.ws_core_forecast_daily` attributes:
- `last_error`, `http_status`, `last_success`

---

## Contributing

PRs welcome. Please keep the version at **1.0.0** until you decide to publish publicly.
