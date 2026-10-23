"""Reasons for intentionally unknown values must match the actual prerequisites."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from custom_components.ws_core import const as c
from custom_components.ws_core.entity_descriptions import SENSORS
from custom_components.ws_core.event import WSRainEvent
from custom_components.ws_core.sensor import WSSensor
from custom_components.ws_core.sensor_status import unknown_status


def coord(**kwargs):
    return SimpleNamespace(sources={}, nowcast_enabled=True, _nowcast_cache=None, **kwargs)


@pytest.mark.parametrize("key", [c.KEY_HEAT_INDEX, c.KEY_THW_INDEX, c.KEY_THSW_INDEX, c.KEY_WIND_CHILL])
def test_mild_weather_is_not_a_sensor_failure(key):
    data = {c.KEY_NORM_TEMP_C: 22.0, c.KEY_NORM_HUMIDITY: 70.0, c.KEY_NORM_WIND_SPEED_MS: 2.0}
    assert unknown_status(key, coord(), data)["reason"] == "outside_valid_range"


def test_missing_temperature_does_not_claim_outside_range():
    assert unknown_status(c.KEY_HEAT_INDEX, coord(), {})["reason"] == "waiting_for_data"


@pytest.mark.parametrize(
    "key",
    [
        c.KEY_SOLAR_ENERGY_TODAY_WHM2,
        c.KEY_PEAK_SUN_HOURS,
        c.KEY_NET_RADIATION,
        c.KEY_CLOUD_COVER_PCT,
        c.KEY_CLEARNESS_INDEX,
    ],
)
def test_unmapped_solar_has_actionable_reason(key):
    assert unknown_status(key, coord(), {})["reason"] == "missing_solar_radiation"


def test_fresh_dry_nowcast_is_not_a_fetch_error():
    co = coord()
    co._nowcast_cache = {"raining_now": False, "next_60min_mm": 0}
    data = {c.KEY_NOWCAST_INTENSITY: "none"}
    assert unknown_status(c.KEY_MINUTES_UNTIL_RAIN, co, data)["reason"] == "no_transition_in_forecast"
    assert unknown_status(c.KEY_MINUTES_UNTIL_RAIN, co, {})["reason"] == "waiting_for_nowcast"


def test_lux_estimate_is_only_recognized_by_supported_solar_calculations():
    co = coord()
    co.sources[c.SRC_LUX] = "sensor.lux"
    co.et0_illuminance_fallback = True
    assert unknown_status(c.KEY_SOLAR_ENERGY_TODAY_WHM2, co, {})["reason"] == "waiting_for_data"
    assert unknown_status(c.KEY_CLOUD_COVER_PCT, co, {})["reason"] == "missing_solar_radiation"


def test_missing_lightning_and_idle_lightning_are_distinct():
    co = coord()
    assert unknown_status(c.KEY_LIGHTNING_DISTANCE_KM, co, {})["reason"] == "missing_lightning_source"
    co._blitzortung_sources = {c.SRC_LIGHTNING_DISTANCE: "sensor.distance"}
    assert unknown_status(c.KEY_LIGHTNING_DISTANCE_KM, co, {})["reason"] == "waiting_for_lightning_location"
    assert unknown_status(c.KEY_LIGHTNING_CLEARANCE_MIN, co, {})["reason"] == "no_strike_recorded"


def test_entity_merges_reason_and_clears_it_when_value_returns():
    co = MagicMock()
    co.sources = {}
    co.data = {c.KEY_NORM_TEMP_C: 22, c.KEY_NORM_HUMIDITY: 70}
    description = next(d for d in SENSORS if d.key == c.KEY_HEAT_INDEX)
    entity = WSSensor(co, MagicMock(entry_id="test"), description, "ws")
    assert entity.native_value is None
    assert entity.extra_state_attributes["reason"] == "outside_valid_range"
    co.data[c.KEY_HEAT_INDEX] = 30.0
    assert "reason" not in entity.extra_state_attributes


def test_event_reason_does_not_replace_event_type_or_timestamp():
    entity = WSRainEvent(MagicMock(), MagicMock(entry_id="test"), "ws")
    assert entity.extra_state_attributes["reason"] == "no_event_recorded"
    entity._trigger_event("started", {"rain_today_mm": 2.0})
    assert entity.state is not None
    assert entity.state_attributes["event_type"] == "started"
    assert entity.extra_state_attributes == {}
