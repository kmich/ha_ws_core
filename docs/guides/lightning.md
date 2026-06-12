# Lightning Detection Guide

Weather Station Core's lightning detection group tracks local strike activity and
gives you a structured safe-to-go-outside countdown.

---

## Compatible sensors

Any sensor that exposes cumulative lightning strike counts works. Supported hardware:

| Hardware | HA integration | Notes |
|---|---|---|
| WH57 (Ecowitt) | Ecowitt / GW series integration | Most common consumer lightning sensor |
| AS3935 (Franklin) | Custom / ESPHome | Franklin Instruments AS3935 chip |
| Blitzortung | Blitzortung integration | Network-based, community-run |

**Blitzortung auto-discovery:** if the Blitzortung HA integration is installed and no
manual lightning sensor is mapped in ws_core, the integration automatically finds
and uses Blitzortung entities. Zero configuration needed.

---

## Enabling lightning detection

**During setup:** enable **Lightning Detection** on the Features step and map your
cumulative strike count sensor (and optionally the nearest distance sensor).

**After setup:** Settings → Devices & Services → Weather Station Core → Configure →
Features → Lightning Detection.

---

## Sensors created

| Entity ID | Unit | Description |
|---|---|---|
| `sensor.ws_lightning_count_1h` | strikes | Strikes detected in the past hour |
| `sensor.ws_lightning_distance` | km | Distance to the nearest detected strike |
| `sensor.ws_lightning_rate` | /min | Average strike rate over the past 15 minutes |
| `sensor.ws_lightning_clearance` | min | Minutes since the last strike |
| `sensor.ws_lightning_proximity` | — | `near` / `clear` based on configurable threshold |
| `event.ws_lightning_event` | — | Fires on strike detection and proximity changes |

---

## Lightning proximity threshold

`number.ws_lightning_proximity_threshold` (on the device page) sets the distance in
kilometres that separates "near" from "clear" for `sensor.ws_lightning_proximity`.
Default is 8 km.

The safety standard for outdoor activities is typically: cease activities when
lightning is within 10 km, resume when the clearance timer exceeds 30 minutes.

---

## Safe-to-go-outside automation

```yaml
alias: "Lightning: all-clear notification"
trigger:
  - platform: numeric_state
    entity_id: sensor.ws_lightning_clearance
    above: 30
condition:
  - condition: state
    entity_id: sensor.ws_lightning_count_1h
    state: "0"
    for:
      minutes: 30
action:
  - service: notify.mobile_app_phone
    data:
      title: "Lightning clear"
      message: >
        No lightning detected for 30 minutes.
        Last strike was {{ state_attr('sensor.ws_lightning_distance', 'distance_km') }} km away.
```

---

## Event entity

`event.ws_lightning_event` fires on:
- `lightning_strike`: when a new strike is detected
- `proximity_near`: when proximity state changes to `near`
- `proximity_clear`: when clearance timer reaches the safe threshold

Use it as an automation trigger for immediate notification:
```yaml
trigger:
  - platform: state
    entity_id: event.ws_lightning_event
    event_type: lightning_strike
```
