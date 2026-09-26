"""Regression tests for config-entry migration (async_migrate_entry).

The v2 -> v3 migration slugs the hemisphere / climate_region values so the
selectors can be translated (issue #104). This runs on every existing install
on upgrade to 2.5.0, so it is worth a dedicated guard.
"""

from __future__ import annotations

import asyncio
import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from custom_components.ws_core import async_migrate_entry
from custom_components.ws_core.const import CONFIG_VERSION


def _run_migration(version, data, options=None):
    """Invoke async_migrate_entry against a mocked hass/entry; return update kwargs."""
    hass = MagicMock()
    hass.config.latitude = 37.9
    hass.config.longitude = 23.7

    captured: dict = {}

    def _update(entry, **kw):
        captured.update(kw)

    hass.config_entries.async_update_entry = _update

    entry = MagicMock()
    entry.version = version
    entry.data = dict(data)
    entry.options = dict(options or {})
    entry.entry_id = "test_entry"

    fake_registry = MagicMock()
    fake_registry.entities.values.return_value = []

    with patch("custom_components.ws_core.er.async_get", return_value=fake_registry):
        result = asyncio.run(async_migrate_entry(hass, entry))

    return result, captured


class TestMigration:
    def test_v2_slugs_display_values_in_data(self):
        ok, cap = _run_migration(2, {"hemisphere": "Northern", "climate_region": "Atlantic Europe", "prefix": "ws"})
        assert ok is True
        assert cap["version"] == CONFIG_VERSION
        assert cap["data"]["hemisphere"] == "northern"
        assert cap["data"]["climate_region"] == "atlantic_europe"

    def test_v2_slugs_display_values_in_options(self):
        _, cap = _run_migration(
            2,
            {"prefix": "ws"},
            {"hemisphere": "Southern", "climate_region": "North America West"},
        )
        assert cap["options"]["hemisphere"] == "southern"
        assert cap["options"]["climate_region"] == "north_america_west"

    def test_already_slugged_values_are_left_unchanged(self):
        # An unknown / already-slug value must pass through untouched (idempotent).
        _, cap = _run_migration(2, {"hemisphere": "northern", "climate_region": "mediterranean", "prefix": "ws"})
        assert cap["data"]["hemisphere"] == "northern"
        assert cap["data"]["climate_region"] == "mediterranean"

    def test_v1_entry_gets_slug_defaults(self):
        # v1 -> v2 fills hemisphere from latitude (37.9 -> northern) as a slug.
        _, cap = _run_migration(1, {"prefix": "ws"})
        assert cap["data"]["hemisphere"] == "northern"
        assert cap["data"]["climate_region"] in {
            "atlantic_europe",
            "mediterranean",
            "continental_europe",
            "scandinavia",
            "north_america_east",
            "north_america_west",
            "australia",
            "custom",
        }


class TestOrphanedForecasterCleanup:
    """switch.ws_enable_local_forecaster / number.ws_forecaster_learning_rate are
    leftovers from the unreleased v2.0 AI/local-forecaster work and show up as
    restored/unavailable on some instances. Cleanup runs on every setup (not
    tied to a config version bump, since affected instances are already current).
    """

    def _entity(self, entity_id, unique_id, config_entry_id):
        ent = MagicMock()
        ent.entity_id = entity_id
        ent.unique_id = unique_id
        ent.config_entry_id = config_entry_id
        return ent

    def test_removes_only_matching_uids_for_this_entry(self):
        from custom_components.ws_core import _async_remove_orphaned_forecaster_entities

        entry = MagicMock()
        entry.entry_id = "entry1"

        dead_switch = self._entity("switch.ws_enable_local_forecaster", "entry1_enable_local_forecaster", "entry1")
        dead_number = self._entity("number.ws_forecaster_learning_rate", "entry1_forecaster_learning_rate", "entry1")
        legit_sensor = self._entity("sensor.ws_temperature", "entry1_temperature", "entry1")
        # Same unique_id suffix but a *different* config entry - must be left alone.
        other_entry_dead = self._entity(
            "switch.ws2_enable_local_forecaster", "entry2_enable_local_forecaster", "entry2"
        )
        # A legitimately user-disabled restored switch - must not be touched.
        user_disabled = self._entity("switch.ws_enable_lightning", "entry1_enable_lightning", "entry1")

        fake_registry = MagicMock()
        fake_registry.entities = {
            e.entity_id: e for e in (dead_switch, dead_number, legit_sensor, other_entry_dead, user_disabled)
        }

        hass = MagicMock()
        with patch("custom_components.ws_core.er.async_get", return_value=fake_registry):
            _async_remove_orphaned_forecaster_entities(hass, entry)

        removed = {c.args[0] for c in fake_registry.async_remove.call_args_list}
        assert removed == {"switch.ws_enable_local_forecaster", "number.ws_forecaster_learning_rate"}

    def test_no_op_once_already_removed(self):
        from custom_components.ws_core import _async_remove_orphaned_forecaster_entities

        entry = MagicMock()
        entry.entry_id = "entry1"
        fake_registry = MagicMock()
        fake_registry.entities = {}

        hass = MagicMock()
        with patch("custom_components.ws_core.er.async_get", return_value=fake_registry):
            _async_remove_orphaned_forecaster_entities(hass, entry)

        fake_registry.async_remove.assert_not_called()


class TestIndoorRoomsMigration:
    """v3 -> v4 (v2.6.0): legacy list[str] indoor rooms -> named-room dicts."""

    def test_legacy_entity_id_list_is_upconverted(self):
        _, cap = _run_migration(
            3,
            {"prefix": "ws"},
            {"indoor_rooms": ["sensor.bedroom_temp", "sensor.office_temp"]},
        )
        assert cap["version"] == CONFIG_VERSION
        rooms = cap["options"]["indoor_rooms"]
        assert isinstance(rooms, list) and len(rooms) == 2
        first = rooms[0]
        assert first["temp"] == "sensor.bedroom_temp"
        assert first["humidity"] is None and first["co2"] is None
        assert first["id"] and first["name"]
        # Name derived from the entity slug, title-cased.
        assert first["name"] == "Bedroom Temp"

    def test_already_dict_shape_is_preserved(self):
        room = {
            "id": "bedroom",
            "name": "Bedroom",
            "temp": "sensor.bt",
            "humidity": "sensor.bh",
            "co2": None,
        }
        _, cap = _run_migration(3, {"prefix": "ws"}, {"indoor_rooms": [room]})
        rooms = cap["options"]["indoor_rooms"]
        assert rooms[0]["id"] == "bedroom"
        assert rooms[0]["humidity"] == "sensor.bh"

    def test_no_indoor_rooms_key_is_noop(self):
        _, cap = _run_migration(3, {"prefix": "ws"}, {})
        assert "indoor_rooms" not in cap["options"]
        assert cap["version"] == CONFIG_VERSION

    def test_duplicate_ids_are_deduplicated(self):
        _, cap = _run_migration(
            3,
            {"prefix": "ws"},
            {"indoor_rooms": ["sensor.temp", "sensor.temp"]},
        )
        rooms = cap["options"]["indoor_rooms"]
        assert rooms[0]["id"] != rooms[1]["id"]
