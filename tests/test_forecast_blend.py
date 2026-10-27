"""Tests for the adaptive rain blend's outcome scoring.

The provider side used to be scored with its daily precipitation probability
against a 6-hour window, so the two sources weren't answering the same
question. It is now the highest hourly probability over the same 6 hours, with
the daily value as a fallback, and stored windows from before the change keep
counting until enough new ones exist.
"""

from __future__ import annotations

import os
import sys
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from homeassistant.util import dt as dt_util

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from custom_components.ws_core.const import KEY_RAIN_PROBABILITY, KEY_RAIN_RATE_FILT
from custom_components.ws_core.coordinator import WSStationCoordinator
from custom_components.ws_core.learning_state import (
    API_BASIS_DAILY,
    API_BASIS_HOURLY,
    LearningState,
    api_rain_prob_for_window,
    brier_score,
    compute_blend_weights,
    record_forecast_outcome,
    scoring_outcomes,
)

NOW_HOUR = "2026-10-27T09"


def _hourly(start_hour: int, probs: list) -> list[dict]:
    return [{"datetime": f"2026-10-27T{start_hour + i:02d}:00", "precip_prob": p} for i, p in enumerate(probs)]


def _outcome(local: float, api: float, rained: int, basis: str | None) -> dict:
    return {
        "ts": datetime.now(UTC).isoformat(),
        "outcome": rained,
        "local_prob": local,
        "openmeteo_prob": api,
        "api_basis": basis,
    }


# ---------------------------------------------------------------------------
# api_rain_prob_for_window
# ---------------------------------------------------------------------------


class TestApiRainProbForWindow:
    def test_takes_highest_hourly_chance_over_next_six_hours(self):
        fc = {"hourly": _hourly(9, [10, 20, 70, 30, 0, 5, 95]), "daily": [{"precip_prob": 90}]}
        # The 95 % at hour 7 is outside the window; the daily 90 % is not used.
        assert api_rain_prob_for_window(fc, NOW_HOUR) == (70.0, API_BASIS_HOURLY)

    def test_skips_hours_before_now(self):
        fc = {"hourly": _hourly(7, [100, 100, 10, 10, 10, 10, 10, 10])}
        assert api_rain_prob_for_window(fc, NOW_HOUR) == (10.0, API_BASIS_HOURLY)

    def test_does_not_combine_hours_as_independent_events(self):
        # 1 - 0.7**6 would be 88 %; correlated hours stay at the hourly maximum.
        fc = {"hourly": _hourly(9, [30, 30, 30, 30, 30, 30])}
        assert api_rain_prob_for_window(fc, NOW_HOUR) == (30.0, API_BASIS_HOURLY)

    def test_falls_back_to_daily_without_hourly_probabilities(self):
        # Met.no and similar providers give no hourly probability.
        fc = {"hourly": _hourly(9, [None] * 6), "daily": [{"precip_prob": 40}]}
        assert api_rain_prob_for_window(fc, NOW_HOUR) == (40.0, API_BASIS_DAILY)

    def test_falls_back_when_fewer_than_half_the_hours_have_a_value(self):
        fc = {"hourly": _hourly(9, [80, 80, None, None, None, None]), "daily": [{"precip_prob": 40}]}
        assert api_rain_prob_for_window(fc, NOW_HOUR) == (40.0, API_BASIS_DAILY)

    def test_half_the_hours_is_enough(self):
        fc = {"hourly": _hourly(9, [80, None, 20, None, 10, None])}
        assert api_rain_prob_for_window(fc, NOW_HOUR) == (80.0, API_BASIS_HOURLY)

    @pytest.mark.parametrize("fc", [None, {}, {"hourly": [], "daily": []}, {"daily": [{"precip_prob": None}]}])
    def test_no_forecast_gives_nothing(self, fc):
        assert api_rain_prob_for_window(fc, NOW_HOUR) == (None, None)


# ---------------------------------------------------------------------------
# scoring_outcomes and blend weights
# ---------------------------------------------------------------------------


class TestScoringOutcomes:
    def test_old_windows_count_until_enough_hourly_ones_exist(self):
        old = [_outcome(50, 50, 0, None) for _ in range(20)]
        new = [_outcome(50, 50, 0, API_BASIS_HOURLY) for _ in range(9)]
        assert scoring_outcomes(old + new) == old + new

    def test_only_hourly_windows_once_there_are_ten(self):
        old = [_outcome(50, 50, 0, None) for _ in range(20)]
        daily = [_outcome(50, 50, 0, API_BASIS_DAILY) for _ in range(3)]
        new = [_outcome(50, 50, 0, API_BASIS_HOURLY) for _ in range(10)]
        assert scoring_outcomes(old + daily + new) == new

    def test_weights_follow_the_hourly_windows_once_they_take_over(self):
        # On the old daily basis the provider was badly wrong (90 % on dry windows);
        # on the hourly basis it is right (0 % on dry windows) and the local model is wrong.
        old = [_outcome(0, 90, 0, None) for _ in range(30)]
        new = [_outcome(90, 0, 0, API_BASIS_HOURLY) for _ in range(10)]
        w_local, w_api = compute_blend_weights(old + new)
        assert w_api > w_local
        assert brier_score(scoring_outcomes(old + new), "openmeteo_prob") == 0.0

    def test_existing_weights_carry_over_before_the_switch(self):
        old = [_outcome(0, 90, 0, None) for _ in range(30)]
        w_local, w_api = compute_blend_weights(old)
        assert w_local > w_api
        # A few hourly windows join the old ones instead of resetting the weights to 50/50.
        w_local_after, _ = compute_blend_weights(old + [_outcome(90, 0, 0, API_BASIS_HOURLY)] * 5)
        assert 0.5 < w_local_after < w_local

    def test_record_stores_the_basis(self):
        state = LearningState()
        record_forecast_outcome(state, 40, 60, rained=True, api_basis=API_BASIS_HOURLY)
        assert state.forecast_outcomes[-1]["api_basis"] == API_BASIS_HOURLY
        assert (state.blend_local, state.blend_openmeteo) == (0.5, 0.5)


# ---------------------------------------------------------------------------
# Coordinator window lifecycle
# ---------------------------------------------------------------------------


class TestSkillWindow:
    def _coordinator(self, forecast: dict | None) -> SimpleNamespace:
        return SimpleNamespace(
            _forecast_cache=forecast,
            _learning_state=LearningState(),
            _skill_window_start=None,
            _skill_window_local_prob=None,
            _skill_window_api_prob=None,
            _skill_window_api_basis=None,
            _skill_window_rain_seen=False,
        )

    def test_window_records_hourly_provider_chance_and_basis(self):
        start = datetime(2026, 10, 27, 9, 5, tzinfo=UTC)
        # Provider hourly times are local, like Open-Meteo's with timezone=auto.
        hours = [
            {"datetime": dt_util.as_local(start + timedelta(hours=i)).strftime("%Y-%m-%dT%H:00"), "precip_prob": p}
            for i, p in enumerate([5, 60, 10, 0, 0, 0])
        ]
        coord = self._coordinator({"hourly": hours, "daily": [{"precip_prob": 95}]})
        update = WSStationCoordinator._update_forecast_skill_window

        update(coord, {KEY_RAIN_PROBABILITY: 30}, start)
        assert coord._skill_window_api_prob == 60.0
        assert coord._skill_window_api_basis == API_BASIS_HOURLY

        update(coord, {KEY_RAIN_RATE_FILT: 0.4}, start + timedelta(hours=2))
        update(coord, {}, start + timedelta(hours=6))

        recorded = coord._learning_state.forecast_outcomes[-1]
        assert recorded["openmeteo_prob"] == 60.0
        assert recorded["api_basis"] == API_BASIS_HOURLY
        assert recorded["local_prob"] == 30
        assert recorded["outcome"] == 1
        assert coord._skill_window_start is None
