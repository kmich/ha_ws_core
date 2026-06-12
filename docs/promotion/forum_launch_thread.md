# Forum launch thread — community.home-assistant.io / Share your Projects

**Target section:** Share your Projects
**Suggested title:** Weather Station Core — 150+ sensors from your PWS, including minutes-until-rain nowcast

---

## Post body

I built a Home Assistant custom integration for personal weather stations that I've
been using daily for a while, and I think it's ready for wider feedback.

**The short version:** Weather Station Core takes the 7 raw sensors your weather
station already provides (temperature, humidity, pressure, wind speed, wind gust,
wind direction, rain total) and turns them into 150+ derived entities. The standout
feature that originally motivated me to build this: knowing whether it will rain in
the next hour and, specifically, how many minutes away that rain is.

[SCREENSHOT: the "Now" view of the dashboard showing ws_minutes_until_rain, current
conditions, and the rain nowcast tile]

### The nowcast

`sensor.ws_minutes_until_rain` pulls Open-Meteo's 15-minute precipitation buckets
(free, no API key) and translates them into a concrete countdown. It also gives you:
- `binary_sensor.ws_rain_expected_1h` — on/off for automations
- `sensor.ws_rain_next_60min` — total expected precipitation in mm
- `sensor.ws_nowcast_intensity` — none / light / moderate / heavy

I have an automation that closes my garden umbrella 20 minutes before rain starts.
It has worked reliably for a couple of months.

### Other things it does

Beyond the nowcast, a few capabilities that are not in other HA weather integrations:

**UTCI heat stress.** The Universal Thermal Climate Index (Bröde 2012 polynomial) is
the metric used by WHO and national weather services for outdoor heat warnings. It
accounts for temperature, humidity, wind, and solar radiation together. Useful if you
run outdoor workers or events.

**Fire danger.** Three systems: Canadian FWI (Van Wagner 1987) with persistent daily
moisture memory, McArthur FFDI for Australian conditions, and Fosberg FFWI for US/global.
All fire sensors with a configurable 1-10 display scale.

**Zambretti barometric forecast.** A local, no-network forecast based on the original
1915 Negretti & Zambra lookup table. 65-75% accuracy for 6-12h in maritime climates.
Combined with the NWP provider, you get `sensor.ws_forecast_agreement` which tells you
when the barometric method and the model disagree — a useful signal for low-confidence
forecasts.

**ET₀ for irrigation.** `sensor.ws_et0_pm_daily` implements FAO-56 Penman-Monteith
(±5-10% accuracy) when you have a solar radiation sensor. Hargreaves-Samani fallback
otherwise. Works with the Smart Irrigation integration.

### Bundled dashboards

Three dashboards are included:

[SCREENSHOT: the full 6-view dashboard (Now / Charts / Advanced / Records /
Diagnostics / Indoor) on a tablet]

- A vanilla dashboard using only native HA cards — nothing from HACS required
- A full dashboard (6 views) using mushroom + mini-graph-card
- A mobile-optimised single-column layout for phones

All three are copy-paste YAML. No setup beyond pasting into the raw config editor.

### Eight upload targets

If you want to share your data: Weather Underground, Weathercloud, PWSWeather,
WOW (UK Met Office), AWEKAS, CWOP/APRS, OpenWeatherMap Stations, and Windy.
Each is independent and has its own status sensor.

### Installation

HACS custom repository: `https://github.com/kmich/ha_ws_core`

Or install manually by copying `custom_components/ws_core` to your `custom_components/`
directory and restarting.

### Translations

Eight languages at full parity: English, French, German, Dutch, Spanish, Italian,
Portuguese, Polish. All entity names, config flow strings, and state labels are covered.
If you maintain a translation in another language, I'd welcome a PR.

### What I'm looking for

- **Feedback on the nowcast.** Does the minutes-until-rain timing match reality for
  your location? Open-Meteo's 15-minute grid is global but coarser in some regions.
- **Upload target bugs.** The Weather Underground credential flow was broken until v2.0.7.
  If other upload targets misbehave, please open an issue with the status sensor value
  and your HA logs.
- **Translation contributions.** Chinese, Japanese, Korean, Czech, Swedish, and
  Norwegian would cover a large fraction of the HA user base.
- **Station compatibility.** I primarily test with Ecowitt/GW series stations. If
  your station brand needs special handling, open an issue.

Repository: https://github.com/kmich/ha_ws_core  
CHANGELOG: https://github.com/kmich/ha_ws_core/blob/main/CHANGELOG.md

---

## Posting notes for maintainer

- Post to the "Share your Projects" section, not "Configuration and Templating"
- Include at least two screenshots: the "Now" dashboard view and one showing
  sensor entities in Developer Tools or the device page
- Pin the thread URL so you can link from HACS submission and Reddit
- Reply to every comment in the first 48 hours — the algorithm surfaces threads
  with rapid reply activity
