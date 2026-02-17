# Weather Station Core

**Turn any personal weather station into a comprehensive, scientifically-grounded weather intelligence hub for Home Assistant.**

## What it does

Weather Station Core reads raw sensor data from your existing weather station (Ecowitt, Davis, WeatherFlow, Shelly, etc.) and produces 40+ derived meteorological values -- all through a guided 7-step config flow, no YAML required.

## Highlights

- **Real Zambretti barometric forecaster** (Negretti & Zambra lookup table, Z-numbers 1-26)
- **Wet-bulb temperature** (Stull 2011), **frost point** (Buck 1981 ice constants)
- **Climate-region-aware** rain probability with Open-Meteo blending
- **Kalman-filtered rain rate** for de-noised precipitation readings
- **36-condition weather classifier** with severity levels
- **Activity scores**: laundry drying, stargazing, running, fire risk
- **7-day forecast** via Open-Meteo (free, no API key)
- **Proper HA integration**: config flow, options flow, diagnostics, device registry

## Requirements

A personal weather station integrated into Home Assistant providing at minimum: temperature, humidity, pressure, wind speed, wind gust, wind direction, and cumulative rainfall.
