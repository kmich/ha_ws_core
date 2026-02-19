# Weather Station Core (`ws_core`)

[![HACS][hacs-badge]][hacs-url]
[![GitHub Release][release-badge]][release-url]
[![License][license-badge]][license-url]
[![Validate][validate-badge]][validate-url]

**Turn any personal weather station into a comprehensive, scientifically-documented weather intelligence hub for Home Assistant.**

Weather Station Core reads raw sensor data from your existing weather station — Ecowitt, Davis, WeatherFlow, Shelly, or any HA-integrated PWS — and produces 40+ derived meteorological values through a guided 7-step config flow. No YAML required.

<p align="center">
  <em>Screenshots: Config flow, Main dashboard, Advanced page</em><br>
  <sub>(Add your own screenshots to <code>docs/img/</code> after installation)</sub>
</p>

---

## Features

- **Real Zambretti barometric forecaster** -- Negretti & Zambra lookup table (Z-numbers 1-26), climate-region-aware wind corrections, seasonal adjustment
- **Wet-bulb temperature** (Stull 2011, +-0.3 C) and **frost point** (Buck 1981 ice constants)
- **Climate-region-aware rain probability** with Open-Meteo NWP blending
- **Kalman-filtered rain rate** for de-noised precipitation readings
- **36-condition weather classifier** with severity levels and MDI icons
- **Activity scores**: laundry drying, stargazing quality, running conditions, fire risk
- **Air Quality Index** via Open-Meteo (free, no API key) -- PM2.5, PM10, NO2, ozone
- **Pollen levels** (grass, tree, weed) via Tomorrow.io (free API key required)
- **Moon phase & illumination** -- calculated astronomically, no API key required
- **Solar PV forecast** (today + tomorrow kWh) via forecast.solar (free, no API key)
- **Penman-Monteith ET0** -- automatically activates when a solar radiation sensor is available
- **7-day daily forecast** via Open-Meteo (free, no API key required)
- **METAR cross-validation** -- auto-detects nearest ICAO airport from your coordinates
- **CWOP & Weather Underground uploads** with credential validation at setup
- **Full options flow** -- every setting reconfigurable post-install via the Configure button, no reinstall needed

---

## Requirements

A personal weather station integrated into Home Assistant providing **at minimum**:

| Measurement | Example entities |
|---|---|
| Temperature | `sensor.gw2000a_outdoor_temperature` |
| Relative humidity | `sensor.gw2000a_outdoor_humidity` |
| Atmospheric pressure | `sensor.gw2000a_absolute_pressure` |
| Wind speed | `sensor.gw2000a_wind_speed` |
| Wind gust | `sensor.gw2000a_wind_gust` |
| Wind direction (°) | `sensor.gw2000a_wind_direction` |
| Cumulative rainfall | `sensor.gw2000a_rain_total` |

**Optional** (improves derived metrics): illuminance (lux), UV index, dew point, battery level.

**Home Assistant**: 2026.2+ · **Python**: 3.12+

---

## Installation

### Via HACS (recommended)

1. Open HACS → Integrations → ⋮ → Custom repositories
2. Add `https://github.com/kmich/ha_ws_core` (category: Integration)
3. Search for "Weather Station Core" and install
4. Restart Home Assistant

### Manual

1. Copy `custom_components/ws_core` to your HA `custom_components/` directory
2. Restart Home Assistant

---

## Configuration

Settings → Devices & Services → Add Integration → "Weather Station Core"

The 7-step wizard walks you through:

| Step | What it does |
|---|---|
| 1. Name & prefix | Station name and entity ID prefix (e.g. `ws` → `sensor.ws_temperature`) |
| 2. Required sensors | Map your 7 mandatory sensor entities |
| 3. Optional sensors | Map illuminance, UV, dew point, battery, solar radiation (leave blank to skip) |
| 4. Location & climate | Hemisphere, climate region, elevation (auto-detected from HA) |
| 5. Display units | Temperature, wind, rain, pressure unit preferences |
| 6. Forecast | Enable/disable Open-Meteo 7-day forecast, coordinates |
| 7. Alerts | Wind/rain/freeze thresholds |
| 8. Features | Toggle all feature groups: activity scores, sea temp, degree days, METAR, CWOP, WU, export, air quality, pollen, moon, solar forecast |
| 8a-8n | Per-feature sub-steps for each enabled feature (ICAO code, API keys, panel config, etc.) |

All settings can be changed later via **Configure** (Settings → Devices & Services → Weather Station Core → Configure). The options flow mirrors the full config flow.

---

## Sensors Created

### Core Measurements (always enabled)

| Entity | Unit | Device Class | Description |
|---|---|---|---|
| `sensor.ws_temperature` | °C | temperature | Normalized temperature |
| `sensor.ws_humidity` | % | humidity | Normalized relative humidity |
| `sensor.ws_station_pressure` | hPa | pressure | Station-level pressure |
| `sensor.ws_sea_level_pressure` | hPa | pressure | Mean sea-level pressure (MSLP) |
| `sensor.ws_wind_speed` | m/s | wind_speed | Sustained wind speed |
| `sensor.ws_wind_gust` | m/s | wind_speed | Wind gust speed |
| `sensor.ws_wind_direction` | ° | wind_direction | Wind direction |
| `sensor.ws_rain_total` | mm | precipitation | Cumulative rainfall (TOTAL_INCREASING) |
| `sensor.ws_rain_rate` | mm/h | — | Kalman-filtered rain rate |
| `sensor.ws_dew_point` | °C | temperature | Dew point (Magnus formula) |
| `sensor.ws_illuminance` | lx | illuminance | Solar illuminance |
| `sensor.ws_uv_index` | — | — | UV index |

### Advanced Meteorological (always enabled)

| Entity | Unit | Description |
|---|---|---|
| `sensor.ws_feels_like` | °C | Apparent temperature (BOM formula) |
| `sensor.ws_wet_bulb` | °C | Wet-bulb temperature (Stull 2011) |
| `sensor.ws_frost_point` | °C | Frost point (ice constants below 0 °C) |
| `sensor.ws_zambretti_forecast` | — | Zambretti barometric forecast text |
| `sensor.ws_zambretti_number` | — | Z-number (1–26) for automations |
| `sensor.ws_wind_beaufort` | — | Beaufort scale number |
| `sensor.ws_wind_quadrant` | — | 4-point wind quadrant (N/E/S/W) |
| `sensor.ws_current_condition` | — | 36-condition classifier |
| `sensor.ws_rain_probability` | % | Local sensor-based rain index |
| `sensor.ws_rain_probability_combined` | % | Blended local + Open-Meteo |
| `sensor.ws_pressure_trend` | — | Rising/Falling/Steady (WMO No. 306) |

### 24h Rolling Statistics

| Entity | Description |
|---|---|
| `sensor.ws_temperature_high_24h` | 24-hour high temperature |
| `sensor.ws_temperature_low_24h` | 24-hour low temperature |
| `sensor.ws_wind_gust_max_24h` | 24-hour maximum gust |

### Activity Scores (disabled by default, enable in options)

| Entity | Scale | Description |
|---|---|---|
| `sensor.ws_laundry_drying_score` | 0–100 | Outdoor drying conditions |
| `sensor.ws_stargazing_quality` | text | Stargazing quality (Excellent/Good/Fair/Poor) |
| `sensor.ws_fire_risk_score` | 0–50 | Simplified fire risk heuristic |
| `sensor.ws_running_score` | 0–100 | Running conditions score |

### Air Quality (optional, enable_air_quality)

| Entity | Unit | Description |
|---|---|---|
| `sensor.ws_air_quality_index` | AQI | US EPA AQI from Open-Meteo (PM2.5-based) |
| `sensor.ws_air_quality_level` | — | Level label: Good / Moderate / Unhealthy / etc. |

### Pollen (optional, enable_pollen + Tomorrow.io API key)

| Entity | Description |
|---|---|
| `sensor.ws_pollen_overall` | Highest of grass/tree/weed (None/Low/Medium/High/Very High) |
| `sensor.ws_pollen_grass` | Grass pollen IQLA index |
| `sensor.ws_pollen_tree` | Tree pollen IQLA index |
| `sensor.ws_pollen_weed` | Weed pollen IQLA index |

### Moon (optional, enable_moon)

| Entity | Description |
|---|---|
| `sensor.ws_moon_display` | Human-readable phase name with emoji |
| `sensor.ws_moon_phase` | Phase key (new/waxing_crescent/first_quarter/etc.) |
| `sensor.ws_moon_illumination` | Illumination percentage |

### Solar PV Forecast (optional, enable_solar_forecast)

| Entity | Unit | Description |
|---|---|---|
| `sensor.ws_solar_forecast_today_kwh` | kWh | Estimated PV generation today |
| `sensor.ws_solar_forecast_tomorrow_kwh` | kWh | Estimated PV generation tomorrow |

### Other Entities

| Entity | Type | Description |
|---|---|---|
| `weather.ws` | weather | Standard HA weather entity with daily forecast |
| `binary_sensor.ws_package_ok` | binary_sensor | True when all required sources are mapped and available |
| `select.ws_graph_range` | select | Dashboard graph time range (6h/24h/3d) |
| `switch.ws_enable_animations` | switch | Dashboard animation toggle |

### Configuration Entities (device page)

All configurable parameters are exposed as entities on the device page so users can adjust them directly without entering the config flow. Changes trigger a coordinator reload automatically.

**Number entities** (thresholds, calibration offsets, algorithm parameters):

| Entity | Unit | Description |
|---|---|---|
| `number.ws_thresh_wind_gust` | m/s | Wind gust alert threshold |
| `number.ws_thresh_rain_rate` | mm/h | Rain rate alert threshold |
| `number.ws_thresh_freeze` | C | Freeze warning threshold |
| `number.ws_cal_temp` | C | Temperature calibration offset |
| `number.ws_cal_humidity` | % | Humidity calibration offset |
| `number.ws_cal_pressure` | hPa | Pressure calibration offset |
| `number.ws_cal_wind` | m/s | Wind speed calibration offset |
| `number.ws_staleness_timeout` | s | Sensor staleness timeout |
| `number.ws_rain_filter_alpha` | -- | Rain-rate Kalman filter smoothing |
| `number.ws_pressure_trend_window` | h | Pressure trend window |
| `number.ws_rain_penalty_light` | mm/h | Rain penalty start threshold |
| `number.ws_rain_penalty_heavy` | mm/h | Rain penalty maximum threshold |

**Switch entities** (feature toggles):

| Entity | Description |
|---|---|
| `switch.ws_enable_zambretti` | Zambretti forecast & classifier |
| `switch.ws_enable_display_sensors` | Display sensors (levels, trends, health) |
| `switch.ws_enable_laundry_score` | Laundry drying score |
| `switch.ws_enable_stargazing_score` | Stargazing quality |
| `switch.ws_enable_fire_risk_score` | Fire risk score |
| `switch.ws_enable_running_score` | Running conditions score |
| `switch.ws_enable_sea_temp` | Sea surface temperature |
| `switch.ws_enable_degree_days` | Degree days |
| `switch.ws_enable_metar` | METAR cross-validation |
| `switch.ws_enable_cwop` | CWOP upload |
| `switch.ws_enable_wunderground` | Weather Underground upload |
| `switch.ws_enable_export` | CSV/JSON data export |
| `switch.ws_enable_air_quality` | Air quality index |
| `switch.ws_enable_pollen` | Pollen levels |
| `switch.ws_enable_moon` | Moon phase & illumination |
| `switch.ws_enable_solar_forecast` | Solar PV forecast |

---

## Dashboards

Two dashboards are provided in `dashboards/`:

### Vanilla Dashboard (`weather_dashboard_vanilla.yaml`)

Uses **only native HA cards** — no HACS frontend dependencies. Works immediately after installation.

To install: copy the YAML contents → Dashboard → Edit → Raw Configuration Editor → paste → save.

### Enhanced Dashboard (`weather_dashboard.yaml`)

Rich visual dashboard requiring these HACS frontend cards:
- `custom:button-card`
- `custom:mini-graph-card`
- `custom:stack-in-card`
- `custom:config-template-card`
- `card-mod`
- `kiosk-mode`

---

## Formula Documentation

Every derived metric is documented with its source reference, valid input range, and known limitations.

### Dew Point — Magnus Formula (Alduchov & Eskridge 1996)

```
γ = (a·T)/(b+T) + ln(RH/100)
Td = (b·γ)/(a-γ)

Over water (T ≥ 0°C): a=17.625, b=243.04
Over ice  (T < 0°C):  a=22.587, b=273.86 (Buck 1981)
```

Valid range: -45 °C to +60 °C, 1–100% RH. Max error: < 0.1 °C.

### Frost Point — Magnus Formula with Ice Constants (Buck 1981)

Same formula as dew point but always uses ice constants (a=22.587, b=273.86). Only physically meaningful below 0 °C; above 0 °C returns the standard dew point.

### Wet-Bulb Temperature (Stull 2011)

```
Tw = T·atan(0.151977·(RH+8.313659)^0.5) + atan(T+RH)
     - atan(RH-1.676331) + 0.00391838·RH^1.5·atan(0.023101·RH)
     - 4.686035
```

Source: Stull, R. (2011). *J. Appl. Meteor. Climatol.*, 50, 2267–2269.
Valid range: RH 5–99%, T −20 to +50 °C. Max error: ±0.3 °C.

### Sea-Level Pressure — Hypsometric Reduction (WMO No. 8)

```
MSLP = P_stn × exp(elevation / (T_K × 29.263))
```

Accuracy: ±0.3 hPa below 500 m, ±1 hPa at 2000 m.
**Limitation**: Uses current temperature only; WMO recommends 12h mean temperature for better accuracy at high elevations.

### Apparent Temperature — Australian BOM (Steadman 1994)

```
AT = Ta + 0.33·e - 0.70·ws - 4.0
where e = (RH/100) × 6.105 × exp((17.27·T)/(237.7+T))
```

Valid for any temperature range (unlike NWS wind chill / heat index which have validity bounds).

### Zambretti Barometric Forecaster (Negretti & Zambra, 1915)

Implements the authentic Negretti & Zambra forecast table with all 26 Z-number entries mapped to their original weather descriptions. The base Z-number is derived from MSLP (950–1050 hPa), then corrected for pressure trend (±4 Z-numbers for rapid change), wind direction (climate-region-aware biases from Watts, 2012), season, and humidity. The final Z-number indexes the historical lookup table — not a parameterized approximation.

Accuracy: 65–75% for 6–12h forecasts in maritime/Mediterranean climates. Less reliable in continental interiors and tropics.

### Pressure Trend — Least-Squares Linear Regression (WMO No. 306)

Fits a linear trend to the pressure history buffer (sampled every 15 minutes, 12 samples = 3h window) and extrapolates the slope to a 3-hour rate. Classifications follow WMO Table 4680 thresholds: Rising Rapidly (>1.6 hPa/3h), Rising (>0.8), Steady, Falling (<−0.8), Falling Rapidly (<−1.6).

### Rain Probability — Heuristic Index

**This is NOT a calibrated probability.** It is a composite index (0–100) combining MSLP, pressure trend, humidity, and wind direction using climate-region-specific thresholds. The combined probability blends this local index with Open-Meteo NWP output, weighting local sensors higher during daytime convective hours (6–18h) when surface observations better capture buildup.

### Fire Risk Score — Simplified Heuristic

**NOT the Canadian FWI.** A simplified 0–50 scale inspired by the FWI structure (Van Wagner 1987) but lacking the daily-accumulated moisture codes (FFMC, DMC, DC) required for the real system. Not suitable for operational fire weather decisions. Consult official fire services.

### Kalman Filter — Rain Rate Smoothing

1D Kalman filter applied to raw rain rate (computed from successive total rainfall readings). Process noise: 0.01, measurement noise: 0.5. Eliminates the spike-and-drop pattern common in tipping-bucket rain gauges.

---

## Example Automations

Example Blueprint automations are provided in `blueprints/`:

- **Frost Alert**: Notify when temperature drops below threshold
- **Rain Notification**: Alert when rain starts or rain probability exceeds threshold
- **Laundry Reminder**: Morning notification when drying conditions are excellent
- **Storm Warning**: Alert on rapid pressure drop with high wind

See `blueprints/README.md` for installation instructions.

---

## Sensor Calibration

All weather sensors drift over time. Use calibration offsets (Settings → Integrations → WS Core → Configure) to correct for known bias by comparing your station to a trusted reference (nearby airport METAR, MADIS station, or a calibrated instrument).

| Offset | Range | Typical use |
|--------|-------|-------------|
| Temperature | ±10 °C | Correct for sensor placement (radiation shield quality, proximity to heat sources) |
| Humidity | ±20% | Compensate for sensor aging (capacitive humidity sensors drift 1–2%/year) |
| Pressure | ±10 hPa | Correct for altitude error if MSLP doesn't match nearby stations |
| Wind speed | ±5 m/s | Adjust for sheltered mounting or anemometer calibration |

Offsets are applied after unit conversion, before all derived calculations (dew point, feels-like, Zambretti, etc.).

---

## Troubleshooting

### Common Issues

| Symptom | Likely Cause | Fix |
|---|---|---|
| All sensors show "unavailable" | Source entities not found | Check source sensor entity IDs in Configure |
| Temperature statistics look wrong | Old `TOTAL_INCREASING` state class | Delete the temperature entity from HA, restart |
| Rain rate stuck at 0 | Rain total sensor reset | Call `ws_core.reset_rain_baseline` service |
| Forecast shows "unavailable" | Open-Meteo API timeout | Check internet; forecast retries automatically |
| "Stale" warning | Source sensor stopped updating | Check your weather station hardware |

### Diagnostics

Download diagnostics via Settings → Devices & Services → Weather Station Core → ⋮ → Download Diagnostics. The export includes sensor availability, compute timing, and quality flags (location data is redacted).

---

## Services

| Service | Description |
|---|---|
| `ws_core.reset_rain_baseline` | Reset the internal rain total baseline. Useful after station rain counter resets. |

---

## Known Limitations

1. **Illuminance-based cloud detection** uses raw lux without solar-angle normalization. Accuracy degrades at low sun elevation angles.
2. **Sea-level pressure** uses current temperature only, not the WMO-recommended 12h mean. Error increases above 500 m during rapid temperature swings.
3. **Rain probability** is a heuristic index, not a statistically calibrated probability. Treat it as relative likelihood.
4. **Fire Risk Score** is a simplified heuristic that does NOT implement the full Canadian FWI moisture tracking system.
5. **24h statistics** are computed from in-memory rolling windows and reset on HA restart.

---

## Contributing

Contributions are welcome! Please open an issue first to discuss what you'd like to change.

- **Translations**: The integration currently supports English. Community translations are welcome — see `custom_components/ws_core/translations/en.json` for the key structure.
- **Bug reports**: Use the GitHub issue template and include your diagnostics export.
- **Weather stations**: If your station brand needs special handling, open an issue with your entity details.

---

## License

[MIT](LICENSE)

---

[hacs-badge]: https://img.shields.io/badge/HACS-Custom-41BDF5.svg
[hacs-url]: https://github.com/hacs/integration
[release-badge]: https://img.shields.io/github/v/release/kmich/ha_ws_core
[release-url]: https://github.com/kmich/ha_ws_core/releases
[license-badge]: https://img.shields.io/github/license/kmich/ha_ws_core
[license-url]: https://github.com/kmich/ha_ws_core/blob/main/LICENSE
[validate-badge]: https://img.shields.io/github/actions/workflow/status/kmich/ha_ws_core/validate.yml?label=validate
[validate-url]: https://github.com/kmich/ha_ws_core/actions/workflows/validate.yml
