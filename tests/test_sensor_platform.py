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
    """Fresh installs must get sensor.{prefix}_{key}, not sensor.weather_station_{key}.

    Regression test for issue #134: entity.entity_id must be set directly.
    _attr_suggested_object_id is treated by Home Assistant as object_id_base,
    which gets prefixed with the device name ("Weather Station") instead of
    the configured prefix whenever has_entity_name=True.
    """
    s = _make_temp_sensor(prefix="ws")
    # _slug_for_key maps the normalized temperature key to "temperature".
    assert s.entity_id == "sensor.ws_temperature"

    s2 = _make_temp_sensor(prefix="home")
    assert s2.entity_id == "sensor.home_temperature"


def test_slug_for_key_only_strips_trailing_unit_suffix():
    """_slug_for_key must strip a unit suffix only at the END of the key.

    The old implementation used chained str.replace(), which also ate
    mid-string matches: "nowcast_confidence" -> "nowcastonfidence" (the "_c"
    inside "_confidence"). It should be left intact.
    """
    from custom_components.ws_core.sensor import WSSensor

    slug = WSSensor._slug_for_key
    # mid-string "_c" must survive
    assert slug("nowcast_confidence") == "nowcast_confidence"
    # trailing unit suffixes are still stripped
    assert slug("soil_temp_c") == "soil_temp"
    assert slug("wind_speed_ms") == "wind_speed"
    assert slug("station_pressure_hpa") == "station_pressure"
    assert slug("rain_rate_mmph") == "rain_rate"
    # keys with no suffix are untouched
    assert slug("dry_streak_days") == "dry_streak_days"


def test_every_sensor_slug_is_a_valid_object_id():
    """No SENSORS entry may produce an entity_id slug with a doubled or
    trailing underscore, or an empty slug."""
    import re

    from custom_components.ws_core.sensor import SENSORS, WSSensor

    for desc in SENSORS:
        slug = WSSensor._slug_for_key(desc.key)
        assert slug and re.fullmatch(r"[a-z0-9]+(?:_[a-z0-9]+)*", slug), f"{desc.key!r} -> bad slug {slug!r}"


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
