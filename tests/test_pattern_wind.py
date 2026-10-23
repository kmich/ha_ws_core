"""Regression coverage for wind warm start and independent speed coverage."""

import math

import pytest

from custom_components.ws_core.pattern_forecast import Instant, Observation, PatternEngine, Thresholds
from custom_components.ws_core.pattern_wind import direction_vectors

from .test_pattern_history import NOW, make_runtime
from .test_pattern_recent import SOURCES_WITH_DIR, five_minute_statistics, recent_plan


def test_raw_directions_crossing_north_do_not_point_south():
    vectors = direction_vectors([(0, "350"), (150, "10")], 0, 300, 600)
    sin_dir, cos_dir = vectors[0]
    assert abs(sin_dir) < 1e-9
    assert cos_dir == pytest.approx(math.cos(math.radians(10)))


def test_opposite_winds_cancel_instead_of_inventing_a_direction():
    assert direction_vectors([(0, "90"), (150, "270")], 0, 300, 600)[0] == pytest.approx((0, 0), abs=1e-9)


@pytest.mark.parametrize("value", ["unavailable", "unknown", "nan", "inf", "361"])
def test_unknown_intervals_do_not_become_calm_or_north(value):
    assert direction_vectors([(0, "90"), (60, value)], 0, 300, 600) == {}


def test_stale_and_incomplete_periods_are_not_replayed():
    assert direction_vectors([(0, "90")], 0, 300, 120) == {}
    assert direction_vectors([(0, "90")], 0, 299, 600) == {}


def test_valid_speed_is_kept_without_direction_in_live_bins():
    eng = PatternEngine(Thresholds())
    ts = NOW.timestamp()
    for i in range(4):
        eng.observe(ts + i * 900, Observation(wind_speed=4))
        eng.issue(ts + i * 900, Instant())
    f, _ = eng._features(ts + 2700, Instant())
    assert f["wind_speed"] == 4
    assert f["wind_u"] is None
    restored = PatternEngine.from_dict(eng.to_dict(), Thresholds())[0]
    assert restored._features(ts + 2700, Instant())[0]["wind_speed"] == 4


def test_statistics_speed_survives_unusable_direction():
    meta, rows = five_minute_statistics(direction=lambda i: (180, 0, 360))
    _, rt = make_runtime(sources=SOURCES_WITH_DIR)
    bins = rt.build_recent_bins(recent_plan(rt), meta, rows, NOW.timestamp())
    assert all(b["s"] == 4 and b["sn"] == 15 and b["n"] == 0 for b in bins)


def test_raw_history_recovers_vectors_when_direction_statistics_are_unsafe():
    meta, rows = five_minute_statistics(direction=lambda i: (180, 0, 360))
    _, rt = make_runtime(sources=SOURCES_WITH_DIR, stats5=(meta, rows))
    calls = []

    def fetch(eid, start, end):
        calls.append(eid)
        return direction_vectors(
            [(start.timestamp(), "350"), (start.timestamp() + 150, "10")], start.timestamp(), end.timestamp(), 14400
        )

    rt._fetch_direction_vectors = fetch
    bins = rt._recent_job(recent_plan(rt), NOW.timestamp())
    assert calls == ["sensor.wd"]
    assert sum(b["n"] > 0 for b in bins) >= 3
    assert all(b["v"] < 0 for b in bins if b["n"])


def test_recorder_failure_keeps_speed_but_does_not_invent_direction():
    meta, rows = five_minute_statistics(direction=lambda i: (180, 0, 360))
    _, rt = make_runtime(sources=SOURCES_WITH_DIR, stats5=(meta, rows))

    def broken(*args):
        raise OSError("raw history unavailable")

    rt._fetch_direction_vectors = broken
    bins = rt._recent_job(recent_plan(rt), NOW.timestamp())
    assert all(b["u"] is None and b["s"] == 4 for b in bins)


def test_overall_status_explains_waiting_instead_of_claiming_training():
    eng = PatternEngine(Thresholds())
    eng.models["rain_1h"].maturity = "learning"
    eng._last_issue = {"rain_1h": {"p": None, "reason": "waiting_for:wind_u"}}
    assert eng.overall_status() == "waiting"
    eng._last_issue["rain_1h"] = {"p": 0.2, "reason": None}
    assert eng.overall_status() == "learning"


def test_collecting_sensor_reports_both_event_and_day_requirements():
    _, rt = make_runtime(sources=SOURCES_WITH_DIR)
    attrs = rt._target_attrs("frost_12h")
    assert attrs["reason"] == "collecting_training_data"
    assert attrs["events_collected"] == 0
    assert attrs["events_required"] == 5
    assert attrs["days_required"] == 7
    assert "Collecting:" in attrs["explanation"]
