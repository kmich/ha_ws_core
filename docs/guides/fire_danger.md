# Fire Danger Guide

Weather Station Core implements three regional fire danger systems. All three run
from your weather station data with no external API calls.

---

## System overview

| System | Region | Standard | Inputs |
|---|---|---|---|
| Canadian FWI | Global (origin: Canada) | Van Wagner (1987) | Temp, RH, wind, 24h rainfall |
| McArthur FFDI | Australia | Noble et al. (1980) | Temp, RH, wind, drought factor |
| Fosberg FFWI | US / global | Fosberg (1978) | Temp, RH, wind |

All three are enabled together via the **Fire Risk** feature toggle.

---

## Enabling fire danger

**During setup:** enable **Fire Risk** on the Features step.

**After setup:** Settings → Devices & Services → Weather Station Core → Configure →
Features → Fire Risk, or toggle `switch.ws_enable_fire_risk_score` on the device page.

---

## Canadian Fire Weather Index (FWI)

The FWI system (Van Wagner 1987) is the most comprehensive of the three. It models
fuel moisture at three depths and derives an index of fire intensity.

### Moisture codes

| Sensor | What it models | Time constant |
|---|---|---|
| `sensor.ws_fwi_ffmc` | Fine dead fuels, litter, surface grass | ~24 hours |
| `sensor.ws_fwi_dmc` | Loosely compacted duff, 5-10 cm depth | ~12 days |
| `sensor.ws_fwi_dc` | Deep compact organic layer, > 10 cm | ~52 days |

Moisture codes are updated once per calendar day and persist across HA restarts.
They self-correct within a few days from the Van Wagner (1987) standard start values.

### Derived indices

| Sensor | Description |
|---|---|
| `sensor.ws_fwi_isi` | Initial Spread Index — expected initial fire spread rate |
| `sensor.ws_fwi_bui` | Buildup Index — total available fuel |
| `sensor.ws_fwi` | Fire Weather Index — intensity of a spreading fire |
| `sensor.ws_fwi_dsr` | Daily Severity Rating — operational difficulty of fire control |

The sub-components (FFMC, DMC, DC, ISI, BUI) are enabled separately via `enable_fwi_components`
to reduce entity count if you only need the composite FWI and DSR.

### Display scale

`sensor.ws_fire_risk_score` maps the FWI to a 1-10 display scale:

| FWI | Fire danger | Score |
|---|---|---|
| < 5 | Very Low | 1 |
| 5-11 | Low | 2 |
| 12-21 | Moderate | 3-4 |
| 22-32 | High | 5-6 |
| 33-49 | Very High | 7-8 |
| ≥ 50 | Extreme | 10 |

---

## McArthur Fire Danger Index (FFDI)

Used operationally in Australia by the Bureau of Meteorology. Computed from
temperature, relative humidity, wind speed, and the FWI drought factor (which
approximates soil moisture depletion).

`sensor.ws_ffdi` — values above 50 correspond to Catastrophic (Code Red) conditions
in the Australian rating system.

---

## Fosberg Fire Weather Index (FFWI)

A simpler index used by NOAA and the US Forest Service. Combines a moisture content
estimate from temperature and relative humidity with wind speed to produce a 0-100
scale of fire weather severity.

`sensor.ws_ffwi` — values above 50 indicate extreme fire weather conditions.

---

## Automation: fire danger alert

See [Blueprints](../blueprints.md) for the `fire_danger_alert.yaml` blueprint that
sends a notification when `sensor.ws_fire_risk_score` reaches a threshold.

Example manual automation:
```yaml
trigger:
  - platform: numeric_state
    entity_id: sensor.ws_fire_risk_score
    above: 6
condition:
  - condition: time
    after: "07:00:00"
    before: "22:00:00"
action:
  - service: notify.mobile_app_phone
    data:
      title: "Fire danger alert"
      message: >
        Fire risk score: {{ states('sensor.ws_fire_risk_score') }}/10.
        FWI: {{ states('sensor.ws_fwi') }}.
```

---

## Disclaimer

These sensors are informational only and are not suitable for operational fire weather
decisions. Consult your national fire service, Bureau of Meteorology (Australia), or
equivalent authority for official fire danger ratings.

**References:**
- Van Wagner, C.E. (1987). *Development and structure of the Canadian Forest Fire
  Weather Index System.* Forestry Technical Report 35. Canadian Forestry Service.
- Fosberg, M.A. (1978). *Weather in wildland fire management: the fire weather index.*
  In: Proceedings: Conference on Sierra Nevada Meteorology.
- Noble, I.R., Bary, G.A.V., Gill, A.M. (1980). *McArthur's fire-danger meters expressed
  as equations.* Australian Journal of Ecology, 5, 201-203.
