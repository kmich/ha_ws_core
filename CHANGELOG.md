# Changelog

All notable changes to Weather Station Core are documented in this file.

## [0.5.0] - 2026-02-18

### Added
- **Sea Surface Temperature**: New `sensor.ws_sea_surface_temperature` via Open-Meteo Marine API. Opt-in toggle with separate lat/lon override. Attributes include swimming comfort label (Cold/Cool/Comfortable/Warm/Hot), 24h hourly forecast, and grid cell metadata.
- **Granular feature toggles**: Each sensor group now has its own on/off toggle in both setup wizard and Configure:
  - Zambretti forecast & weather classifier
  - Display sensors (humidity level, UV level, pressure trend, station health)
  - Laundry drying score
  - Stargazing quality
  - Fire risk score
  - Running conditions score
  - Sea surface temperature
- **Sea temperature dashboard card**: Conditional card on Advanced page showing current SST, comfort badge, and 24h range.
- **Config flow step**: New `sea_temp` step shown when sea temp is enabled, for lat/lon override.

### Fixed
- **Staleness false positives**: Only core weather sensors (temp, humidity, pressure, wind speed/gust/direction) are now checked for staleness. Rain total (static when dry), UV index (zero at night), battery (slow-reporting), and dew point are excluded. Fixes the "sensors are stale" warning for rain_total, uv_index, battery.
- **Activity score unit migration**: Added explicit `native_unit="score"` to laundry drying score, fire risk score, and running score. Fixes "The unit has changed" statistics migration prompt.

### Changed
- **Feature toggles replace coarse groups**: The old `enable_extended_sensors` and `enable_activity_scores` toggles are replaced by individual per-feature toggles. Existing configs auto-migrate via fallback defaults in the Options flow.
- Config flow step 7 (Features) now shows 7 individual toggles instead of 2 group toggles.

## [0.4.5] - 2026-02-18

### Added
- **`select.ws_graph_range`**: Integration-owned select entity for dashboard graph time range (6h/24h/3d). Replaces manual `input_select` helper — auto-created, state restored on restart.
- **`switch.ws_enable_animations`**: Integration-owned switch for dashboard animation toggle. Replaces manual `input_boolean` helper — auto-created, state restored on restart.
- **New platforms**: `select` and `switch` added to integration platforms.

### Fixed
- **Fire Risk Score attributes**: Added `temperature_c`, `humidity_pct`, `wind_ms` to fire risk sensor attributes (dashboard card showed N/A).
- **Dashboard: zero manual helpers**: All `input_select.*` and `input_boolean.*` references replaced with integration-owned entities. Users no longer need to create any helpers manually.
- **Dashboard: advanced features boolean removed**: Nav button always shows active (feature visibility is now controlled by config flow toggles).
- **Dashboard: wildfire risk boolean removed**: Fire risk card visibility now checks if `sensor.ws_fire_risk_score` entity exists (controlled by Activity Scores toggle in config).

### Changed
- `PLATFORMS` expanded to `["sensor", "binary_sensor", "weather", "select", "switch"]`.

## [0.4.4] - 2026-02-18

### Added
- **Rain nowcasting sensors**: `rain_last_1h`, `rain_last_24h` (precipitation device class), `time_since_rain` (human-readable "3h ago" / "No rain recorded").

### Fixed
- **7 entities had broken slugs**: `_slug_for_key()` had no fallback return — `KEY_LUX`, `KEY_UV`, `KEY_ALERT_STATE`, `KEY_ALERT_MESSAGE`, `KEY_PACKAGE_STATUS`, `KEY_PRESSURE_CHANGE_WINDOW_HPA`, `KEY_PRESSURE_TREND_HPAH` all generated `sensor.ws_None`. Added missing overrides + fallback.
- **Activity scores no longer disabled by default**: When the user enables "Activity scores" in Features, the 4 entities appear enabled immediately (removed double-gating from `_DISABLED_BY_DEFAULT`).
- **Dashboard entity references**: Fixed stale `ws_01_*` entity names → current `ws_*` names; `ws_fire_weather_index` → `ws_fire_risk_score`.
- **Dashboard advanced page alignment**: Paired cards into `column_span: 2` row sections (Moon+UV, Laundry+Fire, Rain+Temp, Wind+Pressure align side-by-side).
- **Dashboard helper requirements**: Documented all required HA helpers in dashboard header.

### Note
After upgrading, remove and re-add the integration to clear stale entity registry entries. You must also create the required HA helpers for the advanced dashboard (see dashboard file header).

## [0.4.3] - 2026-02-18

### Added
- **Features step in config flow**: New dedicated step during initial setup with clear toggles for "Extended analysis" (Zambretti, classifier, display sensors) and "Activity scores" (laundry, stargazing, fire, running). Both also available in Options flow (Configure button).
- **Sensor group filtering**: Sensors are now only created when their feature group is enabled. Disabling a group removes its entities entirely instead of just hiding them.
- **Weather entity: apparent temperature, dew point, wind gust, UV index** — standard HA weather entity attributes now properly exposed.
- **Forecast: precipitation probability** (daily), **wind gust, apparent temp, dew point, cloud coverage** (hourly) — expanded Open-Meteo API request.
- **Calibration offsets**: Temperature, humidity, pressure, and wind speed offsets in Options flow.

### Fixed
- **Rain rate `device_class`**: Added `SensorDeviceClass.PRECIPITATION_INTENSITY` to rain rate sensors. Missing device class could cause HA to show "no unique ID" warning for stale entities.
- **Rain rate entity name**: Renamed from "WS Rain Rate Filtered" to "WS Rain Rate" for cleaner display.
- **Activity scores toggle**: Moved from buried position in Alerts step to prominent Features step.
- **Repo cleanup**: Actually removed `.BAK`/`.BROKEN` files, `themes/`, old `.md` issue templates from git.
- **BOM encoding**: Removed UTF-8 BOM from `release.yml`.
- **README Zambretti**: Clarified as authentic N&Z lookup table, not parameterized approximation.

### Changed
- Dashboard v1.1.0: Restructured into 4 pages (Weather, Analysis, Station, Activities) with conditional cards for optional sensor groups.
- Config flow is now 8 steps: User → Required Sources → Optional Sources → Location → Display → Forecast → **Features** → Alerts.

### Note
If you see "no unique ID" warnings on rain rate or other sensors after upgrading, remove the integration and re-add it. This clears stale entity registry entries from earlier versions.

## [0.4.2] - 2026-02-18

### Added
- **Weather entity: apparent temperature, dew point, wind gust, UV index** — standard HA weather entity attributes now properly exposed (were only available as separate sensors before).
- **Daily forecast: precipitation probability** — already fetched from Open-Meteo but was not included in forecast output.
- **Hourly forecast: apparent temperature, dew point, wind gust, cloud coverage** — expanded Open-Meteo API request to provide richer hourly data.
- **Daily forecast: wind gust** — added `windgusts_10m_max` from Open-Meteo.
- **Calibration offsets**: Temperature, humidity, pressure, and wind speed offsets in Options flow. Applied after unit conversion, before all derived calculations.
- **HACS `ignore: brands`** in validate.yml to prevent false CI failures before brands PR is merged.

### Fixed
- **Repo cleanup**: Actually removed `.BAK`/`.BROKEN` files, `themes/` directory, and old `.md` issue templates from git tracking (deletions from 0.4.0 were documented but not committed).
- **BOM encoding**: Removed UTF-8 BOM from `release.yml` that could cause YAML parse issues.
- **README Zambretti description**: Clarified that the implementation uses the authentic Negretti & Zambra lookup table, not a parameterized approximation.

### Changed
- Structured `.yml` GitHub issue templates now properly tracked (replacing old `.md` templates).
- Version 0.4.2 aligned across manifest.json, pyproject.toml, and __init__.py.

## [0.4.1] - 2026-02-17

### Fixed
- **Config flow crash on HA 2025.12+**: `NumberSelectorConfig(step=0.0001)` rejected by newer HA versions; changed to `step=0.001` for lat/lon selectors.
- **Removed `hass.config.units.is_metric`**: Property removed in HA 2025.12; replaced with `temperature_unit == "°C"` check.
- **OptionsFlow deprecation**: Removed `self.config_entry` assignment in `__init__` (now provided by parent class since HA 2025.12).

## [0.4.0] - 2026-02-17

### Breaking Changes
- `sensor.ws_fire_weather_index` renamed to `sensor.ws_fire_risk_score` (entity ID and key changed)
- Fire Risk Score no longer uses "FRI" unit -- it is now unitless (0-50 scale)
- Zambretti forecast now returns real Negretti & Zambra text (26 categories vs. previous heuristic)

### Fixed
- **Temperature sensor `state_class`**: Changed from `TOTAL_INCREASING` to `MEASUREMENT`. This was causing HA long-term statistics to treat temperature drops as counter resets, producing garbage historical data. **If you had this integration installed previously, you may need to delete and re-add the temperature entity to fix statistics.**
- **Rain total sensor `state_class`**: Changed from `MEASUREMENT` to `TOTAL_INCREASING` for correct cumulative counter handling.
- **`iot_class`**: Changed from `local_push` to `calculated` in manifest.json (integration uses polling + computation, not device push).
- **BOM encoding artifacts**: Removed corrupted Unicode characters in `__init__.py` migration messages.
- **`validate.yml`**: Fixed YAML syntax error (merged line break).
- **Dew point below 0 C**: Now uses Magnus ice constants (a=22.587, b=273.86) for temperatures below freezing, reducing error by ~1 C.

### Added
- **Real Zambretti forecaster**: Implements the Negretti & Zambra lookup table with Z-numbers 1-26, climate-region-aware wind direction corrections, seasonal adjustment, and humidity bias.
- **Zambretti Z-number sensor**: Numeric sensor (1-26) for use in automations.
- **Wet-bulb temperature**: Stull 2011 approximation, +/- 0.3 C accuracy. Critical for heat safety assessment.
- **Frost point**: Separate from dew point, using Buck 1981 ice saturation constants below 0 C.
- **Climate-region-aware rain probability**: Pressure thresholds and wind direction biases now respect the configured climate region instead of using hardcoded Atlantic Europe values.
- **Enhanced diagnostics**: Compute timing, sensor availability stats, forecast API failure counts.
- **Device registry**: All entities now properly grouped under a single "Weather Station Core" device.
- **Vanilla dashboard**: Zero-dependency Lovelace dashboard using only native HA cards.
- **Example automations**: Frost alert, rain notification, laundry reminder, storm warning blueprints.

### Changed
- Rain probability time weighting: Local sensors now weighted higher during daytime convective hours (6-18h), lower during stable/frontal periods. Previously inverted.
- Fire Weather Index renamed to **Fire Risk Score** with explicit disclaimer that it is a simplified heuristic, not the real Canadian FWI system.
- All formula documentation added to README with source references and error bounds.
- Version alignment: manifest.json, CHANGELOG, and GitHub release tags now match.

### Removed
- `pyproject.toml.BAK_*` and `.BROKEN` files
- `themes/` directory (undocumented, unused)
- Duplicate `MOON_ICONS`/`MOON_ILLUMINATION` definitions in algorithms.py

## [0.3.9] - 2026-02-17 (unreleased)
- CI fixes, pyproject.toml iteration (development only)

## [0.3.1] - 2026-02-16
- Added activity scores (laundry, stargazing, fire, running)
- 36-condition weather classifier
- Zambretti-inspired barometric forecast (heuristic)
- Kalman-filtered rain rate
- 7-step config flow with auto-detection

## [0.2.0] - 2026-02-15
- Advanced meteorological sensors (feels-like, Beaufort, pressure trend)
- Open-Meteo 7-day forecast integration
- Config migration v1 -> v2 (hemisphere, climate region)

## [0.1.0] - 2026-02-14
- Initial release: 14 core sensors, config flow, unit conversion
