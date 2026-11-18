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


def _ha_entity_hass(attributes: dict, daily: list[dict], hourly: list[dict]) -> MagicMock:
    hass = MagicMock()
    state = MagicMock()
    state.attributes = attributes
    hass.states.get.return_value = state

    async def _call(domain, service, data, blocking, return_response):
        forecast = daily if data["type"] == "daily" else hourly
        return {data["entity_id"]: {"forecast": forecast}}

    hass.services.async_call = AsyncMock(side_effect=_call)
    return hass


@pytest.mark.asyncio
async def test_ha_entity_provider_converts_imperial_source():
    """A °F/mph/in source entity is converted to the metric contract (issue #174)."""
    hass = _ha_entity_hass(
        {"temperature_unit": "°F", "wind_speed_unit": "mph", "precipitation_unit": "in"},
        [
            {
                "datetime": "2026-10-28T12:00:00+00:00",
                "temperature": 66,
                "templow": 39,
                "precipitation": 1.0,
                "wind_speed": 10,
                "wind_gust_speed": 20,
            }
        ],
        [{"datetime": "2026-10-28T12:00:00+00:00", "temperature": 32, "dew_point": 23, "wind_speed": 0}],
    )
    result = await HaWeatherEntityProvider(hass).async_fetch(MagicMock(), 0, 0, api_key="weather.pirateweather")

    day = result["daily"][0]
    assert day["tmax_c"] == pytest.approx(18.89, abs=0.01)
    assert day["tmin_c"] == pytest.approx(3.89, abs=0.01)
    assert day["precip_mm"] == pytest.approx(25.4)
    assert day["wind_kmh"] == pytest.approx(16.09, abs=0.01)
    assert day["gust_kmh"] == pytest.approx(32.19, abs=0.01)

    hour = result["hourly"][0]
    assert hour["temp_c"] == pytest.approx(0.0)
    assert hour["dewpoint_c"] == pytest.approx(-5.0)
    assert hour["wind_kmh"] == 0.0


@pytest.mark.asyncio
async def test_ha_entity_provider_metric_source_keeps_zero_values():
    """Metric values pass through, and 0 is not dropped as falsy."""
    hass = _ha_entity_hass(
        {"temperature_unit": "°C", "wind_speed_unit": "km/h", "precipitation_unit": "mm"},
        [{"datetime": "2026-10-28T12:00:00+00:00", "temperature": 12.5, "templow": 0, "precipitation": 0}],
        [],
    )
    result = await HaWeatherEntityProvider(hass).async_fetch(MagicMock(), 0, 0, api_key="weather.home")

    day = result["daily"][0]
    assert day["tmax_c"] == 12.5
    assert day["tmin_c"] == 0.0
    assert day["precip_mm"] == 0.0


@pytest.mark.asyncio
async def test_pirate_weather_precip_units_and_missing():
    provider = PirateWeatherProvider()
    session = MagicMock()
    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.json = AsyncMock(
        return_value={
            "daily": {
                "data": [
                    {
                        "time": 1763337600,
                        "temperatureHigh": 4.0,
                        "temperatureLow": -1.0,
                        "precipAccumulation": 1.25,  # cm -> 12.5 mm
                        "windSpeed": 3.0,
                        "precipProbability": 0.7,
                        "icon": "sleet",
                    },
                    {
                        "time": 1763424000,
                        "temperatureHigh": 8.0,
                        "temperatureLow": 2.0,
                        # Missing precipAccumulation & precipIntensity -> None, not 0.0
                        "windSpeed": 2.0,
                        "precipProbability": 0.1,
                        "icon": "cloudy",
                    },
                ]
            },
            "hourly": {
                "data": [
                    {"time": 1763337600, "temperature": 3.0, "precipIntensity": 1.4, "precipProbability": 0.6},
                    {"time": 1763341200, "temperature": 3.5, "precipProbability": 0.0},
                ]
            },
        }
    )
    cm = AsyncMock()
    cm.__aenter__.return_value = mock_resp
    cm.__aexit__.return_value = None
    session.get.return_value = cm

    res = await provider.async_fetch(session, 50.0, 10.0, api_key="secret")
    assert res["daily"][0]["precip_mm"] == pytest.approx(12.5)
    assert res["daily"][1]["precip_mm"] is None
    assert res["hourly"][0]["precip_mm"] == pytest.approx(1.4)
    assert res["hourly"][1]["precip_mm"] is None


@pytest.mark.asyncio
async def test_openweathermap_sums_rain_and_snow():
    provider = OpenWeatherMapProvider()
    session = MagicMock()
    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.json = AsyncMock(
        return_value={
            "daily": [
                {"dt": 1763337600, "temp": {"max": 3.0, "min": -1.0}, "rain": 2.5, "snow": 4.0, "pop": 0.8},
                {"dt": 1763424000, "temp": {"max": 0.0, "min": -5.0}, "snow": 3.0, "pop": 0.5},
                {"dt": 1763510400, "temp": {"max": 10.0, "min": 4.0}, "rain": 1.2, "pop": 0.3},
                {"dt": 1763596800, "temp": {"max": 12.0, "min": 5.0}, "pop": 0.0},
            ],
            "hourly": [
                {"dt": 1763337600, "temp": 1.0, "rain": {"1h": 0.6}, "snow": {"1h": 1.4}, "pop": 0.8},
                {"dt": 1763341200, "temp": -1.0, "snow": {"1h": 0.9}, "pop": 0.6},
            ],
        }
    )
    cm = AsyncMock()
    cm.__aenter__.return_value = mock_resp
    cm.__aexit__.return_value = None
    session.get.return_value = cm

    res = await provider.async_fetch(session, 50.0, 10.0, api_key="secret")
    assert [d["precip_mm"] for d in res["daily"]] == [6.5, 3.0, 1.2, 0.0]
    assert [h["precip_mm"] for h in res["hourly"]] == [2.0, 0.9]


@pytest.mark.asyncio
async def test_open_meteo_provider_timestamps_and_preceding_hour_alignment():
    from zoneinfo import ZoneInfo

    from homeassistant.util import dt as dt_util

    berlin = ZoneInfo("Europe/Berlin")
    old_tz = dt_util.get_default_time_zone()
    dt_util.set_default_time_zone(berlin)
    try:
        provider = OpenMeteoProvider()
        session = MagicMock()
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(
            return_value={
                "timezone": "America/New_York",
                "utc_offset_seconds": -14400,
                "daily": {},
                "hourly": {
                    # 08:00..11:00 EDT (-04:00) == 12:00..15:00Z == 14:00..17:00 CEST (+02:00)
                    "time": [
                        "2026-06-21T08:00",
                        "2026-06-21T09:00",
                        "2026-06-21T10:00",
                        "2026-06-21T11:00",
                    ],
                    "temperature_2m": [20.0, 21.0, 22.0, 23.0],
                    # Index 2 (10:00 NY) describes the preceding hour [09:00, 10:00) NY
                    "precipitation_probability": [0, 0, 85, 0],
                    "precipitation": [0.0, 0.0, 4.2, 0.0],
                    "windgusts_10m": [12.0, 14.0, 52.0, 15.0],
                },
            }
        )
        cm = AsyncMock()
        cm.__aenter__.return_value = mock_resp
        cm.__aexit__.return_value = None
        session.get.return_value = cm

        res = await provider.async_fetch(session, 40.71, -74.01)
        called_url = session.get.call_args.args[0]
        assert "&forecast_hours=25" in called_url

        hourly = res["hourly"]
        assert len(hourly) == 4

        # Slot 0: 08:00 NY = 12:00Z = 14:00 Berlin; gets index 1 values for [08:00, 09:00)
        assert hourly[0]["datetime"] == "2026-06-21T14:00"
        assert hourly[0]["utc_datetime"] == "2026-06-21T12:00:00+00:00"
        assert hourly[0]["precip_prob"] == 0
        assert hourly[0]["precip_mm"] == 0.0
        assert hourly[0]["gust_kmh"] == 14.0

        # Slot 1: 09:00 NY = 13:00Z = 15:00 Berlin; gets index 2 spike for [09:00, 10:00)
        assert hourly[1]["datetime"] == "2026-06-21T15:00"
        assert hourly[1]["utc_datetime"] == "2026-06-21T13:00:00+00:00"
        assert hourly[1]["precip_prob"] == 85
        assert hourly[1]["precip_mm"] == 4.2
        assert hourly[1]["gust_kmh"] == 52.0

        # Slot 2: 10:00 NY = 14:00Z = 16:00 Berlin; gets index 3 calm values for [10:00, 11:00)
        assert hourly[2]["datetime"] == "2026-06-21T16:00"
        assert hourly[2]["utc_datetime"] == "2026-06-21T14:00:00+00:00"
        assert hourly[2]["precip_prob"] == 0
        assert hourly[2]["precip_mm"] == 0.0
        assert hourly[2]["gust_kmh"] == 15.0

        # Slot 3: final timestamp has no 12:00 NY row -> unassessed (None) for preceding-hour fields
        assert hourly[3]["datetime"] == "2026-06-21T17:00"
        assert hourly[3]["utc_datetime"] == "2026-06-21T15:00:00+00:00"
        assert hourly[3]["precip_prob"] is None
        assert hourly[3]["precip_mm"] is None
        assert hourly[3]["gust_kmh"] is None
    finally:
        dt_util.set_default_time_zone(old_tz)
