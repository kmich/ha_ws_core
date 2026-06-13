# Sensors Reference

Complete list of entities created by Weather Station Core at v2.1.0.

Entity IDs shown use the default prefix `ws`. If you chose a different prefix during
setup, replace `ws` with your prefix.

---

## Always-on: Core Measurements

Created for every installation, regardless of optional features.

| Entity ID | Unit | State Class | Description |
|---|---|---|---|
| `sensor.ws_temperature` | °C | measurement | Normalized outdoor temperature |
| `sensor.ws_humidity` | % | measurement | Normalized relative humidity |
| `sensor.ws_station_pressure` | hPa | measurement | Station-level atmospheric pressure |
| `sensor.ws_sea_level_pressure` | hPa | measurement | Mean sea-level pressure (MSLP) |
| `sensor.ws_wind_speed` | m/s | measurement | Sustained wind speed |
| `sensor.ws_wind_gust` | m/s | measurement | Wind gust speed |
| `sensor.ws_wind_direction` | ° | measurement_angle | Wind direction |
| `sensor.ws_rain_total` | mm | total_increasing | Cumulative rainfall |
| `sensor.ws_rain_rate` | mm/h | measurement | Kalman-filtered rain rate |
| `sensor.ws_dew_point` | °C | measurement | Dew point — Magnus formula (Alduchov & Eskridge 1996) |
| `sensor.ws_illuminance` | lx | measurement | Solar illuminance (if mapped) |
| `sensor.ws_uv_index` | — | measurement | UV index (if mapped) |

## Always-on: Advanced Meteorological

| Entity ID | Unit | Description |
|---|---|---|
| `sensor.ws_feels_like` | °C | Apparent temperature (BOM/Steadman 1994) |
| `sensor.ws_wet_bulb` | °C | Wet-bulb temperature (Stull 2011, ±0.3 °C) |
| `sensor.ws_frost_point` | °C | Frost point with Buck (1981) ice constants |
| `sensor.ws_zambretti_forecast` | — | Zambretti text forecast (26 phrases) |
| `sensor.ws_zambretti_number` | — | Z-number 1-26 |
| `sensor.ws_wind_beaufort` | — | Beaufort scale classification |
| `sensor.ws_wind_quadrant` | — | N / E / S / W compass quadrant |
| `sensor.ws_current_condition` | — | 36-condition weather classifier |
| `sensor.ws_rain_probability` | % | Local sensor-based rain index |
| `sensor.ws_rain_probability_combined` | % | Brier-score blended local + NWP |
| `sensor.ws_forecast_agreement` | — | `aligned` / `diverging` / `conflict` |
| `sensor.ws_pressure_trend` | — | WMO No. 306 classification + rate |
| `sensor.ws_conditions_summary` | — | Human-readable conditions description (e.g. "Warm · 68% RH · Light rain · SE 12 km/h"). Useful for TTS and Assist. |
| `sensor.ws_rain_last_1h` | mm | Rolling 1-hour rainfall |
| `sensor.ws_rain_last_24h` | mm | Rolling 24-hour rainfall |
| `sensor.ws_rain_today` | mm | Today's accumulated rainfall |

## Always-on: 24h Statistics and Streaks

| Entity ID | Unit | Description |
|---|---|---|
| `sensor.ws_temperature_high_24h` | °C | 24h rolling temperature maximum |
| `sensor.ws_temperature_low_24h` | °C | 24h rolling temperature minimum |
| `sensor.ws_wind_gust_max_24h` | m/s | 24h rolling gust maximum |
| `sensor.ws_dry_streak` | days | Consecutive days without measurable rain |
| `sensor.ws_heat_streak` | days | Consecutive days above heat threshold |
| `sensor.ws_frost_streak` | days | Consecutive days below 0 °C |

## Always-on: ET₀

| Entity ID | Unit | Formula | Description |
|---|---|---|---|
| `sensor.ws_et0_daily` | mm | Hargreaves-Samani 1985 | Daily reference ET₀ (±15-20%) |
| `sensor.ws_et0_pm_daily` | mm | FAO-56 Penman-Monteith | Activates when solar radiation sensor is mapped (±5-10%) |

## Always-on: v2.0 additions

| Entity ID | Unit | Description |
|---|---|---|
| `sensor.ws_cloud_base` | m | Cloud base height (lifted condensation level) |
| `sensor.ws_freezing_level` | m | Freezing-level altitude (ISA lapse rate) |
| `sensor.ws_wind_gust_factor` | — | Gust ÷ mean wind speed ratio |
| `sensor.ws_dominant_wind_direction` | ° | Circular-mean wind direction (24h) |
| `sensor.ws_wind_direction_variability` | ° | Circular standard deviation of wind direction |
| `sensor.ws_rain_this_week` | mm | Rolling weekly rainfall accumulator |
| `sensor.ws_rain_this_month` | mm | Rolling monthly rainfall accumulator |
| `sensor.ws_rain_this_year` | mm | Rolling yearly rainfall accumulator |
| `sensor.ws_rain_rate_max_24h` | mm/h | Rolling 24h maximum rain rate |

---

## Optional: Precipitation Nowcast (`enable_nowcast`)

Requires: coordinates set in Forecast step. Uses Open-Meteo minutely_15 (free, no API key).
Refreshes every 15 minutes.

| Entity ID | Unit | Description |
|---|---|---|
| `sensor.ws_minutes_until_rain` | min | Minutes until rain is expected (unknown when none in window) |
| `sensor.ws_minutes_until_dry` | min | Minutes until rain stops (when currently raining) |
| `sensor.ws_rain_next_60min` | mm | Total precipitation expected in the next 60 minutes |
| `sensor.ws_nowcast_intensity` | — | none / light / moderate / heavy |
| `sensor.ws_nowcast_confidence` | — | `high` / `medium` / `low` — agreement between local gauge and NWP grid for the 0–30 min window |
| `binary_sensor.ws_rain_expected_1h` | — | On when rain is expected within 60 minutes |

---

## Optional: Comfort Indices (`enable_comfort_indices`)

All 21 sensors are created when the feature is enabled.
THSW index, clearness index, and cloud cover also require a solar radiation sensor.

| Entity ID | Unit | Formula / reference | Notes |
|---|---|---|---|
| `sensor.ws_heat_index` | °C | Rothfusz (1990) | Active when T ≥ 27 °C and RH ≥ 40% |
| `sensor.ws_wind_chill` | °C | WMO/NWS (2001) | Active when T ≤ 10 °C and wind > 1.34 m/s |
| `sensor.ws_humidex` | °C | Masterton & Richardson (1979) | Active when result exceeds ambient T |
| `sensor.ws_thw_index` | °C | Davis Instruments | THW — heat index with wind cooling |
| `sensor.ws_thsw_index` | °C | Davis Instruments | THSW — THW plus solar heating; needs solar radiation |
| `sensor.ws_vpd` | kPa | FAO-56 (Allen 1998) | Vapour Pressure Deficit |
| `sensor.ws_absolute_humidity` | g/m³ | Ideal gas law | Mass of water vapour per m³ |
| `sensor.ws_delta_t` | °C | APVMA | Dry-bulb minus wet-bulb; `spray_suitability` attribute |
| `sensor.ws_wind_run` | km | — | Daily accumulated wind travel |
| `sensor.ws_chill_hours_today` | h | Weinberger (1950) | Hours at or below chill base temp today |
| `sensor.ws_chill_hours_season` | h | Weinberger (1950) | Season-to-date chill hours |
| `sensor.ws_clearness_index` | — | Duffie & Beckman (2013) | Kt = observed / clear-sky solar; needs solar radiation |
| `sensor.ws_cloud_cover` | % | — | Derived from clearness index |
| `sensor.ws_utci` | °C | Bröde (2012) | Universal Thermal Climate Index |
| `sensor.ws_wbgt` | °C | — | Wet Bulb Globe Temperature |
| `sensor.ws_air_density` | kg/m³ | — | Air density from temperature and pressure |
| `sensor.ws_specific_humidity` | g/kg | — | Specific humidity |
| `sensor.ws_solar_irradiation_daily` | Wh/m² | — | Daily solar energy accumulation |
| `sensor.ws_net_radiation` | W/m² | FAO-56 | Net radiation |
| `sensor.ws_irrigation_deficit` | mm | — | Irrigation water deficit |
| `sensor.ws_monthly_wind_run` | km | — | Monthly accumulated wind travel |

---

## Optional: Fire Risk (`enable_fire_risk_score`)

| Entity ID | Scale | Description |
|---|---|---|
| `sensor.ws_fire_risk_score` | 1-10 | Display fire danger level mapped from FWI |
| `sensor.ws_fwi` | ≥ 0 | Fire Weather Index (Van Wagner 1987) |
| `sensor.ws_fwi_dsr` | ≥ 0 | Daily Severity Rating |
| `sensor.ws_ffdi` | ≥ 0 | McArthur Fire Danger Index (Australia) |
| `sensor.ws_ffwi` | ≥ 0 | Fosberg Fire Weather Index (US/global) |

FWI sub-components (`enable_fwi_components`, requires fire risk enabled):

| Entity ID | Scale | Description |
|---|---|---|
| `sensor.ws_fwi_ffmc` | 0-101 | Fine Fuel Moisture Code |
| `sensor.ws_fwi_dmc` | ≥ 0 | Duff Moisture Code |
| `sensor.ws_fwi_dc` | ≥ 0 | Drought Code |
| `sensor.ws_fwi_isi` | ≥ 0 | Initial Spread Index |
| `sensor.ws_fwi_bui` | ≥ 0 | Buildup Index |

---

## Optional: Lightning Detection (`enable_lightning`)

| Entity ID | Unit | Description |
|---|---|---|
| `sensor.ws_lightning_count_1h` | strikes | Strikes in the past hour |
| `sensor.ws_lightning_distance` | km | Nearest detected strike |
| `sensor.ws_lightning_rate` | /min | Average strike rate |
| `sensor.ws_lightning_clearance` | min | Minutes since the last strike (safe at ≥30) |
| `sensor.ws_lightning_proximity` | — | `near` / `clear` vs configurable threshold |

Supports WH57, AS3935, and Blitzortung. Blitzortung is auto-discovered if installed.

---

## Optional: Indoor Sensors (`enable_indoor`)

| Entity ID | Description |
|---|---|
| `sensor.ws_indoor_temperature` | Indoor temperature |
| `sensor.ws_indoor_humidity` | Indoor relative humidity |
| `sensor.ws_indoor_co2` | Indoor CO₂ (ppm) |
| `sensor.ws_indoor_temp_delta` | Indoor temperature minus outdoor temperature |
| `sensor.ws_indoor_humidity_delta` | Indoor humidity minus outdoor humidity |
| `sensor.ws_indoor_comfort` | 0-100 composite indoor comfort score |
| `sensor.ws_indoor_room_delta_<room>` | Per-room temperature delta (one per configured room) |

---

## Optional: Degree Days and Leaf Wetness (`enable_degree_days`)

| Entity ID | Unit | Description |
|---|---|---|
| `sensor.ws_hdd_today` | °C·day | Heating degree days today |
| `sensor.ws_hdd_season` | °C·day | Season-to-date HDD |
| `sensor.ws_cdd_today` | °C·day | Cooling degree days today |
| `sensor.ws_cdd_season` | °C·day | Season-to-date CDD |
| `sensor.ws_gdd_today` | °C·day | Growing degree days today |
| `sensor.ws_gdd_season` | °C·day | Season-to-date GDD |
| `sensor.ws_leaf_wetness` | — | `wet` / `dry` |

---

## Optional: Air Quality (`enable_air_quality`)

Free via Open-Meteo. No API key required.

| Entity ID | Unit | Description |
|---|---|---|
| `sensor.ws_air_quality_index` | AQI | US EPA AQI (PM2.5-based) |
| `sensor.ws_no2` | µg/m³ | Nitrogen dioxide |
| `sensor.ws_ozone` | µg/m³ | Ozone |

---

## Optional: Pollen (`enable_pollen`)

Free via Open-Meteo. No API key required.

| Entity ID | Description |
|---|---|
| `sensor.ws_pollen_level` | Highest of grass/tree/weed: None / Low / Medium / High / Very High |
| `sensor.ws_pollen_grass` | Grass pollen IQLA index |
| `sensor.ws_pollen_tree` | Tree pollen IQLA index |
| `sensor.ws_pollen_weed` | Weed pollen IQLA index |

---

## Optional: Moon (`enable_moon`)

Calculated astronomically (Meeus 1998). No API key required.

| Entity ID | Description |
|---|---|
| `sensor.ws_moon` | Phase name with illumination percentage |
| `sensor.ws_moon_illumination` | Illumination percentage (0-100) |

---

## Optional: Solar PV Forecast (`enable_solar_forecast`)

Via forecast.solar (free). Configure your panel peak kWp, azimuth, and tilt.

| Entity ID | Unit | Description |
|---|---|---|
| `sensor.ws_solar_forecast_today` | kWh | Estimated PV generation today |
| `sensor.ws_solar_forecast_tomorrow` | kWh | Estimated PV generation tomorrow |

---

## Optional: Fog and Thunderstorm

| Entity ID | Unit | Description |
|---|---|---|
| `sensor.ws_fog_probability` | % | Dew-point depression fog model |
| `sensor.ws_thunderstorm_risk` | 0-100 | Surface-based thunderstorm risk index |

---

## Optional: Sea Surface Temperature (`enable_sea_temp`)

Via Open-Meteo Marine API (free, no API key).

| Entity ID | Unit | Description |
|---|---|---|
| `sensor.ws_sea_surface_temperature` | °C | SST at your configured coordinates |

---

## Optional: France-only sensors

| Entity ID | Description |
|---|---|
| `sensor.ws_vigilance` | Météo-France Vigilance — `vert` / `jaune` / `orange` / `rouge` |
| `sensor.ws_river_level` | Vigicrues water height at nearest station (m) |

---

## Optional: Station Diagnostics (`enable_diagnostics`)

| Entity ID | Description |
|---|---|
| `sensor.ws_sensor_drift` | Monotonic drift flags from 72h OLS regression |
| `sensor.ws_sensor_consistency` | Cross-sensor physical impossibility flags |
| `sensor.ws_sensor_quality_flags` | Aggregate sensor validation flags |
| `sensor.ws_forecast_skill` | Learned forecast skill score |
| `sensor.ws_solar_lux_factor` | Learned lux → W/m² conversion factor |
| `sensor.ws_climatology_30d` | Rolling 30-day climatology summary |
| `sensor.ws_temperature_anomaly_30d` | Today's mean temperature vs 30-day rolling mean |
| `sensor.ws_rain_anomaly_30d` | Today's rain vs 30-day rolling daily average |
| `sensor.ws_forecast_brier_local` | Brier score for local sensor model (lower is better; requires ≥10 outcomes) |
| `sensor.ws_forecast_brier_api` | Brier score for NWP API model |
| `sensor.ws_forecast_blend_weight_local` | Current learned weight (%) of the local model in the blended probability |
| `sensor.ws_temp_anomaly_90d` | Temperature anomaly (°C) — recent 30d mean vs 90d seasonal baseline (requires ≥60 days of data) |
| `sensor.ws_rain_anomaly_90d` | Precipitation anomaly (mm/d) — recent 30d mean vs 90d seasonal baseline |

---

## Feature: Soil Sensors

Requires: soil moisture or soil temperature source sensors mapped in Configure → Sources, and **Soil Sensors** enabled in Configure → Features.

| Entity ID | Unit | State Class | Description |
|---|---|---|---|
| `sensor.ws_soil_moisture` | % | measurement | Volumetric soil moisture (auto-normalised from 0–1 or 0–100 input) |
| `sensor.ws_soil_temperature` | °C | measurement | Soil temperature |
| `sensor.ws_soil_moisture_deficit` | % | measurement | Deficit from field capacity (40% FC assumed for loam soil) |
| `sensor.ws_irrigation_need` | — | — | Text label: None / Low / Moderate / High / Critical |
| `sensor.ws_irrigation_need_score` | — | measurement | 0–100 irrigation demand score (soil deficit + net ET₀) |

---

## Optional: Network Uploads

Each upload target is independently enabled. Each produces a status sensor.

| Upload target | Config key | Status entity |
|---|---|---|
| Weather Underground | `enable_wunderground` | `sensor.ws_wu_upload_status` |
| Weathercloud | `enable_weathercloud` | `sensor.ws_weathercloud_upload_status` |
| PWSWeather | `enable_pwsweather` | `sensor.ws_pwsweather_upload_status` |
| WOW (UK Met Office) | `enable_wow` | `sensor.ws_wow_upload_status` |
| AWEKAS | `enable_awekas` | `sensor.ws_awekas_upload_status` |
| CWOP / APRS | `enable_cwop` | `sensor.ws_cwop_upload_status` |
| OpenWeatherMap Stations | `enable_owm_stations` | `sensor.ws_owm_stations_upload_status` |
| Windy | `enable_windy` | `sensor.ws_windy_upload_status` |

Status values: `ok`, `error_http`, `error_network`, `error`, `disabled`.
The `last_upload` state attribute holds the timestamp of the last successful upload.

---

## Optional: MQTT Discovery (`enable_mqtt`)

Republishes 70+ derived sensors as MQTT Discovery payloads. Requires the Home Assistant
MQTT integration to be set up.

---

## Other entities

| Entity | Type | Description |
|---|---|---|
| `weather.ws` | weather | Standard HA weather entity with daily forecast |
| `binary_sensor.ws_package_ok` | binary_sensor | On when all required sources are mapped and available |
| `binary_sensor.ws_rain_expected_1h` | binary_sensor | On when rain is expected within 60 minutes (nowcast) |
| `event.ws_rain_event` | event | Fires on rain start and rain stop |
| `event.ws_frost_event` | event | Fires on frost onset and thaw |
| `event.ws_lightning_event` | event | Fires on lightning strike or proximity change |
| `select.ws_graph_range` | select | Dashboard graph time range: 6h / 24h / 3d |
| `sensor.ws_forecast_provider` | sensor | Active forecast provider name |

---

## Configuration entities

All configurable parameters are exposed as entities on the device page. Changes trigger
a coordinator reload automatically.

**Number entities:**

| Entity ID | Unit | Range | Description |
|---|---|---|---|
| `number.ws_thresh_wind_gust` | m/s | 0-50 | Wind gust alert threshold |
| `number.ws_thresh_rain_rate` | mm/h | 0-100 | Rain rate alert threshold |
| `number.ws_thresh_freeze` | °C | -20 to +5 | Freeze warning threshold |
| `number.ws_cal_temp` | °C | ±10 | Temperature calibration offset |
| `number.ws_cal_humidity` | % | ±20 | Humidity calibration offset |
| `number.ws_cal_pressure` | hPa | ±10 | Pressure calibration offset |
| `number.ws_cal_wind` | m/s | ±5 | Wind speed calibration offset |
| `number.ws_staleness_timeout` | s | 60-86400 | Sensor staleness timeout |
| `number.ws_rain_filter_alpha` | — | 0.1-0.99 | Kalman filter smoothing (higher = more smoothing) |
| `number.ws_pressure_trend_window` | h | 1-6 | Pressure trend calculation window |

**Switch entities (feature toggles):**

| Entity ID | Description |
|---|---|
| `switch.ws_enable_display_sensors` | Display-oriented helper sensors |
| `switch.ws_enable_fire_risk_score` | Fire risk score and FWI |
| `switch.ws_enable_fog` | Fog probability |
| `switch.ws_enable_thunderstorm_risk` | Thunderstorm risk index |
| `switch.ws_enable_sea_temp` | Sea surface temperature |
| `switch.ws_enable_wunderground` | Weather Underground upload |
| `switch.ws_enable_air_quality` | Air quality sensors |
| `switch.ws_enable_pollen` | Pollen level sensors |
| `switch.ws_enable_moon` | Moon phase and illumination |
| `switch.ws_enable_solar_forecast` | Solar PV forecast |
| `switch.ws_enable_comfort_indices` | All comfort and heat-stress indices |
