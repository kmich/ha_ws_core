"""Leftover solar-radiation sensors are removed when the station cannot provide them.

Since 2.13.0 the solar sensors are only created with a W/m² source (or, for the
estimated ones, the illuminance fallback with a lux sensor). Registry entries made by
earlier versions stayed behind as unavailable "restored" entities.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.ws_core import const as c
from custom_components.ws_core.sensor import _async_remove_unsupported_solar_entities

ENTRY_ID = "solar_entry"
ESTIMATED_KEYS = (
    c.KEY_ET0_PM_DAILY_MM,
    c.KEY_SOLAR_ENERGY_TODAY_WHM2,
    c.KEY_PEAK_SUN_HOURS,
    c.KEY_NET_RADIATION,
)
MEASURED_KEYS = (c.KEY_CLEARNESS_INDEX, c.KEY_CLOUD_COVER_PCT)
ALL_SOLAR_KEYS = ESTIMATED_KEYS + MEASURED_KEYS


class _FakeRegistry:
    def __init__(self, entries):
        self.entities = {e.entity_id: e for e in entries}
        self.removed: list[str] = []

    def async_remove(self, entity_id):
        self.removed.append(entity_id)
        self.entities.pop(entity_id)


def _entry(key, *, entry_id=ENTRY_ID, domain="sensor", entity_id=None):
    return SimpleNamespace(
        entity_id=entity_id or f"{domain}.ws_{key}",
        unique_id=f"{entry_id}_{key}",
        config_entry_id=entry_id,
        domain=domain,
    )


def _run(entries, *, options=None, sources=None):
    registry = _FakeRegistry(entries)
    with patch("custom_components.ws_core.sensor.er.async_get", return_value=registry):
        _async_remove_unsupported_solar_entities(
            MagicMock(), SimpleNamespace(entry_id=ENTRY_ID), options or {}, sources or {}
        )
    return registry


def _removed_keys(registry):
    return {eid.split(".", 1)[1].removeprefix("ws_") for eid in registry.removed}


def test_no_solar_source_removes_all_six():
    registry = _run([_entry(k) for k in ALL_SOLAR_KEYS], sources={c.SRC_LUX: "sensor.lux"})
    assert _removed_keys(registry) == set(ALL_SOLAR_KEYS)


def test_mapped_solar_radiation_keeps_all_six():
    registry = _run([_entry(k) for k in ALL_SOLAR_KEYS], sources={c.SRC_SOLAR_RADIATION: "sensor.solar"})
    assert registry.removed == []


def test_illuminance_fallback_keeps_estimates_and_removes_measured_only():
    registry = _run(
        [_entry(k) for k in ALL_SOLAR_KEYS],
        options={c.CONF_ET0_ILLUMINANCE_FALLBACK: True},
        sources={c.SRC_LUX: "sensor.lux"},
    )
    assert _removed_keys(registry) == set(MEASURED_KEYS)


def test_fallback_without_a_lux_sensor_removes_all_six():
    registry = _run([_entry(k) for k in ALL_SOLAR_KEYS], options={c.CONF_ET0_ILLUMINANCE_FALLBACK: True})
    assert _removed_keys(registry) == set(ALL_SOLAR_KEYS)


def test_renamed_entity_is_matched_by_unique_id():
    renamed = _entry(c.KEY_ET0_PM_DAILY_MM, entity_id="sensor.station_ws_et0_penman_monteith_daily")
    registry = _run([renamed])
    assert registry.removed == ["sensor.station_ws_et0_penman_monteith_daily"]


def test_other_entries_other_domains_and_other_sensors_are_left_alone():
    other_entry = _entry(c.KEY_CLEARNESS_INDEX, entry_id="other_station", entity_id="sensor.other_clearness")
    other_domain = _entry(c.KEY_CLOUD_COVER_PCT, domain="binary_sensor")
    unrelated = _entry(c.KEY_HEAT_INDEX)
    registry = _run([other_entry, other_domain, unrelated])
    assert registry.removed == []
    assert len(registry.entities) == 3


async def test_setup_removes_leftover_solar_entities(hass, enable_custom_integrations):
    try:
        from pytest_homeassistant.common import MockConfigEntry
    except ImportError:
        from pytest_homeassistant_custom_component.common import MockConfigEntry
    from homeassistant.helpers import entity_registry as er

    entry = MockConfigEntry(
        domain=c.DOMAIN,
        entry_id=ENTRY_ID,
        data={
            c.CONF_PREFIX: "ws",
            c.CONF_SOURCES: {c.SRC_LUX: "sensor.lux"},
            c.CONF_FORECAST_LAT: 37.9,
            c.CONF_FORECAST_LON: 23.7,
        },
        options={},
    )
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    for key in ALL_SOLAR_KEYS:
        registry.async_get_or_create("sensor", c.DOMAIN, f"{ENTRY_ID}_{key}", config_entry=entry)
    registry.async_get_or_create(
        "sensor",
        c.DOMAIN,
        f"{ENTRY_ID}_{c.KEY_HEAT_INDEX}",
        config_entry=entry,
        suggested_object_id="ws_heat_index",
    )

    with (
        patch("custom_components.ws_core.PLATFORMS", ["sensor"]),
        patch("custom_components.ws_core.coordinator.WSStationCoordinator.async_start", AsyncMock()),
        patch("custom_components.ws_core.coordinator.WSStationCoordinator.async_stop", AsyncMock()),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    for key in ALL_SOLAR_KEYS:
        assert registry.async_get_entity_id("sensor", c.DOMAIN, f"{ENTRY_ID}_{key}") is None, key
    assert registry.async_get_entity_id("sensor", c.DOMAIN, f"{ENTRY_ID}_{c.KEY_HEAT_INDEX}") is not None
