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
| FWI moisture codes don't change in the morning | By design (2.8.0+) | The codes advance once a day on the first reading at or after 12:00 local time, the observation time the FWI system is defined on. ISI/FWI still follow the current wind. |
| Repairs shows a "stuck sensors" issue | A reading has not changed for hours | Temperature is flagged after 4 h without any change, humidity and pressure after 6 h (humidity at 0-2 % or 98-100 % is never flagged). Check the sensor and its radiation shield; the issue clears as soon as the value moves. With several stations, each entry raises its own issue. |
| Nowcast always shows unknown | Coordinates not set, or Open-Meteo timeout | Verify forecast coordinates are set in Configure → Forecast. Check internet connectivity. |
| Lightning sensor rejected as "entity not found" during setup | Older versions rejected sensors sitting at `unknown` | Update to 2.4.1+. Lightning distance/azimuth/count sensors are idle (`unknown`) outside a strike and are now accepted as long as the entity exists. |
| Hemisphere / climate region shows a raw value like `atlantic_europe` | Translation not loaded for your language | These are localized in English and French (2.5.0+); other languages fall back to English. Restart HA after updating so new translations load. |

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

### Adaptive (auto-apply) calibration

If you'd rather not track down a reference station yourself, enable **Feature:
Adaptive Sensor Calibration** under **Configure → Features**. It's off by
default. When on, it reuses the regional forecast reference point already
fetched hourly for neighbor QC as a slow-moving comparison: temperature,
humidity, and pressure each get a residual-bias estimate that only settles
after many samples (~10 days), and only once that bias is both confident and
outside a noise deadband does it nudge the same `cal_temp_c` / `cal_humidity`
/ `cal_pressure_hpa` options above - by a small, bounded amount, at most once
per day, never overshooting the learned bias. It never touches wind, since a
grid-model comparison for wind is too dependent on local terrain to trust.

Watch `sensor.ws_auto_calibration` to see what it has learned (`learning` /
`stable` / `adjusted`, plus the current bias estimate for each field and the
date it last nudged something) before deciding whether to leave it on. You
can always turn the toggle off, or override the calibration numbers by hand
at any time - manual changes are respected the same way either way.

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
