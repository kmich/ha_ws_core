"""Tests for historical climate-normals binning (v2.7).

Covers the pure functions behind the Climate Normals feature:
  - parse_archive_daily_response: Open-Meteo archive-api JSON -> flat records
  - compute_climate_normals: records -> smoothed day-of-year normals table
  - climate_normal_for_date: table lookup for a given date
"""

from __future__ import annotations

import os
import sys
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from custom_components.ws_core.climate_normals import (
    climate_normal_for_date,
    compute_climate_normals,
    parse_archive_daily_response,
)


class TestParseArchiveDailyResponse:
    def test_parses_full_payload(self):
        payload = {
            "daily": {
                "time": ["2020-01-01", "2020-01-02"],
                "temperature_2m_max": [10.0, 11.0],
                "temperature_2m_min": [2.0, 3.0],
                "precipitation_sum": [0.0, 1.5],
            }
        }
        records = parse_archive_daily_response(payload)
        assert records == [
            {"date": "2020-01-01", "t_max": 10.0, "t_min": 2.0, "precip": 0.0},
            {"date": "2020-01-02", "t_max": 11.0, "t_min": 3.0, "precip": 1.5},
        ]

    def test_missing_daily_block_returns_empty(self):
        assert parse_archive_daily_response({}) == []

    def test_short_arrays_degrade_to_none(self):
        payload = {"daily": {"time": ["2020-01-01", "2020-01-02"], "temperature_2m_max": [10.0]}}
        records = parse_archive_daily_response(payload)
        assert records[0]["t_max"] == 10.0
        assert records[1]["t_max"] is None
        assert records[1]["t_min"] is None
        assert records[1]["precip"] is None


def _years_of_jan1(t_max: float, t_min: float, precip: float, n_years: int = 10) -> list[dict]:
    """N identical Jan-1 samples across different years - a stable single-day normal."""
    return [{"date": f"{2010 + i}-01-01", "t_max": t_max, "t_min": t_min, "precip": precip} for i in range(n_years)]


class TestComputeClimateNormals:
    def test_empty_input_returns_empty(self):
        assert compute_climate_normals([]) == {}

    def test_stable_repeated_day_averages_to_itself(self):
        records = _years_of_jan1(10.0, 2.0, 1.0)
        normals = compute_climate_normals(records, window_days=0)
        jan1 = normals["1"]
        assert jan1["t_high"] == 10.0
        assert jan1["t_low"] == 2.0
        assert jan1["rain"] == 1.0
        assert jan1["n"] == 10

    def test_window_smooths_across_neighboring_days(self):
        # Jan 1 is cold, Jan 2 is warm - with a window, Jan 1's bucket also
        # picks up Jan 2's samples (and vice versa), pulling the mean between.
        records = _years_of_jan1(0.0, -5.0, 0.0) + [
            {"date": f"{2010 + i}-01-02", "t_max": 20.0, "t_min": 10.0, "precip": 0.0} for i in range(10)
        ]
        normals = compute_climate_normals(records, window_days=1)
        # Jan 1's bucket now includes Jan 2 (dist=1) but not Dec 31 (no data) - mean of 0 and 20.
        assert normals["1"]["t_high"] == 10.0

    def test_zero_window_keeps_days_independent(self):
        records = _years_of_jan1(0.0, -5.0, 0.0) + [
            {"date": f"{2010 + i}-01-02", "t_max": 20.0, "t_min": 10.0, "precip": 0.0} for i in range(10)
        ]
        normals = compute_climate_normals(records, window_days=0)
        assert normals["1"]["t_high"] == 0.0
        assert normals["2"]["t_high"] == 20.0

    def test_year_boundary_wraps_circularly(self):
        # Dec 31 and Jan 1 are calendar-adjacent across the year boundary.
        records = [{"date": "2019-12-31", "t_max": 5.0, "t_min": 1.0, "precip": 0.0}] + _years_of_jan1(15.0, 5.0, 0.0)
        normals = compute_climate_normals(records, window_days=1)
        # Day 365 (Dec 31) is within 1 of day 1 (Jan 1) via circular distance.
        assert normals["1"]["t_high"] == round((5.0 + 15.0 * 10) / 11, 1)

    def test_feb29_collapses_onto_feb28(self):
        records = [{"date": "2020-02-29", "t_max": 8.0, "t_min": 1.0, "precip": 0.0}] + [
            {"date": f"{2011 + i}-02-28", "t_max": 8.0, "t_min": 1.0, "precip": 0.0} for i in range(9)
        ]
        normals = compute_climate_normals(records, window_days=0)
        feb28_yday = date(2001, 2, 28).timetuple().tm_yday
        assert normals[str(feb28_yday)]["n"] == 10  # the leap-year Feb 29 sample merged in

    def test_missing_field_excluded_from_that_metrics_mean(self):
        records = [
            {"date": "2020-01-01", "t_max": 10.0, "t_min": None, "precip": 1.0},
            {"date": "2021-01-01", "t_max": 12.0, "t_min": None, "precip": 3.0},
        ]
        normals = compute_climate_normals(records, window_days=0)
        assert normals["1"]["t_high"] == 11.0
        assert normals["1"]["t_low"] is None
        assert normals["1"]["rain"] == 2.0


class TestClimateNormalForDate:
    def test_looks_up_by_canonical_day_of_year(self):
        normals = compute_climate_normals(_years_of_jan1(10.0, 2.0, 1.0), window_days=0)
        result = climate_normal_for_date(normals, date(2026, 1, 1))
        assert result == {"t_high": 10.0, "t_low": 2.0, "rain": 1.0, "n": 10}

    def test_missing_day_returns_none(self):
        normals = compute_climate_normals(_years_of_jan1(10.0, 2.0, 1.0), window_days=0)
        assert climate_normal_for_date(normals, date(2026, 7, 4)) is None
