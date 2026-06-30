# Changelog

All notable changes to Weather Station Core are documented here.

## [Unreleased]

### Fixed

- **Thunderstorm risk sensor unit (#113):** `sensor.ws_thunderstorm_risk` returns a 0-100 index but declared no unit, so Home Assistant could not render it as a percentage or build long-term statistics. It now reports `%`. Thanks @Benjamin45590.

## [2.5.2] - 2026-06-25

### Fixed

- **French translation metadata:** Updated `fr.json` from PR #108 and repaired JSON syntax so Home Assistant can load the French translation bundle.

## [2.5.1] - 2026-06-24

### Fixed

- **Compatibility with HA 2024.6 - 2024.12:** `sensor.py` referenced `SensorDeviceClass.WIND_DIRECTION` and `SensorStateClass.MEASUREMENT_ANGLE` (added in HA 2025.1) unconditionally, while the declared minimum is HA 2024.6.0. On those older cores the sensor platform failed to load with `AttributeError`. Both are now resolved defensively, so older cores fall back to a plain numeric `°` wind-direction sensor instead of crashing.

### Internal

- Added `tests/test_sensor_platform.py` (imports the sensor module so HA-version incompatibilities are caught by CI) and `tests/test_migration.py` (covers the v2 -> v3 hemisphere/climate-region slug migration).

## [2.5.0] - 2026-06-23

### Added

- **Frost Risk sensor (issue #105):** `frost_risk` was computed internally but never exposed. It is now a proper sensor (high / probable / unlikely / no risk) with EN/FR translations.
- **Localized conditions summary & alerts (issue #104):** The `conditions_summary` and `alert_message` sensor states are now localized to the Home Assistant language (English and French, with English fallback) instead of always being English.

### Changed

- **Translatable Hemisphere / Climate region selectors (issue #104):** The hemisphere and climate-region option values are now lowercase slugs (e.g. `Atlantic Europe` -> `atlantic_europe`) so the dropdowns can be translated. Existing config entries are migrated automatically (config schema v2 -> v3). French labels added.
- **Translated Air Quality / Pollen step descriptions (issue #104):** These config and options-flow steps no longer carry hardcoded English text; descriptions are now in the translation files (EN/FR).
- **Friendlier Forecast Provider state (issue #104):** The `forecast_provider` sensor now shows human-readable provider names (e.g. "Home Assistant weather entity" instead of `ha_weather_entity`).

### Fixed

- **Nonexistent MDI icons (issue #105):** `WS Forecast Daily`, `WS Forecast Tiles`, and `WS Indoor Humidity` used MDI icons that do not exist and rendered blank. Replaced with `mdi:api`, `mdi:weather-partly-cloudy`, and `mdi:water-percent`.

### Notes

- Unit-selector labels (`°C`/`m/s`/`hPa` etc.) remain in English for now; translating them needs a separate option-value migration and is tracked for a later release.

## [2.4.1] - 2026-06-23

### Fixed

- **Lightning source validation (issue #88):** The config and options flows no longer reject lightning distance/azimuth/count sensors as "entity not found" when they sit at `unknown`/`unavailable`. These sensors are normally idle outside of an active strike, so the validator now tolerates an unknown state for them while still requiring the entity to exist.

## [2.4.0] - 2026-06-21

### 🚀 Major Adoption & UX Update (The "Launch" Release)

This release drastically simplifies the setup process and cleans up the Home Assistant UI, preparing the integration for the default HACS store.

### Added

- **Auto-Discovery:** The Config Flow now actively scans your Home Assistant instance for Ecowitt, WeatherFlow, and Ambient Weather integrations. If found, it automatically fills in all 7 required sensor mappings for a "one-click" setup experience.
- **Onboarding Dashboards:** The success screen of the configuration flow now directly links to the recommended UI dashboards and automation blueprints.
- **New Blueprints:** Added native `heat_stress` (UTCI) and `poor_aqi` blueprints. All blueprints now include `source_url` for seamless 1-click importing via the HA UI.
- **Hardware Mapping Guide:** Added a comprehensive [Hardware Mapping Guide](docs/hardware_mapping.md) for users with manual setups.

### Changed

- **Taming Entity Vomit:** Over 30 "advanced" niche sensors (like ET0, FWI sub-components, and Frost Point) are now disabled by default for new installations to prevent dashboard clutter. You can easily re-enable them in the Entities UI.
- **Diagnostic Categories:** 10+ debugging and internal state entities (e.g., Climatology Stats, Package OK) have been moved to the Home Assistant `DIAGNOSTIC` category, hiding them from auto-generated Lovelace dashboards.
- **README & Science Docs:** Completely rewrote the `README.md` to focus on practical automations and outcomes. Moved the dense meteorological formulas into a dedicated `docs/science.md` file.

### Fixed

- **Windows Compatibility:** Resolved a massive test suite failure (`pytest-socket` breaking the `ProactorEventLoop`) that prevented Windows developers from running the tests locally. The suite is now 100% green.

## [2.3.0] - 2026-06-19

### Added

- **Descriptive Frost Risk diagnostic sensor (#90).** A new optional `sensor.ws_frost_risk` provides a categorized text state (`no_risk`, `unlikely`, `probable`, `high`) based on the current and forecasted daily minimum temperatures.

### Fixed

- **Vigicrues Entity Naming & Localization (#89).** Vigicrues sensors (`ws_river_level` and `ws_river_flow`) no longer have hardcoded English prefixes ("WS River Level — ") and now use Home Assistant's native translation system with dynamic placeholders for the station/river name, supporting full localization (e.g. French "Hauteur d'eau").
- **Translation Placeholder Mismatch in French (#91).** Corrected a schema error in `fr.json` for the `forecast_api_failures` error message where `{provider}` was missing, causing a formatting exception.
- **Config Flow Discoverability Hassfest Error.** The config flow now correctly sets an `async_set_unique_id` to comply with Home Assistant architectural requirements for discoverable configurations containing MQTT dependencies.

## [2.2.0] - 2026-06-18

### Added

- **Per-measurement unit selection (#84).** The "Display units" step in the setup wizard and the Configure dialog now expose individual unit selectors for every measurement type, in addition to the existing overall units preset:
  - **Wind speed** - m/s, km/h, mph, kn (knots)
  - **Pressure** - hPa, inHg, mmHg
  - **Rainfall** - mm, in
  - **Distance** (lightning distance) - km, mi
  - **Altitude** (cloud base, freezing level) - m, ft
  - All new selectors default to `auto`, which follows your Home Assistant unit system - fully backward-compatible with existing installs.
  - Individual selections take precedence over the overall units preset. Alert thresholds in the alerts step display in the configured unit.
  - Sensors that restore their last known value (ET0, rain accumulators, max gust, max rain rate) automatically discard stale restored values when the unit preference changes between restarts, preventing display corruption.

## [2.1.3] - 2026-06-16

### Fixed

- **CWOP skipped in options flow (Configure) when combined with other uploaders (#83).** The previous fix (v2.1.2) corrected the initial setup wizard but missed the options flow (Configure button), which has a separate set of step handlers. All five options flow upload handlers (`weathercloud_opt`, `pwsweather_opt`, `wow_opt`, `awekas_opt`, `owm_stations_opt`) had the same incomplete chain and now correctly route to CWOP before MQTT/save.

## [2.1.2] - 2026-06-16

### Fixed

- **CWOP skipped in options flow when combined with other uploaders (#83).** The upload-service step chain was incomplete in four handlers (`pwsweather`, `wow`, `awekas`, `owm_stations`): each jumped straight to MQTT/alerts after its own step, bypassing all later steps (OWM Stations, Windy, CWOP). Enabling PWSWeather + CWOP simultaneously left CWOP unconfigured and silently disabled. The chain now walks all remaining steps in the correct order.
- **Blitzortung auto-discovery misses some installs (#75).** Discovery now also matches by `sensor.blitzortung_*` entity_id prefix, covering forks or installs where the integration platform name differs. The lightning counter pattern now also checks for `"count"` in the entity_id (previously only `"counter"` was checked there).

### Changed

- **French translations (PR #81).** Added translations for soil sensors, `conditions_summary`, `forecast_brier_*`, `nowcast_confidence`, 90-day anomaly sensors, and various terminology improvements contributed by Benjamin45590. Corrected two strings that were accidentally left in English.

## [2.1.0] - 2026-06-13

### Added

- **Nowcast local blending.** The precipitation nowcast now blends live local gauge data into the first two 15-minute NWP buckets (70% local / 30% NWP for t+0–15 min; 50/50 at t+15–30 min) when the local rain rate sensor confirms active precipitation. A new diagnostic sensor `sensor.ws_nowcast_confidence` (`high` / `medium` / `low`) reflects how well the local gauge and NWP grid agree. Sensor is gated behind the Precipitation Nowcast feature toggle.

- **Soil sensor support.** New optional feature group (disabled by default) that reads soil moisture (volumetric %, auto-normalised from 0–1 or 0–100 formats) and soil temperature sensors. Derives:
  - `sensor.ws_soil_moisture` — volumetric soil moisture %
  - `sensor.ws_soil_temperature` — soil temperature °C
  - `sensor.ws_soil_moisture_deficit` — field-capacity deficit (40% FC minus current)
  - `sensor.ws_irrigation_need` — text label: None / Low / Moderate / High / Critical
  - `sensor.ws_irrigation_need_score` — 0–100 numeric irrigation demand score based on soil deficit and net ET₀ demand
  Enable in Configure → Features → Soil sensors.

- **Seasonal anomaly sensors (90-day climatology).** The rolling climatology buffer has been extended from 30 to 90 days. Two new diagnostic sensors compare the most recent 30-day period against the 90-day seasonal baseline:
  - `sensor.ws_temp_anomaly_90d` — temperature anomaly (°C above/below the 90-day mean)
  - `sensor.ws_rain_anomaly_90d` — precipitation anomaly (mm/d above/below the 90-day mean)
  Both sensors activate after 60 days of data and are gated behind the Diagnostics feature toggle.

- **Individual forecast skill sensors.** Three new diagnostic entities expose the per-source Brier score and learned blend weight that the self-learning rain probability system maintains internally:
  - `sensor.ws_forecast_brier_local` — Brier score for the local sensor model (lower is better)
  - `sensor.ws_forecast_brier_api` — Brier score for the NWP API model
  - `sensor.ws_forecast_blend_weight_local` — current learned weight of the local model (%)
  All three are gated behind the Diagnostics feature toggle and require ≥10 verified forecast outcomes.

- **Alert hysteresis / debounce.** Wind, rain, and freeze alert states now require a condition to be sustained for 2 consecutive update ticks before activating, and must be absent for 3 ticks before clearing. Eliminates chatty automations caused by sensor noise around threshold boundaries. Configurable via `ALERT_DEBOUNCE_ON_TICKS` and `ALERT_DEBOUNCE_OFF_TICKS` in `const.py`.

- **Current conditions text summary.** New always-on sensor `sensor.ws_conditions_summary` provides a human-readable description of current conditions (e.g. "Warm · 68% RH · Light rain · SE 12 km/h"). Useful for notification templates, TTS announcements, and Assist voice responses. Attributes include temperature, feels-like, humidity, rain rate, wind, and condition label.

- **HA Repairs issues for sensor faults.** Two new issue types appear in Settings → Repairs when sensor hardware problems are detected:
  - `stuck_sensors` — fires when one or more sensors report an unchanged value for an extended period (typical of frozen/failed sensor hardware)
  - `sensor_drift_detected` — fires when a sensor's value diverges from its historical pattern beyond expected bounds (e.g. mounting shift, electronics degradation)
  Both issues are cleared automatically when the sensor recovers or when Suppress Notifications is enabled.

- **Five automation blueprints.** Import-ready blueprints in `blueprints/automation/ws_core/`:
  - `heat_alert.yaml` — notifies when feels-like exceeds a threshold for ≥5 minutes
  - `freeze_alert.yaml` — notifies when temperature drops to or below a freeze threshold; optionally shuts off an irrigation switch
  - `rain_start.yaml` — triggers on rain start and/or stop; configurable rain rate threshold, optional actions for each event
  - `high_wind.yaml` — notifies on gust exceedances; optionally retracts covers/awnings
  - `poor_aqi.yaml` — notifies when AQI exceeds threshold for ≥10 minutes; optionally closes windows and activates air purifiers

- **Calibration service range validation.** The `ws_core.apply_calibration` service now enforces the same bounds used by the UI number entities via voluptuous `Range()` validators (temp ±10 °C, humidity ±20%, pressure ±10 hPa, wind ±5 m/s). A HA Repairs advisory (`large_calibration_offset`) fires when any applied offset exceeds 50% of its maximum, suggesting possible sensor hardware failure rather than calibration drift.

- **`WsData` typed coordinator model.** A new `models.py` module introduces `WsData(dict)` — a `dict` subclass with typed annotations for all ~140 coordinator data fields. IDE tools now provide autocomplete and type hints for all sensor data keys with zero breaking changes to existing code.

- **Voice/Assist optimisation.** The `weather.*` entity now sets `native_precipitation_unit = mm` and `suggested_display_precision = 1` for cleaner display in the frontend and Assist responses. The `attribution` property now always returns a non-null string.

### Changed

- **Climatology buffer extended from 30 to 90 days.** The rolling climatology window (`CLIMATOLOGY_WINDOW`) has been increased from 30 to 90 days. The existing 30-day anomaly sensors (`sensor.ws_temp_anomaly_30d`, `sensor.ws_rain_anomaly_30d`) are unaffected and continue to use the most recent 30 days; they now have a richer baseline to compare against.

- **`suggested_display_precision = 1` added to temperature and precipitation sensors.** All temperature sensors (dew point, feels-like, wet-bulb, frost point, 24h high/low/average) and precipitation sensors (rain rate, 1h/24h/today/week/month/year accumulators) now declare 1 decimal place as the preferred display precision for the HA frontend statistics graphs.

### Fixed

- **Calibration service accepted out-of-range offsets.** Offsets larger than the sensor's expected calibration range (e.g. `cal_temp_c: 100`) were silently written to the config entry options, corrupting all derived sensors. Voluptuous range validation now rejects these before writing.

## [2.0.8] - 2026-06-13

### Fixed

- **#77**: Binary sensor translations were ignored for all eight diagnostic problem sensors (`temperature_stuck`, `humidity_stuck`, `pressure_stuck`, etc.) — the entity set a hardcoded English `_attr_name` and never set `_attr_translation_key`, so HA always displayed English regardless of system language. All problem sensors now use `_attr_translation_key` and respect every supported locale.
- **#75**: Lightning nearest distance showed "Entity not found" when using Blitzortung as the source — the auto-discovery ran once at coordinator `__init__` time, before Blitzortung had registered its entities. Discovery now retries on every update tick until both count and distance sources are found.
- **#74** (thanks @miczu71): All 15 periodic upload and fetch schedulers (Weather Underground, Weathercloud, PWSWeather, WOW, AWEKAS, OpenWeatherMap Stations, Windy, CWOP, MQTT, AQI, Solar forecast, Météo Vigilance, Vigicrues, Precipitation nowcast, Spatial neighbor QC) were silently failing on HA 2025+ — `async_track_time_interval` fires from a thread outside the event loop, making `hass.async_create_task()` raise `RuntimeError`. Replaced all 15 with `asyncio.sleep` loops running inside `hass.async_create_background_task`.

## [2.0.7] - 2026-06-11

### Fixed

- **#70**: "Unknown error occurred" when editing source sensors via Configure — the options flow called `_validate_numeric_sensor`, which only existed on the config-flow class, raising `AttributeError`. The sensor validator is now a shared module-level helper used by both flows.
- **#71**: "Entity is neither a valid entity ID nor a valid UUID" blocking the whole options dialog — the inline HA weather-entity field carried an empty-string default that fails the weather `EntitySelector`. It now uses a suggested value and is simply omitted when left blank.
- **#72** (thanks @miczu71): Weather Underground credentials could never be saved (and so no uploads were ever sent) because the validator checked the read API (`api.weather.com`), which needs a separate 32-character read key. It now validates the **station key (password)** against the same PWS upload endpoint the uploader actually uses. The Weather Underground field is relabelled "Station key (password)" to match `wunderground.com/member/devices`.

## [2.0.6] - 2026-06-11

### Added

- **#68**: `Home Assistant weather entity` forecast provider — use any existing `weather.*` entity already set up in Home Assistant as the forecast source. No external API calls or keys needed; select it in Configure → Forecast and pick a weather entity from the picker. Uses the `weather.get_forecasts` service (HA 2024.2+) with fallback to the `forecast` attribute on older installations.
- **#63**: Multi-room indoor temperature delta sensors — configure any number of indoor temperature sensors (one per room) in Configure → Indoor. A dedicated `sensor.ws_indoor_room_delta_<room>` diagnostic entity is created for each room, reporting the temperature difference from outdoor and the room's temperature as an attribute.

### Fixed

- **#62**: Blitzortung lightning auto-fallback — when no physical lightning sensor is manually mapped, the coordinator now auto-discovers Blitzortung integration entities at startup and uses them as a fallback. If Blitzortung is installed, no manual mapping is needed.
- Synced `strings.json` with `translations/en.json` (forecast provider description had diverged after the v2.0.5 update).

## [2.0.5] - 2026-06-10

### Fixed

- **#58**: Missing MDI icons on several sensors — all `WSSensorDescription` entries now include an explicit `icon` field.
- **#59**: Dew point and frost point were returning identical values at sub-zero temperatures — frost point now correctly applies Buck (1981) ice-phase saturation constants below 0 °C.
- **#60**: Decimal precision standardised to 2 places across all derived sensors.
- **#56**: Options flow UI simplified — condensed multi-step settings and improved back-navigation flow.

## [2.0.4] - 2026-06-10

### Added

- Dedicated `sensor.ws_forecast_provider` diagnostic entity showing the active forecast provider.
- Configure-flow source remapping for required and optional weather station source sensors.

### Fixed

- Forecast failure Repairs text now names the active forecast provider instead of always saying Open-Meteo.
- `sensor.ws_wu_upload_status` is only created when Weather Underground upload is enabled.
- Clarified the purpose of `switch.ws_enable_animations` and `switch.ws_enable_display_sensors` in entity attributes and documentation.

## [2.0.2] - 2026-06-09

### Fixed

- **French translation (fr.json):** overhauled and expanded by @Benjamin45590 (PR #51),
  with the following corrections applied before merge:
  - NWS/NOAA description was accidentally left in English — restored to French
  - Typo in `leaf_wetness` sensor name (`feuillag` → `feuillage`)
  - Key mismatch: `enable_thunderstorm_risk` → `enable_thunderstorm` in config
    flow `data_description` (aligns with the renamed field)
  - `ws_suppress_notifications` switch label was inverted — now reads
    "Bloquer les notifications HA" (suppress = block)
  - `windy_status` sensor name corrected to "Statut Windy.com" (consistent with
    other upload-status sensors)

## [2.0.1] - 2026-06-08

### Fixed

- Minor version and metadata housekeeping following the 2.0.0 release.

## [2.0.0] - 2026-06-04

The largest release to date — a comprehensive expansion aimed at making
Weather Station Core the most complete personal-weather-station integration
for Home Assistant. All new features are opt-in via feature toggles, so
existing setups are unaffected until you enable them.

### New derived sensors

- **Atmospheric:** cloud base (LCL), freezing level, air density, specific
  humidity, wind gust factor.
- **Human comfort:** WBGT (indoor + solar-corrected outdoor) and **UTCI**
  (Universal Thermal Climate Index, full Bröde 2012 polynomial) — neither
  previously available in any HA weather integration.
- **Fire danger:** McArthur **FFDI** (Australian standard) and Fosberg
  **FFWI** (US/global), alongside the existing Canadian FWI.
- **Agrometeorological:** Heating / Cooling / Growing Degree Days (HDD/CDD/GDD)
  with configurable base temperatures, leaf wetness, irrigation water deficit.
- **Solar/energy:** daily solar irradiation accumulation (Wh/m²), max
  theoretical clear-sky radiation, peak sun hours, net radiation (FAO-56).
- **Wind statistics:** dominant wind direction and direction variability
  (circular statistics), monthly wind run.
- **Rain accumulators:** this week / this month / this year, plus rolling
  24-hour max rain rate.

### Lightning detection (new opt-in group)

- Accepts cumulative strike count + nearest distance from WH57, AS3935,
  Blitzortung, or any compatible sensor.
- Sensors: strikes (1 h), distance, strike rate, clearance timer, and a
  proximity state with a configurable threshold (number entity).

### Indoor sensors (new opt-in group)

- Indoor temperature, humidity, and CO₂ inputs with indoor/outdoor deltas
  and a composite indoor comfort score.

### Data-quality expansion (diagnostics group)

- Stuck-sensor detection, σ-based temporal spike detection, spatial neighbour
  QC (vs Open-Meteo grid point), an overall 0–100 data-quality score, and
  eight per-sensor problem binary sensors.

### Network uploads — seven new targets

- Weathercloud, PWSWeather, WOW (UK Met Office), AWEKAS, CWOP (APRS),
  OpenWeatherMap Stations, and Windy.com — each independently configurable
  with its own status sensor.

### MQTT Discovery republishing

- Publishes 70+ derived sensors as MQTT Discovery payloads for Node-RED,
  external dashboards, or other HA instances. Uses the built-in MQTT
  integration; no extra dependency.

### Home Assistant platform features

- **Event entities** for rain onset/cessation, frost/thaw, and lightning
  strikes/proximity (HA 2023.8+).

### Translations

- Full translations added for **German, Dutch, Spanish, Italian, Portuguese,
  and Polish**, joining English and French — eight languages, all at full
  entity-name parity.

### Dashboards & automations

- Pre-built full Lovelace dashboard (6 views), a mobile-optimised single-column
  dashboard, gauge-card presets, and five automation blueprints (frost alert,
  storm alert, irrigation rain-skip, lightning safety, fire danger).

### Fixes

- Fixed module import order in `const.py` that could raise `NameError` on load.
- Replaced the deprecated `hass.helpers.aiohttp_client` accessor (removed in
  recent HA) with the modern `async_get_clientsession` throughout — fixes all
  network uploads/fetches on HA 2025+.

## [1.10.1] - 2026-06-01

### Improvements

- **Translated selector labels.** Units mode and forecast provider selectors in the config flow now use translation keys, so labels render in the user's language rather than hardcoded English.
- **French translation improvements (PR #43/#44).** Better step descriptions for Weather Underground, AQI, pollen, and solar forecast steps. Switch and number entity names cleaned up. River level and Vigilance Météo state attributes translated. Moon phase state labels added. Forecast provider and units mode options translated.

_All changes contributed by @Benjamin45590._

## [1.10.0] - 2026-05-30

### Bug Fixes

- **Fixed wrong sensor filtering in setup wizard (issue #41).** Atmospheric pressure and other sensors were appearing in incorrect source slots. The device-class filter on entity pickers has been removed — any numeric sensor now appears in any slot.

### Improvements

- **Localised state labels (issue #25).** AQI level, fog probability risk level, thunderstorm risk level, and moon phase now use translation keys so HA renders them in the user's language rather than hardcoded English strings.
- **Per-species pollen levels.** `grass_level`, `tree_level`, and `weed_level` keys added to the pollen sensor attributes alongside the existing overall level.
- **Streak sensor unit corrected.** Dry/heat/frost streak sensors no longer display a literal "d" unit label.
- **French translations.** State translations added for AQI, moon phase, fog, and thunderstorm risk. Hemisphere and climate region selector options also translated.

_All changes contributed by @Benjamin45590._

## [1.9.1] - 2026-05-29

### Bug Fixes

- **Battery voltage sensor accepted (issue #33).** Stations that report battery state as a voltage sensor (e.g. GW3000A reporting `device_class: voltage`) were rejected by the config flow validator. Voltage is now accepted alongside the standard `battery` device class for the battery source slot.

## [1.9.0] - 2026-05-28

### New Features

- **Vigicrues multi-station support (issue #27).** The config flow now includes a station picker that lists up to 20 hydrometric stations within 50 km (powered by Hub'Eau v2). Pin a specific gauge or keep the default auto-detect behaviour. Station name and river name are stored and shown as attributes on `sensor.ws_river_level`. The options flow also exposes the picker for post-install changes.

## [1.8.4] - 2026-05-27

### New Features

- **Suppress HA Repairs notifications (issue #20).** A new `switch.ws_suppress_notifications` entity (off by default, under Settings) lets you silence the three HA Repairs issues that ws_core can raise (missing source entities, stale sensors, forecast API failures). Turning the switch on immediately clears any open issues and prevents new ones from being created. Turning it back off restores normal behaviour on the next coordinator update cycle.

## [1.8.3] - 2026-05-27

### Bug Fixes

- **French translation improvements, part 2 (PR #18).** Applied the remaining terminology improvements contributed by Benjamin45590: river_level, rain_probability, rain_probability_combined, rain_display, rain_anomaly_30d, temperature_anomaly_30d, et0_daily, et0_hourly, solar_lux_factor, wind_quadrant, fire_risk_score attributes, ws_enable_vigicrues switch, and ws_pressure_trend_window number entity labels updated.

## [1.8.2] - 2026-05-27

### Bug Fixes

- **French translation improvements (PR #18).** Applied terminology improvements contributed by Benjamin45590: required-source labels now use proper meteorological terms (Anemometre, Girouette, Pluviometre); entity names for rain_rate, thw_index, thsw_index, pressure_change_window, chill_hours updated; several feature descriptions improved.

## [1.8.1] - 2026-05-27

### Improvements

- **Smarter entity picker for sensor mapping (issue #23).** The config flow now filters the entity picker to only show sensors with the correct `device_class` for each slot, making it much faster to find the right sensor on large installations.
  - Filtered slots: temperature, humidity, atmospheric pressure, rain total, illuminance, dew point, battery, solar radiation.
  - Wind fields (wind speed, wind gust, wind direction) are intentionally left unfiltered — many weather station integrations (Ecowitt, Froggit, etc.) pre-date `device_class` on wind sensors and would produce an empty picker.
  - UV index is also unfiltered — there is no standard HA `device_class` for UV index yet.
  - A new `wrong_sensor_type` validation error surfaces if an entity is manually entered whose `device_class` is explicitly set to something incompatible. Entities with no `device_class` are always accepted.

## [1.8.0] - 2026-05-26

### New Features

- **Vigicrues station picker.** When Vigicrues is enabled, a new config-flow step lists nearby hydrometric stations (via Hub'Eau v2) so you can pin a specific one instead of relying on auto-detect. The station name and river name are stored and shown as state attributes on `sensor.ws_river_level`. The options flow also exposes this picker so you can change the station post-install.
- **Fire danger from Meteo Vigilance.** A dedicated `sensor.ws_fire_danger_vigilance` entity mirrors the fire-hazard phenomenon from your local Vigilance colour (vert → rouge), independent of the composite `sensor.ws_vigilance_max_level`. State attributes include department, all active phenomena, and last-fetched timestamp.

## [1.7.1] - 2026-05-24

### Bug Fixes

- **Rolling-window stats and daily accumulators no longer reset on restart (issue #16).** The 24h temperature/gust/rain buffers and the `rain_today`, `wind_run`, and `chill_hours` accumulators were held in memory only, so they reset on every Home Assistant restart (and therefore every upgrade), and the brief value-restore was immediately overwritten by the reset value. This state is now persisted to storage and rehydrated on startup:
  - 24h windows (`temperature_high/low/avg_24h`, `wind_gust_max_24h`, `rain_last_1h/24h`) are saved and pruned to the trailing 24 hours on reload, so they continue instead of recomputing from scratch.
  - Daily accumulators (`rain_today`, `wind_run`, `chill_hours_today`) are restored only when their saved date is still the current day, so they continue the day rather than carrying a stale total into a new one. The seasonal chill total persists across days.
  - Saved on clean shutdown (covers normal restarts and upgrades) and on an hourly backstop (limits loss to one interval on a hard crash). New installs and missing/corrupt state start fresh, so the change is fully backward-compatible.

## [1.7.0] - 2026-05-22

### New Features

- **Precipitation nowcast** (opt-in, no API key). Adds short-term "is it about to rain" intelligence derived from Open-Meteo's 15-minute precipitation buckets. This is a dedicated fetch independent of your chosen forecast provider, so it works even if you use Met.no / NWS / OpenWeatherMap as your main provider. New entities (created when the **Precipitation Nowcast** feature is enabled):
  - `sensor.ws_minutes_until_rain` - minutes until rain is expected to start (unknown when no rain is in the window).
  - `sensor.ws_minutes_until_dry` - minutes until rain is expected to stop (when currently raining).
  - `sensor.ws_rain_next_60min` - total precipitation expected in the next hour (mm).
  - `sensor.ws_nowcast_intensity` - none / light / moderate / heavy, from the peak rate in the next hour.
  - `binary_sensor.ws_rain_expected_1h` - on when measurable rain is expected within 60 minutes (handy for automations).
  - Enable via the **Precipitation Nowcast** switch or Configure -> Features. Refreshes every 15 minutes. A conditional "Rain Nowcast" dashboard tile is included.

## [1.6.6] - 2026-05-22

### Bug Fixes

- **Dry streak (`sensor.ws_dry_streak`) no longer ignores rain and no longer over-counts (issue #15).** Two bugs were corrected:
  - The streak was evaluated right after midnight against the *current* day's rain total - which had just reset to 0 - so a completed rainy day was never seen and the streak kept climbing (e.g. 12 mm fell but the streak still rose to 25). Streaks are now evaluated for the **completed** calendar day, using that day's final rain total snapshotted at the midnight rollover. A day with ≥ 1 mm now correctly resets the streak to 0.
  - The "once per day" guard was held in memory and reset on every Home Assistant restart or integration reload, so the streak could increment multiple times in a single day. The guard is now persisted in the learning state (`streak_last_counted_date`), so each calendar day is counted exactly once regardless of restarts.
- Added unit tests covering rain-resets-streak, dry-day-increments-by-one, and restart-does-not-double-count.

## [1.6.5] - 2026-05-22

### Dashboard

- **Fixed Station Health and Data Quality badges showing the right text but the wrong (red) color.** The `station_health` and `data_quality` sensors emit lowercase raw states ("online", "ok", "degraded", "stale") which Home Assistant translates to "Online"/"OK" for display. The dashboard's `custom:button-card` JavaScript reads the *raw* state and was comparing against the capitalized display text (`=== 'Online'`, `=== 'OK'`), so the comparisons always failed and the color fell through to red - while CSS `text-transform:uppercase` still rendered "ONLINE"/"OK", making the text look correct. Comparisons are now case-insensitive on both the Advanced top-bar health tile and the main-page header, and the `stale` health state is now handled (orange). Same root cause as the earlier Zambretti underscore fix.

## [1.6.4] - 2026-05-22

### Dashboard

- **Fixed the Air Quality tile showing no category label.** The tile read the AQI sensor's *state* (the numeric value, e.g. 58) and displayed it as the "level", so the category word never appeared. It now reads the category from the sensor's `level` attribute (e.g. "Moderate"), falls back to computing the US EPA category from the AQI number if the attribute is missing, and renders it as a colored badge consistent with the other tiles.

## [1.6.3] - 2026-05-22

### Dashboard

- **Color-coded good/bad badges on the basic metric tiles.** The specialized tiles (AQI, UV, pollen, comfort indices, hazards) already showed a colored category label, but the plain measurement tiles displayed bare numbers. Added at-a-glance qualitative badges:
  - **Temperature Detail** - comfort band (Freezing -> Cold -> Cool -> Comfortable -> Warm -> Hot -> Very hot)
  - **Temperature Extended** - dew-point comfort band (Dry -> Pleasant -> Comfortable -> Sticky -> Humid -> Very humid -> Oppressive)
  - **Wind Detail** - strength band from Beaufort (Calm -> Light -> Fresh -> Strong -> Gale -> Storm)
  - **Pressure Detail** - pressure band (Low -> Slightly low -> Normal -> High)

> Dashboard is copy-paste (HACS does not deliver it). Re-paste `dashboards/weather_dashboard.yaml` via the Raw configuration editor to pick up the badges.

## [1.6.2] - 2026-05-22

### New Features

- **Three new opt-in feature toggles replace the old "disabled by default" mechanism.** Previously, a set of sensors were created in the entity registry in a *disabled* state, meaning they were inert and had to be manually enabled one by one - and nothing ever enabled them automatically. They are now gated by proper feature switches: off = the entity is never created (no clutter, no recorder cost); on = the entity is created and works immediately.
  - **Station Diagnostics** (`switch.ws_enable_diagnostics`) - gates Sensor Drift, Sensor Consistency, Sensor Quality Flags, Forecast Skill, Forecast Agreement, Solar Lux Factor, and 30-day Climatology.
  - **FWI Components** (`switch.ws_enable_fwi_components`) - gates the 5 Canadian FWI intermediate codes (FFMC, DMC, DC, ISI, BUI). Requires **Fire Risk** enabled to produce data; the composite FWI and Daily Severity Rating remain tied to Fire Risk.
  - **Advanced Sensors** (`switch.ws_enable_advanced_sensors`) - gates Zambretti Number (numeric form of the text forecast), hourly ET₀, and smoothed wind direction.
- All three default to **off** (opt-in), consistent with every other optional feature. Enable via Configure -> Features or the switches on the device page.

### Changes

- **Removed `_DISABLED_BY_DEFAULT`** from `sensor.py` entirely. Temperature Display, which was double-gated (behind the Display Sensors toggle *and* disabled-by-default), now works correctly as soon as Display Sensors is enabled.
- New constants in `const.py`: `CONF_ENABLE_DIAGNOSTICS`, `CONF_ENABLE_FWI_COMPONENTS`, `CONF_ENABLE_ADVANCED_SENSORS` and their `DEFAULT_*` counterparts.

> **Existing installs:** the affected sensors were already disabled in your registry, so nothing was working before. After upgrading, enable the relevant feature toggle (Configure -> Features) to create the sensors fresh. Old disabled registry entries can be safely deleted.

## [1.6.1] - 2026-05-22

### Bug Fixes

- **Primary sub-sensors no longer disabled by default.** The following sensors were incorrectly placed in `_DISABLED_BY_DEFAULT`, meaning they were created in a disabled state in the entity registry even when their parent feature was enabled. They are now enabled by default and work immediately when the parent feature switch is turned on:
  - **AQI:** PM2.5, PM10
  - **Pollen:** Pollen Grass, Pollen Tree, Pollen Weed
  - **Moon:** Moon Illumination
  - **Solar Forecast:** Solar Forecast Tomorrow, ET₀ Penman-Monteith (Daily)
  - **Fire Risk:** Fire Weather Index (FWI composite), FWI Daily Severity Rating
- The 5 FWI intermediate components (FFMC, DMC, DC, ISI, BUI) remain disabled by default as they are calculation inputs rather than outputs.
- All diagnostic sensors (Sensor Drift, Sensor Consistency, Sensor Quality Flags, Forecast Skill, Forecast Agreement, Solar Lux Factor, Climatology 30-day, Zambretti Number, ET₀ Hourly, Temperature Display, Wind Direction Smoothed) remain disabled by default.

> **Existing installs:** already-disabled entities in your registry will not be automatically re-enabled on upgrade. Go to Settings -> Devices & Services -> your weather station device, find the affected entities, and click Enable. New installs are unaffected.

## [1.6.0] - 2026-05-22

### New Features

- **Meteo Vigilance** (`sensor.ws_vigilance`) - Worst departmental alert colour from Meteo-France Vigilance (vert/jaune/orange/rouge). State attributes include a full breakdown by weather phenomenon (rain, wind, flood, snow, thunderstorm, fog, heat, cold, avalanche, waves). France only. No API key required. Opt-in via the **Meteo Vigilance** feature switch.
- **Vigicrues River Level** (`sensor.ws_river_level`) - Real-time water height (m) from the nearest gauging station to your configured location, via Hub'Eau v2 API. State attributes include station name, river name, station code, and observation timestamp. France only. No API key required. Opt-in via the **Vigicrues River Level** feature switch.
- **Feature: Meteo Vigilance** (`switch.ws_enable_vigilance_meteo`) - Enables Meteo Vigilance. Fetches every 30 minutes with a 45-second startup delay. Uses BAN reverse geocoding to detect your department automatically.
- **Feature: Vigicrues River Level** (`switch.ws_enable_vigicrues`) - Enables Vigicrues. Fetches every 15 minutes with a 60-second startup delay. Nearest station looked up once then cached.

### Changes

- Config flow and options flow updated with `enable_vigilance_meteo` and `enable_vigicrues` on the features step.
- New constants in `const.py`: `CONF_ENABLE_VIGILANCE_METEO`, `CONF_ENABLE_VIGICRUES`, `DEFAULT_ENABLE_VIGILANCE_METEO`, `DEFAULT_ENABLE_VIGICRUES`, `KEY_VIGILANCE_MAX_LEVEL`, `KEY_RIVER_LEVEL_M`.
- French and English translations added for both new sensors and feature switches.

## [1.5.1] - 2026-05-22

### Bug Fixes

- **Comfort indices now opt-in** - `DEFAULT_ENABLE_COMFORT_INDICES` corrected from `True` to `False`, consistent with every other optional feature group (fog, thunderstorm, air quality, pollen, moon, solar forecast, sea temp). For existing installs, the `CONF_ENABLE_COMFORT_INDICES` key was absent from stored options, so the sensor filter's `False` fallback meant the 13 sensors were never created regardless of the README claim. Enable via the **Comfort Indices** switch on the device page, or via Configure -> Features.
- **Removed dead `entity_registry_enabled_default=False` lines** from all 13 comfort sensor descriptors. The field is not read by `WSSensorEntity.__init__` (only `_DISABLED_BY_DEFAULT` is checked), so these lines had no effect. Removed to eliminate confusion.

## [1.5.0] - 2026-05-21

### New Features

- **NWS Heat Index** (`sensor.ws_heat_index_c`) - Rothfusz regression, valid when T >= 27 C and RH >= 40 %. Returns `None` outside that envelope. Disabled by default; enable via the Comfort Indices feature switch.
- **WMO Wind Chill** (`sensor.ws_wind_chill_c`) - 2001 joint WMO/NWS formula, valid when T <= 10 C and wind > 1.34 m/s. Returns `None` otherwise.
- **Canadian Humidex** (`sensor.ws_humidex`) - Environment Canada formula using dew point. Returns `None` when humidex does not exceed ambient temperature.
- **Vapour Pressure Deficit** (`sensor.ws_vpd_kpa`) - Saturation minus actual vapour pressure in kPa. Essential for greenhouse control and irrigation scheduling.
- **Absolute Humidity** (`sensor.ws_absolute_humidity_gm3`) - Mass of water vapour per m³ of air (g/m³).
- **Delta-T** (`sensor.ws_delta_t_c`) - Dry-bulb minus wet-bulb temperature; the standard spray-application suitability index. State attribute `spray_suitability` classifies as `unsuitable_too_low` (< 2 C), `ideal` (2-8 C), or `unsuitable_too_high` (> 8 C).
- **Davis THW Index** (`sensor.ws_thw_index_c`) - Heat index with wind-cooling adjustment (Davis Instruments formula).
- **Davis THSW Index** (`sensor.ws_thsw_index_c`) - THW plus solar radiation heating effect; requires the optional solar radiation sensor.
- **Wind Run** (`sensor.ws_wind_run_km`) - Daily accumulated wind travel in km; resets at local midnight.
- **Chill Hours Today** (`sensor.ws_chill_hours_today`) - Hours spent at or below the configured base temperature today (default 7.2 C).
- **Chill Hours Season** (`sensor.ws_chill_hours_season`) - Season-to-date chill hour accumulation; season resets on the configured month/day (default July 1 for Northern Hemisphere).
- **Clearness Index Kt** (`sensor.ws_clearness_index_kt`) - Ratio of observed to theoretical clear-sky solar radiation; requires the optional solar radiation sensor. Returns `None` when sun elevation < 5 deg.
- **Cloud Cover %** (`sensor.ws_cloud_cover_pct`) - Approximate cloud cover percentage derived from the clearness index.
- **Feature: Comfort Indices** - New feature switch that gates all 13 sensors above. Default: **off** (opt-in). Enable via the Comfort Indices switch on the device page, or via Configure -> Features.

### Changes

- **Config flow** updated with `enable_comfort_indices` option on the features step.
- New constants in `const.py`: `CONF_ENABLE_COMFORT_INDICES`, `CONF_CHILL_HOUR_BASE_C`, `CONF_CHILL_SEASON_RESET_MONTH`, `CONF_CHILL_SEASON_RESET_DAY` and their `DEFAULT_*` counterparts; 13 new `KEY_*` data constants.
- French translations added for all 13 new sensors and the new feature switch.

## [1.4.2] - 2026-05-21

### Bug Fixes

- **Weather Underground `softwaretype` was stale** - hardcoded to `"ws_core_0.6.0"` since the initial release. Now reads the version dynamically from `manifest.json` at startup, so WU upload reports the correct software version automatically on every release.

### Cleanup

- **Extracted forecast agreement thresholds to constants** - `FORECAST_AGREEMENT_ALIGNED_PP = 20` and `FORECAST_AGREEMENT_CONFLICT_PP = 40` defined in `const.py`; the `_compute_forecast_agreement` logic now references these instead of bare integers.
- **Extracted drift detection thresholds to constants** - `DRIFT_SLOPE_TEMP_C_H`, `DRIFT_SLOPE_HUMIDITY_PCT_H`, `DRIFT_SLOPE_PRESSURE_HPA_H`, `DRIFT_R_SQ_THRESH`, `DRIFT_STUCK_BUCKET_SAMPLES`, `DRIFT_STUCK_BUCKET_MIN_RATE`, `DRIFT_STUCK_RATE_RANGE_MAX` added to `const.py`; `_compute_drift_detection` uses them throughout.
- **Alert threshold lookups now use `CONF_*` / `DEFAULT_*` constants** - three `.entry_options.get("thresh_...", <hardcoded>)` calls replaced with their proper `const.py` symbols (`CONF_THRESH_WIND_GUST_MS`, `CONF_THRESH_RAIN_RATE_MMPH`, `CONF_THRESH_FREEZE_C` and their `DEFAULT_*` counterparts).
- **Coordinator header version updated** - docstring still referenced `v0.3.0`.

## [1.4.1] - 2026-05-21

### Bug Fixes

- **Patch release to fix v1.4.0 release artifact** - the v1.4.0 GitHub release zip was published before CI fixes were committed, causing `translations/en.json` to contain a trailing comma that prevented the integration from loading. No code changes beyond the version bump; the fix was already on `main`.

## [1.4.0] - 2026-05-21

### New Features

- **`apply_calibration` service action** - write sensor calibration offsets directly from an automation or the Developer Tools UI without opening the config flow. Supports `cal_temp_c`, `cal_humidity`, `cal_pressure_hpa`, `cal_wind_ms`; reloads the entry immediately. Documented in `services.yaml` with full field selectors.
- **`temperature_anomaly_30d` and `rain_anomaly_30d` now unit-aware** - added `device_class=TEMPERATURE` and `device_class=PRECIPITATION` respectively so HA auto-converts values to °F / inches for imperial users, just like every other sensor.

### Bug Fixes

- **`wu_status` now translatable** - replaced dynamic strings like `"OK 14:32"` and `"Error HTTP 403: ..."` with enum state keys (`disabled`, `ok`, `error_http`, `error_network`, `error`). Last successful upload timestamp moved to the `last_upload` state attribute. State translations added in English and French.

### Cleanup

- **Removed dead `laundry_reminder.yaml` blueprint** - `sensor.ws_laundry_drying_score` was removed in v0.3.0; this blueprint has been broken for years. `blueprints/README.md` updated accordingly.
- **Removed dead config constants** - `CONF_ENABLE_LAUNDRY`, `CONF_ENABLE_STARGAZING`, `CONF_ENABLE_RUNNING`, `CONF_ENABLE_METAR`, `CONF_METAR_*`, `CONF_ENABLE_CWOP`, `CONF_CWOP_*`, `CONF_ENABLE_EXPORT`, `CONF_EXPORT_*`, `CONF_ENABLE_DEGREE_DAYS`, `CONF_DEGREE_DAY_BASE_C`, `CONF_ENABLE_ACTIVITY_SCORES`, `CONF_ENABLE_EXTENDED_SENSORS` and their corresponding defaults removed from `const.py`. All are already listed in `DEPRECATED_CONF_KEYS_V030` for migration.
- **Removed dead `rain_penalty` config fields** - `rain_penalty_light_mmph` and `rain_penalty_heavy_mmph` were config flow fields for the removed laundry/activity score feature. Removed from `config_flow.py`, `strings.json`, `en.json`, `fr.json`, and `number.py` comment.
- **Removed empty tracked files** - `git` and `ruff` (zero-byte files accidentally committed) removed from the repo.
- **Added `.ruff_cache/` to `.gitignore`** - the ruff cache directory was not gitignored.
- **Dashboard version headers updated** - `weather_dashboard.yaml` and `weather_dashboard_vanilla.yaml` were still labelled `v1.0.0`.
- **Entity map regenerated** - `docs/entity_map.html` was showing `WS Core 1.1.0`; regenerated at v1.4.0 (84 sensors, 11 switches).

## [1.3.2] - 2026-05-19

### Bug Fixes

- **Rain display state now translatable** - `sensor.ws_rain_display` was returning dynamic strings like `"Heavy (3.5 mm/h)"` which can't be used as translation keys. Fixed to return snake_case intensity keys (`dry`, `drizzle`, `light`, `moderate`, `heavy`) with the numeric rate already available in the `rain_rate` attribute. State translations added to all three translation files (closes #8). Reported by @Benjamin45590.

### Improvements

- **French translation polish** - 12 wording improvements contributed by @Benjamin45590: clearer descriptions for the location step, forecast step, and features options; improved Zambretti state labels (`"averses en début de journée"`, `"instable, éclaircies à venir"`, etc.); `"Pluie du jour"` instead of `"Pluie aujourd'hui"`; fog and thunderstorm risk labels shortened; pollen `"none"` changed from `"Nul"` to `"Aucun"`. PR #11.

## [1.3.1] - 2026-05-18

### Improvements

- **Sensor state translations** - all string-state sensors now have translatable values. 11 sensors covered: current condition (29 weather states), Zambretti forecast (25 phrases), pressure trend, alert state, station health, humidity level, UV level, pollen level, forecast agreement, sensor drift, sensor consistency. French translations included throughout.

## [1.3.0] - 2026-05-18

### New Features

- **Météo France forecast provider** - adds Météo France via the Météo Concept API as a 6th provider option. Free tier available, API key required (get one at api.meteo-concept.com). Full daily (7-day) and hourly (24-hour) support with correct WMO weathercode mapping. Contributed by @Benjamin45590.

## [1.2.3] - 2026-05-18

### Bug Fixes

- **Switch, number, select, and binary sensor names now translatable** - all non-sensor entity types (feature toggles, config numbers, graph range select, package OK binary sensor) were still using hardcoded English names. Wired up `has_entity_name = True` and `translation_key` on all four entity classes so names render in the user's language. French translations included (closes #8).

## [1.2.2] - 2026-05-18

### Improvements

- **French translation polish** - 16 copy improvements from native speaker @Benjamin45590: correct term for illuminance (`Éclairement`), missing grammatical articles added, more natural phrasing throughout (`Il pleut`, `Paquet OK`, `Température de surface de la mer`, etc.).

## [1.2.1] - 2026-05-18

### Bug Fixes

- **Entity attribute labels now translatable** - removed hardcoded English metadata strings (`method`, `reference`, `disclaimer`, etc.) from entity attributes; these were developer-documentation noise that couldn't be localised. All remaining attribute keys (`wind_contribution_ms`, `z_number`, `danger_level`, etc.) now have `state_attributes` translations in `strings.json`, `en.json`, and `fr.json`, so the labels render in the user's language in the HA UI (closes #6, thanks @Benjamin45590).
- **README updated** - added Forecast Provider section, corrected sensor count, added missing sensors (`ws_rain_today`, `ws_no2`, `ws_ozone`, `ws_forecast_agreement`), and documented the provider contribution path.

## [1.2.0] - 2026-05-18

### New Features

- **Pluggable forecast provider** - `sensor.ws_forecast_daily` and all NWP-derived sensors now use a swappable provider. Select in the config/options flow. Ships with two built-in providers: **Open-Meteo** (default, free, no API key) and **Met.no** (Norwegian Meteorological Institute, free, no API key, strong European coverage). Adding new providers requires only a new Python file + one-line registry entry.
- **Nowcast correction (0-3 h) - now actually implemented** - local station readings blend into the first three hourly forecast slots with tapering weights (70 % local at h+0, 40 % at h+1, 10 % at h+2, pure NWP from h+3). Blended fields: temperature, humidity, wind speed, dew point.
- **NO₂ and Ozone sensors** - `sensor.ws_no2` and `sensor.ws_ozone` expose the nitrogen dioxide and ozone values already fetched by the AQI module as standalone sensors (µg/m³, disabled by the Air Quality toggle, diagnostic category).
- **Rain Today sensor** - `sensor.ws_rain_today` exposes today's accumulated rainfall (resets at local midnight), separate from the 24 h rolling window.

## [1.1.1] - 2026-05-18

### Bug Fixes

- **All 82 sensor names now translatable** - sensors now use HA's `translation_key` + `has_entity_name` mechanism. Display names update automatically when HA language is changed (e.g. French users see "Température" instead of "WS Temperature"). Entity IDs are unchanged. French translations included out of the box (closes #4, thanks @Benjamin45590).

## [1.1.0] - 2026-05-18

### New Features

- **Full Canadian FWI system** - complete Van Wagner (1987) implementation: FFMC, DMC, DC daily moisture codes with persistent carry-over across HA restarts, ISI, BUI, FWI, DSR. Replaces the previous simplified heuristic. `sensor.ws_fire_risk_score` maps real FWI to a 1-10 danger scale; seven sub-index sensors available (disabled by default).
- **Nowcast correction (0-3h)** - local station readings (temperature, humidity, wind, dew point, rain rate, condition) blend into the first three hourly forecast slots using tapering weights (70 % local at hour 0, pure NWP by hour 3).
- **Adaptive rain probability** - `sensor.ws_rain_probability_combined` uses rolling 90-day Brier-score weights that learn which source (local sensors vs Open-Meteo) has been more accurate; falls back to fixed day/night weights until enough data accumulates.
- **Forecast agreement sensor** - `sensor.ws_forecast_agreement` compares Zambretti Z-number implied rain likelihood to Open-Meteo `precip_prob`; states: `aligned` (< 20 pp delta), `diverging` (20-40 pp), `conflict` (> 40 pp).
- **French translation** - complete `fr.json` covering config flow, options flow, entity names, and issues (thanks @Benjamin45590).

### Bug Fixes

- **Configure button 500 error on HA 2024.3+** - `async_get_options_flow` updated to `@classmethod` + `@callback`; framework now injects `self.config_entry` automatically (thanks @miczu71, PR #2).
- **AQI level attribute always `None`** - `KEY_AQI_LEVEL` was never written to the coordinator data dict; now populated from cached AQI data.
- **Moon phase attribute always `None`** - moon phase was stored under private key `_moon_phase` but sensor read `KEY_MOON_PHASE`; keys aligned.
- **Staleness timeout selector rejected default** - selector max was 3 600 s but default is 7 200 s; raised to 86 400 s (24 h).
- **`enable_fog` shown as raw key in config flow** - translation key was `enable_fog_probability`; aligned to `enable_fog` to match the const.
- **10 additional string/key audit fixes** - orphaned `enable_zambretti` translation, missing `ws_enable_fog` and `ws_enable_thunderstorm_risk` switch entries, missing `features_opt` data descriptions, pollen incorrectly attributed to Tomorrow.io.

## [1.0.0] - 2026-05-14

Initial public release.

### Features

- **Zambretti barometric forecaster** - authentic Negretti & Zambra lookup table (Z-numbers 1-26) with climate-region-aware wind corrections and seasonal adjustment. Accuracy 65-75% for 6-12h forecasts in maritime/Mediterranean climates.
- **36-condition weather classifier** - real-time condition derived from illuminance, rain rate, wind gust, and temperature, with severity levels and MDI icon mapping.
- **Wet-bulb temperature** (Stull 2011, ±0.3 °C), **frost point** (Buck 1981 ice constants), **apparent temperature** (Australian BOM/Steadman).
- **Kalman-filtered rain rate** - eliminates tipping-bucket spike-and-drop artefacts. Configurable smoothing coefficient.
- **Pressure trend** - least-squares regression over configurable window (default 3h), classified per WMO Table 4680.
- **Fog probability** - dew-point depression model with wind-speed and nocturnal corrections.
- **Thunderstorm risk index** - surface-based heuristic (T-Td gap, pressure fall rate, wind acceleration, illuminance drop).
- **Full Canadian FWI system** - complete Van Wagner (1987) implementation: FFMC, DMC, DC (daily moisture codes with persistent carry-over), ISI, BUI, FWI, DSR. `sensor.ws_fire_risk_score` now maps real FWI to a 1-10 danger scale. Seven FWI sub-index sensors available (disabled by default).
- **Streak counters** - consecutive dry, heat, and frost days, reset at local midnight.
- **24h rolling statistics** - temperature high/low, wind gust maximum.
- **Rain accumulation** - 1h and 24h rolling windows, plus today's total.
- **ET₀ reference evapotranspiration** - Hargreaves-Samani 1985 by default; upgrades to FAO-56 Penman-Monteith automatically when a solar radiation sensor (W/m²) is mapped.
- **7-day daily forecast** - Open-Meteo (free, no API key).
- **Air Quality Index** - PM2.5-based US EPA AQI via Open-Meteo (free, no API key).
- **Pollen levels** - grass, tree, weed via Tomorrow.io (free API key required).
- **Moon phase & illumination** - calculated from Meeus 1998 astronomical algorithms, no external API.
- **Solar PV forecast** - today + tomorrow kWh via forecast.solar (free, no API key). Configurable peak kWp, azimuth, tilt.
- **Sea surface temperature** - Open-Meteo Marine API (free, no API key). Optional lat/lon override.
- **Weather Underground upload** - credentials validated at setup; configurable interval.
- **30-day rolling climatology** - local temperature and rain anomalies built from station history. Meaningful after ~14 days.
- **Sensor drift detection** - 72h linear regression flags monotonic drift (R² ≥ 0.85) in temperature, humidity, pressure, and rain rate.
- **Cross-sensor consistency** - six physical-impossibility checks (dew point > temp, gust < wind speed, UV/lux mismatch, etc.).
- **Self-adapting solar lux factor** - updates lux→W/m² conversion on clear days near solar noon, improving ET₀ accuracy over time.
- **Nowcast correction (0-3h)** - local station readings (temperature, humidity, wind, dew point, rain rate, condition) blend into the first three hourly forecast slots using tapering weights (70% local at hour 0, pure NWP by hour 3).
- **Adaptive rain probability** - `sensor.ws_rain_probability_combined` uses rolling 90-day Brier-score weights that learn which source (local sensors vs Open-Meteo) has been more accurate; falls back to fixed day/night weights until enough data accumulates.
- **Forecast agreement sensor** - `sensor.ws_forecast_agreement` compares Zambretti Z-number implied rain likelihood to Open-Meteo `precip_prob`; states: `aligned` (< 20 pp delta), `diverging` (20-40 pp), `conflict` (> 40 pp).

### Integration

- Guided config flow (8 steps + optional feature sub-steps). All settings reconfigurable post-install via Configure button.
- Config entities on device page: 10 `number` entities for thresholds, calibration offsets, and algorithm parameters; 10 `switch` entities for feature toggles. Changes trigger coordinator reload automatically.
- Standard HA `weather` entity with daily forecast.
- Diagnostics export (location data redacted).
- HACS-compatible.
- CI: ruff lint, hassfest, HACS validation, unit tests, version consistency check, no-bytecode check, dashboard entity validator.
