"""Météo France forecast provider via the Météo Concept API (API key required)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import aiohttp
from homeassistant.util import dt as dt_util

from .base import ForecastProvider, _to_datetime, local_date_str, local_datetime_str, utc_datetime_str

_LOGGER = logging.getLogger(__name__)

# Météo Concept integer weather codes -> nearest WMO equivalent
# Full code table: https://api.meteo-concept.com/documentation
_MF_TO_WMO: dict[int, int] = {
    0: 0,  # Soleil -> clear sky
    1: 1,  # Peu nuageux -> mainly clear
    2: 2,  # Ciel voilé -> partly cloudy
    3: 2,  # Nuageux -> partly cloudy
    4: 3,  # Très nuageux -> overcast
    5: 3,  # Couvert -> overcast
    6: 45,  # Brouillard -> fog
    7: 48,  # Brouillard givrant -> depositing rime fog
    10: 61,  # Pluie faible -> slight rain
    11: 63,  # Pluie modérée -> moderate rain
    12: 65,  # Pluie forte -> heavy rain
    13: 66,  # Pluie faible verglaçante -> light freezing rain
    14: 67,  # Pluie modérée verglaçante -> heavy freezing rain
    15: 67,  # Pluie forte verglaçante -> heavy freezing rain
    16: 51,  # Bruine -> drizzle
    20: 71,  # Neige faible -> slight snow
    21: 73,  # Neige modérée -> moderate snow
    22: 75,  # Neige forte -> heavy snow
    30: 77,  # Pluie et neige faibles -> snow grains / mixed
    31: 77,  # Pluie et neige modérées
    32: 77,  # Pluie et neige fortes
    40: 80,  # Averses pluie locales peu fréquentes -> slight rain showers
    41: 80,
    42: 81,  # Averses locales fréquentes -> moderate rain showers
    43: 80,
    44: 81,
    45: 82,  # Averses fréquentes -> violent rain showers
    46: 80,
    47: 80,
    48: 81,
    60: 85,  # Averses neige locales -> slight snow showers
    61: 85,
    62: 86,
    63: 85,
    64: 85,
    65: 86,
    66: 85,
    67: 85,
    68: 86,
    70: 77,  # Averses pluie/neige mêlées
    71: 77,
    72: 77,
    73: 77,
    74: 77,
    75: 77,
    100: 95,  # Orages faibles -> slight thunderstorm
    101: 95,
    102: 96,  # Orages forts -> thunderstorm with hail
    103: 95,
    104: 95,
    105: 96,
    106: 96,  # Orages + risque grêle
    107: 96,
    200: 45,  # Brouillard (duplicate code)
    201: 48,  # Brouillard givrant (duplicate code)
}


class MeteoFranceProvider(ForecastProvider):
    """Météo France provider via Météo Concept API. API key required (free tier available)."""

    PROVIDER_ID = "meteo_france"
    PROVIDER_NAME = "Météo France"
    REQUIRES_API_KEY = True

    _BASE_URL = "https://api.meteo-concept.com/api"

    async def _fetch_endpoint(
        self,
        session: aiohttp.ClientSession,
        path: str,
        headers: dict[str, str],
        params: dict[str, str],
        *,
        allow_fallback_status: bool = False,
    ) -> dict[str, Any] | None:
        url = f"{self._BASE_URL}/{path}"
        async with session.get(url, headers=headers, params=params, timeout=aiohttp.ClientTimeout(total=20)) as resp:
            if resp.status == 401:
                raise ValueError("Météo France: invalid or unauthorized API key")
            if resp.status == 429:
                raise ValueError("Météo France: API rate limit exceeded")
            if allow_fallback_status and resp.status in (403, 404):
                return None
            if resp.status != 200:
                raise aiohttp.ClientResponseError(resp.request_info, resp.history, status=resp.status)
            return await resp.json(content_type=None)

    async def async_fetch(
        self,
        session: aiohttp.ClientSession,
        lat: float,
        lon: float,
        api_key: str | None = None,
    ) -> dict[str, Any]:
        if not api_key:
            raise ValueError("Météo France requires an API key (Météo Concept token)")

        headers = {"Authorization": f"Bearer {api_key}"}
        params = {"latlng": f"{lat},{lon}"}

        daily_data = await self._fetch_endpoint(session, "forecast/daily", headers, params) or {}

        daily_out: list[dict[str, Any]] = []
        for d in (daily_data.get("forecast") or [])[:7]:
            mf_code = d.get("weather")
            daily_out.append(
                {
                    "date": local_date_str(d.get("datetime")) or "",
                    "tmax_c": d.get("tmax"),
                    "tmin_c": d.get("tmin"),
                    "precip_mm": d.get("rr10"),
                    "wind_kmh": round(float(d["wind10m"]), 1) if d.get("wind10m") is not None else None,
                    "gust_kmh": round(float(d["gust10m"]), 1) if d.get("gust10m") is not None else None,
                    "weathercode": _MF_TO_WMO.get(mf_code) if mf_code is not None else None,
                    "precip_prob": d.get("probarain"),
                }
            )

        # Documented hourly routes: /forecast/daily/{0,1}/hourly?hourly=true (2 days = 48h),
        # with /forecast/nextHours?hourly=true fallback when a day route is restricted or incomplete.
        hourly_params = {**params, "hourly": "true"}
        now_utc = datetime.now(tz=UTC)
        by_slot: dict[datetime, dict[str, Any]] = {}

        def _collect_hourly(payload: dict[str, Any] | None) -> None:
            if not payload:
                return
            for item in payload.get("forecast") or []:
                raw_dt = item.get("datetime")
                dt = _to_datetime(raw_dt)
                if dt is None:
                    continue
                if dt.tzinfo is None:
                    dt = dt_util.as_local(dt)
                slot_utc = dt.astimezone(UTC)
                if slot_utc + timedelta(hours=1) <= now_utc:
                    continue
                by_slot.setdefault(slot_utc, {**item, "_dt": dt})

        day0 = await self._fetch_endpoint(
            session, "forecast/daily/0/hourly", headers, hourly_params, allow_fallback_status=True
        )
        _collect_hourly(day0)
        if day0 is not None and len(by_slot) < 25:
            day1 = await self._fetch_endpoint(
                session, "forecast/daily/1/hourly", headers, hourly_params, allow_fallback_status=True
            )
            _collect_hourly(day1)
        if len(by_slot) < 25:
            next_hours = await self._fetch_endpoint(
                session,
                "forecast/nextHours",
                headers,
                hourly_params,
                allow_fallback_status=bool(by_slot),
            )
            _collect_hourly(next_hours)

        hourly_out: list[dict[str, Any]] = []
        for slot_utc in sorted(by_slot)[:25]:
            h = by_slot[slot_utc]
            dt = h["_dt"]
            mf_code = h.get("weather")
            hourly_out.append(
                {
                    "datetime": local_datetime_str(dt) or "",
                    "utc_datetime": utc_datetime_str(dt),
                    "temp_c": h.get("temp2m"),
                    "apparent_temp_c": None,  # not provided by Météo Concept
                    "dewpoint_c": None,  # not provided by Météo Concept
                    "precip_prob": h.get("probarain"),
                    "precip_mm": h.get("rr10"),
                    "weathercode": _MF_TO_WMO.get(mf_code) if mf_code is not None else None,
                    "wind_kmh": round(float(h["wind10m"]), 1) if h.get("wind10m") is not None else None,
                    "gust_kmh": round(float(h["gust10m"]), 1) if h.get("gust10m") is not None else None,
                    "humidity": h.get("rh2m"),
                    "cloud_cover": h.get("nebulosity"),
                }
            )

        return {"provider": self.PROVIDER_ID, "daily": daily_out, "hourly": hourly_out}
