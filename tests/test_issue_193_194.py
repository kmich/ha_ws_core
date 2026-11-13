"""Regression tests for issue #193 (current condition) and #194 (forecast times)."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest
from homeassistant.util import dt as dt_util

from custom_components.ws_core.algorithms import (
    CONDITION_DWELL_S,
    ConditionHold,
    determine_current_condition,
)
from custom_components.ws_core.const import CONF_PREFIX, KEY_CURRENT_CONDITION, KEY_FORECAST
from custom_components.ws_core.providers import HaWeatherEntityProvider
from custom_components.ws_core.providers.base import local_date_str, local_datetime_str
from custom_components.ws_core.weather import WSStationWeather
from tests.test_providers import _ha_entity_hass

# ---------------------------------------------------------------------------
# #193 — current condition
# ---------------------------------------------------------------------------


def _condition(**overrides):
    kwargs = {
        "temp_c": 9.0,
        "humidity": 92.0,
        "wind_speed_ms": 2.0,
        "wind_gust_ms": 5.0,
        "rain_rate_mmph": 0.0,
        "dew_point_c": 7.8,
        "illuminance_lx": 0.0,
        "uv_index": 0.0,
        "zambretti": "fine_weather",
        "pressure_trend": 0.0,
        "sun_elevation": -30.0,
        "sun_azimuth": 300.0,
        "is_day": False,
        "current_hour": 22,
    }
    kwargs.update(overrides)
    return determine_current_condition(**kwargs)


@pytest.mark.parametrize("z_text", ["stormy_much_rain", "stormy_may_improve"])
def test_stormy_outlook_in_rain_is_not_a_hurricane(z_text):
    """Falling pressure (Zambretti 'stormy') with light wind and rain reports rain."""
    assert _condition(zambretti=z_text, rain_rate_mmph=3.0, pressure_trend=-2.0) == "rainy"


def test_stormy_outlook_when_dry_is_pre_storm():
    assert _condition(zambretti="stormy_much_rain", pressure_trend=-2.0) == "pre-storm"


def test_hurricane_needs_measured_hurricane_gusts():
    assert _condition(wind_gust_ms=33.0, wind_speed_ms=20.0) == "hurricane"
    assert _condition(zambretti="stormy_much_rain", wind_gust_ms=8.0) != "hurricane"


def test_heavy_rain_under_stormy_outlook_still_thunderstorm():
    assert _condition(zambretti="stormy_much_rain", rain_rate_mmph=12.0) == "thunderstorm"


def test_condition_hold_ignores_flicker():
    hold = ConditionHold()
    assert hold.update("overcast-night", 0) == "overcast-night"
    # fog and overcast-night alternating every few seconds
    for t in range(5, 600, 10):
        cand = "fog" if (t // 10) % 2 else "overcast-night"
        assert hold.update(cand, t) == "overcast-night"


def test_condition_hold_adopts_a_lasting_change():
    hold = ConditionHold()
    hold.update("overcast-night", 0)
    assert hold.update("fog", 10) == "overcast-night"
    assert hold.update("fog", 10 + CONDITION_DWELL_S - 1) == "overcast-night"
    assert hold.update("fog", 10 + CONDITION_DWELL_S) == "fog"
    assert hold.update("overcast-night", 10 + CONDITION_DWELL_S + 5) == "fog"


def test_condition_hold_reports_critical_at_once():
    hold = ConditionHold()
    hold.update("rainy", 0)
    assert hold.update("hurricane", 1) == "hurricane"


# ---------------------------------------------------------------------------
# #194 — forecast timestamps
# ---------------------------------------------------------------------------


@pytest.fixture
def berlin_tz():
    old = dt_util.get_default_time_zone()
    dt_util.set_default_time_zone(ZoneInfo("Europe/Berlin"))
    try:
        yield
    finally:
        dt_util.set_default_time_zone(old)


def test_local_time_helpers(berlin_tz):
    assert local_datetime_str("2026-11-13T17:00:00+00:00") == "2026-11-13T18:00"
    assert local_datetime_str("2026-11-13T17:00:00Z") == "2026-11-13T18:00"
    assert local_datetime_str("2026-11-13T18:00:00+0100") == "2026-11-13T18:00"
    assert local_datetime_str("2026-11-13T18:00") == "2026-11-13T18:00"  # already local
    assert local_datetime_str(1794589200) == "2026-11-13T18:00"  # 17:00 UTC
    assert local_date_str("2026-11-13T23:00:00+00:00") == "2026-11-14"
    assert local_date_str("2026-11-14") == "2026-11-14"
    assert local_datetime_str(None) is None
    assert local_datetime_str("garbage") is None


@pytest.mark.asyncio
async def test_ha_entity_provider_returns_local_times(berlin_tz):
    """A weather entity answers in UTC; the forecast contract is local time."""
    hass = _ha_entity_hass(
        {"temperature_unit": "°C"},
        [{"datetime": "2026-11-13T23:00:00+00:00", "temperature": 8, "templow": 2}],
        [
            {"datetime": "2026-11-13T17:00:00+00:00", "temperature": 7},
            {"datetime": "2026-11-13T18:00:00+00:00", "temperature": 6},
        ],
    )
    result = await HaWeatherEntityProvider(hass).async_fetch(MagicMock(), 0, 0, api_key="weather.dwd")
    assert [h["datetime"] for h in result["hourly"]] == ["2026-11-13T18:00", "2026-11-13T19:00"]
    assert result["daily"][0]["date"] == "2026-11-14"


def _weather_entity(hourly, daily=None):
    coord = MagicMock()
    coord.data = {
        KEY_CURRENT_CONDITION: "rainy",
        KEY_FORECAST: {"provider": "ha_weather_entity", "hourly": hourly, "daily": daily or []},
    }
    entry = MagicMock()
    entry.entry_id = "e"
    entry.data = {CONF_PREFIX: "ws"}
    entry.options = {}
    return WSStationWeather(coord, entry, "ws")


@pytest.mark.asyncio
async def test_hourly_forecast_has_offset_and_skips_past_hours(berlin_tz):
    now = dt_util.now().replace(minute=0, second=0, microsecond=0)
    hours = [now + timedelta(hours=h) for h in (-2, -1, 0, 1)]
    hourly = [{"datetime": h.strftime("%Y-%m-%dT%H:%M"), "temp_c": 5.0} for h in hours]
    out = await _weather_entity(hourly).async_forecast_hourly()

    assert [o["datetime"] for o in out] == [hours[2].isoformat(), hours[3].isoformat()]
    # The frontend parses the offset, so the card shows the local hour.
    assert dt_util.parse_datetime(out[0]["datetime"]) == hours[2]


@pytest.mark.asyncio
async def test_daily_forecast_has_offset(berlin_tz):
    out = await _weather_entity([], [{"date": "2026-11-14", "tmax_c": 8}]).async_forecast_daily()
    assert out[0]["datetime"] == "2026-11-14T12:00:00+01:00"
