"""Coordinators live on entry.runtime_data."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.config_entries import ConfigEntryState

from custom_components.ws_core import _loaded_coordinators, async_unload_entry
from custom_components.ws_core.config_flow import _guess_defaults
from custom_components.ws_core.const import CONF_PREFIX, DOMAIN, SRC_TEMP


def _entry(entry_id: str, state: ConfigEntryState, prefix: str = "ws"):
    entry = MagicMock()
    entry.entry_id = entry_id
    entry.state = state
    entry.runtime_data = f"coord-{entry_id}"
    entry.data = {CONF_PREFIX: prefix}
    entry.options = {}
    return entry


def test_services_target_only_loaded_entries():
    hass = MagicMock()
    hass.config_entries.async_entries.return_value = [
        _entry("a", ConfigEntryState.LOADED),
        _entry("b", ConfigEntryState.NOT_LOADED),
        _entry("c", ConfigEntryState.LOADED),
    ]
    assert _loaded_coordinators(hass) == ["coord-a", "coord-c"]
    assert _loaded_coordinators(hass, "c") == ["coord-c"]
    assert _loaded_coordinators(hass, "b") == []


def test_guess_defaults_skips_own_sensors_with_custom_prefix():
    hass = MagicMock()
    hass.config_entries.async_entries.return_value = [_entry("a", ConfigEntryState.LOADED, prefix="garden")]
    states = []
    for eid in ("sensor.garden_temperature", "sensor.station_outdoor_temperature"):
        st = MagicMock()
        st.entity_id = eid
        states.append(st)
    hass.states.async_all.return_value = states
    assert _guess_defaults(hass)[SRC_TEMP] == "sensor.station_outdoor_temperature"


@pytest.mark.asyncio
async def test_unload_failure_does_not_stop_coordinator_or_remove_services():
    hass = MagicMock()
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=False)
    hass.config_entries.async_loaded_entries.return_value = []
    hass.services.has_service.return_value = True
    entry = MagicMock()
    entry.entry_id = "test_unload_fail"
    entry.runtime_data = MagicMock()
    entry.runtime_data.async_stop = AsyncMock()

    result = await async_unload_entry(hass, entry)

    assert result is False
    entry.runtime_data.async_stop.assert_not_awaited()
    hass.services.async_remove.assert_not_called()

    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
    result_ok = await async_unload_entry(hass, entry)

    assert result_ok is True
    entry.runtime_data.async_stop.assert_awaited_once()
    assert hass.services.async_remove.call_count == 4
    removed = {c.args for c in hass.services.async_remove.call_args_list}
    assert all(dom == DOMAIN for dom, _ in removed)
