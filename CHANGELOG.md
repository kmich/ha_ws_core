# Changelog

All notable changes to Weather Station Core are documented in this file.

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
