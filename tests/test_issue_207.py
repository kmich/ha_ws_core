"""Regression tests for issue #207: "Clearing after rain" without any rain."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest

from custom_components.ws_core import coordinator as cmod
from custom_components.ws_core.algorithms import determine_current_condition
from tests.test_coordinator import _make_coordinator


def _bright_humid_day(**overrides):
    """Cold, humid, bright midday with no rain falling: the reporter's situation."""
    kwargs = {
        "temp_c": 1.5,
        "humidity": 88.0,
        "wind_speed_ms": 1.5,
        "wind_gust_ms": 3.0,
        "rain_rate_mmph": 0.0,
        "dew_point_c": -0.3,
        "illuminance_lx": 45000.0,
        "uv_index": 2.0,
        "zambretti": "fine_weather",
        "pressure_trend": 0.0,
        "sun_elevation": 25.0,
        "sun_azimuth": 180.0,
        "is_day": True,
        "current_hour": 12,
    }
    kwargs.update(overrides)
    return determine_current_condition(**kwargs)


def test_no_recent_rain_is_not_clearing_after_rain():
    assert _bright_humid_day() != "clearing-after-rain"
    assert _bright_humid_day() == "sunny"


def test_recent_rain_can_still_report_clearing_after_rain():
    assert _bright_humid_day(rained_recently=True) == "clearing-after-rain"


def test_missing_light_reading_cannot_support_clearing_after_rain():
    # Callers substitute 50 000 lx when no light sensor exists; that is not evidence of brightness.
    assert _bright_humid_day(rained_recently=True, illuminance_known=False) != "clearing-after-rain"


def _condition_kwargs(coord, data):
    with patch.object(cmod, "determine_current_condition", return_value="sunny") as cond:
        coord._compute_condition(data, 1.5, 88.0, 1.5, 3.0, 0.0, -0.3, 45000.0, 2.0)
    return cond.call_args.kwargs


def test_coordinator_uses_measured_recent_rain():
    coord = _make_coordinator()
    assert _condition_kwargs(coord, {})["rained_recently"] is False
    assert _condition_kwargs(coord, {"_rain_recent_mm": 0.0})["rained_recently"] is False
    assert _condition_kwargs(coord, {"_rain_recent_mm": 0.4})["rained_recently"] is True


@pytest.mark.parametrize(
    ("counter_increase", "expected"),
    [
        (0.03, "sunny"),
        (0.095, "sunny"),
        (0.1, "clearing-after-rain"),
    ],
)
def test_condition_uses_accumulation_even_when_filtered_rate_was_positive(counter_increase, expected):
    coord = _make_coordinator()
    start = datetime(2026, 11, 20, 12, 0, tzinfo=UTC)
    coord._compute_derived_precipitation({}, start, 10.0)
    rates = []
    for minute in range(1, 35):
        data = {}
        now = start + timedelta(minutes=minute)
        rates.append(coord._compute_derived_precipitation(data, now, 10.0 + counter_increase))
    assert max(rates) > 0
    assert rates[-1] == 0
    assert data["_rain_recent_mm"] == pytest.approx(counter_increase)
    condition = coord._compute_condition(data, 1.5, 88.0, 1.5, 3.0, rates[-1], -0.3, 45000.0, 2.0)
    assert condition == expected


def test_coordinator_reports_missing_light_reading():
    coord = _make_coordinator()
    with patch.object(cmod, "determine_current_condition", return_value="sunny") as cond:
        coord._compute_condition({}, 1.5, 88.0, 1.5, 3.0, 0.0, -0.3, None, 2.0)
    assert cond.call_args.kwargs["illuminance_known"] is False


def test_recent_rain_amount_is_published_from_rain_history():
    coord = _make_coordinator()
    now = datetime(2026, 11, 20, 12, 0, tzinfo=UTC)
    coord.runtime.rain_total_history_24h.extend(
        [(now - timedelta(hours=5), 10.0), (now - timedelta(hours=2), 10.0), (now - timedelta(hours=1), 10.6)]
    )
    data: dict = {}
    coord._compute_derived_precipitation(data, now, 10.6, sample=False)
    assert data["_rain_recent_mm"] == pytest.approx(0.6)
    coord._compute_derived_precipitation(data, now + timedelta(hours=3), 10.6, sample=False)
    assert data["_rain_recent_mm"] == 0.0
