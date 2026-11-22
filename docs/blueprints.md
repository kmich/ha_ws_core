# Automation Blueprints

`ws_core` includes eleven pre-configured automation blueprints located in `blueprints/automation/ws_core/`. Each blueprint imports directly into Home Assistant as an interactive, customizable automation with sensible threshold defaults and hysteresis.

---

## ⚡ 1-Click Blueprint Import

Click any badge below to import the blueprint directly into your Home Assistant instance:

| Blueprint | Purpose | 1-Click Import |
|---|---|---|
| **Weather Window Notification** | Notify ahead of an upcoming outdoor drying, garden work, or custom weather window (requires HA 2024.10.0+) | [![Import](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fkmich%2Fha_ws_core%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fws_core%2Fweather_window_notification.yaml) |
| **Rain Start Warning** | Alert via TTS or phone when rain begins or is imminent; close covers | [![Import](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fkmich%2Fha_ws_core%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fws_core%2Frain_start.yaml) |
| **Irrigation Rain Skip** | Automatically skip scheduled watering when rainfall or ET₀ indicates moist soil | [![Import](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fkmich%2Fha_ws_core%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fws_core%2Firrigation_rain_skip.yaml) |
| **High Wind Protection** | Automatically retract awnings and blinds when severe wind gusts are detected | [![Import](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fkmich%2Fha_ws_core%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fws_core%2Fhigh_wind.yaml) |
| **Freeze Warning** | Alert when temperature approaches freezing; optionally shut off outdoor water valves | [![Import](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fkmich%2Fha_ws_core%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fws_core%2Ffreeze_alert.yaml) |
| **Frost Alert** | Comprehensive frost warning combining temperature, dew point, and frost point | [![Import](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fkmich%2Fha_ws_core%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fws_core%2Ffrost_alert.yaml) |
| **Lightning Safety** | Alert when lightning strikes within range; send all-clear when 30 min clear | [![Import](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fkmich%2Fha_ws_core%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fws_core%2Flightning_safety.yaml) |
| **Heat Stress Alert** | Notify when UTCI / apparent temperature reaches dangerous levels for exercise | [![Import](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fkmich%2Fha_ws_core%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fws_core%2Fheat_stress.yaml) |
| **Storm Alert** | Notify when sudden barometric pressure drop signals an approaching storm | [![Import](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fkmich%2Fha_ws_core%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fws_core%2Fstorm_alert.yaml) |
| **Poor Air Quality** | Alert when AQI crosses safety threshold; optionally turn on air purifiers & close vents | [![Import](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fkmich%2Fha_ws_core%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fws_core%2Fpoor_aqi.yaml) |
| **Fire Danger Alert** | Warn when regional fire danger index crosses high threshold; optional precautionary misting | [![Import](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fkmich%2Fha_ws_core%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fws_core%2Ffire_danger_alert.yaml) |

---

## Detailed Blueprint Configurations

### 1. Rain Start / Stop (`rain_start.yaml`)
Triggers when rain starts (rain rate exceeds threshold) or stops. Uses a Kalman-filtered rain rate sensor so brief gauge vibrations or wind shakes don't cause false alarms.
* **Key parameters:** Rain Rate Sensor, Rain Rate Threshold (default: 0.5 mm/h), Rain Probability Threshold, Notification Service, Optional Actions on Start/Stop (e.g. retract awning, close motorized windows).

### 2. Irrigation Rain Skip (`irrigation_rain_skip.yaml`)
Prevents lawn and garden overwatering by evaluating measured rainfall and evapotranspiration (ET₀).
* **Key parameters:** Today's Rainfall Sensor (`sensor.ws_rain_today_mm`), Rain Skip Threshold (default: 5.0 mm), ET₀ Sensor, Irrigation Switch / Valve.

### 3. High Wind / Gust Alert (`high_wind.yaml`)
Safeguards outdoor awnings, pergolas, and blinds by monitoring sustained wind gusts.
* **Key parameters:** Wind Gust Sensor (`sensor.ws_wind_gust`), Gust Threshold (default: 10 m/s ~ 36 km/h), Sustained Duration, Target Cover Entities to Retract.

### 4. Lightning Safety (`lightning_safety.yaml`)
Alerts when `sensor.ws_lightning_proximity` turns `near` (from a detector such as the Ecowitt WH57, or from Blitzortung), optionally turns off a pool pump, and sends an "All Clear" once `sensor.ws_lightning_clearance` rises past your clearance time.
* **Key parameters:** Lightning Proximity Sensor, Lightning Clearance Sensor, Notification Service, optional Pool Switch, Safe Clearance Time (minutes).
* **Re-import after updating to 3.0.0.** The clearance timer now resumes after a restart instead of starting empty, and the updated blueprint ignores that jump so a restart cannot send a false "All Clear".

### 5. Freeze & Frost Alerts (`freeze_alert.yaml` & `frost_alert.yaml`)
Monitors outdoor temperatures and the scientific Buck (1981) frost point. Triggers before ice forms, enabling pre-emptive protection of sensitive plants and shutting off outdoor hose bibbs.
* **Key parameters:** Temperature & Frost Point Sensors, Alert Threshold, Optional Outdoor Valve Switch to Turn Off.

#### Optional early warning from Pattern Forecast {#frost-early-warning}
Both blueprints have two extra inputs: **Pattern Forecast frost sensor** (pick `sensor.ws_pattern_frost_12h`) and **Pattern frost probability threshold** (default 50 %). When the sensor is chosen, the alert also fires as soon as the probability reaches the threshold, before the temperature actually drops, and **only while that sensor's `maturity` attribute is `skilled`**. The Freeze blueprint also shuts the optional valve in that case. Leave the sensor empty and both blueprints behave exactly as before. See the [Pattern Forecast guide](guides/pattern_forecast.md).

### 6. Weather Window Notification (`weather_window_notification.yaml`) {#weather-window-notification}
Triggers ahead of an upcoming suitable activity window using Home Assistant's native `time` trigger against a `next_start` timestamp sensor (`sensor.ws_window_outdoor_drying_next_start`, `sensor.ws_window_garden_work_next_start`, or `sensor.ws_window_custom_next_start`). Requires Home Assistant **2024.10.0** or newer.
* **Key parameters:** Weather Window Next Start Sensor (`sensor` with `device_class: timestamp`), Lead Time Offset (default `-00:15:00`, i.e. 15 minutes before window start), Notification Service (`notify.persistent_notification` or mobile notify action), Optional Custom Message.

---

## Manual Blueprint Import (Alternative)

If you do not use My Home Assistant:
1. In Home Assistant, go to **Settings → Automations & Scenes → Blueprints**.
2. Click **Import Blueprint** (bottom right).
3. Paste the raw GitHub URL for any blueprint file:
   `https://raw.githubusercontent.com/kmich/ha_ws_core/main/blueprints/automation/ws_core/<blueprint_name>.yaml`
4. Click **Preview** and **Import**.
