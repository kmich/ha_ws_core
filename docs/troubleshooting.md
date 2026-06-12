# Troubleshooting

---

## Common issues

| Symptom | Likely cause | Fix |
|---|---|---|
| All sensors show "unavailable" | Source entities not found | Check source sensor entity IDs in Configure. Verify the entity exists in Developer Tools → States. |
| `binary_sensor.ws_package_ok` is Off | One or more required sources are unavailable | Open Configure and remap the missing source sensors. |
| Temperature statistics look wrong | Old `TOTAL_INCREASING` state class in history | Delete the temperature entity from the entity registry, then restart HA. |
| Rain rate stuck at 0 | Rain total sensor reset after replacement | Call the `ws_core.reset_rain_baseline` service from Developer Tools → Services. |
| Forecast shows "unavailable" | Provider API timeout or auth error | Check internet connectivity. Verify the API key if using OpenWeatherMap, Pirate Weather, or Météo France. The forecast retries automatically. |
| "Stale" warning on sensors | Source sensor stopped updating | Check your weather station hardware. Is the station powered and connected? |
| Weather Underground upload never succeeds | Wrong API credential | Use the **station key (password)** from `wunderground.com/member/devices`, not a read API key. |
| Blitzortung data not appearing | Auto-discovery needs restart | Restart HA after installing Blitzortung. ws_core discovers Blitzortung entities at startup. |
| Comfort indices sensors not created | Feature toggle is off | Toggle `switch.ws_enable_comfort_indices` on the device page, or Configure → Features. |
| FWI values very high on first run | Standard initial values | FWI moisture codes start at Van Wagner (1987) defaults (FFMC=85, DMC=6, DC=15) and self-correct within a few days. |
| Nowcast always shows unknown | Coordinates not set, or Open-Meteo timeout | Verify forecast coordinates are set in Configure → Forecast. Check internet connectivity. |

---

## Diagnostics export

Download a full diagnostics report via:
**Settings → Devices & Services → Weather Station Core → ⋮ → Download Diagnostics**

The export includes sensor availability, coordinator timing, feature toggle state,
and quality flags. Location data (coordinates) is redacted automatically.

Attach the diagnostics file to GitHub issues — it helps identify configuration
problems without requiring detailed manual description.

---

## Enabling debug logging

Add to your `configuration.yaml` to capture detailed logs:

```yaml
logger:
  default: warning
  logs:
    custom_components.ws_core: debug
```

Restart Home Assistant, reproduce the issue, then check **Settings → System → Logs**
or the `home-assistant.log` file. Filter for `ws_core` to find relevant entries.

---

## Resetting the rain baseline

If your weather station was replaced or the cumulative rain counter was reset, the
rain rate sensor may read incorrectly. Reset the internal baseline with:

```yaml
service: ws_core.reset_rain_baseline
```

Call from Developer Tools → Services, or trigger from an automation.

---

## Calibration corrections

If your station readings consistently differ from nearby reference stations (e.g.
airport METAR), apply a calibration offset:

```yaml
service: ws_core.apply_calibration
data:
  cal_temp_c: -0.5      # adjust temperature down by 0.5 °C
  cal_humidity: 3       # adjust humidity up by 3%
  cal_pressure_hpa: 0   # no pressure adjustment
  cal_wind_ms: 0        # no wind adjustment
```

Or adjust the number entities directly from the device page:
`number.ws_cal_temp`, `number.ws_cal_humidity`, `number.ws_cal_pressure`,
`number.ws_cal_wind`.

---

## Reporting bugs

Use the GitHub issue template at https://github.com/kmich/ha_ws_core/issues/new

Include:
1. Your HA version and ws_core version
2. The diagnostics export (download from the integration page)
3. Relevant log lines (with debug logging enabled if possible)
4. Steps to reproduce the issue
