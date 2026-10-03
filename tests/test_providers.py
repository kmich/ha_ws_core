"""Unit tests for the ws_core forecast providers."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.ws_core.providers import (
    HaWeatherEntityProvider,
    MeteoFranceProvider,
    MetNoProvider,
    NwsNoaaProvider,
    OpenMeteoProvider,
    OpenWeatherMapProvider,
    PirateWeatherProvider,
    get_provider,
)


def test_get_provider_registry():
    assert isinstance(get_provider("open_meteo"), OpenMeteoProvider)
    assert isinstance(get_provider("met_no"), MetNoProvider)
    assert isinstance(get_provider("nws_noaa"), NwsNoaaProvider)
    assert isinstance(get_provider("openweathermap"), OpenWeatherMapProvider)
    assert isinstance(get_provider("pirate_weather"), PirateWeatherProvider)
    assert isinstance(get_provider("meteo_france"), MeteoFranceProvider)
    # Unknown falls back to OpenMeteo
    assert isinstance(get_provider("unknown_id"), OpenMeteoProvider)


def test_get_provider_ha_entity():
    mock_hass = MagicMock()
    prov = get_provider("ha_weather_entity", hass=mock_hass)
    assert isinstance(prov, HaWeatherEntityProvider)
    assert prov._hass is mock_hass


def test_provider_api_key_requirements():
    assert OpenMeteoProvider.REQUIRES_API_KEY is False
    assert MetNoProvider.REQUIRES_API_KEY is False
    assert NwsNoaaProvider.REQUIRES_API_KEY is False
    assert OpenWeatherMapProvider.REQUIRES_API_KEY is True
    assert PirateWeatherProvider.REQUIRES_API_KEY is True
    assert MeteoFranceProvider.REQUIRES_API_KEY is True


@pytest.mark.asyncio
async def test_met_no_provider_fetch():
    provider = MetNoProvider()
    session = MagicMock()

    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.json = AsyncMock(
        return_value={
            "properties": {
                "timeseries": [
                    {
                        "time": "2026-06-01T12:00:00Z",
                        "data": {
                            "instant": {
                                "details": {
                                    "air_temperature": 21.5,
                                    "relative_humidity": 55.0,
                                    "wind_speed": 4.0,
                                    "dew_point_temperature": 12.0,
                                    "cloud_area_fraction": 20.0,
                                }
                            },
                            "next_1_hours": {
                                "summary": {"symbol_code": "clearsky_day"},
                                "details": {"precipitation_amount": 0.0},
                            },
                        },
                    }
                ]
            }
        }
    )

    cm = AsyncMock()
    cm.__aenter__.return_value = mock_resp
    cm.__aexit__.return_value = None
    session.get.return_value = cm

    result = await provider.async_fetch(session, 59.91, 10.75)
    assert result["provider"] == "met_no"
    assert "daily" in result
    assert "hourly" in result
