# Repository Description Options

The GitHub repository "About" description must be under 350 characters and contain
the target keywords. Three options follow, with the recommended one marked.

All claims are verifiable from `custom_components/ws_core/` at v2.0.7.

---

## Option A (RECOMMENDED)

**Weather Station Core: 150+ sensors from your PWS. Local Zambretti forecast, nowcast
(minutes until rain), fire danger (FFDI/FFWI/FWI), UTCI heat stress, ET0 irrigation,
lightning detection, 8 upload targets, 8 translations. No API keys required for core
features.**

Character count: 284

Why recommended: leads with the output quantity (150+ sensors) which is immediately
concrete, then chains the differentiating keywords in a scannable list. "No API keys
required" addresses the first objection of PWS owners who have been burned by
free-tier expiry.

---

## Option B

**Turn any weather station into a full weather intelligence hub for Home Assistant:
Zambretti forecast, precipitation nowcast, UTCI, McArthur fire danger, ET0,
lightning, 8 upload networks. 150+ sensors. Fully local-capable.**

Character count: 222

Why this works: shorter, more conversational, works well in truncated display. Leads
with the value proposition rather than a number.

---

## Option C

**HA integration for personal weather stations. Derived sensors: nowcast
(minutes-until-rain), UTCI/WBGT heat stress, fire danger (FWI/FFDI/FFWI),
evapotranspiration, lightning detection, Zambretti barometric forecast,
MQTT republishing. 150+ entities, 8 languages.**

Character count: 263

Why this works: uses more technical keywords that PWS enthusiasts search for
(MQTT, WBGT, FWI specifically). Better for developer/enthusiast audience.

---

## How to set it

1. Go to https://github.com/kmich/ha_ws_core
2. Click the gear icon next to "About" in the right sidebar
3. Paste the chosen description into the "Description" field
4. Set the website to the documentation site URL (once Phase 4 is live)
5. Add the topics listed in `hacs_default_submission.md`
6. Save

Set these topics at the same time (gear icon → Topics):
`home-assistant`, `hacs`, `custom-integration`, `weather`, `weather-station`,
`personal-weather-station`, `zambretti`, `nowcasting`, `fire-weather-index`,
`utci`, `evapotranspiration`, `lightning-detection`, `thermal-comfort`
