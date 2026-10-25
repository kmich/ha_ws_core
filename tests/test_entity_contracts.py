"""Entity creation and registration contracts for optional calculations."""

from unittest.mock import MagicMock

import pytest

from custom_components.ws_core import const as c
from custom_components.ws_core.entity_descriptions import SENSORS
from custom_components.ws_core.sensor import WSSensor, async_setup_entry


def _created_keys(options=None, sources=None):
    coordinator = MagicMock()
    coordinator.sources = sources or {}
    coordinator._pattern = None
    entry = MagicMock(entry_id="contract-test")
    entry.runtime_data = coordinator
    entry.data = {c.CONF_SOURCES: coordinator.sources}
    entry.options = options or {}
    added = []
    # Platform setup has no await points. Drive it directly so this test does
    # not need a Windows event-loop socket in restricted CI environments.
    setup = async_setup_entry(MagicMock(), entry, added.extend)
    with pytest.raises(StopIteration):
        setup.send(None)
    return {entity._desc.key for entity in added if isinstance(entity, WSSensor)}


def test_pm_entity_depends_on_local_radiation_not_pv_forecast():
    assert c.KEY_ET0_PM_DAILY_MM in _created_keys(sources={c.SRC_SOLAR_RADIATION: "sensor.solar"})
    assert c.KEY_ET0_PM_DAILY_MM in _created_keys(
        options={c.CONF_ET0_ILLUMINANCE_FALLBACK: True}, sources={c.SRC_LUX: "sensor.lux"}
    )
    assert c.KEY_ET0_PM_DAILY_MM not in _created_keys(options={c.CONF_ENABLE_SOLAR_FORECAST: True})
    assert c.KEY_SOLAR_FORECAST_TODAY_KWH not in _created_keys(sources={c.SRC_SOLAR_RADIATION: "sensor.solar"})


def test_fwi_components_can_be_selected_without_primary_fire_entities():
    keys = _created_keys(options={c.CONF_ENABLE_FWI_COMPONENTS: True})
    assert c.KEY_FWI_FFMC in keys
    assert c.KEY_FWI_BUI in keys
    assert c.KEY_FWI not in keys
    assert c.KEY_FIRE_RISK_SCORE not in keys


def test_solar_and_irrigation_metrics_do_not_depend_on_comfort_group():
    keys = _created_keys(sources={c.SRC_SOLAR_RADIATION: "sensor.solar"})
    assert c.KEY_SOLAR_ENERGY_TODAY_WHM2 in keys
    assert c.KEY_PEAK_SUN_HOURS in keys
    assert c.KEY_NET_RADIATION in keys
    assert c.KEY_IRRIGATION_DEFICIT in keys
    assert c.KEY_HEAT_INDEX not in keys


@pytest.mark.parametrize("description", SENSORS, ids=lambda d: d.key)
def test_runtime_enabled_default_matches_description(description):
    entity = WSSensor(MagicMock(), MagicMock(entry_id="contract-test"), description, "ws")
    assert entity.entity_registry_enabled_default == description.entity_registry_enabled_default


def test_fresh_and_existing_home_assistant_registry_choices():
    from homeassistant.helpers import entity_registry as er

    registry = er.EntityRegistry(MagicMock())
    registry.entities = er.EntityRegistryItems()
    registry.deleted_entities = {}
    registry.async_schedule_save = MagicMock()

    for key in (c.KEY_FWI, c.KEY_NORM_TEMP_C):
        description = next(d for d in SENSORS if d.key == key)
        entity = WSSensor(MagicMock(), MagicMock(entry_id="contract-test"), description, "ws")
        default_disabler = None if entity.entity_registry_enabled_default else er.RegistryEntryDisabler.INTEGRATION
        saved = registry.async_get_or_create(
            "sensor", c.DOMAIN, entity.unique_id,
            suggested_object_id=entity.entity_id.removeprefix("sensor."),
            disabled_by=default_disabler,
        )
        assert (saved.disabled_by is None) == description.entity_registry_enabled_default

        # A user override and rename survive re-registration on upgrade.
        override = None if default_disabler else er.RegistryEntryDisabler.USER
        saved = registry.async_update_entity(
            saved.entity_id,
            disabled_by=override,
            new_entity_id=f"sensor.user_{key}",
        )
        again = registry.async_get_or_create(
            "sensor", c.DOMAIN, entity.unique_id,
            suggested_object_id=entity.entity_id.removeprefix("sensor."),
            disabled_by=default_disabler,
        )
        assert again.entity_id == saved.entity_id
        assert again.disabled_by == override
