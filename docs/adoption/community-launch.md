# Community Launch Assets

## 1. Reddit Post (`/r/homeassistant`)
**Title:** I was tired of my weather station being useless for automations, so I built an intelligence layer for it.
**Body:**
Hey everyone,

If you have an Ecowitt, Tempest, or any local weather station, you probably know the pain: you get 30 raw sensors in HA, but it's really hard to actually *do* anything with them.

I built **ws_core** to sit on top of your existing hardware integration and turn raw data into actual smart home triggers.

Instead of just "Current Rain: 0mm", it gives you:
* **Minutes-until-rain nowcasting:** Blends your live rain gauge with Open-Meteo to tell you exactly when the rain will hit. (Includes blueprints for TTS alerts!)
* **True Local Forecasting:** Uses the Zambretti barometric algorithm to predict the next 12 hours completely offline, based on your pressure trends.
* **Smart Irrigation ET0:** Calculates exact Penman-Monteith evapotranspiration so you know exactly how much water your lawn lost today.
* **Heat Stress & Fire Danger:** Proper UTCI, WBGT, and Canadian FWI calculations for safety alerts.

It takes 60 seconds to map your sensors in the UI. No YAML required.

**Links:**
* GitHub: [Link]
* Importable Dashboards: [Link]
* Blueprints: [Link]

Let me know what you think! I'm actively looking for feedback on the setup flow.

## 2. Home Assistant Community Forum Post
**Category:** Share your Projects!
**Title:** ws_core: Turn your raw weather station data into actionable intelligence (Nowcasting, Zambretti, ET0)
**Body:**
[Similar to Reddit post, but embed 3 high-quality screenshots: 1. The Dashboard, 2. The Config Flow showing sensor mapping, 3. The Automation blueprint for rain.]

## 3. GitHub Release Announcement (Next Major Version)
**Title:** ws_core v3.0: The Adoption Update
**Highlights:**
* **Radically Simplified Setup:** We've categorized over 100 advanced scientific sensors as disabled-by-default to keep your entity list clean. You now only see what you need.
* **New Documentation Hub:** Focused entirely on automations, outcomes, and getting your dashboards running in under 5 minutes.
* **Dashboard Blueprints:** (If applicable) Easily import our gorgeous weather cards without touching YAML.

## 4. Launch Checklist
- [ ] Test suite is green.
- [ ] README is rewritten and pushed to `main`.
- [ ] `hacs.json` is updated.
- [ ] 3 "Hero" screenshots are captured and embedded in the README.
- [ ] The "Migrating from Thermal Comfort" documentation is up to date.
- [ ] Release tagged on GitHub.
- [ ] Post on Reddit (Thursday morning US time is usually best).
- [ ] Post on HA Forums.
