"""Tests for Pattern Forecast learning from recorder long-term statistics (mocked recorder)."""

from __future__ import annotations

import asyncio
import math
import pathlib
import random
import threading
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from custom_components.ws_core import pattern_runtime
from custom_components.ws_core.const import (
    CONF_ENABLE_PATTERN_FORECAST,
    CONF_PATTERN_STORM_INTERNET_LIGHTNING,
    PATTERN_HISTORY_METHOD,
    PATTERN_HISTORY_RETRY_S,
    PATTERN_PRESSURE_SLOTS,
    SRC_LIGHTNING_COUNT,
)
from custom_components.ws_core.pattern_forecast import (
    N_POOL,
    POOL,
    POOL_INDEX,
    HourlyHistory,
    PatternEngine,
    Thresholds,
)

from .test_pattern_forecast_integration import make_coord

NOW = datetime(2026, 10, 23, 12, 0, tzinfo=UTC)
N = 365 * 24
START_TS = NOW.timestamp() - N * 3600.0

SOURCES = {
    "temperature": "sensor.t",
    "humidity": "sensor.h",
    "pressure": "sensor.p",
    "wind_speed": "sensor.ws",
    "wind_gust": "sensor.wg",
    "rain_total": "sensor.r",
    SRC_LIGHTNING_COUNT: "sensor.l",
}


def year_of_statistics(
    seed: int = 4, fahrenheit: bool = False, drop: set[str] | None = None, hole: tuple[int, int] | None = None
):
    """A year of hourly statistics shaped like the recorder returns them."""
    rng = random.Random(seed)
    drop = drop or set()
    meta: dict[str, dict] = {}
    rows: dict[str, list[dict]] = {
        k: [] for k in ("sensor.t", "sensor.h", "sensor.p", "sensor.ws", "sensor.wg", "sensor.r", "sensor.l")
    }
    rain_sum = 0.0
    strike_sum = 0.0
    press = 1013.0
    rain_left = 0
    for j in range(N):
        ts = START_TS + j * 3600.0
        if hole and hole[0] <= j < hole[1]:
            continue
        doy = (ts / 86400.0) % 365.25
        hour = (ts / 3600.0) % 24.0
        season = math.sin(2 * math.pi * (doy - 110) / 365.25)
        base = 15.0 + 11.0 * season + 5.0 * math.sin(2 * math.pi * (hour - 9.0) / 24.0) + rng.gauss(0, 1.5)
        press += rng.gauss(0, 0.4) - 0.02 * (press - 1013.0)
        if rain_left == 0 and rng.random() < 0.035:
            rain_left = rng.randint(1, 5)
        rain_h = 0.0
        if rain_left:
            rain_left -= 1
            rain_h = 0.2 * rng.randint(1, 6)
            press -= 0.3
        rain_sum += rain_h
        wind = max(0.2, 3.0 + rng.gauss(0, 1.2))
        gust = wind * 1.6 + abs(rng.gauss(0, 1.0)) + (14.0 if rng.random() < 0.004 else 0.0)
        if 13 <= hour < 17 and season > 0.3 and rng.random() < 0.15:
            strike_sum += rng.randint(2, 12)
        rh = max(25.0, min(100.0, 80.0 - 2.0 * (base - 15.0) + rng.gauss(0, 5.0) + (15.0 if rain_h else 0.0)))
        t_mean = base * 9 / 5 + 32 if fahrenheit else base
        spread = 9 / 5 if fahrenheit else 1.0
        rows["sensor.t"].append({"start": ts, "mean": t_mean, "min": t_mean - 2 * spread, "max": t_mean + 2 * spread})
        rows["sensor.h"].append({"start": ts, "mean": rh})
        rows["sensor.p"].append({"start": ts, "mean": press})
        rows["sensor.ws"].append({"start": ts, "mean": wind})
        rows["sensor.wg"].append({"start": ts, "max": gust})
        rows["sensor.r"].append({"start": ts, "sum": rain_sum / (25.4 if fahrenheit else 1.0), "state": rain_sum})
        rows["sensor.l"].append({"start": ts, "sum": strike_sum, "state": strike_sum})
    units = {
        "sensor.t": "°F" if fahrenheit else "°C",
        "sensor.h": "%",
        "sensor.p": "hPa",
        "sensor.ws": "m/s",
        "sensor.wg": "m/s",
        "sensor.r": "in" if fahrenheit else "mm",
        "sensor.l": "",
    }
    for eid, unit in units.items():
        if eid in drop:
            rows.pop(eid)
            continue
        meta[eid] = {
            "statistic_id": eid,
            "unit_of_measurement": unit,
            "has_sum": eid in ("sensor.r", "sensor.l"),
            "has_mean": eid not in ("sensor.r", "sensor.l"),
        }
    return meta, rows


class FakeRecorder:
    """Stands in for get_instance(hass): runs the job on a real worker thread."""

    async def async_add_executor_job(self, fn, *args):
        return await asyncio.get_running_loop().run_in_executor(None, fn, *args)


def make_runtime(options: dict | None = None, stats=None, sources: dict | None = None, stats5=None):
    coord, table = make_coord({CONF_ENABLE_PATTERN_FORECAST: True, **(options or {})}, sources or SOURCES)
    # The mock HA executor does not run background tasks; close retries unless
    # an individual test replaces this hook to exercise their scheduling.
    coord._spawn = lambda coro, name: coro.close()
    rt = coord._pattern
    meta, rows = stats if stats is not None else year_of_statistics()
    meta5, rows5 = stats5 if stats5 is not None else ({}, {})
    threads: list[str] = []
    loop_thread = threading.current_thread().name

    periods: list[str] = []

    def fetch(entity_ids, start, end, period="hour"):
        threads.append(threading.current_thread().name)
        periods.append(period)
        m, r = (meta5, rows5) if period == "5minute" else (meta, rows)
        return {k: v for k, v in m.items() if k in entity_ids}, {k: v for k, v in r.items() if k in entity_ids}

    rt._fetch_statistics = fetch  # type: ignore[method-assign]
    rt._test_threads = threads  # type: ignore[attr-defined]
    rt._test_periods = periods  # type: ignore[attr-defined]
    rt._test_loop_thread = loop_thread  # type: ignore[attr-defined]
    return coord, rt


def learn(rt, recorder=None):
    async def go():
        with (
            patch.object(pattern_runtime, "_recorder_instance", return_value=recorder or FakeRecorder()),
            patch.object(pattern_runtime.dt_util, "utcnow", return_value=NOW),
        ):
            await rt.async_learn_history()

    asyncio.run(go())


@pytest.fixture(scope="module")
def learned():
    coord, rt = make_runtime()
    learn(rt)
    return coord, rt


class TestReplay:
    def test_every_target_learns_and_reports_ok(self, learned):
        _, rt = learned
        eng = rt.engine
        assert set(eng.models) == {"rain_1h", "rain_3h", "rain_6h", "frost_12h", "heat_24h", "gust_3h", "storm_3h"}
        hl = eng.history_learn
        assert hl["status"] == "ok" and hl["reason"] is None
        assert hl["span_days"] > 300
        assert set(hl["targets"]) == set(eng.models)
        for tid, t in hl["targets"].items():
            assert t["status"] == "ok" and t["samples"] > 1000, (tid, t)
            assert eng.models[tid].n_updates == t["samples"]

    def test_status_sensor_reports_history_per_target(self, learned):
        _, rt = learned
        rt._rebuild_published()
        data: dict = {}
        rt._publish(data)
        hist = data["_pattern_status_attrs"]["history_learn"]
        assert hist["status"] == "ok" and hist["span_days"] > 300 and hist["done_at"]
        assert hist["per_target"]["frost_12h"]["status"] == "ok"
        assert hist["per_target"]["frost_12h"]["samples"] > 1000

    def test_replay_runs_off_the_event_loop_thread(self):
        coord, rt = make_runtime()
        learn(rt)
        assert rt._test_threads and all(t != rt._test_loop_thread for t in rt._test_threads)

    def test_history_events_leave_collecting_but_never_reach_skilled(self, learned):
        _, rt = learned
        eng = rt.engine
        eng.issue(  # a live issue re-evaluates maturity
            NOW.timestamp(),
            pattern_runtime.Instant(mslp=1013.0, dp_3h=0.0, temp=10.0, dpd=3.0, t_max_24h=12.0, night_frac_12h=0.5),
        )
        for tid, m in eng.models.items():
            assert m.ev_hist >= 5, tid  # a year holds plenty of events
            assert m.hist_days > 300
            assert m.maturity == "learning", (tid, m.maturity)  # not collecting, never skilled
            assert eng.skill(tid)["n_scored"] == 0  # skill is proven on live 15-minute data only
            assert eng.scoring[tid] == []
            assert m.ev_live == 0
        assert eng.skilled_count() == 0

    def test_replayed_samples_seed_the_usual_rate(self, learned):
        _, rt = learned
        for tid in ("rain_3h", "frost_12h", "heat_24h"):
            rate = rt.engine.base_rate[tid][0]
            assert 0.0 < rate < 1.0 and rt.engine.base_rate[tid][1] > 1000

    def test_wind_direction_is_masked_during_replay(self, learned):
        _, rt = learned
        for tid in ("rain_3h", "heat_24h", "gust_3h"):
            w = rt.engine.named_weights(tid)
            assert w["wind_u"] == 0.0 and w["wind_v"] == 0.0, tid  # no gradient ever reached them
        assert rt.engine.named_weights("frost_12h")["wind_speed"] != 0.0  # speed does train

    def test_standardizer_built_from_history_when_cold(self, learned):
        _, rt = learned
        std = rt.engine.std
        assert std.n[POOL_INDEX["temp"]] > 8000
        assert std.n[POOL_INDEX["wind_u"]] == 0  # masked features are never standardized from replay
        assert 5.0 < std.mean[POOL_INDEX["temp"]] < 25.0

    def test_store_is_saved_after_replay(self):
        class Store:
            saved = None

            async def async_load(self):
                return None

            async def async_save(self, data):
                Store.saved = data

        coord, rt = make_runtime()
        rt.store = Store()
        learn(rt)
        assert Store.saved is not None
        assert Store.saved["history_learn"]["status"] == "ok"
        assert Store.saved["models"]["frost_12h"]["events"]["history"] > 0

    def test_swap_in_happens_on_a_copy(self):
        coord, rt = make_runtime()
        seen: dict = {}
        real = rt._fetch_statistics

        def spy(ids, start, end):
            # while the job runs, the live engine has not been touched
            seen["n_updates"] = {t: m.n_updates for t, m in rt.engine.models.items()}
            seen["hl"] = dict(rt.engine.history_learn)
            return real(ids, start, end)

        rt._fetch_statistics = spy  # type: ignore[method-assign]
        learn(rt)
        assert all(v == 0 for v in seen["n_updates"].values()) and seen["hl"] == {}
        assert all(m.n_updates > 0 for m in rt.engine.models.values())

    def test_second_call_does_not_replay_again(self):
        coord, rt = make_runtime()
        learn(rt)
        hourly = rt._test_periods.count("hour")
        updates = {t: m.n_updates for t, m in rt.engine.models.items()}
        reads = []
        fetch = rt._fetch_statistics

        def bounded_fetch(ids, start, end, period="hour"):
            reads.append((set(ids), (end - start).total_seconds(), period))
            return fetch(ids, start, end, period)

        rt._fetch_statistics = bounded_fetch
        learn(rt)
        # Every target already learned: only recent bins and a short pressure
        # window are refreshed, and model updates remain unchanged.
        assert rt._test_periods.count("hour") == hourly + 1
        assert rt._test_periods[-2:] == ["5minute", "hour"]
        assert reads[-1] == ({"sensor.t", "sensor.p"}, 38 * 3600, "hour")
        assert {t: m.n_updates for t, m in rt.engine.models.items()} == updates
        rt.engine.pressure.clear()
        learn(rt)
        assert rt.engine.pressure_change_24h(NOW.timestamp(), 1013.0) is not None
        assert {t: m.n_updates for t, m in rt.engine.models.items()} == updates

    def test_live_state_survives_the_swap(self):
        coord, rt = make_runtime()
        m = rt.engine.models["rain_3h"]
        m.ev_live = 3
        m.discarded = 2
        rt.engine.pending.append(rt.engine._new_entry(1.0, True, [0.0] * N_POOL))
        learn(rt)
        assert m.ev_live == 3 and m.discarded == 2 and rt.engine.pending
        assert m.ev_hist > 0


class TestRecorderCall:
    def test_statistics_are_requested_hourly_for_the_mapped_entities(self):
        import sys
        import types

        calls: dict = {}

        def list_statistic_ids(hass, statistic_ids=None, statistic_type=None):
            calls["list"] = statistic_ids
            return [{"statistic_id": e, "unit_of_measurement": "x", "has_sum": False} for e in statistic_ids]

        def statistics_during_period(hass, start, end, ids, period, units, types_):
            calls["period"] = (start, end, set(ids), period, units, set(types_))
            return {e: [] for e in ids}

        stats = types.ModuleType("homeassistant.components.recorder.statistics")
        stats.list_statistic_ids = list_statistic_ids
        stats.statistics_during_period = statistics_during_period
        recorder = types.ModuleType("homeassistant.components.recorder")
        recorder.statistics = stats
        coord, rt = make_runtime()
        rt_fetch = pattern_runtime.PatternRuntime._fetch_statistics
        with patch.dict(
            sys.modules,
            {"homeassistant.components.recorder": recorder, "homeassistant.components.recorder.statistics": stats},
        ):
            meta, rows = rt_fetch(rt, {"sensor.t", "sensor.r"}, NOW - timedelta(days=365), NOW)
        assert calls["list"] == {"sensor.t", "sensor.r"}
        start, end, ids, period, units, kinds = calls["period"]
        assert (end - start).days == 365 and ids == {"sensor.t", "sensor.r"}
        assert period == "hour" and units is None
        assert kinds == {"mean", "min", "max", "sum", "state"}
        assert set(meta) == {"sensor.t", "sensor.r"} and set(rows) == {"sensor.t", "sensor.r"}


class TestAvailability:
    def test_missing_rain_statistics_are_reported_per_target(self):
        stats = year_of_statistics(drop={"sensor.r"})
        coord, rt = make_runtime(stats=stats)
        learn(rt)
        t = rt.engine.history_learn["targets"]
        for tid in ("rain_1h", "rain_3h", "rain_6h", "frost_12h", "heat_24h", "storm_3h"):
            assert t[tid]["status"] == "unavailable", tid
            assert t[tid]["reason"] == "history: unavailable (no statistics for sensor.r)"
        assert t["gust_3h"]["status"] == "ok"  # gusts do not need rain
        assert rt.engine.history_learn["status"] == "partial"
        assert "sensor.r" in rt.engine.history_learn["reason"]
        assert rt.engine.models["rain_3h"].n_updates == 0 and rt.engine.models["gust_3h"].n_updates > 0
        assert rt.engine.models["rain_3h"].maturity == "collecting"

    def test_unmapped_sensor_is_explained(self):
        sources = {k: v for k, v in SOURCES.items() if k != "wind_gust"}
        coord, rt = make_runtime(sources=sources)
        learn(rt)
        t = rt.engine.history_learn["targets"]
        assert t["gust_3h"]["reason"] == "history: unavailable (no sensor mapped for gust)"
        assert t["rain_3h"]["status"] == "ok"

    def test_no_lightning_source_means_no_storm_target(self):
        sources = {k: v for k, v in SOURCES.items() if k != SRC_LIGHTNING_COUNT}
        coord, rt = make_runtime(sources=sources)
        learn(rt)
        assert "storm_3h" not in rt.engine.history_learn["targets"]

    def test_internet_storm_uses_the_blitzortung_counter_statistics(self):
        sources = {k: v for k, v in SOURCES.items() if k != SRC_LIGHTNING_COUNT}
        meta, rows = year_of_statistics()
        meta["sensor.blitzortung_lightning_counter"] = dict(
            meta.pop("sensor.l"), statistic_id="sensor.blitzortung_lightning_counter"
        )
        rows["sensor.blitzortung_lightning_counter"] = rows.pop("sensor.l")
        coord, rt = make_runtime({CONF_PATTERN_STORM_INTERNET_LIGHTNING: True}, (meta, rows), sources)
        with patch.object(
            pattern_runtime,
            "find_blitzortung_entities",
            return_value={SRC_LIGHTNING_COUNT: "sensor.blitzortung_lightning_counter"},
        ):
            learn(rt)
        assert rt.engine.history_learn["targets"]["storm_3h"]["status"] == "ok"
        assert rt.engine.data_source("storm_3h") == "internet"

    def test_a_statistic_without_cumulative_data_is_unavailable(self):
        meta, rows = year_of_statistics()
        meta["sensor.r"]["has_sum"] = False
        rows["sensor.r"] = []
        coord, rt = make_runtime(stats=(meta, rows))
        learn(rt)
        assert "no cumulative statistics for sensor.r" in rt.engine.history_learn["targets"]["rain_3h"]["reason"]

    def test_recorder_failure_is_reported_and_remains_immediately_retryable(self):
        class Broken:
            async def async_add_executor_job(self, fn, *args):
                raise OSError("database is locked")

        coord, rt = make_runtime()
        learn(rt, recorder=Broken())
        t = rt.engine.history_learn["targets"]
        assert all(v["status"] == "unavailable" and "recorder error" in v["reason"] for v in t.values())
        assert all(m.n_updates == 0 for m in rt.engine.models.values())
        now = NOW.timestamp()
        assert set(rt.engine.targets_needing_replay(now + 3600)) == set(rt.engine.models)
        assert set(rt.engine.targets_needing_replay(now + PATTERN_HISTORY_RETRY_S + 10)) == set(rt.engine.models)

    def test_recorder_not_running_never_raises(self):
        coord, rt = make_runtime()

        async def go():
            with (
                patch.object(pattern_runtime, "_recorder_instance", side_effect=KeyError("recorder")),
                patch.object(pattern_runtime.dt_util, "utcnow", return_value=NOW),
            ):
                await rt.async_learn_history()

        asyncio.run(go())
        assert rt.engine.history_learn["status"] == "unavailable"

    def test_short_history_uses_what_exists(self):
        meta, rows = year_of_statistics()
        keep = START_TS + (N - 40 * 24) * 3600.0  # only the last 40 days exist
        rows = {k: [r for r in v if r["start"] >= keep] for k, v in rows.items()}
        coord, rt = make_runtime(stats=(meta, rows))
        learn(rt)
        assert rt.engine.history_learn["targets"]["rain_3h"]["status"] == "ok"
        assert 20 < rt.engine.history_learn["span_days"] < 45


class TestResetAndThresholds:
    def test_threshold_change_replays_only_that_target(self):
        coord, rt = make_runtime()
        learn(rt)
        snapshot = rt.engine.to_dict()
        before_std = rt.engine.std.to_dict()
        before_w = {t: list(m.w) for t, m in rt.engine.models.items()}

        coord2, rt2 = make_runtime({"thresh_freeze_c": 2.0})

        async def reload():
            from .test_pattern_forecast_integration import TestStoreWiring

            await rt2.async_load(TestStoreWiring.FakeStore(snapshot))

        asyncio.run(reload())
        assert rt2.engine.targets_needing_replay(NOW.timestamp()) == ["frost_12h"]
        assert rt2.engine.models["frost_12h"].n_updates == 0
        learn(rt2)
        assert rt2.engine.models["frost_12h"].n_updates > 1000
        assert rt2.engine.std.to_dict() == before_std  # the shared standardizer is not disturbed
        for tid, w in before_w.items():
            if tid != "frost_12h":
                assert rt2.engine.models[tid].w == w, tid
        assert rt2.engine.models["frost_12h"].label_id == "frost-v1:thr=2.0"

    def test_service_reset_clears_everything_and_schedules_a_new_replay(self):
        coord, rt = make_runtime()
        learn(rt)

        class Store:
            removed = False

            async def async_remove(self):
                Store.removed = True

        rt.store = Store()
        coord._start_once = MagicMock()  # type: ignore[method-assign]
        asyncio.run(coord.async_reset_pattern_forecast())
        assert Store.removed
        assert all(m.n_updates == 0 and m.maturity == "collecting" for m in rt.engine.models.values())
        assert rt.engine.history_learn == {}
        name = coord._start_once.call_args.args[2]
        assert name == "ws_core_pattern_history"
        assert set(rt.engine.targets_needing_replay(NOW.timestamp())) == set(rt.engine.models)

    def test_startup_schedules_one_delayed_replay(self):
        coord, rt = make_runtime()
        src = pathlib.Path(pattern_runtime.__file__).read_text(encoding="utf-8")
        assert "async_learn_history" in src
        from custom_components.ws_core import coordinator as coord_mod

        text = pathlib.Path(coord_mod.__file__).read_text(encoding="utf-8")
        assert "PATTERN_HISTORY_DELAY_S" in text and "ws_core_pattern_history" in text


class TestNormalization:
    """Statistics go through the same unit conversion and calibration as live data."""

    def _history(self, stats, options=None):
        coord, rt = make_runtime(options, stats)
        plan = {
            n: rt.history_entity(n, START_TS) for n in ("temp", "hum", "press", "wind", "gust", "rain", "lightning")
        }
        meta, rows = stats
        return rt.build_history(plan, meta, rows, START_TS, N, need_night=True), rt

    def test_imperial_statistics_match_metric_ones(self):
        h_c, _ = self._history(year_of_statistics(fahrenheit=False))
        h_f, _ = self._history(year_of_statistics(fahrenheit=True))
        for j in (100, 4000, 8000):
            assert h_f.temp[j] == pytest.approx(h_c.temp[j], abs=0.01)
            assert h_f.temp_min[j] == pytest.approx(h_c.temp_min[j], abs=0.01)
            assert h_f.temp_max[j] == pytest.approx(h_c.temp_max[j], abs=0.01)
        rain_c = [v for v in h_c.rain if v]
        rain_f = [v for v in h_f.rain if v]
        assert len(rain_c) == len(rain_f)
        assert sum(rain_f) == pytest.approx(sum(rain_c), rel=0.02)

    def test_calibration_offsets_are_applied(self):
        base, _ = self._history(year_of_statistics())
        cal, _ = self._history(year_of_statistics(), {"cal_temp_c": 1.5, "cal_pressure_hpa": 2.0, "cal_wind_ms": 0.5})
        assert cal.temp[500] == pytest.approx(base.temp[500] + 1.5)
        assert cal.wind[500] == pytest.approx(base.wind[500] + 0.5)
        assert cal.mslp[500] > base.mslp[500] + 1.0

    def test_counter_resets_and_missing_hours(self):
        meta, rows = year_of_statistics(hole=(1000, 1010))
        # a station that resets its state at hour 2000 (no usable "sum")
        meta["sensor.r"]["has_sum"] = False
        for r in rows["sensor.r"]:
            if r["start"] >= START_TS + 2000 * 3600.0:
                r["state"] -= 500.0
        coord, rt = make_runtime(stats=(meta, rows))
        plan = {
            n: rt.history_entity(n, START_TS) for n in ("temp", "hum", "press", "wind", "gust", "rain", "lightning")
        }
        h = rt.build_history(plan, meta, rows, START_TS, N, need_night=False)
        assert h.rain[2000] == 0.0 and all(v is None or v >= 0 for v in h.rain)  # a reset is not negative rain
        assert h.temp[1005] is None and h.rain[1005] is None and h.rain[1010] is None  # holes stay unknown
        assert h.rain[1011] is not None

    def test_holes_in_history_discard_labels_instead_of_saying_no(self):
        stats_full = year_of_statistics()
        stats_hole = year_of_statistics(hole=(3000, 3040))
        _, full = make_runtime(stats=stats_full)
        _, hole = make_runtime(stats=stats_hole)
        learn(full)
        learn(hole)
        for tid in ("rain_6h", "frost_12h", "heat_24h"):
            a = full.engine.history_learn["targets"][tid]["samples"]
            b = hole.engine.history_learn["targets"][tid]["samples"]
            assert b < a, tid
        assert full.engine.models["heat_24h"].n_updates - hole.engine.models["heat_24h"].n_updates > 40


class TestEngineReplay:
    def _hist(self, n=24 * 60, **over):
        base = dict(
            start_ts=START_TS,
            n=n,
            mslp=[1013.0 + math.sin(j / 30.0) for j in range(n)],
            temp=[10.0 + 8.0 * math.sin(j / 24.0 * 2 * math.pi - 2.0) for j in range(n)],
            temp_min=[8.0 + 8.0 * math.sin(j / 24.0 * 2 * math.pi - 2.0) for j in range(n)],
            temp_max=[12.0 + 8.0 * math.sin(j / 24.0 * 2 * math.pi - 2.0) for j in range(n)],
            dpd=[3.0] * n,
            wind=[3.0] * n,
            gust=[6.0] * n,
            rain=[0.0 if j % 17 else 1.0 for j in range(n)],
            strikes=[0.0] * n,
            night_frac=[0.4] * n,
            tz_offset=[7200.0] * n,
        )
        base.update(over)
        return HourlyHistory(**base)

    def test_replay_report_and_masking(self):
        eng = PatternEngine(Thresholds())
        rep = eng.replay(self._hist(), ["rain_3h", "frost_12h"], update_std=True)
        assert rep["rain_3h"]["samples"] > 1000 and rep["frost_12h"]["samples"] > 1000
        assert eng.models["rain_3h"].ev_hist > 10
        assert eng.models["rain_3h"].hist_days > 50
        assert eng.std.n[POOL_INDEX["wind_u"]] == 0
        assert eng.models["gust_3h"].n_updates == 0  # not in the replayed set

    def test_unknown_hours_are_never_labelled_no(self):
        eng = PatternEngine(Thresholds())
        n = 24 * 20
        rain = [None] * n  # the rain statistic is entirely missing
        rep = eng.replay(self._hist(n=n, rain=rain), ["rain_1h"], update_std=True)
        assert rep["rain_1h"]["samples"] == 0 and eng.models["rain_1h"].n_updates == 0
        assert eng.base_rate["rain_1h"][1] == 0

    def test_replay_never_touches_scoring(self):
        eng = PatternEngine(Thresholds())
        eng.replay(self._hist(), ["rain_3h"], update_std=True)
        assert eng.scoring["rain_3h"] == [] and eng.models["rain_3h"].ev_live == 0

    def test_history_survives_a_store_roundtrip(self):
        eng = PatternEngine(Thresholds())
        rep = eng.replay(self._hist(), list(eng.models), update_std=True)
        eng.adopt_replay(
            eng,
            rep,
            {
                t: {"status": "ok", "reason": None, "samples": r["samples"], "events": r["events"]}
                for t, r in rep.items()
            },
            False,
            1e9,
        )
        again, notes = PatternEngine.from_dict(eng.to_dict(), Thresholds())
        assert notes == [] and again.to_dict() == eng.to_dict()
        assert again.history_learn["status"] == "ok"
        assert again.targets_needing_replay(1e9 + 10) == []

    def test_malformed_history_entries_are_dropped_on_load(self):
        eng = PatternEngine(Thresholds())
        data = eng.to_dict()
        data["history_learn"] = {
            "done_at": 5.0,
            "targets": {
                "rain_3h": {"status": 7},
                "gust_3h": {"status": "ok", "attempted_at": 1.0, "reason": None},
                "bogus": {},
            },
        }
        loaded, _ = PatternEngine.from_dict(data, Thresholds())
        assert set(loaded.history_learn["targets"]) == {"gust_3h"}
        assert "rain_3h" in loaded.targets_needing_replay(10.0)

    def test_pool_names_unchanged_by_replay_module(self):
        assert len(POOL) == 23


# ---------------------------------------------------------------------------
# 2.11.1: rain totals recorded as measurement statistics, and the 24 h
# pressure history seeded from the replay
# ---------------------------------------------------------------------------


def measurement_rain(stats):
    """The same year, but with the rain total recorded as a measurement sensor.

    That is what the recorder keeps for e.g. a Shelly WS90 (state_class:
    measurement on a running total): hourly mean/min/max, no sum or state.
    """
    meta, rows = stats
    meta = {k: dict(v) for k, v in meta.items()}
    meta["sensor.r"].update(has_sum=False, has_mean=True)
    rows = dict(rows)
    rows["sensor.r"] = [
        {"start": r["start"], "mean": r["state"], "min": r["state"], "max": r["state"]} for r in rows["sensor.r"]
    ]
    return meta, rows


class TestMeasurementRainTotals:
    def test_cumulative_key_prefers_sum_then_state_then_max(self):
        key = pattern_runtime.PatternRuntime._cumulative_key
        assert key({"has_sum": True}, [{"sum": 1.0, "state": 1.0}]) == "sum"
        assert key({"has_sum": False}, [{"state": 4.0}]) == "state"
        assert key({"has_sum": False}, [{"mean": 4.0, "max": 4.2, "state": None}]) == "max"
        assert key({"has_sum": False, "has_mean": True}, [{"mean": 4.0, "min": 4.0, "max": 4.2}]) == "max"

    def test_hourly_max_gives_the_same_rain_as_the_sum(self):
        stats = year_of_statistics()
        coord, rt = make_runtime(stats=stats)
        plan = {n: rt.history_entity(n, START_TS) for n in ("temp", "hum", "press", "wind", "gust", "rain")}
        from_sum = rt.build_history(plan, *stats, START_TS, N, need_night=False).rain
        from_max = rt.build_history(plan, *measurement_rain(stats), START_TS, N, need_night=False).rain
        assert sum(1 for v in from_max if v is not None) > N // 2
        assert all(
            (a is None) == (b is None) and (a is None or abs(a - b) < 1e-9)
            for a, b in zip(from_sum, from_max, strict=True)
        )

    def test_rain_and_frost_learn_when_the_total_is_a_measurement(self):
        coord, rt = make_runtime(stats=measurement_rain(year_of_statistics()))
        learn(rt)
        t = rt.engine.history_learn["targets"]
        for tid in ("rain_1h", "rain_3h", "rain_6h", "frost_12h"):
            assert t[tid]["status"] == "ok", (tid, t[tid])
            assert t[tid]["samples"] > 1000
        assert rt.engine.models["rain_3h"].ev_hist > 0


class TestReplayMethodRetry:
    def test_targets_that_failed_under_an_older_method_retry_at_once(self):
        coord, rt = make_runtime()
        learn(rt)
        now = NOW.timestamp()
        assert rt.engine.targets_needing_replay(now + 3600) == []
        targets = rt.engine.history_learn["targets"]
        # what 2.11.0 left behind for a measurement-type rain gauge: no method recorded
        targets["rain_3h"] = {"status": "too_short", "reason": "x", "samples": 0, "events": 0, "attempted_at": now}
        assert rt.engine.targets_needing_replay(now + 3600) == ["rain_3h"]

    def test_targets_that_failed_under_the_current_method_wait_a_week(self):
        meta, rows = year_of_statistics()
        rows["sensor.r"] = []
        coord, rt = make_runtime(stats=(meta, rows))
        learn(rt)
        now = NOW.timestamp()
        entry = rt.engine.history_learn["targets"]["rain_3h"]
        assert entry["status"] != "ok" and entry["method"] == PATTERN_HISTORY_METHOD
        assert "rain_3h" not in rt.engine.targets_needing_replay(now + 3600)
        assert "rain_3h" in rt.engine.targets_needing_replay(now + PATTERN_HISTORY_RETRY_S + 10)

    def test_a_malformed_method_counts_as_old(self):
        coord, rt = make_runtime()
        learn(rt)
        now = NOW.timestamp()
        rt.engine.history_learn["targets"]["gust_3h"] = {
            "status": "too_short",
            "reason": None,
            "attempted_at": now,
            "method": "bogus",
        }
        assert rt.engine.targets_needing_replay(now + 60) == ["gust_3h"]


class TestPressureSeed:
    @staticmethod
    def _warm_runtime():
        start = NOW.timestamp() - 38 * 3600
        rows = {
            "sensor.t": [{"start": start + j * 3600, "mean": 20.0} for j in range(38)],
            "sensor.p": [{"start": start + j * 3600, "mean": 1013.0} for j in range(38)],
        }
        meta = {
            eid: {"statistic_id": eid, "unit_of_measurement": unit, "has_mean": True, "has_sum": False}
            for eid, unit in (("sensor.t", "°C"), ("sensor.p", "hPa"))
        }
        coord, rt = make_runtime(stats=(meta, rows))
        rt.engine.history_learn = {
            "targets": {
                tid: {"status": "ok", "method": PATTERN_HISTORY_METHOD, "attempted_at": NOW.timestamp()}
                for tid in rt.engine.active_target_ids()
            }
        }
        return coord, rt

    def test_pressure_warm_start_is_independent_of_partial_target_replay(self):
        coord, rt = self._warm_runtime()
        rt.engine.history_learn["targets"].pop("rain_3h")
        updates = {t: m.n_updates for t, m in rt.engine.models.items() if t != "rain_3h"}
        reads = []
        fetch = rt._fetch_statistics

        def spy(ids, start, end, period="hour"):
            reads.append(((end - start).total_seconds(), set(ids), period))
            return fetch(ids, start, end, period)

        rt._fetch_statistics = spy
        rt._history_job = lambda *args: {
            "trained": rt.engine,
            "report": {},
            "statuses": {
                "rain_3h": {"status": "unavailable", "reason": "no annual history", "samples": 0, "events": 0}
            },
        }
        learn(rt)
        assert (38 * 3600, {"sensor.t", "sensor.p"}, "hour") in reads
        assert rt.engine.pressure_change_24h(NOW.timestamp(), 1013.0) is not None
        assert {t: m.n_updates for t, m in rt.engine.models.items() if t != "rain_3h"} == updates

    def test_recorder_failure_schedules_bounded_retry(self):
        coord, rt = self._warm_runtime()
        fetch = rt._fetch_statistics
        attempts = 0
        scheduled = []
        coord._spawn = lambda coro, name: scheduled.append(coro)

        def flaky(ids, start, end, period="hour"):
            nonlocal attempts
            if period == "hour" and (end - start).total_seconds() == 38 * 3600 and attempts == 0:
                attempts += 1
                raise RuntimeError("recorder temporarily unavailable")
            return fetch(ids, start, end, period)

        rt._fetch_statistics = flaky

        async def run():
            with (
                patch.object(pattern_runtime.dt_util, "utcnow", return_value=NOW),
                patch.object(pattern_runtime, "_recorder_instance", return_value=FakeRecorder()),
            ):
                await rt.async_learn_history()
                assert len(scheduled) == 1
                with patch.object(pattern_runtime.asyncio, "sleep", return_value=None):
                    await scheduled.pop()

        asyncio.run(run())
        assert attempts == 1
        assert rt.engine.pressure_change_24h(NOW.timestamp(), 1013.0) is not None
        assert not scheduled

    def test_failed_annual_replay_retries_without_training_cooldown(self):
        coord, rt = self._warm_runtime()
        rt.engine.history_learn["targets"].pop("rain_3h")
        before = {tid: list(m.w) for tid, m in rt.engine.models.items()}
        attempts = 0
        scheduled = []
        coord._spawn = lambda coro, name: scheduled.append(coro)

        def flaky_replay(*args):
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise OSError("recorder busy")
            return {
                "trained": rt.engine,
                "report": {},
                "statuses": {"rain_3h": {"status": "ok", "reason": None, "samples": 0, "events": 0}},
            }

        rt._history_job = flaky_replay

        async def run():
            with (
                patch.object(pattern_runtime.dt_util, "utcnow", return_value=NOW),
                patch.object(pattern_runtime, "_recorder_instance", return_value=FakeRecorder()),
            ):
                await rt.async_learn_history()
                assert rt.engine.history_learn["targets"]["rain_3h"]["retryable"] is True
                assert len(scheduled) == 1
                with patch.object(pattern_runtime.asyncio, "sleep", return_value=None):
                    await scheduled.pop()

        asyncio.run(run())
        assert attempts == 2
        assert rt.engine.history_learn["targets"]["rain_3h"]["status"] == "ok"
        assert not scheduled
        assert {tid: list(m.w) for tid, m in rt.engine.models.items()} == before

    def test_sea_level_pressure_recovery_without_temperature_statistics(self):
        coord, rt = self._warm_runtime()
        fetch = rt._fetch_statistics

        def pressure_only(ids, start, end, period="hour"):
            meta, rows = fetch(ids, start, end, period)
            if period == "hour":
                meta.pop("sensor.t", None)
                rows.pop("sensor.t", None)
            return meta, rows

        rt._fetch_statistics = pressure_only
        learn(rt)
        assert rt.engine.pressure_change_24h(NOW.timestamp(), 1013.0) is not None

    def test_missing_pressure_history_reports_unavailable_and_retries_are_bounded(self):
        coord, rt = self._warm_runtime()
        rt._fetch_statistics = lambda ids, start, end, period="hour": ({}, {})
        learn(rt)
        assert rt._warm_start["pressure_status"] == "unavailable"
        assert rt.engine.pressure_change_24h(NOW.timestamp(), 1013.0) is None
        for _ in range(5):
            rt._retry_scheduled = False  # simulate each delayed attempt finishing
            rt._schedule_recovery_retry()
        assert rt._retry_count == len(pattern_runtime._RECOVERY_RETRY_S)
        assert rt._warm_start["retry_exhausted"] is True

    def test_unload_cancellation_during_read_does_not_schedule_retry_or_change_weights(self):
        coord, rt = self._warm_runtime()
        scheduled = []
        coord._spawn = lambda coro, name: scheduled.append(coro)
        before = {tid: list(m.w) for tid, m in rt.engine.models.items()}

        async def run():
            started = asyncio.Event()
            hold = asyncio.Event()

            class SlowRecorder:
                async def async_add_executor_job(self, fn):
                    started.set()
                    await hold.wait()
                    return fn()

            async def recent(now):
                return 0

            rt._async_seed_recent = recent
            with (
                patch.object(pattern_runtime.dt_util, "utcnow", return_value=NOW),
                patch.object(pattern_runtime, "_recorder_instance", return_value=SlowRecorder()),
            ):
                task = asyncio.create_task(rt.async_learn_history())
                await started.wait()
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task

        asyncio.run(run())
        assert not scheduled
        assert not rt._history_running
        assert {tid: list(m.w) for tid, m in rt.engine.models.items()} == before

    def test_replay_seeds_a_day_of_pressure(self, learned):
        coord, rt = learned
        eng = rt.engine
        assert len(eng.pressure) == PATTERN_PRESSURE_SLOTS
        first, last = eng.pressure[0][0], eng.pressure[-1][0]
        assert last <= NOW.timestamp() and last - first >= 23.5 * 3600
        assert all(p[0] % 900.0 == 0 for p in eng.pressure)
        # the next live issues all find their reading from 24 h before
        for k in range(4):
            assert eng.pressure_change_24h(NOW.timestamp() + 900.0 * k, 1013.0) is not None

    def test_seed_is_interpolated_between_hourly_means(self):
        n = 30
        mslp = [1000.0 + j for j in range(n)]
        hist = HourlyHistory(
            start_ts=START_TS,
            n=n,
            mslp=mslp,
            temp=[None] * n,
            temp_min=[None] * n,
            temp_max=[None] * n,
            dpd=[None] * n,
            wind=[None] * n,
            gust=[None] * n,
            rain=[None] * n,
            strikes=[None] * n,
            night_frac=[None] * n,
            tz_offset=[0.0] * n,
        )
        pts = dict((t, v) for t, v in PatternEngine.pressure_seed_from_history(hist))
        mid = START_TS + 10 * 3600.0 + 1800.0  # centre of hour 10
        assert pts[mid] == 1010.0
        assert pts[mid + 900.0] == 1010.25
        assert max(pts) == START_TS + (n - 1) * 3600.0 + 1800.0

    def test_seed_never_bridges_a_missing_hour(self):
        n = 30
        mslp: list[float | None] = [1000.0 + j for j in range(n)]
        mslp[20] = None
        hist = HourlyHistory(START_TS, n, mslp, *([[None] * n] * 9), [0.0] * n)
        pts = PatternEngine.pressure_seed_from_history(hist)
        hole_start = START_TS + 19 * 3600.0 + 1800.0
        hole_end = START_TS + 21 * 3600.0 + 1800.0
        assert not any(hole_start < t < hole_end for t, _ in pts)

    def test_live_readings_always_win(self):
        eng = PatternEngine(Thresholds())
        live_ts = NOW.timestamp() - 2 * 3600.0
        eng.pressure.append([live_ts, 990.0])
        seeds = [[live_ts, 1020.0], [live_ts - 900.0, 1019.0], [float("nan"), 1.0]]
        kept = eng.seed_pressure(seeds)
        assert kept == 1
        assert [live_ts, 990.0] in [list(p) for p in eng.pressure]
        assert [live_ts - 900.0, 1019.0] in [list(p) for p in eng.pressure]
        assert len(eng.pressure) == 2
