"""Real config entry setup, options flow and unload (v3.0.0).

The minimum-version CI job runs this file against the oldest supported Home Assistant,
so a newer-only API in setup, the coordinator constructor or the flows fails there.
"""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntryState
from homeassistant.data_entry_flow import FlowResultType

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
    entry = _entry()
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get("sensor.ws_data_status") is not None

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


async def test_config_flow_starts(hass, enable_custom_integrations):
    result = await hass.config_entries.flow.async_init(c.DOMAIN, context={"source": "user"})
    assert result["type"] in (FlowResultType.FORM, FlowResultType.MENU)
    hass.config_entries.flow.async_abort(result["flow_id"])
