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

### Heat Alert (`heat_alert.yaml`)

Sends a notification when the feels-like temperature (apparent temperature) stays above
a configurable threshold for a sustained period. Uses the ws_core alert hysteresis, so
a single brief spike won't trigger.

**Configurable parameters:**
- Feels-Like Temperature Sensor (e.g. `sensor.ws_feels_like`)
- Heat threshold (°C, default: 35 °C, range 20–55 °C)
- Notification target (e.g. `notify.mobile_app_phone`)
- Cooldown between repeated notifications (minutes, default: 60)

**Required entities:** `sensor.ws_feels_like` (or any temperature sensor with device class `temperature`)

---

### Freeze Alert (`freeze_alert.yaml`)

Notifies when temperature drops to or below a freeze threshold. Optionally calls a
switch off — useful for shutting down irrigation controllers automatically before frost.

**Configurable parameters:**
- Temperature sensor (e.g. `sensor.ws_temperature`)
- Freeze threshold (°C, default: 0 °C, range −10 to +5 °C)
- Notification target
- Irrigation switch to turn off (optional)

**Required entities:** `sensor.ws_temperature` (or any temperature sensor)

---

### Rain Start / Stop (`rain_start.yaml`)

Triggers when rain starts (rate rises above a minimum threshold) or stops. Uses the
filtered rain rate sensor so brief sensor noise doesn't cause false positives.
Supports optional extra actions on start and stop — for example closing an awning
when rain starts or reopening it after rain stops.

**Configurable parameters:**
- Rain Rate Sensor (e.g. `sensor.ws_rain_rate`)
- Minimum rain rate to be considered raining (mm/h, default: 0.5)
- Trigger on: rain starts / rain stops / both (default: both)
- Notification target
- Additional action on rain start (optional — e.g. close a cover)
- Additional action on rain stop (optional)

**Required entities:** `sensor.ws_rain_rate`

---

### High Wind / Gust Alert (`high_wind.yaml`)

Notifies when wind gusts exceed a threshold for a sustained duration. Optionally
retracts covers, awnings, or other wind-sensitive devices automatically.

**Configurable parameters:**
- Wind Gust Sensor (e.g. `sensor.ws_wind_gust`)
- Gust threshold (m/s, default: 10.0 m/s = ~36 km/h = Beaufort 5)
- Sustained duration before triggering (minutes, default: 2)
- Notification target
- Cover / awning entities to retract (optional)

**Required entities:** `sensor.ws_wind_gust`

---

### Poor Air Quality Alert (`poor_aqi.yaml`)

Notifies when the Air Quality Index crosses a configurable threshold. Optionally
closes windows or activates air purifiers. Trigger is debounced — AQI must be above
the threshold for 10 minutes before alerting.

**Configurable parameters:**
- AQI Sensor (e.g. `sensor.ws_air_quality_index`)
- AQI alert threshold (default: 100 — "Unhealthy for Sensitive Groups")
- Notification target
- Window / vent cover or switch entities to close (optional)
- Air purifier switch or fan entities to activate (optional)

**Required entities:** `sensor.ws_air_quality_index`
**Requires:** Air Quality feature enabled in Configure → Features

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
