# Troubleshooting

## Understanding unknown values

An `unknown` value means that a calculation cannot currently return a meaningful
number; it does not by itself mean the station is offline.

**Start with `sensor.ws_data_status`** (3.0.0). It reads **OK** or **Needs attention**,
and reports source problems that persist for five minutes or problems reading usable
PV meter history. Its `waiting` attribute lists readings that are empty for a normal reason, and
`not_on_this_station` lists what your station's sensors or settings cannot provide. See
[Data Status](sensors.md#data-status).

Derived sensors covered by Data Status also have their own attributes: a short `status_text` such as "No rain
expected" or "Learning (2 of 5 events)", the longer `explanation`, and the
machine-readable `reason` (also `data_status` on ordinary sensors). They disappear when a
valid value returns. The Enhanced and Bubble dashboards show `status_text` for empty
Nowcast and Pattern Forecast readings.

| Entity group | Why it can be unknown | Action |
|---|---|---|
| Heat Index, THW, THSW, Wind Chill, Humidex | Since 3.0.0 these show the air temperature (with `formula_applies: false`) when their formula does not apply, so `unknown` means a missing temperature, humidity or wind input. THSW is only created with a solar radiation sensor | Check the source sensors |
| Wind Gust Factor | The wind is calm (below 0.5 m/s), so gust divided by mean wind is not defined (`status_text`: "Calm") | Expected in calm weather |
| Solar Energy, Peak Sun Hours, Net Radiation | No valid solar radiation input | Map a W/m² sensor, or enable the optional illuminance fallback with a mapped lux source for an estimate |
| Clearness Index, Cloud Cover | Requires measured solar radiation and sun elevation of at least 5° | Map radiation; wait for daylight. These do not use the lux fallback |
| Lightning distance, bearing | No mapped/discovered location source, or no strike since the source last reported one ("No recent strike") | Check the source entity; Blitzortung can report zero strikes with an unknown distance |
| Lightning proximity | Since 3.0.0 it reads `clear` whenever a working distance source reports no strike; `unknown` means there is no distance source, or it is unavailable (see `status_text`) | Map a lightning detector or set up Blitzortung, or check that the detector is online |
| Lightning clearance | No strike has ever been recorded. Since 3.0.0 it resumes from the last recorded strike after a restart | Expected until the first strike; unknown does not establish safety |
| Rain/frost/lightning events | No corresponding event recorded yet ("No frost yet") | Expected; the state is the last event time |
| Minutes Until Rain / Dry | No matching transition within the nowcast window ("No rain expected", "Not raining"), or nowcast data not ready | Read `reason`; check Rain Expected and Rain Next 60 min |
| Pattern Forecast | Missing recent inputs, too few checked days/events ("Learning (2 of 5 events)"), or not run yet since a restart ("Starting up", up to 15 minutes) | Read `explanation`, `progress_pct`, `events_collected` and `days_checked` |

Pattern Forecast status `waiting` means missing inputs prevent any forecast from
publishing. `collecting` means training is not yet sufficient. Individual targets
can still be collecting while others publish. Its `warm_start` attribute reports
how many recent wind bins were recovered. At least three usable 15-minute bins
are needed. Raw recorder direction history can recover circular wind components
when arithmetic statistics span north; if excluded or purged, live bins fill the
gap. Wind speed remains usable even without direction.

The updated Weather and Bubble dashboard templates display explanations and
collection progress in the “Why” column. Dashboards already pasted into Home
Assistant must have that card's YAML updated; upgrading the integration alone
does not replace a stored dashboard.

---

## Common issues

| Symptom | Likely cause | Fix |
|---|---|---|
| All sensors show "unavailable" | Source entities not found | Check source sensor entity IDs in Configure. Verify the entity exists in Developer Tools → States. |
| `binary_sensor.ws_package_ok` is Off | One or more required sources are unavailable | Open Configure and remap the missing source sensors. |
| Temperature statistics look wrong | Old `TOTAL_INCREASING` state class in history | Delete the temperature entity from the entity registry, then restart HA. |
| Rain rate stuck at 0 | Rain total sensor reset after replacement | Call the `ws_core.reset_rain_baseline` service from Developer Tools → Services. |
| Forecast shows "unavailable" | Provider API timeout or auth error | Check internet connectivity. Verify the API key if using OpenWeatherMap, Pirate Weather, or Météo France. The forecast retries automatically. |
| "Stale" warning on sensors | Source sensor stopped updating | Check your weather station hardware. Is the station powered and connected? |
| Weather Underground upload never succeeds | Wrong API credential | Use the **station key (password)** from `wunderground.com/member/devices`, not a read API key. |
| Windy upload returns HTTP 401 (`error_auth`) | Stations API v2 credentials used without Station ID, or general API key used instead of Station password | On `stations.windy.com` → My Stations → Connection, copy the **Station password** into API key and the alphanumeric **Station ID** into Station ID. |
| Blitzortung data not appearing | Auto-discovery needs restart | Restart HA after installing Blitzortung. ws_core discovers Blitzortung entities at startup. |
| Comfort indices sensors not created | Feature toggle is off | Toggle `switch.ws_enable_comfort_indices` on the device page, or Configure → Features & Diagnostics. |
| FWI values very high on first run | Standard initial values | FWI moisture codes start at Van Wagner (1987) defaults (FFMC=85, DMC=6, DC=15) and self-correct within a few days. |
| FWI moisture codes don't change in the morning | By design (2.8.0+) | The codes advance once a day on the first reading at or after 12:00 local time, the observation time the FWI system is defined on. ISI/FWI still follow the current wind. |
| Repairs shows a "stuck sensors" issue | A reading has not changed for hours | Temperature is flagged after 4 h without any change, humidity and pressure after 6 h (humidity at 0-2 % or 98-100 % is never flagged). Check the sensor and its radiation shield; the issue clears as soon as the value moves. With several stations, each entry raises its own issue. |
| Nowcast always shows unknown | Coordinates not set, or Open-Meteo timeout | Verify forecast coordinates are set in Configure → Weather Forecast & Location. Check internet connectivity. |
| Lightning sensor rejected as "entity not found" during setup | Older versions rejected sensors sitting at `unknown` | Update to 2.4.1+. Lightning distance/azimuth/count sensors are idle (`unknown`) outside a strike and are now accepted as long as the entity exists. |
| Hemisphere / climate region shows a raw value like `atlantic_europe` | Translation not loaded for your language | These are localized in all 8 supported languages (`en`, `fr`, `de`, `es`, `it`, `nl`, `pl`, `pt`); other languages fall back to English. Restart HA after updating so new translations load. |

---

## Pattern Forecast {#pattern-forecast}

See the [Pattern Forecast guide](guides/pattern_forecast.md) for how it works.

| Symptom | Likely cause | What to do |
|---|---|---|
| Every Pattern sensor is `unknown` | The forecast is `collecting`: fewer than 7 days of checked forecasts or fewer than 5 events | Wait; check `progress_pct` and `sensor.ws_pattern_forecast_status` attributes. `unknown` is deliberate, never a fake 0 % |
| `sensor.ws_pattern_forecast_status` stays `learning` even after history replay and several rainy days | Replayed history (`events_from_history`) leaves `collecting` so forecasts publish right away, but reaching `skilled` (and flipping the status sensor to `active`) requires 15 **live** rain episodes (10 for frost, heat, gust or storm) and `brier_skill > 0.02` | Normal: forecasts in `learning` are already publishing probabilities. Check `per_target` on `sensor.ws_pattern_forecast_status` to read each target's live event progress (`events_live` / `events_required`) and `explanation` |
| Stuck in `collecting` for weeks (rain) | Dry climate or season: not enough rain events | Normal. Events are counted, not days. Learning from history helps if Home Assistant has statistics |
| Stuck in `collecting` for frost, heat or storm | The event does not happen where you live, or not in this season | Normal and reported honestly rather than inventing numbers. You can disable the entity |
| `history_learn` says `no statistics for sensor.x` | The source sensor has no `state_class`, is excluded from the recorder, or was never recorded | Give the sensor a `state_class` (measurement, or total_increasing for rain) and make sure the recorder includes it. The forecast then learns live only |
| `history_learn` says `too short` | Less than a day of statistics exists. In 2.11.0 this also showed for rain gauges whose running total is recorded as a measurement (e.g. the Shelly WS90), which affected rain and frost | It uses what exists and keeps learning live. 2.11.1 reads measurement-type rain totals from their hourly maximum and retries those forecasts automatically |
| `maturity` is `paused` | An input is unavailable, stale, or flagged by the drift, stuck or spike checks (see `reason`) | Fix the sensor; the forecast resumes by itself. Check Station Diagnostics |
| `reason` shows `waiting_for:dp_24h` | A 24 h pressure change needs a reading from 24 h ago | Since 2.11.1 the learning-from-history step (about 2 minutes after start) fills the last day of pressure from the recorder, so this clears then. Without recorder statistics for pressure, wait a day |
| `reason` shows `waiting_for:dpd_1h`, `t_1h`, `t_3h`, `wind_u` or `gust_1h` | These need readings from 1 h or 3 h ago, or several in the last hour | Startup seeds the last 3 hours from recorder statistics after about 2 minutes; forecasts then retry at the next 15-minute issue. Since 2.12.0 unsafe arithmetic wind-direction statistics can fall back to circular components from raw history. If suitable history is excluded, purged or unavailable, wind needs three usable 15-minute bins and other changes may need up to 3 h live. Check `warm_start` and the target's `explanation` |
| No `sensor.ws_pattern_storm_3h` | No lightning detector is mapped, and the internet lightning option is off | Map a detector's strike count sensor in Configure, or, if the Blitzortung integration is installed, turn on **Use internet lightning data** (Configure → Features & Diagnostics). The status sensor's `storm_target` attribute says which case applies |
| Storm sensor name ends in "(internet lightning)" and stays `unknown` | The Blitzortung integration is not installed, is disabled, or its entities are unavailable | Install or enable it. The feed is checked in the entity registry and must be available |
| `maturity` went from `skilled` to `degraded` | Over the last 5 weeks, with at least 3 events, the forecast stopped beating the station's usual rate | It is shown, not hidden. A changed sensor, a new location or a different season can cause it. Reset it if the cause was a one-off |
| A forecast restarted at `collecting` after I changed a setting | The freeze, heat, gust or lightning proximity threshold, or the storm source, defines what the forecast predicts | Expected: only that forecast relearns, from history. Mapping a different station, or editing the elevation, restarts all of them |
| I want to start over | | Call `ws_core.reset_learning_state` with **target** `pattern_forecast` (Developer Tools → Actions). All forecasts return to `collecting` and relearn from history. `all` includes it |
| Probabilities seem too high or low | Not enough examples yet, or sensor siting | Look at `brier_skill` and `usual_rate`; see the guide's notes on frost siting and the rain threshold |

`ws_core.export_learning_state` writes maturity, skill and the named model weights to the
Home Assistant log, and the diagnostics download includes a `pattern_forecast` section
(no location data).

---

## Diagnostics export

Download a full diagnostics report via:
**Settings → Devices & Services → Weather Station Core → ⋮ → Download Diagnostics**

The export includes sensor availability, coordinator timing, feature toggle state,
and quality flags. Location data (coordinates) is redacted automatically.

Attach the diagnostics file to GitHub issues — it helps identify configuration
problems without requiring detailed manual description.

---

## Enabling debug logging

Add to your `configuration.yaml` to capture detailed logs:

```yaml
logger:
  default: warning
  logs:
    custom_components.ws_core: debug
```

Restart Home Assistant, reproduce the issue, then check **Settings → System → Logs**
or the `home-assistant.log` file. Filter for `ws_core` to find relevant entries.

---

## Resetting the rain baseline

If your weather station was replaced or the cumulative rain counter was reset, the
rain rate sensor may read incorrectly. Reset the internal baseline with:

```yaml
service: ws_core.reset_rain_baseline
```

Call from Developer Tools → Services, or trigger from an automation.

---

## Calibration corrections

If your station readings consistently differ from nearby reference stations (e.g.
airport METAR), apply a calibration offset:

```yaml
service: ws_core.apply_calibration
data:
  cal_temp_c: -0.5      # adjust temperature down by 0.5 °C
  cal_humidity: 3       # adjust humidity up by 3%
  cal_pressure_hpa: 0   # no pressure adjustment
  cal_wind_ms: 0        # no wind adjustment
```

### Adaptive (auto-apply) calibration

If you'd rather not track down a reference station yourself, enable **Feature:
Adaptive Sensor Calibration** under **Configure → Features & Diagnostics**. It's off by
default. When on, it reuses the regional Open-Meteo reference point already
fetched hourly for neighbor QC (requesting the station's configured `elevation_m`,
and skipping temperature/pressure samples whose returned model elevation differs
by more than 1 m) as a slow-moving comparison: temperature,
humidity, and pressure each get a residual-bias estimate that only settles
after many samples (~10 days), and only once that bias is both confident and
outside a noise deadband does it nudge the same `cal_temp_c` / `cal_humidity`
/ `cal_pressure_hpa` options above - by a small, bounded amount, at most once
per day, never overshooting the learned bias. It never touches wind, since a
grid-model comparison for wind is too dependent on local terrain to trust.

Watch `sensor.ws_auto_calibration` to see what it has learned (`learning` /
`stable` / `adjusted`, plus the current bias estimate for each field and the
date it last nudged something) before deciding whether to leave it on. You
can always turn the toggle off, or override the calibration numbers by hand
at any time - manual changes are respected the same way either way.

Or adjust the number entities directly from the device page:
`number.ws_cal_temp`, `number.ws_cal_humidity`, `number.ws_cal_pressure`,
`number.ws_cal_wind`.

---

## Reporting bugs

Use the GitHub issue template at https://github.com/kmich/ha_ws_core/issues/new

Include:
1. Your HA version and ws_core version
2. The diagnostics export (download from the integration page)
3. Relevant log lines (with debug logging enabled if possible)
4. Steps to reproduce the issue
