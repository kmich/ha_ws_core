from __future__ import annotations

import datetime
import logging
from typing import Any

import aiohttp

from .base import ForecastProvider

_LOGGER = logging.getLogger(__name__)

# --- Mapping Météo France → WMO ---
MF_TO_WMO = {
    0: 0,    # Soleil
    1: 1,    # Peu nuageux
    2: 2,    # Voilé
    3: 3,    # Nuageux
    4: 45,   # Brouillard
    5: 48,   # Brouillard givrant
    6: 51,   # Bruine faible
    7: 53,   # Bruine modérée
    8: 55,   # Bruine forte
    9: 61,   # Pluie faible
    10: 63,  # Pluie modérée
    11: 65,  # Pluie forte
    12: 80,  # Averses faibles
    13: 81,  # Averses modérées
    14: 82,  # Averses fortes
    15: 71,  # Neige faible
    16: 73,  # Neige modérée
    17: 75,  # Neige forte
    18: 85,  # Averses neige faibles
    19: 86,  # Averses neige fortes
    20: 95,  # Orage faible
    21: 96,  # Orage grêle faible
    22: 99,  # Orage grêle fort
}


class MeteoFrance(ForecastProvider):
    PROVIDER_ID = "meteo_france"
    PROVIDER_NAME = "Météo France"
    REQUIRES_API_KEY = True

    BASE_URL = "https://api.meteo-concept.com/api"

    async def _get(self, session: aiohttp.ClientSession, endpoint: str, api_key: str) -> dict[str, Any]:
        url = f"{self.BASE_URL}/{endpoint}"
        headers = {"Authorization": f"Bearer {api_key}"}

        async with session.get(url, headers=headers) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def async_fetch(
        self,
        session: aiohttp.ClientSession,
        latitude: float,
        longitude: float,
        api_key: str,
    ) -> dict[str, Any]:

        # Daily forecast
        daily_raw = await self._get(
            session,
            f"forecast/daily?latlng={latitude},{longitude}",
            api_key,
        )

        # Hourly forecast
        hourly_raw = await self._get(
            session,
            f"forecast/hourly?latlng={latitude},{longitude}",
            api_key,
        )

        # --- DAILY ---
        daily = []
        for d in daily_raw.get("forecast", [])[:7]:
            mf_code = d.get("weather")
            wmo = MF_TO_WMO.get(mf_code, None)

            daily.append(
                {
                    "date": d.get("datetime"),
                    "tmax_c": d.get("tmax"),
                    "tmin_c": d.get("tmin"),
                    "precip_mm": None,  # MF ne fournit pas la quantité
                    "wind_kmh": d.get("wind10m"),
                    "gust_kmh": d.get("gust10m"),
                    "weathercode": wmo,
                    "precip_prob": d.get("probarain"),
                }
            )

        # --- HOURLY ---
        hourly = []
        for h in hourly_raw.get("forecast", [])[:24]:
            mf_code = h.get("weather")
            wmo = MF_TO_WMO.get(mf_code, None)

            hourly.append(
                {
                    "datetime": h.get("datetime"),
                    "temp_c": h.get("temp2m"),
                    "apparent_temp_c": None,  # MF ne fournit pas
                    "dewpoint_c": h.get("dewpoint"),
                    "precip_prob": h.get("probarain"),
                    "precip_mm": None,
                    "weathercode": wmo,
                    "wind_kmh": h.get("wind10m"),
                    "gust_kmh": h.get("gust10m"),
                    "humidity": h.get("rh2m"),
                    "cloud_cover": None,
                }
            )

        return {
            "provider": self.PROVIDER_ID,
            "daily": daily,
            "hourly": hourly,
        }
