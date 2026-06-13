# Weather Station Core

**Turn any personal weather station into a comprehensive, scientifically-grounded weather intelligence hub for Home Assistant.**

---

![Weather dashboard](https://raw.githubusercontent.com/kmich/ha_ws_core/main/screenshots/dashboard-weather.png)

![Advanced dashboard](https://raw.githubusercontent.com/kmich/ha_ws_core/main/screenshots/dashboard-advanced.png)

---

## What it does

Weather Station Core reads raw sensor data from your existing weather station (Ecowitt, Davis, WeatherFlow, Shelly, etc.) and produces 150+ derived meteorological sensors - all through a guided config flow, no YAML required.

## Highlights

- **Real Zambretti barometric forecaster** (Negretti & Zambra lookup table, Z-numbers 1-26)
- **Wet-bulb temperature** (Stull 2011), **frost point** (Buck 1981 ice constants)
- **Nowcast correction** - local station readings blend into the 0-3h hourly forecast, tapering smoothly to pure NWP by hour 3
- **Adaptive rain probability** - Brier-score-derived blend weights learn which source (local sensors vs Open-Meteo) has been more accurate recently
- **Forecast agreement sensor** - compares Zambretti's implied rain outlook to Open-Meteo's precip probability; flags `aligned`, `diverging`, or `conflict`
- **Kalman-filtered rain rate** for de-noised precipitation readings
- **36-condition weather classifier** with severity levels
- **Fog probability** and **thunderstorm risk** surface heuristics
- **Comfort & agronomy indices** - Heat Index, Wind Chill, Humidex, Davis THW/THSW, VPD, absolute humidity, Delta-T spray window, wind run, chill hours, clearness index & cloud cover
- **Full Canadian FWI system** - FFMC, DMC, DC, ISI, BUI, FWI, DSR with persistent daily moisture memory (Van Wagner 1987); **streak counters** (dry/heat/frost days)
- **7-day forecast** via Open-Meteo (free, no API key)
- **Air quality, pollen, moon phase, solar PV forecast, sea surface temperature** - all optional
- **ET₀ evapotranspiration** (Hargreaves-Samani, upgrades to Penman-Monteith with solar radiation sensor)
- **Pluggable forecast provider** - Open-Meteo (default), Met.no, NWS/NOAA, OpenWeatherMap, Pirate Weather, Météo France, or any existing **Home Assistant `weather.*` entity** — switch provider from the Configure menu at any time, no reinstall needed
- **`apply_calibration` service** - write temperature, humidity, pressure, or wind calibration offsets from an automation or Developer Tools without opening the config flow
- **Full imperial unit support** - all sensors with a `device_class` auto-convert to °F / mph / inches when HA is set to imperial
- **Ground-truth nowcast blending** — local rain gauge blended into the 0–30 min NWP forecast window; `nowcast_confidence` sensor shows agreement level
- **Soil sensor support** — soil moisture, temperature, deficit, and irrigation need (None/Low/Moderate/High/Critical) from optional soil sensors
- **90-day seasonal anomaly sensors** — temperature and rain anomaly vs the 90-day micro-climate baseline
- **Alert hysteresis** — wind/rain/freeze alerts debounced across multiple ticks; no more chatty notifications from sensor noise
- **Five automation blueprints** — heat, freeze, rain, wind, and AQI alerts with configurable thresholds
- **Config entities on device page**: all thresholds, calibration offsets, and feature toggles exposed as `number` and `switch` entities - adjust settings directly without entering the config flow

## Requirements

A personal weather station integrated into Home Assistant providing at minimum: temperature, humidity, pressure, wind speed, wind gust, wind direction, and cumulative rainfall.
