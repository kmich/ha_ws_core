"""Tests for the gust record plausibility gate and the startup repair from recorder statistics."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.util import dt as dt_util

from custom_components.ws_core import history_backfill
from custom_components.ws_core.algorithms import gust_is_plausible
from custom_components.ws_core.const import (
    GUST_PLAUSIBLE_FACTOR,
    GUST_PLAUSIBLE_MARGIN_MS,
    KEY_WIND_GUST_MAX_ALL_TIME,
    KEY_WIND_GUST_MAX_MONTH,
    KEY_WIND_GUST_MAX_YEAR,
    SRC_RAIN_YEAR,
)
from custom_components.ws_core.history_backfill import (
    apply_rain,
    async_backfill_from_statistics,
    first_hour,
    hourly_series,
    period_starts,
    rain_deltas,
)

from .test_coordinator import _make_coordinator

# The hourly statistics of the WS90 gust glitch seen on a live station:
# (gust max, wind mean) in m/s, gust stuck near 40 m/s in a light breeze.
GLITCH_HOURS = [(38.6, 4.8), (38.6, 1.3), (39.4, 4.1), (39.4, 5.5), (39.8, 2.1), (40.0, 2.9), (32.8, 1.2)]


def _plausible(gust, wind):
    return gust_is_plausible(gust, wind, GUST_PLAUSIBLE_FACTOR, GUST_PLAUSIBLE_MARGIN_MS)


class TestGustIsPlausible:
    def test_glitch_is_implausible(self):
        assert not _plausible(40.0, 3.0)

    def test_storm_gusts_are_plausible(self):
        assert _plausible(30.0, 12.0)
        assert _plausible(12.0, 1.0)  # light, turbulent wind: margin covers a high gust factor

    def test_unknown_wind_gives_benefit_of_doubt(self):
        assert _plausible(40.0, None)


class TestLiveGustGate:
    def test_implausible_gust_sets_no_record(self):
        coord = _make_coordinator()
        data = {}
        coord._update_gust_month_year_all_time(data, 12.0, 6.0)
        data = {}
        coord._update_gust_month_year_all_time(data, 40.0, 3.0)
        assert coord._gust_max_all_time == 12.0
        assert coord._gust_max_year == 12.0
        assert coord._gust_max_month == 12.0
        # The records are still published while the glitch lasts
        assert data[KEY_WIND_GUST_MAX_ALL_TIME] == 12.0
        assert data[KEY_WIND_GUST_MAX_YEAR] == 12.0
        assert data[KEY_WIND_GUST_MAX_MONTH] == 12.0

    def test_implausible_gust_on_new_month_does_not_publish_last_month(self):
        coord = _make_coordinator()
        coord._gust_max_month = 20.0
        coord._gust_month_key = "2020-01"
        coord._gust_max_all_time = 25.0
        data = {}
        coord._update_gust_month_year_all_time(data, 40.0, 3.0)
        assert KEY_WIND_GUST_MAX_MONTH not in data
        assert data[KEY_WIND_GUST_MAX_ALL_TIME] == 25.0

    def test_plausible_gust_sets_record(self):
        coord = _make_coordinator()
        data = {}
        coord._update_gust_month_year_all_time(data, 28.0, 11.0)
        assert data[KEY_WIND_GUST_MAX_ALL_TIME] == 28.0

    def test_compute_passes_wind_to_gate(self):
        coord = _make_coordinator(wind_speed=3.0, wind_gust=40.0)
        coord._gust_max_all_time = 15.0
        coord._compute_derived_wind({}, dt_util.utcnow(), 3.0, 40.0, None)
        assert coord._gust_max_all_time == 15.0


class TestPeriodStarts:
    def test_keys_and_starts(self):
        now = dt_util.as_local(datetime(2026, 11, 3, 15, 30, tzinfo=dt_util.UTC))
        p = period_starts(now)
        assert p["week"][0] == now.strftime("%G-W%V")
        assert p["month"][0] == "2026-11"
        assert p["year"][0] == "2026"
        week = dt_util.as_local(dt_util.utc_from_timestamp(p["week"][1]))
        month = dt_util.as_local(dt_util.utc_from_timestamp(p["month"][1]))
        year = dt_util.as_local(dt_util.utc_from_timestamp(p["year"][1]))
        assert (week.weekday(), week.hour, week.minute) == (0, 0, 0)
        assert week <= now < week + timedelta(days=7)
        assert (month.month, month.day, month.hour) == (11, 1, 0)
        assert (year.month, year.day, year.hour) == (1, 1, 0)

    def test_first_hour(self):
        assert first_hour(0.0, 7200.0) == 2
        assert first_hour(0.0, 7000.0) == 2  # a straddling hour is left out
        assert first_hour(7200.0, 0.0) == 0


class TestHourlySeries:
    def test_indexes_by_hour_and_skips_bad_values(self):
        rows = [
            {"start": 3600.0, "max": 2.0},
            {"start": datetime.fromtimestamp(7200.0, dt_util.UTC), "max": 3.0},
            {"start": 10800.0, "max": None},
            {"start": 99999999.0, "max": 9.0},
        ]
        assert hourly_series(rows, 0.0, 4, "max") == [None, 2.0, 3.0, None]


class TestRainDeltas:
    def test_rises_resets_and_jumps(self):
        assert rain_deltas([10.0, 10.5, 2.0, 2.5, 500.0]) == [None, 0.5, 0.0, 0.5, None]

    def test_bridges_gaps(self):
        # Home Assistant was down for two hours while 3 mm fell: still counted
        assert rain_deltas([10.0, None, None, 13.0]) == [None, None, None, 3.0]


def _ts(dt: datetime) -> float:
    return dt.timestamp()


class TestApplyRain:
    def _setup(self, live_year=130.6):
        coord = _make_coordinator()
        now = dt_util.as_local(datetime(2026, 11, 3, 15, 30, tzinfo=dt_util.UTC))
        periods = period_starts(now)
        start_ts = periods["year"][1] - 3600.0
        n = int((_ts(now) - start_ts) // 3600)
        # Counter: 98 mm on Jan 1, 0.1 mm every 4 h, live reading 3 mm above the last hour
        counter = [98.0 + 0.025 * i for i in range(n)]
        rows = {"sensor.rain": [{"start": start_ts + i * 3600.0, "max": v} for i, v in enumerate(counter)]}
        meta = {
            "sensor.rain": {"statistic_id": "sensor.rain", "statistics_unit_of_measurement": "mm", "has_sum": False}
        }
        coord._rain_this_year_key, coord._rain_this_year_mm = periods["year"][0], live_year
        coord._rain_this_month_key, coord._rain_this_month_mm = periods["month"][0], 50.0
        coord._rain_this_week_isoweek, coord._rain_this_week_mm = periods["week"][0], 0.2
        last = counter[-1] + 3.0
        coord._rain_this_year_last_total = coord._rain_this_month_last_total = last
        coord._rain_this_week_last_total = last
        return coord, meta, rows, start_ts, n, periods, counter

    def test_year_total_is_filled_in(self):
        coord, meta, rows, start_ts, n, periods, counter = self._setup()
        changes = apply_rain(coord, meta, rows, start_ts, n, periods)
        expected = counter[-1] - counter[0] + 3.0
        assert abs(coord._rain_this_year_mm - expected) < 0.01
        assert any("year" in c for c in changes)

    def test_totals_are_never_lowered(self):
        coord, meta, rows, start_ts, n, periods, _ = self._setup()
        apply_rain(coord, meta, rows, start_ts, n, periods)
        assert coord._rain_this_month_mm == 50.0  # statistics show less than the live total

    def test_week_total_is_filled_in(self):
        coord, meta, rows, start_ts, n, periods, counter = self._setup()
        apply_rain(coord, meta, rows, start_ts, n, periods)
        first = first_hour(start_ts, periods["week"][1])
        assert abs(coord._rain_this_week_mm - (counter[-1] - counter[first - 1] + 3.0)) < 0.01

    def test_station_year_counter_wins(self):
        coord, meta, rows, start_ts, n, periods, _ = self._setup()
        coord.sources[SRC_RAIN_YEAR] = "sensor.rain_year"
        apply_rain(coord, meta, rows, start_ts, n, periods)
        assert coord._rain_this_year_mm == 130.6

    def test_rolled_over_period_is_left_alone(self):
        coord, meta, rows, start_ts, n, periods, _ = self._setup()
        coord._rain_this_year_key = "2025"
        apply_rain(coord, meta, rows, start_ts, n, periods)
        assert coord._rain_this_year_mm == 130.6

    def test_inches_are_converted(self):
        coord, meta, rows, start_ts, n, periods, counter = self._setup()
        meta["sensor.rain"]["statistics_unit_of_measurement"] = "in"
        for r in rows["sensor.rain"]:
            r["max"] /= 25.4
        apply_rain(coord, meta, rows, start_ts, n, periods)
        assert abs(coord._rain_this_year_mm - (counter[-1] - counter[0] + 3.0)) < 0.01


class FakeRecorder:
    async def async_add_executor_job(self, fn, *args):
        return fn(*args)


class TestAsyncBackfill:
    def test_reads_applies_and_saves_without_changing_gust_records(self):
        coord, meta, rows, start_ts, n, periods, _ = TestApplyRain()._setup()
        coord.hass.config.components = {"recorder"}
        coord._history_store = MagicMock(async_save=AsyncMock())
        coord._dump_history_state = MagicMock(return_value={})
        coord._gust_max_all_time = 30.0
        coord._gust_max_year = 25.0
        coord._gust_max_month = 20.0
        read = MagicMock(return_value=(meta, rows))
        now = dt_util.utc_from_timestamp(start_ts + n * 3600.0 + 600.0)
        with (
            patch.object(history_backfill.dt_util, "utcnow", return_value=now),
            patch.object(history_backfill, "_recorder_instance", return_value=FakeRecorder()),
            patch.object(history_backfill, "read_statistics", read),
        ):
            asyncio.run(async_backfill_from_statistics(coord))
        assert read.call_args.args[1] == {"sensor.rain"}
        assert coord._rain_this_year_mm > 130.6
        assert (coord._gust_max_all_time, coord._gust_max_year, coord._gust_max_month) == (30.0, 25.0, 20.0)
        coord._history_store.async_save.assert_awaited_once()

    def test_without_recorder_does_nothing(self):
        coord = _make_coordinator()
        coord.hass.config.components = set()
        with patch.object(history_backfill, "_recorder_instance") as rec:
            asyncio.run(async_backfill_from_statistics(coord))
        rec.assert_not_called()

    def test_recorder_error_is_swallowed(self):
        coord = _make_coordinator()
        coord.hass.config.components = {"recorder"}
        with patch.object(history_backfill, "_recorder_instance", side_effect=KeyError("recorder")):
            asyncio.run(async_backfill_from_statistics(coord))
