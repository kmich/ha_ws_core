"""Open-Meteo forecast provider (free, no API key)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta, timezone, tzinfo
from typing import Any

import aiohttp
from homeassistant.util import dt as dt_util

from .base import ForecastProvider, local_datetime_str, utc_datetime_str

_LOGGER = logging.getLogger(__name__)


def _parse_om_time(raw_t: Any, default_tz: tzinfo | None) -> datetime | None:
    """Parse an Open-Meteo timestamp into a timezone-aware datetime."""
    if raw_t is None or raw_t == "":
        return None
    if isinstance(raw_t, (int, float)) and not isinstance(raw_t, bool):
        return datetime.fromtimestamp(raw_t, tz=UTC)
    try:
        dt = datetime.fromisoformat(str(raw_t).replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=default_tz or dt_util.get_default_time_zone())
    return dt


class OpenMeteoProvider(ForecastProvider):
    """Forecast provider backed by Open-Meteo (free, no API key, global)."""

    PROVIDER_ID = "open_meteo"
    PROVIDER_NAME = "Open-Meteo"
    REQUIRES_API_KEY = False

    async def async_fetch(
        self,
        session: aiohttp.ClientSession,
        lat: float,
        lon: float,
        api_key: str | None = None,
    ) -> dict[str, Any]:
        url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}"
            "&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,"
            "windspeed_10m_max,windgusts_10m_max,weathercode,precipitation_probability_max"
            "&hourly=temperature_2m,apparent_temperature,dewpoint_2m,"
            "precipitation_probability,precipitation,"
            "weathercode,windspeed_10m,windgusts_10m,"
            "relativehumidity_2m,cloudcover"
            "&forecast_hours=26"
            "&timezone=auto"
        )
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as resp:
            if resp.status != 200:
                raise aiohttp.ClientResponseError(resp.request_info, resp.history, status=resp.status)
            js = await resp.json()

        daily = js.get("daily") or {}
        times = daily.get("time") or []
        tmax = daily.get("temperature_2m_max") or []
        tmin = daily.get("temperature_2m_min") or []
        pr = daily.get("precipitation_sum") or []
        ws = daily.get("windspeed_10m_max") or []
        wg = daily.get("windgusts_10m_max") or []
        wc = daily.get("weathercode") or []
        pp = daily.get("precipitation_probability_max") or []

        daily_out = [
            {
                "date": times[i],
                "tmax_c": tmax[i] if i < len(tmax) else None,
                "tmin_c": tmin[i] if i < len(tmin) else None,
                "precip_mm": pr[i] if i < len(pr) else None,
                "wind_kmh": ws[i] if i < len(ws) else None,
                "gust_kmh": wg[i] if i < len(wg) else None,
                "weathercode": wc[i] if i < len(wc) else None,
                "precip_prob": pp[i] if i < len(pp) else None,
            }
            for i in range(min(len(times), 7))
        ]

        om_tz: tzinfo | None = None
        utc_offset_s = js.get("utc_offset_seconds")
        tz_name = js.get("timezone")
        if isinstance(utc_offset_s, (int, float)) and not isinstance(utc_offset_s, bool):
            om_tz = timezone(timedelta(seconds=int(utc_offset_s)))
        if tz_name and (
            om_tz is None or (utc_offset_s == 0 and str(tz_name).upper() not in ("UTC", "GMT", "ETC/UTC", "ETC/GMT"))
        ):
            resolved_tz = dt_util.get_time_zone(str(tz_name))
            if resolved_tz is not None:
                om_tz = resolved_tz

        hourly = js.get("hourly") or {}
        h_times = hourly.get("time") or []
        h_temp = hourly.get("temperature_2m") or []
        h_app = hourly.get("apparent_temperature") or []
        h_dew = hourly.get("dewpoint_2m") or []
        h_pp = hourly.get("precipitation_probability") or []
        h_precip = hourly.get("precipitation") or []
        h_wc = hourly.get("weathercode") or []
        h_ws = hourly.get("windspeed_10m") or []
        h_wg = hourly.get("windgusts_10m") or []
        h_rh = hourly.get("relativehumidity_2m") or []
        h_cc = hourly.get("cloudcover") or []

        parsed_dts = [_parse_om_time(t, om_tz) for t in h_times]
        hourly_out: list[dict[str, Any]] = []
        for i in range(min(len(h_times), 25)):
            dt_i = parsed_dts[i]
            dt_next = parsed_dts[i + 1] if (i + 1) < len(parsed_dts) else None
            has_next_hour = (
                dt_i is not None
                and dt_next is not None
                and abs((dt_next.astimezone(UTC) - dt_i.astimezone(UTC)).total_seconds() - 3600.0) <= 1.0
            )
            next_idx = i + 1
            # Open-Meteo precipitation_probability, precipitation, and windgusts_10m are preceding-hour values,
            # so values stamped at t_{i+1} describe the interval [t_i, t_i + 1h).
            hourly_out.append(
                {
                    "datetime": (local_datetime_str(dt_i) if dt_i is not None else str(h_times[i])) or str(h_times[i]),
                    "utc_datetime": utc_datetime_str(dt_i) if dt_i is not None else None,
                    "temp_c": h_temp[i] if i < len(h_temp) else None,
                    "apparent_temp_c": h_app[i] if i < len(h_app) else None,
                    "dewpoint_c": h_dew[i] if i < len(h_dew) else None,
                    "precip_prob": h_pp[next_idx] if has_next_hour and next_idx < len(h_pp) else None,
                    "precip_mm": h_precip[next_idx] if has_next_hour and next_idx < len(h_precip) else None,
                    "weathercode": h_wc[i] if i < len(h_wc) else None,
                    "wind_kmh": h_ws[i] if i < len(h_ws) else None,
                    "gust_kmh": h_wg[next_idx] if has_next_hour and next_idx < len(h_wg) else None,
                    "humidity": h_rh[i] if i < len(h_rh) else None,
                    "cloud_cover": h_cc[i] if i < len(h_cc) else None,
                }
            )

        return {
            "provider": self.PROVIDER_ID,
            "daily": daily_out,
            "hourly": hourly_out,
        }
