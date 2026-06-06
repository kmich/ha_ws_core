"""Tests for rolling-window history + accumulator persistence (issue #16).

Verifies that _dump_history_state / _restore_history_state round-trip the 24h
deques and daily accumulators, that 24h windows are pruned on restore, and that
daily accumulators only continue when the saved date is still today.
"""

from __future__ import annotations

import os
import sys
from collections import deque
from datetime import timedelta
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from homeassistant.util import dt as dt_util


def _coord():
    """Minimal coordinator instance with the fields the history methods touch."""
    from custom_components.ws_core.coordinator import WSStationCoordinator, WSStationRuntime

    with patch.object(WSStationCoordinator, "__init__", lambda self, *a, **kw: None):
        c = WSStationCoordinator.__new__(WSStationCoordinator)
    c.runtime = WSStationRuntime()
    # accumulator fields
    c._rain_today_mm = 0.0
    c._rain_today_date = ""
    c._rain_today_last_total = None
    c._rain_prev_day_mm = 0.0
    c._rain_prev_day_date = ""
    c._wind_run_km = 0.0
    c._wind_run_date = ""
    c._chill_hours_today = 0.0
    c._chill_hours_today_date = ""
    c._chill_hours_season = 0.0
    c._chill_hours_season_date = ""
    # v2.0 accumulators persisted by _dump_history_state
    c._wind_run_month_km = 0.0
    c._wind_run_month_key = ""
    c._rain_this_week_mm = 0.0
    c._rain_this_week_isoweek = ""
    c._rain_this_week_last_total = None
    c._rain_this_month_mm = 0.0
    c._rain_this_month_key = ""
    c._rain_this_month_last_total = None
    c._rain_this_year_mm = 0.0
    c._rain_this_year_key = ""
    c._rain_this_year_last_total = None
    c._hdd_today = 0.0
    c._hdd_today_date = ""
    c._hdd_today_samples = 0
    c._cdd_today = 0.0
    c._cdd_today_date = ""
    c._cdd_today_samples = 0
    c._gdd_today = 0.0
    c._gdd_today_date = ""
    c._hdd_season = 0.0
    c._hdd_season_key = ""
    c._cdd_season = 0.0
    c._cdd_season_key = ""
    c._gdd_season = 0.0
    c._gdd_season_key = ""
    c._solar_energy_today_whm2 = 0.0
    c._solar_energy_date = ""
    return c


class TestHistoryRoundTrip:
    def test_deques_and_accumulators_roundtrip(self):
        src = _coord()
        now = dt_util.utcnow()
        today = dt_util.now().strftime("%Y-%m-%d")
        for i in range(3):
            ts = now - timedelta(minutes=10 * i)
            src.runtime.temp_history_24h.append((ts, 20.0 + i))
            src.runtime.gust_history_24h.append((ts, 5.0 + i))
            src.runtime.rain_total_history_24h.append((ts, 100.0 + i))
        src.runtime.pressure_history.extend([1010.0, 1011.0, 1012.0])
        src.runtime.pressure_history_ts = now
        src._rain_today_mm = 12.5
        src._rain_today_date = today
        src._rain_today_last_total = 137.0
        src._wind_run_km = 42.0
        src._wind_run_date = today
        src._chill_hours_today = 3.5
        src._chill_hours_today_date = today
        src._chill_hours_season = 120.0
        src._chill_hours_season_date = today

        blob = src._dump_history_state()

        dst = _coord()
        dst._restore_history_state(blob)

        assert len(dst.runtime.temp_history_24h) == 3
        assert [round(v, 1) for _, v in dst.runtime.temp_history_24h] == [20.0, 21.0, 22.0]
        assert list(dst.runtime.pressure_history) == [1010.0, 1011.0, 1012.0]
        assert dst._rain_today_mm == 12.5
        assert dst._rain_today_last_total == 137.0
        assert dst._wind_run_km == 42.0
        assert dst._chill_hours_today == 3.5
        assert dst._chill_hours_season == 120.0

    def test_old_24h_entries_pruned_on_restore(self):
        src = _coord()
        now = dt_util.utcnow()
        # one fresh, one 30h old (outside the 24h window)
        src.runtime.temp_history_24h.append((now - timedelta(hours=30), 10.0))
        src.runtime.temp_history_24h.append((now - timedelta(hours=1), 21.0))
        blob = src._dump_history_state()

        dst = _coord()
        dst._restore_history_state(blob)
        temps = [v for _, v in dst.runtime.temp_history_24h]
        assert temps == [21.0]  # the 30h-old sample was pruned

    def test_accumulator_not_restored_on_new_day(self):
        src = _coord()
        # saved under yesterday's date
        yesterday = (dt_util.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        src._rain_today_mm = 9.9
        src._rain_today_date = yesterday
        src._wind_run_km = 50.0
        src._wind_run_date = yesterday
        blob = src._dump_history_state()

        dst = _coord()
        dst._restore_history_state(blob)
        # New day -> daily accumulators must NOT carry over yesterday's totals.
        assert dst._rain_today_mm == 0.0
        assert dst._rain_today_date == ""
        assert dst._wind_run_km == 0.0

    def test_empty_blob_is_safe(self):
        dst = _coord()
        dst._restore_history_state({})
        dst._restore_history_state(None)
        assert dst._rain_today_mm == 0.0
        assert len(dst.runtime.temp_history_24h) == 0

    def test_corrupt_entries_skipped(self):
        dst = _coord()
        blob = {
            "temp_history_24h": [["not-a-date", 1.0], [dt_util.utcnow().isoformat(), 22.0], ["x"]],
            "pressure_history": ["bad", 1009.0],
        }
        dst._restore_history_state(blob)
        assert [v for _, v in dst.runtime.temp_history_24h] == [22.0]
        assert list(dst.runtime.pressure_history) == [1009.0]

    def test_season_chill_persists_across_days(self):
        src = _coord()
        yesterday = (dt_util.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        src._chill_hours_season = 200.0
        src._chill_hours_season_date = yesterday
        blob = src._dump_history_state()

        dst = _coord()
        dst._restore_history_state(blob)
        # Season total carries across days (its own reset logic handles rollover).
        assert dst._chill_hours_season == 200.0
        assert dst._chill_hours_season_date == yesterday
