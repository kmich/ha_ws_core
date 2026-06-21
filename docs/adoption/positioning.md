# Positioning: What is ws_core?

To drive adoption, we must ruthlessly clarify what `ws_core` is and what it is not. The biggest risk to adoption is users thinking "I already have an Ecowitt integration, why do I need this?"

## The Core Positioning Statement
> **ws_core is the intelligence layer for your weather station.**
> It does not replace your hardware integration. It sits on top of it, turning raw data into smart home actions: minutes-until-rain alerts, irrigation budgets, fire safety warnings, and hyper-local forecasts.

## What it is NOT
* **It is NOT a hardware integration.** It does not talk to your Ecowitt gateway or WeatherFlow hub. You still need the native HA integrations for that.
* **It is NOT just a dashboard.** While it provides dashboards, its primary value is creating actionable entities for automations.
* **It is NOT a basic cloud forecast.** It is a localized engine that uses *your* yard's data to correct cloud forecasts.

## Who is it for?
1. **The Automation Optimizer:** Users who want to pause sprinklers based on exact ET0 calculations, or retract awnings based on predictive wind gusts.
2. **The Micro-Climate Victim:** Users who live in valleys, coasts, or mountains where generic Open-Meteo or Apple Weather forecasts are consistently wrong.
3. **The Data Nerd:** Users who bought an expensive weather station and are disappointed that Home Assistant just shows them a static number.

## Supported Station "Hero" Examples
When marketing, do not say "Supports any station." Say "Transforms your existing hardware:"
* Ecowitt (GW1100, GW2000, Wittboy)
* WeatherFlow Tempest
* Ambient Weather
* Davis Instruments
* Custom ESPHome / Shelly sensor arrays

## Top 3 "Killer" Use Cases (The Hooks)
1. **The 15-Minute Rain Nowcast:** "Get a TTS warning on your smart speaker 15 minutes before the rain starts, so you can bring the cushions in. It blends your live local gauge with Open-Meteo grids for ultimate accuracy."
2. **The True Irrigation Budget:** "Stop guessing. ws_core calculates exact Penman-Monteith ET0 based on your station's solar radiation and wind, telling your Smart Irrigation exactly how much water the lawn lost today."
3. **The Local Zambretti Forecast:** "No internet? No problem. It uses a 100-year-old barometric algorithm to predict the next 12 hours of weather based entirely on your local pressure trends and wind direction."
