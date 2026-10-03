"""Unit tests for the ws_core select platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.ws_core.const import CONF_PREFIX, DOMAIN
from custom_components.ws_core.select import (
    GRAPH_RANGE_DEFAULT,
    GRAPH_RANGE_OPTIONS,
    WSGraphRangeSelect,
    async_setup_entry,
)


@pytest.fixture
def mock_config_entry():
    entry = MagicMock()
    entry.entry_id = "test_entry_select"
    entry.data = {CONF_PREFIX: "ws"}
    entry.options = {}
    return entry


async def test_async_setup_entry_creates_select(mock_config_entry):
    hass = MagicMock()
    added_entities = []

    def mock_add_entities(entities):
        added_entities.extend(entities)

    await async_setup_entry(hass, mock_config_entry, mock_add_entities)

    assert len(added_entities) == 1
    assert isinstance(added_entities[0], WSGraphRangeSelect)
    assert added_entities[0].entity_id == "select.ws_graph_range"
    assert added_entities[0].unique_id == "test_entry_select_graph_range"


def test_select_entity_properties(mock_config_entry):
    entity = WSGraphRangeSelect(mock_config_entry, "ws")

    assert entity.options == GRAPH_RANGE_OPTIONS
    assert entity.current_option == GRAPH_RANGE_DEFAULT
    assert entity.icon == "mdi:chart-timeline-variant"
    assert entity.device_info == {"identifiers": {(DOMAIN, "test_entry_select")}}


async def test_select_option_updates_state(mock_config_entry):
    entity = WSGraphRangeSelect(mock_config_entry, "ws")
    entity.async_write_ha_state = MagicMock()

    await entity.async_select_option("3d")
    assert entity.current_option == "3d"
    entity.async_write_ha_state.assert_called_once()


async def test_select_restores_valid_state(mock_config_entry):
    entity = WSGraphRangeSelect(mock_config_entry, "ws")

    last_state = MagicMock()
    last_state.state = "6h"

    with patch.object(WSGraphRangeSelect, "async_get_last_state", AsyncMock(return_value=last_state)):
        await entity.async_added_to_hass()

    assert entity.current_option == "6h"


async def test_select_ignores_invalid_restored_state(mock_config_entry):
    entity = WSGraphRangeSelect(mock_config_entry, "ws")

    last_state = MagicMock()
    last_state.state = "invalid_range"

    with patch.object(WSGraphRangeSelect, "async_get_last_state", AsyncMock(return_value=last_state)):
        await entity.async_added_to_hass()

    assert entity.current_option == GRAPH_RANGE_DEFAULT
