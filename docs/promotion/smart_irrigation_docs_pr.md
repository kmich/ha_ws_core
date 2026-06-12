# Smart Irrigation documentation PR proposal

This document contains a proposed PR to the Smart Irrigation integration's own
documentation, adding ws_core as a documented ET₀ source.

**Target repository:** https://github.com/jeroenterheerdt/HAsmartirrigation
(documentation may be in the repo or a separate docs site — check current state before submitting)

---

## PR title

```
Add Weather Station Core as a local ET₀ source option
```

## PR description

```markdown
## What this adds

Documentation for using Weather Station Core (`ws_core`) as a local ET₀ source
for Smart Irrigation.

Weather Station Core is a Home Assistant custom integration that derives 150+ sensors
from personal weather station data. It provides two ET₀ sensors:

- `sensor.ws_et0_pm_daily` — FAO-56 Penman-Monteith (±5-10% accuracy; requires solar
  radiation sensor)
- `sensor.ws_et0_daily` — Hargreaves-Samani 1985 (±15-20% accuracy; always available)

Using ws_core's ET₀ with Smart Irrigation gives fully local operation with no cloud
dependency for ET₀ calculation.

## Configuration

In Smart Irrigation, set the ET₀ source to Manual / Custom sensor and map:
- ET₀ entity: `sensor.ws_et0_pm_daily` (preferred) or `sensor.ws_et0_daily`
- Rainfall entity: `sensor.ws_rain_today`
- Unit: mm/day

See the ws_core documentation for setup details:
https://kmich.github.io/ha_ws_core/guides/smart_irrigation/

## Installation of ws_core

HACS custom repository: `https://github.com/kmich/ha_ws_core`

## Checklist
- [ ] The entity IDs are correct at v2.0.7
- [ ] The configuration steps have been tested
- [ ] The documentation addition fits the existing docs format
```

---

## Content to add to Smart Irrigation docs

Add the following under a "Local weather station" or "Custom ET₀ sources" section:

```markdown
### Weather Station Core

[Weather Station Core](https://github.com/kmich/ha_ws_core) is a Home Assistant
custom integration that derives ET₀ from personal weather station data without any
cloud dependency.

Two ET₀ sensors are available:

| Sensor | Formula | Requirements |
|---|---|---|
| `sensor.ws_et0_pm_daily` | FAO-56 Penman-Monteith (±5-10%) | Solar radiation sensor required |
| `sensor.ws_et0_daily` | Hargreaves-Samani 1985 (±15-20%) | None (temperature only) |

**Configuration in Smart Irrigation:**

1. Set ET₀ source to **Custom sensor**
2. Map `sensor.ws_et0_pm_daily` (or `sensor.ws_et0_daily` as fallback)
3. Map `sensor.ws_rain_today` as the precipitation sensor
4. Set unit to `mm`

To skip irrigation when rain is expected, use ws_core's
`binary_sensor.ws_rain_expected_1h` as a condition in your irrigation automation.
```

---

## Timing

Submit this PR after the main ws_core forum thread is live and has replies — being
able to link to community discussion strengthens the case that the integration is
actively used.
