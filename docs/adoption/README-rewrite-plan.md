# README Rewrite Plan

The current README is structured for an academic peer review, not a consumer product launch. It buries the lead and intimidates new users. Here is the proposed new structure.

## 1. Above the Fold (The Hook)
* **Title:** Weather Station Core (`ws_core`)
* **Tagline:** The Intelligence Layer for your Home Assistant Weather Station.
* **Badges:** HACS, Tests (once fixed!), Version.
* **Hero Image:** A stunning, high-res GIF or image of the enhanced dashboard showing the "Minutes until rain" nowcast.

## 2. What does it do? (The "Why")
Replace the dense feature list with 3-4 bullet points focused on *outcomes*:
* **Stop the Sprinklers Precisely:** Calculates exact ET0 so your irrigation system knows exactly how much water the lawn needs.
* **Never Get Caught in the Rain:** Uses your live rain gauge to correct cloud forecasts, giving you a countdown to the minute the rain starts.
* **Offline Zambretti Forecast:** Predicts the next 12 hours based purely on your local pressure trends, even if the internet goes down.
* **Automate Everything:** Includes 5 ready-to-use blueprints for TTS alerts, freeze warnings, and high-wind awning retraction.

## 3. Does it work with my station?
A clear, reassuring section:
*"If your station is in Home Assistant, it works with ws_core. It is tested heavily with Ecowitt, WeatherFlow Tempest, Ambient Weather, and Davis Instruments."*

## 4. The 60-Second Quickstart
Keep the current quickstart, but emphasize how easy it is.
* Install via HACS.
* Add Integration.
* Map your sensors (Add a screenshot of the mapping UI here!).

## 5. The "Wow" Dashboards
Move the dashboards up! People buy with their eyes.
Provide a direct link to the Dashboard YAML or Blueprint, with side-by-side screenshots of the Mobile and Desktop views.

## 6. Top Automations
Move the blueprints up! Explain *why* they want this integration.
* Link to Rain Warning Blueprint.
* Link to Freeze Warning Blueprint.
* Link to Wind Awning Blueprint.

## 7. Advanced Features (The "Nerd" Section)
*Move the heavy math here.*
* Explain Canadian FWI, UTCI, Stull 2011, etc.
* Reassure normal users that they don't need to understand this to use the integration.

## 8. FAQ & Troubleshooting
* "Why are my entities unavailable?"
* "How do I migrate from Thermal Comfort?"

## 9. Scientific Documentation
Move the deep formulas (Magnus Formula, Penman-Monteith) to a completely separate markdown file (e.g., `docs/science.md`) and link to it. Do not force users to scroll past mathematical equations in the main README.
