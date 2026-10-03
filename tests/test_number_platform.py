"""Unit tests for the ws_core number platform."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from homeassistant.components.number import NumberMode
from homeassistant.helpers.entity import EntityCategory

from custom_components.ws_core.const import (
    CONF_CAL_TEMP_C,
    CONF_PREFIX,
    CONF_THRESH_WIND_GUST_MS,
    DEFAULT_CAL_TEMP_C,
    DOMAIN,
)
from custom_components.ws_core.number import PARAM_NUMBERS, WSConfigNumber, async_setup_entry


@pytest.fixture
def mock_config_entry():
    entry = MagicMock()
    entry.entry_id = "test_entry_123"
    entry.data = {CONF_PREFIX: "ws"}
    entry.options = {}
    return entry


async def test_async_setup_entry_creates_all_numbers(mock_config_entry):
    hass = MagicMock()
    added_entities = []

    def mock_add_entities(entities):
        added_entities.extend(entities)

    await async_setup_entry(hass, mock_config_entry, mock_add_entities)

    assert len(added_entities) == len(PARAM_NUMBERS)
    keys = {e._desc.key for e in added_entities}
    assert "thresh_wind_gust" in keys
    assert "thresh_rain_rate" in keys
    assert "cal_temp" in keys
    assert "cal_humidity" in keys
    assert "cal_pressure" in keys


def test_number_entity_properties(mock_config_entry):
    desc = next(d for d in PARAM_NUMBERS if d.key == "thresh_wind_gust")
    entity = WSConfigNumber(mock_config_entry, "ws", desc)

    assert entity.entity_id == "number.ws_thresh_wind_gust"
    assert entity.unique_id == "test_entry_123_thresh_wind_gust"
    assert entity.entity_category == EntityCategory.CONFIG
    assert entity.icon == "mdi:weather-windy"
    assert entity.native_min_value == 0.0
    assert entity.native_max_value == 120.0
    assert entity.native_step == 0.1
    assert entity.native_unit_of_measurement == "m/s"
    assert entity.mode == NumberMode.BOX
    assert entity.device_info == {"identifiers": {(DOMAIN, "test_entry_123")}}


def test_number_native_value_fallback(mock_config_entry):
    desc = next(d for d in PARAM_NUMBERS if d.key == "cal_temp")
    entity = WSConfigNumber(mock_config_entry, "ws", desc)

    # 1. Fallback to default
    assert entity.native_value == DEFAULT_CAL_TEMP_C

    # 2. Read from entry.data
    mock_config_entry.data[CONF_CAL_TEMP_C] = 1.5
    assert entity.native_value == 1.5

    # 3. Read from entry.options (overrides data)
    mock_config_entry.options[CONF_CAL_TEMP_C] = -2.0
    assert entity.native_value == -2.0


async def test_number_set_native_value(mock_config_entry):
    hass = MagicMock()
    desc = next(d for d in PARAM_NUMBERS if d.key == "thresh_wind_gust")
    entity = WSConfigNumber(mock_config_entry, "ws", desc)
    entity.hass = hass

    await entity.async_set_native_value(35.5)

    hass.config_entries.async_update_entry.assert_called_once_with(
        mock_config_entry,
        options={CONF_THRESH_WIND_GUST_MS: 35.5},
    )
