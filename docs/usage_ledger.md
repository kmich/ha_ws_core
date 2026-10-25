# Entity usage and history coverage ledger

Review basis: repository at baseline `2c927a5` plus this branch's documentation
preview. This is a static scan of shipped dashboards, blueprints, scripts,
documentation, tests, and integration source. It cannot inspect a user's saved
Home Assistant dashboards, automations, scripts, groups, templates, registry,
Node-RED flows, API clients, or other external consumers.

## Classification

- **referenced** — an explicit entity ID appears in an inspected repository
  file; the CSV records the file and line. A reference in code or a test does
  not prove that an installation consumes the entity.
- **no reference found within inspected scope** — no explicit match in those
  scanned repository files. This is not evidence of non-use.
- **usage unknown** — consumer may be dynamic, use a renamed entity, target a
  device/area, or live outside this repository. This applies to every entity
  absent an installation-specific audit.

## Explicit references found

The companion [CSV ledger](entity_usage_ledger.csv) has one row for each of the
246 concrete IDs recognized by the dashboard validator (the validator's
dynamic `binary_sensor.ws_{slug}` pattern is excluded), including
repository reference locations, reference status, a purpose/role summary, and
an external-use caveat. It scans shipped dashboards, blueprints, scripts,
documentation, and tests. The table below highlights common examples;
producer/prerequisite notes describe the integration contract, not whether the
entity exists in any particular install.

| Entity ID (default prefix) | Producer / prerequisite | Repository consumer | Reference status | History / action |
|---|---|---|---|---|
| `sensor.ws_temperature` | Normalized mapped temperature | All dashboard variants; example docs | referenced | Preserve; current observation, history useful |
| `sensor.ws_humidity` | Normalized mapped humidity | Dashboard variants | referenced | Preserve; current observation |
| `sensor.ws_station_pressure` | Mapped station pressure | Enhanced dashboard | referenced | Preserve; distinct from sea-level pressure |
| `sensor.ws_sea_level_pressure` | Pressure plus altitude/config | Full/mobile dashboards | referenced | Preserve; distinct from station pressure |
| `sensor.ws_wind_speed` | Mapped wind speed | Dashboards; examples | referenced | Preserve; current observation |
| `sensor.ws_wind_gust` | Mapped gust | Dashboards; examples | referenced | Preserve; current observation |
| `sensor.ws_wind_direction` | Mapped direction | Full dashboard | referenced | Preserve; current observation |
| `sensor.ws_rain_rate` | Mapped rain total/rate | Dashboards | referenced | Preserve; rate differs from accumulations |
| `sensor.ws_rain_today_mm` | Rain total accumulator | Dashboards; irrigation example | referenced | Calendar-day accumulator; installation-limited since reset/initialization |
| `sensor.ws_rain_this_week` | Rain total accumulator | Full dashboard | referenced | Calendar-week accumulator; not rolling 7 days |
| `sensor.ws_rain_this_month` | Rain total accumulator | Full dashboard | referenced | Calendar-month accumulator |
| `sensor.ws_rain_this_year` | Rain total accumulator | Dashboard/guide references | referenced | Calendar-year accumulator |
| `sensor.ws_feels_like` | Temperature, humidity, wind | Dashboards | referenced | Preserve; presentation summary |
| `sensor.ws_dew_point` | Temperature and humidity | Dashboards | referenced | Preserve; derived observation |
| `sensor.ws_heat_index` | Comfort indices enabled | Dashboard | referenced | Optional; specialist details |
| `sensor.ws_wind_chill` | Comfort indices enabled | Dashboard | referenced | Optional; specialist details |
| `sensor.ws_utci` | Comfort indices enabled | Full dashboard | referenced | Optional; specialist details |
| `sensor.ws_wbgt` | Comfort indices enabled | Full dashboard | referenced | Optional; specialist details |
| `sensor.ws_vpd` | Comfort indices enabled | Dashboard; examples | referenced | Optional; specialist details |
| `sensor.ws_et0_daily` | Temperature range; degree-days feature | Full dashboard; irrigation guide | referenced | Daily estimate; coverage is installation-limited |
| `sensor.ws_et0_penman_monteith` | Required met inputs/radiation; feature prerequisites | Dashboard; irrigation guide | referenced | Daily estimate; do not call historical without coverage metadata |
| `sensor.ws_fwi` | Fire risk feature and required weather inputs | Dashboard | referenced | Keep distinct from FFDI/FFWI |
| `sensor.ws_fire_risk_score` | Derived from FWI | Dashboard | referenced | Presentation summary of FWI, not independent model |
| `sensor.ws_data_quality_score` | Diagnostic computation | Dashboards | referenced | Readiness semantics require correctness work |
| `sensor.ws_station_health` | Required-source status/freshness | Dashboards | referenced | Source health; not model maturity |
| `binary_sensor.ws_package_ok` | Required source mappings | Vanilla dashboard | referenced | Readiness signal for required inputs |
| `sensor.ws_pattern_forecast_status` | Pattern forecast enabled | Dashboard guide/example | referenced | Use status/maturity; not station health |
| `sensor.ws_pattern_frost_12h` | Pattern Forecast enabled | Frost blueprint and examples | referenced | Preserve; published only per maturity rules |
| `sensor.ws_pattern_rain_1h` | Pattern Forecast enabled | Rain examples/docs | referenced | Preserve; published only per maturity rules |
| `sensor.ws_minutes_until_rain` | Nowcast feature and inputs | Use-case examples | referenced | Preserve if enabled; external references unknown |
| `event.ws_rain_event` | Rain event detection | Vanilla dashboard; example | referenced | Event entity; usefulness precedes first event |
| `event.ws_frost_event` | Frost event detection | Vanilla dashboard | referenced | Event entity; usefulness precedes first event |
| `event.ws_lightning_event` | Lightning feature/input | Vanilla dashboard | referenced | Event entity; conditional availability |

The CSV locations distinguish shipped dashboard references from code, test,
and documentation examples. Examples are not evidence that the author's own
installation uses them. The inventory cannot enumerate per-room entities or
all dynamically named river entities, and it doesn't know user-renamed IDs.

## Scope result and decision

The CSV is a repository-scoped inventory, not a universal usage verdict, and no
entity is proposed for disablement. Existing YAML dashboards, blueprints,
scripts, docs, and tests were inspected. The repository contains no
user-specific saved HA configuration, automation export, groups file, or
Node-RED export. Dynamic template rendering, device/area targeting, renamed
IDs, and external clients remain usage unknown. A missing match must never be
interpreted as unused.

## History implementation inventory

| Metric family | Current source and persistence | Coverage conclusion | Backfill decision |
|---|---|---|---|
| 24-hour rolling temperature, gust, rain histories | Coordinator sample deques; selected buffers are saved/restored in the integration history store | Bounded to observed samples, with retention capped at a rolling window; not a recorder replay | No backfill: rolling windows should reflect sampled observations, not statistical aggregates |
| Pressure trend history | Coordinator deque and timestamp persisted | Sampled live window; gaps and sampling cadence constrain coverage | No backfill without raw timed samples and explicit gap policy |
| Rain today/week/month/year | Coordinator cumulative-counter deltas, reset at local calendar boundaries; selected accumulators stored in integration history state | Period total begins when the accumulator observes the period/counter; reset, missing counter, or restart gaps can reduce completeness | Recorder statistics might permit bounded interval deltas, but aggregation metadata/reset semantics need proof first; defer |
| Temperature high/low by 24h/week/month/year/all-time | Coordinator extrema updated from live samples; restored entity values are separate from coordinator extrema | Week/month/year/all-time coverage is installation-limited; restored last state does not prove the coordinator saw all intervening extrema | Never reconstruct extrema from hourly means; defer unless recorder min/max statistics, units, retention, and timestamp boundaries are verified |
| Daily ET₀, solar energy, wind run, degree days, chill/streak counters | Coordinator seasonal/daily accumulators, several persisted in history state or learned-state storage | Period-specific counters depend on observed inputs and reset dates; coverage/completeness metadata is not consistently exposed | No backfill until each measure has a validated method; period totals cannot be combined with overlapping counters |
| Pattern Forecast learning | Separate recorder replay through Pattern Forecast | “Days learned” reports replay/training progress for Pattern targets only, not coverage for ordinary coordinator metrics | Keep separate; event-count validation against hourly min/max remains required |
| Climate normals | Archive daily source, monthly refresh, multi-year day-of-year buckets | External archive-derived normal with separate year-count metadata; not station observations | Existing archive process is the justified backfill path for this distinct metric |

### Proposed coverage contract

For each historical metric, eventually expose: `coverage_start`, the actual
observation period, completeness (`complete`, `partial`, `unknown`), and method
(`live_samples`, `recorder_statistics`, `archive`, or another explicit source).
The present implementation does not uniformly track these fields. Adding them
requires reset-aware metadata alongside each accumulator and careful persisted
state migration. This is not a safe documentation-only claim to retrofit to
existing values, so bounded recorder backfill is deferred. Start with metadata
for live accumulator start/reset and gap detection; consider recorder min/max
for extrema only after checking HA statistic availability and units at runtime.

Acceptance gaps still open: pre-installation retained history, insufficient
retention, midnight/year rollover, counter reset, restart mid-period, unit
conversion, duplicate/overlapping totals, and independent Pattern event-count
comparison against source hourly minima/maxima. No historical coverage claim is
verified by this repository scan.
