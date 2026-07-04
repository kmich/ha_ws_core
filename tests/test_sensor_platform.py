"""Regression tests for the sensor platform module import.

Importing ``sensor.py`` exercises module-level references to Home Assistant
enums. ``SensorDeviceClass.WIND_DIRECTION`` and
``SensorStateClass.MEASUREMENT_ANGLE`` only exist in HA 2025.1+, but the
integration supports down to HA 2024.6.0 (hacs.json). These were previously
referenced unconditionally, so on an older core importing the module raised
``AttributeError`` and the whole sensor platform failed to load. No test
imported ``sensor.py``, so CI never caught it.

This test imports the module so any such HA-version incompatibility is caught
by the CI "Tests" job, which runs against a pinned HA version.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_sensor_module_imports_and_builds_descriptions():
    from custom_components.ws_core import sensor

    assert sensor.SENSORS, "SENSORS list should not be empty"
    keys = {s.key for s in sensor.SENSORS}
    # Both wind-direction sensors must be present regardless of HA version.
    from custom_components.ws_core.const import KEY_DOMINANT_WIND_DIR, KEY_NORM_WIND_DIR_DEG

    assert KEY_NORM_WIND_DIR_DEG in keys
    assert KEY_DOMINANT_WIND_DIR in keys


def test_wind_direction_classes_resolve_without_crashing():
    """The defensive lookups must always yield a usable value."""
    from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass

    from custom_components.ws_core import sensor

    # device class is either the real enum member (new HA) or None (old HA).
    assert sensor._WIND_DIRECTION_DEVICE_CLASS is None or isinstance(
        sensor._WIND_DIRECTION_DEVICE_CLASS, SensorDeviceClass
    )
    # state class always falls back to a real member, never missing.
    assert isinstance(sensor._MEASUREMENT_ANGLE_STATE_CLASS, SensorStateClass)


def _make_temp_sensor(prefix="ws"):
    from unittest.mock import MagicMock

    from custom_components.ws_core.const import KEY_NORM_TEMP_C
    from custom_components.ws_core.sensor import SENSORS, WSSensor

    desc = next(s for s in SENSORS if s.key == KEY_NORM_TEMP_C)
    coord = MagicMock()
    entry = MagicMock()
    entry.entry_id = "entry_1"
    return WSSensor(coord, entry, desc, prefix)


def test_fresh_install_entity_id_uses_prefix():
    """Fresh installs must still get sensor.{prefix}_{key} via suggested_object_id."""
    s = _make_temp_sensor(prefix="ws")
    # _slug_for_key maps the normalized temperature key to "temperature".
    assert s._attr_suggested_object_id == "ws_temperature"

    s2 = _make_temp_sensor(prefix="home")
    assert s2._attr_suggested_object_id == "home_temperature"


def test_added_to_hass_does_not_revert_user_rename():
    """A user-renamed entity_id must survive async_added_to_hass (restart)."""
    import asyncio
    from unittest.mock import AsyncMock, MagicMock, patch

    from custom_components.ws_core.sensor import WSSensor

    s = _make_temp_sensor()
    # Simulate a user who renamed the entity away from the default.
    s.entity_id = "sensor.my_outdoor_temperature"
    s.hass = MagicMock()

    reg = MagicMock()
    with (
        patch(
            "homeassistant.helpers.update_coordinator.CoordinatorEntity.async_added_to_hass",
            new=AsyncMock(),
        ),
        patch.object(WSSensor, "async_get_last_state", new=AsyncMock(return_value=None)),
        patch("homeassistant.helpers.entity_registry.async_get", return_value=reg),
    ):
        asyncio.run(s.async_added_to_hass())

    # The old behaviour force-renamed the entity back to sensor.ws_temperature.
    reg.async_update_entity.assert_not_called()
    assert s.entity_id == "sensor.my_outdoor_temperature"
