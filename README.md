# Weather Station Core (ws_core)

A Home Assistant custom integration that turns your raw Personal Weather Station (PWS) sensors into a complete, normalised weather data layer — with derived meteorological values, a native `weather.*` entity, configurable alerts, and optional activity scores.

Supports any PWS brand (Ecowitt, Fine Offset, Davis, BTHome, DIY) that already has sensors in HA.

---

## What it does

Instead of writing dozens of template sensors yourself, this integration reads your existing raw sensors, converts units automatically, and produces a clean set of derived outputs — all from one config-flow setup screen.

**Core derived values (always created):**
- Dew point (August-Roche-Magnus formula, accurate to ±0.1°C over –40°C–60°C)
- Mean sea-level pressure (WMO hypsometric reduction from station pressure + elevation + temperature)
- Pressure trend (3-hour least-squares regression, WMO classification thresholds)
- Rain rate raw and Kalman-filtered (suppresses tipping-bucket phantom spikes)
- Apparent/feels-like temperature (Australian BOM standard)
- Beaufort wind scale + description
- Smoothed wind direction (circular exponential smoothing, no 360°/0° discontinuity)
- Current weather condition (36-condition classifier using local sensors)
- Zambretti 6–12h barometric forecast (8 regional climate presets)
- Local rain probability (pressure + trend + humidity + wind direction)
- Combined rain probability (local + Open-Meteo time-weighted)
- 24-hour rolling stats: temp high/low/avg, max gust
- Station health monitor (Online / Degraded / Stale / Offline)

**Weather entity:** `weather.{prefix}` — standard HA entity with 7-day Open-Meteo forecast. Condition falls back to local classifier if forecast is unavailable.

**Optional activity scores** (disabled by default, enable in entity registry):
- Laundry drying score (0–100) with estimated dry time
- Stargazing quality with moon phase impact
- Fire Weather Index (Canadian FWI-based)
- Running conditions score

---

## Compatibility

| Component | Version |
|---|---|
| Home Assistant | 2026.2+ |
| Python | 3.12+ |
| HACS | Any current |

---

## Installation

### Via HACS (recommended)

1. In HACS → Integrations → Custom Repositories
2. Add: `https://github.com/kmich/ha_ws_core` (category: Integration)
3. Install **Weather Station Core** and restart Home Assistant

### Manual

1. Copy `custom_components/ws_core` to your HA `custom_components` directory
2. Restart Home Assistant

---

## Configuration

1. **Settings → Devices & Services → Add Integration**
2. Search **Weather Station Core**
3. Name your station and set an entity prefix (default: `ws`)
4. Map required sensors: temperature, humidity, pressure, wind speed, wind gust, wind direction, rain total
5. Optionally map: illuminance, UV index, dew point, battery
6. Set elevation, units (auto/metric/imperial), staleness threshold, and forecast options
7. Set alert thresholds (wind gust, rain rate, freeze point)

Options can be changed at any time via **Settings → Devices & Services → Weather Station Core → Configure**.

---

## Sensors created

### Core measurements (always enabled)

| Entity | Description | Unit |
|---|---|---|
| `sensor.{prefix}_temperature` | Station temperature | °C / °F |
| `sensor.{prefix}_humidity` | Station humidity | % |
| `sensor.{prefix}_dew_point` | Dew point (August-Roche-Magnus) | °C / °F |
| `sensor.{prefix}_station_pressure` | Raw station pressure | hPa |
| `sensor.{prefix}_sea_level_pressure` | MSLP (WMO hypsometric) | hPa |
| `sensor.{prefix}_wind_speed` | Wind speed | m/s |
| `sensor.{prefix}_wind_gust` | Wind gust | m/s |
| `sensor.{prefix}_wind_direction` | Wind direction | ° |
| `sensor.{prefix}_wind_direction_smooth` | Smoothed wind direction (EMA) *(disabled by default)* | ° |
| `sensor.{prefix}_rain_total` | Cumulative precipitation | mm |
| `sensor.{prefix}_rain_rate` | Rain rate (Kalman-filtered) | mm/h |
| `sensor.{prefix}_illuminance` | Solar illuminance | lx |
| `sensor.{prefix}_uv_index` | UV index | — |
| `sensor.{prefix}_battery` | Station battery | % |
| `sensor.{prefix}_feels_like` | Apparent temperature (BOM) | °C / °F |
| `sensor.{prefix}_wind_beaufort` | Beaufort scale 0–12 | — |
| `sensor.{prefix}_wind_quadrant` | Cardinal quadrant (N/E/S/W) | — |
| `sensor.{prefix}_current_condition` | 36-condition classifier | — |
| `sensor.{prefix}_zambretti_forecast` | Barometric 6–12h forecast | — |
| `sensor.{prefix}_rain_probability` | Local rain probability | % |
| `sensor.{prefix}_rain_probability_combined` | Local + API blended probability | % |
| `sensor.{prefix}_rain_display` | Formatted rain text | — |
| `sensor.{prefix}_pressure_trend` | Trend text (Rising/Steady/Falling) | — |
| `sensor.{prefix}_station_health` | Health status | — |
| `sensor.{prefix}_temperature_high_24h` | 24h temperature maximum | °C / °F |
| `sensor.{prefix}_temperature_low_24h` | 24h temperature minimum | °C / °F |
| `sensor.{prefix}_temperature_avg_24h` | 24h temperature average *(disabled by default)* | °C / °F |
| `sensor.{prefix}_wind_gust_max_24h` | 24h maximum wind gust | m/s |
| `sensor.{prefix}_humidity_level` | Humidity text level | — |
| `sensor.{prefix}_uv_level` | UV text level | — |
| `sensor.{prefix}_forecast_tiles` | 5-day forecast tile data | — |

### Diagnostic (enabled, shown in Diagnostics section)

| Entity | Description |
|---|---|
| `sensor.{prefix}_rain_rate_raw` | Unfiltered rain rate |
| `sensor.{prefix}_pressure_trend_raw` | Pressure trend hPa/h |
| `sensor.{prefix}_data_quality_banner` | OK / WARN / ERROR |
| `sensor.{prefix}_sensor_quality_flags` | Bitmask / reasons behind data-quality state *(disabled by default)* |
| `sensor.{prefix}_package_status` | Detailed status string |
| `sensor.{prefix}_alert_state` | clear / advisory / warning |
| `sensor.{prefix}_alert_message` | Alert detail text |
| `sensor.{prefix}_forecast_daily` | Raw forecast provider info |
| `binary_sensor.{prefix}_package_ok` | True when all sources healthy |

### Activity scores (disabled by default)

Enable individually in **Settings → Entities** or the Entity Registry.

| Entity | Description |
|---|---|
| `sensor.{prefix}_laundry_drying_score` | 0–100 with recommendation |
| `sensor.{prefix}_stargazing_quality` | Quality rating + moon phase |
| `sensor.{prefix}_fire_weather_index` | FWI with danger level |
| `sensor.{prefix}_running_score` | Running conditions 0–100 |

---

## Weather entity

`weather.{prefix}` is a standard HA weather entity populated from your local station.

- **Current conditions:** derived from local sensors (36-condition classifier)
- **7-day forecast:** Open-Meteo free API (no account or API key required)
- **Forecast fallback:** if Open-Meteo is unreachable, entity remains available with local data only
- **Attribution:** "Forecast by Open-Meteo" displayed when forecast data is present

---

## Meteorological methods

| Calculation | Method | Reference |
|---|---|---|
| Dew point | August-Roche-Magnus (a=17.62, b=243.12) | Alduchov & Eskridge 1996 |
| Sea-level pressure | Hypsometric reduction | WMO No. 8, §3.1.3 |
| Apparent temperature | Australian BOM (AT = Ta + 0.33·e − 0.70·ws − 4.0) | Steadman 1994 |
| Pressure trend | 3-hour least-squares regression | — |
| Trend thresholds | ±0.8 / ±1.6 hPa per 3h | WMO No. 306, Table 4680 |
| Zambretti forecast | 8-region climate preset lookup | Zambretti 1928 adapted |
| Rain rate filter | 1D Kalman filter (Q=0.01, R=0.5) | — |
| Wind smoothing | Circular exponential smoothing (α=0.3) | — |
| Moon phase | Julian Day algorithm | Conway 1999 |

---

## Dashboard

A sample dashboard is included in `dashboards/weather_dashboard.yaml`.

**To install:**
1. Copy the contents of `weather_dashboard.yaml`
2. In HA: **Settings → Dashboards → Add Dashboard → From YAML → Raw config editor**
3. Paste and save

*Dashboard is **vanilla** (core cards only) — no Lovelace custom cards required.*

---

## Services

### `ws_core.reset_rain_baseline`

Resets the internal rain total baseline used to compute rain rate. Use this if your station resets its cumulative counter (e.g., after a reboot).

```yaml
service: ws_core.reset_rain_baseline
data:
  entry_id: "optional_specific_entry_id"  # omit to reset all stations
```

---

## Alerts

Three threshold-based alerts are computed every minute:

| Alert | Condition | Default threshold |
|---|---|---|
| High wind | `wind_gust >= threshold` | 17.0 m/s (≈ Beaufort 8) |
| Heavy rain | `rain_rate_filtered >= threshold` | 20 mm/h |
| Freeze risk | `temperature <= threshold` | 0.0 °C |

All thresholds are configurable and unit-aware (displays in mph/in·h⁻¹/°F for imperial users).

---

## Support

- **Bugs & features:** [GitHub Issues](https://github.com/kmich/ha_ws_core/issues)
- **Tested hardware:** Ecowitt WS90, Fine Offset WH2350, BTHome sensors, DIY ESPHome stations

---

## License

MIT
