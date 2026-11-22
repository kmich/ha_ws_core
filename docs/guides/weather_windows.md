# Weather Windows

Weather Windows answers a practical question: **when, in the next 24 hours, is the weather
good enough for a job?** Hang out the laundry, mow the lawn, paint the fence. It combines
the hourly forecast with your station's live readings and gives you a status, the start and
end of the next suitable window, and the reasons in plain language.

New in 3.0.0. It is off by default and runs entirely inside Home Assistant on the forecast
ws_core already fetches.

## Turn it on

**Settings → Devices & Services → Weather Station Core → Configure → Decision Engine &
Weather Windows.** Tick *Enable Weather Windows* and pick the profiles you want:

| Profile | For | Default limits |
|---|---|---|
| **Outdoor drying** (`outdoor_drying`) | Laundry on the line | At least 2 h; rain chance ≤ 20%, no rain; 10 to 38 °C; humidity ≤ 75%; wind 3 to 35 km/h, gusts ≤ 45 km/h; cloud cover ≤ 80%; daylight only |
| **Garden work** (`garden_work`) | Mowing, pruning, planting | At least 2 h; rain chance ≤ 30%, rain ≤ 0.1 mm/h; 8 to 32 °C; humidity ≤ 90%; wind ≤ 25 km/h, gusts ≤ 40 km/h; daylight only |
| **Custom** (`custom`) | Anything else, with your own name | Every limit is yours to set, in your own units; minimum duration 1 to 23 h |

The form shows the limits in the units you chose for ws_core (°F, mph, inches and so on).
If the forecast provider cannot supply a value a limit needs, the form says so before you
save.

## What you get

Three entities per enabled profile:

| Entity | State |
|---|---|
| `sensor.ws_window_<profile>_status` | `suitable_now`, `window_upcoming`, `unsuitable` or `unknown` |
| `sensor.ws_window_<profile>_next_start` | When the next suitable window starts (timestamp) |
| `sensor.ws_window_<profile>_next_end` | When it ends (timestamp) |

The status sensor has fixed states, so the automation editor offers them as choices. Its
attributes explain the state:

- `reasons`: one or two sentences in your language, with local times. For example
  *"Suitable now until 15:00."* or *"Next suitable window starts at 10:00 tomorrow for 3
  hours."*
- `reason_codes`: the same as stable codes for automations, such as `window_upcoming`,
  `rain_risk`, `high_gust`, `too_cold`, `nighttime`, `currently_raining`.
- `not_assessed_by_provider`: limits your forecast provider cannot supply, which are
  skipped rather than failing the whole profile.
- `is_truncated` and `horizon_hours`: whether the window runs past the 24-hour horizon.

### How it decides

- **Hour by hour.** Each forecast hour is checked against every limit. Consecutive
  suitable hours that last at least the minimum duration form a window.
- **Your station overrides the forecast right now.** If your gauge says it is raining, or
  your anemometer measures gusts above the limit for three minutes, the status turns
  `unsuitable` even when the forecast was fine. The gust hold clears after five calm
  minutes, so a single gust does not make it flap.
- **A window in progress stays put.** If a window is open, its start time does not move
  forward every hour, and a short interruption is reported as `window_interrupted`
  instead of starting a new window.
- **Honest about missing data.** No usable forecast gives `unknown` with
  `forecast_unavailable`; forecasts with steps longer than an hour give
  `forecast_too_coarse`. Clock changes (DST) are handled, including the repeated hour in
  autumn.

### Forecast providers

Open-Meteo, OpenWeatherMap, Pirate Weather and Météo France supply every input. Met.no has
no rain chance or gusts (rain limits use the rain amount; gust limits are listed under
`not_assessed_by_provider`). NWS has no rain amount, gusts or cloud cover. With a Home
Assistant weather entity as the provider, it depends on that entity; if its hourly list
starts at the next hour, the first hour also covers the current one and
`current_hour_estimated: true` is reported. See
[forecast providers](../forecast_providers.md#provider-capabilities).

## Get notified

The **Weather Window Notification** blueprint sends a notification a chosen time before
the next window starts (at the start, or 5, 15, 30 or 60 minutes before). It needs Home
Assistant 2024.10 or newer.

[![Import](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fkmich%2Fha_ws_core%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fws_core%2Fweather_window_notification.yaml)

Or write your own automation on the status:

```yaml
triggers:
  - trigger: state
    entity_id: sensor.ws_window_outdoor_drying_status
    to: suitable_now
actions:
  - action: notify.mobile_app_phone
    data:
      message: "{{ state_attr('sensor.ws_window_outdoor_drying_status', 'reasons')[0] }}"
```

## Ask on demand

`ws_core.get_weather_windows` evaluates the windows when you call it and returns the full
detail, hour by hour. It does not change the sensors. You can check one profile, or try
different limits without saving them:

```yaml
action: ws_core.get_weather_windows
data:
  profile_id: garden_work
  limits:
    max_wind_kmh: 15
    min_duration_h: 3
response_variable: windows
```

The response, per station and profile, contains `status`, `next_start`, `next_end`,
`duration_h`, `windows` (every suitable window in the horizon), `slots` (each hour with
its result and reasons), `evaluated_limits`, `reason_codes`, `reasons_text`,
`not_assessed_by_provider` and `data_quality`:

```json
{
  "outdoor_drying": {
    "status": "window_upcoming",
    "next_start": "2026-11-21T10:00:00+02:00",
    "next_end": "2026-11-21T13:00:00+02:00",
    "duration_h": 3,
    "reasons_text": ["Next suitable window starts at 10:00 tomorrow for 3 hours."],
    "windows": [
      {"start_iso": "2026-11-21T10:00:00+02:00", "end_iso": "2026-11-21T13:00:00+02:00", "duration_h": 3},
      {"start_iso": "2026-11-21T15:00:00+02:00", "end_iso": "2026-11-21T17:00:00+02:00", "duration_h": 2}
    ],
    "data_quality": {"unassessed_slots": 0, "not_assessed_by_provider": [], "current_hour_estimated": false}
  }
}
```

An unknown station, an unknown profile or impossible limits (for example a minimum above
the maximum, or a minimum duration above 23 hours) raise a clear error instead of
returning an empty result.

`ws_core.get_station_summary` returns a compact snapshot for voice assistants and scripts:
current conditions, 24-hour extremes, active alerts, how fresh the forecast is, Pattern
Forecast maturity and a one-line summary of each weather window.

## Dashboards

The Vanilla and Full dashboards have a **Windows** view with the status, the next window
and the reasons for each profile. See [dashboards](../dashboards.md).

## Turning it off

Unticking a profile or Weather Windows removes its entities on the next reload, so nothing
is left behind as unavailable.
