"""Tests for WSRainExpected1h: device_class, availability, and source tagging.

Covers the nowcast-staleness / local-fallback work: the entity must go
explicitly unavailable when neither a fresh nowcast nor a Zambretti fallback
value exists, and must expose which path (nowcast vs local_fallback) produced
its current state.
"""

from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from custom_components.ws_core.binary_sensor import WSRainExpected1h
from custom_components.ws_core.const import (
    KEY_NOWCAST_FETCHED_AT,
    KEY_NOWCAST_STALE,
    KEY_RAIN_EXPECTED_1H,
    KEY_RAIN_EXPECTED_SOURCE,
)


def _make_entity(data: dict, last_update_success: bool = True) -> WSRainExpected1h:
    coordinator = MagicMock()
    coordinator.data = data
    coordinator.last_update_success = last_update_success
    entry = MagicMock()
    entry.entry_id = "test_entry"
    return WSRainExpected1h(coordinator, entry, "ws")


class TestDeviceClass:
    def test_no_moisture_device_class(self):
        # MOISTURE is reserved for a current wetness/leak reading, not a
        # forecast flag - the entity must not claim it.
        ent = _make_entity({KEY_RAIN_EXPECTED_1H: True})
        assert ent.device_class is None


class TestAvailability:
    def test_available_with_nowcast_value(self):
        ent = _make_entity({KEY_RAIN_EXPECTED_1H: True, KEY_RAIN_EXPECTED_SOURCE: "nowcast"})
        assert ent.available is True
        assert ent.is_on is True

    def test_available_with_local_fallback_value(self):
        ent = _make_entity({KEY_RAIN_EXPECTED_1H: False, KEY_RAIN_EXPECTED_SOURCE: "local_fallback"})
        assert ent.available is True
        assert ent.is_on is False

    def test_unavailable_when_no_value_at_all(self):
        # Stale/failed nowcast and no Zambretti reading either.
        ent = _make_entity({KEY_RAIN_EXPECTED_1H: None, KEY_RAIN_EXPECTED_SOURCE: None})
        assert ent.available is False

    def test_unavailable_when_coordinator_update_failed(self):
        ent = _make_entity({KEY_RAIN_EXPECTED_1H: True}, last_update_success=False)
        assert ent.available is False


class TestAttributes:
    def test_attrs_expose_source_and_staleness(self):
        ent = _make_entity(
            {
                KEY_RAIN_EXPECTED_1H: True,
                KEY_RAIN_EXPECTED_SOURCE: "local_fallback",
                KEY_NOWCAST_FETCHED_AT: "2026-09-26T10:00:00+00:00",
                KEY_NOWCAST_STALE: True,
            }
        )
        attrs = ent.extra_state_attributes
        assert attrs["source"] == "local_fallback"
        assert attrs["nowcast_stale"] is True
        assert attrs["nowcast_fetched_at"] == "2026-09-26T10:00:00+00:00"
