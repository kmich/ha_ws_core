"""Pirate Weather forecast provider (Dark Sky-compatible API, free tier, API key required)."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp

from .base import ForecastProvider, local_date_str, local_datetime_str, utc_datetime_str

_LOGGER = logging.getLogger(__name__)

_ICON_TO_WMO: dict[str, int] = {
    "clear-day": 0,
    "clear-night": 0,
    "partly-cloudy-day": 2,
    "partly-cloudy-night": 2,
    "cloudy": 3,
    "fog": 45,
    "wind": 1,
    "rain": 63,
    "sleet": 68,
    "snow": 73,
    "hail": 89,
    "thunderstorm": 95,
    "tornado": 99,
}


class PirateWeatherProvider(ForecastProvider):
    """Pirate Weather provider. Free tier available, API key required."""

    PROVIDER_ID = "pirate_weather"
    PROVIDER_NAME = "Pirate Weather"
    REQUIRES_API_KEY = True

    async def async_fetch(
        self,
        session: aiohttp.ClientSession,
        lat: float,
        lon: float,
        api_key: str | None = None,
    ) -> dict[str, Any]:
        if not api_key:
            raise ValueError("Pirate Weather requires an API key")

        url = f"https://api.pirateweather.net/forecast/{api_key}/{lat},{lon}?units=si&exclude=minutely,alerts,flags"
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as resp:
            if resp.status == 403:
                raise ValueError("Pirate Weather: invalid or unauthorized API key")
            if resp.status == 429:
                raise ValueError("Pirate Weather: API rate limit exceeded")
            if resp.status != 200:
                # Not ClientResponseError: its message embeds the request URL,
                # which carries the API key, and would leak it into the logs.
                raise ValueError(f"Pirate Weather: HTTP {resp.status}")
            js = await resp.json(content_type=None)

        # Daily
        daily_out: list[dict[str, Any]] = []
        for day in (js.get("daily", {}).get("data") or [])[:7]:
            dt = day.get("time", 0)
            date_str = local_date_str(dt)
            if day.get("precipAccumulation") is not None:
                daily_precip_mm: float | None = round(float(day["precipAccumulation"]) * 10.0, 1)
            elif day.get("liquidAccumulation") is not None:
                daily_precip_mm = round(float(day["liquidAccumulation"]) * 10.0, 1)
            elif day.get("precipIntensity") is not None:
                daily_precip_mm = round(float(day["precipIntensity"]) * 24.0, 1)
            else:
                daily_precip_mm = None
            daily_out.append(
                {
                    "date": date_str,
                    "tmax_c": day.get("temperatureHigh"),
                    "tmin_c": day.get("temperatureLow"),
                    "precip_mm": daily_precip_mm,
                    "wind_kmh": round(float(day["windSpeed"]) * 3.6, 1) if day.get("windSpeed") is not None else None,
                    "gust_kmh": round(float(day["windGust"]) * 3.6, 1) if day.get("windGust") is not None else None,
                    "weathercode": _ICON_TO_WMO.get(day.get("icon", "")),
                    "precip_prob": (
                        round(float(day["precipProbability"]) * 100)
                        if day.get("precipProbability") is not None
                        else None
                    ),
                }
            )

        # Hourly (up to 25 slots for full mid-hour 24h coverage)
        hourly_out: list[dict[str, Any]] = []
        for hour in (js.get("hourly", {}).get("data") or [])[:25]:
            dt = hour.get("time", 0)
            dt_str = local_datetime_str(dt)
            h_intensity = hour.get("precipIntensity")
            hourly_out.append(
                {
                    "datetime": dt_str,
                    "utc_datetime": utc_datetime_str(dt),
                    "temp_c": hour.get("temperature"),
                    "apparent_temp_c": hour.get("apparentTemperature"),
                    "dewpoint_c": hour.get("dewPoint"),
                    "precip_prob": (
                        round(float(hour["precipProbability"]) * 100)
                        if hour.get("precipProbability") is not None
                        else None
                    ),
                    "precip_mm": round(float(h_intensity), 2) if h_intensity is not None else None,
                    "weathercode": _ICON_TO_WMO.get(hour.get("icon", "")),
                    "wind_kmh": round(float(hour["windSpeed"]) * 3.6, 1) if hour.get("windSpeed") is not None else None,
                    "gust_kmh": round(float(hour["windGust"]) * 3.6, 1) if hour.get("windGust") is not None else None,
                    "humidity": (round(hour.get("humidity", 0) * 100, 1) if hour.get("humidity") is not None else None),
                    "cloud_cover": (
                        round(hour.get("cloudCover", 0) * 100, 1) if hour.get("cloudCover") is not None else None
                    ),
                }
            )

        return {"provider": self.PROVIDER_ID, "daily": daily_out, "hourly": hourly_out}
