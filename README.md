# Weather Station Core (`ws_core`)

[![HACS][hacs-badge]][hacs-url]
[![GitHub Release][release-badge]][release-url]
[![License][license-badge]][license-url]
[![Validate][validate-badge]][validate-url]
[![Translations][translation-badge]][translation-url]

**The Intelligence Layer for your Home Assistant Weather Station.**

Turn any weather station into a complete weather intelligence system: local forecasting, precipitation nowcasting, fire danger, irrigation, lightning detection, and data quality. 150+ sensors. Fully local-capable. No API keys required for core features.

![Enhanced dashboard](screenshots/dashboard-advanced.png)

---

## 🚀 What does it do?

* **Never Get Caught in the Rain:** Uses your live rain gauge to correct cloud forecasts, giving you a countdown to the minute the rain starts (`sensor.ws_minutes_until_rain`).
* **Stop the Sprinklers Precisely:** Calculates exact Evapotranspiration (ET0) so your smart irrigation system knows exactly how much water the lawn actually needs.
* **Offline Zambretti Forecast:** Predicts the next 12 hours based purely on your local barometric pressure trends, even if the internet goes down.
* **Automate Everything:** Includes 5 ready-to-use blueprints for TTS alerts, freeze warnings, and high-wind awning retraction.

---

## 📡 Does it work with my station?

**If your station is in Home Assistant, it works with `ws_core`.**

It is tested heavily with Ecowitt, WeatherFlow Tempest, Ambient Weather, Davis Instruments, Netatmo, and local MQTT sensors. All you need are standard sensors like temperature, humidity, pressure, and wind.

---

## ⚡ The 60-Second Quickstart

### Install via HACS (Recommended)

1. Open **HACS** in your Home Assistant sidebar.
2. Go to **Integrations** → ⋮ → **Custom repositories**.
3. Add `https://github.com/kmich/ha_ws_core` as an **Integration**.
4. Search for "Weather Station Core", install, and restart Home Assistant.

### Configure

Go to **Settings → Devices & Services → Add Integration** and search for "Weather Station Core". The setup wizard asks you to map 7 basic sensors:

* Temperature, Humidity, Absolute Pressure, Wind Speed, Wind Gust, Wind Direction, Rain Total

That's it! After the wizard completes, 50+ derived sensors appear automatically. Enable additional features like fire danger or nowcasting via the **Configure** button on the integration.

---

## 📊 The "Wow" Dashboards

`ws_core` comes with drop-in, premium Lovelace dashboards for your data.

| Mobile View | Desktop View |
|---|---|
| ![Mobile dashboard](screenshots/dashboard-weather.png) | ![Desktop dashboard](screenshots/dashboard-advanced.png) |

Check out the `dashboards/` directory for the YAML code. We provide:
* A `vanilla` dashboard using only native HA cards.
* An `enhanced` dashboard using popular custom cards (`mini-graph-card`, `mushroom`).
* Ready-to-use gauge presets with sensible severity color bands.

---

## 🤖 Top Automations

Don't reinvent the wheel. We've included import-ready blueprints to automate your home based on your local weather:

* [**Rain Start Warning:**](blueprints/automation/ws_core/rain_start.yaml) Announce over TTS or send a push notification when rain is expected in the next few minutes.
* [**Freeze Warning:**](blueprints/automation/ws_core/freeze_alert.yaml) Trigger actions when the temperature drops below freezing.
* [**High Wind Gusts:**](blueprints/automation/ws_core/high_wind.yaml) Automatically retract your awnings or close the blinds when a high gust is recorded.
* [**Heat Stress / UTCI:**](blueprints/automation/ws_core/heat_stress.yaml) Notify when outdoor conditions become dangerous for work or exercise.
* [**Poor Air Quality:**](blueprints/automation/ws_core/poor_aqi.yaml) Close the windows and turn on the air purifiers when PM2.5 spikes.

---

## 🔬 Advanced Features (The "Nerd" Section)

Behind the scenes, `ws_core` implements rigorous meteorological and scientific algorithms to derive the most accurate insights from your station's data:

* **UTCI & WBGT:** The gold-standard heat-stress indices used by the WHO.
* **Three Fire Danger Systems:** Canadian FWI, Australian McArthur FFDI, and US Fosberg FFWI.
* **Stull Wet Bulb & Buck Frost Point:** Precise derivations with ice-constant handling.
* **Nowcast Ground-Truth Blending:** Combines Open-Meteo 15-minute grids with your live rain gauge data (70% local / 30% NWP) for the best short-term prediction.
* **Network Uploads:** Syncs to 8 networks simultaneously (WUnderground, Weathercloud, PWSWeather, WOW, AWEKAS, CWOP, OWM, Windy).
* **Adaptive Rain Probability:** Learns over a rolling 90-day window whether the local heuristics or the NWP forecasts have been more accurate.

For the math, citations, and formulas behind these features, read the [**Scientific Documentation**](docs/science.md).

---

## ❓ FAQ & Troubleshooting

* **Why are my entities unavailable?**
  Ensure your source sensors are online. If a required sensor (like temperature) is unavailable, dependent derived metrics will gracefully become `unavailable` until the source recovers.
* **Which sensors do I select during setup?**
  If Auto-Discovery didn't find your station, read our [Hardware Mapping Guide](docs/hardware_mapping.md) for exactly which Ecowitt, Tempest, or Netatmo entities to select.
* **How do I migrate from the Thermal Comfort integration?**
  We have a dedicated [migration guide](docs/migrating_from_thermal_comfort.md) with step-by-step instructions.
* **Do I need an API Key?**
  No. All core features run completely offline locally. Optional features like Air Quality or Nowcast use free APIs that require no registration.

---

[hacs-badge]: https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge
[hacs-url]: https://github.com/hacs/integration
[release-badge]: https://img.shields.io/github/v/release/kmich/ha_ws_core?style=for-the-badge
[release-url]: https://github.com/kmich/ha_ws_core/releases
[license-badge]: https://img.shields.io/github/license/kmich/ha_ws_core?style=for-the-badge
[license-url]: https://github.com/kmich/ha_ws_core/blob/main/LICENSE
[validate-badge]: https://img.shields.io/github/actions/workflow/status/kmich/ha_ws_core/validate.yaml?branch=main&label=validate&style=for-the-badge
[validate-url]: https://github.com/kmich/ha_ws_core/actions/workflows/validate.yaml
[translation-badge]: https://img.shields.io/badge/Translations-8-blue?style=for-the-badge
[translation-url]: https://github.com/kmich/ha_ws_core/tree/main/custom_components/ws_core/translations
