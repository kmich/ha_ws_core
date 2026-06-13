# Irrigation and ET₀ Guide

Weather Station Core provides two ET₀ (reference evapotranspiration) sensors for
irrigation scheduling and water budget management.

ET₀ is the water demand of a reference grass surface under current atmospheric
conditions. It is the standard input for computing crop water requirements.

---

## ET₀ sensors

| Sensor | Formula | When available | Accuracy |
|---|---|---|---|
| `sensor.ws_et0_daily` | Hargreaves-Samani (1985) | Always (once coordinates are set) | ±15-20% vs Penman-Monteith |
| `sensor.ws_et0_pm_daily` | FAO-56 Penman-Monteith | When a solar radiation (W/m²) sensor is mapped | ±5-10% vs lysimeter |

Both sensors update daily. Penman-Monteith is preferred when available; use
Hargreaves-Samani as a fallback if you do not have a solar radiation sensor.

---

## Hargreaves-Samani (1985)

Requires only temperature and latitude-derived extraterrestrial radiation:

```
ET₀ = 0.0023 · Ra · (T_mean + 17.8) · (T_max − T_min)^0.5
```

- `Ra`: extraterrestrial radiation, computed from latitude and day-of-year
- Uses today's temperature high, low, and mean from ws_core's rolling statistics

**Tendency to overestimate in humid climates; underestimate in arid conditions.**

**Reference:** Hargreaves, G.H. & Samani, Z.A. (1985). *Reference crop
evapotranspiration from temperature.* Appl. Eng. Agric., 1, 96-99.

---

## FAO-56 Penman-Monteith

The internationally standard reference method (Allen et al. 1998 / FAO-56):

```
ET₀ = [0.408·Δ·(Rn − G) + γ·(900/(T+273))·u₂·(eₛ − eₐ)] / [Δ + γ·(1 + 0.34·u₂)]
```

Requires:
- Temperature (T), mean
- Relative humidity (for eₛ and eₐ)
- Wind speed at 2m height (u₂), automatically converted from 10m sensor
- Net radiation (Rn), derived from the mapped solar radiation sensor
- Soil heat flux (G), approximated as 0 for daily timestep

**Reference:** Allen, R.G., Pereira, L.S., Raes, D., Smith, M. (1998).
*Crop evapotranspiration — Guidelines for computing crop water requirements.*
FAO Irrigation and Drainage Paper 56. FAO, Rome.

---

## Using ET₀ for irrigation decisions

A simple daily water budget:

```
Irrigation needed (mm) = ETₒ × Kc − effective_rainfall
```

Where `Kc` is a crop coefficient (typically 0.6-1.2 depending on crop type and
growth stage). See FAO-56 Annex tables for crop coefficients.

The `sensor.ws_irrigation_deficit` entity (part of the Comfort Indices group)
computes this value automatically using the Penman-Monteith ET₀ and today's
rainfall accumulation.

---

## Smart Irrigation integration

See the [Smart Irrigation Bridge guide](smart_irrigation.md) for step-by-step
configuration of ws_core's ET₀ as an input to the Smart Irrigation HA integration.

---

## Soil sensor integration (v2.1+)

When soil moisture or temperature sensors are available, enable the **Soil Sensors** feature group in Configure → Features.

### Enabling soil sensors

1. Go to Settings → Devices & Services → Weather Station Core → Configure
2. On the **Sources** step, map your soil moisture sensor and/or soil temperature sensor
3. On the **Features** step, enable **Soil sensors**
4. Restart is not required — sensors appear on the next coordinator update

### Sensors added

| Sensor | Description |
|---|---|
| `sensor.ws_soil_moisture` | Volumetric moisture %. Accepts 0–100% or 0–1 (auto-detected) |
| `sensor.ws_soil_temperature` | Soil temperature in °C |
| `sensor.ws_soil_moisture_deficit` | Difference between 40% field capacity and current moisture |
| `sensor.ws_irrigation_need` | Text label: None / Low / Moderate / High / Critical |
| `sensor.ws_irrigation_need_score` | 0–100 demand score |

### Irrigation need score calculation

```
score = min(100, soil_deficit × 1.5 + max(0, ET₀_today − rain_today) × 5)
```

| Score | Label |
|---|---|
| 0–9 | None |
| 10–24 | Low |
| 25–49 | Moderate |
| 50–74 | High |
| 75–100 | Critical |

### Example automation: irrigate only when needed

```yaml
alias: "Garden: irrigate when soil needs water"
trigger:
  - platform: time
    at: "06:00:00"
condition:
  - condition: state
    entity_id: sensor.ws_irrigation_need
    state_not: "None"
  - condition: state
    entity_id: binary_sensor.ws_rain_expected_1h
    state: "off"
action:
  - service: switch.turn_on
    target:
      entity_id: switch.garden_irrigation
```
