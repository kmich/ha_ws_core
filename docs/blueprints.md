# Automation Blueprints

`ws_core` includes ten pre-configured automation blueprints located in `blueprints/automation/ws_core/`. Each blueprint imports directly into Home Assistant as an interactive, customizable automation with sensible threshold defaults and hysteresis.

---

## ⚡ 1-Click Blueprint Import

Click any badge below to import the blueprint directly into your Home Assistant instance:

| Blueprint | Purpose | 1-Click Import |
|---|---|---|
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
Monitors nearby lightning strikes (e.g. from Ecowitt WH57 or WeatherFlow Tempest) and issues an alert, followed by an official "All Clear" announcement once no strikes occur within 30 minutes.
* **Key parameters:** Lightning Strike Count & Distance Sensors, Proximity Threshold (default: 16 km / 10 mi), Notification Service.

### 5. Freeze & Frost Alerts (`freeze_alert.yaml` & `frost_alert.yaml`)
Monitors outdoor temperatures and the scientific Buck (1981) frost point. Triggers before ice forms, enabling pre-emptive protection of sensitive plants and shutting off outdoor hose bibbs.
* **Key parameters:** Temperature & Frost Point Sensors, Alert Threshold, Optional Outdoor Valve Switch to Turn Off.

---

## Manual Blueprint Import (Alternative)

If you do not use My Home Assistant:
1. In Home Assistant, go to **Settings → Automations & Scenes → Blueprints**.
2. Click **Import Blueprint** (bottom right).
3. Paste the raw GitHub URL for any blueprint file:
   `https://raw.githubusercontent.com/kmich/ha_ws_core/main/blueprints/automation/ws_core/<blueprint_name>.yaml`
4. Click **Preview** and **Import**.
