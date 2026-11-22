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
| `sensor.ws_lightning_clearance` | min | Minutes since the last strike; `safe` attribute is true from 30 minutes |
| `sensor.ws_lightning_proximity` | — | `near` / `clear` based on configurable threshold |
| `event.ws_lightning_event` | — | Fires on strike detection and proximity changes |

Since 3.0.0, **proximity reads `clear`** whenever your distance source (a detector or
Blitzortung) reports no strike, instead of `unknown`. While that source is unavailable (a
detector offline, Blitzortung disconnected) proximity stays `unknown` with the status text
"Lightning source unavailable", since it could not report a strike. The **clearance timer keeps
counting across restarts** from the last strike the lightning event recorded. Distance
and bearing stay empty until there is a strike; their `status_text` attribute then says
"No recent strike".

---

## Lightning proximity threshold

`number.ws_lightning_proximity` (on the device page) sets the distance in
kilometres that separates "near" from "clear" for `sensor.ws_lightning_proximity`.
Default is 8 km.

The safety standard for outdoor activities is typically: cease activities when
lightning is within 10 km, resume when the clearance timer exceeds 30 minutes.

---

## Safe-to-go-outside automation

The **Lightning Safety** blueprint does this for you. If you imported it before 3.0.0,
re-import it: the new version ignores the jump from `unknown` after a restart, so a restart
cannot send a false "all clear". Your own automation needs the same guard:

```yaml
alias: "Lightning: all-clear notification"
triggers:
  - trigger: numeric_state
    entity_id: sensor.ws_lightning_clearance
    above: 30
conditions:
  # Only a real rise past 30 minutes, not a value coming back after a restart
  - condition: template
    value_template: "{{ trigger.from_state is not none and trigger.from_state.state | is_number }}"
actions:
  - action: notify.mobile_app_phone
    data:
      title: "Lightning clear"
      message: >
        No lightning detected for {{ states('sensor.ws_lightning_clearance') | int }} minutes.
```

---

## Event entity

`event.ws_lightning_event` fires with one of two event types:

- `strike_detected`: new strikes were counted (attributes `count_1h`, `distance_km`, `proximity`)
- `proximity_alert`: proximity changed from `clear` to `near` (attribute `distance_km`)

Use it as an automation trigger for an immediate notification:

```yaml
triggers:
  - trigger: state
    entity_id: event.ws_lightning_event
conditions:
  - condition: template
    value_template: "{{ trigger.to_state.attributes.event_type == 'proximity_alert' }}"
actions:
  - action: notify.mobile_app_phone
    data:
      message: "Lightning {{ trigger.to_state.attributes.distance_km }} km away"
```
