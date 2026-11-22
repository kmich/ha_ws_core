# Sensors Reference

Complete list of entities created by Weather Station Core.

Enabling a feature also enables its default sensors. This applies to existing
entities that Weather Station Core disabled by default, such as Fog Probability.
Entities you disabled yourself remain disabled.

Entity IDs shown use the default prefix `ws`. If you chose a different prefix during
setup, replace `ws` with your prefix. Note: Home Assistant's entity registry preserves
user-chosen or pre-existing entity IDs across upgrades, and renaming the Weather Station
device in Home Assistant can offer to regenerate entity IDs using your UI language
(for example `sensor.wetterstation_frostrisiko` in German); fresh setups assign the
English `sensor.<prefix>_*` IDs directly and localize the display name.

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
| `sensor.ws_rain_total` | mm | total_increasing | **Rainfall Counter.** Current amount from the mapped rain source, in your display units. The value follows that source's accumulation period, such as the current rain event or year. See [rainfall sources](hardware_mapping.md#rainfall-sources) |
| `sensor.ws_rain_rate` | mm/h | measurement | Kalman-filtered rain rate |
| `sensor.ws_dew_point` | °C | measurement | Dew point — Magnus formula (Alduchov & Eskridge 1996) |
| `sensor.ws_illuminance` | lx | measurement | Solar illuminance (if mapped) |
| `sensor.ws_uv_index` | — | measurement | UV index (if mapped) |

## Always-on: Advanced Meteorological

| Entity ID | Unit | Description |
|---|---|---|
| `sensor.ws_feels_like` | °C | Apparent temperature (BOM/Steadman 1994) |
| `sensor.ws_wet_bulb` | °C | Wet-bulb temperature (Stull 2011, ±0.3 °C) |
| `sensor.ws_frost_point` | °C | Frost point with Buck (1981) ice constants below 0 °C; equals the dew point above 0 °C |
| `sensor.ws_frost_risk` | — | Frost risk category (enum): `high` / `probable` / `unlikely` / `no_risk` (state is localized). Compares the lower of the current air temperature and the forecast low for the next 12 h against `thresh_freeze_c` +0 / +2 / +4 °C, with a `+0.5 °C` hysteresis and 2-tick on / 3-tick off debounce. Attributes: `min_temp_c`, `forecast_min_c`, `threshold_c`, `frost_point_c`. See [Frost risk](science.md#frost-risk) |
| `sensor.ws_zambretti_forecast` | — | Zambretti text forecast (26 phrases) |
| `sensor.ws_zambretti_number` | — | Z-number 1-26 |
| `sensor.ws_wind_beaufort` | — | Beaufort scale number (0–12); `description` attribute is localized in all 8 languages |
| `sensor.ws_wind_beaufort_description` | — | Localized Beaufort scale label (`calm` .. `hurricane`, Home Assistant enum sensor translated per user language) |
| `sensor.ws_wind_direction_smooth` | ° | Circular EMA-smoothed wind direction (`alpha = 0.3` per 60 s tick; see [Wind smoothing](science.md#wind-smoothing)) |
| `sensor.ws_wind_quadrant` | — | N / E / S / W compass quadrant derived from the smoothed wind direction (`using_smoothed` attribute indicates whether smoothed or raw direction was used) |
| `sensor.ws_current_condition` | — | 36-condition weather classifier from measured readings. A new condition is reported once it has held for 5 minutes, with immediate reporting for hurricane and severe storm. Clearing after rain requires at least 0.1 mm accumulated in the last 3 hours and a measured light reading |
| `sensor.ws_rain_probability` | % | Local sensor-based rain index |
| `sensor.ws_rain_probability_combined` | % | Brier-score blended local + NWP |
| `sensor.ws_forecast_agreement` | — | `aligned` / `diverging` / `conflict` comparing Zambretti's 6–12 h outlook against the forecast provider's peak `precipitation_probability` over the next 12 h (`comparison_window: hourly_12h`, falling back to `daily`). Reports `unknown` (`provider_missing_precip_prob`) if the provider omits rain probability |
| `sensor.ws_pressure_trend` | — | WMO No. 306 classification + rate |
| `sensor.ws_conditions_summary` | — | Human-readable conditions description (e.g. "Warm · 68% RH · Light rain · SE 12 km/h"). Localized in all 8 supported languages (`en`, `fr`, `de`, `es`, `it`, `nl`, `pl`, `pt`, English fallback). Useful for TTS and Assist. |
| `sensor.ws_rain_last_1h` | mm | Rolling 1-hour rainfall |
| `sensor.ws_rain_last_24h` | mm | Rolling 24-hour rainfall |
| `sensor.ws_rain_today_mm` | mm | Today's accumulated rainfall |

## Always-on: 24h Statistics and Streaks

| Entity ID | Unit | Description |
|---|---|---|
| `sensor.ws_temperature_high_24h` | °C | 24h rolling temperature maximum |
| `sensor.ws_temperature_low_24h` | °C | 24h rolling temperature minimum |
| `sensor.ws_wind_gust_max_24h` | m/s | 24h rolling gust maximum |
| `sensor.ws_dry_streak_days` | days | Consecutive days without measurable rain |
| `sensor.ws_heat_streak_days` | days | Consecutive days above heat threshold |
| `sensor.ws_frost_streak_days` | days | Consecutive days below 0 °C |

## Always-on: ET₀

| Entity ID | Unit | Formula | Description |
|---|---|---|---|
| `sensor.ws_et0_daily` | mm | Hargreaves-Samani 1985 | Daily reference ET₀ (±15-20%) |
| `sensor.ws_et0_penman_monteith` | mm | FAO-56 Penman-Monteith | Activates when solar radiation sensor is mapped (±5-10%) |

Penman–Monteith ET₀ describes the previous completed local calendar day and requires
at least 95% radiation and matching temperature, humidity and wind coverage.
Low radiation on a short or overcast day still counts as coverage. A numeric zero
from the radiation sensor (or optional illuminance fallback) can remain unchanged
overnight: with station coordinates configured, it counts while the sun is below
the horizon, for up to 24 hours after its last report. Daylight zeros and positive
readings still require fresh reports. Missing or unavailable sources remain gaps.
After an incomplete day, the sensor and its repair recover once a sufficiently
covered completed day is available; missing history is not filled retrospectively.

## Always-on: v2.0 additions

| Entity ID | Unit | Description |
|---|---|---|
| `sensor.ws_cloud_base` | m | Cloud base height (lifted condensation level) |
| `sensor.ws_freezing_level` | m | Freezing-level altitude (ISA lapse rate) |
| `sensor.ws_wind_gust_factor` | — | Gust ÷ mean wind speed ratio |
| `sensor.ws_dominant_wind_direction` | ° | Circular-mean wind direction over the rolling 24 h buffer; exposes `variability_deg` (24 h circular standard deviation, 0° steady to >100° shifting) |
| `sensor.ws_wind_direction_variability` | ° | Circular standard deviation of wind direction over the rolling 24 h buffer |
| `sensor.ws_rain_this_week` | mm | Rainfall since Monday |
| `sensor.ws_rain_this_month` | mm | Rainfall since the 1st of the month |
| `sensor.ws_rain_this_year` | mm | Station year-to-date total when mapped; otherwise rainfall since January 1 |
| `sensor.ws_rain_rate_max_24h` | mm/h | Rolling 24h maximum rain rate |

The week, month and year totals are counted live, and at every start ws_core also
reads the rain gauge's recorder statistics. Available counter changes can raise
an undercounted total; a total is never lowered. The statistics only exist if the
gauge's sensor has a supported `state_class`. Missing history, counter resets and
gaps crossing a period boundary can prevent full recovery, so these totals may
cover less than the complete calendar period. A mapped year-to-date source is
preferred for the station's annual total.

Gust records reject new implausible readings, but existing records are preserved.
Legacy records do not identify their source observation, and hourly statistics
alone cannot safely establish that a stored record should be lowered.

Source freshness follows the latest report, including unchanged reports. During
calm conditions, a zero wind speed may be corroborated by a zero gust reported
within 10 minutes and the configured staleness timeout. Constant pressure with
fresh reports does not by itself indicate a failed sensor. Missing, unavailable
and genuinely stale sources continue to affect station health and data quality.

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

## Pattern Forecast (`enable_pattern_forecast`) {#pattern-forecast}

Off by default. Learns from your own station; see the [Pattern Forecast guide](guides/pattern_forecast.md).
Probability sensors are `unknown` (never 0 %) while a forecast is `collecting` or `paused`.

| Entity ID | State | Created |
|---|---|---|
| `sensor.ws_pattern_rain_1h` | % (0-100), measurement | Always |
| `sensor.ws_pattern_rain_3h` | % | Always |
| `sensor.ws_pattern_rain_6h` | % | Always |
| `sensor.ws_pattern_frost_12h` | % | Always |
| `sensor.ws_pattern_heat_24h` | % | Always |
| `sensor.ws_pattern_gust_3h` | % | Always |
| `sensor.ws_pattern_storm_3h` | % | With a mapped lightning detector, or with the internet lightning option (the name then ends in "(internet lightning)"; the entity ID does not change) |
| `sensor.ws_pattern_forecast_status` | `collecting` / `waiting` / `learning` / `active` (`active` = at least one forecast is `skilled`) | Always |
| `sensor.ws_pattern_forecast_skill` | Number of forecasts currently `skilled` (diagnostic, disabled by default) | Always |

**Probability sensor attributes** (the same on every forecast):

| Attribute | Meaning |
|---|---|
| `target`, `horizon_h` | `rain` / `frost` / `heat` / `gust` / `storm` and the window in hours |
| `data_source` | `local`, or `internet` (storm only, with the opt-in) |
| `threshold`, `threshold_unit` | The threshold that counts as "it happened", in your display units |
| `maturity` | `collecting` / `learning` / `skilled` / `degraded` / `paused`. Gate automations on `skilled` |
| `progress_pct` | Progress out of `collecting` (only while collecting) |
| `brier_skill` | Skill versus the station's usual rate over the last 52 weeks (0 = no better, 1 = perfect) |
| `usual_rate` | The station's usual chance for this event (30-day running rate) |
| `issued_at`, `valid_until` | When the forecast was issued and when its window ends |
| `top_factors` | Up to three `{factor, effect}` entries, deterministic keys |
| `samples_trained` | Number of examples the model has learned from |
| `events_live`, `events_from_history` | Live events observed since enabling Pattern Forecast, and events replayed from recorder statistics |
| `events_required` | Events needed for the next milestone: `5` (live + history) while `collecting`, or `15` for rain and `10` for frost/heat/gust/storm (live events only) once in `learning` |
| `reason`, `explanation` | Why there is no number right now while `collecting` or `paused` (for example `waiting_for:dp_24h`) |

**Status sensor attributes:** `explanation` (summary of the overall status), `per_target` (maturity, progress, live events, events from
history, events required for the current stage, skill, and a plain-text `explanation` of what each target needs next), `history_learn` (learning-from-history result per
forecast), `internet_inputs` (empty, or `[storm_3h]`), `last_trained_at`, `storm_target`.

**Skill sensor attributes:** `per_target`, each with `brier`, `brier_usual`,
`brier_persistence`, `brier_heuristic`, `bss`, `bss_vs_persistence`, `n_scored`, `events`
and the `reliability` bins.

Services: `ws_core.reset_learning_state` accepts target `pattern_forecast`;
`ws_core.export_learning_state` logs a Pattern Forecast summary.

---

## Optional: Comfort Indices (`enable_comfort_indices`)

All 23 sensors are created when the feature is enabled, except the solar-radiation
ones below. Clearness index, cloud cover and the THSW index are only created when a
solar radiation sensor (W/m²) is mapped. Solar energy, peak sun hours and net
radiation (and Penman-Monteith ET₀) are created with a solar radiation sensor, or
with the illuminance fallback and a lux sensor, as estimates. Entries for these
sensors left by earlier versions on stations without such a sensor are removed
automatically, and `sensor.ws_data_status` lists them under `not_on_this_station`.

**Feels-like sensors outside their range.** Heat index, THW, THSW, wind chill and
humidex only apply in certain weather. Outside it they show the air temperature,
as Davis and NWS stations do, with `formula_applies: false` and an `explanation`
attribute; inside it, `formula_applies` is `true`. Before 3.0.0 they showed
`unknown`. MQTT and exports still send no value when the formula does not apply.

| Entity ID | Unit | Formula / reference | Notes |
|---|---|---|---|
| `sensor.ws_heat_index` | °C | Rothfusz (1990) | Applies when T ≥ 27 °C and RH ≥ 40%; air temperature otherwise |
| `sensor.ws_wind_chill` | °C | WMO/NWS (2001) | Applies when T ≤ 10 °C and wind > 1.34 m/s; air temperature otherwise |
| `sensor.ws_humidex` | °C | Masterton & Richardson (1979) | Applies when it exceeds the air temperature; air temperature otherwise |
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
| `sensor.ws_max_solar_radiation` | W/m² | — | Clear-sky solar radiation estimate |
| `sensor.ws_solar_energy_today` | Wh/m² | — | Daily solar energy accumulation |
| `sensor.ws_peak_sun_hours` | h | — | Peak sun hours from daily solar energy |
| `sensor.ws_net_radiation` | W/m² | FAO-56 | Net radiation |
| `sensor.ws_irrigation_deficit` | mm | — | Irrigation water deficit |
| `sensor.ws_wind_run_month` | km | — | Monthly accumulated wind travel |

---

## Optional: Fire Risk (`enable_fire_risk_score`)

| Entity ID | Scale | Description |
|---|---|---|
| `sensor.ws_fire_risk_score` | 1-10 | Display fire danger level mapped from FWI |
| `sensor.ws_fwi` | ≥ 0 | Fire Weather Index (Van Wagner 1987) |
| `sensor.ws_fwi_dsr` | ≥ 0 | Daily Severity Rating |
| `sensor.ws_ffdi` | ≥ 0 | McArthur Fire Danger Index (Australia) |
| `sensor.ws_ffwi` | ≥ 0 | Fosberg Fire Weather Index (US/global) |

FWI sub-components (`enable_fwi_components`) run the FWI calculation even when the primary fire risk display is off:

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
| `sensor.ws_lightning_clearance` | min | Minutes since the last strike (safe at ≥30); keeps counting across restarts from the last strike the lightning event recorded |
| `sensor.ws_lightning_proximity` | — | `near` / `clear` vs configurable threshold; `clear` when the distance source reports no strike, `unknown` while it is unavailable |

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
| `sensor.ws_indoor_room_delta_<room>` | Per-room indoor/outdoor temperature delta (one per room with a temperature sensor) |
| `sensor.ws_indoor_room_humidity_<room>` | Per-room indoor humidity, with outdoor delta attribute (rooms with a humidity sensor) |
| `sensor.ws_indoor_room_absolute_humidity_<room>` | Per-room absolute humidity in g/m³ (rooms with both temperature and humidity sensors) |
| `sensor.ws_indoor_room_co2_<room>` | Per-room CO₂ in ppm (rooms with a CO₂ sensor) |
| `sensor.ws_indoor_room_comfort_<room>` | Per-room 0-100 composite comfort score (any room with at least one sensor) |

Indoor rooms are configured under **Configure → Indoor Rooms**, where each room is given a name and any combination of temperature, humidity and CO₂ sensors.

Room absolute humidity uses that room's temperature and relative humidity, with temperature converted to Celsius before calculation. It does not require Comfort Indices to be enabled. The value is unknown while either source is missing or unavailable. For ventilation automations, compare it with outdoor `sensor.ws_absolute_humidity` (enable Comfort Indices and the outdoor entity).

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

Degree days are shown in °F·day when the temperature unit is °F (1 °C·day = 1.8 °F·day). The base temperatures stay 18 °C (64.4 °F) for heating and cooling and 10 °C (50 °F) for growing.

Seasons run 1 January - 31 December. Each completed day's total is added to its
season at local midnight (including a day that ended while Home Assistant was stopped),
and all three season totals reset on 1 January.

---

## Optional: Air Quality (`enable_air_quality`)

Free via Open-Meteo. No API key required.

| Entity ID | Unit | Description |
|---|---|---|
| `sensor.ws_air_quality_index` | AQI | Air Quality Index (`aqi_scale`: `auto` selects European EAQI 0–100+ in Europe and US EPA AQI 0–500 elsewhere). Exposes `scale`, `level`, `color`, `source`, `missing_pollutants` for the local estimate, and pollutant concentrations |
| `sensor.ws_pm2_5` | µg/m³ | Fine particulate matter (PM2.5) |
| `sensor.ws_pm10` | µg/m³ | Coarse particulate matter (PM10) |
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

### Local PV forecast (v3.0.0, optional)

Pick the PV energy meters that count your solar production (the same kWh meters as in the Energy dashboard, one or several) under **Configure → Features & Diagnostics → Solar Forecast Settings**. ws_core learns a forecast for your installation:

- It fetches Open-Meteo's hourly irradiance forecast on the plane of your panels (your tilt and azimuth; free, no key).
- From your meters' long-term statistics it learns how many kWh your system really produces per kWh/m² of that irradiance (the **site factor**). Shading, inverter losses, soiling and a wrong kWp setting are all absorbed by it.
- On the first start it reads up to 92 days of history from the recorder and Open-Meteo, so a system with existing statistics is calibrated right away. Without history it starts from your peak power (kWp × 0.80) and refits as days come in.

| Entity ID | Unit | Description |
|---|---|---|
| `sensor.ws_solar_local_forecast_today` | kWh | Local PV forecast for today |
| `sensor.ws_solar_local_forecast_tomorrow` | kWh | Local PV forecast for tomorrow |
| `sensor.ws_solar_local_forecast_remaining_today` | kWh | Energy still expected today (rest of the current hour plus later hours) |

Attributes of `sensor.ws_solar_local_forecast_today`:

| Attribute | Meaning |
|---|---|
| `model_status` | `prior` (from your kWp only), `learning` (fewer than 7 usable days, blended with the prior) or `trained` |
| `days_used` | Days in the last 60 that went into the fit |
| `days_rejected` | Days with complete data whose yield fell outside the fitting band |
| `site_factor` / `prior_site_factor` | Learned and kWp-based kWh per kWh/m² of plane irradiance |
| `skill_local` / `skill_forecast_solar` | Day-ahead error over the last 30 days for this forecast and for forecast.solar: `days`, `mae_kwh`, `bias_kwh`, `correlation` (shown from 5 days) |
| `hourly` | Hourly forecast for today and tomorrow (`start`, `kwh`). Home Assistant Recorder excludes this attribute |
| `meter_problem` / `last_error` | Problems reading usable meter data or refreshing the irradiance forecast |

Skill compares the last forecast made **before** each day with that day's measured yield. The model scores both forecasts on shared days when at least five are available. With fewer shared days each forecast is scored on its own qualifying dates, so the two scores can cover different days. The day-ahead history starts when the feature is turned on.

Notes and limits:

- The meters need long-term statistics (`state_class` `total` or `total_increasing`, unit Wh, kWh or MWh). Lifetime and daily-reset counters both work.
- Each selected meter must cover every modeled hour with at least 25 Wh/m² of panel-plane irradiance. Meters that go offline at night can still qualify. Incomplete productive hours exclude that day. Data Status reports meter statistics problems. A failed history backfill is retried after six hours while short forecast refreshes continue.
- The fit uses least squares on days near the typical yield of the highest-producing fifth of recent days, using at least seven days for that reference when available. This helps when a majority of days are curtailed or snow-covered if enough productive days remain. Consistently curtailed systems can learn a lower factor. With a mix of heavily curtailed and productive days, all days can fall outside the fitting band. In that case the model uses the kWp-based prior and reports the number of rejected days.
- If the irradiance refresh fails, the forecast may keep its last values until local midnight. Check `updated_at` for the last successful refresh and `last_error` for the failure.
- Clearing the PV meter list removes the three Local PV Forecast entities on reload.
- One tilt and azimuth are used for the whole system. For arrays facing different ways, set the orientation of the largest array; the site factor absorbs the rest, but the hourly shape follows that one orientation.
- Uses the forecast latitude and longitude. Removing the integration deletes the learned data (`.storage/ws_core_<entry>_solar_local`).

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
| `sensor.ws_river_flow` | Vigicrues water flow at nearest station (m³/s, converted from Hub'Eau's L/s) |

---

## Always-on: Alerts {#alerts}

Always created (`EntityCategory.DIAGNOSTIC`):

| Entity ID | Description |
|---|---|
| `sensor.ws_alert_state` | Overall alert severity (`clear`, `advisory`, or `warning`). Exposes `message`, `detail_message`, `active_alerts`, `alert_count`, `icon`, `color` |
| `sensor.ws_alert_message` | Stable localized alert title(s) (e.g. `"Freeze risk"`, or multiple active alerts joined with `" \| "`, or `"All clear"` when clear). Live measurements are exposed in `detail_message` and `active_alerts` attributes so state history does not flap on every reading |

**Triggers, thresholds, hysteresis & debounce:**

| Alert | Severity | Config option | Default | Hysteresis deadband to clear |
|---|---|---|---|---|
| Wind | `warning` | `thresh_wind_gust_ms` (`number.ws_thresh_wind_gust`) | `17.0 m/s` (61.2 km/h) | Drops below `threshold - 1.5 m/s` |
| Rain | `warning` | `thresh_rain_rate_mmph` (`number.ws_thresh_rain_rate`) | `10.0 mm/h` | Drops below `threshold - 1.0 mm/h` |
| Freeze | `advisory` | `thresh_freeze_c` (`number.ws_thresh_freeze`) | `0.0 °C` | Rises above `threshold + 0.5 °C` |
| Lightning | `warning` | Nearby strike / `lightning_proximity_km` | Immediate, 30 min hold | Clears 30 min after last nearby strike |

- **Debounce:** Wind, rain and freeze alerts advance on the fixed **60-second tick** and require **2 consecutive ticks** meeting the trigger condition to fire (`ALERT_DEBOUNCE_ON_TICKS = 2`) and **3 consecutive ticks** clear of the hysteresis deadband to turn off (`ALERT_DEBOUNCE_OFF_TICKS = 3`). Lightning triggers immediately with no onset delay.
- **Combining:** `sensor.ws_alert_state` takes the highest active severity (`warning` beats `advisory`). Active alert titles are joined with `" | "` in `sensor.ws_alert_message`, and live formatted values are joined in `detail_message` and listed per alert in `active_alerts`.

**Freeze alert vs `sensor.ws_frost_risk`:** the two answer different questions.

- The **freeze alert** (`sensor.ws_alert_state` = `advisory`, `sensor.ws_alert_message` = "Freeze risk") fires only when the **measured** air temperature is at or below `thresh_freeze_c` (`number.ws_thresh_freeze`, default `0.0 °C`).
- **`sensor.ws_frost_risk`** is an early-warning indicator for ground and grass frost. It uses the lower of the current air temperature and the forecast low over the next 12 hours, so it can rise before the air itself reaches the threshold:

  | State | Lowest temperature considered |
  |---|---|
  | `high` | ≤ `thresh_freeze_c` |
  | `probable` | ≤ `thresh_freeze_c` + 2 °C |
  | `unlikely` | ≤ `thresh_freeze_c` + 4 °C |
  | `no_risk` | above `thresh_freeze_c` + 4 °C |

  It does **not** look at frost point, humidity, wind or cloud cover. The frost point is available separately (`sensor.ws_frost_point`, and the `frost_point_c` attribute). Like the alerts, it needs 2 ticks to step up and 3 ticks to step down, and only steps down once the temperature is more than 0.5 °C above the boundary. See [Frost risk](science.md#frost-risk).

---

## Always-on: Data Status {#data-status}

`sensor.ws_data_status` answers "is an empty sensor a problem?" in one place. Its
state is **OK** or **Needs attention**.

- **Needs attention** reports station-source problems that last more than five minutes,
  as well as problems reading usable PV meter history. Missing entities and stale
  readings can also raise Repairs issues.
- The `summary` attribute says what is going on in one sentence.
- `needs_attention` lists the problems.
- `waiting` lists every sensor that is empty for a normal reason, with that reason.
  Examples: no rain expected, no lightning strike yet, Pattern Forecast still
  collecting data, no frost event yet.
- `not_on_this_station` lists features this station's sensors or settings cannot
  provide, and what would make them work. Examples: clearness index without a W/m²
  solar sensor, or lightning with no detector and no Blitzortung integration.

Derived sensors covered by Data Status also carry `reason` and `explanation` attributes when empty, plus a
short `status_text` such as "No rain expected", "No recent strike" or "Learning (2 of 5
events)". Home Assistant only allows numbers in a sensor with a unit and shows
"Unknown" when there is none, so the bundled dashboards show `status_text` there
instead. To do the same on your own dashboard, use an entities-card row of
`type: attribute` with `attribute: status_text` behind a conditional on
`state: unknown`.

---

## Optional: Station Diagnostics (`enable_diagnostics`)

| Entity ID | Description |
|---|---|
| `sensor.ws_sensor_drift` | Monotonic drift flags from 72h OLS regression (needs 24h of data) |
| `sensor.ws_sensor_consistency` | Cross-sensor physical impossibility flags |
| `sensor.ws_sensor_quality_flags` | Aggregate sensor validation flags |
| `sensor.ws_forecast_skill` | Learned forecast skill score |
| `sensor.ws_solar_lux_factor` | Learned lux → W/m² conversion factor |
| `sensor.ws_climatology_30d` | Rolling 30-day climatology summary |
| `sensor.ws_temperature_anomaly_30d` | Today's mean temperature vs 30-day rolling mean |
| `sensor.ws_rain_anomaly_30d` | Today's rain vs 30-day rolling daily average |
| `sensor.ws_frost_risk` | Frost risk (`no_risk`, `unlikely`, `probable`, `high`); see [Alerts](#alerts) |
| `sensor.ws_forecast_brier_local` | Brier score for local sensor model (lower is better; requires ≥10 outcomes) |
| `sensor.ws_forecast_brier_api` | Brier score for the forecast provider, scored on its highest hourly probability over each 6-hour window ([method](science.md#rain-blend)) |
| `sensor.ws_forecast_blend_weight_local` | Current learned weight (%) of the local model in the blended probability |
| `sensor.ws_temp_anomaly_90d` | Temperature anomaly (°C) — recent 30d mean vs 90d seasonal baseline (requires ≥60 days of data) |
| `sensor.ws_rain_anomaly_90d` | Precipitation anomaly (mm/d) — recent 30d mean vs 90d seasonal baseline |
| `sensor.ws_auto_calibration` | Adaptive calibration status (`learning`/`stable`/`adjusted`) — requires **Feature: Adaptive Sensor Calibration** |
| `sensor.ws_temp_high_normal` | Historical normal high for today's calendar date (~10y average) — requires **Feature: Historical Climate Normals** |
| `sensor.ws_temp_low_normal` | Historical normal low for today's calendar date |
| `sensor.ws_rain_normal` | Historical normal rainfall for today's calendar date |
| `sensor.ws_temp_anomaly_normal` | Today's temperature vs. the historical normal for this specific date — distinct from `_anomaly_30d`/`_90d` (self-referential vs. this station's own recent average) |
| `sensor.ws_rain_anomaly_normal` | Today's rain vs. the historical normal for this specific date |

---

## Feature: Soil Sensors

Requires: soil moisture or soil temperature source sensors mapped in Configure → Sensor Sources, and **Soil Sensors** enabled in Configure → Features & Diagnostics.

| Entity ID | Unit | State Class | Description |
|---|---|---|---|
| `sensor.ws_soil_moisture_pct` | % | measurement | Volumetric soil moisture (respects entity unit or the `soil_moisture_unit` option in Optional Sources) |
| `sensor.ws_soil_temp` | °C | measurement | Soil temperature |
| `sensor.ws_soil_moisture_deficit_pct` | % | measurement | Deficit from field capacity (40% FC assumed for loam soil) |
| `sensor.ws_irrigation_need` | — | — | Text label: None / Low / Moderate / High / Critical |
| `sensor.ws_irrigation_need_score` | — | measurement | 0–100 irrigation demand score (soil deficit + net ET₀) |

---

## Feature: Snow (`enable_snow`)

Off by default. No station-agnostic snow gauge exists, so this is a heuristic
estimate from temperature, humidity, and your existing rain rate - not a
measurement. Precipitation phase is classified from wet-bulb temperature;
snow accumulation converts the liquid-equivalent rain rate via a
temperature-dependent snow-to-liquid ratio (colder = fluffier, higher ratio).
Never touches the existing rain sensors - it's a fully separate, additive
estimate.

| Entity ID | Unit | State Class | Description |
|---|---|---|---|
| `sensor.ws_snow_phase` | — | — | `snow` / `sleet` / `rain` / `none` |
| `binary_sensor.ws_snow_falling` | — | — | On when the phase is `snow` |
| `sensor.ws_snow_rate` | cm/h (or in/h) | measurement | Estimated current snowfall rate |
| `sensor.ws_snow_today` | cm (or in) | total_increasing | Estimated new snow today, resets at local midnight |
| `sensor.ws_snow_this_month` | cm (or in) | total_increasing | Resets on the 1st |
| `sensor.ws_snow_this_year` | cm (or in) | total_increasing | Resets Jan 1st |
| `sensor.ws_snow_record_day` | cm (or in) | measurement | Snowiest single day ever recorded; `date` attribute shows when. Never resets, survives restarts |

---

## Optional: Network Uploads

Each upload target is independently enabled. Each produces a status sensor.

| Upload target | Config key | Status entity |
|---|---|---|
| Weather Underground | `enable_wunderground` | `sensor.ws_wu_upload_status` |
| Weathercloud | `enable_weathercloud` | `sensor.ws_wc_upload_status` |
| PWSWeather | `enable_pwsweather` | `sensor.ws_pws_upload_status` |
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

- Discovery configs go to `<discovery prefix>/sensor/ws_core_<prefix>_<sensor>/config`
  (retained) and values to `<state prefix>/<prefix>/<sensor>/state`. The defaults are
  `homeassistant` and `ws_core`.
- Discovery is sent about 15 seconds after startup. If the broker is not connected yet,
  it is sent with the next state update instead.
- On a clean shutdown the discovery configs are removed again.
- When MQTT republishing is off, ws_core clears its own discovery configs from the broker
  a minute after startup if the MQTT integration is connected. This removes configs left
  by older versions or from before you turned the feature off, which Home Assistant would
  otherwise read at every start. Only the `ws_core_<prefix>_*` topics are touched.
- On Home Assistant versions without the `wind_direction` device class (2025.1 and
  older), Wind Direction and Dominant Wind Direction are published as plain ° sensors.

---

## Other entities

| Entity | Type | Description |
|---|---|---|
| `weather.ws` | weather | Standard HA weather entity with daily and hourly forecast |
| `binary_sensor.ws_package_ok` | binary_sensor | On when all required sources are mapped and available |
| `binary_sensor.ws_rain_expected_1h` | binary_sensor | On when nowcast predicts rain in the next 60 minutes (or when the local gauge currently measures ≥ 0.1 mm/h while nowcast is unavailable); `unknown` with `status_text` when nowcast is unavailable and the station is dry |
| `event.ws_rain_event` | event | Fires on rain start and rain stop |
| `event.ws_frost_event` | event | Fires on frost onset and thaw |
| `event.ws_lightning_event` | event | Fires on lightning strike or proximity change |
| `select.ws_graph_range` | select | Dashboard graph time range: 6h / 24h / 3d |
| `sensor.ws_forecast_provider` | sensor | Active forecast provider name (`forecast_status` attribute shows `ok` / `degraded` / `local_only`) |

**Forecast provider coverage (`weather.ws`):**

- `ha_weather_entity` retains the source entity's full forecast horizon and forwards extra fields when supplied (`cloud_coverage`, `humidity`, `pressure`, `visibility`, `uv_index`, `wind_bearing`). Visibility uses the WS weather entity's selected units. The provider preserves HA condition strings and source attribution and derives missing hourly `apparent_temperature` when temperature, humidity and wind speed are available.
- Fields a source entity or provider omits (for example, DWD does not publish `precipitation_probability`, Met.no omits `wind_gust_speed`, NWS omits `wind_gust_speed` and `cloud_coverage`) remain `null` in the forecast; `sensor.ws_forecast_agreement` reports `unknown` (`provider_missing_precip_prob`) when precipitation probability is absent.

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
| `switch.ws_enable_neighbor_qc` | Hourly sensor sanity check against Open-Meteo (on by default; sends your coordinates) |
| `switch.ws_enable_pattern_forecast` | Pattern Forecast: learned chance of rain, frost, heat, gusts and storms (off by default; local) |

---

## Optional: Weather Windows {#weather-windows}

Off by default (`enable_weather_windows = false`). Configure under **Settings → Devices & Services → Weather Station Core → Configure → Decision Engine & Weather Windows**.

Entities are created **only** when `enable_weather_windows` is turned on, and only for the selected profiles (`outdoor_drying`, `garden_work`, and/or `custom`). Disabling the feature or unchecking a profile removes its disabled entities from Home Assistant's entity registry on reload.

### Profiles and Entities

For each enabled profile `<pid>` (`outdoor_drying`, `garden_work`, `custom`):

| Entity ID | Device Class | Description |
|---|---|---|
| `sensor.ws_window_<pid>_status` | `enum` | Current suitability state: `suitable_now`, `window_upcoming`, `unsuitable`, or `unknown` |
| `sensor.ws_window_<pid>_next_start` | `timestamp` | Start time of the active or next suitable interval (`unknown` if none) |
| `sensor.ws_window_<pid>_next_end` | `timestamp` | End time of the active or next suitable interval (`unknown` if none) |

Default profile criteria (all numeric custom limits accept °C/°F, mm/in, and km/h/mph/m/s/kn matching station units):

| Profile | Min Duration | Rain Limits | Temp (°C) | Humidity | Wind / Gust (km/h) | Daylight | Clouds |
|---|---|---|---|---|---|---|---|
| `outdoor_drying` | 2 h | prob ≤ 20%, mm = 0 | 10 to 38 | ≤ 75% | wind 3 to 35, gust ≤ 45 | Required | ≤ 80% |
| `garden_work` | 2 h | prob ≤ 30%, mm ≤ 0.1 | 8 to 32 | ≤ 90% | wind ≤ 25, gust ≤ 40 | Required | not checked |
| `custom` | 2 h | prob ≤ 25%, mm = 0 | 12 to 30 | ≤ 80% | wind ≤ 30, gust ≤ 50 | Not required | not checked |

### Attributes, Live Station Checks & Provider Coverage

- `sensor.ws_window_<pid>_status` exposes localized `reasons`, stable `reason_codes`, `not_assessed_by_provider`, `substituted_by`, `gust_unavailable`, `is_truncated`, and `horizon_hours`. The action `ws_core.get_weather_windows` also returns `duration_h` for the full window and `remaining_h` for the time still available.
- **Live station checks:** Active station rainfall blocks the current hour. Gusts above the limit for three minutes block the window until five minutes of observed calm. An unavailable gust reading preserves an active hold for up to 30 minutes after the last valid reading.
- **Interrupted windows:** When live rain or a sustained gust blocks a window that the forecast says is open now, the status becomes `unsuitable` with `window_interrupted` plus the live reason, and `next_start` / `next_end` keep the forecast window's original times. The rest of the window stays visible and the notification blueprint does not re-fire for it.
- **Action calls:** `ws_core.get_weather_windows` reads the live gust hold but never starts, resets or advances it, so calling the action (even with custom limits) does not change the sensors.
- **Horizon:** windows are evaluated up to 24 hours ahead, ending on the last full local hour, so a window that runs to the end of the horizon keeps a stable end time. For that reason the minimum duration is limited to 1 to 23 hours.
- **What "suitable now" means:** a window must meet the minimum duration when it opens. Once open, it stays `suitable_now` until the end while conditions hold, even when less than the minimum duration remains. Use the action's `remaining_h` if an automation needs to decide whether there is enough time to start.
- **`next_start` of an open window** is the time the window opened, and stays fixed while it remains open. After a Home Assistant restart it shows the start of the current hour until the window ends.
- **Forecast availability and resolution:** an unavailable forecast reports `unknown` with `forecast_unavailable`. Coarse and sub-hourly data report `forecast_too_coarse` and `forecast_too_fine`, respectively.
- **Provider capability handling:** Limits that depend on a missing forecast field appear in `not_assessed_by_provider`. If the provider supplies one rain signal, Weather Windows uses its configured limit. If only the missing signal has a limit, the available signal must be zero and the substitution appears in `substituted_by`. Gaps can report `unknown` with `missing_data`. A passing interval shorter than the minimum can report `unsuitable` with `short_window`. A forecast too short to tell reports `unknown` with `insufficient_horizon`.

---

## Actions (Services) {#actions}

| Service | Response | Description |
|---|---|---|
| `ws_core.get_weather_windows` | `SupportsResponse.ONLY` | Evaluates enabled profiles (or a chosen `profile_id` with optional custom `limits` dict) across the next 24 hours; raises `ServiceValidationError` on unknown `entry_id`, unknown `profile_id`, or invalid limits |
| `ws_core.get_station_summary` | `SupportsResponse.ONLY` | Deterministic JSON-serializable snapshot of live observations, 24h extremes, alerts, forecast validity (`hourly_horizon_h`, `capabilities`), Pattern Forecast maturity, and Weather Windows (`not_assessed_by_provider` when present) for Home Assistant Assist and scripts |
| `ws_core.export_learning_state` | `SupportsResponse.OPTIONAL` | Returns a compact JSON summary (or complete raw model weights when `full: true` is passed), or writes to the INFO log when called without `return_response` |
| `ws_core.apply_calibration` | None | Updates calibration offsets (`cal_temp_c`, `cal_humidity`, `cal_pressure_hpa`, `cal_wind_ms`) and triggers a reload |
| `ws_core.reset_learning_state` | None | Resets `all`, `solar`, `forecast`, `streaks`, or `pattern_forecast` learning state |
| `ws_core.reset_rain_baseline` | None | Resets the internal cumulative precipitation baseline used for rain rate filtering |
