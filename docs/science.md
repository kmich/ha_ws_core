# Scientific Documentation {#science}

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

The frost point is the temperature at which ice saturation occurs. Relative humidity is
reported with respect to liquid water, so the actual vapour pressure is first taken from
the water Magnus curve (the dew-point constants above) and then inverted on Buck's (1981)
ice-phase curve (a = 22.587, b = 273.86). Returns the dew point when the dew point is at or
above 0 °C, and the frost point (always slightly warmer than the dew point) below 0 °C.

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

`T_K` is the **12-hour mean** temperature (in kelvin), as recommended by WMO, rather
than the instantaneous reading. This avoids a spurious day/night wave in MSLP. Until
at least an hour of history has accumulated (for example just after setup), the
instantaneous temperature is used as a fallback.

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

The system is defined on local-noon observations. The moisture codes advance once per
calendar day, on the first reading at or after 12:00 local time, using that reading's
temperature, humidity and wind plus the rolling 24h rain total (which at noon is exactly
the standard noon-to-noon rainfall). Between those daily steps ISI, BUI, FWI and DSR are
re-evaluated from the stored codes with the current wind; the codes themselves do not
change until the next day's noon reading.

**Disclaimer:** Not suitable for operational fire weather decisions. Consult official
fire services and national fire weather products.

**Reference:** Van Wagner, C.E. (1987). *Development and structure of the Canadian Forest
Fire Weather Index System.* Forestry Technical Report 35. Canadian Forestry Service.

---

### ET₀ — Reference Evapotranspiration {#et0-science}

**Hargreaves-Samani 1985** (default, always available):

```
ET₀ = 0.0023 · Ra · (T_mean + 17.8) · (T_max − T_min)^0.5
T_mean = (T_max + T_min) / 2        (FAO-56 daily mean, from the rolling 24h high/low)
```

`sensor.ws_et0_hourly` spreads the daily total over daylight with a sine curve between
06:00 and 18:00 **local solar time** (derived from the station longitude), peaking at solar
noon and summing to the daily value.

**Accuracy:** ±15-20% vs Penman-Monteith.
**Reference:** Hargreaves, G.H. & Samani, Z.A. (1985). *Appl. Eng. Agric.*, 1, 96-99.

**FAO-56 Penman-Monteith** (activates when a `solar_radiation` W/m² source is mapped):

```
ET₀ = [0.408·Δ·(Rn − G) + γ·(900/(T+273))·u₂·(eₛ − eₐ)] / [Δ + γ·(1 + 0.34·u₂)]
```

The mean temperature term uses the FAO-56 daily mean (T_max + T_min) / 2, and the radiation
term uses the previous complete day's measured irradiation divided by 24 h.

**Accuracy:** ±5-10% vs lysimeter under standard conditions.
**Reference:** Allen, R.G. et al. (1998). *FAO Irrigation and Drainage Paper 56.* FAO, Rome.

---

### Moon Phase — Meeus Astronomical Algorithms (1998)

Computed from Julian Date using simplified lunar orbital equations without external API calls.
**Accuracy:** ±1% illumination, ±0.5 day phase timing.
**Reference:** Meeus, J. (1998). *Astronomical Algorithms*, 2nd ed. Willmann-Bell. Chapter 48.

---

### Update Cadence {#cadence}

Derived values are recomputed whenever a source sensor updates, so dashboards stay
current. State that accumulates *per sample* advances only on a fixed 60-second tick:
the 24h rolling histories, the rain-rate Kalman filter, wind-direction smoothing, the
daily degree-day means, spike and drift buffers, alert debounce counters and solar-factor
learning. Between ticks those values are shown including the latest reading but are not
stored, so their behaviour does not depend on how often your station reports.

---

### Rain Rate — 1D Kalman Filter

Optimal recursive smoothing eliminates tipping-bucket spike-and-drop artefacts.
The filter takes one measurement per 60-second tick.
Configurable measurement noise (`number.ws_rain_filter_alpha`).

---

### 30-Day Rolling Climatology

After approximately 14 days of operation, the integration builds a local climate baseline
from the station's own history. Temperature and rain anomaly sensors are meaningful after
30+ days of continuous operation.

---

### Sensor Drift Detection — Linear Regression (72h)

OLS regression over the last 72h (one sample per minute) flagging monotonic drift
(slope magnitude + R² ≥ 0.85) in temperature, humidity and pressure, plus a stuck
rain-rate check over 4h. No slope is judged on less than 24h of data, so the diurnal
temperature and humidity cycle cannot pass for drift. The buffers are in memory, so the
24h warm-up restarts after a Home Assistant restart.

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

### Stuck-Value Detection

`sensor.ws_sensor_stuck` and the per-sensor *stuck* binary sensors flag a reading that has
not moved beyond a small tolerance for a sustained period:

| Sensor | Tolerance | Flagged after |
|---|---|---|
| Temperature | 0.05 °C | 4 h unchanged |
| Humidity | 0.5 % | 6 h unchanged (ignored within 2 % of 0 % or 100 %, e.g. fog) |
| Pressure | 0.05 hPa | 6 h unchanged |

The check is time-based rather than sample-based because derived values are recomputed on
every source update, and a healthy sensor with 0.1 resolution can legitimately hold one
value for several minutes.

---

### US Air Quality Index

`sensor.ws_air_quality_index` is the higher of the PM2.5 and PM10 sub-indices, computed
from Open-Meteo's current concentrations with the US EPA breakpoints, including the
2024 PM2.5 revision (Good = 0-9.0 µg/m³). Concentrations are truncated as the EPA
specifies (PM2.5 to 0.1 µg/m³, PM10 to 1 µg/m³) before lookup. The EPA index is defined
on 24h averages; ws_core applies it to current values, so treat it as an indicator.

**Reference:** US EPA (2024). *Technical Assistance Document for the Reporting of Daily Air
Quality — the Air Quality Index (AQI).*

---

### Adaptive Rain Blend {#rain-blend}

`sensor.ws_rain_probability_combined` blends the local rain index
(`sensor.ws_rain_probability`) with the forecast provider's precipitation probability,
and learns how much to trust each from how they have scored at your station.

- **Windows.** Every 6 hours a window opens and records both probabilities. The
  provider side is the highest hourly precipitation probability over the same 6 hours.
  Consecutive hours are strongly correlated, so treating them as independent events
  (`1 - prod(1 - p_h)`) would overstate the chance; providers build their daily
  probability the same way. If fewer than half the hours have a probability (Met.no,
  for example, gives none), today's daily probability is used instead.
- **Outcome.** The window counts as wet if the filtered rain rate goes above 0.1 mm/h at
  any point in it.
- **Score.** Each source gets a Brier score, `mean((p - y)^2)`, over the last 90 days,
  once at least 10 windows have closed.
- **Weight.** Each source's weight is its share of `1 - B`:
  `w_local = (1 - B_local) / ((1 - B_local) + (1 - B_provider))`. This moves gently: a
  source has to be clearly and persistently worse before it loses much of its weight.
  With fewer than 10 windows the blend uses a fixed time-of-day weight.
- **Blended value.** The published combined probability applies those weights to the
  local index and the provider's daily probability for today.

Before 2.13.5 the provider side was scored with its daily probability against the
6-hour window, so the two sources weren't answering the same question. Each window
now records which basis it used. Once 10 windows use the hourly basis, only those are
scored; until then, older windows still count, so learned weights carry over instead of
resetting.

---

## Pattern Forecast {#pattern-forecast}

Pattern Forecast is the one part of `ws_core` that learns. It estimates the probability
that an event happens at this station within a window, using only this station's own
sensors. This section is the method; the [user guide](guides/pattern_forecast.md)
shows how to use it.

### Events and thresholds

| Forecast | Event, checked against | Window | Threshold |
|---|---|---|---|
| Rain | Rain total gains at least 0.2 mm | 1 h, 3 h, 6 h | fixed (a conventional measurable-rain floor, one tip of a 0.2 mm bucket) |
| Frost | Lowest temperature at or below the freeze threshold | 12 h | `thresh_freeze_c`, default 0 °C |
| Heat | Highest temperature at or above the hot-day threshold | 24 h | `thresh_heat_day_c`, default 30 °C |
| Gust | Highest gust at or above the gust alert threshold | 3 h | `thresh_wind_gust_ms`, default 17 m/s |
| Storm | At least 2 lightning strikes within the proximity distance | 3 h | `lightning_proximity_km`, default 15 km |

Forecasts are issued every 15 minutes (on :00, :15, :30, :45). Rain, gust and storm
models learn from every issue; frost and heat learn from the on-the-hour issues only,
because their 12 to 24 h windows overlap so much that quarter-hour samples add almost
no information.

### Features

One pool of 23 inputs is computed at each issue. Each forecast uses a fixed subset
(a tick marks use); every model also has a bias term. All values are metric.

| # | Feature | Definition | Rain | Frost | Heat | Gust | Storm |
|---|---|---|:-:|:-:|:-:|:-:|:-:|
| 1 | `mslp` | Sea-level pressure, hPa | x | x | x | x | x |
| 2 | `dp_3h` | 3 h pressure tendency (least-squares) | x | x | | x | x |
| 3 | `dp_24h` | 24 h pressure change | x | x | x | x | |
| 4 | `temp` | Temperature, °C | | x | x | | x |
| 5 | `dpd` | Dew point depression, T - Td | x | x | x | | x |
| 6 | `dpd_1h` | Change in `dpd` over 1 h | x | | | | x |
| 7 | `t_1h` | Temperature change over 1 h | x | x | | x | x |
| 8 | `t_3h` | Temperature change over 3 h | | x | x | | |
| 9 | `t_max_24h` | Highest temperature, last 24 h | | | x | | |
| 10 | `wind_u` | 1 h mean east-west wind component | x | | x | x | |
| 11 | `wind_v` | 1 h mean north-south wind component | x | | x | x | |
| 12 | `wind_speed` | 1 h mean wind speed | | x | | x | |
| 13 | `gust_1h` | Highest gust, last 1 h | | | | x | x |
| 14 | `rain_1h` | log(1 + rain in the last 1 h, mm) | x | x | | | x |
| 15 | `dry_hours` | log(1 + hours since rain), capped at 48 h | x | | x | | |
| 16 | `cloud_deficit` | 1 - clearness index while the sun is up, else 0 | x | | x | | x |
| 17 | `solar_ok` | 1 when feature 16 is real, else 0 | x | | x | | x |
| 18 | `last_day_clearness` | Clearness of the last daylight hour, carried through the night | | x | | | |
| 19 | `last_day_clearness_ok` | 1 when feature 18 is real | | x | | | |
| 20 | `night_frac_12h` | Fraction of the next 12 h with the sun below the horizon (local solar-position math) | | x | | | |
| 21 | `hour_sin` | sin(2 pi * local hour / 24) | x | x | x | x | x |
| 22 | `hour_cos` | cos(2 pi * local hour / 24) | x | x | x | x | x |
| 23 | `lightning_1h` | log(1 + strikes within proximity, last 1 h) | | | | | x |
| | **Inputs per forecast** | | **14** | **14** | **13** | **10** | **13** |

Wind direction enters as east-west and north-south components, because an angle cannot
be averaged or fed to a linear model; calm wind is a separate speed input for the same
reason. Missing solar data becomes 0 plus a `_ok` = 0 flag, so the model can tell
"clear" from "no data".

### Model

Each forecast is one small online logistic regression over its features plus a bias:
`p = 1 / (1 + exp(-(w0 + sum(wi * zi))))`.

- **Standardizer.** A running mean and variance per feature, shared by all models:
  Welford's algorithm for the first 7 days of samples, then a slow exponential average
  with a half-life of about 30 days. Standardized values `z` are clipped to +/-5, so one
  sensor spike cannot blow up a weight.
- **Training.** Stochastic gradient descent with an L2 penalty on the weights (not the
  bias), AdaGrad per-weight step sizes and a **learning-rate floor**, so the model
  never stops adapting to the seasons. Gradients are clipped and the weight norm is
  bounded. After each update, a non-finite or out-of-bound weight restores the model's
  last daily checkpoint.
- **Plain log loss.** No class weighting, because weighting a rare event destroys
  calibration.
- **Monotone rain.** The events are nested (rain within 1 h implies rain within 3 h), so
  after prediction `p3 = max(p3, p1)` and `p6 = max(p6, p3)`.
- **Size.** About 100 weights, tens of microseconds per prediction, pure Python, no
  numpy, no new dependency.
- **Explanation.** Each feature's signed contribution `wi * zi` is mapped to a
  deterministic factor key (for example falling pressure, clear sky); the three largest
  become `top_factors`.

### Labels

Every issued forecast waits in a small pending buffer, keeping running tallies, until its
window closes. Then the label is decided:

- If valid readings cover **less than 90 %** of the window, or Home Assistant was down
  or restarted while it was open, the label is **unknown and discarded**. Missing data
  is never read as "it did not happen"; that would bias every model low.
- Counters (rain, lightning) sum **positive deltas**. A decrease is a counter reset, not
  negative rain. A single jump far beyond what is physically possible invalidates the
  window.
- Lightning strikes count only within the proximity distance when a distance sensor is
  mapped.

### Scoring

The forecast is **scored first, then trained on** (prequential evaluation), so the score
is never flattered by the example it just learned from. Over weekly aggregates covering
the last 52 weeks:

- The **Brier score** of the model, `mean((p - y)^2)`.
- The **Brier skill score** versus the station's usual rate, `BSS = 1 - B_model / B_usual`,
  where the usual rate is a 30-day running base rate. 0 means no better than always
  saying the usual chance, 1 is perfect, negative is worse.
- The Brier score of **conditional persistence** ("same as now": wet now, frost in the
  last 24 h, hot in the last 24 h, strong gust in the last 3 h, lightning in the last
  hour), reported as `bss_vs_persistence`. This is the bar to clear where persistence is
  strong (rain 1 h, heat).
- A 10-bin **reliability** table (count, mean forecast, observed frequency).
- For information only: the Brier score of the existing heuristics (`rain_probability`
  and `thunderstorm_risk`) where one exists.

### Maturity

Events, not samples, are counted, because consecutive samples are strongly
autocorrelated. An event is a rain, gust or storm episode (separated from the previous by
6 h, 6 h and 3 h of quiet), a local night whose minimum reached the freeze threshold, or
a local date whose maximum reached the hot-day threshold.

| Forecast | Leaves `collecting` at | `skilled` when, within the last 52 weeks of live data |
|---|---|---|
| Rain | 7 days and 5 events | at least 15 events and BSS above 0.02 |
| Frost | 7 days and 5 frost nights | at least 10 frost nights and BSS above 0.02 |
| Heat | 7 days and 5 hot days | at least 10 hot days and BSS above 0.02 |
| Gust | 7 days and 5 episodes | at least 10 episodes and BSS above 0.02 |
| Storm | 7 days and 5 episodes | at least 10 episodes and BSS above 0.02 |

A `skilled` forecast becomes `degraded` when its BSS over the last 5 weeks is 0 or less,
judged only when those weeks contain at least 3 events; otherwise the previous verdict
stands, so a seasonal forecast does not flap out of season. The gates are constants and
may be tuned after beta data. Input checks reuse the existing staleness, spike, drift
and stuck-sensor detectors; a flagged input pauses only the forecasts that use it.

### Learning from recorder statistics

Home Assistant keeps hourly long-term statistics (mean, min, max, sum) of sensors that
have a `state_class`. When Pattern Forecast starts with an empty model it replays up to
365 days of them through the same unit conversion and calibration offsets as live data,
on the recorder executor and on a copy of the models, then swaps the result in.

Replay is approximate and is labelled as such: one sample per hour; the hourly mean
stands in for the instantaneous value; 1 h and 3 h changes come from hourly means;
frost labels use the hourly minimum and heat labels the hourly maximum; wind direction
is masked (an angle cannot be averaged across 0 and 360 degrees), so `wind_u` and
`wind_v` receive no gradient; storm labels have no distance filter; clearness inputs
are unavailable. Replayed samples count toward leaving `collecting`, but never toward
`skilled`, because skill must be proven on live 15-minute data.

### Local-first contract

Inputs and labels come only from the configured source sensors. It never reads the
forecast cache, nowcast, climate normals, neighbor quality control or any other
network-fed value, and it sends nothing anywhere. The single exception is the explicit,
labelled, off-by-default option to use Blitzortung lightning for the storm forecast when
no detector is mapped; it feeds only the storm model.

---

## Services {#services}

| Service | Description |
|---|---|
| `ws_core.reset_rain_baseline` | Reset the internal rain total baseline (useful after station rain counter resets) |
| `ws_core.reset_learning_state` | Reset learned solar factor, forecast skill, streak counters and/or the Pattern Forecast models |
| `ws_core.export_learning_state` | Write the learning state to the Home Assistant log |
| `ws_core.apply_calibration` | Write sensor calibration offsets from an automation or Developer Tools |

Omit `entry_id` to target every Weather Station Core entry.

---

## Sensor Calibration {#calibration}

Each source reading is first converted to canonical metric units (°C, hPa, m/s, mm),
then the calibration offset is added, and only then are the derived metrics computed.
So an offset is always expressed in metric units regardless of your display units.

| Offset | Range | Typical use |
|---|---|---|
| Temperature | ±10 °C | Correct for sensor placement or radiation shield quality |
| Humidity | ±20% | Compensate for sensor aging |
| Pressure | ±10 hPa | Correct for altitude error |
| Wind speed | ±5 m/s | Adjust for sheltered mounting (applied to wind gust too) |

Source sensors may report pressure in hPa, mbar, Pa, kPa, inHg, mmHg or psi, and wind in
m/s, km/h, mph, knots or ft/s; they are converted before the offset is added.

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
2. Sea-level pressure uses the WMO-recommended 12h mean temperature once enough
   history exists, and falls back to the current temperature during the first hour
   of operation.
3. Rain probability is a heuristic index, not a statistically calibrated probability.
4. FWI moisture codes are initialised at Van Wagner's standard defaults on first run and self-correct within a few days.
5. Thunderstorm Risk is a surface-based proxy only and cannot detect elevated convection.
6. 24h statistics are computed from rolling windows that are persisted to disk and
   restored on HA restart, so a normal restart preserves them. Extended downtime
   still leaves a gap in the window until it refills.
7. Pattern Forecast needs time and real events at your station before a forecast is
   published, may never mature where an event is rare, is seasonal (heat and storm are
   beta until a summer of live data has been checked), and sees only what one station's
   sensors reveal. It is not a regional or radar forecast. Learning from history is
   approximate (see [Pattern Forecast](#pattern-forecast)).

---

## Example Automations

Ten automation blueprints are provided in `blueprints/automation/ws_core/`, including:

- **Frost Alert** — Notify when temperature drops below threshold
- **Storm Alert** — Alert on rapid pressure drop with high wind
- **Irrigation Rain Skip** — Skip watering when rain is expected or accumulated
- **Lightning Safety** — Notify when lightning is detected nearby
- **Fire Danger Alert** — Alert when fire danger reaches a configurable level

See [the blueprints folder](https://github.com/kmich/ha_ws_core/tree/main/blueprints) for installation instructions.

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

[MIT](https://github.com/kmich/ha_ws_core/blob/main/LICENSE)

---

[hacs-badge]: https://img.shields.io/badge/HACS-Default-41BDF5.svg
[hacs-url]: https://github.com/hacs/integration
[release-badge]: https://img.shields.io/github/v/release/kmich/ha_ws_core
[release-url]: https://github.com/kmich/ha_ws_core/releases
[license-badge]: https://img.shields.io/github/license/kmich/ha_ws_core
[license-url]: https://github.com/kmich/ha_ws_core/blob/main/LICENSE
[validate-badge]: https://img.shields.io/github/actions/workflow/status/kmich/ha_ws_core/validate.yml?label=validate
[validate-url]: https://github.com/kmich/ha_ws_core/actions/workflows/validate.yml
[translation-badge]: https://img.shields.io/badge/translations-8-blue
[translation-url]: https://github.com/kmich/ha_ws_core/tree/main/custom_components/ws_core/translations
