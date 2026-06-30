# Migrating from Thermal Comfort

This page maps every Thermal Comfort sensor to its Weather Station Core equivalent
and provides a 5-step migration procedure.

Thermal Comfort (last release: February 2025) provides heat-stress comfort indices
as a template-free HA integration. Weather Station Core includes all of those indices
and extends them significantly.

---

## Entity mapping

Thermal Comfort entity IDs follow `sensor.<name>_<metric>`. ws_core uses
`sensor.ws_<metric>` (or your chosen prefix, set in step 1 of setup).

| Thermal Comfort sensor | ws_core equivalent | Notes |
|---|---|---|
| `sensor.<name>_apparent_temperature` | `sensor.ws_feels_like` | Same formula: Australian BOM / Steadman (1994). Values match within 0.1 °C for identical inputs. |
| `sensor.<name>_heat_index` | `sensor.ws_heat_index` | Same formula: NWS Rothfusz regression. Active when T ≥ 27 °C and RH ≥ 40%. |
| `sensor.<name>_heat_index_perception` | Attribute `level` on `sensor.ws_heat_index` | Classification is in the sensor attribute, not a separate entity. |
| `sensor.<name>_humidex` | `sensor.ws_humidex` | Same formula: Environment Canada (Masterton & Richardson 1979). |
| `sensor.<name>_humidex_perception` | Attribute `level` on `sensor.ws_humidex` | See heat_index_perception note above. |
| `sensor.<name>_absolute_humidity` | `sensor.ws_absolute_humidity` | Same formula: ideal gas law for water vapour. |
| `sensor.<name>_dew_point` | `sensor.ws_dew_point` | ws_core uses Magnus formula (Alduchov & Eskridge 1996). Typical difference: < 0.2 °C. |
| `sensor.<name>_frost_point` | `sensor.ws_frost_point` | ws_core uses Buck (1981) ice constants below 0 °C — more physically accurate. |
| `sensor.<name>_wind_chill` | `sensor.ws_wind_chill` | Same formula: WMO/NWS 2001. Active when T ≤ 10 °C and wind > 1.34 m/s. |
| `sensor.<name>_thw_index` | `sensor.ws_thw_index` | Same formula: Davis Instruments THW index. |
| `sensor.<name>_thsw_index` | `sensor.ws_thsw_index` | Requires a solar radiation sensor mapped in ws_core. |
| `sensor.<name>_moist_air_enthalpy` | No direct equivalent | The `sensor.ws_vpd` sensor covers related HVAC/greenhouse use cases. |
| `sensor.<name>_relative_strain_index` | No direct equivalent | Not in ws_core. Keep Thermal Comfort alongside ws_core if needed. |
| `sensor.<name>_summer_simmer_index` | No direct equivalent | Not in ws_core. Keep Thermal Comfort alongside ws_core if needed. |

### Additional sensors ws_core provides beyond Thermal Comfort

| ws_core sensor | Description |
|---|---|
| `sensor.ws_utci` | UTCI (Universal Thermal Climate Index, Bröde 2012) — the WHO standard |
| `sensor.ws_wbgt` | Wet Bulb Globe Temperature |
| `sensor.ws_vpd` | Vapour Pressure Deficit (greenhouse, irrigation) |
| `sensor.ws_delta_t` | Delta-T spray application index |
| All fire danger sensors | FWI, FFDI, FFWI (see [Fire Danger](guides/fire_danger.md)) |
| Nowcast sensors | `ws_minutes_until_rain`, etc. |
| ET₀ sensors | `ws_et0_daily`, `ws_et0_pm_daily` |
| Lightning sensors | Strike count, distance, clearance |

---

## Formula differences

| Metric | Thermal Comfort | ws_core | Impact |
|---|---|---|---|
| Dew point | August-Roche-Magnus | Magnus, Alduchov & Eskridge (1996) | < 0.2 °C difference |
| Frost point | Same formula as dew point always | Buck (1981) ice constants below 0 °C | More accurate below 0 °C |
| Apparent temperature | Steadman (1994) BOM | Steadman (1994) BOM | Identical |
| Heat index | Rothfusz (1990) | Rothfusz (1990) | Identical |
| Wind chill | WMO/NWS 2001 | WMO/NWS 2001 | Identical |

---

## 5-step migration

### Step 1: Install ws_core alongside Thermal Comfort

Install Weather Station Core via HACS without removing Thermal Comfort. Both can run
simultaneously. This lets you verify that ws_core values match before switching
automations.

### Step 2: Enable comfort indices

In ws_core: Settings → Devices & Services → Weather Station Core → Configure →
Features → Comfort Indices.

Or toggle `switch.ws_enable_comfort_indices` on the device page.

### Step 3: Verify values

Open Developer Tools → States and compare:
- `sensor.<tc_name>_apparent_temperature` vs `sensor.ws_feels_like`
- `sensor.<tc_name>_heat_index` vs `sensor.ws_heat_index`
- `sensor.<tc_name>_dew_point` vs `sensor.ws_dew_point`

Differences of < 0.5 °C for all temperature sensors are expected. Larger differences
indicate a unit mismatch or input sensor issue.

### Step 4: Update automations and dashboards

Replace Thermal Comfort entity IDs with ws_core equivalents using the table above.
Do a find-and-replace on dashboard YAML for each entity ID pair.

### Step 5: Remove Thermal Comfort

Once automations and dashboards are confirmed working:
1. Settings → Devices & Services → Thermal Comfort → Delete
2. Restart Home Assistant

---

## Handling missing equivalents

Three Thermal Comfort sensors have no ws_core equivalent:
`moist_air_enthalpy`, `relative_strain_index`, `summer_simmer_index`.

Options:
- Keep Thermal Comfort installed alongside ws_core (they do not conflict)
- Recreate them as HA template sensors using the formulas from Thermal Comfort's
  source code (`custom_components/thermal_comfort/sensor.py`)

---

## Indoor-only use case

ws_core is designed for outdoor weather station data. If you use Thermal Comfort
only with indoor temperature and humidity sensors (no outdoor weather station),
ws_core's outdoor weather mode is not a direct replacement.

ws_core does have an Indoor Sensors group (`enable_indoor`) for monitoring
indoor comfort alongside outdoor weather - including named multi-room support,
where each room can have its own temperature, humidity and CO₂ sensors with
per-room delta and comfort sensors - but it still requires a full outdoor
station for the core integration to function.
