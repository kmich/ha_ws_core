# Upgrading to 3.0

3.0.0 is a major release. Most installs update without doing anything, but read this page
first if you use automations on the sensors below, call ws_core actions from scripts, or
run an older Home Assistant.

## Before you update

- **Home Assistant 2024.12 or newer is required.** On 2024.6 to 2024.11, update Home
  Assistant first. HACS will not install 3.0.0 on an older version.
- **Take a backup** (Settings → System → Backups). Downgrading to 2.14.x works, but see
  [Pattern Forecast](#pattern-forecast-relearns-a-few-inputs) below.

## What changes for you

| Change | What it means | What to do |
|---|---|---|
| **Feels-like sensors show the air temperature** when their formula does not apply | Heat index, THW, THSW, wind chill and humidex used to be `unknown` outside their range (for example heat index below 27 °C). They now show the air temperature, as Davis and NWS stations do, with `formula_applies: false` | Automations that tested for `unknown` should test `formula_applies` instead. MQTT and exports still send no value when the formula does not apply |
| **Lightning proximity and clearance always have a value** | With a lightning detector or Blitzortung, `sensor.ws_lightning_proximity` reads `clear` when no strike is reported (`unknown` while the detector is unavailable), and `sensor.ws_lightning_clearance` keeps counting from the last strike across restarts | If you use the **Lightning Safety** blueprint, re-import it so a restart cannot send a false "all clear" |
| **Actions raise clear errors** | All ws_core actions now fail with an error message for an unknown station, an unknown profile or invalid limits, instead of returning `{}` or an `error` key | Scripts that checked the response for an error should handle the action error instead (for example `continue_on_error`) |
| **Leftover solar sensors are removed** | On stations without a solar radiation sensor (W/m²), the clearness index, cloud cover, THSW, solar energy, peak sun hours, net radiation and Penman-Monteith ET₀ entries left over from earlier versions are removed. They could never have a value. With the illuminance fallback and a lux sensor, only clearness index, cloud cover and THSW are removed | Remove dashboard cards that pointed at them. Mapping a solar radiation sensor later creates them again |
| **Turning a feature off removes its entities** | Unticking Weather Windows or one of its profiles removes those entities on reload | Nothing |
| **Removing the integration deletes its stored data** | Deleting a Weather Station Core entry also deletes its learning state, history, climate normals and Pattern Forecast files in `.storage` | Back up first if you might want that data back |
| **Alert messages stay stable; live readings move to attributes** | `sensor.ws_alert_message` now shows stable localized alert titles (e.g. `"Freeze risk"`) instead of changing state with every 0.1° reading, and the 3-tick clear debounce + hysteresis deadband (`+0.5 °C`, `-1.5 m/s`, `-1.0 mm/h`) now hold alerts steadily | Automations or templates parsing numbers from `sensor.ws_alert_message` state should read `detail_message` or `active_alerts` attributes instead |
| **60-minute rain flag drops Zambretti fallback** | `binary_sensor.ws_rain_expected_1h` no longer falls back to the 6–12 h Zambretti outlook when Open-Meteo nowcast is stale; it reads `on` (`source: local_rain`) if your gauge currently sees ≥ 0.1 mm/h, or `unknown` (with `status_text`) while dry | Automations relying on `binary_sensor.ws_rain_expected_1h` being `off` during nowcast outages should treat `unknown` as "nowcast unavailable" |
| **European AQI auto-selected in Europe** | `sensor.ws_air_quality_index` defaults to `aqi_scale: auto`, using the European EAQI (0–100+ scale with PM2.5, PM10, NO₂, O₃ and SO₂) for European stations and US EPA AQI (0–500) elsewhere | Switch back to `us` under **Configure → Features & Diagnostics → Air Quality** if your automations expect US EPA thresholds |
| **Frost risk follows your freeze threshold and the forecast** | `sensor.ws_frost_risk` now uses the forecast low for the next 12 hours (previously it was never read) and steps at `thresh_freeze_c` +0 / +2 / +4 °C, with hysteresis and debounce, so it may read higher earlier in the evening | Nothing, unless you changed `thresh_freeze_c`: the steps move with it |

## Pattern Forecast relearns a few inputs

On the first start, Pattern Forecast resets what it learned for two kinds of input that
earlier versions computed inconsistently: the 3-hour pressure change and the four solar
inputs. Everything else it learned is kept, including the event counts that decide when a
forecast is trusted.

- A full copy of the old state is written first, to
  `.storage/ws_core_<entry_id>_pattern_forecast_pre_v3_backup`.
- The pressure input relearns straight away from up to 90 days of your recorder history.
- The solar inputs relearn from live daylight readings over the following days and weeks.
  Forecasts keep working meanwhile.

## The options moved into a menu

**Configure** now opens a menu: *Sensor Sources*, *Weather Forecast & Location*,
*Decision Engine & Weather Windows*, *Indoor Rooms*, *Thresholds, Units & Calibration*,
*Weather Services & Uploads* and *Features & Diagnostics*. Your settings are unchanged; they
are just easier to find.

## New things worth turning on

- **[Weather Windows](guides/weather_windows.md):** when in the next 24 hours the weather
  suits drying laundry, garden work or your own activity.
- **Data Status** (`sensor.ws_data_status`, always on): one sensor that says whether
  anything needs attention, and why any other sensor is empty. See
  [sensors](sensors.md#data-status).
- **Local PV forecast:** pick your PV energy meters under *Features & Diagnostics → Solar
  Forecast* and ws_core learns a forecast from your real yield. See
  [sensors](sensors.md#optional-solar-pv-forecast-enable_solar_forecast).

The [changelog](https://github.com/kmich/ha_ws_core/blob/main/CHANGELOG.md) lists every
change.
