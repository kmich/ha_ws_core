# Automation Blueprints

Five automation blueprints are provided in `blueprints/automation/ws_core/`.
Each is a single YAML file that imports into HA as a configurable automation template.

---

## Installing a blueprint

1. Go to **Settings → Automations & Scenes → Blueprints**
2. Click **Import Blueprint**
3. Paste the raw URL of the blueprint file from GitHub:
   `https://raw.githubusercontent.com/kmich/ha_ws_core/main/blueprints/automation/ws_core/<filename>.yaml`
4. Click **Preview blueprint** then **Import**
5. Create an automation from the imported blueprint and configure the parameters

---

## Available blueprints

### Frost Alert (`frost_alert.yaml`)

Sends a notification when the temperature drops below a configurable threshold.
Optionally requires temperature to be falling before alerting (filters out false
positives when the station is warming up from a cold start).

**Configurable parameters:**
- Notification service (e.g. `notify.mobile_app_phone`)
- Temperature threshold (default: 2 °C)
- Require falling temperature: yes / no

**Required entities:** `sensor.ws_temperature`

---

### Storm Alert (`storm_alert.yaml`)

Triggers when rapid pressure drop is combined with high wind. Uses `sensor.ws_pressure_trend`
state and `sensor.ws_wind_gust` value together for a two-factor check.

**Configurable parameters:**
- Notification service
- Minimum gust speed (m/s)
- Pressure trend states that trigger (default: "Falling Rapidly")

**Required entities:** `sensor.ws_pressure_trend`, `sensor.ws_wind_gust`

---

### Irrigation Rain Skip (`irrigation_rain_skip.yaml`)

Suppresses an irrigation schedule when either recent rainfall exceeds a threshold
or rain is expected in the next hour. Pairs with the Smart Irrigation integration
or any irrigation integration that exposes a skip/enable switch.

**Configurable parameters:**
- Rain threshold for the past 24h (mm)
- Whether to use the nowcast rain expected flag
- The switch or input_boolean to toggle when skipping

**Required entities:** `sensor.ws_rain_last_24h`
**Optional:** `binary_sensor.ws_rain_expected_1h` (requires Precipitation Nowcast enabled)

---

### Lightning Safety (`lightning_safety.yaml`)

Triggers when lightning is detected within a configurable distance and the
clearance timer has not yet reached the safe threshold (30 minutes by default).
Sends a notification or triggers a scene.

**Configurable parameters:**
- Notification service
- Maximum safe distance (km)
- Clearance threshold (minutes, default: 30)

**Required entities:** `sensor.ws_lightning_proximity` or `sensor.ws_lightning_clearance`
**Requires:** Lightning Detection feature enabled

---

### Fire Danger Alert (`fire_danger_alert.yaml`)

Notifies when the fire risk score reaches or exceeds a configurable level.
Optionally triggers only when the score has been at that level for a minimum
duration (avoids alerts on transient spikes).

**Configurable parameters:**
- Notification service
- Minimum fire risk score to trigger (1-10 scale, default: 6)
- Require sustained duration: yes / no

**Required entities:** `sensor.ws_fire_risk_score`
**Requires:** Fire Risk feature enabled

---

## Writing your own automations

All sensor entities are standard HA sensors and work with any automation trigger,
condition, or action. A few useful patterns:

**Trigger on rain starting:**
```yaml
trigger:
  - platform: state
    entity_id: event.ws_rain_event
    event_type: rain_start
```

**Condition: spray window is suitable:**
```yaml
condition:
  - condition: state
    entity_id: sensor.ws_delta_t
    attribute: spray_suitability
    state: ideal
```

**Action: apply calibration offset:**
```yaml
action:
  - service: ws_core.apply_calibration
    data:
      cal_temp_c: -0.5
```
