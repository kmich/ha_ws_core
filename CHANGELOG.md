# Changelog

All notable changes to Weather Station Core are documented here.

## [1.4.2] - 2026-05-21

### Bug Fixes

- **Weather Underground `softwaretype` was stale** — hardcoded to `"ws_core_0.6.0"` since the initial release. Now reads the version dynamically from `manifest.json` at startup, so WU upload reports the correct software version automatically on every release.

### Cleanup

- **Extracted forecast agreement thresholds to constants** — `FORECAST_AGREEMENT_ALIGNED_PP = 20` and `FORECAST_AGREEMENT_CONFLICT_PP = 40` defined in `const.py`; the `_compute_forecast_agreement` logic now references these instead of bare integers.
- **Extracted drift detection thresholds to constants** — `DRIFT_SLOPE_TEMP_C_H`, `DRIFT_SLOPE_HUMIDITY_PCT_H`, `DRIFT_SLOPE_PRESSURE_HPA_H`, `DRIFT_R_SQ_THRESH`, `DRIFT_STUCK_BUCKET_SAMPLES`, `DRIFT_STUCK_BUCKET_MIN_RATE`, `DRIFT_STUCK_RATE_RANGE_MAX` added to `const.py`; `_compute_drift_detection` uses them throughout.
- **Alert threshold lookups now use `CONF_*` / `DEFAULT_*` constants** — three `.entry_options.get("thresh_...", <hardcoded>)` calls replaced with their proper `const.py` symbols (`CONF_THRESH_WIND_GUST_MS`, `CONF_THRESH_RAIN_RATE_MMPH`, `CONF_THRESH_FREEZE_C` and their `DEFAULT_*` counterparts).
- **Coordinator header version updated** — docstring still referenced `v0.3.0`.

## [1.4.1] - 2026-05-21

### Bug Fixes

- **Patch release to fix v1.4.0 release artifact** — the v1.4.0 GitHub release zip was published before CI fixes were committed, causing `translations/en.json` to contain a trailing comma that prevented the integration from loading. No code changes beyond the version bump; the fix was already on `main`.

## [1.4.0] - 2026-05-21

### New Features

- **`apply_calibration` service action** — write sensor calibration offsets directly from an automation or the Developer Tools UI without opening the config flow. Supports `cal_temp_c`, `cal_humidity`, `cal_pressure_hpa`, `cal_wind_ms`; reloads the entry immediately. Documented in `services.yaml` with full field selectors.
- **`temperature_anomaly_30d` and `rain_anomaly_30d` now unit-aware** — added `device_class=TEMPERATURE` and `device_class=PRECIPITATION` respectively so HA auto-converts values to °F / inches for imperial users, just like every other sensor.

### Bug Fixes

- **`wu_status` now translatable** — replaced dynamic strings like `"OK 14:32"` and `"Error HTTP 403: ..."` with enum state keys (`disabled`, `ok`, `error_http`, `error_network`, `error`). Last successful upload timestamp moved to the `last_upload` state attribute. State translations added in English and French.

### Cleanup

- **Removed dead `laundry_reminder.yaml` blueprint** — `sensor.ws_laundry_drying_score` was removed in v0.3.0; this blueprint has been broken for years. `blueprints/README.md` updated accordingly.
- **Removed dead config constants** — `CONF_ENABLE_LAUNDRY`, `CONF_ENABLE_STARGAZING`, `CONF_ENABLE_RUNNING`, `CONF_ENABLE_METAR`, `CONF_METAR_*`, `CONF_ENABLE_CWOP`, `CONF_CWOP_*`, `CONF_ENABLE_EXPORT`, `CONF_EXPORT_*`, `CONF_ENABLE_DEGREE_DAYS`, `CONF_DEGREE_DAY_BASE_C`, `CONF_ENABLE_ACTIVITY_SCORES`, `CONF_ENABLE_EXTENDED_SENSORS` and their corresponding defaults removed from `const.py`. All are already listed in `DEPRECATED_CONF_KEYS_V030` for migration.
- **Removed dead `rain_penalty` config fields** — `rain_penalty_light_mmph` and `rain_penalty_heavy_mmph` were config flow fields for the removed laundry/activity score feature. Removed from `config_flow.py`, `strings.json`, `en.json`, `fr.json`, and `number.py` comment.
- **Removed empty tracked files** — `git` and `ruff` (zero-byte files accidentally committed) removed from the repo.
- **Added `.ruff_cache/` to `.gitignore`** — the ruff cache directory was not gitignored.
- **Dashboard version headers updated** — `weather_dashboard.yaml` and `weather_dashboard_vanilla.yaml` were still labelled `v1.0.0`.
- **Entity map regenerated** — `docs/entity_map.html` was showing `WS Core 1.1.0`; regenerated at v1.4.0 (84 sensors, 11 switches).

## [1.3.2] - 2026-05-19

### Bug Fixes

- **Rain display state now translatable** — `sensor.ws_rain_display` was returning dynamic strings like `"Heavy (3.5 mm/h)"` which can't be used as translation keys. Fixed to return snake_case intensity keys (`dry`, `drizzle`, `light`, `moderate`, `heavy`) with the numeric rate already available in the `rain_rate` attribute. State translations added to all three translation files (closes #8). Reported by @Benjamin45590.

### Improvements

- **French translation polish** — 12 wording improvements contributed by @Benjamin45590: clearer descriptions for the location step, forecast step, and features options; improved Zambretti state labels (`"averses en début de journée"`, `"instable, éclaircies à venir"`, etc.); `"Pluie du jour"` instead of `"Pluie aujourd'hui"`; fog and thunderstorm risk labels shortened; pollen `"none"` changed from `"Nul"` to `"Aucun"`. PR #11.

## [1.3.1] - 2026-05-18

### Improvements

- **Sensor state translations** - all string-state sensors now have translatable values. 11 sensors covered: current condition (29 weather states), Zambretti forecast (25 phrases), pressure trend, alert state, station health, humidity level, UV level, pollen level, forecast agreement, sensor drift, sensor consistency. French translations included throughout.

## [1.3.0] - 2026-05-18

### New Features

- **Météo France forecast provider** — adds Météo France via the Météo Concept API as a 6th provider option. Free tier available, API key required (get one at api.meteo-concept.com). Full daily (7-day) and hourly (24-hour) support with correct WMO weathercode mapping. Contributed by @Benjamin45590.

## [1.2.3] - 2026-05-18

### Bug Fixes

- **Switch, number, select, and binary sensor names now translatable** — all non-sensor entity types (feature toggles, config numbers, graph range select, package OK binary sensor) were still using hardcoded English names. Wired up `has_entity_name = True` and `translation_key` on all four entity classes so names render in the user's language. French translations included (closes #8).

## [1.2.2] - 2026-05-18

### Improvements

- **French translation polish** — 16 copy improvements from native speaker @Benjamin45590: correct term for illuminance (`Éclairement`), missing grammatical articles added, more natural phrasing throughout (`Il pleut`, `Paquet OK`, `Température de surface de la mer`, etc.).

## [1.2.1] - 2026-05-18

### Bug Fixes

- **Entity attribute labels now translatable** — removed hardcoded English metadata strings (`method`, `reference`, `disclaimer`, etc.) from entity attributes; these were developer-documentation noise that couldn't be localised. All remaining attribute keys (`wind_contribution_ms`, `z_number`, `danger_level`, etc.) now have `state_attributes` translations in `strings.json`, `en.json`, and `fr.json`, so the labels render in the user's language in the HA UI (closes #6, thanks @Benjamin45590).
- **README updated** — added Forecast Provider section, corrected sensor count, added missing sensors (`ws_rain_today`, `ws_no2`, `ws_ozone`, `ws_forecast_agreement`), and documented the provider contribution path.

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
