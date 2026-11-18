"""Tests for burst coalescing and update debounce in WSStationCoordinator (v3.0.0)."""

from __future__ import annotations

from typing import Any
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

    def test_v3_burst_coalescing_and_weather_windows_performance_gate(self):
        """Replay 25x12-sensor bursts with Weather Windows ON: assert 1 write/burst & <10% burst budget."""
        import statistics
        import time
        from datetime import UTC, datetime, timedelta

        from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

        from custom_components.ws_core.const import (
            CONF_ENABLE_WEATHER_WINDOWS,
            CONF_FORECAST_ENABLED,
            CONF_FORECAST_LAT,
            CONF_FORECAST_LON,
            KEY_WEATHER_WINDOWS,
            SRC_DEW_POINT,
            SRC_GUST,
            SRC_HUM,
            SRC_LUX,
            SRC_PRESS,
            SRC_RAIN_TOTAL,
            SRC_RAIN_YEAR,
            SRC_SOLAR_RADIATION,
            SRC_TEMP,
            SRC_UV,
            SRC_WIND,
            SRC_WIND_DIR,
        )
        from custom_components.ws_core.coordinator import WSStationCoordinator
        from tests.test_coordinator import _make_state

        now = datetime(2026, 6, 21, 11, 0, tzinfo=UTC)
        sources = {
            SRC_TEMP: "sensor.temp",
            SRC_HUM: "sensor.hum",
            SRC_PRESS: "sensor.press",
            SRC_WIND: "sensor.wind",
            SRC_GUST: "sensor.gust",
            SRC_WIND_DIR: "sensor.wind_dir",
            SRC_RAIN_TOTAL: "sensor.rain",
            SRC_RAIN_YEAR: "sensor.rain_y",
            SRC_LUX: "sensor.lux",
            SRC_UV: "sensor.uv",
            SRC_DEW_POINT: "sensor.dew",
            SRC_SOLAR_RADIATION: "sensor.solar",
        }
        states = {eid: _make_state("20.0", "", now) for eid in sources.values()}
        states["sun.sun"] = MagicMock(state="above_horizon", attributes={"elevation": 45, "azimuth": 180})
        hass = MagicMock()
        hass.config.latitude = 37.9
        hass.config.longitude = 23.7
        hass.states.get = lambda eid: states.get(eid)

        with patch.object(DataUpdateCoordinator, "__init__", lambda self, *a, **kw: None):
            coord = WSStationCoordinator(
                hass,
                {
                    "entry_id": "bench_gate",
                    "sources": sources,
                    CONF_FORECAST_ENABLED: True,
                    CONF_ENABLE_WEATHER_WINDOWS: True,
                    CONF_FORECAST_LAT: 37.9,
                    CONF_FORECAST_LON: 23.7,
                },
                {},
            )

        coord.data = {}
        state_writes = 0

        def _record_write(data):
            nonlocal state_writes
            coord.data = data
            state_writes += 1

        coord.async_set_updated_data = _record_write  # type: ignore[method-assign]

        scheduled: list = []

        def _fake_call_later(_hass, _delay, cb):
            scheduled.append(cb)
            return MagicMock()

        def _make_fresh_forecast(fetch_time: datetime) -> dict[str, Any]:
            return {
                "provider": "open_meteo",
                "daily": [
                    {
                        "date": fetch_time.strftime("%Y-%m-%d"),
                        "tmax_c": 28.0,
                        "tmin_c": 18.0,
                        "precip_prob": 10,
                    }
                ],
                "hourly": [
                    {
                        "datetime": (fetch_time + timedelta(hours=h)).isoformat(),
                        "temp_c": 22.0 + (h % 5) * 0.2,
                        "apparent_temp_c": 22.0,
                        "dewpoint_c": 12.0,
                        "precip_prob": 5,
                        "precip_mm": 0.0,
                        "wind_kmh": 12.0,
                        "gust_kmh": 18.0,
                        "humidity": 50.0,
                        "cloud_cover": 20.0,
                    }
                    for h in range(25)
                ],
            }

        burst_ms: list[float] = []
        source_events = [MagicMock(data={"entity_id": eid}) for eid in sources.values()]
        current_now = [now]
        with (
            patch("custom_components.ws_core.coordinator.async_call_later", side_effect=_fake_call_later),
            patch("custom_components.ws_core.coordinator.dt_util.utcnow", side_effect=lambda: current_now[0]),
            patch("custom_components.ws_core.coordinator.dt_util.now", side_effect=lambda: current_now[0]),
            patch.object(coord, "_get_cached_or_schedule_forecast", side_effect=lambda t: coord._forecast_cache),
        ):
            for i in range(25):
                burst_now = now + timedelta(minutes=i * 15)
                current_now[0] = burst_now
                coord.runtime.last_forecast_fetch = burst_now
                coord._forecast_cache = _make_fresh_forecast(burst_now)
                scheduled.clear()
                t0 = time.perf_counter()
                for ev in source_events:
                    coord._handle_source_change(ev)
                assert len(scheduled) == 1
                scheduled[0](burst_now)
                burst_ms.append((time.perf_counter() - t0) * 1000.0)

        assert state_writes == 25  # 1 write per 12-sensor burst (vs 12 baseline)
        assert KEY_WEATHER_WINDOWS in coord.data
        ww_eval = coord.data[KEY_WEATHER_WINDOWS]
        assert "outdoor_drying" in ww_eval
        # Verify that all 24 hourly forecast slots were actually evaluated for the profiles
        assert len(ww_eval["outdoor_drying"]["slots"]) == 24
        assert len(ww_eval["garden_work"]["slots"]) == 24
        burst_sorted = sorted(burst_ms)
        p95_burst_ms = burst_sorted[int(0.95 * len(burst_sorted)) - 1]
        assert statistics.median(burst_sorted) > 0.0
        # M0 baseline was 9.672 ms p95 per 12-sensor burst (+10% gate = 10.639 ms)
        assert p95_burst_ms <= 10.639
