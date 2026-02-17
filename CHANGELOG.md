# Changelog

## [0.3.1] - 2026-02-17 — Hotfix (correctness + polish)

### Fixed
- Time-based 24h rolling stats (no longer assumes 1 update/minute; resilient to restarts and interval changes)
- Rain total sensor state class set to `total_increasing` for correct long-term statistics
- Prevent parallel Open-Meteo forecast fetch tasks during startup (in-flight guard)
- README dashboard section updated: vanilla dashboard has no custom-card dependencies


## [0.3.0] - 2026-02-17 — Roadmap Phase 1 & 2

### Highlights
- 7-step guided setup wizard asking every relevant question
- Hemisphere and climate region selection (auto-detected from HA location)
- Elevation auto-detected from HA system config and weather station entities
- Full config migration: v1 configs upgrade automatically to v2
- `_compute()` refactored into 8 focused sub-methods (~30 lines each)
- Physics-based sensor quality validation with cross-checks
- All magic numbers replaced with documented named constants
- Disclaimers added to Fire Weather Index and rain probability attributes

### Added

**Setup wizard (7 steps):**
- Step 4 — Location: hemisphere (N/S, auto-detected), climate region (8 presets, auto-guessed from lat/lon), station elevation (auto-detected from HA config and entity attributes)
- Step 5 — Display: wind/rain/pressure units and temperature unit (°C / °F / Auto) as explicit choices
- Step 6 — Forecast: Open-Meteo enable/disable, refresh interval, lat/lon override
- Step 7 — Alerts: all thresholds, filter parameters, activity score toggle

**Hemisphere awareness:**
- Zambretti forecast now respects hemisphere (affects summer/winter season logic)
- Climate region wired through coordinator to Zambretti algorithm

**Sensor quality flags** (`sensor.{prefix}_sensor_quality_flags`):
- Physics range checks: temperature (-60°C to +60°C), humidity (0–100%), pressure (870–1085 hPa)
- Cross-checks: dew point ≤ temperature, gust ≥ wind speed
- New diagnostic sensor exposes flag count + flag list as attributes

**Config migration:**
- `async_migrate_entry` handles v1 → v2 (adds hemisphere, climate_region)
- Hemisphere auto-inferred from HA latitude during migration
- `CONFIG_VERSION = 2` in const.py

**Named physical constants** (replaces all magic numbers):
- `SLP_GAS_CONSTANT_RATIO = 29.263`
- `MAGNUS_A = 17.62`, `MAGNUS_B = 243.12`
- `PRESSURE_TREND_RISING_RAPID = 1.6`, etc.
- `BEAUFORT_BOUNDARIES`, `RAIN_RATE_PHYSICAL_CAP_MMPH`, `WIND_SMOOTH_ALPHA`

**Validation limits:**
- `VALID_TEMP_MIN_C/MAX_C`, `VALID_PRESSURE_MIN/MAX_HPA`, `VALID_ELEVATION_MIN/MAX_M`
- `VALID_WIND_GUST_MAX_MS = 113.0 m/s` (world record) — used as UI upper bound
- Alert threshold inputs validated against physical limits

**Disclaimers (per roadmap §1.4):**
- Fire Weather Index: "Simplified heuristic — NOT suitable for operational fire weather decisions"
- Rain probability: "Heuristic estimate — accuracy depends on sensor quality and local climate patterns"

**Fire weather now uses real 24h rain accumulation** (was hardcoded 0.0)

### Changed

**`coordinator._compute()` refactored into 8 sub-methods:**
- `_compute_raw_readings()` — unit conversion
- `_compute_derived_wind()` — Beaufort, quadrant, smoothing, 24h max
- `_compute_derived_precipitation()` — Kalman filter, rain display
- `_compute_derived_temperature()` — dew point, feels-like, 24h stats
- `_compute_derived_pressure()` — MSLP, trend, Zambretti
- `_compute_rain_probability()` — local + API probability
- `_compute_activity_scores()` — laundry, stargazing, fire, running
- `_compute_health()` — staleness, package status, alerts

**Options flow** now exposes hemisphere, climate region, and temp unit alongside all existing settings

**`strings.json` / `translations/en.json`** fully updated with all new step and field labels

**Removed:**
- `temp_check/` scratch folder (removed in v0.2.1)
- Zip files from repository root (removed in v0.2.1)

---

## [0.2.1] - 2026-02-17 — Bug Fixes

### Fixed
- `NameError`: `DEFAULT_ENABLE_ACTIVITY_SCORES` not imported in config_flow.py
- Options changes silently did nothing (missing `add_update_listener`)
- 5 `_LOGGER.error()` debug calls left in `async_step_settings`
- `async_step_settings` only exposed elevation — all other settings hidden
- `weather.py` used deprecated `temperature`/`pressure`/`wind_speed` properties
- `weather.condition` was `None` when forecast API unavailable
- Dew point formula used different constants in algorithms.py vs coordinator.py
- Fire weather hardcoded `rain_24h = 0.0`
- Running score computed but never exposed as a sensor
- `hacs.json` version mismatch (`2024.6.0` vs `2026.2+`)

### Added
- `add_update_listener` wired in `async_setup_entry`
- `weather.condition` fallback to local 36-condition classifier
- `sensor.{prefix}_running_score` (disabled by default)
- GitHub Actions: `validate.yml` (lint + hassfest + HACS validation + tests)
- GitHub Actions: `release.yml` (auto-build release zip on tag)
- `tests/test_algorithms.py` with 35 algorithm checks

---

## [0.2.0] - 2026-02-17

Full restoration of all meteorological algorithms from the original YAML package.
See original CHANGELOG for details.

---

## [0.1.2] - 2026-02-16
- Fixed deprecation warnings for HA 2026.2 compatibility

## [0.1.1] - 2026-02-15
- Initial HACS release
