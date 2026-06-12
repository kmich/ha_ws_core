# Quickstart

This page gets you from zero to a working installation in about 5 minutes.

## Requirements

- Home Assistant 2026.3 or newer
- A personal weather station already integrated into HA, providing at minimum:

| Measurement | Example entity |
|---|---|
| Outdoor temperature | `sensor.gw2000a_outdoor_temperature` |
| Outdoor relative humidity | `sensor.gw2000a_outdoor_humidity` |
| Atmospheric pressure | `sensor.gw2000a_absolute_pressure` |
| Wind speed | `sensor.gw2000a_wind_speed` |
| Wind gust | `sensor.gw2000a_wind_gust` |
| Wind direction (degrees) | `sensor.gw2000a_wind_direction` |
| Cumulative rainfall | `sensor.gw2000a_rain_total` |

Any HA-integrated weather station brand works (Ecowitt, Davis, WeatherFlow, Shelly,
Froggit, and others). The integration does not care which integration produced the
entities — it reads whatever you map.

**Optional sensors** (improves derived metrics if present): illuminance (lux),
UV index, dew point, battery level, solar radiation (W/m²).

---

## Step 1: Install via HACS

1. Open HACS in your Home Assistant sidebar
2. Go to **Integrations** and click the three-dot menu in the top right
3. Choose **Custom repositories**
4. Paste `https://github.com/kmich/ha_ws_core` and select category **Integration**
5. Click **Add**, then close the dialog
6. Search for "Weather Station Core" and click **Download**
7. Restart Home Assistant

### Manual installation (alternative)

Copy the `custom_components/ws_core/` directory from the repository into your HA
`custom_components/` directory, then restart Home Assistant.

---

## Step 2: Add the integration

1. Go to **Settings → Devices & Services**
2. Click **+ Add Integration**
3. Search for "Weather Station Core" and select it

The setup wizard opens and guides you through 8 steps.

---

## Step 3: Complete the setup wizard

### Step 1 — Name and prefix

Give your station a name (e.g. "Back Garden") and an entity ID prefix (e.g. `ws`).
All entities will use this prefix: `sensor.ws_temperature`, `sensor.ws_humidity`, etc.

### Step 2 — Required sensors

Map the 7 mandatory sensor entities from your weather station.

Use the entity picker to find each one. You can type the entity ID directly or browse
the picker. The integration accepts any sensor regardless of brand or integration source.

### Step 3 — Optional sensors

Map illuminance, UV index, dew point, battery level, and solar radiation sensors
if your station provides them. Leave any field blank to skip it.

- **Solar radiation (W/m²):** enables Penman-Monteith ET₀ and THSW index
- **Illuminance (lx):** enables cloud cover estimation and the 36-condition classifier

### Step 4 — Location and climate

Enter your hemisphere, climate region, and elevation. Home Assistant coordinates are
used to auto-detect your location if you have them set.

**Climate region** affects the Zambretti forecast's wind direction correction:
- Atlantic Europe (default for most of Europe)
- Mediterranean
- Continental / Inland
- Nordic / Scandinavia

### Step 5 — Display units

Choose your preferred units for temperature, wind speed, rainfall, and pressure.
These control how sensor values are displayed without affecting the underlying
calculations.

### Step 6 — Forecast provider

Enable the 7-day forecast and choose a provider. Open-Meteo is the default (free,
no API key, global coverage). See [Forecast Providers](forecast_providers.md) for
all options.

### Step 7 — Features

Toggle optional feature groups on or off. You can change these later via Configure.

| Feature | What it creates |
|---|---|
| Fire Risk | FWI, FFDI, FFWI, fire risk score |
| Fog | Fog probability |
| Thunderstorm Risk | Thunderstorm risk index |
| Sea Temperature | SST via Open-Meteo Marine API |
| Weather Underground | Upload to WU with credential validation |
| Air Quality | AQI, NO₂, ozone |
| Pollen | Grass, tree, weed pollen levels |
| Moon | Moon phase and illumination |
| Solar Forecast | PV generation forecast |
| Comfort Indices | Heat Index, UTCI, VPD, Delta-T, and more |
| Meteo Vigilance | France only — weather alert colour |
| Vigicrues | France only — river level |
| Station Diagnostics | Drift detection, data-quality score |
| FWI Components | Individual FWI moisture codes |
| Advanced Sensors | Zambretti number, hourly ET₀, smoothed wind direction |
| Precipitation Nowcast | Minutes until rain, intensity, 60-min total |

### Step 8 — Alerts

Set thresholds for wind gust, rain rate, and freeze warnings. These are configurable
as number entities on the device page after setup.

---

## Step 4: Verify the entities

After setup, go to **Settings → Devices & Services → Weather Station Core** and
click the device to see all created entities.

`binary_sensor.ws_package_ok` is `On` when all required source sensors are available.
If it shows `Off`, go to Configure and remap any missing source sensors.

---

## Next steps

- [Sensors Reference](sensors.md) — complete list of all entities
- [Dashboards](dashboards.md) — install the bundled dashboard in 2 minutes
- [Blueprints](blueprints.md) — automation blueprints for frost, storm, and irrigation alerts
- [Forecast Providers](forecast_providers.md) — change your NWP provider
- [Configure](#reconfigure) — all settings are changeable post-install via Configure

---

## Reconfigure

Every setting from the wizard is changeable after installation without reinstalling.

Go to **Settings → Devices & Services → Weather Station Core → Configure**.

The options flow mirrors the full setup wizard. Changes take effect after saving.

To remap a required or optional sensor (e.g. after replacing your weather station
hardware), use **Configure → Required sensors** or **Configure → Optional sensors**.
