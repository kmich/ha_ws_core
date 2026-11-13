"""Abstract base class for forecast providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any

import aiohttp
from homeassistant.util import dt as dt_util


def local_datetime_str(value: datetime | str | int | float | None) -> str | None:
    """Wall-clock time in Home Assistant's timezone, as the contract's "YYYY-MM-DDTHH:MM".

    Accepts an aware datetime, an ISO string with an offset ("Z", "+01:00" or
    "+0100"), or a Unix timestamp. An ISO string without an offset is taken to
    be local already. Every consumer of the forecast compares these strings
    with the local hour, and the weather entity attaches the local timezone
    to them, so a UTC wall-clock here shows up shifted by the UTC offset.
    """
    dt = _to_datetime(value)
    if dt is None:
        return None
    return dt_util.as_local(dt).strftime("%Y-%m-%dT%H:%M")


def local_date_str(value: datetime | str | int | float | None) -> str | None:
    """Calendar date in Home Assistant's timezone, as "YYYY-MM-DD"."""
    dt = _to_datetime(value)
    if dt is None:
        return None
    return dt_util.as_local(dt).strftime("%Y-%m-%d")


def _to_datetime(value: datetime | str | int | float | None) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=UTC)
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


class ForecastProvider(ABC):
    """Abstract base for weather forecast providers.

    To add a new provider:
      1. Subclass ForecastProvider in a new file under providers/
      2. Set PROVIDER_ID (snake_case), PROVIDER_NAME (display name), REQUIRES_API_KEY
      3. Implement async_fetch() returning the normalized dict format below
      4. Register in providers/__init__.py PROVIDERS dict

    Normalized return format from async_fetch():
    {
        "provider": str,          # matches PROVIDER_ID
        "daily": [                # exactly 7 entries
            {
                "date": str,          # local date "YYYY-MM-DD"
                "tmax_c": float|None,
                "tmin_c": float|None,
                "precip_mm": float|None,
                "wind_kmh": float|None,
                "gust_kmh": float|None,
                "weathercode": int|None,   # WMO code; None if provider doesn't supply
                "precip_prob": int|None,   # 0-100 %; None if not available
            },
            ...
        ],
        "hourly": [               # up to 24 entries (next 24 h)
            {
                "datetime": str,       # "YYYY-MM-DDTHH:MM", local time in HA's
                                       # timezone (use local_datetime_str)
                "temp_c": float|None,
                "apparent_temp_c": float|None,
                "dewpoint_c": float|None,
                "precip_prob": int|None,
                "precip_mm": float|None,
                "weathercode": int|None,
                "wind_kmh": float|None,
                "gust_kmh": float|None,
                "humidity": float|None,
                "cloud_cover": float|None,
            },
            ...
        ],
    }
    """

    PROVIDER_ID: str = ""
    PROVIDER_NAME: str = ""
    REQUIRES_API_KEY: bool = False

    @abstractmethod
    async def async_fetch(
        self,
        session: aiohttp.ClientSession,
        lat: float,
        lon: float,
        api_key: str | None = None,
    ) -> dict[str, Any]:
        """Fetch forecast and return normalized dict."""
