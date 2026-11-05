"""Source health regressions for unchanged pressure and calm wind reports."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from custom_components.ws_core import coordinator as cmod
from custom_components.ws_core.const import (
    KEY_DATA_QUALITY_SCORE,
    KEY_HEALTH_DISPLAY,
    KEY_NORM_HUMIDITY,
    KEY_NORM_PRESSURE_HPA,
    KEY_NORM_TEMP_C,
    KEY_NORM_WIND_GUST_MS,
    KEY_NORM_WIND_SPEED_MS,
    KEY_PACKAGE_OK,
    KEY_SENSOR_STUCK,
    SRC_GUST,
    SRC_PRESS,
    SRC_WIND,
)
from tests.test_coordinator import _make_coordinator

NOW = datetime(2026, 11, 5, 12, tzinfo=UTC)
OLD = NOW - timedelta(hours=12)


def _station(wind=0.0, gust=0.0):
    coord = _make_coordinator(wind_speed=wind, wind_gust=gust)
    coord.staleness_s = 7200
    for eid in coord.sources.values():
        state = coord.hass.states.get(eid)
        state.last_updated = NOW
        state.last_reported = NOW
    return coord


def _outputs(coord, now=NOW):
    data = {}
    with patch.object(cmod.ir, "async_create_issue") as create, patch.object(cmod.ir, "async_delete_issue"):
        coord._compute_data_quality_score(data, now)
        coord._compute_health(data, now, [], [])
    return data, create.call_args_list


@pytest.mark.parametrize("source", [SRC_WIND, SRC_PRESS])
def test_unchanged_but_reported_values_remain_healthy(source):
    coord = _station()
    coord.hass.states.get(coord.sources[source]).last_updated = OLD
    data, calls = _outputs(coord)
    assert data[KEY_PACKAGE_OK] is True
    assert data[KEY_HEALTH_DISPLAY] == "online"
    assert data[KEY_DATA_QUALITY_SCORE] == 100
    assert not any("stale_sensors" in c.args[2] for c in calls)


def test_stale_zero_wind_with_fresh_zero_gust_is_calm():
    coord = _station()
    state = coord.hass.states.get(coord.sources[SRC_WIND])
    state.last_updated = state.last_reported = OLD
    data, calls = _outputs(coord)
    assert data[KEY_PACKAGE_OK] is True
    assert data[KEY_DATA_QUALITY_SCORE] == 100
    assert SRC_WIND not in data["_stale_sources"]
    assert not any("stale_sensors" in c.args[2] for c in calls)


@pytest.mark.parametrize("gust", [1.0, "unavailable", "unknown", "nan"])
def test_nonzero_or_invalid_gust_cannot_corroborate_stale_calm_wind(gust):
    coord = _station(gust=gust)
    state = coord.hass.states.get(coord.sources[SRC_WIND])
    state.last_updated = state.last_reported = OLD
    data, calls = _outputs(coord)
    assert data[KEY_PACKAGE_OK] is False
    assert SRC_WIND in data["_stale_sources"]
    assert data[KEY_DATA_QUALITY_SCORE] < 100
    assert any("stale_sensors" in c.args[2] for c in calls)


@pytest.mark.parametrize("age", [601, 9000])
def test_gust_must_be_recent_enough_to_corroborate_calm(age):
    coord = _station()
    coord.hass.states.get(coord.sources[SRC_WIND]).last_reported = OLD
    coord.hass.states.get(coord.sources[SRC_GUST]).last_reported = NOW - timedelta(seconds=age)
    data, _ = _outputs(coord)
    assert SRC_WIND in data["_stale_sources"]


def test_calm_corroboration_respects_shorter_configured_timeout():
    coord = _station()
    coord.staleness_s = 60
    coord.hass.states.get(coord.sources[SRC_WIND]).last_reported = OLD
    coord.hass.states.get(coord.sources[SRC_GUST]).last_reported = NOW - timedelta(seconds=61)
    data, _ = _outputs(coord)
    assert SRC_WIND in data["_stale_sources"]


def test_all_sources_stopped_reporting_remain_stale():
    coord = _station()
    for eid in coord.sources.values():
        state = coord.hass.states.get(eid)
        state.last_updated = state.last_reported = OLD
    data, calls = _outputs(coord)
    assert data[KEY_PACKAGE_OK] is False
    assert SRC_WIND in data["_stale_sources"]
    assert SRC_PRESS in data["_stale_sources"]
    assert any("stale_sensors" in c.args[2] for c in calls)


def test_stale_nonzero_wind_is_not_exempted_by_fresh_zero_gust():
    coord = _station(wind=1.0)
    coord.hass.states.get(coord.sources[SRC_WIND]).last_reported = OLD
    data, _ = _outputs(coord)
    assert SRC_WIND in data["_stale_sources"]


def test_missing_gust_mapping_does_not_exempt_calm_wind():
    coord = _station()
    coord.sources.pop(SRC_GUST)
    coord.hass.states.get(coord.sources[SRC_WIND]).last_reported = OLD
    get_state = coord.hass.states.get

    def strict_get(entity_id):
        # Match the real StateMachine: None is not a valid entity ID.
        assert isinstance(entity_id, str)
        return get_state(entity_id)

    coord.hass.states.get = strict_get
    data, _ = _outputs(coord)
    assert SRC_WIND in data["_stale_sources"]


def test_last_updated_fallback_for_states_without_last_reported():
    coord = _station()
    old_state = SimpleNamespace(state="0.0", attributes={}, last_updated=OLD)
    original_get = coord.hass.states.get
    coord.hass.states.get = lambda eid: old_state if eid == "sensor.wind" else original_get(eid)
    coord.sources.pop(SRC_GUST)
    assert coord._source_is_stale(SRC_WIND, NOW) is True


def test_unavailable_pressure_still_degrades_health():
    coord = _station()
    coord.hass.states.get(coord.sources[SRC_PRESS]).state = "unavailable"
    data, _ = _outputs(coord)
    assert data[KEY_PACKAGE_OK] is False


def test_fresh_constant_integer_pressure_has_no_stuck_or_consistency_warning():
    coord = _station(wind=3.0, gust=4.0)
    coord._pressure_stuck_ref = 1013.0
    coord._pressure_stuck_start = OLD
    coord._rain_total_for_consistency = None
    coord._rain_rate_nonzero_since = None
    for hour in range(12):
        now = NOW + timedelta(hours=hour)
        for eid in coord.sources.values():
            coord.hass.states.get(eid).last_reported = now
        data = {
            KEY_NORM_TEMP_C: 20.0 + hour,
            KEY_NORM_HUMIDITY: 50.0 + hour,
            KEY_NORM_PRESSURE_HPA: 1013.0,
            KEY_NORM_WIND_SPEED_MS: 3.0,
            KEY_NORM_WIND_GUST_MS: 4.0,
        }
        coord._compute_data_quality_score(data, now)
        coord._compute_consistency_checks(data, now)
    assert SRC_PRESS not in data[KEY_SENSOR_STUCK]
    assert data["_pressure_stuck"] is False
    assert not any(f["check"] == "pressure_stuck" for f in data["_consistency_details"])
