# Weather Station Core - v1.3.0

**Release date:** TBD (May 2026)

A focused cleanup release. The integration was originally called *Core* but had grown to 80+ sensors. This release strips it back down to a true core (~25 essential sensors), fixes several long-standing bugs in the forecast/condition logic, and removes feature scaffolding that was never wired up.

> ℹ️  This release contains breaking changes (entities and config keys removed). The integration's `async_migrate_entry` performs a one-shot cleanup on first launch — see *Migration* section below.

---

## Bug fixes

### `weather.ws` reports "cloudy" when it's actually sunny
Previously, the `weather.ws` entity returned Open-Meteo's *daily* weathercode as the *current* condition. Open-Meteo's daily code is a summary of the whole day, so on partly-cloudy days the entity would say "cloudy" even when the sun was clearly out. The condition property now prefers, in order:

1. The local-sensor-driven `ws_current_condition` (which integrates real-time illuminance, rain rate, wind gust, etc.).
2. Open-Meteo's *hourly* weathercode for the current hour.
3. Open-Meteo's daily summary as a last-resort fallback.

### `ws_uv_level` reports `unknown` at night
The coordinator was using a truthy check (`if uv := data.get(KEY_UV):`) which treats `0.0` as falsy and skipped setting the UV level entirely. UV=0 now maps to `"None"` per the WMO scale (0 = None, 1-2 = Low, 3-5 = Moderate, 6-7 = High, 8-10 = Very High, 11+ = Extreme).

### `ws_zambretti_forecast` returns "Showery" in stable high pressure
Three fixes here:
- **Recalibrated MSLP→Z scale** to match the original Zambretti dial bands. The previous linear interpolation flattened the "fairly fine" zone too aggressively, so 1015 hPa MSLP returned Z=10 ("Changeable") when it should have been Z=6-8.
- **Wind-direction influence is suppressed at very low wind speeds** (`< 1.0 m/s`). At calm conditions, wind direction is meteorological noise rather than a prevailing-wind signal.
- **Sanity guard against rain narratives in fair conditions:** if MSLP > 1015, humidity < 60%, no 24h rain, and pressure trend ≥ −1 hPa/3h, the forecast text is clamped into the "fairly fine" band.

---

## Removed entities (22)

Hard-removed via `async_migrate_entry` on first launch — no `_2` suffix duplicates. If you reference any of these in automations or dashboards, update those references.

**METAR cross-validation family (7):**
`ws_metar_validation`, `ws_temp_vs_metar_delta`, `ws_pressure_vs_metar_delta`, `ws_cal_suggestion_temperature`, `ws_cal_suggestion_pressure`, `ws_learned_temp_bias`, `ws_learned_pressure_bias` — feature was scaffolded but never produced output without METAR config.

**Roadmap-but-not-built (2):**
`ws_last_export_time`, `ws_cwop_upload_status` — uploads/exports never wired up.

**Lifestyle scores (3):**
`ws_running_score`, `ws_laundry_drying_score`, `ws_stargazing_quality` — out of scope for "core."

**Degree days (4):**
`ws_growing_degree_days_today`, `ws_growing_degree_days_season`, `ws_cooling_degree_days_today`, `ws_heating_degree_days_today` — baselines were never properly seeded (counted from install date instead of Jan 1 / season start).

**Redundancies (6):**
- `ws_moon_phase` — phase string is now an attribute on `ws_moon`.
- `ws_air_quality_level` — level string is now an attribute on `ws_air_quality_index`.
- `ws_pressure_trend_raw` — value already exists in `ws_pressure_trend`'s `trend_rate_hpah` attribute.
- `ws_rain_rate_raw` — keep filtered only.
- `ws_precipitation_type` — trivially derivable from rain rate + temperature.
- `ws_time_since_rain` — overlapped with `ws_dry_streak`.

---

## Removed services
- **`ws_core.apply_learned_calibration`** — tied to the cut METAR family.

---

## Disabled-by-default entities (3)
These remain registered but won't show up unless the user explicitly enables them in HA's entity settings. They depend on infrastructure that's deferred to future releases:

- `ws_temperature_anomaly_30_day` — needs proper climatology baseline (target: v1.4.0).
- `ws_rain_anomaly_30_day` — same.
- `ws_weather_underground_status` — WU upload roadmap (target: v1.5.0+).

---

## Config flow simplification

The setup wizard had ~20 steps, most for cut features. Removed:
- `degree_days` step (and its `_opt` reconfigure variant)
- `metar` step (and `_opt`)
- `cwop` step (and `_opt`)
- `export` step (and `_opt`)
- 7 toggle checkboxes from the `features` step (laundry, stargazing, running, degree_days, metar, cwop, export)

Added two new toggles to the `features` step:
- **Fog probability** (default off)
- **Thunderstorm risk** (default off)

The **pollen** step no longer asks for a Tomorrow.io API key — pollen now comes from the same Open-Meteo Air Quality API call as AQI (free, no key, single fetch). Includes alder, birch, grass, mugwort, olive, and ragweed pollen levels.

---

## Default-off opt-in behavior

All risk and lifestyle-adjacent features now default to **off** in the wizard, rather than being silently enabled:
- Fire risk score
- Fog probability
- Thunderstorm risk
- Sea surface temperature
- Air quality
- Pollen
- Moon
- Solar forecast
- Weather Underground upload

Users who want them tick the box during setup. This keeps the entity list small for users who don't need extras.

---

## Migration

On first launch of v1.3.0 the integration:

1. **Removes 22 deprecated entities** from the HA entity registry, matching by both `unique_id` and entity slug. This prevents the dreaded `_2` suffix problem and keeps the registry clean.
2. **Scrubs ~20 deprecated config keys** from `entry.data` and `entry.options`.
3. **Bumps the config entry version to 3** (was 2 in v1.2.0). The migration handler chains v1→v2→v3 so users on very old releases also pick up the cleanup.
4. **Bumps the learning-state schema to v2** in the persistent Store. Old state files are discarded on load — you'll lose the rolling 30-day climatology buffer and forecast skill outcomes once, then they rebuild over the next 30 days. Streak counters are preserved if their fields existed.

**No user action is required.** Just install and restart.

---

## Internal cleanup

For maintainers / developers:

- **~1,700 lines of code removed** across 11 files.
- `coordinator.py`: removed `_compute_activity_scores`, `_compute_degree_days`, `_async_fetch_metar`, `_async_upload_cwop`, `_async_export_data`, `_async_fetch_pollen` (Tomorrow.io). Renamed `_compute_fog_precip_type` → `_compute_fog_and_thunderstorm`. Renamed `_compute_gdd_and_streaks` → `_compute_streaks`.
- `algorithms.py`: removed 13 unused functions (lifestyle scores, METAR helpers, degree-day calcs, `precipitation_type`).
- `learning_state.py`: removed METAR bias EMA fields and GDD season tracking.
- `_compute_learning_sensors`: METAR-gated branch removed. Solar lux factor and forecast skill remain.
- Pollen fetch: now piggybacks on `_async_fetch_aqi`'s single Open-Meteo Air Quality API call.

---

## Known follow-ups (deferred)

- **Dashboards** (`weather_dashboard.yaml`, `weather_dashboard_vanilla.yaml`) still reference cut sensors. The advanced dashboard simplification pass is its own release — see issue tracker.
- **Climatology baseline for anomaly sensors** — fetch 30-year normals from Open-Meteo's climate-api on integration setup, store as static lookup. Target: v1.4.0.
- **METAR family** may return as an optional integration in v2.x with proper Open-Meteo cross-validation as a fallback when METAR is unavailable.

---

## Numbering note

This release was tracked internally as "v0.3.0" during development. Since the previous shipped version is v1.2.0, the actual release number is **v1.3.0** (logical next minor). The repository's internal v0.3.0 references in code comments are the development codename and don't reflect the public version.
