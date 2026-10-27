# Pattern Forecast Guide

Pattern Forecast learns from **your own station** and answers one kind of question:

> What is the chance that X happens at my station in the next H hours?

X is something your station can measure itself: rain, frost, a hot day, a strong gust
or a thunderstorm. The forecast is a probability over a time window, not a countdown
and not a regional weather forecast. It needs time to learn, it says so while it is
learning, and it keeps a running score of how good it really is.

It is off by default.

---

## What it forecasts

| Entity | Question it answers | Window | Counts as "it happened" | Threshold comes from |
|---|---|---|---|---|
| `sensor.ws_pattern_rain_1h` | Will the gauge record rain? | next 1 h | at least 0.2 mm | fixed (measurable rain) |
| `sensor.ws_pattern_rain_3h` | same | next 3 h | at least 0.2 mm | fixed |
| `sensor.ws_pattern_rain_6h` | same | next 6 h | at least 0.2 mm | fixed |
| `sensor.ws_pattern_frost_12h` | Will it freeze at the sensor? | next 12 h | lowest temperature at or below the freeze threshold | your **Freeze threshold** setting (default 0 °C) |
| `sensor.ws_pattern_heat_24h` | Will it be a hot day? | next 24 h | highest temperature at or above the hot-day threshold | your **Heat day threshold** setting (default 30 °C) |
| `sensor.ws_pattern_gust_3h` | Will there be a strong gust? | next 3 h | highest gust at or above the gust alert threshold | your **Wind gust threshold** setting (default 17 m/s) |
| `sensor.ws_pattern_storm_3h` | Will lightning strike nearby? | next 3 h | at least 2 strikes within the lightning proximity distance | your **Lightning proximity** setting (default 15 km) |

Two strikes, not one, because consumer lightning detectors occasionally register a
single false strike from electrical noise. The thresholds are the alert settings you
already have, so "frost" means the same thing in the frost alert, the frost streak and
here. Changing one makes only that forecast start learning again.

The states are whole percent values, 0 to 100. The three rain horizons never contradict
each other: the 3 h chance is never lower than the 1 h chance, and the 6 h chance never
lower than the 3 h chance.

Two more entities report on the feature itself:

- `sensor.ws_pattern_forecast_status` is `collecting`, `waiting` (required inputs missing), `learning` or `active`.
- `sensor.ws_pattern_forecast_skill` (diagnostic, disabled by default) counts how many
  forecasts are currently proven `skilled`.

The full attribute list is in the [Sensors Reference](../sensors.md#pattern-forecast).

---

## Turn it on

**During setup:** enable **Pattern Forecast** on the Features step.

**After setup:** toggle `switch.ws_enable_pattern_forecast`, or go to Settings → Devices
& Services → Weather Station Core → Configure → Features → Pattern Forecast.

Nothing extra to map: it uses the temperature, humidity, pressure, wind and rain
sensors you already mapped. A solar radiation or illuminance sensor is optional and
improves the rain, heat and frost forecasts.

If you have no lightning detector but the Blitzortung integration is installed, one
extra question appears; see [The storm forecast and its data source](#storm-source).

The storm sensor is created only when it has a lightning source. Each forecast you
do not want can simply be disabled as an entity; it keeps learning quietly, so
re-enabling it later shows a warm forecast.

---

## It is not useful on day one, and it says so {#maturity}

Pattern Forecast checks every forecast it makes against what the station measured
afterwards, and learns from the result. That takes time and real events, so each
forecast has a **maturity**, shown in the `maturity` attribute:

| `maturity` | Meaning | State of the sensor |
|---|---|---|
| `collecting` | Not enough yet: fewer than 7 days of checked forecasts, or fewer than 5 events seen | `unknown` (never 0 %) |
| `learning` | Publishing numbers, but it has not yet proven it beats the station's usual rate | number, flagged |
| `skilled` | Has seen enough real events since going live and beats the station's usual rate by a margin | number |
| `degraded` | Was `skilled`, but has stopped beating the usual rate recently | number, flagged |
| `paused` | An input is unavailable, stale, or flagged by the drift and stuck-sensor checks | `unknown` |

While `collecting`, the `progress_pct` attribute shows how far along it is.

"Beats the usual rate" has a precise meaning. The lazy forecast always says the usual
chance for your station, for example 10 % if it rains within 3 h about one time in ten
here (a 30-day running figure, so it follows the seasons). Pattern Forecast is scored
against that lazy forecast with the Brier skill score: 0 means no better, 1 means
perfect, negative means worse. Heat is also compared with "same as now", because hot
days follow hot days and that bar is hard to clear. The scores are in
`brier_skill` and, on the skill sensor, `bss_vs_persistence`.

Events are counted, not samples. One rainy afternoon is one piece of evidence, not 96.

**Gate your automations on `maturity`, not on the raw number.** A `learning` forecast
can be right, but it has not earned your trust yet.

### What to expect

- **Frost** is the most learnable: clear sky, calm wind, dry air and long nights are
  all things your station measures. Frost brought by an incoming cold air mass is
  caught only partly.
- **Rain** at 1 h is dominated by "it is raining now, so it probably still will be".
  3 h and 6 h frontal rain is learnable; summer pop-up showers are predicted poorly.
- **Gust**: frontal and pressure-driven wind is partly foreseeable. Thunderstorm
  downdraft gusts are not.
- **Heat** is mostly persistence. Its value is near the threshold.
- **Storm** is the hardest. One station has a weak view of atmospheric instability, so
  expect modest skill at best.
- **Heat and storm are beta** until a full summer of live data has been checked.
- Out of season the chance sits near 0 %. That is correct ("no frost tonight"), not a bug.
- Some climates never produce enough events for a forecast: frost on a frost-free coast,
  storms where thunder is rare. The sensor then stays `collecting` and shows progress
  instead of inventing numbers.

---

## Learning from history {#history}

Home Assistant already keeps hourly **long-term statistics** of your sensors. When you
enable Pattern Forecast (and after a reset, and for any single forecast whose threshold
you change), it reads up to a year of them once and trains on them, so a seasonal
forecast does not start from nothing. A user switching it on in October gets a frost
forecast that remembers last winter.

What this means in practice:

- It runs in the background, off the event loop, about two minutes after startup.
- Replayed history **counts toward leaving `collecting`** and trains the model, but it
  **never counts toward `skilled`**. Skill has to be proven on live data.
- Some inputs are approximate in history: wind direction cannot be averaged across
  0 and 360 degrees, so those two inputs are left out of the replay. Storm labels have
  no distance filter. Short changes are taken from hourly means.
- It needs statistics. A sensor without a `state_class`, an entity excluded from the
  recorder, or a short history just means less to learn from. The result is reported
  per forecast in the status sensor's `history_learn` attribute, for example
  `history: unavailable (no statistics for sensor.my_rain_total)`.
- Only your own recorder database is read. Nothing is downloaded.

---

## Why this number? `top_factors`

Every published forecast carries up to three `top_factors`, each with an `effect` of
`raises` or `lowers`:

```yaml
top_factors:
  - factor: pressure_falling
    effect: raises
  - factor: air_near_saturation
    effect: raises
  - factor: afternoon
    effect: lowers
```

They are deterministic keys, never free text, computed from the model's own weights.
Typical keys: `pressure_falling`, `pressure_rising`, `air_near_saturation`, `dry_air`,
`wet_wind_sector`, `raining_now`, `long_dry_spell`, `cloudy` (rain);
`clear_sky`, `calm_wind`, `long_night`, `already_cold`, `cooling_fast` (frost);
`hot_yesterday`, `sunny`, `warm_wind_sector` (heat); `windy_now`, `gusty_now` (gust);
`lightning_nearby`, `warm_and_humid` (storm); and `afternoon` or `night`. Home Assistant
cannot translate a list, so the display names for every key are shipped as the
`selector.pattern_factor` and `selector.pattern_effect` options of the integration's
translations, in all eight languages, for dashboards that want to show them.

---

## The storm forecast and its data source {#storm-source}

Everything above is 100 % local. The storm forecast needs lightning data, and where it
comes from is the one place the feature can touch the internet:

| Your setup | Storm source | Label |
|---|---|---|
| A lightning detector is mapped (for example an Ecowitt WH57 or an AS3935) | The detector. Always wins | `data_source: local` |
| No detector, Blitzortung installed, and you turned on **Use internet lightning data** | The Blitzortung integration | `data_source: internet`, the sensor name ends in "(internet lightning)", and the status sensor lists `internet_inputs: [storm_3h]` |
| Neither | No storm forecast is created; the status sensor says why | |

The internet option is **off by default**. It is only offered when you have no detector
but Blitzortung is installed, in setup and in Configure. When on:

- Blitzortung data feeds the storm forecast only. Rain, frost, heat and gust never see
  it.
- A tick counts for storm labels only while the Blitzortung entities are available, and
  the integration is checked in the entity registry, so a renamed look-alike is not
  accepted.
- Quiet skies and a dead feed look the same to a counter that only changes when strikes
  happen. A silent outage that leaves the entities "available" can therefore
  mislabel quiet hours as "no storm". Treat the labels as lower trust than a local
  detector. This never affects another forecast.
- Switching the source (adding or removing a detector, toggling the option) restarts
  only the storm forecast, because local and internet detection differ in range and
  rate.

---

## Example: a Shelly WS90

A Shelly WS90 reports temperature, humidity, pressure, wind speed, gusts, wind
direction and rain, plus solar radiation and UV on a standard setup. That is everything
Pattern Forecast needs for rain, frost, heat and gust. Map the entities of your WS90
as usual (see the [Hardware Mapping Guide](../hardware_mapping.md); your entity names
will differ from any example).

What to expect on this kind of station:

- **Storm:** the WS90 has no lightning detector. Without a separate detector the storm
  forecast is not created, unless you use the Blitzortung option above.
- **Rain:** the WS90 measures rain with a piezo sensor, which can register the odd
  false count. The 0.2 mm floor and a 90 % coverage rule keep a lone count from being
  read as a rain event, and a stuck or drifting rain reading pauses the rain forecasts.
- **Frost:** the air sensor sits at mast height, where ground and grass frost can form
  while the air is still +2 or +3 °C. If you care about ground frost, raise your
  **Freeze threshold** (for example to 2 °C). Only the frost forecast starts learning
  again, from history.
- **Heat:** a passive radiation shield can read high in strong sun with light wind. The
  forecast learns what *your* sensor reads, which is what your alerts use as well.

---

## How it compares to the other rain sensors

| | `rain_probability` | `rain_probability_combined` | Nowcast | Pattern Forecast |
|---|---|---|---|---|
| Entities | `sensor.ws_rain_probability` | `sensor.ws_rain_probability_combined` | `sensor.ws_minutes_until_rain`, `sensor.ws_rain_next_60min`, `binary_sensor.ws_rain_expected_1h` | `sensor.ws_pattern_rain_1h` / `_3h` / `_6h` |
| What it tells you | A 0-100 index from sea-level pressure, pressure trend, humidity and wind direction, tuned by climate region | A 0-100 blend of that index and the provider's rain chance for today; the weights adapt to which source has scored better | Minutes until rain starts or stops, and the next-hour total | The chance your gauge records at least 0.2 mm in the next 1, 3 or 6 h |
| Window | No stated window (an index of current conditions) | Today, as in the provider's daily rain chance | The next 60 minutes | 1 h, 3 h, 6 h |
| Based on | Your sensors, fixed rules | Your sensors and Open-Meteo or your chosen provider | Open-Meteo 15-minute forecast, blended with your gauge for the first 30 minutes | Your sensors only, learned from your station |
| Local or cloud | Local | Needs the forecast provider (internet) | Needs Open-Meteo (internet) | Local |
| Learned or rule-based | Rule-based | Rule-based, with adaptive blend weights | Model data, adjusted by your gauge | Learned; scored against your own history |
| Is it a probability? | No, an index | Closer, but not calibrated per station | No, a precipitation amount | Yes, with a published skill score |
| Works offline | Yes | No | No | Yes |

Use them together: the nowcast for "how many minutes", Pattern Forecast for "how likely
in the next hours, at this house", and `rain_probability` as a simple always-on index.
Pattern Forecast is independent of the forecast provider and of the nowcast: it uses
none of their data, and works with both switched off.

Similarly, `sensor.ws_thunderstorm_risk` is a surface-based rule-of-thumb index, whereas
the Pattern storm forecast learns from your detector; and the frost alert blueprints
react to the temperature, whereas the Pattern frost forecast can warn before it drops.

---

## Automations

### Frost protection that waits for a proven forecast

```yaml
alias: "Garden: cover plants when frost is likely"
trigger:
  - platform: numeric_state
    entity_id: sensor.ws_pattern_frost_12h
    above: 60
condition:
  - condition: template
    value_template: "{{ state_attr('sensor.ws_pattern_frost_12h', 'maturity') == 'skilled' }}"
action:
  - action: notify.mobile_app_phone
    data:
      title: "Frost likely tonight"
      message: >
        {{ states('sensor.ws_pattern_frost_12h') }} % chance of frost in the next 12 hours.
        Cover the tomatoes.
```

The same early warning is built into the [Frost Alert and Freeze Protection
blueprints](../blueprints.md#frost-early-warning) as an optional input.

### Close the skylight before the rain

```yaml
alias: "House: close the skylight when rain is likely within the hour"
trigger:
  - platform: numeric_state
    entity_id: sensor.ws_pattern_rain_1h
    above: 50
condition:
  - condition: template
    value_template: "{{ state_attr('sensor.ws_pattern_rain_1h', 'maturity') in ['skilled', 'learning'] }}"
  - condition: state
    entity_id: cover.skylight
    state: open
action:
  - action: cover.close_cover
    target:
      entity_id: cover.skylight
```

Closing a skylight is cheap, so this one accepts `learning` as well. Use `skilled`
alone for anything costly or hard to undo.

### Skip a sprinkler cycle when rain is likely

```yaml
condition:
  - condition: numeric_state
    entity_id: sensor.ws_pattern_rain_6h
    above: 60
  - condition: template
    value_template: "{{ state_attr('sensor.ws_pattern_rain_6h', 'maturity') == 'skilled' }}"
```

---

## A dashboard card

The Enhanced Weather and Bubble dashboards in `dashboards/` already show every forecast
with its maturity and the reason behind it. For any other dashboard, this native Markdown
card lists every forecast with its maturity:

```yaml
type: markdown
title: Pattern Forecast
content: |-
  {% set rows = [
    ('Rain, next 1 h', 'sensor.ws_pattern_rain_1h'),
    ('Rain, next 3 h', 'sensor.ws_pattern_rain_3h'),
    ('Rain, next 6 h', 'sensor.ws_pattern_rain_6h'),
    ('Frost, next 12 h', 'sensor.ws_pattern_frost_12h'),
    ('Hot day, next 24 h', 'sensor.ws_pattern_heat_24h'),
    ('Strong gust, next 3 h', 'sensor.ws_pattern_gust_3h'),
  ] %}
  | Event | Chance | Status | Why |
  |---|---|---|---|
  {% for name, entity in rows -%}
  | {{ name }} | {% if is_number(states(entity)) %}{{ states(entity) | float(0) | round(0) | int }} %{% else %}-{% endif %} | {{ state_attr(entity, 'maturity') or 'n/a' }} | {{ state_attr(entity, 'explanation') or state_attr(entity, 'reason') or '' }} |
  {% endfor %}
  Overall: {{ states('sensor.ws_pattern_forecast_status') }}
```

Add `('Storm, next 3 h', 'sensor.ws_pattern_storm_3h')` to the list if you have a
storm forecast. A dash means the forecast is still `collecting` or `paused`.

---

## Honest limits

- It is a probability over a window at **your** station. It is not a radar nowcast,
  not a regional forecast, and not a replacement for national weather services or
  warnings.
- It sees only what pressure, temperature, moisture, wind and sky reveal at your mast.
- It needs time. Weeks to a season, depending on how often the event happens where you
  live. A Mediterranean summer, with a rain day or two a month, can leave the rain
  forecasts in `collecting` for months without history.
- No accuracy figures are published, because they would depend on your climate and your
  sensors. The sensor reports its own measured skill instead.
- Not forecast: hail, fog, snow and multi-day heatwaves (a single station cannot see
  them coming). The existing fog probability sensor and heat streak sensor remain.
- Everything needed to judge it is in the attributes: `maturity`, `brier_skill`,
  `usual_rate` and the status sensor.

---

## Resetting and re-learning

Call `ws_core.reset_learning_state` with **target** `pattern_forecast` (or `all`) to
delete the learned state. Every forecast returns to `collecting` and relearns from
history. There is no automatic reset, even from `degraded`: you decide.

Changing the freeze, heat, gust or lightning proximity threshold, or the storm data
source, restarts only the affected forecast. Mapping a different station, or editing
the elevation, restarts all of them.

The trained state is stored on your own Home Assistant machine, in its own storage
file, around 30 to 50 KB per station.

See also: [Troubleshooting](../troubleshooting.md#pattern-forecast),
[method and equations](../science.md#pattern-forecast), [Nowcast](nowcast.md),
[Lightning Detection](lightning.md).
