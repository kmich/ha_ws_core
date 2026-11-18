"""Tests for v3.0.0 Pattern Forecast learning migration, scoped feature reset, and dp_3h alignment."""

from __future__ import annotations

from custom_components.ws_core.const import (
    PATTERN_CORRUPTED_FEATURES,
    PATTERN_HISTORY_FEATURES_METHOD,
    PATTERN_HISTORY_METHOD,
    PATTERN_SCHEMA_VERSION,
)
from custom_components.ws_core.pattern_forecast import (
    N_POOL,
    POOL,
    POOL_INDEX,
    REPLAY_MASKED_FEATURES,
    HourlyHistory,
    PatternEngine,
    Thresholds,
)


def _make_engine() -> PatternEngine:
    eng = PatternEngine(Thresholds())
    for _tid, m in eng.models.items():
        # Seed weights with distinct values
        m.w = [1.0 + 0.1 * i for i in range(len(m.w))]
        m.g2 = [0.5] * len(m.w)
        m.cp_w = list(m.w)
        m.cp_g2 = list(m.g2)
    for i in range(N_POOL):
        eng.std.mean[i] = 10.0 + i
        eng.std.var[i] = 4.0
        eng.std.n[i] = 100
    return eng


class TestScopedFeatureReset:
    """Verify that scoped_reset_features only resets the corrupted standardizer slots and model weights."""

    def test_only_corrupted_standardizer_slots_are_reset(self):
        eng = _make_engine()
        corrupted_slots = {POOL_INDEX[f] for f in PATTERN_CORRUPTED_FEATURES}
        untouched_slots = set(range(N_POOL)) - corrupted_slots

        # Save copies of untouched slot values
        before_mean = list(eng.std.mean)
        before_var = list(eng.std.var)
        before_n = list(eng.std.n)

        touched_targets = eng.scoped_reset_features(PATTERN_CORRUPTED_FEATURES)
        assert len(touched_targets) > 0

        # Corrupted slots are reset to baseline
        for slot in corrupted_slots:
            assert eng.std.mean[slot] == 0.0, POOL[slot]
            assert eng.std.var[slot] == 1.0, POOL[slot]
            assert eng.std.n[slot] == 0, POOL[slot]

        # Untouched slots are byte-for-byte identical
        for slot in untouched_slots:
            assert eng.std.mean[slot] == before_mean[slot], POOL[slot]
            assert eng.std.var[slot] == before_var[slot], POOL[slot]
            assert eng.std.n[slot] == before_n[slot], POOL[slot]

    def test_model_weights_reset_only_for_affected_features(self):
        eng = _make_engine()
        rain_model = eng.models["rain_3h"]
        initial_weights = list(rain_model.w)

        # Check which features in rain_3h are corrupted
        corrupted_in_rain = [f for f in PATTERN_CORRUPTED_FEATURES if f in rain_model.spec.features]
        assert "dp_3h" in corrupted_in_rain
        assert "cloud_deficit" in corrupted_in_rain
        assert len(corrupted_in_rain) == 3

        eng.scoped_reset_features(PATTERN_CORRUPTED_FEATURES)

        # Bias (w[0]) is preserved
        assert rain_model.w[0] == initial_weights[0]

        # Corrupted feature weights are reset to 0.0
        for feat in corrupted_in_rain:
            idx = rain_model.spec.features.index(feat) + 1
            assert rain_model.w[idx] == 0.0
            assert rain_model.g2[idx] == 0.0
            assert rain_model.cp_w[idx] == 0.0

        # Other feature weights are preserved
        for feat in rain_model.spec.features:
            if feat not in PATTERN_CORRUPTED_FEATURES:
                idx = rain_model.spec.features.index(feat) + 1
                assert rain_model.w[idx] == initial_weights[idx], feat


class TestReplayMaskingAndDp3hAlignment:
    """Verify that solar features are masked in replay and dp_3h uses 3h change."""

    def test_solar_features_in_replay_masked_features(self):
        for feat in ("cloud_deficit", "solar_ok", "last_day_clearness", "last_day_clearness_ok"):
            assert feat in REPLAY_MASKED_FEATURES

    def test_replay_does_not_train_solar_features_as_zeros(self):
        eng = _make_engine()
        solar_slots = [
            POOL_INDEX[f] for f in ("cloud_deficit", "solar_ok", "last_day_clearness", "last_day_clearness_ok")
        ]

        # Record standardizer before replay
        n_before = [eng.std.n[s] for s in solar_slots]

        # Dummy history
        n = 30
        hist = HourlyHistory(
            start_ts=1000.0,
            n=n,
            mslp=[1013.0] * n,
            temp=[15.0] * n,
            temp_min=[12.0] * n,
            temp_max=[18.0] * n,
            dpd=[3.0] * n,
            wind=[4.0] * n,
            gust=[6.0] * n,
            rain=[0.0] * n,
            strikes=[0.0] * n,
            night_frac=[0.5] * n,
            tz_offset=[0.0] * n,
        )

        eng.replay(hist, ["rain_3h"], update_std=True)

        # Standardizer n for solar slots should NOT have incremented
        for s, nb in zip(solar_slots, n_before, strict=True):
            assert eng.std.n[s] == nb, POOL[s]

    def test_replay_scoped_features_relearns_dp3h_only(self):
        eng = _make_engine()
        rain_model = eng.models["rain_3h"]
        rain_model.n_updates = 42
        rain_model.ev_live = 5

        dp_slot = POOL_INDEX["dp_3h"]
        dp_idx = rain_model.spec.features.index("dp_3h") + 1
        solar_slots = {
            POOL_INDEX[f] for f in ("cloud_deficit", "solar_ok", "last_day_clearness", "last_day_clearness_ok")
        }

        eng.scoped_reset_features(PATTERN_CORRUPTED_FEATURES)
        assert eng.std.n[dp_slot] == 0
        assert rain_model.w[dp_idx] == 0.0

        # Snapshot everything except dp_3h std slot and dp_3h weights
        saved_std_mean = list(eng.std.mean)
        saved_std_var = list(eng.std.var)
        saved_std_n = list(eng.std.n)
        saved_weights = list(rain_model.w)
        saved_base_rate = list(eng.base_rate["rain_3h"])
        saved_cond = [list(c) for c in eng.cond["rain_3h"]]

        # Build 96 hours of history with pressure drops before rain so dp_3h gets non-zero signal
        n = 96
        mslp = []
        rain = []
        for i in range(n):
            phase = i % 24
            # Pressure falls smoothly before hours 12..14 rain
            mslp.append(1018.0 - (1.5 * phase if phase <= 12 else 0.0))
            rain.append(2.0 if 12 <= phase <= 14 else 0.0)

        hist = HourlyHistory(
            start_ts=1700000000.0,
            n=n,
            mslp=mslp,
            temp=[15.0] * n,
            temp_min=[12.0] * n,
            temp_max=[18.0] * n,
            dpd=[3.0] * n,
            wind=[4.0] * n,
            gust=[6.0] * n,
            rain=rain,
            strikes=[0.0] * n,
            night_frac=[0.5] * n,
            tz_offset=[0.0] * n,
        )

        counts = eng.replay_scoped_features(hist, ["rain_3h"], {"dp_3h"})
        assert counts["rain_3h"] > 0
        assert eng.std.n[dp_slot] > 0
        assert rain_model.w[dp_idx] != 0.0

        # Solar slots stay untouched, other slots untouched
        for slot in range(N_POOL):
            if slot == dp_slot:
                continue
            assert eng.std.mean[slot] == saved_std_mean[slot], POOL[slot]
            assert eng.std.var[slot] == saved_std_var[slot], POOL[slot]
            assert eng.std.n[slot] == saved_std_n[slot], POOL[slot]
            if slot in solar_slots:
                assert eng.std.n[slot] == 0

        # Non-dp_3h weights (including bias w[0]) and counters/rates stay byte-for-byte identical
        for idx, val in enumerate(saved_weights):
            if idx != dp_idx:
                assert rain_model.w[idx] == val
        assert rain_model.n_updates == 42
        assert rain_model.ev_live == 5
        assert eng.base_rate["rain_3h"] == saved_base_rate
        assert eng.cond["rain_3h"] == saved_cond

    async def test_migrate_feature_replay_relearns_dp3h_from_recorder(self):
        from datetime import UTC, datetime
        from unittest.mock import AsyncMock, MagicMock, patch

        from custom_components.ws_core import pattern_runtime
        from custom_components.ws_core.const import (
            PATTERN_HISTORY_FEATURES_METHOD,
            PATTERN_HISTORY_METHOD,
        )
        from custom_components.ws_core.pattern_runtime import PatternRuntime

        rt = PatternRuntime.__new__(PatternRuntime)
        rt.engine = _make_engine()
        rt.fingerprint = rt.engine.source_fingerprint
        rt.coord = MagicMock()
        rt.coord.elevation_m = 0.0
        rt.coord.sources = {
            "temperature": "sensor.t",
            "humidity": "sensor.h",
            "pressure": "sensor.p",
            "rain_total": "sensor.r",
        }
        rt.store = MagicMock()
        rt.store.async_save = AsyncMock()
        rt._published = {"rain_3h": {"probability": 10}}

        rain_model = rt.engine.models["rain_3h"]
        rain_model.ev_live = 7
        rain_model.n_updates = 88
        saved_other_weights = {
            feat: rain_model.w[rain_model.spec.features.index(feat) + 1]
            for feat in rain_model.spec.features
            if feat not in PATTERN_CORRUPTED_FEATURES
        }
        saved_bias = rain_model.w[0]
        dp_slot = POOL_INDEX["dp_3h"]
        dp_idx = rain_model.spec.features.index("dp_3h") + 1

        # Simulate pre-v3 state without features_method
        rt.engine.history_learn = {
            "status": "ok",
            "targets": {
                "rain_3h": {"status": "ok", "attempted_at": 1000.0, "reason": None, "method": PATTERN_HISTORY_METHOD}
            },
        }

        n = 96
        mslp = [1018.0 - (1.5 * (i % 24) if (i % 24) <= 12 else 0.0) for i in range(n)]
        rain = [2.0 if 12 <= (i % 24) <= 14 else 0.0 for i in range(n)]
        hist = HourlyHistory(
            start_ts=1700000000.0,
            n=n,
            mslp=mslp,
            temp=[15.0] * n,
            temp_min=[12.0] * n,
            temp_max=[18.0] * n,
            dpd=[3.0] * n,
            wind=[4.0] * n,
            gust=[6.0] * n,
            rain=rain,
            strikes=[0.0] * n,
            night_frac=[0.5] * n,
            tz_offset=[0.0] * n,
        )

        class _FakeRecorder:
            async def async_add_executor_job(self, fn, *args):
                return fn(*args)

        rt.history_entity = lambda name, _ts: f"sensor.{name}"  # type: ignore[method-assign]
        rt._fetch_statistics = lambda ids, s, e: ({"sensor.p": {"statistic_id": "sensor.p"}}, {})  # type: ignore[method-assign]
        rt.build_history = lambda *a, **kw: hist  # type: ignore[method-assign]

        now = datetime(2026, 6, 21, 12, 0, tzinfo=UTC)
        with patch.object(pattern_runtime, "_recorder_instance", return_value=_FakeRecorder()):
            retry_needed = await rt._async_migrate_feature_replay(now)

        assert retry_needed is False
        assert rt.engine.history_learn["features_method"] == PATTERN_HISTORY_FEATURES_METHOD
        assert rt.engine.std.n[dp_slot] > 0
        assert rain_model.w[dp_idx] != 0.0
        # Solar weights/slots remain reset while unrelated state stays untouched
        assert rt.engine.std.n[POOL_INDEX["cloud_deficit"]] == 0
        assert rain_model.w[0] == saved_bias
        for feat, val in saved_other_weights.items():
            assert rain_model.w[rain_model.spec.features.index(feat) + 1] == val, feat
        assert rain_model.ev_live == 7
        assert rain_model.n_updates == 88
        assert rt.store.async_save.await_count == 1

    async def test_migrate_feature_replay_retries_after_recorder_failure(self):
        from datetime import UTC, datetime
        from unittest.mock import AsyncMock, MagicMock, patch

        from custom_components.ws_core import pattern_runtime
        from custom_components.ws_core.const import (
            PATTERN_HISTORY_FEATURES_METHOD,
            PATTERN_HISTORY_METHOD,
        )
        from custom_components.ws_core.pattern_runtime import PatternRuntime

        rt = PatternRuntime.__new__(PatternRuntime)
        rt.engine = _make_engine()
        rt.fingerprint = rt.engine.source_fingerprint
        rt.coord = MagicMock()
        rt.coord.elevation_m = 0.0
        rt.coord.sources = {"temperature": "sensor.t", "humidity": "sensor.h", "pressure": "sensor.p"}
        rt.store = MagicMock()
        rt.store.async_save = AsyncMock()
        rt._published = {}

        rain_model = rt.engine.models["rain_3h"]
        dp_slot = POOL_INDEX["dp_3h"]
        dp_idx = rain_model.spec.features.index("dp_3h") + 1
        rt.engine.history_learn = {
            "status": "ok",
            "targets": {
                "rain_3h": {"status": "ok", "attempted_at": 1000.0, "reason": None, "method": PATTERN_HISTORY_METHOD}
            },
        }

        n = 96
        mslp = [1018.0 - (1.5 * (i % 24) if (i % 24) <= 12 else 0.0) for i in range(n)]
        rain = [2.0 if 12 <= (i % 24) <= 14 else 0.0 for i in range(n)]
        hist = HourlyHistory(
            start_ts=1700000000.0,
            n=n,
            mslp=mslp,
            temp=[15.0] * n,
            temp_min=[12.0] * n,
            temp_max=[18.0] * n,
            dpd=[3.0] * n,
            wind=[4.0] * n,
            gust=[6.0] * n,
            rain=rain,
            strikes=[0.0] * n,
            night_frac=[0.5] * n,
            tz_offset=[0.0] * n,
        )

        class _FakeRecorder:
            async def async_add_executor_job(self, fn, *args):
                return fn(*args)

        rt.history_entity = lambda name, _ts: f"sensor.{name}"  # type: ignore[method-assign]
        now = datetime(2026, 6, 21, 12, 0, tzinfo=UTC)

        # 1. Recorder raises -> scoped reset saved, features_method NOT marked complete, returns True to retry
        rt._fetch_statistics = MagicMock(side_effect=RuntimeError("database is locked"))  # type: ignore[method-assign]
        with patch.object(pattern_runtime, "_recorder_instance", return_value=_FakeRecorder()):
            retry_first = await rt._async_migrate_feature_replay(now)

        assert retry_first is True
        assert "features_method" not in rt.engine.history_learn
        assert rt.engine.std.n[dp_slot] == 0
        assert rain_model.w[dp_idx] == 0.0

        # 2. Recorder recovers -> dp_3h is relearned, features_method stamped, returns False
        rt._fetch_statistics = lambda ids, s, e: ({"sensor.p": {"statistic_id": "sensor.p"}}, {})  # type: ignore[method-assign]
        rt.build_history = lambda *a, **kw: hist  # type: ignore[method-assign]
        with patch.object(pattern_runtime, "_recorder_instance", return_value=_FakeRecorder()):
            retry_second = await rt._async_migrate_feature_replay(now)

        assert retry_second is False
        assert rt.engine.history_learn["features_method"] == PATTERN_HISTORY_FEATURES_METHOD
        assert rt.engine.std.n[dp_slot] > 0
        assert rain_model.w[dp_idx] != 0.0
        assert rt.store.async_save.await_count == 2

    async def test_failed_dp3h_migration_stays_pending_across_ordinary_replay(self):
        from datetime import UTC, datetime
        from unittest.mock import AsyncMock, MagicMock, patch

        from custom_components.ws_core import pattern_runtime
        from custom_components.ws_core.const import (
            PATTERN_HISTORY_FEATURES_METHOD,
            PATTERN_HISTORY_METHOD,
        )
        from custom_components.ws_core.pattern_runtime import PatternRuntime

        rt = PatternRuntime.__new__(PatternRuntime)
        rt.engine = _make_engine()
        rt.fingerprint = rt.engine.source_fingerprint
        rt.coord = MagicMock()
        rt.coord.elevation_m = 0.0
        rt.coord.sources = {
            "temperature": "sensor.t",
            "humidity": "sensor.h",
            "pressure": "sensor.p",
            "rain_total": "sensor.r",
        }
        rt.store = MagicMock()
        rt.store.async_save = AsyncMock()
        rt._published = {}
        rt._warm_start = {}
        rt._history_running = False
        rt._retry_scheduled = False
        rt._retry_count = 0
        rt._recent_failed = False
        rt._recovery_issue_pending = False

        rain_model = rt.engine.models["rain_3h"]
        dp_slot = POOL_INDEX["dp_3h"]
        dp_idx = rain_model.spec.features.index("dp_3h") + 1
        rt.engine.history_learn = {
            "status": "partial",
            "targets": {
                "rain_3h": {"status": "ok", "attempted_at": 1000.0, "reason": None, "method": PATTERN_HISTORY_METHOD}
            },
        }

        n = 96
        mslp = [1018.0 - (1.5 * (i % 24) if (i % 24) <= 12 else 0.0) for i in range(n)]
        rain = [2.0 if 12 <= (i % 24) <= 14 else 0.0 for i in range(n)]
        hist = HourlyHistory(
            start_ts=1700000000.0,
            n=n,
            mslp=mslp,
            temp=[15.0] * n,
            temp_min=[12.0] * n,
            temp_max=[18.0] * n,
            dpd=[3.0] * n,
            wind=[4.0] * n,
            gust=[6.0] * n,
            rain=rain,
            strikes=[0.0] * n,
            night_frac=[0.5] * n,
            tz_offset=[0.0] * n,
        )

        class _FakeRecorder:
            async def async_add_executor_job(self, fn, *args):
                return fn(*args)

        rt.history_entity = lambda name, _ts: f"sensor.{name}"  # type: ignore[method-assign]
        rt._async_forget_misread_replay = AsyncMock(return_value=False)  # type: ignore[method-assign]
        rt._async_seed_recent = AsyncMock(return_value=0)  # type: ignore[method-assign]
        rt._async_seed_pressure = AsyncMock(return_value=(0, False))  # type: ignore[method-assign]
        rt._rebuild_published = MagicMock()  # type: ignore[method-assign]
        rt._schedule_recovery_retry = MagicMock()  # type: ignore[method-assign]
        rt.build_history = lambda *a, **kw: hist  # type: ignore[method-assign]

        # Run 1: dp_3h migration fails on transient recorder error while gust_3h completes ordinary replay.
        # adopt_replay() must NOT stamp features_method so rain_3h stays pending for retry.
        rt._fetch_statistics = MagicMock(side_effect=RuntimeError("database is locked"))  # type: ignore[method-assign]
        trained_other, _ = PatternEngine.from_dict(
            rt.engine.to_dict(), rt.engine.thresholds, rt.engine.storm_source, rt.fingerprint
        )
        rt._history_job = MagicMock(  # type: ignore[method-assign]
            return_value={
                "trained": trained_other,
                "report": {"gust_3h": {"samples": 200, "events": 5, "first": 1700000000.0, "last": 1700720000.0}},
                "statuses": {
                    "gust_3h": {"status": "ok", "reason": None, "samples": 200, "events": 5, "retryable": False}
                },
                "pressure_seed": [],
                "last_rain_ts": None,
            }
        )

        now = datetime(2026, 6, 21, 12, 0, tzinfo=UTC)
        with (
            patch.object(pattern_runtime, "_recorder_instance", return_value=_FakeRecorder()),
            patch("custom_components.ws_core.pattern_runtime.dt_util.utcnow", return_value=now),
        ):
            await rt.async_learn_history()

        assert rt._schedule_recovery_retry.call_count == 1
        assert "features_method" not in (rt.engine.history_learn or {})
        assert rt.engine.std.n[dp_slot] == 0
        assert rain_model.w[dp_idx] == 0.0

        # Run 2: Recorder recovers -> retry completes dp_3h migration and stamps features_method.
        rt._fetch_statistics = lambda ids, s, e: ({"sensor.p": {"statistic_id": "sensor.p"}}, {})  # type: ignore[method-assign]
        with (
            patch.object(pattern_runtime, "_recorder_instance", return_value=_FakeRecorder()),
            patch("custom_components.ws_core.pattern_runtime.dt_util.utcnow", return_value=now),
        ):
            await rt.async_learn_history()

        assert rt.engine.history_learn["features_method"] == PATTERN_HISTORY_FEATURES_METHOD
        assert rt.engine.std.n[dp_slot] > 0
        assert rain_model.w[dp_idx] != 0.0

    def test_dp3h_scale_in_replay(self):
        eng = _make_engine()
        n = 30
        mslp = [1013.0] * n
        # Inject a 3.0 hPa 3-hour pressure fall between index 22 and 25
        mslp[22] = 1013.0
        mslp[25] = 1010.0

        hist = HourlyHistory(
            start_ts=1000.0,
            n=n,
            mslp=mslp,
            temp=[15.0] * n,
            temp_min=[12.0] * n,
            temp_max=[18.0] * n,
            dpd=[3.0] * n,
            wind=[4.0] * n,
            gust=[6.0] * n,
            rain=[0.0] * n,
            strikes=[0.0] * n,
            night_frac=[0.5] * n,
            tz_offset=[0.0] * n,
        )

        # Replay and check standardizer update for dp_3h
        dp_slot = POOL_INDEX["dp_3h"]
        std_before = eng.std.n[dp_slot]
        eng.replay(hist, ["rain_3h"], update_std=True)
        assert eng.std.n[dp_slot] > std_before


class TestDowngradeTolerance:
    """Verify that storage schema remains compatible with earlier versions."""

    def test_schema_version_is_unchanged(self):
        assert PATTERN_SCHEMA_VERSION == 1

    def test_serialized_engine_loads_cleanly(self):
        eng = _make_engine()
        eng.history_learn = {
            "features_method": PATTERN_HISTORY_FEATURES_METHOD,
            "targets": {
                "rain_3h": {"status": "ok", "attempted_at": 1000.0, "reason": None, "method": PATTERN_HISTORY_METHOD}
            },
        }
        d = eng.to_dict()
        loaded, notes = PatternEngine.from_dict(d, eng.thresholds, eng.storm_source, eng.source_fingerprint)
        assert len(notes) == 0
        assert loaded.history_learn.get("features_method") == PATTERN_HISTORY_FEATURES_METHOD
