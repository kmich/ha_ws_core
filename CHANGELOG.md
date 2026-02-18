# Changelog

All notable changes to Weather Station Core are documented in this file.

## [1.0.0] - 2026-02-18

### Added
- **Air Quality Index** (v0.7.0): PM2.5, PM10, NO₂, ozone via Open-Meteo AQI API. Free, no API key. Uses forecast lat/lon. Enable with `enable_air_quality`. Sensors: `sensor.ws_air_quality_index`, `sensor.ws_air_quality_level`.
- **Pollen levels** (v0.7.0): Grass, tree, and weed pollen indices via Tomorrow.io. Free API key required. Enable with `enable_pollen`. Sensors: `sensor.ws_pollen_overall`, `sensor.ws_pollen_grass`, `sensor.ws_pollen_tree`, `sensor.ws_pollen_weed`. Interval: 6h default (free tier: 500 calls/day).
- **Moon phase & illumination** (v0.8.0): Calculated from astronomical algorithms, no external API. Enable with `enable_moon`. Sensors: `sensor.ws_moon_display`, `sensor.ws_moon_phase`, `sensor.ws_moon_illumination_pct`. Attributes include age, days to next full/new moon.
- **Solar PV forecast** (v0.9.0): Daily generation forecast (kWh) via forecast.solar. Free, no API key. Configurable peak kWp, panel azimuth, and tilt. Enable with `enable_solar_forecast`. Sensors: `sensor.ws_solar_forecast_today_kwh`, `sensor.ws_solar_forecast_tomorrow_kwh`.
- **Penman-Monteith ET₀** (v0.9.0): Higher-accuracy evapotranspiration when a solar radiation sensor (`solar_radiation` source, W/m²) is configured. Activates automatically. Sensor: `sensor.ws_et0_pm_daily_mm`. Replaces Hargreaves-Samani when available.
- **Multi-step options flow** (v1.0.0): The Configure button now guides through all settings in discrete steps (Core → Features → per-feature sub-steps), matching the initial config flow. Every option from the config flow is now accessible post-install without reinstalling.
- **METAR ICAO auto-detection** (v1.0.0): Leave the ICAO field blank during setup to automatically find the nearest airport from your forecast lat/lon via aviationweather.gov.
- **Weather Underground credential validation** (v1.0.0): Station ID and API key are validated against the WU API before saving; setup shows an error immediately if the credentials are invalid.
- **Tomorrow.io pollen key validation** (v1.0.0): API key is validated at setup time and in the options flow.
- **Unit tests** (v1.0.0): 44 algorithm tests covering dew point, sea-level pressure, apparent temperature, Beaufort, Zambretti, UV, laundry, AQI, pollen, moon phases, ET₀, Kalman filtering. All pass. Run with `pytest tests/`.
- **GitHub Actions CI** (v1.0.0): Automatically runs ruff linting, ruff format check, unit tests, and hassfest on every push and pull request.

### Changed
- Config flow features step now includes all v0.7–0.9 toggles: air quality, pollen, moon, solar forecast.
- `_autodetect_metar_icao` helper falls back to aviationweather.gov when ICAO field is left blank.


## [0.5.1] - 2026-02-18

### Added (v0.5.0 completion)

- **RestoreEntity mixin**: `WSSensor` now mixes in `RestoreEntity` so sensors that are slow to warm up (24h stats, Kalman filter, degree days, METAR, ET₀) report their last-known value immediately on HA restart instead of showing `unknown` for several minutes.
- **Heating/Cooling Degree Days**: New sensors `sensor.ws_heating_degree_days_today` and `sensor.ws_cooling_degree_days_today` accumulate HDD/CDD throughout the day (resets at midnight). Configurable base temperature (default 18°C). Companion rate sensors (`hdd_rate`, `cdd_rate`) are available as diagnostic sensors for use with HA's Riemann sum utility meter for monthly/seasonal totals. Toggle: `enable_degree_days`.
- **METAR cross-validation**: Fetches aviation METAR from aviationweather.gov (free, no key) for a user-configured ICAO station (e.g. `LGAV`). Exposes `sensor.ws_metar_validation` (Match/Plausible/Check sensor/Stale METAR), `sensor.ws_temp_vs_metar_delta`, `sensor.ws_pressure_vs_metar_delta`, plus raw METAR temperature and pressure sensors. Toggle: `enable_metar`. Config step prompts for ICAO code.
- **Storm banner** (dashboard): A new `custom:button-card` banner that activates automatically when wind Beaufort >= 7 or the condition contains "thunderstorm". Shows Near-Gale / Gale Warning / Storm Warning / Thunderstorm with appropriate colour and pulse animation for severe events. Appears above the existing alert/data quality banners.
- **Wind rose** (dashboard): New section on the Advanced page using `custom:windrose-card` (HACS card). Displays 24h wind direction/speed distribution. Requires `custom:windrose-card` to be installed from HACS.
- **Radar** (dashboard): New section on the Advanced page showing RainViewer live radar iframe, auto-centred on your HA home location. Free, no API key required.

### Added (v0.6.0 preview — sensors available, upload activated via config)

- **ET₀ reference evapotranspiration** (`sensor.ws_et0_daily`, `sensor.ws_et0_hourly`): Hargreaves-Samani 1985 method using daily temp high/low and latitude. Accuracy ±15-20% vs Penman-Monteith; improves with a solar radiation sensor (future enhancement). Activates automatically when forecast lat/lon is configured.
- **CWOP upload** (`sensor.ws_cwop_upload_status`): Uploads observations to cwop.aprs.net via APRS-IS TCP. Configure callsign, passcode (-1 for citizens), and interval. Toggle: `enable_cwop`.
- **Weather Underground upload** (`sensor.ws_wu_upload_status`): Uploads to WUnderground Personal Weather Station API. Configure station ID, API key, and interval. Toggle: `enable_wunderground`.
- **CSV/JSON export** (`sensor.ws_last_export_time`): Periodically writes all sensor readings to `/config/ws_core_export/ws_core_YYYYMMDD.csv` and/or `.json`. Appends to the daily file. Toggle: `enable_export`.

### Changed

- Config flow Features step now shows 12 toggles (added: Degree Days, METAR, CWOP, WUnderground, Export).
- New conditional config steps: `degree_days` (base temp), `metar` (ICAO + interval), `cwop`, `wunderground`, `export`.
- Dashboard `weather_dashboard.yaml` bumped to v2.1.0.



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
