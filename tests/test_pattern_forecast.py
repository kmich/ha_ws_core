"""Tests for the Pattern Forecast engine (pure module, no Home Assistant needed)."""

from __future__ import annotations

import ast
import asyncio
import json
import math
import pathlib
import time
from types import SimpleNamespace

import pytest

from custom_components.ws_core import pattern_forecast as pf
from custom_components.ws_core.const import (
    PATTERN_POOL_ID,
    PATTERN_SCHEMA_VERSION,
    PATTERN_SKILLED_MIN_EVENTS,
)
from custom_components.ws_core.pattern_forecast import (
    N_POOL,
    POOL,
    TARGET_BY_ID,
    TARGETS,
    Instant,
    Observation,
    PatternEngine,
    Standardizer,
    Thresholds,
    label_id,
)

from .pattern_world import STEP_S, T0, World, make_engine

WEEK = 7 * 86400.0


def _planted(kind: str, days: int, seed: int = 3, storm: str | None = None):
    world = World(kind, days, seed=seed)
    eng = make_engine(storm)
    world.run(eng)
    return world, eng


@pytest.fixture(scope="module")
def rain_run():
    return _planted("rain", 40)


@pytest.fixture(scope="module")
def frost_run():
    return _planted("frost", 90)


def _clone(eng: PatternEngine) -> PatternEngine:
    """Independent copy (module-scoped runs are shared, so mutating tests work on a clone)."""
    import copy

    again, _ = PatternEngine.from_dict(
        json.loads(json.dumps(eng.to_dict())), eng.thresholds, eng.storm_source, eng.source_fingerprint, eng.tick_cap_s
    )
    again._now_ts = eng._now_ts
    again._last_issue = copy.deepcopy(eng._last_issue)
    again._last_issue_ts = eng._last_issue_ts
    return again


def _unit(storm: str | None = None, **kw) -> PatternEngine:
    """Engine for hand-fed 60 s ticks (default downtime cap of 3 minutes)."""
    return make_engine(storm, cap=pf.PATTERN_TICK_CAP_S, **kw)


def add_entry(eng: PatternEngine, ts: float, probs: dict[str, float], hourly: bool = True) -> dict:
    """Open a pending entry by hand (zero features) for label-rule unit tests."""
    entry = eng._new_entry(ts, hourly, [0.0] * N_POOL)
    entry["p"] = dict(probs)
    entry["c"] = dict.fromkeys(probs, 0)
    eng.pending.append(entry)
    return entry


def feed(eng: PatternEngine, t_from: float, t_to: float, step: float = 60.0, **fields) -> None:
    ts = t_from
    while ts <= t_to:
        eng.observe(ts, Observation(**fields))
        ts += step


# ---------------------------------------------------------------------------
# Registry, pool and masks
# ---------------------------------------------------------------------------


class TestRegistry:
    def test_pool_and_targets(self):
        assert N_POOL == 23
        assert len(set(POOL)) == 23
        assert [t.target_id for t in TARGETS] == [
            "rain_1h",
            "rain_3h",
            "rain_6h",
            "frost_12h",
            "heat_24h",
            "gust_3h",
            "storm_3h",
        ]

    def test_input_counts_match_the_spec_table(self):
        counts = {t.kind: len(t.features) for t in TARGETS}
        assert counts == {"rain": 14, "frost": 14, "heat": 13, "gust": 10, "storm": 13}
        for t in TARGETS:
            assert set(t.features) <= set(POOL)
            assert len(set(t.features)) == len(t.features)

    def test_only_storm_sees_lightning(self):
        for t in TARGETS:
            assert ("lightning_1h" in t.features) == (t.kind == "storm")

    def test_horizons_and_hourly_training(self):
        assert [TARGET_BY_ID[x].horizon_h for x in ("rain_1h", "rain_3h", "rain_6h", "frost_12h", "heat_24h")] == [
            1,
            3,
            6,
            12,
            24,
        ]
        assert TARGET_BY_ID["frost_12h"].hourly_only and TARGET_BY_ID["heat_24h"].hourly_only
        assert not TARGET_BY_ID["rain_1h"].hourly_only

    def test_no_forecaster_in_any_id(self):
        # DEPRECATED_KEYS_FORECASTER entities are deleted on every setup
        names = [t.target_id for t in TARGETS] + list(pf.FACTOR_KEYS) + list(POOL) + [PATTERN_POOL_ID]
        assert not [n for n in names if "forecaster" in n]

    def test_label_ids(self):
        th = Thresholds()
        assert label_id("rain", th) == "rain-v1:mm=0.2"
        assert label_id("frost", th) == "frost-v1:thr=0.0"
        assert label_id("heat", th) == "heat-v1:thr=30.0"
        assert label_id("gust", th) == "gust-v1:thr=17.0"
        assert label_id("storm", th, "internet") == "storm-v1:km=15:src=internet"
        assert label_id("storm", th, "local") == "storm-v1:km=15:src=local"

    def test_storm_target_only_with_a_source(self):
        assert "storm_3h" not in PatternEngine().models
        assert len(PatternEngine().active_target_ids()) == 6
        assert "storm_3h" in PatternEngine(storm_source="local").models

    def test_no_em_dash_in_module(self):
        src = pathlib.Path(pf.__file__).read_text(encoding="utf-8")
        assert chr(0x2014) not in src


class TestNoNetworkImports:
    def test_module_imports_nothing_network_capable(self):
        src = pathlib.Path(pf.__file__).read_text(encoding="utf-8")
        tree = ast.parse(src)
        absolute: set[str] = set()
        relative: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                absolute.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    relative.add(node.module or "")
                else:
                    absolute.add((node.module or "").split(".")[0])
        assert absolute <= {"__future__", "hashlib", "logging", "math", "collections", "dataclasses", "typing"}
        assert relative == {"const"}  # constants only
        lowered = src.lower()
        for banned in ("aiohttp", "clientsession", "homeassistant", "socket", "urllib", "requests", "asyncio"):
            assert banned not in lowered, banned


# ---------------------------------------------------------------------------
# Standardizer
# ---------------------------------------------------------------------------


class TestStandardizer:
    def test_welford_matches_batch_stats(self):
        s = Standardizer()
        xs = [float(x % 7) + 0.1 * x for x in range(200)]
        for x in xs:
            s.update(0, x)
        mean = sum(xs) / len(xs)
        var = sum((x - mean) ** 2 for x in xs) / len(xs)
        assert s.mean[0] == pytest.approx(mean)
        assert s.var[0] == pytest.approx(var)

    def test_switches_to_slow_ema_after_the_first_week(self):
        s = Standardizer()
        for _ in range(pf.PATTERN_STD_WELFORD_N):
            s.update(0, 10.0)
        for _ in range(500):
            s.update(0, 20.0)
        # slow EMA: 500 samples move the mean only a little toward 20
        assert 10.0 < s.mean[0] < 11.5

    def test_z_is_clipped_and_zero_without_data(self):
        s = Standardizer()
        assert s.z(0, 123.0) == 0.0  # not enough samples yet
        for x in range(100):
            s.update(0, float(x % 3))
        assert s.z(0, 10_000.0) == 5.0
        assert s.z(0, -10_000.0) == -5.0
        assert s.z(0, None) == 0.0

    def test_constant_feature_does_not_divide_by_zero(self):
        s = Standardizer()
        for _ in range(100):
            s.update(3, 1.0)
        assert s.z(3, 1.0) == 0.0
        assert math.isfinite(s.z(3, 2.0))

    def test_roundtrip_and_validation(self):
        s = Standardizer()
        for x in range(50):
            s.update(1, float(x))
        again = Standardizer.from_dict(json.loads(json.dumps(s.to_dict())))
        assert again is not None and again.to_dict() == s.to_dict()
        assert Standardizer.from_dict({"mean": [0.0] * 3, "var": [1.0] * 3, "n": [0] * 3}) is None
        bad = s.to_dict()
        bad["var"][0] = float("nan")
        assert Standardizer.from_dict(bad) is None


# ---------------------------------------------------------------------------
# Learning: a planted rule is found, noise is not
# ---------------------------------------------------------------------------


class TestPlantedRules:
    @pytest.mark.parametrize(
        ("kind", "days", "storm", "tid"),
        [
            ("rain", 40, None, "rain_3h"),
            ("frost", 90, None, "frost_12h"),
            ("heat", 120, None, "heat_24h"),
            ("gust", 50, None, "gust_3h"),
            ("storm", 70, "local", "storm_3h"),
        ],
    )
    def test_target_learns_its_planted_rule(self, kind, days, storm, tid):
        _, eng = _planted(kind, days, storm=storm)
        sk = eng.skill(tid)
        assert sk["bss"] is not None and sk["bss"] > 0.1, sk
        assert eng.models[tid].n_updates > 500
        assert eng.models[tid].maturity == "skilled"
        assert eng.models[tid].ev_live >= PATTERN_SKILLED_MIN_EVENTS[kind]

    def test_rain_learns_the_precursor_direction(self, rain_run):
        _, eng = rain_run
        w = eng.named_weights("rain_3h")
        assert w["dpd"] < 0  # air near saturation raises the chance
        assert w["dp_3h"] < 0  # falling pressure raises the chance

    def test_frost_learns_clear_sky_and_calm(self, frost_run):
        _, eng = frost_run
        w = eng.named_weights("frost_12h")
        assert w["last_day_clearness"] > 0
        assert w["wind_speed"] < 0

    def test_heat_beats_persistence(self):
        _, eng = _planted("heat", 120)
        assert eng.skill("heat_24h")["bss_vs_persistence"] > 0

    @pytest.mark.parametrize("seed", [1, 2])
    def test_pure_noise_never_reaches_skilled(self, seed):
        world = World("noise", 150, seed=seed)
        eng = make_engine("local")
        world.run(eng)
        for tid, m in eng.models.items():
            assert m.maturity != "skilled", tid
            assert m.ev_live >= 20, (tid, m.ev_live)  # plenty of events: the BSS bar is what holds
            bss = eng.skill(tid)["bss"]
            assert bss is not None and bss < 0.02, (tid, bss)

    def test_same_seed_is_deterministic(self):
        a = _planted("rain", 12, seed=7)[1].to_dict()
        b = _planted("rain", 12, seed=7)[1].to_dict()
        assert a == b

    def test_compute_time_budget(self):
        world = World("rain", 6, seed=2)
        eng = make_engine()
        t0 = time.perf_counter()
        world.run(eng)
        elapsed = time.perf_counter() - t0
        calls = world.n + world.n // 3
        assert elapsed / calls < 0.005  # average well under 5 ms per observe/issue call

    def test_state_stays_bounded(self, rain_run, frost_run):
        for _, eng in (rain_run, frost_run):
            assert len(eng.pending) <= pf.PATTERN_PENDING_MAX
            assert len(eng.pressure) <= pf.PATTERN_PRESSURE_SLOTS
            assert len(eng.bins) <= pf.PATTERN_BIN_COUNT
            for rows in eng.scoring.values():
                assert len(rows) <= pf.PATTERN_SCORING_WEEKS + 2
            assert len(json.dumps(eng.to_dict())) < 100_000


# ---------------------------------------------------------------------------
# Issuing: monotone rain, hourly-only targets, explanation
# ---------------------------------------------------------------------------


class TestIssue:
    def test_rain_horizons_are_monotone_at_every_issue(self):
        world = World("rain", 20, seed=5)
        eng = make_engine()
        seen: list[tuple[float, float, float]] = []
        real_issue = eng.issue

        def spy(ts, inst, *a, **kw):
            out = real_issue(ts, inst, *a, **kw)
            if all(out.get(t, {}).get("p") is not None for t in pf.RAIN_CHAIN):
                seen.append(tuple(out[t]["p"] for t in pf.RAIN_CHAIN))
            return out

        eng.issue = spy  # type: ignore[method-assign]
        world.run(eng)
        assert len(seen) > 500
        assert all(p1 <= p3 <= p6 for p1, p3, p6 in seen)

    def test_monotone_even_when_the_raw_models_disagree(self, rain_run):
        eng = _clone(rain_run[1])
        # make the 1 h model far more confident than the 3 h model
        eng.models["rain_1h"].w[0] = 3.0
        eng.models["rain_3h"].w[0] = -3.0
        eng.models["rain_6h"].w[0] = -3.0
        out = eng.issue(
            eng._last_issue_ts + 900.0, Instant(mslp=1013.0, dp_3h=0.0, temp=14.0, dpd=4.0, night_frac_12h=0.3)
        )
        probs = [out[t]["p"] for t in pf.RAIN_CHAIN if out[t]["p"] is not None]
        assert probs == sorted(probs)

    def test_frost_and_heat_train_on_the_hour_only(self):
        world = World("frost", 4, seed=2)
        eng = make_engine()
        world.run(eng)
        assert any(not e["hr"] for e in eng.pending)
        for e in eng.pending:
            if not e["hr"]:
                assert not {"frost_12h", "heat_24h"} & set(e["p"])

    def test_pending_entries_are_dropped_after_a_day(self, frost_run):
        _, eng = frost_run
        oldest = min(e["ts"] for e in eng.pending)
        assert eng._now_ts - oldest <= 86400.0 + 3600.0

    def test_double_issue_in_the_same_minute_is_ignored(self, rain_run):
        eng = _clone(rain_run[1])
        n = len(eng.pending)
        ts = eng._last_issue_ts + 900.0
        inst = Instant(mslp=1013.0, dp_3h=0.0, temp=14.0, dpd=4.0, night_frac_12h=0.3)
        eng.issue(ts, inst)
        n1 = len(eng.pending)
        eng.issue(ts + 10.0, inst)
        assert len(eng.pending) == n1 >= n

    def test_missing_input_pauses_only_the_targets_that_use_it(self):
        world = World("storm", 3, seed=4)
        eng = make_engine("local")
        world.run(eng)
        # night_frac_12h feeds the frost model only
        inst = Instant(mslp=1013.0, dp_3h=0.0, temp=10.0, dpd=3.0, t_max_24h=15.0, night_frac_12h=None)
        out = eng.issue(eng._last_issue_ts + 900.0, inst)
        for tid in ("rain_1h", "rain_3h", "rain_6h", "heat_24h", "gust_3h", "storm_3h"):
            assert out[tid]["p"] is not None, tid
        assert out["frost_12h"]["p"] is None and out["frost_12h"]["reason"] == "waiting_for:night_frac_12h"

    def test_dp_24h_is_missing_for_the_first_day(self):
        eng = make_engine()
        World("rain", 1, seed=1).run(eng)  # exactly 24 h of history
        out = eng._last_issue
        assert out["rain_3h"]["p"] is None
        assert out["rain_3h"]["reason"] == "waiting_for:dp_24h"
        assert out["gust_3h"]["p"] is None
        assert eng.pressure_change_24h(eng._last_issue_ts, 1010.0) is None

    def test_top_factors_are_deterministic_translated_keys(self, rain_run):
        eng = _clone(rain_run[1])
        eng.issue(
            eng._last_issue_ts + 900.0,
            Instant(mslp=1008.0, dp_3h=-2.0, temp=14.0, dpd=0.5, night_frac_12h=0.3, local_hour=15.0),
        )
        out = eng.output("rain_3h")
        factors = out["top_factors"]
        assert 1 <= len(factors) <= 3
        for f in factors:
            assert set(f) == {"factor", "effect"}
            assert f["factor"] in pf.FACTOR_KEYS
            assert f["effect"] in ("raises", "lowers")
        assert {f["factor"] for f in factors} & {"air_near_saturation", "pressure_falling"}
        assert eng.output("rain_3h")["top_factors"] == factors

    def test_short_dry_spell_does_not_claim_it_is_raining(self):
        model = SimpleNamespace(
            spec=SimpleNamespace(kind="rain"),
            contributions=lambda *_: {"dry_hours": (-1.0, 2.0), "rain_1h": (1.0, 1.0)},
        )
        # Below-average dry time is not proof of current rain. Actual rain
        # observations can still produce the raining-now explanation.
        assert pf._top_factors(model, None, [], 12.0) == [{"factor": "raining_now", "effect": "raises"}]
        model.contributions = lambda *_: {"dry_hours": (-1.0, 2.0)}
        assert pf._top_factors(model, None, [], 12.0) == []

    def test_outputs_have_the_documented_shape(self, rain_run):
        _, eng = rain_run
        out = eng.output("rain_3h")
        for key in (
            "target",
            "horizon_h",
            "probability",
            "maturity",
            "progress_pct",
            "brier_skill",
            "usual_rate",
            "issued_at",
            "valid_until",
            "top_factors",
            "samples_trained",
            "events_live",
            "events_from_history",
            "events_required",
        ):
            assert key in out
        assert out["valid_until"] == out["issued_at"] + 3 * 3600
        assert out["horizon_h"] == 3
        sk = eng.skill("rain_3h")
        assert len(sk["reliability"]) == 10
        for key in (
            "brier",
            "brier_usual",
            "brier_persistence",
            "brier_heuristic",
            "bss",
            "bss_vs_persistence",
            "n_scored",
            "events",
        ):
            assert key in sk

    def test_heuristic_brier_is_tracked_when_supplied(self):
        eng = make_engine()
        entry = add_entry(eng, T0, {"rain_1h": 0.3})
        entry["h"]["rain_1h"] = 0.6
        feed(eng, T0 + 60, T0 + 3700, rain_total=0.0)
        sk = eng.skill("rain_1h")
        assert sk["brier_heuristic"] == pytest.approx(0.36)
        assert sk["brier"] == pytest.approx(0.09)


# ---------------------------------------------------------------------------
# Labels: coverage, gaps, counters
# ---------------------------------------------------------------------------


class TestLabels:
    def test_complete_window_without_rain_is_labelled_no(self):
        eng = _unit()
        add_entry(eng, T0, {"rain_1h": 0.4})
        feed(eng, T0 + 60, T0 + 3700, rain_total=5.0)
        m = eng.models["rain_1h"]
        assert m.discarded == 0 and m.n_updates == 1
        assert eng.base_rate["rain_1h"][1] == 1
        assert eng.skill("rain_1h")["n_scored"] == 1

    def test_rain_in_the_window_is_labelled_yes(self):
        eng = _unit()
        add_entry(eng, T0, {"rain_1h": 0.4})
        eng.observe(T0 + 30, Observation(rain_total=5.0))
        feed(eng, T0 + 60, T0 + 1800, rain_total=5.0)
        feed(eng, T0 + 1860, T0 + 3700, rain_total=5.4)
        assert eng.base_rate["rain_1h"][0] > pf.PATTERN_PRIOR_RATE["rain"]
        assert eng.models["rain_1h"].n_updates == 1

    def test_downtime_discards_the_label_instead_of_saying_no(self):
        eng = _unit()
        add_entry(eng, T0, {"rain_1h": 0.4, "rain_3h": 0.4})
        feed(eng, T0 + 60, T0 + 1200, rain_total=5.0)
        # HA was down for 40 minutes, then ticks resume past the 1 h mark
        feed(eng, T0 + 3600, T0 + 3700, rain_total=5.0)
        m = eng.models["rain_1h"]
        assert m.discarded == 1
        assert m.n_updates == 0
        assert eng.skill("rain_1h")["n_scored"] == 0
        assert eng.base_rate["rain_1h"][1] == 0  # the usual rate never saw a fake "no"

    def test_unavailable_rain_sensor_is_never_dry(self):
        eng = _unit()
        add_entry(eng, T0, {"rain_1h": 0.4})
        feed(eng, T0 + 60, T0 + 3700, rain_total=None, temp=10.0)
        m = eng.models["rain_1h"]
        assert m.discarded == 1 and m.n_updates == 0

    def test_ninety_percent_coverage_is_enough(self):
        eng = _unit()
        add_entry(eng, T0, {"rain_1h": 0.4})
        feed(eng, T0 + 60, T0 + 3000, rain_total=5.0)
        feed(eng, T0 + 3300, T0 + 3700, rain_total=5.0)  # a 5 min hole: 3,240 of 3,600 s is still >= 90%
        assert eng.models["rain_1h"].n_updates == 1

    def test_below_ninety_percent_coverage_is_discarded(self):
        eng = _unit()
        add_entry(eng, T0, {"rain_1h": 0.4})
        feed(eng, T0 + 60, T0 + 2700, rain_total=5.0)
        feed(eng, T0 + 3300, T0 + 3700, rain_total=5.0)  # a 10 min hole
        assert eng.models["rain_1h"].n_updates == 0 and eng.models["rain_1h"].discarded == 1

    def test_float_sum_of_tips_still_counts_as_point_two(self):
        eng = _unit()
        add_entry(eng, T0, {"rain_1h": 0.4})
        eng.observe(T0 + 30, Observation(rain_total=12.2))
        feed(eng, T0 + 60, T0 + 3700, rain_total=12.4)  # 12.4 - 12.2 is 0.19999999999999929
        assert eng.base_rate["rain_1h"][0] > pf.PATTERN_PRIOR_RATE["rain"]

    def test_counter_reset_is_not_negative_rain(self):
        eng = _unit()
        add_entry(eng, T0, {"rain_1h": 0.4})
        eng.observe(T0 + 30, Observation(rain_total=400.0))
        feed(eng, T0 + 60, T0 + 1000, rain_total=400.25)
        feed(eng, T0 + 1060, T0 + 3700, rain_total=0.0)  # the counter was reset
        e_rain = eng.base_rate["rain_1h"][0]
        assert eng.counter_resets["rain"] == 1
        assert eng.models["rain_1h"].n_updates == 1
        assert e_rain > pf.PATTERN_PRIOR_RATE["rain"]  # the 0.2 mm before the reset still counts

    def test_reset_to_zero_without_rain_stays_dry(self):
        eng = _unit()
        add_entry(eng, T0, {"rain_1h": 0.4})
        eng.observe(T0 + 30, Observation(rain_total=400.0))
        feed(eng, T0 + 60, T0 + 1000, rain_total=400.0)
        feed(eng, T0 + 1060, T0 + 3700, rain_total=0.0)
        assert eng.base_rate["rain_1h"][0] < pf.PATTERN_PRIOR_RATE["rain"]

    def test_absurd_jump_invalidates_the_window(self):
        eng = _unit()
        add_entry(eng, T0, {"rain_1h": 0.4})
        eng.observe(T0 + 30, Observation(rain_total=1.0))
        feed(eng, T0 + 60, T0 + 1000, rain_total=1.0)
        feed(eng, T0 + 1060, T0 + 3700, rain_total=9000.0)
        assert eng.models["rain_1h"].discarded == 1
        assert eng.models["rain_1h"].n_updates == 0

    def test_frost_uses_the_lowest_temperature_in_the_window(self):
        eng = _unit(frost_c=0.0)
        add_entry(eng, T0, {"frost_12h": 0.3})
        feed(eng, T0 + 60, T0 + 20000, step=60.0, temp=3.0)
        feed(eng, T0 + 20060, T0 + 20300, step=60.0, temp=-0.5)
        feed(eng, T0 + 20360, T0 + 43300, step=60.0, temp=3.0)
        assert eng.base_rate["frost_12h"][0] > pf.PATTERN_PRIOR_RATE["frost"]

    def test_heat_uses_the_highest_temperature_in_the_window(self):
        eng = _unit(heat_c=30.0)
        add_entry(eng, T0, {"heat_24h": 0.3})
        feed(eng, T0 + 60, T0 + 86500, step=60.0, temp=24.0)
        assert eng.base_rate["heat_24h"][0] < pf.PATTERN_PRIOR_RATE["heat"]
        assert eng.models["heat_24h"].n_updates == 1

    def test_gust_label_needs_the_threshold(self):
        eng = _unit(gust_ms=17.0)
        add_entry(eng, T0, {"gust_3h": 0.2})
        feed(eng, T0 + 60, T0 + 4000, step=60.0, gust=10.0)
        feed(eng, T0 + 4060, T0 + 4120, step=60.0, gust=18.0)
        feed(eng, T0 + 4180, T0 + 10900, step=60.0, gust=10.0)
        assert eng.base_rate["gust_3h"][0] > pf.PATTERN_PRIOR_RATE["gust"]

    def test_storm_needs_two_strikes_within_proximity(self):
        eng = _unit("local", storm_km=15.0)
        add_entry(eng, T0, {"storm_3h": 0.2})
        eng.observe(T0 + 30, Observation(strikes_total=100.0))
        feed(eng, T0 + 60, T0 + 4000, step=60.0, strikes_total=100.0)
        eng.observe(T0 + 4060, Observation(strikes_total=101.0, strike_km=5.0))  # one strike: noise
        feed(eng, T0 + 4120, T0 + 10900, step=60.0, strikes_total=101.0)
        one_strike = eng.base_rate["storm_3h"][0]
        assert one_strike < pf.PATTERN_PRIOR_RATE["storm"]

        eng2 = _unit("local", storm_km=15.0)
        add_entry(eng2, T0, {"storm_3h": 0.2})
        eng2.observe(T0 + 30, Observation(strikes_total=100.0))
        feed(eng2, T0 + 60, T0 + 4000, step=60.0, strikes_total=100.0)
        eng2.observe(T0 + 4060, Observation(strikes_total=103.0, strike_km=5.0))
        feed(eng2, T0 + 4120, T0 + 10900, step=60.0, strikes_total=103.0)
        assert eng2.base_rate["storm_3h"][0] > pf.PATTERN_PRIOR_RATE["storm"]

    def test_far_strikes_do_not_count(self):
        eng = _unit("local", storm_km=15.0)
        add_entry(eng, T0, {"storm_3h": 0.2})
        eng.observe(T0 + 30, Observation(strikes_total=0.0))
        feed(eng, T0 + 60, T0 + 4000, step=60.0, strikes_total=0.0)
        eng.observe(T0 + 4060, Observation(strikes_total=40.0, strike_km=60.0))
        feed(eng, T0 + 4120, T0 + 10900, step=60.0, strikes_total=40.0)
        assert eng.base_rate["storm_3h"][0] < pf.PATTERN_PRIOR_RATE["storm"]

    def test_unavailable_storm_source_discards_instead_of_dry(self):
        eng = _unit("internet")
        add_entry(eng, T0, {"storm_3h": 0.2})
        feed(eng, T0 + 60, T0 + 11000, step=60.0, strikes_total=None, temp=10.0)
        m = eng.models["storm_3h"]
        assert m.discarded == 1 and m.n_updates == 0

    def test_a_gap_in_the_world_run_discards_but_never_invents_dry(self):
        world = World("rain", 12, seed=3)
        eng = make_engine()
        # skip 2 h of the world entirely (no observe, no issue)
        orig_observe = eng.observe
        gap_start, gap_end = T0 + 5 * 86400, T0 + 5 * 86400 + 7200

        def observe(ts, obs, tz=0.0):
            if gap_start <= ts < gap_end:
                return
            orig_observe(ts, obs, tz)

        eng.observe = observe  # type: ignore[method-assign]
        world.run(eng)
        assert eng.models["rain_1h"].discarded > 0
        assert eng.models["rain_3h"].discarded > 0
        assert eng.models["rain_1h"].n_updates > 100


# ---------------------------------------------------------------------------
# Events (what maturity counts)
# ---------------------------------------------------------------------------


class TestEvents:
    def test_rain_episodes_are_separated_by_six_dry_hours(self):
        eng = _unit()
        eng.observe(T0, Observation(rain_total=1.0))
        eng.observe(T0 + 60, Observation(rain_total=1.25))  # episode 1
        eng.observe(T0 + 3600, Observation(rain_total=1.5))  # same episode (gap < 6 h)
        eng.observe(T0 + 3600 + 7 * 3600, Observation(rain_total=1.75))  # new episode
        assert eng.models["rain_3h"].ev_live == 2

    def test_a_single_spurious_tip_below_threshold_is_not_an_event(self):
        eng = _unit(rain_mm=0.2)
        eng.observe(T0, Observation(rain_total=1.0))
        eng.observe(T0 + 60, Observation(rain_total=1.1))
        assert eng.models["rain_1h"].ev_live == 0

    def test_frost_nights_count_once_per_night(self):
        eng = _unit()
        for k in range(3):  # three cold ticks on the same night
            eng.observe(T0 + 3600 * k, Observation(temp=-1.0))
        eng.observe(T0 + 86400 + 3600, Observation(temp=-2.0))  # next night
        assert eng.models["frost_12h"].ev_live == 2

    def test_heat_days_count_once_per_local_date(self):
        eng = _unit()
        eng.observe(T0 + 12 * 3600, Observation(temp=31.0), 0.0)
        eng.observe(T0 + 15 * 3600, Observation(temp=32.0), 0.0)
        eng.observe(T0 + 86400 + 13 * 3600, Observation(temp=31.0), 0.0)
        assert eng.models["heat_24h"].ev_live == 2

    def test_heat_date_follows_the_local_offset(self):
        eng = _unit()
        # 23:00 UTC is already the next day at UTC+3
        eng.observe(T0 + 12 * 3600, Observation(temp=31.0), 3 * 3600.0)
        eng.observe(T0 + 23 * 3600, Observation(temp=31.0), 3 * 3600.0)
        assert eng.models["heat_24h"].ev_live == 2

    def test_storm_episode_needs_two_strikes(self):
        eng = _unit("local")
        eng.observe(T0, Observation(strikes_total=10.0))
        eng.observe(T0 + 60, Observation(strikes_total=11.0))
        assert eng.models["storm_3h"].ev_live == 0
        eng.observe(T0 + 120, Observation(strikes_total=12.0))
        assert eng.models["storm_3h"].ev_live == 1
        eng.observe(T0 + 4 * 3600, Observation(strikes_total=20.0))  # >3 h later: new episode
        assert eng.models["storm_3h"].ev_live == 2

    def test_gust_episode_gap(self):
        eng = _unit(gust_ms=17.0)
        eng.observe(T0, Observation(gust=20.0))
        eng.observe(T0 + 3600, Observation(gust=21.0))
        eng.observe(T0 + 3600 + 7 * 3600, Observation(gust=19.0))
        assert eng.models["gust_3h"].ev_live == 2

    def test_events_land_in_the_weekly_aggregate(self):
        eng = _unit()
        eng.observe(T0, Observation(gust=20.0))
        w = eng.window_stats("gust_3h", T0, 52)
        assert w["ev"] == 1


# ---------------------------------------------------------------------------
# Maturity
# ---------------------------------------------------------------------------


def _rows(eng: PatternEngine, tid: str, now: float, spec: list[tuple[int, float, float, int]]) -> None:
    """spec: (weeks_ago, brier_model_sum, brier_usual_sum, events); n fixed at 100."""
    wk_now = int(now // WEEK)
    eng.scoring[tid] = [[float(wk_now - ago), 100.0, bm, bu, bu, 0.0, 0.0, float(ev)] for ago, bm, bu, ev in spec]


class TestMaturity:
    NOW = T0 + 80 * 86400

    def _model(self, tid="frost_12h", days=30.0, events=12):
        eng = make_engine()
        m = eng.models[tid]
        m.first_scored = self.NOW - days * 86400
        m.last_scored = self.NOW
        m.ev_live = events
        return eng, m

    def test_collecting_until_a_week_and_five_events(self):
        eng, m = self._model(days=3.0, events=20)
        eng._update_maturity(m, self.NOW)
        assert m.maturity == "collecting"
        eng, m = self._model(days=30.0, events=4)
        eng._update_maturity(m, self.NOW)
        assert m.maturity == "collecting"
        assert eng.progress_pct(m) == 80

    def test_skilled_then_back_to_learning_when_the_bar_is_not_met(self):
        eng, m = self._model(events=12)
        _rows(eng, "frost_12h", self.NOW, [(1, 9.0, 10.0, 6), (2, 10.0, 10.0, 6)])  # 12 events, BSS 0.05 > 0.02
        eng._update_maturity(m, self.NOW)
        assert m.maturity == "skilled"
        _rows(eng, "frost_12h", self.NOW, [(1, 10.0, 10.0, 6), (2, 10.0, 10.0, 6)])  # BSS 0
        m.maturity = "learning"
        eng._update_maturity(m, self.NOW)
        assert m.maturity == "learning"

    def test_skilled_needs_the_event_count(self):
        eng, m = self._model(events=12)
        _rows(eng, "frost_12h", self.NOW, [(1, 5.0, 10.0, 4)])  # great BSS but only 4 events
        eng._update_maturity(m, self.NOW)
        assert m.maturity == "learning"

    def test_degraded_when_recent_weeks_lose_to_the_usual_rate(self):
        eng, m = self._model(events=30)
        m.maturity = "skilled"
        _rows(eng, "frost_12h", self.NOW, [(1, 12.0, 10.0, 2), (2, 12.0, 10.0, 2), (20, 2.0, 10.0, 20)])
        eng._update_maturity(m, self.NOW)
        assert m.maturity == "degraded"

    def test_off_season_keeps_the_previous_verdict(self):
        eng, m = self._model(events=30)
        m.maturity = "skilled"
        # last 5 weeks hold only 2 events: not enough to judge, even though they look bad
        _rows(eng, "frost_12h", self.NOW, [(1, 12.0, 10.0, 1), (3, 12.0, 10.0, 1), (20, 2.0, 10.0, 28)])
        eng._update_maturity(m, self.NOW)
        assert m.maturity == "skilled"

    def test_degraded_recovers_to_skilled(self):
        eng, m = self._model(events=30)
        m.maturity = "degraded"
        _rows(eng, "frost_12h", self.NOW, [(1, 5.0, 10.0, 4), (2, 5.0, 10.0, 4), (20, 2.0, 10.0, 12)])
        eng._update_maturity(m, self.NOW)
        assert m.maturity == "skilled"

    def test_history_events_leave_collecting_but_never_make_skilled(self):
        eng, m = self._model(events=0)
        m.first_scored = m.last_scored = None
        m.hist_days = 200.0
        m.ev_hist = 40
        eng._update_maturity(m, self.NOW)
        assert m.maturity == "learning"  # no live scoring rows, so no skill
        assert eng.progress_pct(m) == 100

    def test_overall_status(self):
        eng = make_engine()
        assert eng.overall_status() == "collecting"
        eng.models["rain_1h"].maturity = "learning"
        eng._last_issue = {"rain_1h": {"p": 0.2}}
        assert eng.overall_status() == "learning"
        eng.models["rain_3h"].maturity = "skilled"
        eng._last_issue["rain_3h"] = {"p": 0.2}
        assert eng.overall_status() == "active"
        assert eng.skilled_count() == 1

    def test_probability_is_unknown_while_collecting(self, rain_run):
        eng = _clone(rain_run[1])
        assert eng.output("rain_3h")["probability"] is not None
        eng.models["rain_3h"].maturity = "collecting"
        assert eng.output("rain_3h")["probability"] is None
        assert eng.output("rain_3h")["top_factors"] == []

    def test_paused_when_an_input_goes_missing_after_maturing(self, rain_run):
        eng = _clone(rain_run[1])
        eng.models["frost_12h"].maturity = "learning"
        eng._last_issue["frost_12h"] = {"p": None, "reason": "waiting_for:temp", "factors": [], "issued_at": 1.0}
        assert eng.target_status("frost_12h") == "paused"
        assert eng.output("frost_12h")["probability"] is None
        eng.models["frost_12h"].maturity = "collecting"
        assert eng.target_status("frost_12h") == "collecting"


# ---------------------------------------------------------------------------
# Per-target reset
# ---------------------------------------------------------------------------


class TestPerTargetReset:
    def _trained(self):
        world = World("storm", 30, seed=2)
        eng = make_engine("local")
        world.run(eng)
        return eng

    def test_threshold_change_resets_only_its_target(self):
        eng = self._trained()
        before = {tid: (id(m), list(m.w), m.n_updates) for tid, m in eng.models.items()}
        reset = eng.configure(Thresholds(frost_c=2.0), "local")
        assert reset == ["frost_12h"]
        for tid, m in eng.models.items():
            if tid == "frost_12h":
                assert m.n_updates == 0 and m.maturity == "collecting"
                assert m.label_id == "frost-v1:thr=2.0"
                assert eng.scoring[tid] == []
            else:
                assert (id(m), list(m.w), m.n_updates) == before[tid]
        assert eng.models["rain_3h"].n_updates > 0

    def test_each_threshold_maps_to_its_own_target(self):
        for kw, tid in (
            ({"heat_c": 32.0}, "heat_24h"),
            ({"gust_ms": 12.0}, "gust_3h"),
            ({"storm_km": 25.0}, "storm_3h"),
            ({"rain_mm": 0.1}, None),
        ):
            eng = make_engine("local")
            reset = eng.configure(Thresholds(**kw), "local")
            if tid:
                assert reset == [tid]
            else:
                assert reset == ["rain_1h", "rain_3h", "rain_6h"]

    def test_unchanged_configuration_resets_nothing(self):
        eng = self._trained()
        assert eng.configure(Thresholds(), "local") == []

    def test_storm_source_change_resets_only_storm(self):
        eng = self._trained()
        assert eng.models["storm_3h"].n_updates > 0
        rain_w = list(eng.models["rain_3h"].w)
        assert eng.configure(Thresholds(), "internet") == ["storm_3h"]
        assert eng.models["storm_3h"].n_updates == 0
        assert eng.models["storm_3h"].label_id == "storm-v1:km=15:src=internet"
        assert eng.models["rain_3h"].w == rain_w
        assert eng.internet_inputs() == ["storm_3h"]
        assert eng.data_source("storm_3h") == "internet"
        assert eng.data_source("rain_3h") == "local"

    def test_removing_the_storm_source_drops_the_storm_target(self):
        eng = self._trained()
        assert eng.configure(Thresholds(), None) == ["storm_3h"]
        assert "storm_3h" not in eng.models
        assert eng.internet_inputs() == []
        assert not any("storm_3h" in e["p"] for e in eng.pending)

    def test_reset_target_and_reset_all(self):
        eng = self._trained()
        eng.reset_target("rain_3h")
        assert eng.models["rain_3h"].n_updates == 0
        assert eng.models["gust_3h"].n_updates > 0
        eng.reset_all()
        assert all(m.n_updates == 0 for m in eng.models.values())
        assert eng.pending == [] and len(eng.pressure) == 0
        assert eng.thresholds == Thresholds() and eng.storm_source == "local"

    def test_pending_forecasts_of_a_reset_target_are_dropped(self):
        eng = self._trained()
        assert any("frost_12h" in e["p"] for e in eng.pending)
        eng.configure(Thresholds(frost_c=1.0), "local")
        assert not any("frost_12h" in e["p"] for e in eng.pending)


# ---------------------------------------------------------------------------
# Numeric guard
# ---------------------------------------------------------------------------


class TestNumericGuard:
    def test_non_finite_weight_restores_the_checkpoint(self, rain_run):
        eng = _clone(rain_run[1])
        m = eng.models["rain_3h"]
        good = list(m.cp_w)
        m.w[2] = float("nan")
        ok = m.train(eng.std, [0.0] * N_POOL, 1.0, eng._now_ts)
        assert ok is False
        assert m.w == good
        assert all(math.isfinite(v) for v in m.w)

    def test_weights_stay_bounded_under_extreme_input(self):
        eng = make_engine()
        for i in range(N_POOL):
            for x in range(200):
                eng.std.update(i, float(x % 5))
        m = eng.models["rain_3h"]
        feat = [1e9] * N_POOL
        for k in range(2000):
            m.train(eng.std, feat, float(k % 2), T0 + k)
        assert math.sqrt(sum(w * w for w in m.w[1:])) <= pf.PATTERN_WEIGHT_NORM_MAX + 1e-6
        assert all(math.isfinite(w) for w in m.w)
        assert 0.0 < m.predict(eng.std, feat) < 1.0

    def test_learning_rate_has_a_floor(self):
        eng = make_engine()
        m = eng.models["rain_3h"]
        m.g2[1] = 1e12  # AdaGrad has all but stopped
        w0 = m.w[1]
        m._step(1, 0.5)
        assert w0 - m.w[1] == pytest.approx(pf.PATTERN_LEARNING_RATE_FLOOR * 0.5)


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def _roundtrip(eng: PatternEngine, **kw):
    data = json.loads(json.dumps(eng.to_dict()))
    return PatternEngine.from_dict(data, eng.thresholds, eng.storm_source, eng.source_fingerprint, **kw)


class TestPersistence:
    def test_store_roundtrip_is_exact(self, frost_run):
        _, eng = frost_run
        again, notes = _roundtrip(eng)
        assert notes == []
        assert again.to_dict() == eng.to_dict()
        assert again.output("frost_12h")["samples_trained"] == eng.output("frost_12h")["samples_trained"]

    def test_roundtrip_with_storm_and_continued_running(self):
        world, eng = _planted("storm", 25, storm="local")
        again, notes = _roundtrip(eng)
        assert notes == [] and again.to_dict() == eng.to_dict()
        again.tick_cap_s = STEP_S * 1.5
        World("storm", 3, seed=11).run(again, start=eng._now_ts + 900.0)  # restored engine keeps learning
        assert again.models["storm_3h"].n_updates > eng.models["storm_3h"].n_updates

    def test_payload_has_the_documented_keys(self, rain_run):
        _, eng = rain_run
        d = eng.to_dict()
        for key in (
            "schema_version",
            "pool_id",
            "source_fingerprint",
            "standardizer",
            "models",
            "pending",
            "pressure_24h",
            "scoring",
            "reliability",
            "base_rate",
            "cond_freq",
            "history_learn",
        ):
            assert key in d
        assert d["schema_version"] == PATTERN_SCHEMA_VERSION and d["pool_id"] == PATTERN_POOL_ID
        m = d["models"]["rain_3h"]
        for key in ("label_id", "mask_id", "w", "g2", "n_updates", "checkpoint", "maturity", "events"):
            assert key in m
        assert set(m["checkpoint"]) == {"w", "g2", "at"}
        assert set(m["events"]) == {"live", "history"}

    @pytest.mark.parametrize(
        "garbage",
        [None, {}, [], "nope", 42, {"schema_version": 1}, {"schema_version": "x"}, [1, 2, 3]],
    )
    def test_garbage_store_starts_fresh(self, garbage):
        eng, _ = PatternEngine.from_dict(garbage, Thresholds(), "local")
        assert all(m.n_updates == 0 for m in eng.models.values())
        assert eng.overall_status() == "collecting"

    def test_schema_pool_and_fingerprint_mismatch_start_fresh(self, rain_run):
        _, eng = rain_run
        for key, bad in (("schema_version", 99), ("pool_id", "pool-v0"), ("source_fingerprint", "other-station")):
            data = json.loads(json.dumps(eng.to_dict()))
            data[key] = bad
            fresh, notes = PatternEngine.from_dict(data, eng.thresholds, None, eng.source_fingerprint)
            assert all(m.n_updates == 0 for m in fresh.models.values()), key
            assert notes and "discarded" in notes[0]

    def test_corrupt_arrays_reset_only_that_model(self, rain_run):
        _, eng = rain_run
        data = json.loads(json.dumps(eng.to_dict()))
        data["models"]["rain_3h"]["w"] = data["models"]["rain_3h"]["w"][:-1]  # wrong length
        data["models"]["rain_6h"]["w"][1] = None  # not a number
        data["models"]["frost_12h"]["g2"][0] = "x"
        fresh, notes = PatternEngine.from_dict(data, eng.thresholds, None, "")
        assert len(notes) == 3
        for tid in ("rain_3h", "rain_6h", "frost_12h"):
            assert fresh.models[tid].n_updates == 0
        assert fresh.models["rain_1h"].n_updates == eng.models["rain_1h"].n_updates
        assert fresh.models["gust_3h"].n_updates == eng.models["gust_3h"].n_updates

    def test_nan_and_inf_are_rejected(self, rain_run):
        _, eng = rain_run
        for bad in (float("nan"), float("inf")):
            data = eng.to_dict()
            data["models"]["rain_3h"] = dict(data["models"]["rain_3h"], w=[bad] * len(data["models"]["rain_3h"]["w"]))
            fresh, notes = PatternEngine.from_dict(data, eng.thresholds, None, "")
            assert fresh.models["rain_3h"].n_updates == 0 and notes

    def test_label_mismatch_resets_only_that_target_on_load(self, frost_run):
        _, eng = frost_run
        data = json.loads(json.dumps(eng.to_dict()))
        loaded, notes = PatternEngine.from_dict(data, Thresholds(frost_c=2.0), None, "")
        assert loaded.models["frost_12h"].n_updates == 0
        assert loaded.models["rain_3h"].n_updates == eng.models["rain_3h"].n_updates
        assert any("frost_12h" in n for n in notes)
        assert not any("frost_12h" in e["p"] for e in loaded.pending)

    def test_mask_mismatch_resets_that_target(self, rain_run):
        _, eng = rain_run
        data = json.loads(json.dumps(eng.to_dict()))
        data["models"]["gust_3h"]["mask_id"] = "gust-m0:deadbeef00"
        loaded, notes = PatternEngine.from_dict(data, eng.thresholds, None, "")
        assert loaded.models["gust_3h"].n_updates == 0
        assert loaded.models["rain_3h"].n_updates == eng.models["rain_3h"].n_updates
        assert notes

    def test_invalid_pending_entries_are_dropped(self, rain_run):
        _, eng = rain_run
        data = json.loads(json.dumps(eng.to_dict()))
        n = len(data["pending"])
        data["pending"][0]["f"] = data["pending"][0]["f"][:5]
        data["pending"][1]["p"] = {"rain_1h": 7.0}
        data["pending"].append("junk")
        loaded, _ = PatternEngine.from_dict(data, eng.thresholds, None, "")
        assert len(loaded.pending) == n - 2

    def test_restart_mid_window_discards_spanning_labels(self):
        world, eng = _planted("rain", 10, seed=6)
        n_scored = {t: eng.skill(t)["n_scored"] for t in pf.RAIN_CHAIN}
        discarded = {t: eng.models[t].discarded for t in pf.RAIN_CHAIN}
        assert eng.pending
        again, _ = _roundtrip(eng)
        again.tick_cap_s = STEP_S * 1.5
        # HA was down for 7 h: every open window spans the downtime
        ts = eng._now_ts + 7 * 3600
        feed(again, ts, ts + 600, step=60.0, rain_total=1.0, temp=10.0)
        for t in pf.RAIN_CHAIN:
            assert again.skill(t)["n_scored"] == n_scored[t]
        assert sum(again.models[t].discarded for t in pf.RAIN_CHAIN) > sum(discarded.values())
        assert not [e for e in again.pending if "rain_1h" in e["p"] and e["ts"] < eng._now_ts]

    def test_async_load_and_save_with_a_fake_store(self, frost_run):
        _, eng = frost_run

        class FakeStore:
            def __init__(self, data):
                self.data = data
                self.saved = None

            async def async_load(self):
                if isinstance(self.data, Exception):
                    raise self.data
                return self.data

            async def async_save(self, data):
                if self.data == "boom":
                    raise OSError("disk full")
                self.saved = data

        async def go():
            store = FakeStore(json.loads(json.dumps(eng.to_dict())))
            loaded = await pf.async_load_engine(store, eng.thresholds, None, "")
            assert loaded.to_dict() == eng.to_dict()
            await pf.async_save_engine(store, loaded)
            assert store.saved == eng.to_dict()
            # unreadable / failing stores never raise
            fresh = await pf.async_load_engine(FakeStore(ValueError("corrupt json")), eng.thresholds, None, "")
            assert all(m.n_updates == 0 for m in fresh.models.values())
            await pf.async_save_engine(FakeStore("boom"), loaded)

        asyncio.run(go())
