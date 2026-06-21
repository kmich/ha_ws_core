# Draft: Home Assistant Community Forum Post

**Category:** Share your Projects!
**Title:** Weather Station Core: Turn any local station into a completely offline, 150+ sensor intelligence hub

**Body:**

Hi everyone,

I've been working on a custom integration that I think many of you with local weather stations (Ecowitt, WeatherFlow, Davis, Ambient, Shelly, etc.) will find incredibly useful. 

Many of us pipe our raw weather station data into HA, but that raw data only tells you what is happening *right now*. To actually automate your home, you need to know what is going to happen next. 

That is what **[Weather Station Core (ws_core)](https://github.com/kmich/ha_ws_core)** does.

It takes your 7 required base sensors (Temp, Hum, Pressure, Wind, Gust, Dir, Rain) and derives over 150+ advanced meteorological entities entirely locally. No API keys required.

### 🌟 Key Features

* **Ground-Truth Nowcasting:** It blends your physical rain gauge data with the Open-Meteo 15-minute grid. If your local gauge detects rain earlier than the forecast expected, the integration instantly shifts the forecast to give you a highly accurate `sensor.ws_minutes_until_rain`. 
* **Offline Zambretti Forecaster:** If the internet goes down, your smart home still knows the weather. It uses the physical barometric pressure trends in your backyard to output a 12-hour forecast and a 36-condition weather classifier.
* **Smart Irrigation & Comfort:** Includes Evapotranspiration (ET0) for exact watering needs, and the gold-standard UTCI index for heat-stress automations.
* **Safety First:** Includes full Fire Danger systems (Canadian FWI, Australian FFDI) and a fog probability algorithm.

### 🚀 5-Second Setup

I just pushed a huge update to make this as plug-and-play as possible. If you use the standard Ecowitt, WeatherFlow, or Ambient integrations, `ws_core` will **auto-discover** all your sensors during the Config Flow. 

*(See attached image: `setup_success.png`)*

It also includes 5 native Blueprints (Rain Warning, Freeze Alert, High Wind, Heat Stress, Poor AQI) that you can import with one click to get your automations running instantly. 

### 📊 Dashboards Included

I know half the fun is looking at the data, so the repository includes drop-in YAML for some incredibly detailed mobile and desktop dashboards.

*(See attached image: `mobile_dashboard.png`)*

### How to Install

It's currently available via HACS as a custom repository (I am finalizing the submission for the default HACS store this week).

1. HACS -> Integrations -> 3 Dots -> Custom Repositories
2. Add `https://github.com/kmich/ha_ws_core` (Category: Integration)
3. Install, restart, and go to Settings -> Devices & Services to set it up!

Let me know what you think, or if you have any feature requests! 

*(If you are a meteorology nerd and want to see the math/formulas behind the derived sensors, check out the [Science Docs](https://github.com/kmich/ha_ws_core/blob/main/docs/science.md))*
