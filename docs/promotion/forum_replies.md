# Evergreen forum reply drafts

These are ready-to-paste replies for recurring thread types on
community.home-assistant.io. Each answers the question first, then mentions ws_core
as a concrete solution. Post only where genuinely relevant.

---

## Reply A — "Local / offline / self-hosted weather forecast" threads

**Target:** Threads asking how to get a local or API-free weather forecast in HA.
**Character count:** ~110 words

---

The Zambretti barometric method works entirely from local sensor readings — no network
call, no API key, no cloud dependency. It uses mean sea-level pressure, a 3-hour
pressure trend, and wind direction to produce a forecast from the original 1915
Negretti & Zambra lookup table. Accuracy runs 65-75% for 6-12h forecasts in
maritime and Mediterranean climates.

If you have a weather station already integrated into HA, the Weather Station Core
integration (`https://github.com/kmich/ha_ws_core`) does this automatically as part
of a broader set of derived sensors. It also supports Open-Meteo as a free NWP backup,
but the Zambretti forecast works without any internet access.

---

## Reply B — Dew point / humidity template threads

**Target:** Threads asking how to calculate dew point, absolute humidity, or VPD
from temperature and relative humidity sensors.
**Character count:** ~130 words

---

For a one-off dew point sensor, a template works fine. The Magnus formula
(Alduchov & Eskridge 1996) is:

```
{{ (243.04 * (log(states('sensor.humidity')|float / 100)
   + 17.625 * states('sensor.temperature')|float
   / (243.04 + states('sensor.temperature')|float))
   / (17.625 - log(states('sensor.humidity')|float / 100)
   - 17.625 * states('sensor.temperature')|float
   / (243.04 + states('sensor.temperature')|float))) | round(1) }}
```

If you also want absolute humidity, vapour pressure deficit, frost point, or wet-bulb
temperature without maintaining separate templates, the Weather Station Core integration
(`https://github.com/kmich/ha_ws_core`) derives all of those automatically from the
same temperature and humidity inputs, alongside 140+ other sensors.

---

## Reply C — Rain prediction / nowcast question threads

**Target:** Threads asking how to get a short-term rain prediction, automate on
"rain in the next hour", or get minute-level rain timing.
**Character count:** ~135 words

---

Open-Meteo provides a 15-minute precipitation forecast (the `minutely_15` endpoint)
that is free and requires no API key. You can pull it with a REST sensor and parse
the next few buckets to get a rough "is rain coming" flag.

For a more complete implementation: Weather Station Core (`https://github.com/kmich/ha_ws_core`)
wraps this into ready-to-use entities — `sensor.ws_minutes_until_rain` gives a
countdown in minutes, `binary_sensor.ws_rain_expected_1h` gives an on/off trigger
for automations, and `sensor.ws_nowcast_intensity` gives a none / light / moderate /
heavy classification. It refreshes every 15 minutes and is independent of whatever
forecast provider you use for the 7-day forecast.

The integration requires a weather station already integrated into HA (any brand),
but the nowcast itself only needs your GPS coordinates.

---

## Posting guidance

- Reply only on threads where the question is open and unsolved.
- Do not post if someone else has already mentioned ws_core in the same thread.
- If the thread is more than 6 months old, check whether a better answer already
  exists before replying.
- Always answer the question directly first (as written above). The ws_core mention
  is a "here is a more complete option" addendum, not the lead.
