"""Regressions for recorder counter baselines, period boundaries and resets."""

from unittest.mock import patch

import pytest

from custom_components.ws_core.history_backfill import apply_rain, read_statistics
from tests.test_coordinator import _make_coordinator


def _rain(rows, has_sum=True, live=0.0, raw=1010.0, first=3600.0):
    coord = _make_coordinator()
    coord._rain_this_week_isoweek = "week"
    coord._rain_this_week_mm = live
    coord._rain_this_week_last_total = raw
    coord._rain_this_month_key = ""
    coord._rain_this_year_key = ""
    periods = {"week": ("week", first), "month": ("month", first), "year": ("year", first)}
    meta = {"sensor.rain": {"has_sum": has_sum, "statistics_unit_of_measurement": "mm"}}
    return coord, meta, {"sensor.rain": rows}, periods


@pytest.mark.parametrize("sum_start", [0.0, 2000.0])
def test_recorder_sum_and_raw_counter_can_have_different_zero_points(sum_start):
    coord, meta, rows, periods = _rain(
        [
            {"start": 0.0, "sum": sum_start, "state": 1000.0},
            {"start": 3600.0, "sum": sum_start + 10.0, "state": 1010.0},
        ],
        raw=1013.0,
    )
    apply_rain(coord, meta, rows, 0.0, 2, periods)
    assert coord._rain_this_week_mm == 13.0


def test_sum_without_raw_state_uses_recorded_changes_only():
    coord, meta, rows, periods = _rain(
        [
            {"start": 0.0, "sum": 0.0},
            {"start": 3600.0, "sum": 10.0},
        ]
    )
    apply_rain(coord, meta, rows, 0.0, 2, periods)
    assert coord._rain_this_week_mm == 10.0


def test_station_reset_does_not_reset_recorder_sum():
    coord, meta, rows, periods = _rain(
        [
            {"start": 0.0, "sum": 100.0, "state": 1000.0},
            {"start": 3600.0, "sum": 110.0, "state": 5.0},
        ],
        raw=8.0,
    )
    apply_rain(coord, meta, rows, 0.0, 2, periods)
    assert coord._rain_this_week_mm == 13.0


def test_raw_reset_after_last_statistic_adds_no_unproven_tail():
    coord, meta, rows, periods = _rain(
        [
            {"start": 0.0, "sum": 0.0, "state": 1000.0},
            {"start": 3600.0, "sum": 10.0, "state": 1010.0},
        ],
        raw=3.0,
    )
    apply_rain(coord, meta, rows, 0.0, 2, periods)
    assert coord._rain_this_week_mm == 10.0


def test_unbounded_live_counter_jump_is_not_added_as_tail():
    coord, meta, rows, periods = _rain(
        [
            {"start": 0.0, "max": 1000.0},
            {"start": 3600.0, "max": 1010.0},
        ],
        has_sum=False,
        raw=1500.0,
    )
    apply_rain(coord, meta, rows, 0.0, 2, periods)
    assert coord._rain_this_week_mm == 10.0


def test_gap_crossing_period_boundary_is_not_all_booked_to_new_period():
    coord, meta, rows, periods = _rain(
        [
            {"start": 0.0, "max": 10.0},
            {"start": 10800.0, "max": 30.0},
        ],
        has_sum=False,
        raw=30.0,
        first=7200.0,
    )
    apply_rain(coord, meta, rows, 0.0, 4, periods)
    assert coord._rain_this_week_mm == 0.0


def test_gap_inside_period_still_counts_counter_growth():
    coord, meta, rows, periods = _rain(
        [
            {"start": 0.0, "max": 10.0},
            {"start": 10800.0, "max": 13.0},
        ],
        has_sum=False,
        raw=13.0,
    )
    apply_rain(coord, meta, rows, 0.0, 4, periods)
    assert coord._rain_this_week_mm == 3.0


def test_empty_metadata_does_not_query_all_recorded_entities():
    with (
        patch("homeassistant.components.recorder.statistics.list_statistic_ids", return_value=[]),
        patch("homeassistant.components.recorder.statistics.statistics_during_period") as query,
    ):
        assert read_statistics(None, {"sensor.not_recorded"}, 0.0, 3600.0) == ({}, {})
    query.assert_not_called()
