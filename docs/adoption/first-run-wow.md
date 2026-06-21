# The 5-Minute "Wow" Journey

Currently, a user installs `ws_core` and is met with a massive list of manual data entry, followed by a silent dump of 50+ entities. Here is how we redesign the first 5 minutes to guarantee adoption and delight.

## Minute 1: The Promise
The user finds `ws_core` on HACS or Reddit. They read the new tagline: *"Turn your Ecowitt/Tempest into a smart-home oracle."* They see an animated GIF of a dashboard showing "Rain arriving in 12 minutes." They click Install.

## Minute 2: The frictionless Config Flow
* **Current state:** "Map your 7 mandatory sensors."
* **New state:** The setup wizard opens.
  * **Step 1:** "Select your weather station device." (A dropdown showing their Ecowitt Gateway).
  * **Step 2:** `ws_core` automatically scans the device registry and pre-fills the temperature, humidity, pressure, and wind entities.
  * **Step 3:** The user clicks "Submit" and sees a success message: "Weather intelligence activated."

## Minute 3: The Curated Entity List
* **Current state:** 50+ sensors activated. User is overwhelmed.
* **New state:** Only the 15 "Hero" entities are enabled. The user opens their HA device page and sees:
  * `sensor.ws_minutes_until_rain`
  * `sensor.ws_zambretti_forecast`
  * `sensor.ws_current_condition`
  * `sensor.ws_et0_daily`
  The advanced stuff (Vapour Pressure Deficit, Frost Point, Air Density) is neatly tucked away under the "Disabled by default" section, waiting for power users.

## Minute 4: The Visual Payoff
The success screen of the integration (or the README) provides a massive, unmistakable link: **"Get the Dashboard."**
The user clicks a My Home Assistant link or imports a Blueprint. Instantly, they have a beautiful Mushroom-based or custom Lovelace card showing their new intelligent data, side-by-side with their raw data. They see the "Nowcast" graph visually blending their local data with the cloud forecast. **<- This is the WOW moment.**

## Minute 5: The Actionable Outcome
The user sees a section in the README: **"Top Automations."**
They click the "Rain Warning" Blueprint. They select their smart speaker and the `sensor.ws_minutes_until_rain`.
They have just built an enterprise-grade, hyper-local weather warning system in 5 minutes. They immediately go to Reddit to tell everyone else to install `ws_core`.
