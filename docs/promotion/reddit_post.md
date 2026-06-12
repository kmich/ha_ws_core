# Reddit post — r/homeassistant

**Subreddit:** r/homeassistant
**Post type:** Link or text (text preferred; paste screenshot URL from Imgur or similar)
**Suggested title:** I built a HA integration that tells you it will rain in 23 minutes

---

## Post body

[SCREENSHOT: dashboard "Now" view showing sensor.ws_minutes_until_rain at a
specific countdown value, with current weather conditions alongside]

I've been running this for a few months and wanted to share it with the community.

My weather station sends temperature, humidity, pressure, wind, and rain data to HA.
What I wanted was: "will it rain in the next hour, and exactly how many minutes away
is that rain?" I built Weather Station Core to answer that question, and it ended up
growing into a much larger integration.

**The nowcast:** `sensor.ws_minutes_until_rain` uses Open-Meteo's free 15-minute
precipitation data to give a countdown. `binary_sensor.ws_rain_expected_1h` gives
you an on/off trigger for automations. I use it to close the garden umbrella
automatically 20 minutes before rain arrives.

**Other things it does that I haven't seen elsewhere:**
- UTCI (Universal Thermal Climate Index, Bröde 2012) — the WHO standard for heat stress
- Canadian FWI + McArthur FFDI + Fosberg FFWI — fire danger for your region
- Zambretti barometric forecast — fully local, no internet required, 65-75% accuracy
- Penman-Monteith ET₀ for irrigation (Smart Irrigation compatible)
- 8 upload targets (Weather Underground, Weathercloud, WOW, CWOP, and more)

150+ sensors total. 8 translations. All free, no API keys required for core features.

HACS custom repo: `https://github.com/kmich/ha_ws_core`

Happy to answer questions about setup, station compatibility, or specific sensors.

---

## Pre-written FAQ comment (post as a top-level comment on your own post)

**Q: What weather stations does it support?**

A: Any station that is already integrated into Home Assistant. Ecowitt/GW series,
Davis, WeatherFlow, Shelly, and anything else with a HA integration that exposes
temperature, humidity, pressure, wind, and rain sensors. You map 7 specific sensors
during setup — the integration does not care what brand produced them.

**Q: Does it require API keys or cloud accounts?**

A: No API key is required for the Zambretti forecast, ET₀, moon phase, nowcast, UTCI,
or fire danger. Open-Meteo (free, no registration) is the default for NWP forecasts
and the nowcast. Weather Underground upload requires your WU station ID and key.

**Q: How does it relate to the Thermal Comfort integration?**

A: ws_core includes all of Thermal Comfort's heat-stress sensors (heat index, humidex,
wind chill, dew point, absolute humidity) plus UTCI, WBGT, and about 130 additional
sensors. A migration guide is at `docs/migrating_from_thermal_comfort.md` in the repo.

**Q: Does it slow down HA?**

A: The coordinator runs every 90 seconds (configurable). All derived calculations are
pure Python with no I/O. The nowcast and NWP fetches happen on a separate 15-minute
cycle. On a Raspberry Pi 4, coordinator execution takes under 50ms.

**Q: Can I use it without a physical weather station?**

A: The 7 required sensors must come from somewhere. If you have a virtual station
(template sensors from nearby airport METAR data, for example), it will work. But
the core value of the integration is in deriving useful output from station data
you already have.

---

## Posting notes for maintainer

- Post after the forum thread is live and has at least a few replies (so you can
  link to the thread in the comments for discussion)
- The Reddit post itself should focus on one concrete feature (the nowcast) and
  be under 300 words — the FAQ comment can be longer
- Cross-post timing suggestion: 1 week after the forum launch thread
- Consider posting on a Tuesday or Wednesday morning UTC for maximum r/homeassistant
  visibility
