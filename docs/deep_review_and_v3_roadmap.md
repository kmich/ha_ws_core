# Weather Station Core (`ws_core`): Deep Code Audit, Ecosystem Comparison & v3.0 Roadmap

> **Review snapshot:** Current branch `HEAD` (`v2.13.14`), cross-checked against `origin/main` (`v2.13.17`, commit `915cf66`) and [docs/v3-review-2026-11-17.md](v3-review-2026-11-17.md).

---

## Executive Summary

`ws_core` already has strong engineering fundamentals: hardware-agnostic entity normalization, 8 forecast providers behind a shared adapter abstraction, persistent learning and daily accumulators, prequential scoring in Pattern Forecast, recursive secret/coordinate redaction in diagnostics, and extensive unit tests.

However, a deep review of the codebase alongside leading Home Assistant and personal weather station (PWS) ecosystems (**Thermal Comfort**, **Smart Irrigation**, **Mold Indicator**, **MeteoAlarm**, **WeatherFlow Forecast**, **WeeWX**, and **CumulusMX**) shows two things:

1. **Significant scientific, physical, provider, and state-management bugs remain** in the calculation engine, learning pipeline, forecast adapters, uploaders, and options flow that undermine trust if left unresolved.
2. **To justify a true v3.0**, `ws_core` should evolve from a **passive 240+ sensor calculator** into an **active Weather Decision & Microclimate Engine**—combining local observations, Pattern Forecast, hourly forecasts, room psychrometrics, soil water balance, and Home Assistant 2026 platform primitives (`SupportsResponse` services, `CalendarEntity`, multi-device grouping, interactive `RepairsFlow`, and menu-based options).

---

## Part 1: Deep Code Review — Confirmed Bugs & Technical Debt

The six reliability issues previously documented in [v3-review-2026-11-17.md](v3-review-2026-11-17.md) (expired daily forecast cache in rain blend, soil moisture `<= 1.0` fraction discontinuity, forecast retry backoff timestamp, `weather.py` nowcast slot index blending, missing rain rate firing `stopped` in `event.py`, and `async_unload_entry` teardown order) remain open unless fixed separately.

Below are the additional critical, high, and medium findings uncovered by auditing the calculation engine, learning state, providers, uploaders, platforms, and config flow.

### A. Scientific, Meteorological & Learning Bugs

| Severity | Area | Location | Issue & Impact |
|---|---|---|---|
| **Critical** | Neighbor QC & Auto-Calibration Pressure | `custom_components/ws_core/coordinator.py:3129`, `3159-3160`, `3225-3242` | Compares Open-Meteo `current.surface_pressure` (pressure at the coarse NWP grid elevation) against `KEY_NORM_PRESSURE_HPA` (station pressure). In hilly/mountainous terrain, a 120–150 m grid-elevation mismatch (~15–18 hPa) causes Neighbor QC to permanently flag barometer errors and causes `enable_auto_calibration` to actively corrupt `cal_pressure_hpa` toward the ±10 hPa clamp. **Fix:** fetch `pressure_msl` and compare against `KEY_SEA_LEVEL_PRESSURE_HPA`. |
| **Critical** | Pattern Forecast Replay Solar Standardization | `custom_components/ws_core/pattern_forecast.py:185`, `1512-1524` | During recorder history `replay()`, `cloud_deficit`, `solar_ok`, `last_day_clearness`, and `last_day_clearness_ok` are hardcoded to `0.0`, but `REPLAY_MASKED_FEATURES` (`line 185`) only masks `{"wind_u", "wind_v"}`. `self.std.update()` ingests up to 8,760 consecutive zeros, collapsing mean and variance to `0.0`. On live daytime ticks, `std.z()` divides by `PATTERN_STD_FLOOR = 0.01` and clips solar z-scores to `+5.0` for weeks. **Fix:** include all 4 solar features in `REPLAY_MASKED_FEATURES`. |
| **High** | High-Latitude `math.acos` Crash (`\|lat\| >= 66.5°`) | `custom_components/ws_core/algorithms.py:1440`, `2379`; `coordinator.py:2766`, `5030` | `extraterrestrial_radiation_mj` and `calculate_max_solar_radiation` pass `-tan(phi) * tan(delta)` to `math.acos()` without clamping to `[-1.0, 1.0]`. Above the Arctic/Antarctic circle during polar day/night, `math.acos` raises an unhandled `ValueError: math domain error`, crashing `coordinator._compute()` in `calculate_max_solar_radiation` and `et0_penman_monteith`, and causing `et0_hargreaves` (`except Exception: return 0.0`) to return `0.0` during 24-hour summer daylight. |
| **High** | Clear-Sky Solar & Net Radiation Unit Mismatch | `custom_components/ws_core/algorithms.py:2366-2432`; `coordinator.py:2766-2768`, `2892-2894` | `calculate_max_solar_radiation` divides daily clear-sky energy $R_{so}$ ($\text{MJ m}^{-2}\text{ day}^{-1}$) by `86400 s/day`, producing a **24-hour average** (~280–340 W/m² including night) rather than instantaneous clear-sky irradiance (~900–1,000 W/m²). Passing that 24h mean as `max_solar_wm2` into `calculate_net_radiation` alongside instantaneous `solar_rad` (~800 W/m²) causes `ratio = min(1.0, solar_wm2 / max_solar_wm2)` to saturate at `1.0` even under heavy cloud cover. Additionally, nighttime `solar_wm2 <= 1.0` sets `cloud_term = 1.0` (100% clear sky every night). |
| **High** | Learned Lux Factor Projection & Dead Output | `custom_components/ws_core/learning_state.py:278-316`; `coordinator.py:4802-4827`, `5580` | `update_solar_lux_factor` computes Meinel Direct Normal Irradiance (`1353 * 0.7 ** (am**0.678)`) without multiplying by `cos_z` for a horizontal sensor plane, has no clear-sky cloud check despite the comment at `coordinator.py:4811`, and its learned `solar_lux_factor` is **never used**: `_get_solar_radiation_for_et0` (`coordinator.py:5580`) hardcodes `LUX_TO_WM2_FACTOR = 0.0079`. |
| **High** | Pattern Forecast Nighttime `cloud_deficit`, `dp_3h` Scale & Seasonal Drift | `custom_components/ws_core/pattern_runtime.py:398-404`; `pattern_forecast.py:371-398`, `1497` | (1) At night (`kt is None`), `cloud_deficit` is set to `0.0` — numerically identical to a 100% cloudless daytime sky (`1.0 - kt = 0.0`) — and fed into `Standardizer`. (2) `replay()` divides 3h pressure delta by `3.0` (`hPa/h`, line `1497`), whereas live `_tick()` passes `KEY_PRESSURE_TREND_HPAH` (`hPa/3h`, 3× larger). (3) The 30-day EMA `Standardizer` shifts what `z(temp)` means across seasons while `frost` and `heat` targets use fixed absolute °C thresholds. |
| **High** | 30-Day Climatology & Diurnal Anomaly Bugs | `custom_components/ws_core/learning_state.py:404-406`; `coordinator.py:3343`, `4052-4073` | `climatology_stats(state)` evaluates the full 90-day deque (`CLIMATOLOGY_WINDOW = 90`), so `sensor.ws_climatology_30d`, `sensor.ws_temperature_anomaly_30d`, and `sensor.ws_rain_anomaly_30d` report 90-day stats instead of calling `climatology_stats_by_window(state, 30)`. Furthermore, both `KEY_TEMP_ANOMALY_30D` and `KEY_TEMP_ANOMALY_NORMAL` compare **instantaneous** `tc` against the 24-hour daily normal mean, producing a fake ±6 °C diurnal wave between night and afternoon on normal days. |
| **Medium** | Pressure Trend Unit Labelling (`hPa/3h` vs `hPa/h`) & Non-Uniform Sampling | `custom_components/ws_core/algorithms.py:467-481`; `const.py:261`; `entity_descriptions.py:453-460`; `coordinator.py:2040-2058` | `least_squares_pressure_trend` multiplies per-interval OLS slope by `180 / interval_minutes`, returning **hPa/3h** (matching WMO Table 4680), yet `KEY_PRESSURE_TREND_HPAH` declares `native_unit="hPa/h"` and `thunderstorm_risk_index` (`algorithms.py:1935, 1938`) labels it `>1.6 hPa/h` (off by 3×). `rt.pressure_history` also stores bare floats without timestamps, so outage gaps distort OLS spacing. |
| **Medium** | WBGT & UTCI Globe Temperature Negative Below 330 W/m² | `custom_components/ws_core/algorithms.py:2165`; `coordinator.py:1938` | `tg = temp_c + 0.393 * solar_w_m2**0.4 - 4.0` yields `tg < temp_c` (up to `-3.6 °C` cooler than shade air temperature) whenever `0 < solar_w_m2 < 330 W/m²`. |
| **Medium** | Adaptive Rain Blend Weights Trapped Near 50/50 | `custom_components/ws_core/learning_state.py:234-250` | `w_l = (1 - BS_l) / ((1 - BS_l) + (1 - BS_a))`. Because precipitation Brier scores typically sit in `0.08–0.20`, a source with **half the Brier error** (`0.10` vs `0.20`) receives only a `52.9%` vs `47.1%` weight instead of meaningful differentiation. |
| **Medium** | ET₀ Wind Height, FFDI Hardcoded Drought, Unweighted Calm Wind & Seasonal Resets | `algorithms.py:1837`; `coordinator.py:2144-2152`, `2575-2613`, `2742` | (1) `et0_penman_monteith` hardcodes 10 m anemometer height (`u2 = u_z * 0.748`), underestimating aerodynamic ET₀ for 2 m PWS mounts. (2) `calculate_ffdi` is called without `drought_factor`, defaulting to `10.0` (maximum drought). (3) 24h dominant wind direction includes calm (`wind_ms == 0`) readings. (4) Degree-day seasons reset strictly on Jan 1, splitting Northern Hemisphere winter (`hdd_season`) and Southern Hemisphere summer (`gdd_season`) in half and ignoring `CONF_GDD_RESET_MONTH`. |
| **Low/Med** | Wet-Bulb Pressure Ignored & Unclamped; NWS Heat Index Adjustments | `algorithms.py:85-138` | Stull (2011) wet-bulb ignores station pressure/altitude (up to 1–2.5 °C high at 1,500–2,500 m) and lacks `[dew_point, temp_c]` bounds. `calculate_heat_index` omits the standard NWS SR 90-23 low-RH (`<13%`) and high-RH (`>85%`) adjustments. |

---

### B. Provider, Uploader, Event, Config & State-Management Bugs

| Severity | Area | Location | Issue & Impact |
|---|---|---|---|
| **High** | Pirate Weather Daily Precip | `custom_components/ws_core/providers/pirate_weather.py:71` | Maps `precip_mm` to `day.get("precipAccumulation", 0.0)`, which in Pirate Weather / Dark Sky (`units=si`) is **snow accumulation in cm**. Liquid rain days report `0.0 mm`. |
| **High** | OpenWeatherMap Dropped Snow | `custom_components/ws_core/providers/open_weather_map.py:103`, `117` | Daily `day.get("rain", day.get("snow", 0.0))` drops snow whenever any rain occurs on the same day; hourly `precip_mm` ignores `(hour.get("snow") or {}).get("1h")` entirely. |
| **High** | `WeatherEntity` Forecast Dict Keys & Attribution | `custom_components/ws_core/weather.py:216`, `313`, `386-391` | Uses `"native_wind_gust_speed"`, `"native_apparent_temperature"`, and `"native_dew_point"` inside `Forecast` dicts instead of standard HA `Forecast` keys (`"wind_gust_speed"`, `"apparent_temperature"`, `"dew_point"`), bypassing HA unit conversion in `weather.get_forecasts`. Line `216` checks `provider == "open-meteo"` (hyphen) instead of `"open_meteo"`, breaking attribution. |
| **High** | Options Flow °F Freeze Threshold Corruption | `custom_components/ws_core/config_flow.py:1711-1713` vs `1949-1957` | `_build_core_schema` converts `thresh_freeze_c` for display using `imperial` (`units_mode == "imperial_us"`), while `async_step_init` converts input using `temp_u == "°F"`. Under `units_mode == "auto"` on an imperial HA system (or a temperature-only unit override), `0.0 °C` is displayed in °C and saved as `(0 - 32) * 5/9 = -17.8 °C`. |
| **High** | `number.ws_staleness_timeout` Max Violates Default | `custom_components/ws_core/number.py:157-163` vs `const.py:89` | `DEFAULT_STALENESS_S` is `7200` and config flow allows `60..86400`, but `number.py:161` sets `native_max=3600.0`, violating its own max constraint out of the box. |
| **Medium** | Network Uploaders Send False Zeroes & Leak AWEKAS Errors | `custom_components/ws_core/uploaders.py:85-89`, `443-448` | Uses `or 0` for `None` wind/rain readings, uploading false `0` wind from `0°` and `0.0` rain to WU, CWOP/MADIS, WOW, Weathercloud, PWSWeather, and AWEKAS during sensor outages, with no QC/health gate. `async_upload_awekas` logs raw exceptions without `_redact_secrets()`. |
| **Medium** | `WSLightningEvent` Misses Strikes in Rolling Window | `custom_components/ws_core/event.py:190-202` | Triggers `"strike_detected"` only if `count_1h > _prev_count_1h`. When new strikes coincide with older strikes aging out of the 60-minute window, `count_1h <= _prev_count_1h` and the strike event is silently dropped. (`use_cases.md:161-165` also erroneously tells users to trigger on event `state` `to: "started"` instead of `attribute: event_type`). |
| **Medium** | `sample=False` Midnight & Transient `None` Bugs | `custom_components/ws_core/coordinator.py:1947-2018`, `2154-2198`, `2800-2804` | Temporary `None` on `tc` or `gust_ms` returns early before writing stored weekly/monthly/yearly/all-time records to `data`, dropping 11 record sensors to `unknown`. Between `00:00:00` and the first 60s tick, `_compute_solar_energy` returns early on `sample=False` without writing `KEY_SOLAR_ENERGY_TODAY_WHM2` or `KEY_PEAK_SUN_HOURS`. |
| **Medium** | Missing `CONF_ENABLE_SOIL` Switch & Orphaned Repair Issue | `custom_components/ws_core/switch.py:116-365`; `coordinator.py:3864`; `const.py:1269-1276` | `CONF_ENABLE_SOIL` has config flow & strings support but is missing from `FEATURE_SWITCHES` in `switch.py`. Repairs issue `"et0_pm_unavailable"` is omitted from `ENTRY_REPAIR_ISSUES`, so `async_remove_entry` never deletes it. |
| **Low** | Missing Translation Key & Empty-Date Forecast Tiles | `custom_components/ws_core/strings.json:27-44`; `ha_weather_entity.py:183-195`; `coordinator.py:5068-5081` | `config.step.optional_sources.data` is missing `"lightning_azimuth"`. `ha_weather_entity` pads daily forecasts to 7 rows with `"date": ""`, leaking empty entries into `sensor.ws_forecast_tiles`. |

---

### C. Architectural & Performance Bottlenecks

1. **Unthrottled full-pipeline recompute on every sensor packet** (`coordinator.py:1375`, `1520-1521`):
   A multi-sensor packet from Ecowitt, Shelly WS90, ESPHome, or MQTT updates 8–14 source entities within milliseconds, synchronously triggering 8–14 consecutive full `_compute(sample=False)` cycles and ~1,500+ entity callbacks with no coalescing window. Furthermore, `_compute_lightning` (`coordinator.py:3490`) runs `_discover_blitzortung()`—scanning every entity in HA's entity registry—on every compute cycle whenever a user uses a hardware lightning sensor without Blitzortung installed.
2. **246–310 entities attached to a single monolithic device** (`__init__.py:227-234`):
   Every outdoor, forecast, agronomy, fire, air quality, diagnostic, control, and named indoor room entity belongs to one `DeviceInfo`, slowing down the Device UI and making it impossible to assign indoor rooms to separate Home Assistant Areas.
3. **2,519-line linear Options Wizard with no menu and no Back button** (`config_flow.py:1678-2519`, `2229-2231`):
   Editing any single option forces the user through a 27-field core form followed by 5–15 sequential wizard steps, with `_flow_back()` implemented as a no-op (`return None`).
4. **Full config entry reload on any option/switch/number change** (`__init__.py:405-407`):
   Toggling any switch, adjusting a threshold, or applying an automatic calibration nudge tears down `WSStationCoordinator`—wiping the 72h drift buffers (requiring a fresh 24h warm-up), spike/stuck timers, 24h wind direction history, and all 9 HTTP caches.
5. **6,005-line monolithic coordinator & inline HTTP clients**:
   While forecast providers are cleanly extracted to `providers/`, 8 other HTTP clients (AQI, Pollen, Marine SST, Nowcast, Neighbor QC, ERA5 Climate Normals, Forecast.Solar, French Vigilance, and Hub'Eau Vigicrues) remain embedded inside `coordinator.py`. (Vigilance also re-geocodes static lat/lon coordinates every 30 minutes.)

---

## Part 2: Cross-Check Against Similar Integrations & PWS Platforms

| Peer Integration / Platform | Key Capabilities It Excels At | Gaps Identified in `ws_core` |
|---|---|---|
| **Thermal Comfort** (`dolezsa/thermal_comfort`) & **HA Mold Indicator** | Per-room dew point, moist air enthalpy (`kJ/kg`), relative strain, summer simmer, cold-bridge surface condensation/mold risk (`calibration_factor`), and indoor/outdoor moisture comparison. | `ws_core`'s Named Indoor Rooms expose deltas, absolute humidity, and comfort score, but lack **per-room dew point, enthalpy, cold-wall mold risk, and an actionable indoor vs. outdoor ventilation decision** (factoring in rain, wind, AQI, and pollen). |
| **Smart Irrigation** (`HAsmartirrigation`) & **Irrigation Unlimited** | Persistent multi-zone soil-water balance bucket (`mm` ledger tracking ET₀ depletion, effective rainfall, runoff cap, and **recorded irrigation applied**) plus runtime calculation. | `ws_core` only computes a memoryless single-day `et0 - rain` difference and an uncalibrated 40%-field-capacity probe deficit. It has **no persistent multi-day water ledger** and no action to record actual watering events. |
| **MeteoAlarm**, **NWS Alerts**, **DWD Warnings** | Official regional CAP weather warnings across Europe, North America, and Australia with severity, onset/expiry, and advisory text. | `ws_core` embeds bespoke French Vigilance and Vigicrues scrapers, leaving non-French users with no official warning ingestion. It lacks a **generic HA Alert / CAP entity adapter** to integrate existing regional alert integrations into its hazard state. |
| **WeatherFlow Forecast** (`briis`), **Pirate Weather**, **Open-Meteo** | Twice-daily (`day`/`night`) forecasts (`FORECAST_TWICE_DAILY`), hourly comfort/agro projections, and multi-model comparisons. | `ws_core` drops NWS day/night granularity, lacks `FORECAST_TWICE_DAILY`, and **does not project its domain indices (Delta-T, UTCI, WBGT, Frost Point, Drying rate) onto the 24–48h hourly forecast**. |
| **Forecast.Solar** / **Solcast** / **Open-Meteo Solar** | Multi-array PV forecasts compatible with the HA Energy Dashboard, plus expected-vs-measured solar irradiance checks (shading/soiling/snow detection). | `ws_core` exposes only single-array `today`/`tomorrow` kWh totals and does not compare pyranometer output against expected clear-sky/PV curves for panel alerts. |
| **WeeWX** & **CumulusMX** (Classic PWS Suites) | Directional **8/16-point Wind Rose** distributions, **multi-sensor fusion/failover** (e.g., shaded minimum of two thermometers, backup rain gauge), and NOAA-style monthly/annual climate reports. | `ws_core` tracks only a scalar 24h dominant bearing (corrupted by calm hours) with no wind rose bins, maps only one entity per source type, and lacks structured climate summary reports. |
| **HA 2025/2026 Platform Standards** | `SupportsResponse` actions, `CalendarEntity`, `ConfigSubentry` for child resources, interactive `RepairsFlow`, multi-device `via_device` hierarchies, and Assist/LLM tool context. | `ws_core` logs `export_learning_state` instead of returning data (`SupportsResponse`), uses static `is_fixable=False` repairs, attaches 250+ entities to one device, and has no `CalendarEntity` or Assist summary action. |

---

## Part 3: Strategic Vision for v3.0 — From Passive Sensor Calculator to Active Weather Decision & Microclimate Engine

Today, `ws_core` gives users 240+ raw/derived numbers and leaves them to mentally synthesize 6–10 sensors—or write fragile Jinja templates—to answer everyday questions:
- *"When in the next 24 hours can I hang laundry, mow, or spray the garden?"*
- *"Should I open the bedroom windows right now, or keep them closed?"*
- *"Does the lawn actually need watering after the last 4 days of sun and rain?"*

A substantial **v3.0** should focus on **five concrete pillars** that turn `ws_core`'s existing depth into deterministic, explainable, automation-ready decisions:

### Pillar 1: Predictive Activity & Agronomic "Weather Windows" Engine
Combine **live station observations + Pattern Forecast (0–6h) + hourly NWP forecast (0–48h)** to evaluate configurable time windows over the next 24–48 hours:
- **Built-in & configurable profiles:**
  - **Outdoor Drying / Laundry:** VPD, rain amount/probability, wind speed, and daylight/solar irradiance.
  - **Garden Spraying & Mowing:** Hourly projected **Delta-T** (`2–8 °C` APVMA window), wind/gust limits, leaf wetness, and post-spray rain-free curing window (`>= 4h`).
  - **Outdoor Work / Sport Comfort:** Hourly projected **UTCI / WBGT**, UV index, AQI, lightning clearance, and frost/wind-chill floors.
  - **Stargazing / Astronomy:** Astronomical darkness, moon illumination (`algorithms.py`), cloud cover, dew-point spread (optics condensation risk), and wind speed.
  - **Awning / Cover & Frost Protection Outlook:** Unified short-term hazard windows.
- **Surfacing & Provenance Contract:**
  - Compact per-profile sensors (`status`: `suitable_now` / `window_upcoming` / `unsuitable` / `unknown`, `next_window_start`, `next_window_duration_h`) carrying explicit `blocking_reasons`, `evaluated_limits`, and `data_quality` (freshness, forecast validity, missing inputs) without bloating the HA recorder.
  - `SupportsResponse.ONLY` service **`ws_core.get_weather_windows`** returning full hourly slots, suitability scores, and rejection reasons for dashboards, scripts, and Home Assistant Assist/LLM agents.
  - Optional **`calendar.<prefix>_weather_windows`** entity displaying upcoming suitable windows and hazard intervals directly on HA Calendar cards.

### Pillar 2: Psychrometric Room Ventilation, Enthalpy & Cold-Bridge Mold Advisor
Elevate Named Indoor Rooms into a full superset of *Thermal Comfort* and HA's *Mold Indicator*:
- **Per-Room Psychrometrics:** Add **Dew Point**, **Moist Air Enthalpy (`kJ/kg`)**, and **Cold-Bridge Surface Relative Humidity / Mold Risk** (from indoor temp/RH, outdoor temp, and a configurable thermal bridge factor $f_{Rsi}$).
- **Smart Room Ventilation Advisor (`sensor.<prefix>_room_<room>_ventilation_advice`):**
  - States: `recommended_cooling`, `recommended_dehumidify`, `recommended_air_quality`, `not_recommended`, `hold_hazard`, `unknown`.
  - Evaluates moisture gradients ($\Delta\text{AH}$), enthalpy gradients ($\Delta h$), and room $\text{CO}_2$, while automatically gating against outdoor rain, high wind gusts, poor AQI, and high pollen.
  - Exposes structured reasons (`abs_humidity_delta_gm3`, `enthalpy_delta_kjkg`, `blocking_factors`).

### Pillar 3: Persistent Soil-Water Balance Bucket ("Virtual Soil Moisture")
Bridge the gap between daily `ET₀` and real irrigation controllers:
- Maintain a persistent, reset-safe **Root-Zone Water Balance Ledger (`mm`)** tracking daily $K_c \times \text{ET}_0$ depletion minus effective rainfall (with field-capacity/runoff capping and configurable readily available water `RAW_mm`).
- Add **`ws_core.record_irrigation`** so smart valves or irrigation automations can credit applied `mm` (or `duration_min × rate`) directly into the soil bucket.
- Fix physical soil probe handling with explicit `%` vs `0–1` fraction config, probe calibration, and configurable field capacity / wilting point.

### Pillar 4: Multi-Sensor Station Fusion, 16-Point Wind Rose & Universal Alerts
Bring classic PWS power-user capabilities into Home Assistant:
- **Multi-Sensor Source Fusion & Failover:** Support secondary/redundant temperature, wind, or rain entities (e.g., `min()` of two radiation-shielded thermometers to defeat solar heating spikes; automatic failover to a backup rain/wind sensor if primary goes `unavailable`/`stale`).
- **24h / 7d Speed-Weighted Wind Rose:** Compute 8- or 16-sector directional frequencies, calm percentage, and per-sector mean/max speeds (and fix dominant direction to ignore calm `0 m/s` vane parking).
- **Universal Weather Alert Adapter:** Allow mapping any HA alert entity (`meteoalarm`, `nws_alerts`, `dwd_weather_warnings`, etc.) into `ws_core`'s unified alert state, dashboard banner, and Weather Windows blocker.

### Pillar 5: Home Assistant 2026 Platinum Architecture & UX Overhaul
- **Multi-Device Hierarchy (`via_device`):** Group entities cleanly across logical devices (*Station Core*, *Forecast & Pattern Engine*, *Agronomy & Fire*, *Air Quality & Environment*, *System, Diagnostics & Uploaders*, plus **one device per Named Indoor Room** and **per River Station** so rooms map directly to HA Areas). Preserve all existing `unique_id`s and `entity_id`s on upgrade.
- **Menu-Driven Options Flow & Live Option Application:** Replace the 15-step linear options wizard with `async_show_menu()` sections that save immediately, and apply switches/numbers/calibration nudges in memory without tearing down 72h drift buffers or HTTP caches. Consider `ConfigSubentry` for rooms, river stations, and uploaders.
- **Micro-Batched Compute Pipeline & Scoped Quality:** Coalesce multi-sensor packet bursts (`100–250 ms` debounce) so 12 simultaneous sensor updates trigger **1** compute pass instead of 12; propagate source freshness along dependency edges so stale wind does not degrade humidity-only outputs.
- **Interactive `RepairsFlow` & Response Actions:** Upgrade static repairs to interactive fix flows (remap missing sensor, resolve ET₀ prerequisite, clamp calibration), add `SupportsResponse` to `export_learning_state`, and add `ws_core.get_station_summary` for Assist/LLM voice summaries.
- **Subsystem Decomposition:** Extract inline HTTP fetchers, quality/health engine, accumulators, and pure decision calculators out of the 6,005-line `coordinator.py` into focused modules.

---

## Part 4: Suggested Release Phasing

### Phase 1: `v2.13.18` Non-Breaking Reliability & Science Hotfixes (Ship Before v3)
1. **Fix Neighbor QC & Auto-Calibration pressure** (`pressure_msl` vs `KEY_SEA_LEVEL_PRESSURE_HPA`).
2. **Fix Pattern Forecast `REPLAY_MASKED_FEATURES`** (mask the 4 solar features during history replay), nighttime `cloud_deficit` handling, and `dp_3h` scale alignment (`hPa/3h` vs `hPa/h`).
3. **Fix solar geometry & radiation physics:** clamp `math.acos` for `|lat| >= 66.5°`, distinguish instantaneous clear-sky $R_{so}(t)$ from 24h-mean $R_{so}$ in `calculate_net_radiation`, add `cos_z` horizontal projection to `update_solar_lux_factor`, and wire learned `solar_lux_factor` into ET₀ fallback.
4. **Fix forecast & provider bugs:** Pirate Weather `precipAccumulation` vs `precipIntensity`, OWM snow omission, `weather.py` `Forecast` dict keys (`wind_gust_speed`, `apparent_temperature`, `dew_point`) and `open_meteo` attribution, forecast cache expiry in rain blend, and `last_attempt` retry backoff.
5. **Fix config/platform/state edge cases:** `config_flow.py` °F freeze threshold conversion, `number.ws_staleness_timeout` max (`86400`), `CONF_ENABLE_SOIL` switch, `WSLightningEvent` rolling-window detection, missing rain `event.py` guard, `async_unload_entry` stop order, 30d climatology window & diurnal anomaly reference, and transient `None` preservation on historical extremes.

### Phase 2: `v3.0` Core Refactor & Decision Engine
1. **Foundation:** Micro-batched `_compute`, live options updates without wiping buffers/caches, menu-based Options Flow, modularized coordinator subsystems, and `via_device` multi-device migration (preserving existing entity IDs/unique IDs).
2. **Vertical Slice 1 (Decision Engine):** Shared provenance/quality contract + Weather Windows engine (Drying, Spraying, Outdoor Comfort, Stargazing) + `ws_core.get_weather_windows` response action + optional `calendar` platform + dashboard/blueprint updates.
3. **Vertical Slice 2 (Indoor & Garden):** Per-room psychrometrics (dew point, enthalpy, mold risk) + Room Ventilation Advisor + Persistent Soil-Water Balance Bucket (`ws_core.record_irrigation`).
4. **Vertical Slice 3 (PWS Analytics & HA 2026 Polish):** Multi-sensor fusion/failover, 16-point Wind Rose, universal HA alert entity adapter, `FORECAST_TWICE_DAILY`, interactive `RepairsFlow`, and `ws_core.get_station_summary` response action.
