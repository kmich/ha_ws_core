"""Empty sensors say what is happening: status_text, lightning proximity and clearance."""

from __future__ import annotations

from collections import deque
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from custom_components.ws_core import const as c
from custom_components.ws_core.event import WSFrostEvent, WSLightningEvent, WSRainEvent
from custom_components.ws_core.sensor import WSSensor, WSSensorDescription
from custom_components.ws_core.sensor_status import status_text, unknown_status
from tests.test_coordinator import _make_coordinator

# --- status_text wording -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("reason", "explanation", "text"),
    [
        ("waiting_for_lightning_location", None, "No recent strike"),
        ("no_strike_recorded", None, "No strike yet"),
        ("calm", None, "Calm"),
        ("collecting_training_data", "Collecting: 2/5 events, 352.2/7.0 checked days.", "Learning (2 of 5 events)"),
        ("collecting_training_data", "no counts here", "Learning"),
        ("waiting_for:dp_24h", None, "Waiting for history"),
        ("waiting_for_first_run", None, "Starting up"),
        ("something_new", None, "Waiting for data"),
        (None, None, "Waiting for data"),
    ],
)
def test_status_text_wording(reason, explanation, text):
    assert status_text(reason, explanation=explanation) == text


def _nowcast_coord():
    return SimpleNamespace(sources={}, nowcast_enabled=True, _nowcast_cache={"x": 1})


@pytest.mark.parametrize(
    ("key", "rate", "text"),
    [
        (c.KEY_MINUTES_UNTIL_RAIN, 0.0, "No rain expected"),
        (c.KEY_MINUTES_UNTIL_RAIN, 1.2, "Raining now"),
        (c.KEY_MINUTES_UNTIL_DRY, 0.0, "Not raining"),
        (c.KEY_MINUTES_UNTIL_DRY, 1.2, "Rain continues"),
    ],
)
def test_nowcast_minutes_say_what_is_happening(key, rate, text):
    data = {c.KEY_NOWCAST_INTENSITY: "none", c.KEY_RAIN_RATE_FILT: rate}
    out = unknown_status(key, _nowcast_coord(), data)
    assert out["reason"] == "no_transition_in_forecast"
    assert out["status_text"] == text


def test_every_unknown_status_has_a_status_text():
    co = SimpleNamespace(sources={}, nowcast_enabled=False, _nowcast_cache=None, _blitzortung_sources={})
    for key in (
        c.KEY_HEAT_INDEX,
        c.KEY_WIND_GUST_FACTOR,
        c.KEY_MINUTES_UNTIL_RAIN,
        c.KEY_LIGHTNING_DISTANCE_KM,
        c.KEY_LIGHTNING_CLEARANCE_MIN,
        "some_other_key",
    ):
        assert unknown_status(key, co, {})["status_text"]


def test_pattern_sensor_status_text_while_learning_and_after_restart():
    learning = WSSensorDescription(
        key="pattern_frost_12h",
        attrs_fn=lambda d: {
            "maturity": "collecting",
            "reason": "collecting_training_data",
            "explanation": "Collecting: 1/5 events, 348.3/7.0 checked days.",
        },
    )
    coordinator = MagicMock()
    coordinator.data = {}
    attrs = WSSensor(coordinator, MagicMock(entry_id="e"), learning, "ws").extra_state_attributes
    assert attrs["status_text"] == "Learning (1 of 5 events)"

    first_run = WSSensorDescription(key="pattern_rain_3h", attrs_fn=lambda d: {"maturity": "learning"})
    attrs = WSSensor(coordinator, MagicMock(entry_id="e"), first_run, "ws").extra_state_attributes
    assert attrs["status_text"] == "Starting up"


@pytest.mark.parametrize(
    ("cls", "text"),
    [(WSRainEvent, "No rain event yet"), (WSFrostEvent, "No frost yet"), (WSLightningEvent, "No strike yet")],
)
def test_events_without_history_say_so(cls, text):
    ent = cls(MagicMock(), MagicMock(entry_id="e"), "ws")
    assert ent.extra_state_attributes["status_text"] == text


# --- lightning proximity and clearance ---------------------------------------------------


def _lightning_coord():
    coord = _make_coordinator()
    coord.lightning_enabled = True
    coord._lightning_proximity_km = 25.0
    coord._lightning_count_history_1h = deque()
    coord._lightning_last_count = None
    coord._lightning_last_strike_ts = None
    coord._lightning_last_near_strike_ts = None
    coord._blitzortung_sources = {}
    coord._last_blitz_scan_ts = 0.0
    coord.entry_data = {**coord.entry_data, "entry_id": "station"}
    return coord


def _registry(entity_id="event.ws_lightning_event"):
    # ``entities`` is read by the rate-limited Blitzortung discovery, whose timing depends on the clock
    return SimpleNamespace(async_get_entity_id=lambda domain, platform, uid: entity_id, entities={})


def _run(coord, now, event_state=None):
    states = {"event.ws_lightning_event": event_state} if event_state is not None else {}
    data: dict = {}
    with (
        patch.object(coord, "_num", return_value=None),
        patch("homeassistant.helpers.entity_registry.async_get", return_value=_registry()),
        patch.object(coord.hass.states, "get", side_effect=lambda eid: states.get(eid), create=True),
    ):
        coord._compute_lightning(data, now)
    return data


def test_proximity_is_clear_when_the_distance_source_reports_no_strike():
    coord = _lightning_coord()
    coord._blitzortung_sources = {c.SRC_LIGHTNING_DISTANCE: "sensor.blitzortung_distance"}
    data = _run(coord, datetime.now(UTC))
    assert data[c.KEY_LIGHTNING_PROXIMITY] == "clear"


def test_proximity_stays_unknown_without_a_distance_source():
    coord = _lightning_coord()
    data = _run(coord, datetime.now(UTC))
    assert c.KEY_LIGHTNING_PROXIMITY not in data


def test_clearance_resumes_from_the_lightning_event_after_a_restart():
    coord = _lightning_coord()
    now = datetime(2026, 11, 21, 8, 0, tzinfo=UTC)
    last = now - timedelta(days=14)
    data = _run(coord, now, SimpleNamespace(state=last.isoformat()))
    assert data[c.KEY_LIGHTNING_CLEARANCE_MIN] == round(14 * 24 * 60, 0)
    assert coord._lightning_strike_restored is True


def test_clearance_waits_while_the_event_entity_is_still_loading():
    coord = _lightning_coord()
    now = datetime(2026, 11, 21, 8, 0, tzinfo=UTC)
    data = _run(coord, now, SimpleNamespace(state="unavailable"))
    assert c.KEY_LIGHTNING_CLEARANCE_MIN not in data
    assert getattr(coord, "_lightning_strike_restored", False) is False  # tried again next update


def test_clearance_stays_unknown_when_no_strike_was_ever_recorded():
    coord = _lightning_coord()
    data = _run(coord, datetime.now(UTC), SimpleNamespace(state="unknown"))
    assert c.KEY_LIGHTNING_CLEARANCE_MIN not in data
    assert coord._lightning_strike_restored is True


def test_a_new_strike_wins_over_the_restored_time():
    coord = _lightning_coord()
    now = datetime(2026, 11, 21, 8, 0, tzinfo=UTC)
    coord._lightning_last_strike_ts = now - timedelta(minutes=5)
    data = _run(coord, now, SimpleNamespace(state=(now - timedelta(days=14)).isoformat()))
    assert data[c.KEY_LIGHTNING_CLEARANCE_MIN] == 5
