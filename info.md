# Weather Station Core

**Turn any personal weather station into a comprehensive, scientifically-grounded weather intelligence hub for Home Assistant.**

## What it does

Weather Station Core reads raw sensor data from your existing weather station (Ecowitt, Davis, WeatherFlow, Shelly, etc.) and produces ~25 derived meteorological values -- all through a guided config flow, no YAML required.

## Highlights

- **Real Zambretti barometric forecaster** (Negretti & Zambra lookup table, Z-numbers 1-26, calibrated for your climate region)
- **Wet-bulb temperature** (Stull 2011), **frost point** (Buck 1981 ice constants)
- **Climate-region-aware** rain probability with Open-Meteo blending
- **Kalman-filtered rain rate** for de-noised precipitation readings
- **36-condition weather classifier** using both local sensors and Open-Meteo
- **Risk sensors** (opt-in): fire risk, fog probability, thunderstorm risk
- **Air Quality + Pollen** via Open-Meteo (free, no API key required)
- **Moon phase & illumination** calculated astronomically
- **Solar PV forecast** via forecast.solar (free, no API key)
- **7-day forecast** via Open-Meteo (free, no API key)
- **Config entities on device page**: thresholds, calibration offsets, and feature toggles as `number` and `switch` entities
- **Proper HA integration**: config flow, options flow, diagnostics, device registry

## v1.3.0 — what changed

- ~25 active sensors (down from 80+). Integration is called *Core* for a reason.
- Removed METAR family, lifestyle scores, degree days, CWOP upload, CSV/JSON export
- Pollen now via Open-Meteo (free, no API key) instead of Tomorrow.io
- Fixed: `weather.ws` condition now uses local sensor data instead of Open-Meteo's daily summary
- Fixed: `ws_uv_level` shows "None" at night instead of `unknown`
- Fixed: `ws_zambretti_forecast` output calibrated for Mediterranean climate

## Requirements

A personal weather station integrated into Home Assistant providing at minimum: temperature, humidity, pressure, wind speed, wind gust, wind direction, and cumulative rainfall.
