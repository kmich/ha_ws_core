# Weather Station Core (`ws_core`)

[![HACS][hacs-badge]][hacs-url]
[![GitHub Release][release-badge]][release-url]
[![License][license-badge]][license-url]
[![Validate][validate-badge]][validate-url]
[![Translations][translation-badge]][translation-url]

**Turn any weather station into a complete weather intelligence system: local forecasting,
precipitation nowcasting, fire danger, irrigation, lightning detection, and data quality.
150+ sensors. Fully local-capable. No API keys required for core features.**

---

## Why ws_core

Capabilities verified against `custom_components/ws_core/` at v2.0.7.
Each point describes functionality not available in any other Home Assistant weather integration.

- **Precipitation nowcast with minutes-until-rain.** `sensor.ws_minutes_until_rain`
  and `binary_sensor.ws_rain_expected_1h` use Open-Meteo 15-minute precipitation buckets
  refreshed every 15 minutes. No other HA integration exposes a minutes-precision rain
  arrival time.
- **UTCI (Universal Thermal Climate Index).** Full Bröde (2012) polynomial implementation.
  The gold-standard heat-stress metric used by WHO and national meteorological services.
  Not previously available in any HA weather integration.
- **Three fire danger systems in one integration.** Canadian FWI (Van Wagner 1987)
  with persistent daily moisture memory, McArthur FFDI (Australia), and Fosberg
  FFWI (US/global). Cover every inhabited continent where fire weather matters.
- **Zambretti barometric forecast.** The original Negretti & Zambra (1915) 26-entry
  lookup table with climate-region-aware wind corrections. Fully local: no network
  call, no API, 65-75% 6-12h accuracy in maritime and Mediterranean climates.
- **Penman-Monteith ET0** activates automatically when a solar radiation sensor is
  mapped, giving `sensor.ws_et0_pm_daily` with ±5-10% accuracy. The Hargreaves
  fallback (`sensor.ws_et0_daily`) works without solar radiation. Both are compatible
  with the Smart Irrigation integration.
- **8 upload targets in one integration.** Weather Underground, Weathercloud,
  PWSWeather, WOW (UK Met Office), AWEKAS, CWOP/APRS, OpenWeatherMap Stations, Windy.
  Each has an independent toggle and a status sensor.
- **8 full translations.** English, French, German, Dutch, Spanish, Italian,
  Portuguese, Polish. All 150+ entity names, config flow strings, and state labels
  are translated. New translations welcome.
- **Adaptive rain probability.** `sensor.ws_rain_probability_combined` uses a
  rolling 90-day Brier-score blend that learns, per location, whether local sensors
  or the NWP provider have been more accurate.

---

## 60-second quickstart {#quickstart}

### Install via HACS (recommended)

1. Open HACS in your Home Assistant sidebar
2. Go to **Integrations** and click the three-dot menu in the top right
3. Choose **Custom repositories**, add `https://github.com/kmich/ha_ws_core` with
   category **Integration**, and click **Add**
4. Search for "Weather Station Core" and click **Download**
5. Restart Home Assistant

### Configure

Go to **Settings → Devices & Services → Add Integration** and search for
"Weather Station Core". The setup wizard asks for:

| What you need | Example |
|---|---|
| Temperature sensor | `sensor.gw2000a_outdoor_temperature` |
| Humidity sensor | `sensor.gw2000a_outdoor_humidity` |
| Pressure sensor | `sensor.gw2000a_absolute_pressure` |
| Wind speed sensor | `sensor.gw2000a_wind_speed` |
| Wind gust sensor | `sensor.gw2000a_wind_gust` |
| Wind direction sensor | `sensor.gw2000a_wind_direction` |
| Cumulative rainfall sensor | `sensor.gw2000a_rain_total` |

Those 7 sensors are all that is required. Everything else is optional or auto-detected.

After the wizard completes, 50+ sensors appear immediately. Enable additional feature
groups (fire danger, nowcast, UTCI, lightning, etc.) from the device page or via
**Configure**.

---

## Screenshots {#screenshots}

| Weather view | Advanced view |
|---|---|
| ![Weather dashboard](screenshots/dashboard-weather.png) | ![Advanced dashboard](screenshots/dashboard-advanced.png) |

---

## What's New in 2.0.7

- **Configure dialog fixes** — editing source sensors no longer fails with "Unknown error
  occurred" (#70), and the general settings step no longer blocks with "Entity is neither
  a valid entity ID nor a valid UUID" when no HA weather entity is selected (#71).
- **Weather Underground uploads fixed** (thanks @miczu71, #72) — credential validation
  now checks the station key (password) against the actual PWS upload endpoint, so valid
  credentials save correctly and uploads are sent. The field is relabelled "Station key
  (password)" to match `wunderground.com/member/devices`.

## What's New in 2.0

Version 2.0 is the largest release to date. Highlights (all opt-in via the Features step):

- **WBGT and UTCI** — gold-standard heat-stress indices, plus cloud base, freezing level,
  air density, and specific humidity.
- **Fire danger for every region** — McArthur FFDI (Australia) and Fosberg FFWI (US/global)
  join the existing Canadian FWI.
- **Lightning detection** — count, distance, strike rate, clearance timer, and proximity
  alerts from WH57 / AS3935 / Blitzortung sensors.
- **Indoor sensors** — temperature, humidity, CO₂ with indoor/outdoor deltas and
  per-room temperature delta sensors.
- **Degree days and agro** — HDD/CDD/GDD, leaf wetness, irrigation water deficit,
  daily solar irradiation, net radiation.
- **Seven new upload networks** — Weathercloud, PWSWeather, WOW, AWEKAS, CWOP,
  OpenWeatherMap Stations, Windy.
- **MQTT Discovery republishing**, **HA Event entities**, expanded data-quality sensors.
- **Eight languages** (German, Dutch, Spanish, Italian, Portuguese, Polish added).

See the [CHANGELOG](CHANGELOG.md) for the complete list.

---

## Feature Reference {#features}

- **Real Zambretti barometric forecaster** — Negretti & Zambra lookup table (Z-numbers
  1-26), climate-region-aware wind corrections, seasonal adjustment
- **Wet-bulb temperature** (Stull 2011, ±0.3 °C) and **frost point** (Buck 1981 ice constants)
- **Comfort and heat-stress indices** — Heat Index (NWS Rothfusz), Wind Chill (WMO 2001),
  Humidex (Environment Canada), Davis THW/THSW; plus VPD, absolute humidity,
  Delta-T spray window, wind run, chill hours, and solar-derived clearness index and cloud cover
- **UTCI** (Universal Thermal Climate Index, Bröde 2012) and **WBGT**
- **Nowcast correction (0-3 h)** — local station readings blend into the first three hourly
  forecast slots with tapering weights (70% local at h+0, 40% at h+1, 10% at h+2,
  pure NWP from h+3); fields: temperature, humidity, dew point, wind speed
- **Adaptive rain probability** — `sensor.ws_rain_probability_combined` uses
  Brier-score-derived blend weights that learn over a rolling 90-day window which source
  (local heuristic vs NWP) has historically been more accurate
- **Forecast agreement sensor** — `sensor.ws_forecast_agreement` compares Zambretti's
  Z-number-implied rain likelihood against the NWP provider's `precip_prob`;
  states: `aligned` (< 20 pp delta), `diverging` (20-40 pp), `conflict` (> 40 pp)
- **Kalman-filtered rain rate** for de-noised precipitation readings
- **36-condition weather classifier** with severity levels and MDI icons
- **Fog probability** — dew-point depression model with wind, night, and rain corrections
- **Thunderstorm risk index** — surface-based heuristic proxy (T-Td gap, pressure fall
  rate, wind acceleration)
- **Streak counters** — consecutive dry days, heat days, and frost days
- **Full Canadian FWI system** — FFMC, DMC, DC, ISI, BUI, FWI, DSR with persistent daily
  moisture memory (Van Wagner 1987)
- **Pluggable forecast provider** — Open-Meteo (default, free), Met.no (free),
  NWS/NOAA (free, US only), OpenWeatherMap (API key), Pirate Weather (API key),
  Météo France (API key), or any existing HA `weather.*` entity
- **Air Quality Index** via Open-Meteo (free, no API key) — PM2.5, PM10, NO₂, ozone
- **Pollen levels** (grass, tree, weed) via Open-Meteo (free, no API key)
- **Moon phase and illumination** — calculated astronomically, no API key required
- **Solar PV forecast** (today + tomorrow kWh) via forecast.solar (free, no API key)
- **Penman-Monteith ET₀** — activates automatically when a solar radiation sensor is mapped
- **Sea surface temperature** via Open-Meteo Marine API (free, no API key)
- **30-day rolling climatology** — local temperature and rain anomalies built from station history
- **Sensor drift and consistency monitoring** — 72h regression drift detection,
  cross-sensor physics checks
- **MQTT Discovery republishing** — 70+ derived sensors published as MQTT Discovery payloads
- **8 upload targets** — Weather Underground, Weathercloud, PWSWeather, WOW, AWEKAS,
  CWOP/APRS, OpenWeatherMap Stations, Windy
- **8 translations** — EN, FR, DE, NL, ES, IT, PT, PL; all entity names, state labels,
  and config flow strings covered

---

## Requirements {#requirements}

A personal weather station integrated into Home Assistant providing at minimum:

| Measurement | Example entities |
|---|---|
| Temperature | `sensor.gw2000a_outdoor_temperature` |
| Relative humidity | `sensor.gw2000a_outdoor_humidity` |
| Atmospheric pressure | `sensor.gw2000a_absolute_pressure` |
| Wind speed | `sensor.gw2000a_wind_speed` |
| Wind gust | `sensor.gw2000a_wind_gust` |
| Wind direction (°) | `sensor.gw2000a_wind_direction` |
| Cumulative rainfall | `sensor.gw2000a_rain_total` |

**Optional** (improves derived metrics): illuminance (lux), UV index, dew point,
battery level, solar radiation (W/m²).

**Home Assistant**: 2026.3+ · **Python**: 3.12+

---

## Installation {#installation}

### Via HACS (recommended)

1. Open HACS → Integrations → ⋮ → Custom repositories
2. Add `https://github.com/kmich/ha_ws_core` (category: Integration)
3. Search for "Weather Station Core" and install
4. Restart Home Assistant

### Manual

1. Copy `custom_components/ws_core` to your HA `custom_components/` directory
2. Restart Home Assistant

---

## Configuration {#configuration}

Settings → Devices & Services → Add Integration → "Weather Station Core"

The setup wizard walks you through:

| Step | What it does |
|---|---|
| 1. Name and prefix | Station name and entity ID prefix (e.g. `ws` → `sensor.ws_temperature`) |
| 2. Required sensors | Map your 7 mandatory sensor entities |
| 3. Optional sensors | Map illuminance, UV, dew point, battery, solar radiation (leave blank to skip) |
| 4. Location and climate | Hemisphere, climate region, elevation (auto-detected from HA) |
| 5. Display units | Temperature, wind, rain, pressure unit preferences |
| 6. Forecast | Enable/disable 7-day forecast, coordinates, forecast provider |
| 7. Features | Toggle feature groups: fire risk, fog, thunderstorm, sea temp, WU upload, air quality, pollen, moon, solar forecast, comfort indices, Meteo Vigilance, Vigicrues, station diagnostics, FWI components, advanced sensors, precipitation nowcast |
| 8. Alerts | Wind/rain/freeze thresholds |

All settings can be changed later via **Configure** (Settings → Devices & Services → Weather Station Core → Configure).

---

## Sensors Created {#sensors}

### Core Measurements (always enabled)

| Entity | Unit | Device Class | Description |
|---|---|---|---|
| `sensor.ws_temperature` | °C | temperature | Normalized temperature |
| `sensor.ws_humidity` | % | humidity | Normalized relative humidity |
| `sensor.ws_station_pressure` | hPa | pressure | Station-level pressure |
| `sensor.ws_sea_level_pressure` | hPa | pressure | Mean sea-level pressure (MSLP) |
| `sensor.ws_wind_speed` | m/s | wind_speed | Sustained wind speed |
| `sensor.ws_wind_gust` | m/s | wind_speed | Wind gust speed |
| `sensor.ws_wind_direction` | ° | wind_direction | Wind direction |
| `sensor.ws_rain_total` | mm | precipitation | Cumulative rainfall (TOTAL_INCREASING) |
| `sensor.ws_rain_rate` | mm/h | precipitation_intensity | Kalman-filtered rain rate |
| `sensor.ws_dew_point` | °C | temperature | Dew point (Magnus formula) |
| `sensor.ws_illuminance` | lx | illuminance | Solar illuminance |
| `sensor.ws_uv_index` | - | - | UV index |

### Advanced Meteorological (always enabled)

| Entity | Unit | Description |
|---|---|---|
| `sensor.ws_feels_like` | °C | Apparent temperature (BOM/Steadman formula) |
| `sensor.ws_wet_bulb` | °C | Wet-bulb temperature (Stull 2011) |
| `sensor.ws_frost_point` | °C | Frost point (ice constants below 0 °C) |
| `sensor.ws_zambretti_forecast` | - | Zambretti barometric forecast text |
| `sensor.ws_zambretti_number` | - | Z-number (1-26) for automations |
| `sensor.ws_wind_beaufort` | - | Beaufort scale number |
| `sensor.ws_wind_quadrant` | - | 4-point compass quadrant (N/E/S/W) |
| `sensor.ws_current_condition` | - | 36-condition weather classifier |
| `sensor.ws_rain_probability` | % | Local sensor-based rain index |
| `sensor.ws_rain_probability_combined` | % | Blended local + NWP (Brier-score adaptive weights) |
| `sensor.ws_forecast_agreement` | - | Zambretti vs NWP agreement: `aligned` / `diverging` / `conflict` |
| `sensor.ws_pressure_trend` | - | Rising/Falling/Steady with rate (WMO No. 306) |
| `sensor.ws_rain_last_1h` | mm | Rolling 1-hour rain accumulation |
| `sensor.ws_rain_last_24h` | mm | Rolling 24-hour rain accumulation |
| `sensor.ws_rain_today` | mm | Today's accumulated rainfall (resets at local midnight) |

### 24h Rolling Statistics

| Entity | Description |
|---|---|
| `sensor.ws_temperature_high_24h` | 24-hour high temperature |
| `sensor.ws_temperature_low_24h` | 24-hour low temperature |
| `sensor.ws_wind_gust_max_24h` | 24-hour maximum gust |

### Streak Counters (always enabled)

| Entity | Unit | Description |
|---|---|---|
| `sensor.ws_dry_streak` | days | Consecutive days without measurable rain |
| `sensor.ws_heat_streak` | days | Consecutive days above heat threshold |
| `sensor.ws_frost_streak` | days | Consecutive days below 0 °C |

### ET₀ Reference Evapotranspiration {#et0}

| Entity | Unit | Description |
|---|---|---|
| `sensor.ws_et0_daily` | mm | Daily ET₀ — Hargreaves-Samani 1985 (±15-20%) |
| `sensor.ws_et0_pm_daily` | mm | Daily ET₀ — Penman-Monteith (activates when solar radiation sensor is mapped; ±5-10%) |

### Always-on additions (v2.0)

| Entity | Unit | Description |
|---|---|---|
| `sensor.ws_cloud_base` | m | Estimated cloud base height (lifted condensation level) |
| `sensor.ws_freezing_level` | m | Estimated freezing-level altitude (ISA lapse rate) |
| `sensor.ws_wind_gust_factor` | - | Gust ÷ mean wind speed ratio |
| `sensor.ws_dominant_wind_direction` | ° | Circular-mean wind direction over 24 h |
| `sensor.ws_wind_direction_variability` | ° | Circular standard deviation of wind direction |
| `sensor.ws_rain_this_week` / `_this_month` / `_this_year` | mm | Rolling rain accumulators |
| `sensor.ws_rain_rate_max_24h` | mm/h | Rolling 24 h maximum rain rate |

### Optional: Precipitation Nowcast (`enable_nowcast`) {#nowcast}

Opt-in. Short-term rain timing from Open-Meteo's 15-minute precipitation buckets
(free, no API key, independent of the chosen forecast provider). Refreshes every 15 minutes.

| Entity | Unit | Description |
|---|---|---|
| `sensor.ws_minutes_until_rain` | min | Minutes until rain is expected to start (unknown when none in window) |
| `sensor.ws_minutes_until_dry` | min | Minutes until rain is expected to stop (when raining) |
| `sensor.ws_rain_next_60min` | mm | Total precipitation expected in the next hour |
| `sensor.ws_nowcast_intensity` | - | none / light / moderate / heavy (peak rate in the next hour) |
| `binary_sensor.ws_rain_expected_1h` | - | On when measurable rain is expected within 60 minutes |

### Optional: Comfort Indices (`enable_comfort_indices`) {#comfort}

| Entity | Unit | Description |
|---|---|---|
| `sensor.ws_heat_index` | °C | NWS Heat Index (Rothfusz); active only when T ≥ 27 °C and RH ≥ 40% |
| `sensor.ws_wind_chill` | °C | WMO/NWS Wind Chill (2001); active only when T ≤ 10 °C and wind > 1.34 m/s |
| `sensor.ws_humidex` | °C | Canadian Humidex (Environment Canada) |
| `sensor.ws_thw_index` | °C | Davis THW index — Heat Index with wind cooling |
| `sensor.ws_thsw_index` | °C | Davis THSW index — THW plus solar heating (needs solar radiation sensor) |
| `sensor.ws_vpd` | kPa | Vapour Pressure Deficit — greenhouse / irrigation control |
| `sensor.ws_absolute_humidity` | g/m³ | Mass of water vapour per m³ of air |
| `sensor.ws_delta_t` | °C | Dry-bulb minus wet-bulb; `spray_suitability` attribute: `ideal` (2-8 °C) / too low / too high |
| `sensor.ws_wind_run` | km | Daily accumulated wind travel; resets at local midnight |
| `sensor.ws_chill_hours_today` | h | Hours today at or below the chill base temperature (default 7.2 °C) |
| `sensor.ws_chill_hours_season` | h | Season-to-date chill hours; resets on configured date |
| `sensor.ws_clearness_index` | - | Clearness index Kt (needs solar radiation sensor) |
| `sensor.ws_cloud_cover` | % | Approximate cloud cover derived from the clearness index |
| `sensor.ws_utci` | °C | UTCI (Universal Thermal Climate Index, Bröde 2012) |
| `sensor.ws_wbgt` | °C | Wet Bulb Globe Temperature |
| `sensor.ws_air_density` | kg/m³ | Air density |
| `sensor.ws_specific_humidity` | g/kg | Specific humidity |
| `sensor.ws_solar_irradiation_daily` | Wh/m² | Daily solar energy accumulation |
| `sensor.ws_net_radiation` | W/m² | Net radiation (FAO-56) |
| `sensor.ws_irrigation_deficit` | mm | Irrigation water deficit |

### Optional: Fire Risk and Canadian FWI (`enable_fire_risk_score`) {#fire-danger}

| Entity | Scale | Description |
|---|---|---|
| `sensor.ws_fire_risk_score` | 1-10 | Fire danger level derived from FWI |
| `sensor.ws_fwi` | ≥ 0 | Fire Weather Index — intensity of a spreading fire |
| `sensor.ws_fwi_dsr` | ≥ 0 | Daily Severity Rating — difficulty of fire control |
| `sensor.ws_ffdi` | ≥ 0 | McArthur Fire Danger Index (Australia) |
| `sensor.ws_ffwi` | ≥ 0 | Fosberg Fire Weather Index (US/global) |

FWI sub-components (enable via `enable_fwi_components`):

| Entity | Scale | Description |
|---|---|---|
| `sensor.ws_fwi_ffmc` | 0-101 | Fine Fuel Moisture Code |
| `sensor.ws_fwi_dmc` | ≥ 0 | Duff Moisture Code |
| `sensor.ws_fwi_dc` | ≥ 0 | Drought Code |
| `sensor.ws_fwi_isi` | ≥ 0 | Initial Spread Index |
| `sensor.ws_fwi_bui` | ≥ 0 | Buildup Index |

### Optional: Lightning Detection (`enable_lightning`) {#lightning}

Accepts cumulative strike count + optional nearest-distance from a WH57, AS3935, or
Blitzortung device. Blitzortung auto-discovered if installed and no manual mapping is set.

| Entity | Unit | Description |
|---|---|---|
| `sensor.ws_lightning_count_1h` | strikes | Strikes in the last hour |
| `sensor.ws_lightning_distance` | km | Nearest detected strike |
| `sensor.ws_lightning_rate` | /min | Average strike rate |
| `sensor.ws_lightning_clearance` | min | Minutes since the last strike (safe at ≥30) |
| `sensor.ws_lightning_proximity` | - | `near` / `clear` vs a configurable threshold |

### Optional: Indoor Sensors (`enable_indoor`)

| Entity | Description |
|---|---|
| `sensor.ws_indoor_temperature` / `_humidity` / `_co2` | Indoor readings |
| `sensor.ws_indoor_temp_delta` / `_humidity_delta` | Indoor/outdoor differentials |
| `sensor.ws_indoor_comfort` | 0-100 composite comfort score |
| `sensor.ws_indoor_room_delta_<room>` | Per-room temperature delta vs outdoor |

### Optional: Degree Days and Leaf Wetness (`enable_degree_days`)

| Entity | Description |
|---|---|
| `sensor.ws_hdd_today` / `_season` | Heating degree days (configurable base) |
| `sensor.ws_cdd_today` / `_season` | Cooling degree days |
| `sensor.ws_gdd_today` / `_season` | Growing degree days (base/cap configurable) |
| `sensor.ws_leaf_wetness` | wet / dry |

### Optional: Air Quality (`enable_air_quality`)

| Entity | Unit | Description |
|---|---|---|
| `sensor.ws_air_quality_index` | AQI | US EPA AQI from Open-Meteo (PM2.5-based) |
| `sensor.ws_no2` | µg/m³ | Nitrogen dioxide (diagnostic) |
| `sensor.ws_ozone` | µg/m³ | Ozone (diagnostic) |

### Optional: Pollen (`enable_pollen`)

| Entity | Description |
|---|---|
| `sensor.ws_pollen_level` | Highest of grass/tree/weed (None/Low/Medium/High/Very High) |
| `sensor.ws_pollen_grass` | Grass pollen IQLA index |
| `sensor.ws_pollen_tree` | Tree pollen IQLA index |
| `sensor.ws_pollen_weed` | Weed pollen IQLA index |

### Optional: Moon (`enable_moon`)

| Entity | Description |
|---|---|
| `sensor.ws_moon` | Human-readable phase name with illumination % |
| `sensor.ws_moon_illumination` | Illumination percentage |

### Optional: Solar PV Forecast (`enable_solar_forecast`)

| Entity | Unit | Description |
|---|---|---|
| `sensor.ws_solar_forecast_today` | kWh | Estimated PV generation today |
| `sensor.ws_solar_forecast_tomorrow` | kWh | Estimated PV generation tomorrow |

### Optional: Fog Probability (`enable_fog`)

| Entity | Unit | Description |
|---|---|---|
| `sensor.ws_fog_probability` | % | Dew-point depression fog model |

### Optional: Thunderstorm Risk (`enable_thunderstorm_risk`)

| Entity | Scale | Description |
|---|---|---|
| `sensor.ws_thunderstorm_risk` | 0-100 | Surface-based thunderstorm risk index |

### Optional: Sea Surface Temperature (`enable_sea_temp`)

| Entity | Unit | Description |
|---|---|---|
| `sensor.ws_sea_surface_temperature` | °C | SST via Open-Meteo Marine API |

### Optional: Meteo Vigilance (`enable_vigilance_meteo`)

France only. No API key required. Fetches from Météo-France Vigilance every 30 minutes.

| Entity | Description |
|---|---|
| `sensor.ws_vigilance` | Worst departmental alert colour: `vert` / `jaune` / `orange` / `rouge` |

### Optional: Vigicrues River Level (`enable_vigicrues`)

France only. No API key required.

| Entity | Unit | Description |
|---|---|---|
| `sensor.ws_river_level` | m | Real-time water height at the nearest gauging station |

### Optional: Station Diagnostics (`enable_diagnostics`)

| Entity | Description |
|---|---|
| `sensor.ws_sensor_drift` | Per-sensor monotonic drift detection flags |
| `sensor.ws_sensor_consistency` | Cross-sensor physical consistency flags |
| `sensor.ws_sensor_quality_flags` | Aggregate sensor validation flags |
| `sensor.ws_forecast_skill` | Learned forecast skill score |
| `sensor.ws_solar_lux_factor` | Learned lux → W/m² conversion factor |
| `sensor.ws_climatology_30d` | Rolling 30-day climatology summary |
| `sensor.ws_temperature_anomaly_30d` | Today's mean temperature vs 30-day rolling mean |
| `sensor.ws_rain_anomaly_30d` | Today's rain vs 30-day rolling daily average |

### Optional: Network Uploads

Each upload target is an independent toggle with its own credentials and a status sensor:
`enable_wunderground`, `enable_weathercloud`, `enable_pwsweather`, `enable_wow`,
`enable_awekas`, `enable_cwop`, `enable_owm_stations`, `enable_windy`.

### Optional: MQTT Discovery (`enable_mqtt`)

Republishes 70+ derived sensors as MQTT Discovery entities for Node-RED, external
dashboards, or other HA instances. Requires the Home Assistant MQTT integration.

### HA Event entities (v2.0)

`event.ws_rain_event`, `event.ws_frost_event`, and `event.ws_lightning_event`
fire on weather transitions (rain start/stop, frost/thaw, lightning strike/proximity)
for use as automation triggers. Requires Home Assistant 2023.8+.

### Other Entities

| Entity | Type | Description |
|---|---|---|
| `weather.ws` | weather | Standard HA weather entity with daily forecast |
| `binary_sensor.ws_package_ok` | binary_sensor | True when all required sources are mapped and available |
| `select.ws_graph_range` | select | Dashboard graph time range (6h/24h/3d) |
| `sensor.ws_forecast_provider` | sensor | Active forecast provider diagnostic |
| `switch.ws_enable_animations` | switch | Dashboard-only animation toggle |

### Configuration Entities (device page)

**Number entities** (thresholds, calibration offsets, algorithm parameters):

| Entity | Unit | Description |
|---|---|---|
| `number.ws_thresh_wind_gust` | m/s | Wind gust alert threshold |
| `number.ws_thresh_rain_rate` | mm/h | Rain rate alert threshold |
| `number.ws_thresh_freeze` | °C | Freeze warning threshold |
| `number.ws_cal_temp` | °C | Temperature calibration offset |
| `number.ws_cal_humidity` | % | Humidity calibration offset |
| `number.ws_cal_pressure` | hPa | Pressure calibration offset |
| `number.ws_cal_wind` | m/s | Wind speed calibration offset |
| `number.ws_staleness_timeout` | s | Sensor staleness timeout |
| `number.ws_rain_filter_alpha` | - | Rain-rate Kalman filter smoothing coefficient |
| `number.ws_pressure_trend_window` | h | Pressure trend calculation window |

---

## Dashboards {#dashboards}

Three dashboards are provided in `dashboards/`:

### Vanilla Dashboard (`weather_dashboard_vanilla.yaml`)

Uses only native HA cards — no HACS frontend dependencies. Works immediately after installation.

To install: copy the YAML → Dashboard → Edit → Raw Configuration Editor → paste → save.

### Enhanced Dashboard (`weather_dashboard.yaml`)

Rich visual dashboard requiring: `custom:button-card`, `custom:mini-graph-card`,
`custom:stack-in-card`, `custom:config-template-card`, `custom:windrose-card`,
`card-mod`, `kiosk-mode`.

### v2.0 Dashboards

- **`ws_core_dashboard.yaml`** — full 6-view dashboard (Now / Charts / Advanced /
  Records / Diagnostics / Indoor). Needs `mushroom` + `mini-graph-card`.
- **`ws_core_dashboard_mobile.yaml`** — single-column, touch-optimised layout for
  phones. Needs `mushroom` + `mini-graph-card`.
- **`ws_core_gauge_presets.yaml`** — drop-in gauge cards with sensible severity bands
  for 12 common sensors. Uses the built-in `gauge` card (no HACS needed).

---

## Migrating from Thermal Comfort {#migrating-from-thermal-comfort}

If you are currently using the Thermal Comfort integration, see
[docs/migrating_from_thermal_comfort.md](docs/migrating_from_thermal_comfort.md) for
a step-by-step guide with entity ID mapping.

---

## Forecast Provider {#forecast-provider}

| Provider | Free | API key | Notes |
|---|---|---|---|
| **Open-Meteo** *(default)* | Yes | No | Global coverage |
| **Met.no** | Yes | No | Norwegian Meteorological Institute; excellent European coverage |
| **NWS/NOAA** | Yes | No | US only |
| **OpenWeatherMap** | Free tier | Yes | One Call 3.0 API |
| **Pirate Weather** | Free tier | Yes | Dark Sky-compatible API |
| **Météo France** | Free tier | Yes | Météo Concept API |
| **Home Assistant weather entity** | Yes | No | Uses any existing `weather.*` entity. No external calls. |

Change the provider at any time via **Configure** — no reinstall needed.

---

## Scientific Documentation {#science}

Every derived metric is documented with its algorithm, source reference, valid input
range, and known limitations.

---

### Dew Point — Magnus Formula (Alduchov & Eskridge 1996)

The dew point T_d is the temperature at which air becomes saturated if cooled at
constant pressure and humidity.

```
γ(T, RH) = (a·T) / (b + T) + ln(RH / 100)
T_d = (b · γ) / (a − γ)

Over water (T ≥ 0 °C): a = 17.625, b = 243.04 °C   [Alduchov & Eskridge 1996]
Over ice  (T < 0 °C):  a = 22.587, b = 273.86 °C   [Buck 1981]
```

**Valid range:** −45 °C to +60 °C, 1-100% RH. **Max error:** < 0.1 °C within range.
**Reference:** Alduchov, O.A. & Eskridge, R.E. (1996). *J. Appl. Meteor.*, 35, 601-609.

---

### Frost Point — Magnus Formula with Ice Constants (Buck 1981)

The frost point is the temperature at which ice saturation occurs. Uses Buck's (1981)
ice-phase saturation constants (a = 22.587, b = 273.86). Returns dew point above 0 °C,
frost point below 0 °C.

**Reference:** Buck, A.L. (1981). *J. Appl. Meteor.*, 20, 1527-1532.

---

### Wet-Bulb Temperature — Stull (2011)

```
T_w = T · atan(0.151977 · (RH + 8.313659)^0.5)
    + atan(T + RH)
    − atan(RH − 1.676331)
    + 0.00391838 · RH^1.5 · atan(0.023101 · RH)
    − 4.686035
```

**Valid range:** T −20 to +50 °C, RH 5-99%. **Max error:** ±0.3 °C.
**Reference:** Stull, R. (2011). *J. Appl. Meteor. Climatol.*, 50, 2267-2269.

---

### Sea-Level Pressure — Hypsometric Reduction (WMO No. 8)

```
MSLP = P_station × exp(elevation_m / (T_K × 29.263))
```

**Accuracy:** ±0.3 hPa below 500 m, ±1 hPa at 2000 m.
**Reference:** WMO No. 8 — Guide to Meteorological Instruments and Methods of Observation, Annex 3A.

---

### Apparent Temperature — Australian BOM / Steadman (1994)

```
AT = T_a + 0.33 · e − 0.70 · ws − 4.0

where e = (RH / 100) × 6.105 × exp((17.27 · T) / (237.7 + T))   [vapour pressure, hPa]
      ws = wind speed at 10 m height [m/s]
```

**Reference:** Steadman, R.G. (1994). *Aust. Met. Mag.*, 43, 1-16.

---

### Heat Index — NWS Rothfusz Regression (1990)

```
HI = −42.379 + 2.04901523·T + 10.14333127·RH − 0.22475541·T·RH
     − 0.00683783·T² − 0.05481717·RH² + 0.00122874·T²·RH
     + 0.00085282·T·RH² − 0.00000199·T²·RH²       (T in °F)
```

**Valid range:** T ≥ 27 °C (80 °F) and RH ≥ 40%.
**Reference:** Rothfusz, L.P. (1990). *The Heat Index Equation.* NWS Technical Attachment SR 90-23.

---

### Wind Chill — WMO / NWS Joint Index (2001)

```
WCT = 13.12 + 0.6215·T − 11.37·V^0.16 + 0.3965·T·V^0.16
      (T in °C, V = wind speed in km/h)
```

**Valid range:** T ≤ 10 °C and wind > 1.34 m/s (4.8 km/h).
**Reference:** Environment Canada / NWS (2001). New wind chill equivalent temperature index.

---

### Humidex — Environment Canada (Masterton & Richardson 1979)

```
e = 6.1078 · exp[5417.7530 · (1/273.16 − 1/(273.16 + T_d))]
Humidex = T + 0.5555 · (e − 10)        (T, T_d in °C; e in hPa)
```

**Reference:** Masterton, J.M. & Richardson, F.A. (1979). *Humidex: A method of quantifying human discomfort.* Environment Canada, CLI 1-79.

---

### Davis THW and THSW Indices

```
THW  = HeatIndex − 1.072 · V          (V in mph)
THSW = THW + 0.01 · solar_radiation    (solar in W/m²)
```

**Reference:** Davis Instruments WeatherLink documentation; Steadman (1979).

---

### Vapour Pressure Deficit (VPD)

```
e_s = 0.6108 · exp(17.27·T / (T + 237.3))     (saturation, kPa)
VPD = e_s − e_s · RH/100
```

**Reference:** Allen, R.G. et al. (1998). *FAO Irrigation and Drainage Paper 56.*

---

### Delta-T — Spray Application Index

```
Delta-T = T − T_wetbulb
```

| Delta-T | Suitability |
|---|---|
| < 2 °C | Unsuitable (too humid) |
| 2-8 °C | Ideal spray window |
| > 8 °C | Unsuitable (too dry) |

**Reference:** APVMA spraying guidelines.

---

### Zambretti Barometric Forecaster (Negretti & Zambra, 1915) {#zambretti}

The Zambretti forecaster produces a forecast letter A-Z (Z-number 1-26) from three
observable surface quantities: MSLP, pressure trend, and wind direction. The final
Z-number indexes the authentic 26-entry Negretti & Zambra lookup table.

**Accuracy:** 65-75% for 6-12h forecasts in maritime and Mediterranean climates.

**References:**
- Negretti & Zambra (1915). *A Treatise on Meteorological Instruments.* London.
- Watts, A. (2012). *Instant Wind Forecasting.* Adlard Coles Nautical.

---

### Pressure Trend — Least-Squares Regression (WMO No. 306)

OLS regression fitted to the pressure history buffer (configurable window, default 3h),
slope extrapolated to a standardised 3-hour equivalent rate. Classification follows
WMO synoptic code Table 4680.

**Reference:** WMO No. 306 — Manual on Codes, Vol. I.1, Table 4680.

---

### Canadian Forest Fire Weather Index System (Van Wagner 1987) {#fwi}

Complete Van Wagner (1987) implementation: FFMC, DMC, DC moisture codes with persistent
daily carry-over across HA restarts, ISI, BUI, FWI, DSR.

**Disclaimer:** Not suitable for operational fire weather decisions. Consult official
fire services and national fire weather products.

**Reference:** Van Wagner, C.E. (1987). *Development and structure of the Canadian Forest
Fire Weather Index System.* Forestry Technical Report 35. Canadian Forestry Service.

---

### ET₀ — Reference Evapotranspiration {#et0-science}

**Hargreaves-Samani 1985** (default, always available):

```
ET₀ = 0.0023 · Ra · (T_mean + 17.8) · (T_max − T_min)^0.5
```

**Accuracy:** ±15-20% vs Penman-Monteith.
**Reference:** Hargreaves, G.H. & Samani, Z.A. (1985). *Appl. Eng. Agric.*, 1, 96-99.

**FAO-56 Penman-Monteith** (activates when a `solar_radiation` W/m² source is mapped):

```
ET₀ = [0.408·Δ·(Rn − G) + γ·(900/(T+273))·u₂·(eₛ − eₐ)] / [Δ + γ·(1 + 0.34·u₂)]
```

**Accuracy:** ±5-10% vs lysimeter under standard conditions.
**Reference:** Allen, R.G. et al. (1998). *FAO Irrigation and Drainage Paper 56.* FAO, Rome.

---

### Moon Phase — Meeus Astronomical Algorithms (1998)

Computed from Julian Date using simplified lunar orbital equations without external API calls.
**Accuracy:** ±1% illumination, ±0.5 day phase timing.
**Reference:** Meeus, J. (1998). *Astronomical Algorithms*, 2nd ed. Willmann-Bell. Chapter 48.

---

### Rain Rate — 1D Kalman Filter

Optimal recursive smoothing eliminates tipping-bucket spike-and-drop artefacts.
Configurable measurement noise (`number.ws_rain_filter_alpha`).

---

### 30-Day Rolling Climatology

After approximately 14 days of operation, the integration builds a local climate baseline
from the station's own history. Temperature and rain anomaly sensors are meaningful after
30+ days of continuous operation.

---

### Sensor Drift Detection — Linear Regression (72h)

OLS regression over 72h flagging monotonic drift (slope magnitude + R² ≥ 0.85) in
temperature, humidity, pressure, and rain rate.

---

### Cross-Sensor Consistency Checks

Six physical-impossibility checks per coordinator update:

| Check | Violation condition |
|---|---|
| Gust vs wind | Gust speed < sustained wind speed |
| Dew point vs temperature | Dew point > air temperature |
| UV vs illuminance | UV index > 0 while illuminance < 50 lx |
| UV vs time of day | UV index > 2 between 22:00-04:00 local time |
| Rain rate vs total | Rain rate > 0 but cumulative rain total unchanged |
| Pressure stuck | Pressure unchanging for > 3h while wind speed > 2 m/s |

---

## Services {#services}

| Service | Description |
|---|---|
| `ws_core.reset_rain_baseline` | Reset the internal rain total baseline (useful after station rain counter resets) |
| `ws_core.apply_calibration` | Write sensor calibration offsets from an automation or Developer Tools |

---

## Sensor Calibration {#calibration}

All offsets are applied after unit conversion, before all derived calculations.

| Offset | Range | Typical use |
|---|---|---|
| Temperature | ±10 °C | Correct for sensor placement or radiation shield quality |
| Humidity | ±20% | Compensate for sensor aging |
| Pressure | ±10 hPa | Correct for altitude error |
| Wind speed | ±5 m/s | Adjust for sheltered mounting |

---

## Troubleshooting {#troubleshooting}

| Symptom | Likely Cause | Fix |
|---|---|---|
| All sensors show "unavailable" | Source entities not found | Check source sensor entity IDs in Configure |
| Temperature statistics look wrong | Old `TOTAL_INCREASING` state class | Delete the temperature entity from HA, restart |
| Rain rate stuck at 0 | Rain total sensor reset | Call `ws_core.reset_rain_baseline` service |
| Forecast shows "unavailable" | Provider API timeout or auth error | Check internet; verify API key if using OWM/Pirate Weather |
| "Stale" warning | Source sensor stopped updating | Check your weather station hardware |

Download diagnostics via **Settings → Devices & Services → Weather Station Core → ⋮ → Download Diagnostics**.

---

## Known Limitations

1. Illuminance-based cloud detection uses raw lux without solar-angle normalization. Accuracy degrades at low sun elevation angles.
2. Sea-level pressure uses current temperature only, not the WMO-recommended 12h mean.
3. Rain probability is a heuristic index, not a statistically calibrated probability.
4. FWI moisture codes are initialised at Van Wagner's standard defaults on first run and self-correct within a few days.
5. Thunderstorm Risk is a surface-based proxy only and cannot detect elevated convection.
6. 24h statistics are computed from in-memory rolling windows and reset on HA restart.

---

## Example Automations

Five automation blueprints are provided in `blueprints/automation/ws_core/`:

- **Frost Alert** — Notify when temperature drops below threshold
- **Storm Alert** — Alert on rapid pressure drop with high wind
- **Irrigation Rain Skip** — Skip watering when rain is expected or accumulated
- **Lightning Safety** — Notify when lightning is detected nearby
- **Fire Danger Alert** — Alert when fire danger reaches a configurable level

See [blueprints/README.md](blueprints/README.md) for installation instructions.

---

## Contributing {#contributing}

Contributions are welcome. Open an issue first to discuss what you'd like to change.

- **Translations**: Copy `custom_components/ws_core/translations/en.json` to a new
  locale file (e.g. `de.json`) and open a PR. All entity names, config flow strings,
  and state labels are covered.
- **Bug reports**: Use the GitHub issue template and include your diagnostics export.
- **Weather stations**: If your station brand needs special handling, open an issue
  with your entity details.
- **New forecast providers**: Create `custom_components/ws_core/providers/your_provider.py`,
  subclass `ForecastProvider` from `base.py`, and add one line to `providers/__init__.py`.

---

## License

[MIT](LICENSE)

---

[hacs-badge]: https://img.shields.io/badge/HACS-Custom-41BDF5.svg
[hacs-url]: https://github.com/hacs/integration
[release-badge]: https://img.shields.io/github/v/release/kmich/ha_ws_core
[release-url]: https://github.com/kmich/ha_ws_core/releases
[license-badge]: https://img.shields.io/github/license/kmich/ha_ws_core
[license-url]: https://github.com/kmich/ha_ws_core/blob/main/LICENSE
[validate-badge]: https://img.shields.io/github/actions/workflow/status/kmich/ha_ws_core/validate.yml?label=validate
[validate-url]: https://github.com/kmich/ha_ws_core/actions/workflows/validate.yml
[translation-badge]: https://img.shields.io/badge/translations-8-blue
[translation-url]: https://github.com/kmich/ha_ws_core/tree/main/custom_components/ws_core/translations
