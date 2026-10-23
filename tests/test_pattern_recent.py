"""Pattern Forecast: the 15-min history bins seeded from 5-minute short-term statistics (2.11.2)."""

from __future__ import annotations

import math

import pytest

from custom_components.ws_core import pattern_runtime
from custom_components.ws_core.const import PATTERN_BIN_COUNT
from custom_components.ws_core.pattern_forecast import Instant, PatternEngine, Thresholds

from .test_pattern_history import NOW, SOURCES, learn, learned, make_runtime  # noqa: F401 - fixture

SOURCES_WITH_DIR = {**SOURCES, "wind_direction": "sensor.wd"}


def five_minute_statistics(now_ts=None, hours=3.6, direction=None, rain_key="sum", t0=20.0):
    """~3.5 h of 5-minute statistics ending at ``now_ts``, shaped like the recorder returns them.

    Temperature rises 1 degC per hour, humidity is 60 %, wind 4 m/s from the east
    (90 deg) unless ``direction`` gives (mean, min, max) per period, gust 7 m/s,
    and 0.2 mm of rain falls every 15 minutes.
    """
    now_ts = NOW.timestamp() if now_ts is None else now_ts
    n = int(hours * 12)
    start = now_ts - n * 300.0
    rows: dict[str, list[dict]] = {
        k: [] for k in ("sensor.t", "sensor.h", "sensor.ws", "sensor.wd", "sensor.wg", "sensor.r")
    }
    for i in range(n):
        ts = start + i * 300.0
        t = t0 + (ts - start) / 3600.0
        rows["sensor.t"].append({"start": ts, "mean": t, "min": t - 0.1, "max": t + 0.1})
        rows["sensor.h"].append({"start": ts, "mean": 60.0, "min": 59.0, "max": 61.0})
        rows["sensor.ws"].append({"start": ts, "mean": 4.0, "min": 3.0, "max": 5.0})
        dm, dlo, dhi = direction(i) if direction else (90.0, 80.0, 100.0)
        rows["sensor.wd"].append({"start": ts, "mean": dm, "min": dlo, "max": dhi})
        rows["sensor.wg"].append({"start": ts, "mean": 5.0, "min": 4.0, "max": 7.0})
        total = 100.0 + 0.2 * math.floor((ts + 300.0 - start) / 900.0)
        if rain_key == "sum":
            rows["sensor.r"].append({"start": ts, "sum": total, "state": total})
        else:  # a running total recorded as a measurement (e.g. Shelly WS90)
            rows["sensor.r"].append({"start": ts, "mean": total, "min": total, "max": total})
    units = {
        "sensor.t": "°C",
        "sensor.h": "%",
        "sensor.ws": "m/s",
        "sensor.wd": "°",
        "sensor.wg": "m/s",
        "sensor.r": "mm",
    }
    meta = {
        eid: {
            "statistic_id": eid,
            "unit_of_measurement": u,
            "has_sum": eid == "sensor.r" and rain_key == "sum",
            "has_mean": not (eid == "sensor.r" and rain_key == "sum"),
            "mean_type": 1,
        }
        for eid, u in units.items()
    }
    return meta, rows


def recent_plan(rt):
    return {n: rt.recent_entity(n, NOW.timestamp()) for n in pattern_runtime._RECENT_INPUTS}


class TestRecentBinsFromShortTermStatistics:
    def test_bins_match_the_live_shape(self):
        meta, rows = five_minute_statistics()
        coord, rt = make_runtime(sources=SOURCES_WITH_DIR)
        bins = rt.build_recent_bins(recent_plan(rt), meta, rows, NOW.timestamp())
        assert len(bins) == PATTERN_BIN_COUNT
        assert [b["ts"] for b in bins] == [NOW.timestamp() - k * 900.0 for k in range(12, -1, -1)]
        last = bins[-1]
        assert last["t"] == round(rows["sensor.t"][-1]["mean"], 2)  # the bin's last 5-minute mean
        assert 0.0 < last["d"] < 15.0  # dew point depression at 60 % RH
        # wind from the east, live convention: u = -s*sin(dir), v = -s*cos(dir)
        assert last["u"] == pytest.approx(-4.0, abs=1e-6)
        assert last["v"] == pytest.approx(0.0, abs=1e-6)
        assert last["s"] == pytest.approx(4.0)
        assert last["n"] == 15
        assert last["g"] == pytest.approx(7.0)
        assert last["r"] == pytest.approx(0.2)
        assert last["k"] is None  # no storm source in this setup

    def test_one_hour_and_three_hour_changes_exist_at_the_next_issue(self):
        coord, rt = make_runtime(sources=SOURCES_WITH_DIR, stats5=five_minute_statistics())
        learn(rt)
        eng = rt.engine
        ts = NOW.timestamp() + 900.0 + 30.0
        feats, _ = eng._features(ts, Instant(temp=24.0, dpd=8.0, mslp=1013.0, local_hour=12.0))
        for name in ("dpd_1h", "t_1h", "t_3h", "wind_u", "wind_v", "wind_speed", "gust_1h", "rain_1h"):
            assert feats[name] is not None, name
        one_hour_ago = next(b for b in eng.bins if b["ts"] == ts - 30.0 - 3600.0)
        assert feats["t_1h"] == pytest.approx(24.0 - one_hour_ago["t"], abs=1e-6)

    def test_a_direction_that_may_straddle_north_is_not_averaged(self):
        def straddle(i):
            return (180.0, 2.0, 358.0) if i % 3 == 2 else (10.0, 5.0, 15.0)

        meta, rows = five_minute_statistics(direction=straddle)
        coord, rt = make_runtime(sources=SOURCES_WITH_DIR)
        bins = rt.build_recent_bins(recent_plan(rt), meta, rows, NOW.timestamp())
        for b in bins:
            assert b["n"] < 15  # the straddling period is dropped
            assert b["v"] < 0 and abs(b["u"]) < 1.5  # the rest point roughly north
        meta["sensor.wd"]["mean_type"] = 2  # a circular mean (HA mean_type 2) is trusted as is
        bins = rt.build_recent_bins(recent_plan(rt), meta, rows, NOW.timestamp())
        assert all(b["n"] == 15 for b in bins)

    def test_measurement_type_rain_totals_work_here_too(self):
        meta, rows = five_minute_statistics(rain_key="max")
        coord, rt = make_runtime(sources=SOURCES_WITH_DIR)
        bins = rt.build_recent_bins(recent_plan(rt), meta, rows, NOW.timestamp())
        assert all(b["r"] == pytest.approx(0.2) for b in bins)

    def test_an_unfinished_period_is_never_used(self):
        meta, rows = five_minute_statistics()
        coord, rt = make_runtime(sources=SOURCES_WITH_DIR)
        now = NOW.timestamp() + 120.0  # the next 5-minute period is still being recorded
        meta2, rows2 = five_minute_statistics(now_ts=NOW.timestamp() + 300.0)
        bins = rt.build_recent_bins(recent_plan(rt), meta2, rows2, now)
        assert bins[-1]["ts"] == NOW.timestamp()
        assert bins[-1]["t"] == round(rows2["sensor.t"][-2]["mean"], 2)

    def test_seeding_runs_at_every_start_even_without_a_replay(self):
        coord, rt = make_runtime(sources=SOURCES_WITH_DIR, stats5=five_minute_statistics())
        learn(rt)
        assert rt.engine.targets_needing_replay(NOW.timestamp() + 60) == []
        rt.engine.bins.clear()
        learn(rt)
        assert len(rt.engine.bins) == PATTERN_BIN_COUNT

    def test_recorder_failure_never_raises(self):
        coord, rt = make_runtime(sources=SOURCES_WITH_DIR)

        def broken(*args, **kwargs):
            raise OSError("database is locked")

        rt._fetch_statistics = broken  # type: ignore[method-assign]
        learn(rt)
        assert len(rt.engine.bins) == 0

    def test_no_sensors_mapped_means_nothing_is_read(self):
        coord, rt = make_runtime(sources=SOURCES_WITH_DIR)
        assert rt._recent_job(dict.fromkeys(pattern_runtime._RECENT_INPUTS), NOW.timestamp()) == []


class TestSeedBins:
    def _live_bin(self, ts, t):
        return {"ts": ts, "t": t, "d": 1.0, "u": None, "v": None, "s": None, "g": None, "r": 0.0, "k": None, "n": 0}

    def test_live_bins_always_win_and_junk_is_dropped(self):
        eng = PatternEngine(Thresholds())
        live_ts = NOW.timestamp() + 20.0
        eng.bins.append(self._live_bin(live_ts, 1.0))
        seeds = [
            {"ts": NOW.timestamp(), "t": 99.0, "n": 15},  # within 7.5 min of the live bin: dropped
            {"ts": NOW.timestamp() - 900.0, "t": 5.0, "d": float("nan"), "n": 15},
            {"ts": "bad"},
            "not a dict",
        ]
        assert eng.seed_bins(seeds) == 1
        kept = {b["ts"]: b for b in eng.bins}
        assert kept[live_ts]["t"] == 1.0
        assert kept[NOW.timestamp() - 900.0]["t"] == 5.0
        assert kept[NOW.timestamp() - 900.0]["d"] is None

    def test_at_most_three_hours_are_kept(self):
        eng = PatternEngine(Thresholds())
        eng.seed_bins([{"ts": NOW.timestamp() - k * 900.0, "t": float(k), "n": 15} for k in range(30)])
        assert len(eng.bins) == PATTERN_BIN_COUNT
        assert eng.bins[-1]["ts"] == NOW.timestamp()

    def test_seeded_bins_survive_a_store_roundtrip(self):
        eng = PatternEngine(Thresholds())
        eng.seed_bins([{"ts": NOW.timestamp() - k * 900.0, "t": float(k), "n": 15} for k in range(4)])
        back, _ = PatternEngine.from_dict(eng.to_dict(), Thresholds())
        assert [b["ts"] for b in back.bins] == [b["ts"] for b in eng.bins]


class TestLastRain:
    def test_replay_sets_the_last_rain_from_history(self, learned):  # noqa: F811 - fixture
        coord, rt = learned
        eng = rt.engine
        assert eng.last_rain_ts is not None
        assert NOW.timestamp() - 30 * 86400 < eng.last_rain_ts <= NOW.timestamp()

    def test_seed_last_rain_never_moves_backwards(self):
        eng = PatternEngine(Thresholds())
        eng.seed_last_rain(NOW.timestamp())
        eng.seed_last_rain(NOW.timestamp() - 3600.0)
        eng.seed_last_rain(float("nan"))
        assert eng.last_rain_ts == NOW.timestamp()
