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
        ok, cap = _run_migration(
            2, {"hemisphere": "Northern", "climate_region": "Atlantic Europe", "prefix": "ws"}
        )
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
        _, cap = _run_migration(
            2, {"hemisphere": "northern", "climate_region": "mediterranean", "prefix": "ws"}
        )
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
