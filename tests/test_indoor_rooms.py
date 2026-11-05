"""Tests for named multi-room indoor monitoring (issue #115, v2.6.0).

Exercises WSStationCoordinator._compute_indoor directly with a minimal
hand-built coordinator so we don't need a full HA environment.
"""

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from homeassistant.components.sensor import SensorStateClass

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from custom_components.ws_core.const import (
    CONF_ENABLE_COMFORT_INDICES,
    CONF_ENABLE_INDOOR,
    CONF_INDOOR_ROOMS,
    CONF_PREFIX,
    KEY_ABSOLUTE_HUMIDITY,
    KEY_INDOOR_ROOMS_DATA,
    KEY_NORM_HUMIDITY,
    KEY_NORM_TEMP_C,
)
from custom_components.ws_core.coordinator import WSStationCoordinator
from custom_components.ws_core.sensor import WSSensor, async_setup_entry


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
        rooms = [
            {
                "id": "bedroom",
                "name": "Bedroom",
                "temp": "sensor.bed_t",
                "humidity": "sensor.bed_h",
                "co2": "sensor.bed_c",
            }
        ]
        coord = _build_coord(states, rooms)

        data = {KEY_NORM_TEMP_C: 10.0, KEY_NORM_HUMIDITY: 60.0}
        coord._compute_indoor(data)

        room = data[KEY_INDOOR_ROOMS_DATA]["bedroom"]
        assert room["name"] == "Bedroom"
        assert room["temp_c"] == 21.0
        assert room["delta_c"] == 11.0  # 21 indoor - 10 outdoor
        assert room["humidity_pct"] == 45.0
        assert room[KEY_ABSOLUTE_HUMIDITY] == pytest.approx(8.24, abs=0.01)
        assert room["humidity_delta_pct"] == -15.0  # 45 - 60
        assert room["co2_ppm"] == 800
        assert room["comfort"] == 100  # all values in comfortable bands

    def test_co2_penalty_lowers_comfort(self):
        states = {"sensor.t": _state(21.0, "°C"), "sensor.c": _state(1800, "ppm")}
        rooms = [{"id": "office", "name": "Office", "temp": "sensor.t", "humidity": None, "co2": "sensor.c"}]
        coord = _build_coord(states, rooms)
        data = {KEY_NORM_TEMP_C: 18.0}
        coord._compute_indoor(data)
        room = data[KEY_INDOOR_ROOMS_DATA]["office"]
        # CO2 >1500 -> -25; temp in band -> no penalty.
        assert room["comfort"] == 75
        assert "humidity_pct" not in room  # no humidity sensor assigned

    def test_temperature_only_room_has_no_co2_or_humidity_fields(self):
        states = {"sensor.t": _state(19.5, "°C")}
        rooms = [{"id": "loft", "name": "Loft", "temp": "sensor.t", "humidity": None, "co2": None}]
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
        rooms = [{"id": "garage", "name": "Garage", "temp": "sensor.t", "humidity": None, "co2": None}]
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

    @pytest.mark.parametrize("temperature,unit", [(21.0, "°C"), (69.8, "°F"), (294.15, "K")])
    def test_absolute_humidity_uses_room_inputs_without_outdoor_data(self, temperature, unit):
        states = {"sensor.t": _state(temperature, unit), "sensor.h": _state(45.0, "%")}
        rooms = [{"id": "bedroom", "name": "Bedroom", "temp": "sensor.t", "humidity": "sensor.h"}]
        coord = _build_coord(states, rooms)
        data = {}
        coord._compute_indoor(data)
        assert data[KEY_INDOOR_ROOMS_DATA]["bedroom"][KEY_ABSOLUTE_HUMIDITY] == pytest.approx(8.24, abs=0.01)

    @pytest.mark.parametrize("source", ["sensor.t", "sensor.h"])
    @pytest.mark.parametrize("value", [None, "unavailable", "unknown", "invalid", "nan", "inf"])
    def test_absolute_humidity_clears_when_either_source_is_missing(self, source, value):
        states = {"sensor.t": _state(21.0, "°C"), "sensor.h": _state(45.0, "%")}
        rooms = [{"id": "bedroom", "name": "Bedroom", "temp": "sensor.t", "humidity": "sensor.h"}]
        coord = _build_coord(states, rooms)
        first = {}
        coord._compute_indoor(first)
        assert KEY_ABSOLUTE_HUMIDITY in first[KEY_INDOOR_ROOMS_DATA]["bedroom"]
        if value is None:
            states.pop(source)
        else:
            states[source] = _state(value)
        updated = {}
        coord._compute_indoor(updated)
        assert KEY_ABSOLUTE_HUMIDITY not in updated[KEY_INDOOR_ROOMS_DATA]["bedroom"]

    def test_zero_relative_humidity_is_valid(self):
        rooms = [{"id": "dry", "name": "Dry", "temp": "sensor.t", "humidity": "sensor.h"}]
        coord = _build_coord({"sensor.t": _state(0, "°C"), "sensor.h": _state(0, "%")}, rooms)
        data = {}
        coord._compute_indoor(data)
        assert data[KEY_INDOOR_ROOMS_DATA]["dry"][KEY_ABSOLUTE_HUMIDITY] == 0


def _room_entities(rooms, enabled=True):
    coordinator = MagicMock()
    coordinator.sources = {}
    coordinator._pattern = None
    coordinator.data = {}
    entry = MagicMock(entry_id="indoor-test")
    entry.runtime_data = coordinator
    entry.data = {CONF_ENABLE_INDOOR: enabled, CONF_INDOOR_ROOMS: rooms}
    entry.options = {CONF_PREFIX: "home", CONF_ENABLE_COMFORT_INDICES: False}
    added = []
    setup = async_setup_entry(MagicMock(), entry, added.extend)
    with pytest.raises(StopIteration):
        setup.send(None)
    return coordinator, {entity._desc.key: entity for entity in added if isinstance(entity, WSSensor)}


def test_room_absolute_humidity_entities_use_independent_sources_and_update():
    rooms = [
        {"id": "bedroom", "name": "Bedroom", "temp": "sensor.bed_t", "humidity": "sensor.bed_h"},
        {"id": "office", "name": "Office", "temp": "sensor.office_t", "humidity": "sensor.office_h"},
    ]
    states = {
        "sensor.bed_t": _state(21, "°C"),
        "sensor.bed_h": _state(45, "%"),
        "sensor.office_t": _state(25, "°C"),
        "sensor.office_h": _state(60, "%"),
    }
    coord = _build_coord(states, rooms)
    data = {}
    coord._compute_indoor(data)
    platform_coord, entities = _room_entities(rooms)
    platform_coord.data = data
    bedroom = entities["indoor_room_absolute_humidity_bedroom"]
    office = entities["indoor_room_absolute_humidity_office"]
    assert bedroom.native_value == pytest.approx(8.24, abs=0.01)
    assert office.native_value == pytest.approx(13.81, abs=0.01)
    assert bedroom.entity_id == "sensor.home_indoor_room_absolute_humidity_bedroom"
    assert bedroom.unique_id == "indoor-test_indoor_room_absolute_humidity_bedroom"
    assert bedroom.native_unit_of_measurement == "g/m³"
    assert bedroom.device_class is None  # HA's humidity device class requires percent.
    assert bedroom.state_class == SensorStateClass.MEASUREMENT
    assert bedroom.entity_registry_enabled_default
    assert bedroom.translation_key == "indoor_room_absolute_humidity"
    assert bedroom.translation_placeholders == {"room_name": "Bedroom"}
    assert bedroom.extra_state_attributes == {
        "temp_c": 21.0,
        "humidity_pct": 45.0,
        "temperature_source_entity": "sensor.bed_t",
        "humidity_source_entity": "sensor.bed_h",
    }
    states["sensor.bed_h"] = _state("unavailable")
    platform_coord.data = {}
    coord._compute_indoor(platform_coord.data)
    assert bedroom.native_value is None
    assert office.native_value == pytest.approx(13.81, abs=0.01)
    states["sensor.bed_h"] = _state(0, "%")
    platform_coord.data = {}
    coord._compute_indoor(platform_coord.data)
    assert bedroom.native_value == 0


@pytest.mark.parametrize("temp,humidity", [("sensor.t", None), (None, "sensor.h"), (None, None)])
def test_absolute_humidity_requires_both_mapped_room_sources(temp, humidity):
    rooms = [{"id": "room", "name": "Room", "temp": temp, "humidity": humidity, "co2": "sensor.co2"}]
    coord = _build_coord({"sensor.t": _state(21, "°C"), "sensor.h": _state(45, "%")}, rooms)
    data = {}
    coord._compute_indoor(data)
    assert KEY_ABSOLUTE_HUMIDITY not in data[KEY_INDOOR_ROOMS_DATA]["room"]
    _, entities = _room_entities(rooms)
    assert "indoor_room_absolute_humidity_room" not in entities


def test_disabled_indoor_group_creates_no_room_absolute_humidity_sensor():
    _, entities = _room_entities(
        [{"id": "room", "name": "Room", "temp": "sensor.t", "humidity": "sensor.h"}], enabled=False
    )
    assert "indoor_room_absolute_humidity_room" not in entities


def test_room_absolute_humidity_translations_preserve_room_placeholder():
    package = Path(__file__).resolve().parents[1] / "custom_components" / "ws_core"
    for path in [package / "strings.json", *sorted((package / "translations").glob("*.json"))]:
        strings = json.loads(path.read_text(encoding="utf-8"))
        assert "{room_name}" in strings["entity"]["sensor"]["indoor_room_absolute_humidity"]["name"], path.name
