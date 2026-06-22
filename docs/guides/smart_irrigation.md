# Smart Irrigation Bridge

This guide shows how to use ws_core's ET₀ sensors as the input for the
[Smart Irrigation](https://github.com/jeroenterheerdt/HAsmartirrigation) integration.

Smart Irrigation uses ET₀ to calculate how much to irrigate each day, accounting for
rainfall. ws_core provides the ET₀ value; Smart Irrigation decides the watering schedule.

---

## Prerequisites

- Weather Station Core installed and configured
- [Smart Irrigation](https://github.com/jeroenterheerdt/HAsmartirrigation) installed via HACS
- A solar radiation sensor mapped in ws_core (for Penman-Monteith ET₀)
  OR acceptance of the Hargreaves-Samani approximation

---

## Which ET₀ sensor to use

Use `sensor.ws_et0_pm_daily` if you have a solar radiation sensor mapped in ws_core.
This uses FAO-56 Penman-Monteith with ±5-10% accuracy.

Use `sensor.ws_et0_daily` if you do not have a solar radiation sensor. This uses
Hargreaves-Samani with ±15-20% accuracy. Adequate for most residential irrigation
scheduling.

---

## Step 1: Configure Smart Irrigation with a manual ET₀ source

In Smart Irrigation configuration, when prompted for the ET₀ source, choose
**Manual / Custom sensor** (the exact option name may vary by Smart Irrigation version).

---

## Step 2: Map the ET₀ entity

Set the ET₀ entity to:
- **Preferred:** `sensor.ws_et0_pm_daily`
- **Fallback:** `sensor.ws_et0_daily`

Set the unit to `mm` (millimetres per day).

---

## Step 3: Map the rainfall entity

Smart Irrigation also needs daily rainfall. Map:
- `sensor.ws_rain_today` for today's accumulated rainfall

This sensor resets at local midnight and accumulates rain from your physical gauge.
The unit is `mm`.

---

## Step 4: Verify the values

After one full day of operation, check that:
1. `sensor.ws_et0_pm_daily` (or `ws_et0_daily`) shows a non-zero value
2. `sensor.ws_rain_today` shows today's rainfall correctly
3. Smart Irrigation shows a sensible irrigation time calculation for your zone

Typical Penman-Monteith ET₀ values:
- Temperate summer: 3-6 mm/day
- Mediterranean summer: 6-9 mm/day
- Arid summer: 8-12 mm/day

---

## Step 5: Set up the irrigation skip automation

Use the ws_core `irrigation_rain_skip.yaml` blueprint (see [Blueprints](../blueprints.md))
to automatically skip irrigation when:
- Rain accumulated in the past 24h exceeds a threshold, OR
- Rain is expected in the next hour (`binary_sensor.ws_rain_expected_1h` is On)

---

## Sample automation (without blueprint)

```yaml
alias: "Irrigation: rain skip"
trigger:
  - platform: state
    entity_id: binary_sensor.ws_rain_expected_1h
    to: "on"
  - platform: numeric_state
    entity_id: sensor.ws_rain_last_24h
    above: 10
action:
  - service: switch.turn_off
    target:
      entity_id: switch.smart_irrigation_<zone_name>
```

Replace `<zone_name>` with your Smart Irrigation zone switch entity ID.
