"""Coordinators live on entry.runtime_data."""

from unittest.mock import MagicMock

from homeassistant.config_entries import ConfigEntryState

from custom_components.ws_core import _loaded_coordinators
from custom_components.ws_core.config_flow import _guess_defaults
from custom_components.ws_core.const import CONF_PREFIX, SRC_TEMP


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
