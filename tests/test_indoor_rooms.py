"""Tests for named multi-room indoor monitoring (issue #115, v2.6.0).

Exercises WSStationCoordinator._compute_indoor directly with a minimal
hand-built coordinator so we don't need a full HA environment.
"""

import os
import sys
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from custom_components.ws_core.const import (
    KEY_INDOOR_ROOMS_DATA,
    KEY_NORM_HUMIDITY,
    KEY_NORM_TEMP_C,
)
from custom_components.ws_core.coordinator import WSStationCoordinator


def _state(val, unit=""):
    m = MagicMock()
    m.state = str(val)
    m.attributes = {"unit_of_measurement": unit}
    m.last_updated = datetime.now(UTC)
    return m


def _build_coord(states, rooms):
    hass = MagicMock()
    hass.states.get = lambda eid: states.get(eid)
    with patch.object(WSStationCoordinator, "__init__", lambda self, *a, **kw: None):
        coord = WSStationCoordinator.__new__(WSStationCoordinator)
    coord.hass = hass
    coord.indoor_enabled = True
    coord._indoor_rooms = rooms
    coord._indoor_temp_prev = None
    coord._indoor_hum_prev = None
    # No main indoor group sensors configured for these tests.
    coord.sources = {}
    return coord


class TestIndoorRooms:
    def test_full_room_temp_humidity_co2_and_comfort(self):
        states = {
            "sensor.bed_t": _state(21.0, "°C"),
            "sensor.bed_h": _state(45.0, "%"),
            "sensor.bed_c": _state(800, "ppm"),
        }
        rooms = [{"id": "bedroom", "name": "Bedroom", "temp": "sensor.bed_t",
                  "humidity": "sensor.bed_h", "co2": "sensor.bed_c"}]
        coord = _build_coord(states, rooms)

        data = {KEY_NORM_TEMP_C: 10.0, KEY_NORM_HUMIDITY: 60.0}
        coord._compute_indoor(data)

        room = data[KEY_INDOOR_ROOMS_DATA]["bedroom"]
        assert room["name"] == "Bedroom"
        assert room["temp_c"] == 21.0
        assert room["delta_c"] == 11.0  # 21 indoor - 10 outdoor
        assert room["humidity_pct"] == 45.0
        assert room["humidity_delta_pct"] == -15.0  # 45 - 60
        assert room["co2_ppm"] == 800
        assert room["comfort"] == 100  # all values in comfortable bands

    def test_co2_penalty_lowers_comfort(self):
        states = {"sensor.t": _state(21.0, "°C"), "sensor.c": _state(1800, "ppm")}
        rooms = [{"id": "office", "name": "Office", "temp": "sensor.t",
                  "humidity": None, "co2": "sensor.c"}]
        coord = _build_coord(states, rooms)
        data = {KEY_NORM_TEMP_C: 18.0}
        coord._compute_indoor(data)
        room = data[KEY_INDOOR_ROOMS_DATA]["office"]
        # CO2 >1500 -> -25; temp in band -> no penalty.
        assert room["comfort"] == 75
        assert "humidity_pct" not in room  # no humidity sensor assigned

    def test_temperature_only_room_has_no_co2_or_humidity_fields(self):
        states = {"sensor.t": _state(19.5, "°C")}
        rooms = [{"id": "loft", "name": "Loft", "temp": "sensor.t",
                  "humidity": None, "co2": None}]
        coord = _build_coord(states, rooms)
        data = {KEY_NORM_TEMP_C: 5.0}
        coord._compute_indoor(data)
        room = data[KEY_INDOOR_ROOMS_DATA]["loft"]
        assert room["temp_c"] == 19.5
        assert room["delta_c"] == 14.5
        assert "co2_ppm" not in room and "humidity_pct" not in room
        assert room["comfort"] == 100

    def test_unavailable_sensor_is_skipped(self):
        states = {"sensor.t": _state("unavailable", "°C")}
        rooms = [{"id": "garage", "name": "Garage", "temp": "sensor.t",
                  "humidity": None, "co2": None}]
        coord = _build_coord(states, rooms)
        data = {KEY_NORM_TEMP_C: 5.0}
        coord._compute_indoor(data)
        # Room dict still present (carries name) but no readings.
        room = data[KEY_INDOOR_ROOMS_DATA]["garage"]
        assert "temp_c" not in room
        assert "comfort" not in room

    def test_no_rooms_leaves_key_unset(self):
        coord = _build_coord({}, [])
        data = {KEY_NORM_TEMP_C: 10.0}
        coord._compute_indoor(data)
        assert KEY_INDOOR_ROOMS_DATA not in data
