import aiohttp
from .base import ForecastProvider

class MeteoFrance(ForecastProvider):
    NAME = "Météo France"
    ID = "meteo_france"

    BASE_URL = "https://api.meteo-concept.com/api"

    async def async_fetch(self, session, lat, lon, api_key=None):
        if api_key is None:
            raise ValueError("Météo France requires an API key")

        # 1) Daily forecast (7 days)
        daily_url = (
            f"{self.BASE_URL}/forecast/daily?token={api_key}&latlng={lat},{lon}"
        )

        # 2) Hourly forecast (24h)
        hourly_url = (
            f"{self.BASE_URL}/forecast/hourly?token={api_key}&latlng={lat},{lon}"
        )

        async with session.get(daily_url) as r:
            daily_data = await r.json()

        async with session.get(hourly_url) as r:
            hourly_data = await r.json()

        # Normalisation WS Core (7-day daily + 24h hourly)
        # Format documenté dans ForecastProvider 

        daily = []
        for d in daily_data.get("forecast", [])[:7]:
            daily.append({
                "date": d.get("datetime"),
                "temp_max": d.get("tmax"),
                "temp_min": d.get("tmin"),
                "precip_prob": d.get("probarain"),
                "wind_speed": d.get("wind10m"),
                "wind_gust": d.get("gust10m"),
                "condition": d.get("weather"),
            })

        hourly = []
        for h in hourly_data.get("forecast", [])[:24]:
            hourly.append({
                "time": h.get("datetime"),
                "temperature": h.get("temp2m"),
                "humidity": h.get("rh2m"),
                "dew_point": None,  # MF ne le fournit pas
                "wind_speed": h.get("wind10m"),
                "wind_gust": h.get("gust10m"),
                "precip_prob": h.get("probarain"),
            })

        return {
            "daily": daily,
            "hourly": hourly,
        }
