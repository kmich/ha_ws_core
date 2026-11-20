"""Unit tests for the ws_core forecast providers."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

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
    before = datetime(2026, 10, 28, 11, 30, tzinfo=UTC)  # the provider drops hours that already passed
    with patch("custom_components.ws_core.providers.ha_weather_entity.dt_util.utcnow", return_value=before):
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
        assert "&forecast_hours=26" in called_url

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


@pytest.mark.asyncio
async def test_owm_and_pirate_weather_preserve_zero_wind_gust():
    session = MagicMock()
    cm = AsyncMock()
    cm.__aexit__.return_value = None
    session.get.return_value = cm

    # OpenWeatherMap: wind_gust == 0.0 must stay 0.0, not None
    owm_resp = AsyncMock()
    owm_resp.status = 200
    owm_resp.json = AsyncMock(
        return_value={
            "daily": [
                {"dt": 1763337600, "temp": {"max": 12.0, "min": 5.0}, "wind_speed": 0.0, "wind_gust": 0.0, "pop": 0.0}
            ],
            "hourly": [{"dt": 1763337600, "temp": 10.0, "wind_speed": 0.0, "wind_gust": 0.0, "pop": 0.0}],
        }
    )
    cm.__aenter__.return_value = owm_resp
    owm_res = await OpenWeatherMapProvider().async_fetch(session, 50.0, 10.0, api_key="secret")
    assert owm_res["daily"][0]["gust_kmh"] == 0.0
    assert owm_res["daily"][0]["wind_kmh"] == 0.0
    assert owm_res["hourly"][0]["gust_kmh"] == 0.0
    assert owm_res["hourly"][0]["wind_kmh"] == 0.0

    # Pirate Weather: windGust == 0.0 must stay 0.0, not None
    pw_resp = AsyncMock()
    pw_resp.status = 200
    pw_resp.json = AsyncMock(
        return_value={
            "daily": {"data": [{"time": 1763337600, "windSpeed": 0.0, "windGust": 0.0, "precipProbability": 0.0}]},
            "hourly": {"data": [{"time": 1763337600, "windSpeed": 0.0, "windGust": 0.0, "precipProbability": 0.0}]},
        }
    )
    cm.__aenter__.return_value = pw_resp
    pw_res = await PirateWeatherProvider().async_fetch(session, 50.0, 10.0, api_key="secret")
    assert pw_res["daily"][0]["gust_kmh"] == 0.0
    assert pw_res["daily"][0]["wind_kmh"] == 0.0
    assert pw_res["hourly"][0]["gust_kmh"] == 0.0
    assert pw_res["hourly"][0]["wind_kmh"] == 0.0


@pytest.mark.asyncio
async def test_met_no_and_nws_keep_current_in_progress_hour():
    from datetime import UTC, datetime, timedelta
    from unittest.mock import patch

    fixed_now = datetime(2026, 6, 21, 12, 15, tzinfo=UTC)
    current_hr_iso = "2026-06-21T12:00:00Z"
    next_hr_iso = "2026-06-21T13:00:00Z"

    session = MagicMock()
    cm = AsyncMock()
    cm.__aexit__.return_value = None
    session.get.return_value = cm

    # Met.no keeps 12:00Z even when fetched at 12:15Z
    met_resp = AsyncMock()
    met_resp.status = 200
    met_resp.json = AsyncMock(
        return_value={
            "properties": {
                "timeseries": [
                    {"time": current_hr_iso, "data": {"instant": {"details": {"air_temperature": 21.0}}}},
                    {"time": next_hr_iso, "data": {"instant": {"details": {"air_temperature": 22.0}}}},
                ]
            }
        }
    )
    cm.__aenter__.return_value = met_resp
    with patch("custom_components.ws_core.providers.met_no.datetime") as mock_dt:
        mock_dt.now.return_value = fixed_now
        mock_dt.fromisoformat.side_effect = datetime.fromisoformat
        met_res = await MetNoProvider().async_fetch(session, 59.91, 10.75)
    assert [h["utc_datetime"] for h in met_res["hourly"]] == ["2026-06-21T12:00:00+00:00", "2026-06-21T13:00:00+00:00"]

    # NWS/NOAA keeps 12:00Z even when fetched at 12:15Z
    points_resp = AsyncMock()
    points_resp.status = 200
    points_resp.json = AsyncMock(
        return_value={
            "properties": {"forecast": "https://api.weather.gov/f", "forecastHourly": "https://api.weather.gov/h"}
        }
    )
    daily_resp = AsyncMock()
    daily_resp.status = 200
    daily_resp.json = AsyncMock(return_value={"properties": {"periods": []}})
    hourly_resp = AsyncMock()
    hourly_resp.status = 200
    hourly_resp.json = AsyncMock(
        return_value={
            "properties": {
                "periods": [
                    {"startTime": (fixed_now - timedelta(minutes=15)).isoformat(), "temperature": 70},
                    {"startTime": (fixed_now + timedelta(minutes=45)).isoformat(), "temperature": 72},
                ]
            }
        }
    )
    cm.__aenter__.side_effect = [points_resp, daily_resp, hourly_resp]
    with patch("custom_components.ws_core.providers.nws_noaa.datetime") as mock_nws_dt:
        mock_nws_dt.now.return_value = fixed_now
        mock_nws_dt.fromisoformat.side_effect = datetime.fromisoformat
        nws_res = await NwsNoaaProvider().async_fetch(session, 40.71, -74.01)
    assert [h["utc_datetime"] for h in nws_res["hourly"]] == ["2026-06-21T12:00:00+00:00", "2026-06-21T13:00:00+00:00"]


def test_capability_matrix_covers_every_registered_provider():
    from custom_components.ws_core.providers import PROVIDERS, get_provider_capabilities

    assert "ha_weather_entity" in PROVIDERS
    for pid, cls in PROVIDERS.items():
        caps = get_provider_capabilities(pid)
        assert caps.provider_id == pid
        assert caps.provider_id != "unknown"
        assert caps.requires_api_key is cls.REQUIRES_API_KEY
        assert caps.to_dict()["provider_id"] == pid

    # Alias compatibility
    assert get_provider_capabilities("open_weather_map").provider_id == "openweathermap"
    assert get_provider_capabilities("nonexistent").provider_id == "unknown"


@pytest.mark.asyncio
async def test_open_meteo_honors_zero_utc_offset_across_dst():
    """Open-Meteo uses the static response utc_offset_seconds (even 0) across DST transitions."""
    provider = OpenMeteoProvider()
    session = MagicMock()
    mock_resp = AsyncMock()
    mock_resp.status = 200
    # 2026-03-29 Europe/London springs forward at 01:00 UTC -> 02:00 BST, yet Open-Meteo
    # stamps the entire response using its fixed header offset (utc_offset_seconds = 0).
    mock_resp.json = AsyncMock(
        return_value={
            "timezone": "Europe/London",
            "utc_offset_seconds": 0,
            "daily": {},
            "hourly": {
                "time": [
                    "2026-03-29T00:00",
                    "2026-03-29T01:00",
                    "2026-03-29T02:00",
                    "2026-03-29T03:00",
                ],
                "temperature_2m": [8.0, 7.5, 7.0, 6.5],
                "precipitation_probability": [0, 10, 80, 0],
                "precipitation": [0.0, 0.2, 3.5, 0.0],
                "windgusts_10m": [10.0, 18.0, 48.0, 12.0],
            },
        }
    )
    cm = AsyncMock()
    cm.__aenter__.return_value = mock_resp
    cm.__aexit__.return_value = None
    session.get.return_value = cm

    res = await provider.async_fetch(session, 51.50, -0.12)
    hourly = res["hourly"]
    assert [h["utc_datetime"] for h in hourly] == [
        "2026-03-29T00:00:00+00:00",
        "2026-03-29T01:00:00+00:00",
        "2026-03-29T02:00:00+00:00",
        "2026-03-29T03:00:00+00:00",
    ]
    # All three intervals [00..01), [01..02), [02..03) retain exact 1h spacing and shifted metrics
    assert hourly[1]["precip_prob"] == 80
    assert hourly[1]["precip_mm"] == 3.5
    assert hourly[1]["gust_kmh"] == 48.0
    assert hourly[2]["precip_prob"] == 0
    assert hourly[2]["precip_mm"] == 0.0
    assert hourly[2]["gust_kmh"] == 12.0


@pytest.mark.asyncio
async def test_open_meteo_fetches_hourly_in_utc_and_daily_in_local_tz():
    from zoneinfo import ZoneInfo

    from homeassistant.util import dt as dt_util

    berlin = ZoneInfo("Europe/Berlin")
    old_tz = dt_util.get_default_time_zone()
    dt_util.set_default_time_zone(berlin)
    try:
        provider = OpenMeteoProvider()
        session = MagicMock()

        daily_resp = AsyncMock()
        daily_resp.status = 200
        daily_resp.json = AsyncMock(
            return_value={
                "timezone": "Europe/Berlin",
                "utc_offset_seconds": 7200,
                "daily": {
                    "time": ["2026-10-25"],
                    "temperature_2m_max": [16.0],
                    "temperature_2m_min": [6.0],
                    "precipitation_sum": [3.0],
                    "windspeed_10m_max": [20.0],
                    "windgusts_10m_max": [35.0],
                    "weathercode": [61],
                    "precipitation_probability_max": [70],
                },
            }
        )

        # Fall-back DST night in Europe/Berlin: 00:00Z..03:00Z cross both 02:00+02:00 and 02:00+01:00
        hourly_resp = AsyncMock()
        hourly_resp.status = 200
        hourly_resp.json = AsyncMock(
            return_value={
                "timezone": "GMT",
                "utc_offset_seconds": 0,
                "hourly": {
                    "time": [
                        "2026-10-25T00:00",
                        "2026-10-25T01:00",
                        "2026-10-25T02:00",
                        "2026-10-25T03:00",
                    ],
                    "temperature_2m": [11.0, 10.0, 9.0, 8.5],
                    "precipitation_probability": [0, 10, 85, 5],
                    "precipitation": [0.0, 0.1, 4.5, 0.0],
                    "windgusts_10m": [12.0, 18.0, 50.0, 14.0],
                },
            }
        )

        cm = AsyncMock()
        cm.__aexit__.return_value = None
        cm.__aenter__.side_effect = [daily_resp, hourly_resp]
        session.get.return_value = cm

        res = await provider.async_fetch(session, 52.52, 13.41)
        assert session.get.call_count == 2
        daily_url = session.get.call_args_list[0].args[0]
        hourly_url = session.get.call_args_list[1].args[0]
        assert "&daily=" in daily_url
        assert "&timezone=auto" in daily_url
        assert "&hourly=" not in daily_url
        assert "&hourly=" in hourly_url
        assert "&forecast_hours=26" in hourly_url
        assert "&timezone=UTC" in hourly_url
        assert "&daily=" not in hourly_url

        assert res["daily"][0]["date"] == "2026-10-25"
        hourly = res["hourly"]
        assert [h["utc_datetime"] for h in hourly] == [
            "2026-10-25T00:00:00+00:00",
            "2026-10-25T01:00:00+00:00",
            "2026-10-25T02:00:00+00:00",
            "2026-10-25T03:00:00+00:00",
        ]
        # Both repeated 02:00 local hours are kept distinctly with contiguous UTC intervals
        assert [h["datetime"] for h in hourly[:3]] == [
            "2026-10-25T02:00",
            "2026-10-25T02:00",
            "2026-10-25T03:00",
        ]
        assert hourly[1]["precip_prob"] == 85
        assert hourly[1]["precip_mm"] == 4.5
        assert hourly[1]["gust_kmh"] == 50.0
    finally:
        dt_util.set_default_time_zone(old_tz)


@pytest.mark.asyncio
async def test_meteo_france_documented_routes_and_wind_units():
    from datetime import UTC, datetime, timedelta
    from unittest.mock import patch

    fixed_now = datetime(2026, 6, 21, 18, 15, tzinfo=UTC)

    def _resp(status: int, payload: dict | None = None):
        r = AsyncMock()
        r.status = status
        r.json = AsyncMock(return_value=payload or {})
        return r

    daily_payload = {
        "forecast": [
            {
                "datetime": "2026-06-21T00:00:00+0200",
                "tmax": 26,
                "tmin": 14,
                "rr10": 1.2,
                "wind10m": 20,
                "gust10m": 45,
                "weather": 1,
                "probarain": 30,
            }
        ]
    }
    # Day 0 has 10 past hours and 4 active/future hours (20:00..23:00+02:00 == 18:00..21:00Z)
    day0_payload = {
        "forecast": [
            {
                "datetime": (datetime(2026, 6, 21, 16, 0, tzinfo=UTC) + timedelta(hours=k)).isoformat(),
                "temp2m": 20 + k,
                "rh2m": 60,
                "wind10m": 0 if k == 2 else 18,
                "gust10m": 0 if k == 2 else 36,
                "rr10": 0.0,
                "rr1": 1.2,
                "probarain": 10,
                "weather": 0,
            }
            for k in range(6)  # 16:00Z, 17:00Z (past at 18:15Z), 18:00Z..21:00Z (active/future)
        ]
    }
    day1_payload = {
        "forecast": [
            {
                "datetime": (datetime(2026, 6, 21, 22, 0, tzinfo=UTC) + timedelta(hours=k)).isoformat(),
                "temp2m": 15,
                "rh2m": 75,
                "wind10m": 12,
                "gust10m": 28,
                "rr10": 0.5,
                "rr1": 2.4,
                "probarain": 40,
                "weather": 10,
            }
            for k in range(24)
        ]
    }

    session = MagicMock()
    cm = AsyncMock()
    cm.__aexit__.return_value = None
    cm.__aenter__.side_effect = [
        _resp(200, daily_payload),
        _resp(200, day0_payload),
        _resp(200, day1_payload),
    ]
    session.get.return_value = cm

    with patch("custom_components.ws_core.providers.meteo_france.datetime") as mock_dt:
        mock_dt.now.return_value = fixed_now
        res = await MeteoFranceProvider().async_fetch(session, 48.112, -1.6819, api_key="tok")

    called = [(c.args[0], c.kwargs.get("params")) for c in session.get.call_args_list]
    assert called[0][0].endswith("/forecast/daily")
    assert called[1][0].endswith("/forecast/daily/0/hourly")
    assert called[1][1]["hourly"] == "true"
    assert called[2][0].endswith("/forecast/daily/1/hourly")
    assert called[2][1]["hourly"] == "true"
    assert not any(url.endswith("/forecast/hourly") for url, _ in called)

    # Wind/gust values stay in km/h (NOT multiplied by 3.6) and keep 0.0;
    # hourly precip_mm uses accumulated rr10 rather than upper-bound convective rr1.
    assert res["daily"][0]["wind_kmh"] == 20.0
    assert res["daily"][0]["gust_kmh"] == 45.0
    assert len(res["hourly"]) == 25
    assert res["hourly"][0]["utc_datetime"] == "2026-06-21T18:00:00+00:00"
    assert res["hourly"][0]["precip_mm"] == 0.0
    assert res["hourly"][0]["wind_kmh"] == 0.0
    assert res["hourly"][0]["gust_kmh"] == 0.0
    assert res["hourly"][1]["wind_kmh"] == 18.0
    assert res["hourly"][1]["gust_kmh"] == 36.0
    assert res["hourly"][4]["precip_mm"] == 0.5

    # When daily/{day}/hourly is forbidden, falls back to documented /forecast/nextHours?hourly=true
    session2 = MagicMock()
    cm2 = AsyncMock()
    cm2.__aexit__.return_value = None
    cm2.__aenter__.side_effect = [
        _resp(200, daily_payload),
        _resp(403, {}),
        _resp(
            200,
            {
                "forecast": [
                    {
                        "datetime": "2026-06-21T20:00:00+0200",
                        "temp2m": 22,
                        "rr10": 0.2,
                        "rr1": 1.8,
                        "wind10m": 15,
                        "gust10m": 32,
                        "weather": 1,
                    }
                ]
            },
        ),
    ]
    session2.get.return_value = cm2
    with patch("custom_components.ws_core.providers.meteo_france.datetime") as mock_dt:
        mock_dt.now.return_value = fixed_now
        fallback_res = await MeteoFranceProvider().async_fetch(session2, 48.112, -1.6819, api_key="tok")

    fallback_urls = [(c.args[0], c.kwargs.get("params")) for c in session2.get.call_args_list]
    assert fallback_urls[1][0].endswith("/forecast/daily/0/hourly")
    assert fallback_urls[2][0].endswith("/forecast/nextHours")
    assert fallback_urls[2][1]["hourly"] == "true"
    assert fallback_res["hourly"][0]["precip_mm"] == 0.2
    assert fallback_res["hourly"][0]["wind_kmh"] == 15.0
    assert fallback_res["hourly"][0]["gust_kmh"] == 32.0


@pytest.mark.asyncio
async def test_ha_entity_provider_drops_elapsed_hours_before_keeping_25_rows():
    """An entity that lists hours earlier in the day still yields the next 24 hours."""
    from datetime import timedelta

    now = datetime(2026, 11, 20, 18, 20, tzinfo=UTC)
    first = now.replace(minute=0) - timedelta(hours=10)
    rows = [{"datetime": (first + timedelta(hours=i)).isoformat(), "temperature": 10 + i * 0.1} for i in range(48)]
    hass = _ha_entity_hass({"temperature_unit": "°C"}, [], rows)
    with patch("custom_components.ws_core.providers.ha_weather_entity.dt_util.utcnow", return_value=now):
        result = await HaWeatherEntityProvider(hass).async_fetch(MagicMock(), 0, 0, api_key="weather.any")
    hourly = result["hourly"]
    assert len(hourly) == 25
    assert hourly[0]["utc_datetime"] == now.replace(minute=0).isoformat()  # the in-progress hour
