# Automation Recipes & Real-World Benefits

Weather Station Core is designed to make your smart home **react to the weather automatically**.

Here are the most popular recipes and automations, complete with 1-click blueprint imports, recommended thresholds, and sample YAML.

---

## 1. 🌧️ Save the Laundry & Patio Cushions (Rain Alert)

**The Problem:** Rain starts while your laundry is drying on the line, patio cushions are outside, or upstairs skylights are wide open. Standard weather apps only give broad regional probabilities ("30% chance of rain in London") that don't tell you what's happening at your roof.

**The Solution:** `ws_core` pairs your station's physical rain gauge with 15-minute radar grids to calculate `sensor.ws_minutes_until_rain`.

[![Import Rain Start Blueprint](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fkmich%2Fha_ws_core%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fws_core%2Frain_start.yaml)

### Sample YAML Automation
```yaml
alias: "Weather: Rain Starting Soon Announcement"
description: "Broadcast an alert when rain is expected within 10 minutes."
trigger:
  - platform: numeric_state
    entity_id: sensor.ws_minutes_until_rain
    below: 10
condition:
  - condition: numeric_state
    entity_id: sensor.ws_minutes_until_rain
    above: 0
action:
  - action: tts.speak
    target:
      entity_id: tts.piper
    data:
      media_player_entity_id: media_player.living_room_speaker
      message: "Attention: rain is predicted to start in {{ states('sensor.ws_minutes_until_rain') }} minutes. Please close the patio doors."
  - action: notify.mobile_app_all_phones
    data:
      title: "🌧️ Rain Inbound"
      message: "Rain starting in ~{{ states('sensor.ws_minutes_until_rain') }} min."
```

---

## 2. 🌱 Smart Irrigation: Stop Watering After It Poured

**The Problem:** Typical timer-based irrigation controllers run on a schedule regardless of whether 25mm of rain fell yesterday. This wastes costly water and drowns roots.

**The Solution:** Use `ws_core` Evapotranspiration (ET₀) and today's rain accumulation (`sensor.ws_rain_today_mm`) to skip or adjust watering.

[![Import Irrigation Rain Skip Blueprint](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fkmich%2Fha_ws_core%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fws_core%2Firrigation_rain_skip.yaml)

### Recommended Sensors for Garden & Irrigation
* **Penman-Monteith Reference ET₀:** `sensor.ws_et0_penman_monteith` (best when solar radiation sensor is present).
* **Daily ET₀ (Hargreaves-Samani):** `sensor.ws_et0_daily` (no solar sensor required).
* **Today's Total Rainfall:** `sensor.ws_rain_today_mm`.
* **Smart Irrigation Integration:** Feed `sensor.ws_et0_penman_monteith` directly into the popular `HAsmartirrigation` integration as the evapotranspiration source.

---

## 3. 🌬️ Protect Outdoor Awnings & Blinds from Wind Gusts

**The Problem:** High summer convective storms or sudden squalls can produce 50+ km/h wind gusts in seconds, bending awning arms or snapping fabric sails before you have time to manually retract them.

**The Solution:** The `ws_core` sustained wind gust monitor detects peak gust velocities and issues immediate cover retraction commands.

[![Import High Wind Protection Blueprint](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fkmich%2Fha_ws_core%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fws_core%2Fhigh_wind.yaml)

### Recommended Gust Thresholds by Hardware
| Hardware Type | Safe Wind Gust Limit | Trigger Suggestion |
|---|---|---|
| Light fabric awning / shade sail | 10–12 m/s (~36–43 km/h) | Immediate retract |
| Motorized exterior venetian blinds | 12–15 m/s (~43–54 km/h) | Retract with 1 min debounce |
| Heavy-duty cassette awning | Check manufacturer rating (usually 15–18 m/s) | Retract on sustained gusts |

---

## 4. ❄️ Prevent Frozen Outdoor Pipes & Protect Delicate Plants

**The Problem:** Relying on simple ambient temperature often misses radiation frost, where surfaces drop below freezing even if the air sensor reads +2°C.

**The Solution:** `ws_core` derives the **Buck (1981) Frost Point** and **Frost Risk Category**, alerting you hours before damaging ice forms.

[![Import Freeze Alert Blueprint](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fkmich%2Fha_ws_core%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fws_core%2Ffreeze_alert.yaml)

### Key Entities
* `sensor.ws_frost_risk` (Human-readable: *None, Slight, Moderate, High, Severe*)
* `sensor.ws_frost_point` (Temperature at which frost will deposit on ground surfaces)
* `sensor.ws_frost_streak_days` (Count of consecutive freezing days)

---

## 5. ⚡ Lightning Proximity Safety (Physical Sensor or Free Blitzortung)

**The Problem:** Thunderstorms can produce lethal cloud-to-ground strikes miles ahead of the actual rain cloud.

**The Solution:** Works with hardware sensors (Ecowitt WH57, Tempest) **OR the free Blitzortung HA integration** (zero hardware needed!). If Blitzortung is installed, `ws_core` auto-discovers it, tracking strike distance and running a 30-minute "All Clear" countdown when no strikes have occurred.

[![Import Lightning Safety Blueprint](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fkmich%2Fha_ws_core%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fws_core%2Flightning_safety.yaml)

---

## 🏃 6. Heat Stress & Outdoor Activity Safety (UTCI & WBGT)

**The Problem:** Thermometers tell you ambient temperature, but they don't reflect how heat affects the human body under direct sunlight and high humidity.

**The Solution:** `ws_core` calculates the Universal Thermal Climate Index (**UTCI**) and Wet-Bulb Globe Temperature (**WBGT**) — the official standards used by the World Health Organization and OSHA for heat stress warnings during sports and construction.

[![Import Heat Stress Blueprint](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fkmich%2Fha_ws_core%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fws_core%2Fheat_stress.yaml)

---

## 🌿 7. Plant Health & Spraying Windows (Delta-T, VPD, Leaf Wetness)

**The Problem:** Applying foliar fertilizer, fungicides, or organic treatments at the wrong time wastes money: if Delta-T is too high, the droplets evaporate before absorption; if too low, droplets don't dry, increasing fungal risk.

**The Solution:** `ws_core` computes agricultural-grade microclimate metrics:
* **Delta-T Spray Window:** `sensor.ws_delta_t` provides an attribute `spray_suitability` (`ideal`, `marginal`, `unacceptable`).
* **VPD (Vapor Pressure Deficit):** `sensor.ws_vpd` tells greenhouse growers and plant enthusiasts whether leaves are transpiring optimally.
* **Leaf Wetness:** `sensor.ws_leaf_wetness` estimates when condensation remains on foliage, helping you predict and prevent black spot, powdery mildew, and blight.

---

## ⚡ 8. Energy & HVAC Optimization (Heating & Cooling Degree Days)

**The Problem:** Heat pumps and AC units consume electricity reactively, spiking bills during peak-tariff hours.

**The Solution:** Track thermal loads with scientific **Degree Days**:
* **Heating Degree Days (HDD):** `sensor.ws_hdd` measures how cold the day was relative to a base comfort temperature, allowing you to correlate exactly with heating gas or heat pump kWh.
* **Cooling Degree Days (CDD):** `sensor.ws_cdd` measures summer heat load to trigger pre-cooling automations when solar production is peaked or electricity is cheap.
* **Growing Degree Days (GDD):** `sensor.ws_gdd` tracks thermal accumulation to predict lawn growth spurts and harvest dates.

---

## 🌍 9. 10-Year Climate Normals (ERA5 Historical Comparison)

**The Problem:** Weather apps tell you it's 24°C, but is that typical or an extreme anomaly for today?

**The Solution:** Enable **Climate Normals** under **Configure → Features**. `ws_core` queries the Open-Meteo ERA5 10-year archive for your specific coordinates, populating:
* `sensor.ws_temp_anomaly_normal`: Tells you: *"Today is +3.8°C warmer than the 10-year historical average for this date."*
* `sensor.ws_precip_anomaly_normal`: Compares rainfall against your location's historical seasonal benchmarks.

---

## ❄️ 10. Snow Accumulation & Phase Estimation (Without a Snow Gauge)

**The Problem:** Traditional tipping-bucket rain gauges cannot measure snow until it melts, leaving a blank spot in winter automation.

**The Solution:** `ws_core` uses wet-bulb temperature, surface temperature, and precipitation rate to determine precipitation phase (rain, freezing rain, sleet, snow) and derives estimated snow accumulation (`sensor.ws_snow_rate_hourly` and `sensor.ws_snow_accumulation_24h`), so you know when to salt driveways or turn on pipe heating cables.

---

## 🎯 11. Instant Automations with Native HA Events

Instead of writing slow, poll-based YAML, `ws_core` provides native **Home Assistant Event Entities** for instant sub-second execution:

* `event.ws_rain_event` (`started`, `stopped`)
* `event.ws_frost_event` (`onset`, `thaw`)
* `event.ws_lightning_event` (`strike`)

```yaml
alias: "Instantly Close Blinds on Rain"
trigger:
  - platform: state
    entity_id: event.ws_rain_event
    to: "started"
action:
  - action: cover.close_cover
    target:
      entity_id: cover.patio_shades
```
