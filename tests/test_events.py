"""Tests for weather event entities (rain, frost, lightning)."""

from __future__ import annotations

from collections import deque
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

from custom_components.ws_core.const import KEY_LIGHTNING_COUNT_1H, SRC_LIGHTNING_COUNT, SRC_LIGHTNING_DISTANCE
from custom_components.ws_core.event import WSLightningEvent, WSRainEvent
from tests.test_coordinator import _make_coordinator, _make_state


def _rain_event() -> WSRainEvent:
    coord = MagicMock()
    entry = MagicMock()
    entry.entry_id = "evt_entry"
    ent = WSRainEvent(coord, entry, "ws")
    ent.async_write_ha_state = MagicMock()
    ent._trigger_event = MagicMock()
    return ent


def _lightning_event() -> WSLightningEvent:
    coord = MagicMock()
    entry = MagicMock()
    entry.entry_id = "evt_entry"
    ent = WSLightningEvent(coord, entry, "ws")
    ent.async_write_ha_state = MagicMock()
    ent._trigger_event = MagicMock()
    return ent


class TestRainEvent:
    def test_missing_rain_rate_does_not_fire_stopped_or_duplicate_started(self):
        ent = _rain_event()
        # Initial dry reading
        ent.check_and_fire({"rain_rate_mmph_filtered": 0.0})
        # Rain begins -> started
        ent.check_and_fire({"rain_rate_mmph_filtered": 2.4, "_rain_today_mm": 0.5})
        assert [c.args[0] for c in ent._trigger_event.call_args_list] == ["started"]

        # Sensor unavailable -> key missing or None: must NOT fire stopped
        ent.check_and_fire({})
        ent.check_and_fire({"rain_rate_mmph_filtered": None})
        assert [c.args[0] for c in ent._trigger_event.call_args_list] == ["started"]

        # Sensor recovers still raining -> must NOT fire a second started
        ent.check_and_fire({"rain_rate_mmph_filtered": 1.8, "_rain_today_mm": 0.8})
        assert [c.args[0] for c in ent._trigger_event.call_args_list] == ["started"]

        # Rain actually stops -> fires stopped once
        ent.check_and_fire({"rain_rate_mmph_filtered": 0.0, "_rain_today_mm": 0.8})
        assert [c.args[0] for c in ent._trigger_event.call_args_list] == ["started", "stopped"]


class TestLightningEvent:
    def test_new_strike_fires_even_when_old_strike_ages_out_of_1h_window(self):
        coord = _make_coordinator()
        coord.lightning_enabled = True
        coord._blitzortung_sources = {}
        coord.sources = {
            **coord.sources,
            SRC_LIGHTNING_COUNT: "sensor.l_count",
            SRC_LIGHTNING_DISTANCE: "sensor.l_dist",
        }
        t0 = datetime(2026, 11, 17, 12, 0, tzinfo=UTC)
        # An old strike occurred 61 minutes before t1, so it expires at t1.
        coord._lightning_count_history_1h = deque([(t0, 1.0)])
        coord._lightning_last_count = 5.0
        coord._lightning_last_strike_ts = t0

        ent = _lightning_event()
        coord.event_entities = {"WSLightningEvent": ent}

        # Seed initial count_1h=1 at t0 + 30m
        t_mid = t0 + timedelta(minutes=30)
        states = {
            "sensor.l_count": _make_state("5", "", t_mid),
            "sensor.l_dist": _make_state("25", "km", t_mid),
        }
        coord.hass.states.get = lambda eid: states.get(eid)
        data1: dict = {}
        coord._compute_lightning(data1, t_mid)
        assert data1[KEY_LIGHTNING_COUNT_1H] == 1
        ent.check_and_fire(data1)
        assert ent._trigger_event.call_count == 0

        # At t0 + 61m: old strike expires AND 1 new strike occurs (counter 5 -> 6).
        # count_1h stays 1, yet strike_detected MUST fire.
        t1 = t0 + timedelta(minutes=61)
        states["sensor.l_count"] = _make_state("6", "", t1)
        data2: dict = {}
        coord._compute_lightning(data2, t1)
        assert data2[KEY_LIGHTNING_COUNT_1H] == 1
        ent.check_and_fire(data2)
        assert [c.args[0] for c in ent._trigger_event.call_args_list] == ["strike_detected"]

    def test_counter_reset_does_not_fire_strike(self):
        coord = _make_coordinator()
        coord.lightning_enabled = True
        coord._blitzortung_sources = {}
        coord.sources = {**coord.sources, SRC_LIGHTNING_COUNT: "sensor.l_count"}
        t0 = datetime(2026, 11, 17, 12, 0, tzinfo=UTC)
        coord._lightning_last_count = 10.0

        ent = _lightning_event()
        states = {"sensor.l_count": _make_state("0", "", t0)}
        coord.hass.states.get = lambda eid: states.get(eid)

        data: dict = {}
        coord._compute_lightning(data, t0)
        ent.check_and_fire(data)
        ent._trigger_event.assert_not_called()
