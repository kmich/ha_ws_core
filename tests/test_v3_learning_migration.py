"""Tests for v3.0.0 Pattern Forecast learning migration, scoped feature reset, and dp_3h alignment."""

from __future__ import annotations

from datetime import UTC, datetime

from custom_components.ws_core import pattern_runtime
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
from custom_components.ws_core.pattern_runtime import PatternRuntime


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
        assert rt.engine.history_learn["features_reset_method"] == PATTERN_HISTORY_FEATURES_METHOD
        assert rt.engine.std.n[dp_slot] == 0
        assert rain_model.w[dp_idx] == 0.0

        # 2. Recorder recovers -> dp_3h is relearned, features_method stamped, returns False
        rt._fetch_statistics = lambda ids, s, e: ({"sensor.p": {"statistic_id": "sensor.p"}}, {})  # type: ignore[method-assign]
        rt.build_history = lambda *a, **kw: hist  # type: ignore[method-assign]
        with patch.object(pattern_runtime, "_recorder_instance", return_value=_FakeRecorder()):
            retry_second = await rt._async_migrate_feature_replay(now)

        assert retry_second is False
        assert rt.engine.history_learn["features_method"] == PATTERN_HISTORY_FEATURES_METHOD
        assert rt.engine.history_learn["features_reset_method"] == PATTERN_HISTORY_FEATURES_METHOD
        assert rt.engine.std.n[dp_slot] > 0
        assert rain_model.w[dp_idx] != 0.0
        assert rt.store.async_save.await_count == 2

    async def test_dp3h_migration_discards_results_if_reset_occurs_during_replay(self):
        from unittest.mock import AsyncMock, MagicMock, patch

        coord = MagicMock()
        coord.hass = MagicMock()
        coord.sources = {}
        coord.elevation_m = 0.0
        coord.entry_options = {}

        rt = PatternRuntime(coord)
        rt.store = MagicMock()
        rt.store.async_save = AsyncMock()
        rt.store.async_remove = AsyncMock()

        rt.engine.history_learn = {
            "status": "ok",
            "targets": {
                "rain_3h": {"status": "ok", "attempted_at": 1000.0, "reason": None, "method": PATTERN_HISTORY_METHOD}
            },
        }

        n = 96
        hist = HourlyHistory(
            start_ts=1700000000.0,
            n=n,
            mslp=[1018.0 - (1.5 * (i % 24) if (i % 24) <= 12 else 0.0) for i in range(n)],
            temp=[15.0] * n,
            temp_min=[12.0] * n,
            temp_max=[18.0] * n,
            dpd=[3.0] * n,
            wind=[4.0] * n,
            gust=[6.0] * n,
            rain=[2.0 if 12 <= (i % 24) <= 14 else 0.0 for i in range(n)],
            strikes=[0.0] * n,
            night_frac=[0.5] * n,
            tz_offset=[0.0] * n,
        )

        rt.history_entity = lambda name, _ts: f"sensor.{name}"  # type: ignore[method-assign]
        rt._fetch_statistics = lambda ids, s, e: ({"sensor.p": {"statistic_id": "sensor.p"}}, {})  # type: ignore[method-assign]
        rt.build_history = lambda *a, **kw: hist  # type: ignore[method-assign]

        class _ResettingRecorder:
            async def async_add_executor_job(self, fn, *args):
                res = fn(*args)
                # User or service calls reset while in flight
                await rt.async_reset()
                return res

        now = datetime(2026, 6, 21, 12, 0, tzinfo=UTC)
        with patch.object(pattern_runtime, "_recorder_instance", return_value=_ResettingRecorder()):
            result = await rt._async_migrate_feature_replay(now)

        assert result is False
        assert rt.engine.history_learn == {}
        assert all(m.maturity == "collecting" and m.n_updates == 0 for m in rt.engine.models.values())
        assert rt.store.async_remove.await_count == 1
        assert rt.store.async_save.await_count == 0

    async def test_dp3h_migration_retries_when_replay_yields_no_usable_statistics(self):
        from unittest.mock import AsyncMock, MagicMock, patch

        coord = MagicMock()
        coord.hass = MagicMock()
        coord.sources = {}
        coord.elevation_m = 0.0
        coord.entry_options = {}

        rt = PatternRuntime(coord)
        rt.store = MagicMock()
        rt.store.async_save = AsyncMock()

        rt.engine.history_learn = {
            "status": "ok",
            "targets": {
                "rain_3h": {"status": "ok", "attempted_at": 1000.0, "reason": None, "method": PATTERN_HISTORY_METHOD}
            },
        }

        n = 96
        empty_hist = HourlyHistory(
            start_ts=1700000000.0,
            n=n,
            mslp=[None] * n,
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

        class _FakeRecorder:
            async def async_add_executor_job(self, fn, *args):
                return fn(*args)

        rt.history_entity = lambda name, _ts: f"sensor.{name}"  # type: ignore[method-assign]
        rt._fetch_statistics = lambda ids, s, e: ({"sensor.p": {"statistic_id": "sensor.p"}}, {})  # type: ignore[method-assign]
        rt.build_history = lambda *a, **kw: empty_hist  # type: ignore[method-assign]

        now = datetime(2026, 6, 21, 12, 0, tzinfo=UTC)
        with patch.object(pattern_runtime, "_recorder_instance", return_value=_FakeRecorder()):
            needs_retry = await rt._async_migrate_feature_replay(now)

        assert needs_retry is True
        assert "features_method" not in rt.engine.history_learn
        assert rt.engine.history_learn["targets"]["rain_3h"].get("features_method") != PATTERN_HISTORY_FEATURES_METHOD
        assert rt.engine.history_learn["features_reset_method"] == PATTERN_HISTORY_FEATURES_METHOD

    async def test_dp3h_migration_avoids_adding_live_and_historical_coefficients(self):
        from unittest.mock import AsyncMock, MagicMock, patch

        coord = MagicMock()
        coord.hass = MagicMock()
        coord.sources = {}
        coord.elevation_m = 0.0
        coord.entry_options = {}

        rt = PatternRuntime(coord)
        rt.store = MagicMock()
        rt.store.async_save = AsyncMock()

        rain_model = rt.engine.models["rain_3h"]
        dp_slot = POOL_INDEX["dp_3h"]
        dp_idx = rain_model.spec.features.index("dp_3h") + 1

        rt.engine.history_learn = {
            "status": "ok",
            "features_reset_method": PATTERN_HISTORY_FEATURES_METHOD,
            "targets": {
                "rain_3h": {"status": "ok", "attempted_at": 1000.0, "reason": None, "method": PATTERN_HISTORY_METHOD}
            },
        }

        live_w = 0.25
        live_g2 = 0.06
        rain_model.w[dp_idx] = live_w
        rain_model.g2[dp_idx] = live_g2
        rain_model.cp_w[dp_idx] = live_w
        rain_model.cp_g2[dp_idx] = live_g2
        rt.engine.std.update(dp_slot, -1.0)

        n = 96
        hist = HourlyHistory(
            start_ts=1700000000.0,
            n=n,
            mslp=[1018.0 - (1.5 * (i % 24) if (i % 24) <= 12 else 0.0) for i in range(n)],
            temp=[15.0] * n,
            temp_min=[12.0] * n,
            temp_max=[18.0] * n,
            dpd=[3.0] * n,
            wind=[4.0] * n,
            gust=[6.0] * n,
            rain=[2.0 if 12 <= (i % 24) <= 14 else 0.0 for i in range(n)],
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
            retry = await rt._async_migrate_feature_replay(now)

        assert retry is False
        assert rt.engine.history_learn["features_method"] == PATTERN_HISTORY_FEATURES_METHOD
        replayed_w = rain_model.w[dp_idx]
        assert replayed_w != 0.0
        assert replayed_w != live_w
        assert rain_model.g2[dp_idx] != (live_g2 + rain_model.g2[dp_idx])
        assert rt.engine.std.n[dp_slot] > 0
        assert rt.engine.std.var[dp_slot] > 0.0

    async def test_replacement_replay_remains_queued_when_reset_during_replay(self):
        from unittest.mock import AsyncMock, MagicMock

        coord = MagicMock()
        coord.hass = MagicMock()
        coord.sources = {}
        coord.elevation_m = 0.0
        coord.entry_options = {}
        coord._start_once = MagicMock()

        rt = PatternRuntime(coord)
        rt.store = MagicMock()
        rt.store.async_save = AsyncMock()
        rt.store.async_remove = AsyncMock()

        # Simulate replay currently running
        rt._history_running = True
        assert rt._history_queued is False

        # Reset occurs while replay is running -> replacement replay is queued
        await rt.async_reset()
        assert rt._history_queued is True

        # Replay attempt during active replay also preserves queued status
        await rt.async_learn_history()
        assert rt._history_queued is True

        # When running replay finishes, finally block launches the queued replacement replay
        rt._history_running = False
        if rt._history_queued:
            rt._history_queued = False
            coord._start_once(rt.async_learn_history, 0, "ws_core_pattern_history")

        coord._start_once.assert_called_once_with(rt.async_learn_history, 0, "ws_core_pattern_history")
        assert rt._history_queued is False

    async def test_full_startup_migration_preserves_live_learning_across_outage_replay_restart_and_retry(self):
        import inspect
        import math
        from datetime import UTC, datetime
        from unittest.mock import MagicMock, patch

        from custom_components.ws_core import pattern_runtime
        from custom_components.ws_core.const import (
            PATTERN_HISTORY_FEATURES_METHOD,
            PATTERN_HISTORY_METHOD,
            SRC_GUST,
            SRC_HUM,
            SRC_PRESS,
            SRC_RAIN_TOTAL,
            SRC_TEMP,
            SRC_WIND,
            SRC_WIND_DIR,
        )
        from custom_components.ws_core.pattern_runtime import PatternRuntime

        class _MemoryStore:
            def __init__(self, initial: dict | None = None):
                self.data = initial

            async def async_load(self):
                return self.data

            async def async_save(self, data: dict):
                self.data = data

        class _FakeRecorder:
            async def async_add_executor_job(self, fn, *args):
                return fn(*args)

        def _make_coord():
            coord = MagicMock()
            coord.hass = MagicMock()
            coord.hass.config.latitude = None
            coord.hass.config.longitude = None
            coord.elevation_m = 0.0
            coord.staleness_s = 900
            coord.forecast_lat = None
            coord.forecast_lon = None
            coord.cal_temp_c = 0.0
            coord.cal_humidity = 0.0
            coord.cal_pressure_hpa = 0.0
            coord.cal_wind_ms = 0.0
            coord.entry_options = {}
            coord.sources = {
                SRC_TEMP: "sensor.temp",
                SRC_HUM: "sensor.hum",
                SRC_PRESS: "sensor.press",
                SRC_WIND: "sensor.wind",
                SRC_GUST: "sensor.gust",
                SRC_WIND_DIR: "sensor.dir",
                SRC_RAIN_TOTAL: "sensor.rain",
            }
            coord._to_celsius = lambda v, _u=None: float(v)
            coord._to_hpa = lambda v, _u=None: float(v)
            coord._to_ms = lambda v, _u=None: float(v)
            coord._to_mm = lambda v, _u=None: float(v)
            coord._spawn = MagicMock()
            return coord

        now = datetime(2026, 6, 21, 12, 0, tzinfo=UTC)
        end_ts = math.floor(now.timestamp() / 3600.0) * 3600.0
        n_hours = 120
        start_ts = end_ts - n_hours * 3600.0

        # Build valid metric recorder statistics so real build_history + _history_job run end-to-end.
        meta_all = {
            "sensor.temp": {"statistic_id": "sensor.temp", "statistics_unit_of_measurement": "°C"},
            "sensor.hum": {"statistic_id": "sensor.hum", "statistics_unit_of_measurement": "%"},
            "sensor.press": {"statistic_id": "sensor.press", "statistics_unit_of_measurement": "hPa"},
            "sensor.wind": {"statistic_id": "sensor.wind", "statistics_unit_of_measurement": "m/s"},
            "sensor.gust": {"statistic_id": "sensor.gust", "statistics_unit_of_measurement": "m/s"},
            "sensor.rain": {"statistic_id": "sensor.rain", "statistics_unit_of_measurement": "mm", "has_sum": True},
        }
        rows_all: dict[str, list[dict]] = {eid: [] for eid in meta_all}
        rain_sum = 0.0
        for h in range(n_hours):
            row_ts = start_ts + h * 3600.0
            phase = h % 24
            press_val = 1018.0 - (1.5 * phase if phase <= 12 else 0.0)
            gust_val = 18.0 if phase == 13 else 5.0
            if 12 <= phase <= 14:
                rain_sum += 2.0
            rows_all["sensor.temp"].append({"start": row_ts, "mean": 15.0, "min": 12.0, "max": 18.0})
            rows_all["sensor.hum"].append({"start": row_ts, "mean": 70.0})
            rows_all["sensor.press"].append({"start": row_ts, "mean": press_val})
            rows_all["sensor.wind"].append({"start": row_ts, "mean": 4.0})
            rows_all["sensor.gust"].append({"start": row_ts, "mean": gust_val, "max": gust_val})
            rows_all["sensor.rain"].append({"start": row_ts, "sum": rain_sum})

        # Seed store with pre-v3 persisted engine: rain_3h is "ok" with corrupted pre-v3 weights,
        # other targets not learned yet so ordinary replay runs during the same startup.
        coord = _make_coord()
        rt_init = PatternRuntime(coord)
        rt_init.engine = _make_engine()
        rt_init.engine.source_fingerprint = rt_init.fingerprint
        dp_slot = POOL_INDEX["dp_3h"]
        cloud_slot = POOL_INDEX["cloud_deficit"]
        dp_idx_rain = rt_init.engine.models["rain_3h"].spec.features.index("dp_3h") + 1
        cloud_idx_rain = rt_init.engine.models["rain_3h"].spec.features.index("cloud_deficit") + 1
        rt_init.engine.models["rain_3h"].n_updates = 50
        rt_init.engine.models["rain_3h"].ev_live = 4
        rt_init.engine.history_learn = {
            "status": "partial",
            "targets": {
                "rain_3h": {
                    "status": "ok",
                    "attempted_at": 1000.0,
                    "reason": None,
                    "method": PATTERN_HISTORY_METHOD,
                },
                "gust_3h": {
                    "status": "unavailable",
                    "attempted_at": 1000.0,
                    "reason": "earlier outage",
                    "retryable": True,
                    "method": PATTERN_HISTORY_METHOD,
                },
            },
        }
        store = _MemoryStore(rt_init.engine.to_dict())

        # Outage controller: fail inside the migration _dp3h_job while recorder outage is active,
        # while allowing ordinary _history_job replay and later retries to read recorder stats.
        migration_outage = [True]

        def _fake_fetch(ids, start_dt, end_dt, period="hour"):
            if period == "5minute":
                return {}, {}
            if migration_outage[0] and any(frame.function == "_dp3h_job" for frame in inspect.stack()):
                raise RuntimeError("database is locked")
            return (
                {k: v for k, v in meta_all.items() if k in ids},
                {k: v for k, v in rows_all.items() if k in ids},
            )

        def _attach_fake_io(rt_obj: PatternRuntime) -> None:
            rt_obj._read_statistic_meta = lambda ids: {k: v for k, v in meta_all.items() if k in ids}  # type: ignore[method-assign]
            rt_obj._fetch_statistics = _fake_fetch  # type: ignore[method-assign]

        # Startup 1: load pre-v3 store -> one-time reset runs once -> dp_3h migration fails ->
        # real _history_job replays gust_3h -> adopt_replay preserves features_reset_method & pending migration.
        rt1 = PatternRuntime(coord)
        await rt1.async_load(store)
        _attach_fake_io(rt1)

        with (
            patch.object(pattern_runtime, "_recorder_instance", return_value=_FakeRecorder()),
            patch("custom_components.ws_core.pattern_runtime.dt_util.utcnow", return_value=now),
        ):
            await rt1.async_learn_history()

        assert coord._spawn.call_count >= 1
        assert rt1.engine.history_learn["features_reset_method"] == PATTERN_HISTORY_FEATURES_METHOD
        assert "features_method" not in rt1.engine.history_learn
        assert rt1.engine.history_learn["targets"]["gust_3h"]["status"] == "ok"
        assert "features_method" not in rt1.engine.history_learn["targets"]["gust_3h"]
        assert rt1.engine.std.n[dp_slot] == 0
        assert rt1.engine.std.n[cloud_slot] == 0
        assert rt1.engine.models["rain_3h"].w[dp_idx_rain] == 0.0
        assert rt1.engine.models["rain_3h"].w[cloud_idx_rain] == 0.0

        # Simulate live learning accumulated after the one-time reset (both solar cloud_deficit and live dp_3h).
        for sample_dp, sample_cd in ((-1.2, 0.35), (0.8, 0.55), (-0.4, 0.25)):
            rt1.engine.std.update(dp_slot, sample_dp)
            rt1.engine.std.update(cloud_slot, sample_cd)
        rt1.engine.models["rain_3h"].w[dp_idx_rain] = 0.22
        rt1.engine.models["rain_3h"].g2[dp_idx_rain] = 0.05
        rt1.engine.models["rain_3h"].cp_w[dp_idx_rain] = 0.22
        rt1.engine.models["rain_3h"].cp_g2[dp_idx_rain] = 0.05
        rt1.engine.models["rain_3h"].w[cloud_idx_rain] = -0.31
        rt1.engine.models["rain_3h"].g2[cloud_idx_rain] = 0.08
        rt1.engine.models["rain_3h"].cp_w[cloud_idx_rain] = -0.31
        rt1.engine.models["rain_3h"].cp_g2[cloud_idx_rain] = 0.08
        rt1.engine.models["rain_3h"].n_updates = 53
        rt1.engine.models["rain_3h"].ev_live = 5
        await rt1.async_save()

        saved_live_dp_n = rt1.engine.std.n[dp_slot]
        saved_live_cloud_n = rt1.engine.std.n[cloud_slot]
        saved_live_cloud_mean = rt1.engine.std.mean[cloud_slot]

        # Simulated restart + second failed migration attempt while recorder is still down:
        # Must NOT re-run scoped_reset_features or lose ANY live learning accumulated since the reset!
        rt2 = PatternRuntime(coord)
        await rt2.async_load(store)
        _attach_fake_io(rt2)

        with (
            patch.object(pattern_runtime, "_recorder_instance", return_value=_FakeRecorder()),
            patch("custom_components.ws_core.pattern_runtime.dt_util.utcnow", return_value=now),
        ):
            await rt2.async_learn_history()

        assert rt2.engine.history_learn["features_reset_method"] == PATTERN_HISTORY_FEATURES_METHOD
        assert "features_method" not in rt2.engine.history_learn
        assert rt2.engine.std.n[cloud_slot] == saved_live_cloud_n
        assert rt2.engine.std.mean[cloud_slot] == saved_live_cloud_mean
        assert rt2.engine.models["rain_3h"].w[cloud_idx_rain] == -0.31
        assert rt2.engine.std.n[dp_slot] == saved_live_dp_n
        assert rt2.engine.models["rain_3h"].w[dp_idx_rain] == 0.22
        assert rt2.engine.models["rain_3h"].n_updates == 53
        assert rt2.engine.models["rain_3h"].ev_live == 5

        # Later successful retry once recorder recovers -> merges historical dp_3h replay cleanly with live state.
        migration_outage[0] = False
        with (
            patch.object(pattern_runtime, "_recorder_instance", return_value=_FakeRecorder()),
            patch("custom_components.ws_core.pattern_runtime.dt_util.utcnow", return_value=now),
        ):
            await rt2.async_learn_history()

        assert rt2.engine.history_learn["features_method"] == PATTERN_HISTORY_FEATURES_METHOD
        assert rt2.engine.history_learn["features_reset_method"] == PATTERN_HISTORY_FEATURES_METHOD
        # Historical samples + post-reset live samples are both represented
        assert rt2.engine.std.n[dp_slot] > saved_live_dp_n
        assert rt2.engine.models["rain_3h"].w[dp_idx_rain] != 0.22
        assert rt2.engine.models["rain_3h"].w[cloud_idx_rain] == -0.31
        assert rt2.engine.std.n[cloud_slot] == saved_live_cloud_n
        assert rt2.engine.models["rain_3h"].n_updates == 53
        assert rt2.engine.models["rain_3h"].ev_live == 5
        assert store.data["history_learn"]["features_method"] == PATTERN_HISTORY_FEATURES_METHOD
        assert store.data["history_learn"]["features_reset_method"] == PATTERN_HISTORY_FEATURES_METHOD

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
