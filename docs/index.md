# Weather Station Core

**Turn your weather station into proactive smart home automations — not just numbers on a dashboard.**

Weather Station Core (`ws_core`) is a Home Assistant custom integration that transforms raw sensor data from any weather station into local predictive intelligence. Predict rain down to the minute, calculate real garden evapotranspiration (ET₀), protect awnings from wind gusts, and predict storms offline — **100% locally on your machine with zero cloud dependencies.**

[![Open your Home Assistant instance and add this repository to HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=kmich&repository=ha_ws_core&category=integration)

---

## ⚡ What do you want to automate?

<div class="grid cards" markdown>

-   :material-weather-pouring:{ .lg .middle } __Smart Rain Defense__

    ---

    Predict the exact minute rain begins using your physical rain gauge. Alert your phone and close windows/skylights automatically.

    [:octicons-arrow-right-24: Read Rain Nowcast Guide](guides/nowcast.md)

-   :material-sprinkler-variant:{ .lg .middle } __Precision Garden & Irrigation__

    ---

    Stop overwatering after rain. Uses scientific FAO-56 Penman-Monteith ET₀ to calculate real soil moisture needs.

    [:octicons-arrow-right-24: Read Irrigation Guide](guides/irrigation.md)

-   :material-weather-windy:{ .lg .middle } __Home & Property Protection__

    ---

    Retract awnings and blinds before high wind gusts hit. Receive frost alerts to protect delicate plants and outdoor pipes.

    [:octicons-arrow-right-24: Browse Use Cases](use_cases.md)

-   :material-shield-home:{ .lg .middle } __100% Local Resilience__

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
* **[Dashboards](dashboards.md):** Drop-in Lovelace dashboards (Vanilla HA cards & Mushroom card versions).
* **[Sensor Reference](sensors.md):** Complete catalog of all 170+ available derived sensors and feature groups.
