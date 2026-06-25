# Weather Station Core

**Turn any personal weather station into a complete weather intelligence system.**

Weather Station Core (`ws_core`) is a Home Assistant custom integration that reads raw
sensor data from any HA-integrated weather station and derives 150+ meteorological
values through a guided setup flow.

---

## What it does

You provide 7 sensor entities — temperature, humidity, pressure, wind speed, wind gust,
wind direction, cumulative rainfall. ws_core does the rest.

### Capabilities not available in any other HA weather integration

- **Precipitation nowcast** with minutes-until-rain precision
  (`sensor.ws_minutes_until_rain`)
- **UTCI** (Universal Thermal Climate Index, full Bröde 2012 polynomial)
- **Three fire danger systems**: Canadian FWI, McArthur FFDI (Australia),
  Fosberg FFWI (US/global)
- **Zambretti barometric forecast** — fully local, no network call, no API
- **Penman-Monteith ET₀** for irrigation scheduling (Smart Irrigation compatible)
- **8 upload targets** in one integration (WU, Weathercloud, WOW, CWOP, and more)
- **8 translations** at full entity-name parity, including translatable config-flow selectors (hemisphere, climate region) and localized human-readable sensor states (conditions summary, alerts, frost risk)

### Always-on (core features, no API key required)

| What | How |
|---|---|
| Zambretti forecast | From your station's pressure + wind data |
| 36-condition classifier | From illuminance, rain rate, temperature, wind |
| Wet-bulb, frost point, frost risk | Stull (2011), Buck (1981) + frost-risk category |
| Pressure trend | WMO No. 306 least-squares regression |
| Kalman-filtered rain rate | De-noised tipping-bucket readings |
| ET₀ (Hargreaves-Samani) | No solar radiation sensor required |
| Moon phase and illumination | Meeus (1998) astronomical algorithms |
| Adaptive rain probability | 90-day Brier-score blended local + NWP |
| Streak counters | Dry days, heat days, frost days |

### Optional feature groups

| Group | What it adds |
|---|---|
| Comfort Indices | Heat Index, Wind Chill, Humidex, **UTCI**, WBGT, VPD, Delta-T, THW, THSW, chill hours, clearness index, cloud cover |
| Precipitation Nowcast | `ws_minutes_until_rain`, `ws_minutes_until_dry`, `ws_rain_next_60min`, `ws_rain_expected_1h` |
| Fire Risk | FWI, FFDI, FFWI, fire risk score (1-10) |
| Lightning Detection | Strike count, distance, rate, clearance countdown, proximity state |
| Indoor Sensors | Indoor temp/humidity/CO₂, deltas, comfort score, per-room deltas |
| Degree Days | HDD, CDD, GDD, leaf wetness |
| Air Quality | AQI, NO₂, ozone (Open-Meteo, free) |
| Network Uploads | WU, Weathercloud, PWSWeather, WOW, AWEKAS, CWOP, OWM Stations, Windy |
| MQTT Discovery | 70+ sensors as MQTT Discovery payloads |
| Station Diagnostics | Drift detection, spike flags, spatial QC, data-quality score |

---

## Getting started

See the [Quickstart](quickstart.md) for a 5-minute installation walkthrough.

---

## Project status

- **Version:** 2.5.2 (June 2026)
- **License:** MIT
- **Repository:** [github.com/kmich/ha_ws_core](https://github.com/kmich/ha_ws_core)
- **Issues:** [GitHub Issues](https://github.com/kmich/ha_ws_core/issues)
