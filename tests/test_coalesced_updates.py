"""Tests for burst coalescing and update debounce in WSStationCoordinator (v3.0.0)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.ws_core.const import (
    COALESCE_BURST_DELAY_S,
    SRC_LIGHTNING_COUNT,
)
from tests.test_coordinator import _make_coordinator


class TestBurstCoalescing:
    """Verify that multi-sensor bursts are debounced into a single refresh."""

    def test_sync_call_without_event_flushes_immediately(self):
        coord = _make_coordinator()
        coord._compute = MagicMock(return_value={"test": 1})
        coord.async_set_updated_data = MagicMock()

        coord._handle_source_change(None)
        assert coord._debounce_handle is None
        coord._compute.assert_called_once_with(sample=False)
        coord.async_set_updated_data.assert_called_once_with({"test": 1})

    def test_source_change_with_event_schedules_debounce(self):
        coord = _make_coordinator()
        coord.hass = MagicMock()
        coord.hass.loop = MagicMock()
        coord._compute = MagicMock(return_value={})
        coord.async_set_updated_data = MagicMock()

        with patch("custom_components.ws_core.coordinator.async_call_later") as mock_call_later:
            timer_mock = MagicMock()
            mock_call_later.return_value = timer_mock

            event = MagicMock()
            event.data = {"entity_id": "sensor.station_temp"}

            # First update of a burst
            coord._handle_source_change(event)
            assert coord._debounce_handle is timer_mock
            mock_call_later.assert_called_once()
            args, _ = mock_call_later.call_args
            assert args[1] == COALESCE_BURST_DELAY_S

            # Second and third rapid updates in the same burst do not schedule new timers
            coord._handle_source_change(event)
            coord._handle_source_change(event)
            assert mock_call_later.call_count == 1

    def test_tick_cancels_pending_debounce_and_computes_sample(self):
        coord = _make_coordinator()
        timer_mock = MagicMock()
        coord._debounce_handle = timer_mock
        coord._compute = MagicMock(return_value={})
        coord.async_set_updated_data = MagicMock()

        coord._handle_tick(None)
        timer_mock.assert_called_once()
        assert coord._debounce_handle is None
        coord._compute.assert_called_once_with(sample=True)

    @pytest.mark.asyncio
    async def test_async_stop_cancels_pending_debounce(self):
        coord = _make_coordinator()
        timer_mock = MagicMock()
        coord._debounce_handle = timer_mock
        coord._async_save_history = AsyncMock()

        await coord.async_stop()
        timer_mock.assert_called_once()
        assert coord._debounce_handle is None

    def test_lightning_hazard_bypasses_debounce_immediately(self):
        coord = _make_coordinator()
        coord.hass = MagicMock()
        coord.hass.loop = MagicMock()
        coord.sources[SRC_LIGHTNING_COUNT] = "sensor.lightning_count"
        timer_mock = MagicMock()
        coord._debounce_handle = timer_mock
        coord._compute = MagicMock(return_value={"hazard": True})
        coord.async_set_updated_data = MagicMock()

        event = MagicMock()
        event.data = {"entity_id": "sensor.lightning_count"}

        coord._handle_source_change(event)
        # Previous debounce timer cancelled, and computed immediately without delay
        timer_mock.assert_called_once()
        assert coord._debounce_handle is None
        coord._compute.assert_called_once_with(sample=False)
        coord.async_set_updated_data.assert_called_once_with({"hazard": True})
