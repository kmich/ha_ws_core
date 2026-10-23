# Pattern Forecast v1 - Feature Spec

**Status:** Draft for review (rev 3: multi-target, Blitzortung opt-in)
**Target:** ws_core 2.11.0 (current: 2.10.1)
**Author:** Konstantinos Michalitsis
**Date:** 2026-10-23

A local, learning-based short-term forecaster that trains only on the user's own station. It forecasts five events the station itself can measure: **rain, frost, heat, strong gusts and thunderstorms**. No cloud input by default (the single exception is an explicit, clearly labelled opt-in for storm lightning data, section 0), no LLM, no new Python dependencies.

---

## 0. Name and framing

### Name: **Pattern Forecast**

| Candidate | Verdict | Reason |
|---|---|---|
| **Pattern Forecast** | **Chosen** | Says what it does (learns recurring weather patterns at this station) and what it outputs (a forecast). Not tied to one weather type, so it covers rain, frost, heat, gust and storm, and extends to a temperature curve in v2 without a rename. Entity IDs read well: `sensor.ws_pattern_frost_12h`. |
| Station Learning | Rejected | "Learning" is already taken: `LearningState`, `reset_learning_state`, `export_learning_state` cover calibration bias, streaks and the Brier blend. A second "learning" subsystem would blur services and docs. It also does not say what the user gets. |
| Local Forecast | Rejected | Zambretti is also a local forecast; ambiguous. |
| Smart / AI Forecast | Rejected | Marketing fluff, and "AI" invites exactly the expectation (and the LLM baggage) this replaces. |

Naming constraint: no config key, unique_id or translation key may contain `forecaster`. `DEPRECATED_KEYS_FORECASTER` (`enable_local_forecaster`, `forecaster_learning_rate`) is matched by `_async_remove_orphaned_forecaster_entities()` in `__init__.py` on every setup, so reusing those keys would get new entities deleted.

### The one rule that decides what can be forecast

Pattern Forecast learns by checking every past forecast against what the station actually measured afterwards. So a target qualifies only if both of these hold:

1. **The station measures it.** There must be a sensor reading to check the forecast against.
2. **It happens often enough to learn from.** That means at least a handful of times a season.

This is why rain, frost, heat, gust and storm are in, and why hail, fog and multi-day heatwaves are not (section 1).

### Local-first contract

Pattern Forecast is the first ws_core forecast feature that is local all the way through, by default:

- **Inputs:** only the configured source sensors (the required set, plus optional solar/lux and lightning).
- **Labels (ground truth):** only the station's own sensors (rain gauge, thermometer, anemometer, lightning detector).
- **Never reads** `_forecast_cache`, nowcast data, Open-Meteo, climate normals, neighbor QC, or any other network-fed value. It works with the forecast provider disabled and the network unplugged.
- **Never sends** anything anywhere. No skill telemetry, no model upload.

This is enforced by a test (the engine module imports nothing network-capable, and the integration test runs it with `forecast_enabled = False`, the opt-in below off, and no aiohttp session).

### The one exception: internet lightning for the storm forecast (opt-in, off by default)

Many Home Assistant users have no lightning detector but do run the Blitzortung integration. Blitzortung feeds lightning from a community network over the internet; ws_core already discovers it as a fallback (`_discover_blitzortung()`). Pattern Forecast may use it for the **storm target only**, and only when **all** of these hold:

1. **No local hardware detector is mapped.** Local always wins. If a hardware detector (e.g. Ecowitt WH57, Tempest via local UDP) is mapped, Blitzortung is ignored even with the opt-in on.
2. **The user explicitly opts in.** `pattern_storm_internet_lightning` defaults to off (section 6).
3. **It is labelled everywhere it shows:**
   - the storm sensor's friendly name gets the suffix "(internet lightning)";
   - every probability sensor carries a `data_source` attribute (`local`, or `internet` for storm in this mode);
   - the status sensor lists `internet_inputs: [storm_3h]`;
   - the diagnostics download flags it.
4. **It stays contained.** Blitzortung data feeds only the storm model's lightning feature and storm labels. Rain, frost, heat and gust never see it, so they stay 100% local in every configuration.

The marketing line becomes: **"Pattern Forecast is 100% local. The storm forecast can optionally use internet lightning data if you don't own a lightning detector; it is off by default and labelled when on."**

### Flag: current local-first claims vs. the code

Relevant because Pattern Forecast will be positioned against these:

1. **README line 11** credits "your own rain gauge" with predicting "the exact minute rain begins ... 100% locally ... zero cloud dependencies". That capability is `derive_nowcast()`, which runs on Open-Meteo `minutely_15` data (opt-in, `enable_nowcast`); the gauge only blends in. The claim is inaccurate today.
2. **`DEFAULT_FORECAST_ENABLED = True`** with `DEFAULT_FORECAST_PROVIDER = open_meteo`, so a default install makes outbound calls. `sensor.ws_rain_probability_combined` and the Brier blend weights (`learning_state.compute_blend_weights`) use Open-Meteo's daily `precip_prob`.
3. README line 63 ("unless you explicitly enable an optional external service") is contradicted by point 2.

4. **The hourly neighbor-QC fetch** (`_async_fetch_neighbor_qc`, Open-Meteo) starts whenever a location is configured. It has no toggle, and setup pre-fills the HA home location, so ws_core cannot currently run fully offline.
5. **French Vigilance** sends coordinates to the government geocoder (`api-adresse.data.gouv.fr`) before querying by department code; the README said "department code" only.

**Status:** the README has been corrected alongside this spec (intro, nowcast wording, pillar 4, Blitzortung row, Data & Privacy Disclosure table, FAQ). Point 4 is now fixed in code: the new `enable_neighbor_qc` option (on by default) turns the fetch off. Pattern Forecast must not inherit the "exact minute" language: it outputs probabilities over windows, not a countdown.

---

## 1. Exact v1 scope

### What it forecasts

Each forecast answers one question: **"what is the chance that X happens at my station in the next H hours?"**, where X is measured by the station itself.

| Target | Question (at issue time *t*) | Horizon(s) | Checked against | Threshold (existing setting, reused) | Created when |
|---|---|---|---|---|---|
| **Rain** | Gauge records >= 0.2 mm in (t, t+H] | 1 h, 3 h, 6 h | Rain total | `PATTERN_RAIN_THRESHOLD_MM = 0.2` (constant) | Always |
| **Frost** | Lowest temperature in (t, t+12h] <= freeze threshold | 12 h | Temperature | `thresh_freeze_c` (default 0 °C) | Always |
| **Heat** | Highest temperature in (t, t+24h] >= hot-day threshold | 24 h | Temperature | `thresh_heat_day_c` (default 30 °C) | Always |
| **Gust** | Highest gust in (t, t+3h] >= gust alert threshold | 3 h | Gust | `thresh_wind_gust_ms` (default 17 m/s) | Always |
| **Storm** | >= 2 lightning strikes within proximity in (t, t+3h] | 3 h | Lightning count (+ distance if mapped) | `lightning_proximity_km` (default 15 km) | A **local hardware** lightning detector is mapped, **or** the internet-lightning opt-in is on and Blitzortung is present |

Notes:

- **Rain 0.2 mm** is the conventional "measurable rain" floor and one tip of a 0.2 mm tipping bucket. It also filters single spurious counts on haptic/piezo gauges such as the Shelly WS90's. The 0.1 vs. 0.2 decision is settled from real WS90 data (open question 1).
- **Frost** is about the air temperature at the sensor. Ground and grass frost can form when the air at mast height is still +2 to +3 °C. Users who care about ground frost raise `thresh_freeze_c`; the docs explain this.
- **Storm >= 2 strikes**, not 1, because consumer lightning detectors (AS3935 chip) register occasional single false strikes from electrical noise.
- **Thresholds are the user's existing alert settings**, so "frost" means the same thing in the frost alert, the frost streak and Pattern Forecast. Changing one re-learns only that target (section 4).

### What it does not forecast, and why

| Not forecast | Reason |
|---|---|
| **Hail** | No consumer station measures it reliably (piezo gauges cannot tell hail from heavy rain; only the Tempest reports a hail flag), and it occurs a few times a year at most. Nothing to learn from. |
| **Multi-day heatwave** | Seeing a heatwave days ahead needs regional weather models; one station cannot. v1 covers the near term: the **heat** target says "hot day within 24 h", and the existing heat streak sensor says "we are in a heatwave". |
| **Fog** | Needs a visibility sensor, which stations do not have. The existing `fog_probability` heuristic stays. |
| **Snow** | Needs snow depth or a reliable precipitation-type reading; rare in most climates. |

### Issue and training cadence

- **Issued every 15 minutes**, aligned to :00/:15/:30/:45, on the existing 60 s `_handle_tick` (`sample=True`) path. Not on `_handle_source_change`, which fires on every sensor update.
- **Trained on:**
  - every 15-min sample for rain, gust and storm (short windows);
  - only the on-the-hour samples for frost and heat. Their 12-24 h windows overlap so heavily that 15-min samples add almost no information and would quadruple the weight of each event.
- **Output:** integer percent 0-100. Rain horizons are monotone by construction (section 3).

### How each forecast is checked (labels)

Each issued forecast keeps a small running tally until its window closes, updated on every 60 s tick:

- rain total at start and latest;
- lowest and highest temperature;
- highest gust;
- lightning strikes within proximity;
- the number of valid ticks.

When the window closes:

- **The label is unknown (not "no")** if valid readings cover less than 90% of the window, or HA was down during it. Treating missing data as "it didn't happen" would bias every model low; unknown labels are discarded.
- **Counters (rain, lightning)** sum positive deltas. A decrease is treated as a counter reset (many detectors reset daily), not as negative rain. A jump beyond a sanity cap invalidates the window.
- **Internet lightning (opt-in) has an extra rule.** A Blitzortung counter only changes when strikes happen, so "no change" cannot tell "no storm" from "internet down". A tick counts as valid for storm only while the Blitzortung entities are `available`, and the same 90% coverage rule applies. A silent outage that leaves the entities `available` is a known residual risk (section 9, R20).

### What it is and is not

| It is | It is not |
|---|---|
| A calibrated probability that *this station* measures the event in the window | A radar nowcast or a regional forecast. It sees only what pressure, temperature, moisture, wind and sky reveal at the mast |
| Learned only from this station, so it picks up local quirks (wet wind direction, frost hollows, sea breeze, föhn) | A replacement for national weather services or warnings |
| Honest about its own skill, measured continuously per target | A source of published accuracy numbers |

### Expected behavior by target

Qualitative only; no numbers go in user docs until beta data exists.

| Target | Expectation |
|---|---|
| **Frost** | **The most learnable target.** Radiative frost is driven by clear skies, calm wind, dry air and long nights, all measured locally. Frost brought in by an arriving cold air mass is caught only partly (pressure and wind trend). |
| **Rain** | 1 h is dominated by persistence: if it is raining now, it probably still will be. 3 h / 6 h frontal rain is learnable (falling pressure, moistening air, wet-sector wind). Summer pop-up showers will be predicted poorly. |
| **Gust** | Frontal and pressure-gradient wind events are partly foreseeable from pressure tendency. Thunderstorm downdraft gusts are not. |
| **Heat** | Mostly persistence: yesterday's high predicts today's. Its real value is near the threshold ("will it reach 30 °C tomorrow?"). It must beat persistence to be worth showing (see `bss_vs_persistence`). |
| **Storm** | **The hardest target.** One station has a weak view of atmospheric instability. Expect modest skill, mostly from "lightning nearby in the last hour" and warm, humid, pressure-falling afternoons. |

### Cold start and maturity

**A new install is not useful on day one, and the UI must say so.** Probability sensors are `unknown` (not 0%) until the target has seen enough checked forecasts and enough events.

Maturity is tracked **per target and horizon**:

| State | Meaning | Probability sensor |
|---|---|---|
| `collecting` | Not enough data yet: < 7 days of checked forecasts **or** < 5 events seen | `unknown` |
| `learning` | Publishing numbers, but has not yet proven it beats the station's usual rate | Published, flagged |
| `skilled` | Has seen enough real events since going live **and** beats the station's usual rate by a margin | Published |
| `degraded` | Was `skilled`, but has stopped beating the usual rate recently | Published, flagged |
| `paused` | An input is unavailable, stale, or flagged by the existing drift/stuck detectors | `unknown` |

**What "beats the station's usual rate" means.** The baseline is a lazy forecast that always says the usual chance for this station. For example, if it rains within 3 h 10% of the time here, the lazy forecast always says 10%. The model is scored against that lazy forecast with the Brier skill score (BSS):

- 0 means no better than the lazy forecast.
- 1 means perfect.
- Negative means worse than the lazy forecast.

The "usual chance" is a 30-day running rate, so it follows the seasons and is a fair, non-trivial bar.

**Events are counted, not samples,** because samples are heavily autocorrelated: one rainy afternoon is one piece of evidence, not 96.

Initial gates per target are constants, to be tuned in beta:

| Target | One "event" is | Leaves `collecting` at | `skilled` when, within the last 52 weeks of live data |
|---|---|---|---|
| Rain | A wet period, separated from the previous one by >= 6 h dry | 7 days + 5 events | >= 15 events and BSS > 0.02 |
| Frost | A local night whose minimum reached the threshold | 7 days + 5 frost nights | >= 10 frost nights and BSS > 0.02 |
| Heat | A local date whose maximum reached the threshold | 7 days + 5 hot days | >= 10 hot days and BSS > 0.02 |
| Gust | A gust episode, separated from the previous one by >= 6 h | 7 days + 5 episodes | >= 10 episodes and BSS > 0.02 |
| Storm | A storm episode, separated from the previous one by >= 3 h | 7 days + 5 episodes | >= 10 episodes and BSS > 0.02 |

**`degraded`:** BSS <= 0 over the last 5 weeks, evaluated only when those weeks contain >= 3 events. Otherwise the previous verdict stands. This stops a seasonal target from flapping in its off-season.

**Seasonal targets and honest expectations:**

- Frost, heat and storm are seasonal. A new install in October will not see a hot day or a summer storm until next year, unless Home Assistant has last summer in its history: learning from past history (section 4) is what makes these targets usable in year one.
- Out of season the probability will sit near 0%. That is correct and useful ("no frost tonight"), not a bug.
- Some climates may never reach `skilled` for some targets, for example frost on a frost-free coast or storm in a region with few thunderstorms. The sensor says so (`collecting`, with progress) rather than inventing numbers.
- Rain in a Mediterranean summer (0-2 rain days a month) can sit in `collecting` for 2-3 months without history.

Docs will tell users to gate automations on the sensor's `maturity` attribute being `skilled`, not on the raw probability.

---

## 2. Feature list for v1

There is one shared pool of 23 inputs computed every 15 minutes. Each target uses only the features that are physically relevant to it (a fixed mask per target), plus a bias term. All values are metric and come from values the coordinator already has or from small new buffers.

✓ = used by that target.

| # | Feature | Definition | Rain | Frost | Heat | Gust | Storm |
|---|---|---|:-:|:-:|:-:|:-:|:-:|
| 1 | `mslp` | Sea-level pressure, hPa | ✓ | ✓ | ✓ | ✓ | ✓ |
| 2 | `dp_3h` | 3 h pressure tendency (existing least-squares `trend_3h`) | ✓ | ✓ | | ✓ | ✓ |
| 3 | `dp_24h` | 24 h pressure change (**new** 15-min pressure deque, 97 slots) | ✓ | ✓ | ✓ | ✓ | |
| 4 | `temp` | Temperature, °C | | ✓ | ✓ | | ✓ |
| 5 | `dpd` | Dew point depression T - Td, °C | ✓ | ✓ | ✓ | | ✓ |
| 6 | `dpd_1h` | Change in DPD over 1 h | ✓ | | | | ✓ |
| 7 | `t_1h` | Temperature change over 1 h | ✓ | ✓ | | ✓ | ✓ |
| 8 | `t_3h` | Temperature change over 3 h (evening cooling rate) | | ✓ | ✓ | | |
| 9 | `t_max_24h` | Highest temperature in the last 24 h (existing `temp_high_24h`) | | | ✓ | | |
| 10 | `wind_u` | 1 h mean east-west wind component, m/s | ✓ | | ✓ | ✓ | |
| 11 | `wind_v` | 1 h mean north-south wind component, m/s | ✓ | | ✓ | ✓ | |
| 12 | `wind_speed` | 1 h mean wind speed, m/s | | ✓ | | ✓ | |
| 13 | `gust_1h` | Highest gust in the last 1 h, m/s | | | | ✓ | ✓ |
| 14 | `rain_1h` | log1p(rain in last 1 h, mm) | ✓ | ✓ | | | ✓ |
| 15 | `dry_hours` | log1p(hours since last rain), capped at 48 h | ✓ | | ✓ | | |
| 16 | `cloud_deficit` | 1 - clearness index while the sun is up, else 0 | ✓ | | ✓ | | ✓ |
| 17 | `solar_ok` | 1 if feature 16 is valid, else 0 | ✓ | | ✓ | | ✓ |
| 18 | `last_day_clearness` | Clearness index of the last daytime hour, carried through the night | | ✓ | | | |
| 19 | `last_day_clearness_ok` | 1 if feature 18 is valid, else 0 | | ✓ | | | |
| 20 | `night_frac_12h` | Fraction of the next 12 h with the sun below the horizon (local astronomy math) | | ✓ | | | |
| 21 | `hour_sin` | sin(2 pi * local hour / 24) | ✓ | ✓ | ✓ | ✓ | ✓ |
| 22 | `hour_cos` | cos(2 pi * local hour / 24) | ✓ | ✓ | ✓ | ✓ | ✓ |
| 23 | `lightning_1h` | log1p(strikes within proximity in last 1 h) | | | | | ✓ |
| | **Inputs per target** | | **14** | **14** | **13** | **10** | **13** |

### Why each target gets what it gets

- **Rain:** the same 14 as rev 1.
  - Saturation and its trend: `dpd`, `dpd_1h`.
  - The pressure story: `mslp`, `dp_3h`, `dp_24h`. 24 h change cancels the twice-daily pressure tide that distorts 3 h tendency, especially at low latitudes.
  - The station's own wet wind direction: `wind_u`/`wind_v`. This replaces the hand-coded `_RAIN_WIND_BIAS` quadrants with local truth.
  - Persistence: `rain_1h`, `dry_hours`.
  - Cloud: `cloud_deficit`.
  - The daily cycle of showers: hour of day.
- **Frost:** the radiative-cooling recipe.
  - Clear sky: `last_day_clearness`, because at night the station has no sky reading, so the last daylight one is carried forward.
  - Calm wind: `wind_speed`. A linear model cannot learn "calm" from direction components, so speed is a separate input.
  - Dry air: `dpd`. The dew point sets how far the temperature can fall.
  - Long nights: `night_frac_12h`. This also carries the season.
  - Starting point and cooling rate: `temp`, `t_3h`.
  - Wet ground and cloud: `rain_1h`.
- **Heat:**
  - Persistence: `t_max_24h`, `temp`.
  - Sunshine and dry ground: `cloud_deficit`, `dry_hours`.
  - Warm-air advection and föhn: `wind_u`/`wind_v`.
  - Settled high pressure: `mslp`, `dp_24h`.
- **Gust:**
  - Pressure gradient and approaching fronts: `mslp`, `dp_3h`, `dp_24h`.
  - Current wind and gustiness: `wind_speed`, `gust_1h`.
  - Windy direction: `wind_u`/`wind_v`.
  - Frontal passage: `t_1h`.
- **Storm:**
  - Warm, moist air: `temp`, `dpd`, `dpd_1h`.
  - Falling pressure: `dp_3h`.
  - Building cloud: `cloud_deficit`.
  - Outflow: `t_1h`, `gust_1h`.
  - Afternoon timing: hour of day.
  - Persistence: `lightning_1h`, `rain_1h`.

### Missing data rules

- If temperature, humidity, pressure, wind or the rain total is unavailable or flagged, no sample is issued and the affected targets go to `paused`.
- Solar/lux is optional: features 16-19 use 0 plus the `*_ok` = 0 indicator, so the model can tell "clear" from "no data".
- `lightning_1h` comes from the mapped hardware detector or, with the opt-in, from Blitzortung. If that source is unavailable, only the storm target pauses.
- `dp_24h` is unavailable for the first 24 h of a brand-new install; samples are skipped until it exists. Restarts restore the deque, and learning from past history makes this moot.
- The 1 h and 3 h changes and the 1 h wind means come from the pending buffer (section 3), not new deques.

### Trimmed from the original 16-feature sketch

| Dropped | Reason |
|---|---|
| RH | Nearly collinear with DPD; DPD is the more physical form |
| RH slope | Replaced by DPD slope (`dpd_1h`) |
| Rain rate | Derived from the same gauge via the Kalman filter; redundant with `rain_1h` |
| Rain 3 h, rain 24 h | Replaced by `dry_hours` |
| Temp slope 3 h, wind speed, gust | **Kept, but only where they matter**: frost/heat (`t_3h`), frost/gust (`wind_speed`), gust/storm (`gust_1h`). Rain does not use them |
| Solar deficit | **Kept** as `cloud_deficit` + `solar_ok`, plus the night-time carry-forward for frost |

**Added** relative to the sketch: wind direction (u/v), hour of day, night fraction, last-daylight clearness, 24 h max, lightning.

**Deferred to v2:** day-of-year sin/cos. It needs about a year of data to learn anything. Until then, the learning-rate floor and `night_frac_12h` handle seasons.

---

## 3. Model choice

### One small online logistic regression per target and horizon

There are 7 models: `rain_1h`, `rain_3h`, `rain_6h`, `frost_12h`, `heat_24h`, `gust_3h`, `storm_3h`. Each is:

- an L2-regularized logistic regression over its feature mask plus a bias term (11-15 weights; about 100 weights in total);
- trained online by SGD with **AdaGrad** per-weight step sizes and a **learning-rate floor**, so it never stops adapting to the seasons. Gradient clipped; weight-norm bounded.

**Shared standardizer:** a per-feature running mean and variance for the pool of 23 inputs. It uses Welford during the first 7 days, then a slow EMA with a half-life of about 30 days. z-scores are clipped to +/-5, so a single sensor spike cannot blow up a weight.

**Monotone rain horizons:** the events are nested (rain within 1 h implies rain within 3 h), so after prediction `p3 = max(p3, p1)` and `p6 = max(p6, p3)`.

### Why this fits inside a Home Assistant integration

| Requirement | How it is met |
|---|---|
| No heavy dependencies | Pure Python `math`. `manifest.json` `requirements` stays `[]`. No numpy, scikit-learn or river |
| No GPU, tiny CPU | Predicting is 7 dot products of length <= 15 every 15 min; training is the same on label arrival. Microseconds, so it runs inline in the synchronous `_compute()` callback with no executor hop |
| Async-safe | No awaits in the hot path. Storage I/O goes through HA `Store` (executor-backed). Only learning from past history (section 4) touches the executor, and it trains on a copy that is swapped in on the loop |
| Probabilities, not scores | Log-loss training yields probabilities directly, with no class weighting (class weighting would destroy calibration for rare events like storms) |
| Stable online learning | Convex loss, no local minima, no divergence with clipping |
| Explainable without an LLM | Each feature's signed contribution w_i * z_i gives a deterministic "why": the top 3 factors become translated attribute keys (e.g. `clear_sky`: raises, `windy`: lowers). This replaces the abandoned LLM narrative |
| Small, bounded state | About 100 weights + 100 AdaGrad accumulators + 46 standardizer floats |

### Pending buffer (delayed outcomes)

- At each issue time, append `{ts_utc, raw_features[23], issued probabilities, window tallies}`.
  - Quarter-hour entries live 6 h (the longest short window).
  - On-the-hour entries live 24 h (for heat).
  - The buffer is capped at about 48 entries.
- On each 60 s tick, update the running tallies (rain, min/max temperature, max gust, lightning, valid ticks) of every open entry.
- When a target's window closes for an entry:
  1. Apply the label rules from section 1. If the label is invalid, discard it.
  2. **Score first:** add the issued probability to that target's prequential aggregates.
  3. **Then train:** one SGD step using the stored raw features standardized with current stats.
- The buffer doubles as short history for the 1 h and 3 h changes and the 1 h wind means.

### Scoring and baselines (per target and horizon)

Over a 52-week window of **weekly** aggregates:

- Brier score for the **model**.
- Brier score for the **usual rate** (30-day running base rate), used for BSS.
- Brier score for **conditional persistence**, the "same as now" forecast. This is the bar the model must clear where persistence is strong (rain 1 h, heat); reported as `bss_vs_persistence`. "Now" means:

  | Target | "Now" condition |
  |---|---|
  | Rain | Wet now |
  | Frost | Last 24 h minimum reached the threshold |
  | Heat | Last 24 h maximum reached the threshold |
  | Gust | Last 3 h gust reached the threshold |
  | Storm | Lightning nearby in the last 1 h |

- Reliability histogram, 10 bins, for calibration plots.
- Diagnostic only: Brier score of the existing heuristics where one exists, to inform any future blend decision:
  - `rain_probability / 100` for rain;
  - `thunderstorm_risk_index / 100` for storm.

### Drift guard (kept, trimmed to what earns its keep)

- **Input gate:** reuse the existing staleness, spike and drift detectors (`KEY_SENSOR_QUALITY_FLAGS`, `KEY_SENSOR_DRIFT_FLAGS`, `DRIFT_STUCK_BUCKET_*`). A flagged input pauses the targets that use it. No second drift detector.
- **Label gate:** as in section 1.
- **Numeric guard:** after each update, a non-finite or out-of-bound weight restores that model's last daily checkpoint and logs once.
- **Skill guard:** the `degraded` state. There is no automatic reset; the user decides via the reset service.
- Not included: statistical concept-drift detectors (ADWIN, Page-Hinkley). Too much machinery for 100 weights.

### Sketch components not carried into v1

| Component | Decision | Reason |
|---|---|---|
| Platt calibration | **Dropped** | Platt fits a sigmoid on a margin score. A log-loss LR already *is* that sigmoid, so stacking a second adds parameters for no expected gain. Monitor reliability bins, and add isotonic calibration only if beta data shows systematic miscalibration |
| k-NN analog matcher | **Deferred (v2)** | Needs a stored feature archive (storage growth, frequent large writes), is only meaningful after months of data, and costs O(N) per query. LR contributions already provide the explanation |
| Kalman trend model | **Out (v2)** | For the temperature curve |
| Learning-rate number entity | **Dropped** | Not a user-meaningful knob, and its old unique_id is on the orphan-cleanup list |

### Alternatives considered

- **Gradient-boosted trees / scikit-learn / river:** a heavy dependency on HA OS, batch training needs an archive, and the gain is unproven at this data scale.
- **One multi-output model:** couples targets with very different seasons and event rates; separate small models are simpler to reset, gate and explain.
- **Naive Bayes:** poorly calibrated with correlated inputs.

---

## 4. Persistence

### Store

A new, separate store, created only when the feature is enabled:

`Store(hass, 1, f"ws_core_{entry_id}_pattern_forecast")`

Why not extend `LearningState`: `LearningState.from_dict()` discards **everything** (streak records, FWI codes, calibration bias) on any schema-version mismatch. Pattern Forecast will change its feature set over time; that must never wipe a user's dry-streak record, and a learning-state bump must never wipe trained models. Separate stores also give independent reset.

### Payload

| Key | Content | Bound |
|---|---|---|
| `schema_version` | Store layout version | - |
| `pool_id` | Feature pool definition version (e.g. `"pool-v1"`) | - |
| `source_fingerprint` | Hash of the mapped source entity IDs plus elevation | - |
| `standardizer` | `mean[23]`, `var[23]`, `n` | Fixed |
| `models.<target_id>` | `label_id` (definition + threshold, plus data source for storm, e.g. `"frost-v1:thr=0.0"`, `"storm-v1:km=15:src=internet"`), `mask_id`, `w[]`, `g2[]`, `n_updates`, `checkpoint{w, g2, at}`, `maturity`, `events{live, history}` | 7 entries, fixed |
| `pending` | Pending buffer entries | <= 48 |
| `pressure_24h` | `[ts, hPa]` at 15 min | <= 97 |
| `scoring.<target_id>` | Weekly aggregates (n, Brier model/usual/persistence/heuristic, events) | <= 53 weeks each |
| `reliability.<target_id>` | 10 bins x (count, sum p, sum y) | Fixed |
| `base_rate`, `cond_freq` | Per target | Fixed |
| `history_learn` | `done_at`, `span_days`, `status` and `reason` per target | Fixed |

Estimated size: **30-50 KB JSON per config entry**, and nothing grows with time. The `models` dict is keyed by target id, so the v2 temperature curve is just another key.

### Per-target reset (key design point)

Each model carries its own `label_id` and `mask_id`. On load, and whenever options change:

| Change | Effect |
|---|---|
| **A threshold changes** (e.g. the user raises `thresh_freeze_c` to 2 °C for ground frost) | Only `frost_12h` resets and re-learns from history. Rain, heat, gust and storm are untouched |
| **A target's feature mask changes** in a future release | Only that target resets |
| **The storm data source changes** (hardware detector added or removed, internet-lightning opt-in toggled) | Only `storm_3h` resets. Local and internet lightning differ in range and detection rate, so their labels are not interchangeable |
| **The pool definition or `source_fingerprint` changes** (different station mapped, elevation edited) | Everything resets; the standardizer would be wrong |

### Write and load

- **Write:** on the existing hourly backstop (`_async_maybe_save_learning`), on `async_stop`, and once after learning from history. A hard crash loses at most 1 h of samples. HA `Store` writes atomically (temp file + rename).
- **Load:**
  - Validate `schema_version`, `pool_id`, `source_fingerprint`, each model's ids and array lengths, and that every number is finite.
  - A per-model mismatch resets that model; a global mismatch resets all. Either way it logs one warning and re-learns from history.
  - Unreadable JSON starts fresh, following the `async_load_learning()` pattern.
- **Restart mid-window:**
  - Open entries whose windows span the downtime fail the 90% coverage rule and are discarded.
  - Entries older than their longest window are dropped.

### Cold start: learning from past history

Home Assistant's recorder already keeps **long-term statistics**: hourly mean, min and max per sensor, kept indefinitely by default, stored locally in SQLite or MariaDB. Pattern Forecast uses them so it does not start from zero. This ships in v1 (decided).

1. **On first enable, and after any reset,** a background job reads up to 365 days of hourly statistics with `statistics_during_period` via `get_instance(hass).async_add_executor_job`:

   | Data | Statistic | Used for |
   |---|---|---|
   | Temperature | mean / **min** / **max** | Features; **frost labels use the hourly min; heat labels use the hourly max** |
   | Humidity, pressure, wind speed | mean | Features |
   | Gust | **max** | Gust labels |
   | Rain total | state/sum | Rain labels |
   | Lightning count from the active storm source (local detector, or Blitzortung with the opt-in), if it has statistics | state/sum | Storm labels (approximate) |

2. **Replay:**
   - Build hourly samples through the same normalization path as live data (unit conversion, current `cal_*` offsets).
   - Label each target, and train copies of the models in the executor; swap them in on the event loop.
3. **Approximations:**
   - *Wind direction:* averaging degrees across 0/360 is meaningless, so replayed samples train with `wind_u`/`wind_v` masked (no gradient).
   - *Storm:* replayed storm labels have no distance filter (hourly mean distance is meaningless), so they are approximate.
   - *Short changes:* the 1 h changes are approximated from hourly means.
4. **What replayed samples count for:**
   - They count toward leaving `collecting` and they train the weights.
   - They do **not** count toward `skilled`, because skill must be proven on live 15-min data.
5. **The big win:** with a year of history, every seasonal target (frost, heat, storm) has already seen one season on day one. A user enabling the feature in October gets a frost model that remembers last winter.
6. **When history is unavailable:** a source without `state_class` (no long-term statistics), an excluded entity, or short history means it uses what exists. The reason is reported per target (e.g. `history: unavailable (no statistics for sensor.x)`). Without history it is a pure cold start: live samples begin once `dp_24h` exists.

Learning from history is also the migration path after any reset, so ws_core never needs its own raw-data archive: HA already keeps one.

---

## 5. New entities

All are gated by `CONF_ENABLE_PATTERN_FORECAST` through `_FEATURE_TOGGLE_MAP`, and defined as `WSSensorDescription` entries in `entity_descriptions.py`. New `KEY_PATTERN_*` constants go in `const.py`, with typed fields in `models.WsData`.

| Entity | State | Created |
|---|---|---|
| `sensor.ws_pattern_rain_1h` | % (0-100), `MEASUREMENT`, precision 0 | Always |
| `sensor.ws_pattern_rain_3h` | same | Always |
| `sensor.ws_pattern_rain_6h` | same | Always |
| `sensor.ws_pattern_frost_12h` | same | Always |
| `sensor.ws_pattern_heat_24h` | same | Always |
| `sensor.ws_pattern_gust_3h` | same | Always |
| `sensor.ws_pattern_storm_3h` | same | With a mapped local lightning detector, or with the internet-lightning opt-in (friendly name then ends in "(internet lightning)"; entity ID unchanged, so automations survive a source switch) |
| `sensor.ws_pattern_forecast_status` | enum: `collecting` (still training), `waiting` (required inputs missing), `learning` (some published, none skilled), `active` (at least one skilled) | Always |
| `sensor.ws_pattern_forecast_skill` | Number of targets currently `skilled` | `EntityCategory.DIAGNOSTIC`, disabled by default |

All probability sensors are `unknown` while their target is `collecting` or `paused`.

**Probability sensor attributes** (identical shape on every target, so one dashboard card works for all):

- `target`, `horizon_h`
- `data_source`: `local`, or `internet` (storm only, with the opt-in)
- `threshold` and `threshold_unit`, in the user's display units
- `maturity` (the value automations gate on), `progress_pct` (while collecting)
- `brier_skill`, `usual_rate`
- `issued_at`, `valid_until`
- `top_factors`: up to 3 entries of `{factor, effect}`, deterministic translated keys only, no free text. `effect` is `raises` or `lowers`. Factor keys:

  | Factor keys | Typical target |
  |---|---|
  | `pressure_falling`, `pressure_rising`, `air_near_saturation`, `dry_air`, `wet_wind_sector`, `raining_now`, `long_dry_spell`, `cloudy` | Rain |
  | `clear_sky`, `calm_wind`, `long_night`, `already_cold`, `cooling_fast` | Frost |
  | `hot_yesterday`, `sunny`, `warm_wind_sector` | Heat |
  | `windy_now`, `gusty_now` | Gust |
  | `lightning_nearby`, `warm_and_humid` | Storm |
  | `afternoon`, `night` | Any |

- `samples_trained`

**Status attributes:**

- `per_target`: maturity, progress_pct, events_live, events_from_history, events_required and BSS for each target
- `history_learn`: status, span and reason per target
- `internet_inputs`: the targets currently using internet data (empty, or `[storm_3h]`)
- `last_trained_at`

**Skill attributes:** per target:

- `brier`, `brier_usual`, `brier_persistence`, `brier_heuristic`
- `bss`, `bss_vs_persistence`
- `n_scored`, `events`
- `reliability` bins

**Switch:** `switch.ws_enable_pattern_forecast`, a `WSFeatureDesc` in `FEATURE_SWITCHES`, the same pattern as the other features.

**Services (no new service):**

- `reset_learning_state`: add target option `pattern_forecast`. It deletes the store, returns everything to `collecting`, and re-learns from history. `all` includes it.
- `export_learning_state`: also logs a Pattern Forecast summary (maturity and skill per target, named weights).

**Diagnostics download:** add a `pattern_forecast` section with maturity and skill per target, named weights, standardizer stats, and whether internet lightning is in use. It contains no location data.

**Deliberately not added:**

- Binary "likely" sensors: the threshold is the user's call, via a template or blueprint.
- `weather.py` forecast injection.
- Per-target maturity sensors: maturity is an attribute, keeping the entity count at 9.
- A number entity for the learning rate.

**Translations:** entity names, enum states and `top_factors` keys in `strings.json` and all 8 `translations/*.json`.

**Docs and blueprints:**

- Docs examples: a frost-protection automation gated on `maturity == skilled`, and a dashboard card showing all targets with their maturity.
- The existing `frost_alert` / `freeze_alert` blueprints gain an optional early-warning input. If the user picks `sensor.ws_pattern_frost_12h` and a probability threshold, the alert can fire before the temperature actually drops, but only while that sensor's `maturity` is `skilled`. Left empty, the blueprints behave exactly as today.

---

## 6. Config flow additions

- **One boolean** turns on every target: `CONF_ENABLE_PATTERN_FORECAST = "enable_pattern_forecast"`, `DEFAULT_ENABLE_PATTERN_FORECAST = False`. It goes in the `features` step (setup) and the options flow, next to `enable_nowcast`.
- **No new threshold fields.** Every target reuses an existing setting (`thresh_freeze_c`, `thresh_heat_day_c`, `thresh_wind_gust_ms`, `lightning_proximity_km`), so there is one definition of "frost", "hot day" and "strong gust" across the integration. Horizons, the rain threshold, learning rates and maturity gates are `PATTERN_*` constants in `const.py`.
- **Storm data source:**
  - **With a hardware lightning detector mapped,** the storm target uses it automatically. No question is asked, and Blitzortung is ignored.
  - **Without one, but with Blitzortung entities discovered,** an extra config step `pattern_forecast` appears after `features`, in both setup and options. It follows the existing chained-step pattern (like `sea_temp`) and holds one boolean:
    - `CONF_PATTERN_STORM_INTERNET_LIGHTNING = "pattern_storm_internet_lightning"`, `DEFAULT_PATTERN_STORM_INTERNET_LIGHTNING = False`.
    - Field description (en): "Use internet lightning data (Blitzortung) for the storm forecast. You don't have a lightning detector, so the storm forecast can only work with data downloaded from the Blitzortung community network. All other forecasts stay 100% local. Off by default."
  - **With neither,** no storm target is created. The status sensor attributes say why.
- **No per-target toggles.** A target the user does not want (e.g. frost in the tropics) is hidden by disabling its entity in HA. It keeps training in the background at negligible cost, so re-enabling it shows a warm model.
- **Field description (en):** "Learns from your station's own history to estimate the chance of rain, frost, a hot day, strong gusts and (with a local lightning detector) thunderstorms over the next hours. Each forecast shows numbers once it has seen enough examples at your station, often right away if Home Assistant already has long-term history of your sensors. Runs entirely on this machine."
- **No config entry version bump.** It is a new optional key, read with its default, the same as every other `CONF_ENABLE_*`.

### Default: **off**, and why

1. **Upgrade safety.** Existing installs should not gain up to 9 entities, a new storage file and a recorder query on an upgrade.
2. **First impressions.** On by default, new users would see `unknown` sensors for days to months and conclude the integration is broken.
3. **The usual argument for default-on (lost learning time) is neutralized** by learning from past history.
4. **Repo convention.** Nearly every non-core feature is opt-in.

Revisit default-on in a later minor, once beta stations show typical time-to-`skilled`.

---

## 7. Explicitly out of scope for v1

- **Temperature curve forecasting** (actual degrees over the next hours; the Kalman trend model). v2; the store reserves a model slot for it.
- **Hail, fog, snow, multi-day heatwave** (reasons in section 1).
- **Any LLM narrative, text generation, or cloud AI API.** Permanently, not just in v1. The "why" is the deterministic `top_factors` attribute.
- **Any network-derived input or label,** except the storm opt-in above: Open-Meteo, nowcast, radar, neighbor stations, NWP blending, and Blitzortung for any target other than storm. This includes feeding Pattern Forecast into `rain_probability_combined` or the Brier blend; that is a v2 decision once skill data exists.
- **Cross-station or transfer learning,** shared priors, model import/export between users, any skill telemetry.
- **k-NN analog matching;** a separate calibration layer (Platt/isotonic).
- **Amount or intensity predictions** (how much rain, how cold, how strong); horizons other than those listed; minute-level timing.
- **`weather` entity integration;** binary "likely" sensors; new blueprints (only the optional frost early-warning input on the two existing frost/freeze blueprints is in scope).
- **User-tunable hyperparameters;** per-target enable toggles.
- **Day-of-year seasonality features.**

---

## 8. Complexity and effort estimate

Baseline from recent history: a typical ws_core feature PR is **about 500-750 added lines across 12-15 files**:

| PR | Lines | Files |
|---|---|---|
| Adaptive calibration (`06717d9`) | 487 | 12 |
| Climate normals (`6ad1f5e`) | 585 | 12 |
| Snow (`efdfe08`) | 741 | 15 |

**Pattern Forecast with five targets: about 3,400-4,000 added lines including tests. Roughly 5-6x a typical feature.** The engine is built around a small **target registry**, where each target declares its window, label rule, feature mask, event rule and threshold source. Adding a target after the first is then mostly declaration plus tests, not new machinery.

### Already landed (not part of the Pattern Forecast PR)

These prerequisites were done in commit `7719020` and need no further work:

- **Off switch for the hourly neighbor-QC fetch:** `enable_neighbor_qc`, on by default, plus `switch.ws_enable_neighbor_qc`, strings in all 8 languages and tests. ws_core can now run fully offline.
- **Corrected local-first claims** in the README, the docs homepage and the Data & Privacy Disclosure (section 0).
- **This spec.**

### One PR

All of Pattern Forecast ships as **a single PR** for 2.11.0. Nothing is split into follow-ups.

It is built as four ordered commits so it can be reviewed commit by commit, and so each commit leaves the test suite green:

| Commit | Contents | Est. lines (code + tests) |
|---|---|---|
| **1. Engine** | New pure module `pattern_forecast.py` (no HA imports): feature pool, standardizer, target registry (5 targets / 7 models), LR + AdaGrad, pending buffer with window tallies, labeling, prequential scoring, maturity, per-target reset, (de)serialization with validation. Tests on synthetic weather series per target | ~900 + ~900 |
| **2. Integration** | Coordinator hooks (issue tick, 24 h pressure deque, night fraction, last-daylight clearness, store load/save, data keys), `const.py`, 9 sensor descriptions, feature switch, config + options flow including the internet-lightning step, lightning-source locality check and labelling, `strings.json` + 8 translations, reset/export service targets, diagnostics | ~700 + ~400 |
| **3. Learning from history** | Recorder long-term statistics replay (executor, masking, per-target labels, swap-in) | ~350 + ~200 |
| **4. Docs and blueprints** | `docs/guides/pattern_forecast.md` (including a table comparing the four "chance of rain" style sensors), `sensors.md` rows, mkdocs nav, README feature entry, example automations and dashboard card. Also an optional early-warning trigger on `sensor.ws_pattern_frost_12h` in the existing `frost_alert` / `freeze_alert` blueprints. CHANGELOG entry and manifest version bump to 2.11.0 | ~200 + ~50 |

**Total: about 3,400-4,000 lines.** The PR is large on purpose, to keep the feature in one place. Commit 1 is self-contained and holds most of the logic, so reviewers can read the engine and its tests first and then check that commits 2-4 only wire it in.

**Key tests:**

1. For each target, learns a planted rule (e.g. clear + calm + dry -> frost) and reaches BSS > 0.
2. Pure noise with a fixed base rate: BSS stays near 0 and the target never reaches `skilled`.
3. Rain horizons are monotone.
4. Gaps and downtime discard labels rather than labeling them "no".
5. Counter resets are handled.
6. A threshold change resets only its target.
7. Blitzortung is used only for storm, only with the opt-in, only when no hardware detector is mapped, and always labelled.
8. Store round-trip equality, plus corrupt or mismatched stores starting fresh.
9. No network imports, and it runs with the forecast provider disabled.
10. Compute-time budget, via the existing `last_compute_ms`.

**Validation timeline (the real calendar constraint):** a beta starting now (late October) gets live validation of **rain, frost and gust** over the winter. **Heat and storm** cannot be validated live until next summer. For those, beta stations (the maintainer's Shelly WS90 included) replay summer 2026 from recorder history and score it prequentially. Heat and storm ship labelled "beta" in the docs until a summer of live data confirms them. Calendar time is dominated by this, not by code.

---

## 9. Risk list

| # | Risk | Likelihood / impact | Mitigation |
|---|---|---|---|
| R1 | **Cold-start usefulness:** weeks to a full season before numbers; users assume it is broken | High / Medium | `unknown` (not 0%) during `collecting`, with progress; status sensor; learning from past history; default off; honest docs and config text |
| R2 | **Low skill even when mature**, especially storm, convective rain, and heat beyond persistence | High / Medium | Skill vs. the usual rate and vs. persistence exposed per target; `skilled` gate; no accuracy claims in README; positioned as a complement to official forecasts and warnings |
| R3 | **Rare or seasonal events** (frost on mild coasts, storms in quiet regions, rain in arid summers): a target may never reach `skilled` | High / Low | Event-based gates; seasonal-safe `degraded` rule; documented as expected, not a bug; entity can be disabled |
| R4 | **Label quality, precipitation:** piezo false counts (WS90), clogged or stuck buckets, unheated gauges delaying snow melt into the wrong window | Medium / High | 0.2 mm threshold; coverage rule; counter-reset handling; reuse the `DRIFT_STUCK_BUCKET_*` detector to pause; never label missing as "no" |
| R5 | **Label quality, temperature:** sensor siting decides frost and heat labels. A passive shield (like the WS90's) can read high in strong sun with light wind, inflating "hot day" labels; mast height misses ground frost | Medium / Medium | Labels deliberately reflect what *this* station reads (consistent with its alerts and streaks); docs explain siting and the ground-frost threshold tip; existing calibration offsets apply |
| R6 | **Label quality, lightning:** AS3935-type detectors false-trigger on electrical noise; distance estimates are coarse | Medium / Medium | >= 2 strikes within proximity; proximity uses the existing setting; history-replayed storm labels count only toward `collecting` |
| R7 | **State corruption:** partial write, NaN weights, schema-valid nonsense | Low / High | HA `Store` atomic writes; validation on load (lengths, finiteness, ids); per-model checkpoint and auto-restore; per-model or full reset + re-learn as the last resort |
| R8 | **Model poisoning by bad input** (spike, miswired source) | Medium / Medium | Input gate on existing spike/drift flags; z-clip +/-5; gradient clip; weight bound |
| R9 | **Memory and storage growth** | Low / Low | Every buffer capped (pending <= 48, pressure <= 97, scoring <= 53 weeks per target); no raw archive; about 30-50 KB per entry. The history replay holds about 100k floats transiently, capped at 365 days, released after |
| R10 | **Event-loop blocking** | Low / High | Inline work is microseconds; replay reads and trains in the executor on copies; test with a compute-time budget |
| R11 | **Backward compatibility on schema change** | Certain over time / Medium | Per-target `label_id` / `mask_id` and global `pool_id`: only what changed re-learns, via history replay; never reinterpret old weights; CHANGELOG notes which targets re-learn; entity unique_ids stable; `LearningState` untouched |
| R12 | **Settings changes** (threshold edits, different station mapped, elevation edited) | Medium / Medium | Threshold edit resets only its target; source or elevation change resets all; small shifts (calibration offsets, auto-calibration nudges) are absorbed by the EMA standardizer |
| R13 | **Local-contract leak via Blitzortung** (internet data reaching a target silently or by default) | Low / High | Opt-in off by default; hardware always wins; the source's integration is checked in the entity registry; Blitzortung feeds only the storm model; `data_source` / `internet_inputs` labels; covered by tests |
| R14 | **Key collision with the orphan cleanup** (`forecaster` keys deleted on every setup) | Low / High | Naming rule in section 0; unit test asserting no new key intersects `DEPRECATED_KEYS_FORECASTER` |
| R15 | **User confusion** among overlapping sensors (`rain_probability`, `rain_probability_combined`, nowcast, Pattern Forecast rain; thunderstorm risk vs. Pattern storm; frost alert vs. Pattern frost) | High / Low | Docs comparison table (source, horizon, local or cloud, learned or rule-based); distinct "pattern" naming |
| R16 | **Seasonal shift** (a model trained in one season meets the next) | Medium / Medium | AdaGrad learning-rate floor keeps adapting; `night_frac_12h` carries season for frost; `degraded` state surfaces it; day-of-year features in v2 |
| R17 | **Time handling** (DST, clock jumps) | Low / Medium | Windows and labels in UTC; local time only for hour features and the night/date event definitions |
| R18 | **Recorder edge cases** (excluded entities, MariaDB vs SQLite, purge, statistics unit changes) | Medium / Low | Replay is best-effort per target with a reported reason; the feature works without it; units converted via the same normalization path as live data |
| R19 | **Scope:** five targets make v1 large and the validation season-bound | Medium / Medium | Target registry keeps per-target cost low; heat and storm labelled beta until a summer of live data; a target can be dropped from the registry before release without touching the others |
| R20 | **Silent internet outage with the Blitzortung opt-in:** the entities stay `available` while no data arrives, so quiet hours get labelled "no storm" | Medium / Medium | Storm ticks are valid only while the Blitzortung entities are `available`; if the coordinator can see a feed-health signal (last-update age of the integration), treat a stale feed as unavailable; documented as lower-trust labels; does not affect any other target |

---

## Open questions for review

1. **Rain threshold for the WS90:** 0.1 or 0.2 mm? Answer from your own recorder data: check the smallest step the rain total moves by (the resolution), and how often lone single counts happen while humidity is low (likely false counts).
2. **"Skilled" bars:** are 10-15 real events plus beating the usual rate by 2% the right bars? Revisit after the beta with real numbers.
3. ~~Ship learning from past history in the same release?~~ **Decided:** yes. Everything ships in one PR for 2.11.0 (section 8).
4. ~~README: correct the local-first claims before this feature is announced?~~ **Done** (section 0), including the new off switch for the neighbor-QC fetch.
5. ~~Blitzortung: exclude entirely, or allow as a labelled opt-in?~~ **Decided:** allowed as an explicit opt-in for storm only, off by default, labelled (section 0).

---

## Implementation notes

Decisions made while building the four commits where the spec was ambiguous or silent. Each names the commit that made it.

### Commit 1 (engine)

- **`PATTERN_*` algorithm constants** (rates, gates, caps, priors) are in `const.py` from commit 1 because the engine imports them. The `CONF_` / `DEFAULT_` / `KEY_` names arrive with the wiring in commit 2.
- **Engine API.** `observe(ts, Observation)` runs on every 60 s tick (tallies, events, label resolution); `issue(ts, Instant)` runs on the 15-minute marks. Timestamps are UTC epoch seconds. The local UTC offset is passed in so frost nights and hot days use the local date.
- **Extra persisted keys** beyond the spec table: `recent_bins` (thirteen 15-minute bins, the short history behind the 1 h / 3 h changes and 1 h wind means, 3 h of coverage), `episodes`, `first_obs_ts`, `last_rain_ts`, `last_trained_at`. All are bounded. The standardizer keeps a per-feature count list instead of a single `n`, because masked features update less often.
- **Warm-up.** `dpd_1h`, `t_1h`, `t_3h`, the 1 h wind means, `gust_1h`, `rain_1h` and `lightning_1h` need at least three bins in the last hour (or a bin near 1 h / 3 h ago). A target whose mask contains a missing feature publishes nothing for that issue (`reason: waiting_for:<feature>`) and opens no pending entry. Exposed as `paused` only once the target has left `collecting`; before that it stays `collecting`.
- **`dp_24h`** is the change in sea-level pressure versus the 15-minute slot 24 h ago (tolerance +/-7.5 min).
- **`solar_ok`** is 1 only while the sun is up and a clearness index exists, so at night `cloud_deficit = 0` and `solar_ok = 0`.
- **Downtime discards labels.** Besides the 90% coverage rule, a gap of more than 15 minutes between ticks, or a restart, marks every window still open as unlabellable, so a tail that was never observed is never called "no" (the spec's "or HA was down during it"). Shorter holes only reduce coverage.
- **Float slack.** Rain and strike sums compare with a 1e-6 tolerance, because sums of 0.2 mm tips land at 0.19999999999999996.
- **Event definitions** (maturity counts these, independent of forecast samples): rain, gust and storm are episodes separated by 6 h, 6 h and 3 h without activity; an episode counts once its rain reaches the rain threshold, its first gust above threshold, or its second strike within proximity. A frost night is a noon-to-noon local window containing a reading at or below the freeze threshold; a heat day is a local date with a reading at or above the heat threshold.
- **Lightning proximity** filters the strikes of a tick by the latest strike distance reading when a distance sensor exists; without one every strike counts.
- **Scoring details.** Weekly rows are keyed by the week the label was resolved. The usual rate and each conditional-persistence rate are running rates (shrunk toward a per-kind prior at first, about a 30-day EMA later). Persistence falls back to the usual rate until its condition has 10 samples. Brier skill is reported only once the window has seen at least one event.
- **Initial bias** of every model is the logit of a per-kind prior rate, so the first published numbers are not 50%.
- **Explanation.** `top_factors` accumulates the signed contributions of the features behind each factor key; a factor is reported only when its condition is actually present (the sign of the standardized value matches), and the two hour-of-day features map to `afternoon` (12-18 h) or `night` (21-05 h).
- **Test cadence.** The synthetic-station tests tick every 5 minutes, so `PatternEngine` takes a `tick_cap_s` argument (default 180 s) for the longest gap that still counts as coverage.

### Commit 2 (integration)

- **Code layout.** The coordinator-side logic lives in two new modules, `pattern_runtime.py` (reads the normalized readings, feeds the engine, builds entity attributes, loads and saves the store, diagnostics summary) and `pattern_sources.py` (storm source decision, strict Blitzortung registry check, source fingerprint). The coordinator only constructs `PatternRuntime`, calls `update()` from `_compute()`, and loads and saves it next to the learning state. A failing engine is logged once and never breaks the rest of the integration.
- **Issue timing.** `update(..., sample=True)` always feeds `observe()`; `issue()` runs on the first sample tick inside the first 5 minutes after a :00/:15/:30/:45 mark, once per mark. `_handle_source_change` passes `sample=False` and does neither.
- **Storm source.** "A hardware detector is mapped" means the lightning strike counter source is mapped, regardless of the `enable_lightning` toggle. The opt-in alone selects `internet`, so a slow Blitzortung start never silently drops the storm sensor; whether Blitzortung is actually present is checked when data is read: the entity must belong to the `blitzortung` platform in the entity registry (an entity id prefix is not enough), must not be disabled and must not be `unavailable`, rescanned every 15 minutes while missing. Until then storm ticks are invalid, so the storm target stays `collecting` or `paused` and the status sensor's `storm_target` attribute says it is waiting for the integration. The config-flow question only appears when Blitzortung entities exist at that moment. The feed-health signal of R20 was not added: Blitzortung's entities only update on strikes, so their last-update age cannot tell a quiet sky from a dead feed.
- **Idle detectors.** A local hardware counter that reports `unknown` (many detectors do while idle) is read as "no new strikes" once a numeric value has been seen; `unavailable` stays invalid. Internet counters get no such leniency.
- **Clearness input.** `cloud_deficit` and `solar_ok` come from the mapped solar radiation sensor, or from the illuminance sensor times `LUX_TO_WM2_FACTOR`, plus `sun.sun` elevation; they do not depend on the comfort-indices toggle. `last_day_clearness` is a roughly 1 h EMA of the clearness index while the sun is more than 10 degrees up; the engine remembers the last value (persisted as `last_day_clear`, valid for 26 h) so frost keeps its sky signal through the night and across restarts.
- **Night fraction** uses a new low-precision solar position routine (`algorithms.solar_elevation_deg`, `night_fraction_ahead`), sampled every 30 minutes over the next 12 h, with the sun below -0.833 degrees counted as night.
- **Input gate.** Flags from the existing detectors (drift details, stuck, spike, physical-range and consistency texts) null the affected observation or instant fields (temperature, dew point/humidity, pressure, rain total, wind, gust); the masks then pause only the targets that use them.
- **Entities.** Names carry no parentheses ("Pattern Rain 1 h", "Pattern Storm 3 h (internet lightning)"); the internet variant is a separate translation key (`pattern_storm_3h_internet`) so the entity id and unique id never change. Probability sensors add an optional `reason` attribute (for example `waiting_for:dp_24h`), and the status sensor adds `storm_target`. Threshold attributes use the configured wind, rain, distance and temperature units. `top_factors`, `per_target` and `history_learn` are excluded from the recorder.
- **Factor labels.** Home Assistant cannot translate list-valued attributes, so the factor and effect labels are `selector.pattern_factor` / `selector.pattern_effect` options in `strings.json` and all translations (a valid, hassfest-safe place for arbitrary key to label maps). The 22 factor keys are covered by a test against the engine.
- **A source removed later.** If the storm source disappears (detector unmapped, opt-in turned off), the storm sensor is no longer created; a previously registered entity stays in the registry as unavailable until the user removes it.
- **Reset.** `reset_learning_state` with target `pattern_forecast` (or `all`) resets the engine, deletes the store and, in commit 3, starts a history replay. The store is not deleted when the config entry is removed (same as the learning store).
- **Config flow.** The tail of the setup `features` step was extracted into `_features_chain()` and the options routing into `_features_opt_route()` so the new `pattern_forecast` / `pattern_forecast_opt` step can be chained in front of them. The source fingerprint covers the mapped source entities (not the lightning ones) and elevation.

### Commit 3 (learning from history)

- **When it runs.** Once, 2 minutes after startup, for every target that has no recorded history result yet; again right after `reset_learning_state` (5 s later); and for a single target after a threshold or storm-source change reset it (the per-target result is dropped with the model, so only that target replays). A target that could not replay (no statistics, recorder error, too short) is retried at most once a week.
- **Executor and copy.** The recorder read (`list_statistic_ids` for the units, then one `statistics_during_period` call with `period="hour"` and types mean, min, max, sum, state) and the training run in one job on the recorder executor against a copy of the engine built from a snapshot. The result is adopted on the event loop: only the learned parameters (weights, AdaGrad accumulators, checkpoint, usual and persistence rates, `ev_hist`, `hist_days`) replace the live ones; live counters, scoring rows and pending forecasts are kept.
- **Normalization.** Rows are converted with the same unit helpers and `cal_*` offsets as live data, using the unit stored with the statistic; sea-level pressure uses the same reduction (12 h mean temperature when at least 6 hours exist); the dew point depression comes from the hourly mean temperature and humidity. A cumulative sensor (rain, lightning) uses `sum` when the statistic has one and otherwise `state`; a decrease is a counter reset (0), a jump beyond the live sanity caps is unknown.
- **Samples and labels.** One sample per hour boundary, needing 25 hours of prior history (for `dp_24h`). The hourly mean stands in for the instantaneous value; 1 h / 3 h changes and `dp_3h` come from hourly means; `rain_1h`, `gust_1h` and `lightning_1h` are the previous hour's value. Labels cover the following hours and need at least 90% of them present (missing hours are never "no"). Frost labels use the hourly minimum, heat labels the hourly maximum, gust labels the hourly maximum gust, rain and storm labels the hourly deltas (storm has no distance filter, so it is approximate).
- **What it feeds.** Replayed samples train the weights, seed the usual-rate and persistence rates and count toward leaving `collecting` (`hist_days`, `ev_hist`), but they write no weekly scoring rows, so they never count toward `skilled`.
- **Standardizer.** If the engine is cold (nothing live yet) the replay builds the standardizer, each hourly sample weighing like four 15-minute ones in the slow EMA. If the standardizer is already warm (a single target replaying after a reset) it is left untouched, so the other targets are not disturbed.
- **Masking.** `wind_u` and `wind_v` train masked (no gradient, not standardized). `solar_ok`, `cloud_deficit` and the last-daylight clearness are 0 in replay (no clearness history is read), so models trained mostly from history learn those weights from live data later.
- **Reporting.** Per target: `status` (`ok`, `unavailable`, `too_short`), `reason` (for example `history: unavailable (no statistics for sensor.rain)`), sample and event counts, plus overall `status`, `span_days` and `done_at`, shown in the status sensor's `history_learn` attribute and the diagnostics.
- **What each target needs.** rain: temperature, humidity, pressure, rain; frost: the same plus wind speed; heat: as rain; gust: temperature, pressure, wind speed, gust; storm: temperature, humidity, pressure, gust, rain and the lightning counter of the active source (Blitzortung with the opt-in).

### Commit 4 (docs and blueprints)

- **Docs scope.** Beyond the guide, the docs site covers the feature in `science.md` (method), `sensors.md`, `troubleshooting.md`, `index.md`, `quickstart.md`, `use_cases.md`, `blueprints.md`, `dashboards.md` and `forecast_providers.md`, with `{#pattern-forecast}` anchors on the sensors, science and troubleshooting pages. The shipped dashboards are unchanged; the example card lives in the guide as a native Markdown card (its template is rendered in a test).
- **Blueprints.** The early warning is a second, template trigger (`trigger_variables` carry the inputs) next to the existing numeric-state trigger. With the new sensor input left empty (its default) the template is constant `false`, so behaviour is unchanged; otherwise it is true only when the probability is at or above the threshold (default 50 %) and the sensor's `maturity` attribute is `skilled`. The freeze blueprint's valve shut-off also runs on the early warning.
- **Release metadata.** Version 2.11.0 in `manifest.json`, `pyproject.toml` and `_INTEGRATION_VERSION`; the `[Unreleased]` changelog section (the neighbor-QC off switch and the privacy wording fixes) is merged into `## [2.11.0] - 2026-10-23` together with the Pattern Forecast entry.
- **README.** One feature entry plus a Data & Privacy row for the labelled storm opt-in.
- **mkdocs.** `mkdocs` is not installed in the build environment, so `mkdocs build --strict` was not run; relative links and anchors of the changed pages are checked by `tests/test_pattern_forecast_docs.py` instead. Only the nav entry was added to `mkdocs.yml`.
