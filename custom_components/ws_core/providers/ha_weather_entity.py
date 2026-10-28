"""Forecast provider that reads from an existing Home Assistant weather.* entity."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

import aiohttp
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util.unit_conversion import (
    DistanceConverter,
    SpeedConverter,
    TemperatureConverter,
)

from .base import ForecastProvider

_LOGGER = logging.getLogger(__name__)

# Map HA weather condition strings → WMO weather codes (best-effort)
_CONDITION_TO_WMO: dict[str, int] = {
    "clear-night": 0,
    "sunny": 0,
    "partlycloudy": 2,
    "cloudy": 3,
    "windy": 3,
    "windy-variant": 3,
    "fog": 45,
    "hail": 96,
    "lightning": 95,
    "lightning-rainy": 95,
    "pouring": 63,
    "rainy": 61,
    "snowy": 71,
    "snowy-rainy": 68,
    "exceptional": 0,
}

# weather.get_forecasts answers in the source entity's display units, which
# its state attributes name. ws_core's forecast contract is metric.
_TEMP_UNIT_ATTR = "temperature_unit"
_WIND_UNIT_ATTR = "wind_speed_unit"
_PRECIP_UNIT_ATTR = "precipitation_unit"


def _first(entry: dict, *keys: str) -> Any:
    """Return the first value among keys that is not None (0 is a real value)."""
    for key in keys:
        value = entry.get(key)
        if value is not None:
            return value
    return None


def _convert(value: Any, converter: Any, from_unit: str | None, to_unit: str) -> float | None:
    """Convert value into to_unit; pass it through when the source unit is unknown."""
    if value is None:
        return None
    try:
        num = float(value)
    except (TypeError, ValueError):
        return None
    if not from_unit or from_unit == to_unit:
        return num
    try:
        return round(converter.convert(num, from_unit, to_unit), 2)
    except HomeAssistantError:
        _LOGGER.debug("Unsupported forecast unit %r, passing the value through", from_unit)
        return num


class HaWeatherEntityProvider(ForecastProvider):
    """Forecast provider backed by an existing Home Assistant weather.* entity.

    No external API calls are made — data is read directly from HA state.
    The entity_id of the weather entity is passed via the api_key parameter.
    """

    PROVIDER_ID = "ha_weather_entity"
    PROVIDER_NAME = "Home Assistant weather entity"
    REQUIRES_API_KEY = False

    def __init__(self, hass: Any = None) -> None:
        self._hass = hass
        # Unit attributes of the source entity, refreshed on every fetch.
        self._units: dict[str, Any] = {}

    async def async_fetch(
        self,
        session: aiohttp.ClientSession,
        lat: float,
        lon: float,
        api_key: str | None = None,
    ) -> dict[str, Any]:
        """Read forecast from the HA weather entity identified by api_key (entity_id)."""
        if self._hass is None:
            raise ValueError("HaWeatherEntityProvider requires hass; pass hass= to get_provider()")
        entity_id = (api_key or "").strip()
        if not entity_id:
            raise ValueError("No weather entity_id configured for ha_weather_entity provider")

        # Try the service-based approach first (HA 2024.2+)
        daily_forecast = await self._get_forecast_via_service(entity_id, "daily")
        hourly_forecast = await self._get_forecast_via_service(entity_id, "hourly")

        state = self._hass.states.get(entity_id)
        # Fall back to the deprecated forecast attribute if service call fails
        if not daily_forecast and not hourly_forecast:
            if state is None:
                raise ValueError(f"Weather entity '{entity_id}' not found in Home Assistant")
            raw = state.attributes.get("forecast") or []
            # Determine if daily or hourly by checking datetime spacing
            daily_forecast = raw
            hourly_forecast = []

        self._units = dict(state.attributes) if state is not None else {}
        daily_out = self._normalise_daily(daily_forecast)
        hourly_out = self._normalise_hourly(hourly_forecast or [])

        return {
            "provider": self.PROVIDER_ID,
            "daily": daily_out,
            "hourly": hourly_out,
        }

    async def _get_forecast_via_service(self, entity_id: str, forecast_type: str) -> list[dict]:
        """Call weather.get_forecasts service and return the forecast list."""
        try:
            response = await self._hass.services.async_call(
                "weather",
                "get_forecasts",
                {"entity_id": entity_id, "type": forecast_type},
                blocking=True,
                return_response=True,
            )
            return (response or {}).get(entity_id, {}).get("forecast") or []
        except Exception as exc:  # noqa: BLE001
            _LOGGER.debug("weather.get_forecasts (%s, %s) unavailable: %s", entity_id, forecast_type, exc)
            return []

    def _temp_c(self, entry: dict, *keys: str) -> float | None:
        return _convert(_first(entry, *keys), TemperatureConverter, self._units.get(_TEMP_UNIT_ATTR), "°C")

    def _speed_kmh(self, entry: dict, *keys: str) -> float | None:
        return _convert(_first(entry, *keys), SpeedConverter, self._units.get(_WIND_UNIT_ATTR), "km/h")

    def _precip_mm(self, entry: dict, *keys: str) -> float | None:
        return _convert(_first(entry, *keys), DistanceConverter, self._units.get(_PRECIP_UNIT_ATTR), "mm")

    def _condition_to_wmo(self, condition: str | None) -> int | None:
        if not condition:
            return None
        return _CONDITION_TO_WMO.get(condition.lower())

    def _parse_dt(self, dt_str: str | None) -> str | None:
        if not dt_str:
            return None
        try:
            dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
            return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M")
        except (ValueError, AttributeError):
            return dt_str[:16] if dt_str else None

    def _normalise_daily(self, raw: list[dict]) -> list[dict]:
        out: list[dict] = []
        for entry in raw[:7]:
            dt_str = entry.get("datetime") or entry.get("date") or ""
            date = dt_str[:10] if dt_str else ""
            out.append(
                {
                    "date": date,
                    "tmax_c": self._temp_c(entry, "temperature", "native_temperature"),
                    "tmin_c": self._temp_c(entry, "templow", "native_templow"),
                    "precip_mm": self._precip_mm(entry, "precipitation", "native_precipitation"),
                    "wind_kmh": self._speed_kmh(entry, "wind_speed", "native_wind_speed"),
                    "gust_kmh": self._speed_kmh(entry, "wind_gust_speed", "native_wind_gust_speed"),
                    "weathercode": self._condition_to_wmo(entry.get("condition")),
                    "precip_prob": entry.get("precipitation_probability"),
                }
            )
        # Pad to 7 days with None entries if fewer returned
        while len(out) < 7:
            out.append(
                {
                    "date": "",
                    "tmax_c": None,
                    "tmin_c": None,
                    "precip_mm": None,
                    "wind_kmh": None,
                    "gust_kmh": None,
                    "weathercode": None,
                    "precip_prob": None,
                }
            )
        return out

    def _normalise_hourly(self, raw: list[dict]) -> list[dict]:
        out: list[dict] = []
        for entry in raw[:24]:
            out.append(
                {
                    "datetime": self._parse_dt(entry.get("datetime")) or "",
                    "temp_c": self._temp_c(entry, "temperature", "native_temperature"),
                    "apparent_temp_c": self._temp_c(entry, "apparent_temperature", "native_apparent_temperature"),
                    "dewpoint_c": self._temp_c(entry, "dew_point", "native_dew_point"),
                    "precip_prob": entry.get("precipitation_probability"),
                    "precip_mm": self._precip_mm(entry, "precipitation", "native_precipitation"),
                    "weathercode": self._condition_to_wmo(entry.get("condition")),
                    "wind_kmh": self._speed_kmh(entry, "wind_speed", "native_wind_speed"),
                    "gust_kmh": self._speed_kmh(entry, "wind_gust_speed", "native_wind_gust_speed"),
                    "humidity": entry.get("humidity"),
                    "cloud_cover": entry.get("cloud_coverage"),
                }
            )
        return out
