"""Real config entry setup, options flow and unload (v3.0.0).

The minimum-version CI job runs this file against the oldest supported Home Assistant,
so a newer-only API in setup, the coordinator constructor or the flows fails there.
"""

from __future__ import annotations

from unittest.mock import patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er

from custom_components.ws_core import const as c

try:
    from pytest_homeassistant.common import MockConfigEntry
except ImportError:
    from pytest_homeassistant_custom_component.common import MockConfigEntry


def _entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=c.DOMAIN,
        entry_id="smoke_station",
        title="Smoke station",
        data={
            c.CONF_PREFIX: "ws",
            c.CONF_NAME: "Smoke station",
            c.CONF_SOURCES: {c.SRC_TEMP: "sensor.smoke_temp", c.SRC_HUM: "sensor.smoke_hum"},
            c.CONF_FORECAST_ENABLED: False,
            c.CONF_FORECAST_LAT: 37.9,
            c.CONF_FORECAST_LON: 23.7,
        },
        options={},
    )


async def test_real_setup_options_flow_and_unload(hass, enable_custom_integrations):
    hass.states.async_set("sensor.smoke_temp", "21.5", {"unit_of_measurement": "°C"})
    hass.states.async_set("sensor.smoke_hum", "55", {"unit_of_measurement": "%"})
    hass.states.async_set(
        "sensor.smoke_event_rain", "21.4", {"unit_of_measurement": "mm", "state_class": "total_increasing"}
    )
    entry = _entry()
    entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        entry,
        data={
            **entry.data,
            c.CONF_SOURCES: {**entry.data[c.CONF_SOURCES], c.SRC_RAIN_TOTAL: "sensor.smoke_event_rain"},
        },
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get("sensor.ws_data_status") is not None
    await entry.runtime_data.async_refresh()
    rainfall_counter = hass.states.get("sensor.ws_rain_total")
    assert rainfall_counter is not None
    assert float(rainfall_counter.state) == 21.4
    assert rainfall_counter.name.endswith("Rainfall Counter")
    assert hass.services.has_service(c.DOMAIN, "get_weather_windows")

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.MENU
    assert result["menu_options"]
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": result["menu_options"][0]}
    )
    assert result["type"] in (FlowResultType.FORM, FlowResultType.MENU)
    hass.config_entries.options.async_abort(result["flow_id"])

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.services.has_service(c.DOMAIN, "get_weather_windows")


async def test_failed_platform_setup_stops_coordinator(hass, enable_custom_integrations):
    entry = _entry()
    entry.add_to_hass(hass)
    with patch.object(
        type(hass.config_entries), "async_forward_entry_setups", side_effect=RuntimeError("test platform failure")
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert entry.runtime_data._stopped
    assert not hass.services.has_service(c.DOMAIN, "get_weather_windows")


async def test_feature_opt_in_restores_only_integration_disabled_entities(hass, enable_custom_integrations):
    entry = _entry()
    entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(entry, options={c.CONF_ENABLE_THUNDERSTORM: True, c.CONF_ENABLE_MOON: True})
    registry = er.async_get(hass)
    old = registry.async_get_or_create(
        "sensor",
        c.DOMAIN,
        f"{entry.entry_id}_{c.KEY_FOG_PROBABILITY}",
        config_entry=entry,
        disabled_by=er.RegistryEntryDisabler.INTEGRATION,
        suggested_object_id="renamed_fog",
    )
    hidden = registry.async_get_or_create(
        "sensor",
        c.DOMAIN,
        f"{entry.entry_id}_{c.KEY_THUNDERSTORM_RISK}",
        config_entry=entry,
        disabled_by=er.RegistryEntryDisabler.USER,
    )
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(old.entity_id) is None
    await hass.services.async_call("switch", "turn_on", {"entity_id": "switch.ws_enable_fog"}, blocking=True)
    await hass.async_block_till_done()
    assert registry.async_get(old.entity_id).disabled_by is None
    assert hass.states.get(old.entity_id) is not None
    assert registry.async_get(hidden.entity_id).disabled_by is er.RegistryEntryDisabler.USER
    assert hass.states.get(hidden.entity_id) is None
    moon = registry.async_get_entity_id("sensor", c.DOMAIN, f"{entry.entry_id}_{c.KEY_MOON_ILLUMINATION_PCT}")
    assert moon is not None
    assert registry.async_get(moon).disabled_by is None
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_config_flow_starts(hass, enable_custom_integrations):
    result = await hass.config_entries.flow.async_init(c.DOMAIN, context={"source": "user"})
    assert result["type"] in (FlowResultType.FORM, FlowResultType.MENU)
    hass.config_entries.flow.async_abort(result["flow_id"])
