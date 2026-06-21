# Draft: Reddit Launch Post for /r/homeassistant

**Title:** I built an integration that turns your "dumb" local weather station (Ecowitt, Ambient, WeatherFlow) into an insanely powerful, offline forecasting engine.

**Body:**

Hey everyone,

Like many of you, I have a local weather station in my backyard (an Ecowitt). It gave me the temperature and the wind speed, but I realized I wasn't actually *doing* anything with that data. Home Assistant would just show me "It's 22°C outside", but I still had to open my phone's weather app to find out if it was going to rain, or if I needed to water the lawn.

So, I built **Weather Station Core**. 

It takes the 7 basic, raw sensors from your existing weather station and runs them through rigorous meteorological models to generate over 150+ intelligent sensors—completely locally, with zero API keys required. 

Here is what it actually *does* for your smart home:

⛈️ **Never get caught in the rain again.** It blends your local rain gauge data with the Open-Meteo 15-minute grid to give you a highly accurate `sensor.ws_minutes_until_rain`. You can use the included [Rain Start Blueprint](https://github.com/kmich/ha_ws_core/blob/main/blueprints/automation/kmich/ha_ws_core/rain_start.yaml) to have Alexa yell at you to bring the laundry in exactly 5 minutes before the first drop hits.

🥵 **Real Heat Stress & Air Quality.** It calculates the WHO gold-standard UTCI (Universal Thermal Climate Index). Use the included [Heat Stress Blueprint](https://github.com/kmich/ha_ws_core/blob/main/blueprints/automation/kmich/ha_ws_core/heat_stress.yaml) to prevent your smart blinds from opening when the sun is blazing.

🌾 **Stop wasting water.** It calculates daily Evapotranspiration (ET0) so your smart irrigation system knows *exactly* how much water the lawn actually lost today.

🌐 **Works completely offline.** Internet down? Doesn't matter. It includes an offline Zambretti algorithm that predicts the next 12 hours based purely on the barometric pressure trends happening in your backyard. 

**"Wow, that sounds complicated to set up."**
It's not. I just pushed a massive update that adds **Auto-Discovery**. If you have the Ecowitt, WeatherFlow, or Ambient integrations installed, `ws_core` will automatically find your sensors during the config flow. It literally takes 5 seconds to install. 

*(See attached image: `setup_success.png`)*

**"What about my Dashboards?"**
I know we all love a good dashboard. The integration comes with 3 drop-in, premium Lovelace dashboards. 

*(See attached image: `mobile_dashboard.png`)*

I'd love for you to try it out and tell me what you think. It's available right now as a custom repository in HACS, and I'm currently preparing it for submission to the default HACS store.

🔗 **GitHub Repository:** [https://github.com/kmich/ha_ws_core](https://github.com/kmich/ha_ws_core)
📖 **The Deep Science behind it:** [docs/science.md](https://github.com/kmich/ha_ws_core/blob/main/docs/science.md)

Happy automating! Let me know if you run into any issues setting it up with your specific station hardware.
