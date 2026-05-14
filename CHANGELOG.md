# Changelog

All notable changes to Weather Station Core are documented here.

## [1.0.0] - 2026-05-14

Initial public release.

### Features

- **Zambretti barometric forecaster** — authentic Negretti & Zambra lookup table (Z-numbers 1–26) with climate-region-aware wind corrections and seasonal adjustment. Accuracy 65–75% for 6–12h forecasts in maritime/Mediterranean climates.
- **36-condition weather classifier** — real-time condition derived from illuminance, rain rate, wind gust, and temperature, with severity levels and MDI icon mapping.
- **Wet-bulb temperature** (Stull 2011, ±0.3 °C), **frost point** (Buck 1981 ice constants), **apparent temperature** (Australian BOM/Steadman).
- **Kalman-filtered rain rate** — eliminates tipping-bucket spike-and-drop artefacts. Configurable smoothing coefficient.
- **Pressure trend** — least-squares regression over configurable window (default 3h), classified per WMO Table 4680.
- **Fog probability** — dew-point depression model with wind-speed and nocturnal corrections.
- **Thunderstorm risk index** — surface-based heuristic (T–Td gap, pressure fall rate, wind acceleration, illuminance drop).
- **Fire risk score** — simplified 0–50 heuristic inspired by Canadian FWI structure (Van Wagner 1987). Not suitable for operational fire weather decisions.
- **Streak counters** — consecutive dry, heat, and frost days, reset at local midnight.
- **24h rolling statistics** — temperature high/low, wind gust maximum.
- **Rain accumulation** — 1h and 24h rolling windows, plus today's total.
- **ET₀ reference evapotranspiration** — Hargreaves-Samani 1985 by default; upgrades to FAO-56 Penman-Monteith automatically when a solar radiation sensor (W/m²) is mapped.
- **7-day daily forecast** — Open-Meteo (free, no API key).
- **Air Quality Index** — PM2.5-based US EPA AQI via Open-Meteo (free, no API key).
- **Pollen levels** — grass, tree, weed via Tomorrow.io (free API key required).
- **Moon phase & illumination** — calculated from Meeus 1998 astronomical algorithms, no external API.
- **Solar PV forecast** — today + tomorrow kWh via forecast.solar (free, no API key). Configurable peak kWp, azimuth, tilt.
- **Sea surface temperature** — Open-Meteo Marine API (free, no API key). Optional lat/lon override.
- **Weather Underground upload** — credentials validated at setup; configurable interval.
- **30-day rolling climatology** — local temperature and rain anomalies built from station history. Meaningful after ~14 days.
- **Sensor drift detection** — 72h linear regression flags monotonic drift (R² ≥ 0.85) in temperature, humidity, pressure, and rain rate.
- **Cross-sensor consistency** — six physical-impossibility checks (dew point > temp, gust < wind speed, UV/lux mismatch, etc.).
- **Self-adapting solar lux factor** — updates lux→W/m² conversion on clear days near solar noon, improving ET₀ accuracy over time.

### Integration

- Guided config flow (8 steps + optional feature sub-steps). All settings reconfigurable post-install via Configure button.
- Config entities on device page: 10 `number` entities for thresholds, calibration offsets, and algorithm parameters; 10 `switch` entities for feature toggles. Changes trigger coordinator reload automatically.
- Standard HA `weather` entity with daily forecast.
- Diagnostics export (location data redacted).
- HACS-compatible.
- CI: ruff lint, hassfest, HACS validation, unit tests, version consistency check, no-bytecode check, dashboard entity validator.
