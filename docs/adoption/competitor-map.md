# Competitor Map

To market `ws_core` effectively, we must understand the landscape of Home Assistant weather integrations. `ws_core` must position itself not as a competitor to these tools, but as an *enhancement* layer.

## 1. Hardware Integrations (The Data Sources)
* **Ecowitt, Ambient Weather, WeatherFlow Tempest**
* **What they do:** Connect to the hub, pull raw data (Temp: 22C, Rain: 0mm).
* **What ws_core does better:** `ws_core` doesn't do this at all; it relies on them.
* **Positioning:** "ws_core takes your Ecowitt data and makes it smart."

## 2. Cloud Forecast Integrations (The Grids)
* **Open-Meteo, Met.no, AccuWeather, Pirate Weather**
* **What they do:** Provide regional grid forecasts (e.g., "30% chance of rain today").
* **What ws_core does better:** `ws_core` uses a 100-year-old local algorithm (Zambretti) that operates entirely offline based on the user's *actual* pressure trends, and corrects the cloud nowcast with the user's *actual* rain gauge.
* **Positioning:** "Stop relying on a weather station 30 miles away. ws_core corrects Open-Meteo forecasts using your backyard data."

## 3. Smart Irrigation (The Specialists)
* **HA Smart Irrigation Integration**
* **What they do:** Calculate irrigation time based on ET0 (Evapotranspiration).
* **What ws_core does better:** Smart Irrigation often guesses ET0 using cloud data or simple approximations. `ws_core` calculates the gold-standard Penman-Monteith ET0 using the user's *actual* solar radiation sensors.
* **Positioning:** "ws_core provides the most accurate ET0 data possible to feed into your Smart Irrigation setup."

## 4. Thermal Comfort / Mold Risk Integrations
* **Thermal Comfort (custom component), Mold Indicator**
* **What they do:** Calculate dew point, absolute humidity, and mold risk.
* **What ws_core does better:** `ws_core` handles this and much more, including outdoor safety (Canadian FWI, UTCI). The `ws_core` repo even includes a migration guide from Thermal Comfort.
* **Positioning:** "The ultimate upgrade from Thermal Comfort, handling both indoor comfort and outdoor safety."

## 5. Dashboards and UI
* **Weather Card, Clock Weather Card, Mushroom Weather**
* **What they do:** Display weather entities beautifully.
* **What ws_core does better:** `ws_core` doesn't replace them; it powers them.
* **Positioning:** "Provide our import-ready Mushroom dashboard that automatically hooks into ws_core's advanced entities."
