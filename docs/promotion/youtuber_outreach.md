# YouTuber outreach email templates

Two variants follow. Choose based on the creator's content focus.
Send the fact sheet appendix regardless of which variant you use.

Keep the email under 200 words. Creators receive many pitches; shorter is better.

---

## Variant A — Nowcast / general HA audience

**Subject:** HA integration that tells you it will rain in 23 minutes — demo angle

---

Hi [Name],

I built a Home Assistant integration for personal weather stations called Weather
Station Core. One feature stands out for video content: `sensor.ws_minutes_until_rain`
— a live countdown to rain arrival using Open-Meteo's free 15-minute data. I have it
automate closing my garden umbrella before rain arrives.

Beyond the nowcast: 150+ derived sensors from 7 raw station inputs, UTCI heat stress,
Canadian/Australian/US fire danger, Zambretti barometric forecast (fully local, no
internet), and ET₀ for irrigation — all in one integration with no API keys for the
core features.

It's been running in production for several months across a growing user base.
The repository is at https://github.com/kmich/ha_ws_core with a full CHANGELOG.

I have attached a one-page fact sheet. Happy to do a live demo of any feature you'd
like to cover. No sponsor expectations — share it only if it's useful for your audience.

[Your name]

---

## Variant B — Fire danger / seasonal angle (summer/wildfire season)

**Subject:** HA integration tracking fire danger from your weather station — seasonal
demo angle

---

Hi [Name],

I built Weather Station Core, a Home Assistant integration that derives fire danger
indices directly from personal weather station data — no API, no cloud dependency.
It supports three regional systems: Canadian FWI (Van Wagner 1987), McArthur FFDI
for Australia, and Fosberg FFWI for US/global conditions. Fire risk appears on a
1-10 display scale with a `sensor.ws_fire_risk_score` entity usable in automations.

The integration does much more (150+ sensors total: nowcast, UTCI, ET₀, lightning
detection, Zambretti forecast), but fire danger is the feature most relevant to
wildfire season content. I've attached a one-page fact sheet with specifics.

Repository: https://github.com/kmich/ha_ws_core

Happy to demo any part of this live. No sponsor expectations.

[Your name]

---

## Appendix: Fact sheet for creators

### Weather Station Core — one-page reference

**What it is:** A Home Assistant custom integration that transforms raw personal
weather station data into 150+ derived sensors. Supports Ecowitt, Davis, WeatherFlow,
Shelly, and any other HA-integrated weather station.

**Installation:** HACS custom repository `https://github.com/kmich/ha_ws_core`.
Takes under 5 minutes including a guided 8-step setup wizard.

**Requirements:** 7 sensor entities from any HA-integrated weather station:
temperature, humidity, pressure, wind speed, wind gust, wind direction, cumulative rain.

**Key features for video content:**

| Feature | Entity / demo angle |
|---|---|
| Precipitation nowcast | `sensor.ws_minutes_until_rain` — live countdown; automate umbrella, laundry, window closing |
| UTCI heat stress | `sensor.ws_utci` — WHO-standard index; outdoor worker safety, event planning |
| Fire danger | `sensor.ws_fire_risk_score`, `sensor.ws_ffdi`, `sensor.ws_ffwi` — 1-10 scale, automatable |
| Local forecast | `sensor.ws_zambretti_forecast` — no internet, 65-75% accuracy |
| ET₀ irrigation | `sensor.ws_et0_pm_daily` — integrates with Smart Irrigation |
| Lightning detection | `sensor.ws_lightning_clearance` — safe-to-go-outside countdown |
| Data quality | `sensor.ws_sensor_quality_flags`, drift detection, spike detection |

**Dashboard:** Three bundled dashboards — vanilla (no HACS frontend deps), full 6-view,
and mobile-optimised. All copy-paste YAML.

**API keys required:** None for core features. Open-Meteo (free) for NWP forecasts.
Optional paid providers: OpenWeatherMap, Pirate Weather, Météo France.

**Translations:** English, French, German, Dutch, Spanish, Italian, Portuguese, Polish.

**Version:** 2.0.7 (June 2026). Active development; 60+ issues resolved in 5 weeks.

**Scientific basis:** Every formula is documented with its reference paper:
Stull (2011) wet-bulb, Bröde (2012) UTCI, Van Wagner (1987) FWI, Alduchov (1996)
Magnus, Allen (1998) Penman-Monteith, Meeus (1998) moon phase.

**Contact:** GitHub issues at https://github.com/kmich/ha_ws_core/issues
