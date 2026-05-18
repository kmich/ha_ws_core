# Changelog

All notable changes to Weather Station Core are documented here.

## [1.2.0] - 2026-05-18

### New Features

- **Pluggable forecast provider** — `sensor.ws_forecast_daily` and all NWP-derived sensors now use a swappable provider. Select in the config/options flow. Ships with two built-in providers: **Open-Meteo** (default, free, no API key) and **Met.no** (Norwegian Meteorological Institute, free, no API key, strong European coverage). Adding new providers requires only a new Python file + one-line registry entry.
- **Nowcast correction (0–3 h) — now actually implemented** — local station readings blend into the first three hourly forecast slots with tapering weights (70 % local at h+0, 40 % at h+1, 10 % at h+2, pure NWP from h+3). Blended fields: temperature, humidity, wind speed, dew point.
- **NO₂ and Ozone sensors** — `sensor.ws_no2` and `sensor.ws_ozone` expose the nitrogen dioxide and ozone values already fetched by the AQI module as standalone sensors (µg/m³, disabled by the Air Quality toggle, diagnostic category).
- **Rain Today sensor** — `sensor.ws_rain_today` exposes today's accumulated rainfall (resets at local midnight), separate from the 24 h rolling window.

## [1.1.1] - 2026-05-18

### Bug Fixes

- **All 82 sensor names now translatable** — sensors now use HA's `translation_key` + `has_entity_name` mechanism. Display names update automatically when HA language is changed (e.g. French users see "Température" instead of "WS Temperature"). Entity IDs are unchanged. French translations included out of the box (closes #4, thanks @Benjamin45590).

## [1.1.0] - 2026-05-18

### New Features

- **Full Canadian FWI system** — complete Van Wagner (1987) implementation: FFMC, DMC, DC daily moisture codes with persistent carry-over across HA restarts, ISI, BUI, FWI, DSR. Replaces the previous simplified heuristic. `sensor.ws_fire_risk_score` maps real FWI to a 1–10 danger scale; seven sub-index sensors available (disabled by default).
- **Nowcast correction (0–3h)** — local station readings (temperature, humidity, wind, dew point, rain rate, condition) blend into the first three hourly forecast slots using tapering weights (70 % local at hour 0, pure NWP by hour 3).
- **Adaptive rain probability** — `sensor.ws_rain_probability_combined` uses rolling 90-day Brier-score weights that learn which source (local sensors vs Open-Meteo) has been more accurate; falls back to fixed day/night weights until enough data accumulates.
- **Forecast agreement sensor** — `sensor.ws_forecast_agreement` compares Zambretti Z-number implied rain likelihood to Open-Meteo `precip_prob`; states: `aligned` (< 20 pp delta), `diverging` (20–40 pp), `conflict` (> 40 pp).
- **French translation** — complete `fr.json` covering config flow, options flow, entity names, and issues (thanks @Benjamin45590).

### Bug Fixes

- **Configure button 500 error on HA 2024.3+** — `async_get_options_flow` updated to `@classmethod` + `@callback`; framework now injects `self.config_entry` automatically (thanks @miczu71, PR #2).
- **AQI level attribute always `None`** — `KEY_AQI_LEVEL` was never written to the coordinator data dict; now populated from cached AQI data.
- **Moon phase attribute always `None`** — moon phase was stored under private key `_moon_phase` but sensor read `KEY_MOON_PHASE`; keys aligned.
- **Staleness timeout selector rejected default** — selector max was 3 600 s but default is 7 200 s; raised to 86 400 s (24 h).
- **`enable_fog` shown as raw key in config flow** — translation key was `enable_fog_probability`; aligned to `enable_fog` to match the const.
- **10 additional string/key audit fixes** — orphaned `enable_zambretti` translation, missing `ws_enable_fog` and `ws_enable_thunderstorm_risk` switch entries, missing `features_opt` data descriptions, pollen incorrectly attributed to Tomorrow.io.

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
- **Full Canadian FWI system** — complete Van Wagner (1987) implementation: FFMC, DMC, DC (daily moisture codes with persistent carry-over), ISI, BUI, FWI, DSR. `sensor.ws_fire_risk_score` now maps real FWI to a 1–10 danger scale. Seven FWI sub-index sensors available (disabled by default).
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
- **Nowcast correction (0–3h)** — local station readings (temperature, humidity, wind, dew point, rain rate, condition) blend into the first three hourly forecast slots using tapering weights (70% local at hour 0, pure NWP by hour 3).
- **Adaptive rain probability** — `sensor.ws_rain_probability_combined` uses rolling 90-day Brier-score weights that learn which source (local sensors vs Open-Meteo) has been more accurate; falls back to fixed day/night weights until enough data accumulates.
- **Forecast agreement sensor** — `sensor.ws_forecast_agreement` compares Zambretti Z-number implied rain likelihood to Open-Meteo `precip_prob`; states: `aligned` (< 20 pp delta), `diverging` (20–40 pp), `conflict` (> 40 pp).

### Integration

- Guided config flow (8 steps + optional feature sub-steps). All settings reconfigurable post-install via Configure button.
- Config entities on device page: 10 `number` entities for thresholds, calibration offsets, and algorithm parameters; 10 `switch` entities for feature toggles. Changes trigger coordinator reload automatically.
- Standard HA `weather` entity with daily forecast.
- Diagnostics export (location data redacted).
- HACS-compatible.
- CI: ruff lint, hassfest, HACS validation, unit tests, version consistency check, no-bytecode check, dashboard entity validator.
