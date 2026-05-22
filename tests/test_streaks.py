"""Tests for dry/heat/frost streak counters (issue #15).

Covers two regressions:
  1. A rainy day must reset the dry streak (it was reading the freshly-reset
     current-day rain ~0 right after midnight, so it never saw the rain).
  2. The same calendar day must be counted exactly once, even across restarts
     (the once-per-day guard used to be in-memory and reset on reload).
"""

from __future__ import annotations

import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from custom_components.ws_core.const import (
    KEY_DRY_STREAK,
    KEY_TEMP_HIGH_24H,
    KEY_TEMP_LOW_24H,
)
from custom_components.ws_core.learning_state import LearningState, update_daily_streaks

# ---------------------------------------------------------------------------
# Pure function: update_daily_streaks
# ---------------------------------------------------------------------------


class TestUpdateDailyStreaks:
    def _state(self, **kw) -> LearningState:
        s = LearningState()
        for k, v in kw.items():
            setattr(s, k, v)
        return s

    def test_rain_resets_dry_streak(self):
        # The exact issue #15 scenario: 25-day streak, then a 12 mm day.
        s = self._state(dry_streak_days=25)
        update_daily_streaks(
            s, "2026-05-20", t_high=18.0, t_low=9.0, rain_today_mm=12.0, thresh_heat_c=30.0, thresh_freeze_c=0.0
        )
        assert s.dry_streak_days == 0
        assert s.dry_streak_last_rain_date == "2026-05-20"

    def test_dry_day_increments_by_one(self):
        s = self._state(dry_streak_days=5)
        update_daily_streaks(
            s, "2026-05-20", t_high=18.0, t_low=9.0, rain_today_mm=0.0, thresh_heat_c=30.0, thresh_freeze_c=0.0
        )
        assert s.dry_streak_days == 6

    def test_trace_rain_below_1mm_still_counts_as_dry(self):
        # < 1 mm is treated as a dry day (a "rain day" needs >= 1 mm).
        s = self._state(dry_streak_days=3)
        update_daily_streaks(
            s, "2026-05-20", t_high=18.0, t_low=9.0, rain_today_mm=0.4, thresh_heat_c=30.0, thresh_freeze_c=0.0
        )
        assert s.dry_streak_days == 4

    def test_one_mm_resets(self):
        s = self._state(dry_streak_days=10)
        update_daily_streaks(
            s, "2026-05-20", t_high=18.0, t_low=9.0, rain_today_mm=1.0, thresh_heat_c=30.0, thresh_freeze_c=0.0
        )
        assert s.dry_streak_days == 0


# ---------------------------------------------------------------------------
# Persistence: new guard field round-trips
# ---------------------------------------------------------------------------


class TestLearningStatePersistence:
    def test_streak_guard_field_roundtrips(self):
        s = LearningState()
        s.streak_last_counted_date = "2026-05-20"
        restored = LearningState.from_dict(s.to_dict())
        assert restored.streak_last_counted_date == "2026-05-20"

    def test_old_state_without_field_defaults_empty(self):
        # Simulate a pre-1.6.6 state file (no streak_last_counted_date key).
        data = LearningState().to_dict()
        data.pop("streak_last_counted_date", None)
        restored = LearningState.from_dict(data)
        assert restored.streak_last_counted_date == ""


# ---------------------------------------------------------------------------
# Coordinator-level: day-boundary + restart guard
# ---------------------------------------------------------------------------


def _streak_coord(prev_date: str, prev_rain: float, last_counted: str = "", dry_streak: int = 0) -> object:
    """Minimal coordinator instance for exercising _compute_streaks."""
    from custom_components.ws_core.coordinator import WSStationCoordinator

    with patch.object(WSStationCoordinator, "__init__", lambda self, *a, **kw: None):
        coord = WSStationCoordinator.__new__(WSStationCoordinator)
    coord._rain_prev_day_date = prev_date
    coord._rain_prev_day_mm = prev_rain
    coord.thresh_heat_day_c = 30.0
    coord.entry_options = {}
    coord._learning_state = LearningState()
    coord._learning_state.dry_streak_days = dry_streak
    coord._learning_state.streak_last_counted_date = last_counted
    return coord


class TestComputeStreaksDayBoundary:
    def test_completed_rainy_day_resets(self):
        coord = _streak_coord("2026-05-20", prev_rain=12.0, dry_streak=25)
        data = {KEY_TEMP_HIGH_24H: 18.0, KEY_TEMP_LOW_24H: 9.0}
        coord._compute_streaks(data, None)
        assert data[KEY_DRY_STREAK] == 0
        assert coord._learning_state.streak_last_counted_date == "2026-05-20"

    def test_completed_dry_day_increments(self):
        coord = _streak_coord("2026-05-20", prev_rain=0.0, dry_streak=5)
        data = {KEY_TEMP_HIGH_24H: 18.0, KEY_TEMP_LOW_24H: 9.0}
        coord._compute_streaks(data, None)
        assert data[KEY_DRY_STREAK] == 6

    def test_same_day_not_double_counted_on_restart(self):
        # First run counts the completed day.
        coord = _streak_coord("2026-05-20", prev_rain=0.0, dry_streak=5)
        data = {KEY_TEMP_HIGH_24H: 18.0, KEY_TEMP_LOW_24H: 9.0}
        coord._compute_streaks(data, None)
        assert data[KEY_DRY_STREAK] == 6
        # Second run for the SAME completed day (e.g. after a restart) must not
        # increment again - the guard is persisted in LearningState.
        coord._compute_streaks(data, None)
        assert data[KEY_DRY_STREAK] == 6

    def test_no_prev_day_does_nothing(self):
        # Fresh install: no completed day captured yet.
        coord = _streak_coord("", prev_rain=0.0, dry_streak=0)
        data = {KEY_TEMP_HIGH_24H: 18.0, KEY_TEMP_LOW_24H: 9.0}
        coord._compute_streaks(data, None)
        assert data[KEY_DRY_STREAK] == 0
        assert coord._learning_state.streak_last_counted_date == ""
