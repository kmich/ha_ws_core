# Hardware Mapping Guide

`ws_core` is designed to be hardware-agnostic. It does not connect to your weather station directly; instead, it reads the generic sensor entities your station pushes into Home Assistant.

If you are using the Auto-Discovery feature during setup, your required sensors will be filled in automatically. However, if you need to map them manually, this guide shows exactly which sensors to select for the most common weather stations.

## Ecowitt / Ambient Weather
*Requires the official `ecowitt` or `ambient_network` integration.*

| `ws_core` Required Field | Ecowitt Entity Pattern | Notes |
|---|---|---|
| **Temperature** | `sensor.*_outdoor_temperature` | Do not map indoor temperature here. |
| **Humidity** | `sensor.*_outdoor_humidity` | |
| **Pressure** | `sensor.*_absolute_pressure` | Absolute pressure is preferred over relative. |
| **Wind Speed** | `sensor.*_wind_speed` | |
| **Wind Gust** | `sensor.*_wind_gust` | |
| **Wind Direction** | `sensor.*_wind_direction` | |
| **Rain Total** | `sensor.*_yearly_rain` or `_event_rain` | `ws_core` works best with a continually increasing counter, so `yearly_rain` is safest. |

**Optional Ecowitt Sensors to Map:**
*   **Solar Radiation:** `sensor.*_solar_radiation` (Enables Penman-Monteith ET0)
*   **UV Index:** `sensor.*_uv_index`
*   **Lightning Strikes:** `sensor.*_lightning_strike_count` (WH57)
*   **Lightning Distance:** `sensor.*_lightning_strike_distance` (WH57)

---

## WeatherFlow Tempest
*Requires the official `weatherflow` integration or local MQTT integration.*

| `ws_core` Required Field | Tempest Entity Pattern | Notes |
|---|---|---|
| **Temperature** | `sensor.*_air_temperature` | |
| **Humidity** | `sensor.*_relative_humidity` | |
| **Pressure** | `sensor.*_station_pressure` | Maps to absolute/station pressure. |
| **Wind Speed** | `sensor.*_wind_speed` | |
| **Wind Gust** | `sensor.*_wind_gust` | |
| **Wind Direction** | `sensor.*_wind_direction` | |
| **Rain Total** | `sensor.*_precipitation` | Maps to the accumulated precipitation sensor. |

**Optional Tempest Sensors to Map:**
*   **Solar Illuminance:** `sensor.*_illuminance`
*   **UV Index:** `sensor.*_uv`

---

## Davis Instruments (WeatherLink)
*Requires the `weatherlink` integration.*

| `ws_core` Required Field | Davis Entity Pattern | Notes |
|---|---|---|
| **Temperature** | `sensor.*_temp_out` | |
| **Humidity** | `sensor.*_hum_out` | |
| **Pressure** | `sensor.*_bar_absolute` | |
| **Wind Speed** | `sensor.*_wind_speed_avg` | |
| **Wind Gust** | `sensor.*_wind_gust_high` | |
| **Wind Direction** | `sensor.*_wind_dir` | |
| **Rain Total** | `sensor.*_rain_year` | |

---

## Netatmo Smart Weather Station
*Requires the official `netatmo` integration.*

| `ws_core` Required Field | Netatmo Entity Pattern | Notes |
|---|---|---|
| **Temperature** | `sensor.*_temperature` | Make sure to pick the Outdoor module. |
| **Humidity** | `sensor.*_humidity` | Outdoor module. |
| **Pressure** | `sensor.*_pressure` | From the Indoor module. |
| **Wind Speed** | `sensor.*_wind_strength` | Requires the Anemometer accessory. |
| **Wind Gust** | `sensor.*_gust_strength` | Requires the Anemometer accessory. |
| **Wind Direction** | `sensor.*_wind_direction` | Requires the Anemometer accessory. |
| **Rain Total** | `sensor.*_rain` | Requires the Rain Gauge accessory. |

---

## DIY / ESPHome / Shelly

If you built your own weather station using a Shelly UNI or ESPHome, you simply need to ensure your `sensor.*` entities output data in the correct unit class. 

*   **Pressure:** Must use `device_class: pressure`
*   **Wind Speed:** Must be in `m/s`, `km/h`, or `mph`. 
*   **Rain:** Must be a cumulative sensor (state class `total` or `total_increasing`), measuring in `mm` or `in`.

If your DIY wind sensor triggers very rapidly, consider using Home Assistant's `filter` platform to smooth the raw data before passing it into `ws_core`.
