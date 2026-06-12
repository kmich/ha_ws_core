# Forecast Providers

Weather Station Core supports seven interchangeable forecast backends. Change provider
at any time via **Settings → Devices & Services → Weather Station Core → Configure →
Forecast** without reinstalling.

`sensor.ws_forecast_provider` shows the currently active provider.

---

## Provider comparison

| Provider | Free | API key | Coverage | Notes |
|---|---|---|---|---|
| **Open-Meteo** *(default)* | Yes | No | Global | No registration required |
| **Met.no** | Yes | No | Global (excellent Europe) | Norwegian Meteorological Institute |
| **NWS / NOAA** | Yes | No | US only | Returns error outside continental US |
| **OpenWeatherMap** | Free tier | Yes | Global | One Call 3.0 API; free tier requires registration at openweathermap.org |
| **Pirate Weather** | Free tier | Yes | Global | Dark Sky-compatible API; free tier at pirateweather.net |
| **Météo France** | Free tier | Yes | Global | Météo Concept API; free tier at api.meteo-concept.com |
| **HA weather entity** | Yes | No | Depends on entity | Uses any existing `weather.*` entity in HA |

---

## Open-Meteo (default)

Global hourly and daily forecast. No account, no API key. Updated every 15 minutes.

Supports the nowcast feature (`sensor.ws_minutes_until_rain`) — this is a separate
Open-Meteo endpoint that works regardless of which provider you choose for the 7-day
forecast.

---

## Met.no

Norwegian Meteorological Institute's public API. Particularly accurate for Northern
Europe, the Nordic region, and polar areas. No API key or registration required.
Requires a valid contact email in the User-Agent header (automatically set by ws_core).

---

## NWS / NOAA

US National Weather Service forecast API. No API key required. Returns an error if
your coordinates are outside the continental United States.

---

## OpenWeatherMap

Uses the One Call 3.0 API endpoint. A free tier is available but requires registration
at openweathermap.org to obtain an API key. Enter the key in Configure → Forecast.

---

## Pirate Weather

A Dark Sky-compatible API hosted at pirateweather.net. Free tier available; API key
required. Suitable as a fallback for users who had Dark Sky access.

---

## Météo France

Uses the Météo Concept API (api.meteo-concept.com). Free tier available; API key
required. Contributed by @Benjamin45590.

---

## Home Assistant weather entity

Uses any existing `weather.*` entity already integrated into Home Assistant. No
external network call is made — forecast data comes from the existing HA integration.

This is useful if you already have Met.no, OpenWeatherMap, or another HA weather
integration set up and do not want ws_core to make its own API calls.

To configure: in Configure → Forecast, select "Home Assistant weather entity" as
the provider, then pick the entity from the dropdown.

Uses the `weather.get_forecasts` service (HA 2024.2+) with fallback to the `forecast`
attribute on older installations.

---

## Adding a new provider

See [Contributing](contributing.md) for the provider contribution path.

New providers require: a Python file in `custom_components/ws_core/providers/`, a
one-line registry entry in `providers/__init__.py`, and translation strings for the
provider name.
