# Precipitation Nowcast Guide

The Precipitation Nowcast feature answers the question "will it rain in the next hour,
and when exactly?"

It uses Open-Meteo's 15-minute precipitation forecast data, which is free and requires
no API key, and is independent of your chosen 7-day forecast provider.

---

## Enabling the nowcast

**During setup:** enable **Precipitation Nowcast** on the Features step.

**After setup:** toggle `switch.ws_enable_nowcast` on the device page, or go to
Settings → Devices & Services → Weather Station Core → Configure → Features →
Precipitation Nowcast.

Requires: forecast coordinates set in the Forecast configuration step.

---

## Sensors created

| Entity ID | Unit | Description |
|---|---|---|
| `sensor.ws_minutes_until_rain` | min | Minutes until rain is expected to start. State is `unknown` when no rain is in the 60-minute window. |
| `sensor.ws_minutes_until_dry` | min | Minutes until rain is expected to stop. State is `unknown` when it is not currently raining. |
| `sensor.ws_rain_next_60min` | mm | Total precipitation expected in the next 60 minutes. |
| `sensor.ws_nowcast_intensity` | — | Peak intensity in the next hour: `none` / `light` / `moderate` / `heavy` |
| `sensor.ws_nowcast_confidence` | — | Agreement between local gauge and NWP grid: `high` / `medium` / `low` |
| `binary_sensor.ws_rain_expected_1h` | — | On when measurable rain is expected within 60 minutes. |

All sensors update every 15 minutes.

---

## How it works

Open-Meteo's `minutely_15` endpoint returns precipitation values in 15-minute buckets
for the next several hours. ws_core reads the next four buckets (60 minutes), determines
when rain starts, when it stops, and the peak rate in the window.

The sensor uses your configured forecast coordinates (latitude/longitude from the
Forecast step), not your physical GPS location. In most cases these are the same; if
you have set a custom location in the Forecast step, that is used.

---

## Local gauge blending (v2.1+)

For the first 30 minutes of the nowcast window — where the local rain gauge is ground truth — ws_core blends live local measurements into the NWP forecast:

| Time bucket | Local weight | NWP weight |
|---|---|---|
| 0–15 min | 70% | 30% |
| 15–30 min | 50% | 50% |
| 30+ min | 0% (pure NWP) | 100% |

Blending only activates when the local gauge reports > 0.05 mm per 15-minute period. When the gauge is dry but NWP predicts rain, the `sensor.ws_nowcast_confidence` sensor shows `low`. When both agree, it shows `high`.

The `sensor.ws_nowcast_confidence` entity is a diagnostic sensor gated behind the Precipitation Nowcast feature toggle.

---

## Using the nowcast in automations

**Close umbrella before rain:**
```yaml
alias: "Garden: close umbrella before rain"
trigger:
  - platform: numeric_state
    entity_id: sensor.ws_minutes_until_rain
    below: 20
condition:
  - condition: state
    entity_id: cover.garden_umbrella
    state: "open"
action:
  - service: cover.close_cover
    target:
      entity_id: cover.garden_umbrella
```

**Skip irrigation when rain is coming:**
```yaml
condition:
  - condition: state
    entity_id: binary_sensor.ws_rain_expected_1h
    state: "on"
```

**Notify when rain is 15 minutes away:**
```yaml
trigger:
  - platform: numeric_state
    entity_id: sensor.ws_minutes_until_rain
    below: 15
    above: 0
action:
  - service: notify.mobile_app_phone
    data:
      message: >
        Rain expected in {{ states('sensor.ws_minutes_until_rain') }} minutes
        ({{ states('sensor.ws_nowcast_intensity') }},
        {{ states('sensor.ws_rain_next_60min') }} mm forecast).
```

---

## Limitations and accuracy

- **Grid resolution:** Open-Meteo uses a global NWP grid. In flat terrain with uniform
  weather, accuracy is high. In mountainous or coastal areas with rapid local variation,
  the forecast may lag or miss highly localised convective events.
- **Convective storms:** Short-lived convective cells (summer thunderstorm pop-ups) are
  difficult to forecast even with 15-minute resolution. The sensor is most reliable for
  frontal and stratiform precipitation.
- **Update interval:** Data refreshes every 15 minutes. If conditions change rapidly,
  there may be up to a 15-minute lag before the sensor reflects them.
- **The sensor is not calibrated rain probability.** It reflects the NWP model's
  precipitation quantity forecast, not a verified probability.

---

## Interaction with the 7-day forecast provider

The nowcast always uses Open-Meteo's minutely_15 endpoint, regardless of which
7-day forecast provider you have selected (Met.no, NWS, OpenWeatherMap, etc.).
This ensures the nowcast is always available and does not conflict with provider
API quotas.
