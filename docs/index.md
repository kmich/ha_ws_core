# Weather Station Core

Weather Station Core (`ws_core`) is a Home Assistant integration for personal weather stations. It reads the temperature, humidity, pressure, wind and rain sensors your station already provides and calculates the things you'd actually automate on: frost point, heat stress, evapotranspiration for irrigation, fire danger, a barometric outlook, and short-term rain, frost and gust chances learned from your own station's history.

Derived values are calculated inside Home Assistant. By default ws_core also fetches a weather forecast and runs an hourly sanity check against Open-Meteo; both can be turned off, and every other internet feature is opt-in. The [data and privacy table](https://github.com/kmich/ha_ws_core#data-and-privacy) in the README lists them all.

[![Open Weather Station Core in HACS on your Home Assistant.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=kmich&repository=ha_ws_core&category=integration)

---

## ⚡ What do you want to automate?

<div class="grid cards" markdown>

-   :material-weather-pouring:{ .lg .middle } __Smart Rain Defense__

    ---

    Get a minutes-until-rain countdown from Open-Meteo's 15-minute precipitation forecast, cross-checked against your physical rain gauge. Alert your phone and close windows/skylights automatically.

    [:octicons-arrow-right-24: Read Rain Nowcast Guide](guides/nowcast.md)

-   :material-sprinkler-variant:{ .lg .middle } __Precision Garden & Irrigation__

    ---

    Stop overwatering after rain. Uses scientific FAO-56 Penman-Monteith ET₀ to calculate real soil moisture needs.

    [:octicons-arrow-right-24: Read Irrigation Guide](guides/irrigation.md)

-   :material-chart-timeline-variant:{ .lg .middle } __Learned Chances: Rain, Frost, Heat, Gusts, Storms__

    ---

    Pattern Forecast learns from your own station and scores itself. It gives the chance of rain, frost, a hot day, strong gusts and storms over the next hours, 100% local (the storm forecast can optionally use internet lightning data if you have no detector). It needs time to learn and shows `unknown` until it has earned trust.

    [:octicons-arrow-right-24: Read the Pattern Forecast Guide](guides/pattern_forecast.md)

-   :material-weather-windy:{ .lg .middle } __Home & Property Protection__

    ---

    Retract awnings and blinds before high wind gusts hit. Receive frost alerts to protect delicate plants and outdoor pipes.

    [:octicons-arrow-right-24: Browse Use Cases](use_cases.md)

-   :material-shield-home:{ .lg .middle } __Local-First Resilience__

    ---

    Offline Zambretti barometric forecasting predicts weather trends with zero internet connection or API keys.

    [:octicons-arrow-right-24: View Science & Calculations](sensors.md)

</div>

---

## 🚀 The Difference: From Numbers to Action

Most weather integrations simply display values like `21°C` or `12 km/h` on a dashboard card. `ws_core` converts those measurements into actionable triggers:

| Standard Weather Integration | With Weather Station Core |
|---|---|
| Displays current wind speed on a card | **Automatically retracts outdoor awnings** when severe gusts hit |
| Sprinklers turn on blindly on a schedule | **Calculates exact evapotranspiration (ET₀)** to skip unnecessary watering |
| General weather app says *"30% rain chance"* | **TTS voice alert:** *"🌧️ Rain starts in 7 minutes at your home"* |
| Internet drops = no forecasts | **Offline Zambretti forecast** predicts the next 12 hours locally |
| Raw sensors without context | **50+ local derived metrics:** frost risk, UTCI heat stress, fire risk, wet-bulb |

---

## 📡 Works With Your Weather Station

If your weather station is connected to Home Assistant, `ws_core` can use it. Supported setups include:

* **Ecowitt / Ambient Weather:** GW-series, WS90 Wittboy, WH57 lightning, soil moisture, and rain gauges.
* **WeatherFlow Tempest:** Air temperature, pressure, wind gusts, rain rate, and illuminance.
* **Davis Instruments:** Vantage Pro2, Vantage Vue, and WeatherLink entities.
* **Netatmo:** Smart Weather Station with outdoor, rain, and wind modules.
* **DIY / ESPHome / Shelly / MQTT:** Any standard sensor entity reporting temperature, humidity, pressure, wind, and rain.

👉 *See the [Hardware Mapping Guide](hardware_mapping.md) for exact entity mappings for each brand.*

---

## 🛠️ Ready-Made Resources

* **[3-Minute Quickstart](quickstart.md):** Step-by-step installation via HACS with auto-discovery.
* **[Blueprints](blueprints.md):** 1-click importable automations for rain alerts, wind protection, and irrigation skips.
* **[Dashboards](dashboards.md):** Drop-in Lovelace dashboards: native cards only, Mushroom, an animated Enhanced dashboard and a mobile-first Bubble Card dashboard.
* **[Sensor Reference](sensors.md):** Complete catalog of all 170+ available derived sensors and feature groups.
