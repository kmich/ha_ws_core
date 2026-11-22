"""Tests for v3.0.0 Pattern Forecast learning migration, scoped feature reset, and dp_3h alignment."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from custom_components.ws_core import pattern_runtime
from custom_components.ws_core.const import (
    PATTERN_CORRUPTED_FEATURES,
    PATTERN_HISTORY_FEATURES_METHOD,
    PATTERN_HISTORY_METHOD,
    PATTERN_SCHEMA_VERSION,
    PATTERN_STD_MIN_N,
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


class _FakeRecorder:
    async def async_add_executor_job(self, fn, *args):
        return fn(*args)


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

    async def test_reset_during_the_pre_migration_backup_wins(self):
        from unittest.mock import AsyncMock, MagicMock

        coord = MagicMock()
        coord.hass = MagicMock()
        coord.sources = {}
        coord.elevation_m = 0.0
        coord.entry_options = {}

        rt = PatternRuntime(coord)
        rt.store = MagicMock()
        rt.store.async_save = AsyncMock()
        rt.store.async_remove = AsyncMock()
        rt.store.async_load = AsyncMock(return_value=None)
        rt.engine.history_learn = {
            "status": "ok",
            "targets": {
                "rain_3h": {"status": "ok", "attempted_at": 1000.0, "reason": None, "method": PATTERN_HISTORY_METHOD}
            },
        }

        async def _slow_backup_save(_payload):
            await rt.async_reset()  # the user resets learning while the backup is written

        rt.backup_store = MagicMock()
        rt.backup_store.async_load = AsyncMock(return_value=None)
        rt.backup_store.async_save = AsyncMock(side_effect=_slow_backup_save)

        result = await rt._async_migrate_feature_replay(datetime(2026, 6, 21, 12, 0, tzinfo=UTC))

        assert result is False
        rt.backup_store.async_save.assert_awaited_once()
        assert rt.engine.history_learn == {}  # the pre-reset targets were not written back
        assert all(m.maturity == "collecting" and m.n_updates == 0 for m in rt.engine.models.values())
        assert rt.store.async_save.await_count == 0

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
            coord._spawn = MagicMock(
                side_effect=lambda coro, _name=None: coro.close() if hasattr(coro, "close") else None
            )
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
        legacy_payload = rt_init.engine.to_dict()
        legacy_payload.pop("features_migration_pending")
        for target in legacy_payload["history_learn"]["targets"].values():
            target["method"] = PATTERN_HISTORY_METHOD - 1
        store = _MemoryStore(legacy_payload)

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

    async def test_queued_replay_dropped_when_entry_unloads_or_cancels(self):
        import asyncio
        from unittest.mock import AsyncMock, MagicMock, patch

        coord = MagicMock()
        coord.hass = MagicMock()
        coord.sources = {}
        coord.elevation_m = 0.0
        coord.entry_options = {}
        coord._stopped = False
        coord._start_once = MagicMock()
        coord._spawn = MagicMock()

        rt = PatternRuntime(coord)
        rt.store = MagicMock()
        rt.store.async_save = AsyncMock()
        rt.store.async_remove = AsyncMock()

        # Case 1: CancelledError raised during async_learn_history
        rt._history_queued = True
        with patch.object(rt, "_async_forget_misread_replay", side_effect=asyncio.CancelledError()):
            import pytest

            with pytest.raises(asyncio.CancelledError):
                await rt.async_learn_history()

        assert rt._history_running is False
        assert rt._history_queued is False
        coord._start_once.assert_not_called()
        coord._spawn.assert_not_called()

        # Case 2: Coordinator stopped when async_learn_history is called
        coord._stopped = True
        rt._history_queued = True
        await rt.async_learn_history()
        assert rt._history_running is False
        assert rt._history_queued is False
        coord._start_once.assert_not_called()
        coord._spawn.assert_not_called()

        # Case 3: Coordinator stopped during async_learn_history run
        coord._stopped = False
        rt._history_queued = True

        async def _stop_coord(*_args, **_kwargs):
            coord._stopped = True
            return False

        with (
            patch.object(rt, "_async_forget_misread_replay", side_effect=_stop_coord),
            patch.object(rt, "_async_migrate_feature_replay", return_value=False),
            patch.object(rt, "_async_seed_recent", return_value=0),
            patch.object(rt, "_async_seed_pressure", return_value=(0, False)),
        ):
            await rt.async_learn_history()

        assert rt._history_running is False
        assert rt._history_queued is False
        coord._start_once.assert_not_called()
        coord._spawn.assert_not_called()

    async def test_dp3h_migration_requires_samples_after_scaler_warms_up(self):
        from unittest.mock import AsyncMock, MagicMock, patch

        coord = MagicMock()
        coord.hass = MagicMock()
        coord.sources = {}
        coord.elevation_m = 0.0
        coord.entry_options = {}

        rt = PatternRuntime(coord)
        rt.store = MagicMock()
        rt.store.async_save = AsyncMock()

        eng = rt.engine
        eng.history_learn = {
            "features_method": 3,
            "features_reset_method": 3,
            "targets": {
                "rain_3h": {
                    "status": "ok",
                    "attempted_at": 1000.0,
                    "reason": None,
                    "method": PATTERN_HISTORY_METHOD,
                    "features_method": 3,
                },
            },
        }

        # Case A: history length is 35 (yields 11 vectors, < PATTERN_STD_MIN_N = 20) -> standardizer cold, 0 samples trained
        n_short = 35
        hist_short = HourlyHistory(
            start_ts=1700000000.0,
            n=n_short,
            mslp=[1013.0] * n_short,
            temp=[15.0] * n_short,
            temp_min=[12.0] * n_short,
            temp_max=[18.0] * n_short,
            dpd=[3.0] * n_short,
            wind=[4.0] * n_short,
            gust=[6.0] * n_short,
            rain=[2.0] * n_short,
            strikes=[0.0] * n_short,
            night_frac=[0.5] * n_short,
            tz_offset=[0.0] * n_short,
        )

        counts_short = eng.replay_scoped_features(hist_short, ["rain_3h"], {"dp_3h"})
        assert counts_short["rain_3h"] == 0
        assert eng.std.n[POOL_INDEX["dp_3h"]] == (n_short - 24)

        rt.history_entity = lambda name, _ts: f"sensor.{name}"  # type: ignore[method-assign]
        rt._fetch_statistics = lambda ids, s, e: ({"sensor.p": {"statistic_id": "sensor.p"}}, {})  # type: ignore[method-assign]
        rt.build_history = lambda *a, **kw: hist_short  # type: ignore[method-assign]

        now = datetime(2026, 6, 21, 12, 0, tzinfo=UTC)
        with patch.object(pattern_runtime, "_recorder_instance", return_value=_FakeRecorder()):
            retry = await rt._async_migrate_feature_replay(now)

        assert retry is True
        assert rt.engine.history_learn["targets"]["rain_3h"].get("features_method") != PATTERN_HISTORY_FEATURES_METHOD
        assert rt.engine.history_learn.get("features_method") != PATTERN_HISTORY_FEATURES_METHOD

        # Case B: history length is 60 (yields 36 vectors, >= PATTERN_STD_MIN_N = 20) -> warm standardizer, samples trained after row 20
        n_long = 60
        mslp_long = [1015.0 - (0.5 * (i % 6)) for i in range(n_long)]
        rain_long = [2.0 if (i % 6) == 3 else 0.0 for i in range(n_long)]
        hist_long = HourlyHistory(
            start_ts=1700000000.0,
            n=n_long,
            mslp=mslp_long,
            temp=[15.0] * n_long,
            temp_min=[12.0] * n_long,
            temp_max=[18.0] * n_long,
            dpd=[3.0] * n_long,
            wind=[4.0] * n_long,
            gust=[6.0] * n_long,
            rain=rain_long,
            strikes=[0.0] * n_long,
            night_frac=[0.5] * n_long,
            tz_offset=[0.0] * n_long,
        )

        counts_long = eng.replay_scoped_features(hist_long, ["rain_3h"], {"dp_3h"})
        # 36 vectors total, first 20 vectors warm up the scaler, remaining 16 vectors train
        assert counts_long["rain_3h"] > 0
        assert eng.std.n[POOL_INDEX["dp_3h"]] >= PATTERN_STD_MIN_N

        rt.build_history = lambda *a, **kw: hist_long  # type: ignore[method-assign]
        with patch.object(pattern_runtime, "_recorder_instance", return_value=_FakeRecorder()):
            retry_long = await rt._async_migrate_feature_replay(now)

        assert retry_long is False
        assert rt.engine.history_learn["targets"]["rain_3h"]["features_method"] == PATTERN_HISTORY_FEATURES_METHOD
        assert rt.engine.history_learn["features_method"] == PATTERN_HISTORY_FEATURES_METHOD

    async def test_dp3h_migration_preserves_scale_used_by_already_trained_targets(self):
        from unittest.mock import AsyncMock, MagicMock, patch

        coord = MagicMock()
        coord.hass = MagicMock()
        coord.sources = {}
        coord.elevation_m = 0.0
        coord.entry_options = {}

        rt = PatternRuntime(coord)
        rt.store = MagicMock()
        rt.store.async_save = AsyncMock()

        eng = rt.engine
        dp_slot = POOL_INDEX["dp_3h"]

        # Suppose rain_3h was already trained/migrated to method 4 with an established standardizer scale
        eng.std.mean[dp_slot] = 1012.5
        eng.std.var[dp_slot] = 4.2
        eng.std.n[dp_slot] = 100

        rain_model = eng.models["rain_3h"]
        rain_dp_idx = rain_model.spec.features.index("dp_3h") + 1
        rain_model.w[rain_dp_idx] = -0.35
        rain_model.cp_w[rain_dp_idx] = -0.35

        # gust_3h needs migration (features_method = 3)
        gust_model = eng.models["gust_3h"]
        gust_dp_idx = gust_model.spec.features.index("dp_3h") + 1
        gust_model.w[gust_dp_idx] = 0.0

        eng.history_learn = {
            "features_method": 3,
            "features_reset_method": 4,  # one-time reset already occurred earlier
            "targets": {
                "rain_3h": {
                    "status": "ok",
                    "attempted_at": 1000.0,
                    "reason": None,
                    "method": PATTERN_HISTORY_METHOD,
                    "features_method": PATTERN_HISTORY_FEATURES_METHOD,
                },
                "gust_3h": {
                    "status": "ok",
                    "attempted_at": 1000.0,
                    "reason": None,
                    "method": PATTERN_HISTORY_METHOD,
                    "features_method": 3,
                },
            },
        }

        # Provide a 48h history with different pressure dynamics
        n = 48
        mslp = [1000.0 + (i * 0.1) for i in range(n)]
        gust = [15.0 if (i % 6) == 0 else 5.0 for i in range(n)]
        hist = HourlyHistory(
            start_ts=1700000000.0,
            n=n,
            mslp=mslp,
            temp=[15.0] * n,
            temp_min=[12.0] * n,
            temp_max=[18.0] * n,
            dpd=[3.0] * n,
            wind=[4.0] * n,
            gust=gust,
            rain=[0.0] * n,
            strikes=[0.0] * n,
            night_frac=[0.5] * n,
            tz_offset=[0.0] * n,
        )

        rt.history_entity = lambda name, _ts: f"sensor.{name}"  # type: ignore[method-assign]
        rt._fetch_statistics = lambda ids, s, e: ({"sensor.p": {"statistic_id": "sensor.p"}}, {})  # type: ignore[method-assign]
        rt.build_history = lambda *a, **kw: hist  # type: ignore[method-assign]

        now = datetime(2026, 6, 21, 12, 0, tzinfo=UTC)
        with patch.object(pattern_runtime, "_recorder_instance", return_value=_FakeRecorder()):
            retry = await rt._async_migrate_feature_replay(now)

        assert retry is False
        # The established scale in eng.std used by rain_3h MUST be preserved exactly!
        assert eng.std.mean[dp_slot] == 1012.5
        assert eng.std.var[dp_slot] == 4.2
        assert eng.std.n[dp_slot] == 100

        # rain_3h weight is preserved
        assert rain_model.w[rain_dp_idx] == -0.35

        # gust_3h weight was trained and migrated
        assert gust_model.w[gust_dp_idx] != 0.0
        assert eng.history_learn["targets"]["gust_3h"]["features_method"] == PATTERN_HISTORY_FEATURES_METHOD
        assert eng.history_learn["features_method"] == PATTERN_HISTORY_FEATURES_METHOD

    async def test_dp3h_migration_preserves_scale_for_live_only_models(self):
        from unittest.mock import AsyncMock, MagicMock, patch

        coord = MagicMock()
        coord.hass = MagicMock()
        coord.sources = {}
        coord.elevation_m = 0.0
        coord.entry_options = {}

        rt = PatternRuntime(coord)
        rt.store = MagicMock()
        rt.store.async_save = AsyncMock()

        eng = rt.engine
        dp_slot = POOL_INDEX["dp_3h"]

        # Suppose the station has warm live standardizer data
        eng.std.mean[dp_slot] = 1014.2
        eng.std.var[dp_slot] = 3.8
        eng.std.n[dp_slot] = 80

        # gust_3h is a live-only model (not in history_learn targets, or status != 'ok')
        gust_model = eng.models["gust_3h"]
        gust_dp_idx = gust_model.spec.features.index("dp_3h") + 1
        gust_model.w[gust_dp_idx] = 0.42
        gust_model.cp_w[gust_dp_idx] = 0.42
        gust_model.n_updates = 60

        # rain_3h is the only target that replayed from history and needs migration
        rain_model = eng.models["rain_3h"]
        rain_dp_idx = rain_model.spec.features.index("dp_3h") + 1
        rain_model.w[rain_dp_idx] = 0.0

        eng.history_learn = {
            "features_method": 3,
            "features_reset_method": 4,  # one-time reset occurred earlier
            "targets": {
                "rain_3h": {
                    "status": "ok",
                    "attempted_at": 1000.0,
                    "reason": None,
                    "method": PATTERN_HISTORY_METHOD,
                    "features_method": 3,
                },
                "gust_3h": {
                    "status": "unavailable",
                    "attempted_at": 1000.0,
                    "reason": "no statistics",
                    "retryable": False,
                    "method": PATTERN_HISTORY_METHOD,
                },
            },
        }

        n = 48
        mslp = [1000.0 + (i * 0.1) for i in range(n)]
        rain = [2.0 if (i % 6) == 3 else 0.0 for i in range(n)]
        hist = HourlyHistory(
            start_ts=1700000000.0,
            n=n,
            mslp=mslp,
            temp=[15.0] * n,
            temp_min=[12.0] * n,
            temp_max=[18.0] * n,
            dpd=[3.0] * n,
            wind=[4.0] * n,
            gust=[5.0] * n,
            rain=rain,
            strikes=[0.0] * n,
            night_frac=[0.5] * n,
            tz_offset=[0.0] * n,
        )

        rt.history_entity = lambda name, _ts: f"sensor.{name}"  # type: ignore[method-assign]
        rt._fetch_statistics = lambda ids, s, e: ({"sensor.p": {"statistic_id": "sensor.p"}}, {})  # type: ignore[method-assign]
        rt.build_history = lambda *a, **kw: hist  # type: ignore[method-assign]

        now = datetime(2026, 6, 21, 12, 0, tzinfo=UTC)
        with patch.object(pattern_runtime, "_recorder_instance", return_value=_FakeRecorder()):
            retry = await rt._async_migrate_feature_replay(now)

        assert retry is False
        # The established scale in eng.std for the live-only model MUST be preserved!
        assert eng.std.mean[dp_slot] == 1014.2
        assert eng.std.var[dp_slot] == 3.8
        assert eng.std.n[dp_slot] == 80

        # Live-only gust_3h weight is preserved
        assert gust_model.w[gust_dp_idx] == 0.42

        # rain_3h weight was trained and migrated
        assert rain_model.w[rain_dp_idx] != 0.0
        assert eng.history_learn["targets"]["rain_3h"]["features_method"] == PATTERN_HISTORY_FEATURES_METHOD
        assert eng.history_learn["features_method"] == PATTERN_HISTORY_FEATURES_METHOD

    async def test_legacy_units_check_discards_stale_results_if_reset_during_execution(self):
        from unittest.mock import AsyncMock, MagicMock, patch

        from custom_components.ws_core.const import PATTERN_HISTORY_UNITS_METHOD

        coord = MagicMock()
        coord.hass = MagicMock()
        coord.sources = {}
        coord.elevation_m = 0.0
        coord.entry_options = {}

        rt = PatternRuntime(coord)
        rt.store = MagicMock()
        rt.store.async_save = AsyncMock()
        rt.store.async_remove = AsyncMock()

        eng = rt.engine
        eng.history_learn = {
            "features_method": PATTERN_HISTORY_FEATURES_METHOD,
            "targets": {
                "rain_3h": {
                    "status": "ok",
                    "attempted_at": 1000.0,
                    "reason": None,
                    # Method 2 is before PATTERN_HISTORY_UNITS_METHOD (3)
                    "method": PATTERN_HISTORY_UNITS_METHOD - 1,
                    "features_method": PATTERN_HISTORY_FEATURES_METHOD,
                },
            },
        }

        # Simulate recorder executor job where a reset occurs while job is in-flight
        class _ResettingRecorder:
            async def async_add_executor_job(self, fn, *args):
                # An in-flight reset occurs while reading statistic metadata
                await rt.async_reset()
                return {"sensor.press": {"statistic_id": "sensor.press", "unit": "hPa"}}

        rt.history_entity = lambda name, _ts: f"sensor.{name}"  # type: ignore[method-assign]

        now = datetime(2026, 6, 21, 12, 0, tzinfo=UTC)
        with patch.object(pattern_runtime, "_recorder_instance", return_value=_ResettingRecorder()):
            ret = await rt._async_forget_misread_replay(now)

        # Result is discarded because learning was reset in flight
        assert ret is False
        # Store was not re-saved with stale replay state
        rt.store.async_save.assert_not_called()
        # Engine remains cleanly reset
        assert not rt.engine.history_learn

    def test_adopt_replay_migrates_non_pressure_models_without_dp_warm(self):
        eng = _make_engine()
        trained = _make_engine()
        dp_slot = POOL_INDEX["dp_3h"]
        trained.std.n[dp_slot] = 0
        eng.std.n[dp_slot] = 0

        # heat_24h is a non-pressure model (does not use dp_3h)
        assert "dp_3h" not in eng.models["heat_24h"].spec.features

        report = {"heat_24h": {"samples": 120, "events": 4, "first": 1000.0, "last": 2000.0}}
        statuses = {"heat_24h": {"status": "ok", "reason": None, "samples": 120, "events": 4}}

        eng.adopt_replay(trained, report, statuses, update_std=False, now_ts=3000.0)

        # Non-pressure model gets stamped with PATTERN_HISTORY_FEATURES_METHOD even when dp_warm is False
        heat_entry = eng.history_learn["targets"]["heat_24h"]
        assert heat_entry.get("features_method") == PATTERN_HISTORY_FEATURES_METHOD
        assert eng.history_learn.get("features_method") == PATTERN_HISTORY_FEATURES_METHOD

    def test_adopt_replay_preserves_existing_features_method_on_prior_targets(self):
        eng = _make_engine()
        trained = _make_engine()
        dp_slot = POOL_INDEX["dp_3h"]
        trained.std.n[dp_slot] = 0
        eng.std.n[dp_slot] = 0

        # Prior target rain_3h was already migrated
        eng.history_learn = {
            "features_method": 3,
            "features_reset_method": PATTERN_HISTORY_FEATURES_METHOD,
            "targets": {
                "rain_3h": {
                    "status": "ok",
                    "attempted_at": 1000.0,
                    "reason": None,
                    "method": PATTERN_HISTORY_METHOD,
                    "features_method": PATTERN_HISTORY_FEATURES_METHOD,
                },
            },
        }

        # Another pressure target gust_3h replays but dp_3h is not warm (n=0)
        report = {"gust_3h": {"samples": 50, "events": 2, "first": 1000.0, "last": 2000.0}}
        statuses = {"gust_3h": {"status": "ok", "reason": None, "samples": 50, "events": 2}}

        eng.adopt_replay(trained, report, statuses, update_std=False, now_ts=3000.0)

        # Prior rain_3h MUST preserve its features_method marker
        assert eng.history_learn["targets"]["rain_3h"]["features_method"] == PATTERN_HISTORY_FEATURES_METHOD
        # gust_3h remains pending because it uses dp_3h and dp is not warm
        assert "features_method" not in eng.history_learn["targets"]["gust_3h"]
        # Overall features_method remains pending (< 4)
        assert eng.history_learn.get("features_method") == 3

    async def test_migrate_feature_replay_non_pressure_only_completes_without_recorder_read(self):
        from unittest.mock import AsyncMock, MagicMock, patch

        coord = MagicMock()
        coord.hass = MagicMock()
        coord.sources = {}
        coord.elevation_m = 0.0
        coord.entry_options = {}

        rt = PatternRuntime(coord)
        rt.store = MagicMock()
        rt.store.async_save = AsyncMock()
        rt.engine = _make_engine()
        eng = rt.engine
        cloud_slot = POOL_INDEX["cloud_deficit"]
        assert eng.std.n[cloud_slot] > 0

        eng.history_learn = {
            "features_method": 3,
            "targets": {
                "heat_24h": {
                    "status": "ok",
                    "attempted_at": 1000.0,
                    "reason": None,
                    "method": PATTERN_HISTORY_METHOD,
                },
                "rain_3h": {
                    "status": "unavailable",
                    "attempted_at": 1000.0,
                    "reason": "no sensor",
                    "retryable": False,
                    "method": PATTERN_HISTORY_METHOD,
                },
            },
        }

        recorder_calls = 0

        class _CountingRecorder:
            async def async_add_executor_job(self, fn, *args):
                nonlocal recorder_calls
                recorder_calls += 1
                return fn(*args)

        now = datetime(2026, 6, 21, 12, 0, tzinfo=UTC)
        with patch.object(pattern_runtime, "_recorder_instance", return_value=_CountingRecorder()):
            retry = await rt._async_migrate_feature_replay(now)

        assert retry is False
        assert recorder_calls == 0
        assert eng.std.n[cloud_slot] == 0  # corrupted solar features were still reset
        assert eng.history_learn["targets"]["heat_24h"]["features_method"] == PATTERN_HISTORY_FEATURES_METHOD
        assert eng.history_learn["features_method"] == PATTERN_HISTORY_FEATURES_METHOD
        assert eng.history_learn["features_reset_method"] == PATTERN_HISTORY_FEATURES_METHOD
        rt.store.async_save.assert_awaited_once()

    async def test_async_learn_history_aborts_and_discards_seed_if_reset_during_seed(self):
        from unittest.mock import AsyncMock, MagicMock, patch

        coord = MagicMock()
        coord.hass = MagicMock()
        coord.sources = {}
        coord.elevation_m = 0.0
        coord.entry_options = {}
        coord._stopped = False
        scheduled: list = []

        def _fake_start_once(fn, delay, name):
            scheduled.append((fn, delay, name))

        coord._start_once = _fake_start_once

        rt = PatternRuntime(coord)
        rt.store = MagicMock()
        rt.store.async_save = AsyncMock()
        rt.store.async_remove = AsyncMock()
        rt._history_job = MagicMock(side_effect=AssertionError("_history_job should not run after in-flight reset"))  # type: ignore[method-assign]

        class _ResetDuringSeedRecorder:
            async def async_add_executor_job(self, fn, *args):
                await rt.async_reset()
                return [{"ts": 1700000000.0, "t": 15.0, "r": 2.0}]

        with (
            patch.object(pattern_runtime, "_recorder_instance", return_value=_ResetDuringSeedRecorder()),
            patch(
                "custom_components.ws_core.pattern_runtime.dt_util.utcnow",
                return_value=datetime(2026, 6, 21, 12, 0, tzinfo=UTC),
            ),
        ):
            await rt.async_learn_history()

        # Stale bins/rain were discarded and replacement replay was queued cleanly
        assert len(rt.engine.bins) == 0
        assert rt.engine.last_rain_ts is None
        assert rt._history_job.call_count == 0
        assert len(scheduled) == 1
        assert scheduled[0][0] == rt.async_learn_history

    async def test_dp3h_migration_retries_if_live_scale_warms_during_job(self):
        from unittest.mock import AsyncMock, MagicMock, patch

        coord = MagicMock()
        coord.hass = MagicMock()
        coord.sources = {}
        coord.elevation_m = 0.0
        coord.entry_options = {}

        rt = PatternRuntime(coord)
        rt.store = MagicMock()
        rt.store.async_save = AsyncMock()
        eng = rt.engine
        dp_slot = POOL_INDEX["dp_3h"]

        eng.history_learn = {
            "features_method": 3,
            "features_reset_method": PATTERN_HISTORY_FEATURES_METHOD,
            "targets": {
                "rain_3h": {
                    "status": "ok",
                    "attempted_at": 1000.0,
                    "reason": None,
                    "method": PATTERN_HISTORY_METHOD,
                },
            },
        }

        n = 48
        hist = HourlyHistory(
            start_ts=1700000000.0,
            n=n,
            mslp=[1000.0 + (i * 0.1) for i in range(n)],
            temp=[15.0] * n,
            temp_min=[12.0] * n,
            temp_max=[18.0] * n,
            dpd=[3.0] * n,
            wind=[4.0] * n,
            gust=[5.0] * n,
            rain=[2.0 if (i % 6) == 3 else 0.0 for i in range(n)],
            strikes=[0.0] * n,
            night_frac=[0.5] * n,
            tz_offset=[0.0] * n,
        )

        class _WarmingRecorder:
            async def async_add_executor_job(self, fn, *args):
                res = fn(*args)
                # Simulate live ticks pushing dp_3h across warmup while executor ran
                eng.std.mean[dp_slot] = 999.5
                eng.std.var[dp_slot] = 2.5
                eng.std.n[dp_slot] = PATTERN_STD_MIN_N + 5
                return res

        rt.history_entity = lambda name, _ts: f"sensor.{name}"  # type: ignore[method-assign]
        rt._fetch_statistics = lambda ids, s, e: ({"sensor.p": {"statistic_id": "sensor.p"}}, {})  # type: ignore[method-assign]
        rt.build_history = lambda *a, **kw: hist  # type: ignore[method-assign]

        now = datetime(2026, 6, 21, 12, 0, tzinfo=UTC)
        with patch.object(pattern_runtime, "_recorder_instance", return_value=_WarmingRecorder()):
            retry = await rt._async_migrate_feature_replay(now)

        # Should NOT overwrite the newly warmed live scale; instead retries under has_warm_scale=True
        assert retry is True
        assert eng.std.mean[dp_slot] == 999.5
        assert eng.std.n[dp_slot] == PATTERN_STD_MIN_N + 5
        assert "features_method" not in eng.history_learn["targets"]["rain_3h"]

    async def test_dp3h_migration_preserves_live_learning_when_every_pressure_target_pending(self):
        from unittest.mock import AsyncMock, MagicMock, patch

        coord = MagicMock()
        coord.hass = MagicMock()
        coord.sources = {}
        coord.elevation_m = 0.0
        coord.entry_options = {}

        rt = PatternRuntime(coord)
        rt.store = MagicMock()
        rt.store.async_save = AsyncMock()
        eng = rt.engine
        dp_slot = POOL_INDEX["dp_3h"]

        # Warm live scale accumulated after the one-time reset
        eng.std.mean[dp_slot] = 0.25
        eng.std.var[dp_slot] = 3.5
        eng.std.n[dp_slot] = 80

        # Every single pressure model in eng.models is pending migration
        pressure_tids = [t for t, m in eng.models.items() if "dp_3h" in m.spec.features]
        eng.history_learn = {
            "features_method": 3,
            "features_reset_method": PATTERN_HISTORY_FEATURES_METHOD,
            "targets": {
                tid: {
                    "status": "ok",
                    "attempted_at": 1000.0,
                    "reason": None,
                    "method": PATTERN_HISTORY_METHOD,
                    "features_method": 3,
                }
                for tid in pressure_tids
            },
        }

        rain_model = eng.models["rain_3h"]
        rain_dp_idx = rain_model.spec.features.index("dp_3h") + 1
        rain_model.w[rain_dp_idx] = 0.35
        rain_model.g2[rain_dp_idx] = 100.0
        rain_model.cp_w[rain_dp_idx] = 0.35
        rain_model.cp_g2[rain_dp_idx] = 100.0

        n = 48
        hist = HourlyHistory(
            start_ts=1700000000.0,
            n=n,
            mslp=[1000.0 + (i * 0.1) for i in range(n)],
            temp=[15.0] * n,
            temp_min=[12.0] * n,
            temp_max=[18.0] * n,
            dpd=[3.0] * n,
            wind=[4.0] * n,
            gust=[5.0] * n,
            rain=[2.0 if (i % 6) == 3 else 0.0 for i in range(n)],
            strikes=[0.0] * n,
            night_frac=[0.5] * n,
            tz_offset=[0.0] * n,
        )

        rt.history_entity = lambda name, _ts: f"sensor.{name}"  # type: ignore[method-assign]
        rt._fetch_statistics = lambda ids, s, e: ({"sensor.p": {"statistic_id": "sensor.p"}}, {})  # type: ignore[method-assign]
        rt.build_history = lambda *a, **kw: hist  # type: ignore[method-assign]

        now = datetime(2026, 6, 21, 12, 0, tzinfo=UTC)
        with patch.object(pattern_runtime, "_recorder_instance", return_value=_FakeRecorder()):
            retry = await rt._async_migrate_feature_replay(now)

        assert retry is False
        # Even when every pressure target was pending, warm live scale is preserved
        assert eng.std.mean[dp_slot] == 0.25
        assert eng.std.var[dp_slot] == 3.5
        assert eng.std.n[dp_slot] == 80
        # And post-reset live dp_3h weight was refined rather than reset back to 0.0
        assert abs(rain_model.w[rain_dp_idx] - 0.35) < 0.05
        assert eng.history_learn["features_method"] == PATTERN_HISTORY_FEATURES_METHOD

    async def test_dp3h_migration_lets_recoverable_targets_finish_when_another_lacks_history(self):
        from unittest.mock import AsyncMock, MagicMock, patch

        coord = MagicMock()
        coord.hass = MagicMock()
        coord.sources = {}
        coord.elevation_m = 0.0
        coord.entry_options = {}

        rt = PatternRuntime(coord)
        rt.store = MagicMock()
        rt.store.async_save = AsyncMock()
        eng = rt.engine
        dp_slot = POOL_INDEX["dp_3h"]

        rain_model = eng.models["rain_3h"]
        rain_dp_idx = rain_model.spec.features.index("dp_3h") + 1
        rain_model.w[rain_dp_idx] = 0.0

        gust_model = eng.models["gust_3h"]
        gust_dp_idx = gust_model.spec.features.index("dp_3h") + 1
        gust_model.w[gust_dp_idx] = 0.0

        eng.history_learn = {
            "features_method": 3,
            "features_reset_method": PATTERN_HISTORY_FEATURES_METHOD,
            "targets": {
                "rain_3h": {
                    "status": "ok",
                    "attempted_at": 1000.0,
                    "reason": None,
                    "method": PATTERN_HISTORY_METHOD,
                    "features_method": 3,
                },
                "gust_3h": {
                    "status": "ok",
                    "attempted_at": 1000.0,
                    "reason": None,
                    "method": PATTERN_HISTORY_METHOD,
                    "features_method": 3,
                },
            },
        }

        n = 60
        mslp = [1015.0 - (0.5 * (i % 6)) for i in range(n)]
        rain = [2.0 if (i % 6) == 3 else 0.0 for i in range(n)]

        # Attempt 1: rain + pressure history present, gust history missing (None)
        hist_no_gust = HourlyHistory(
            start_ts=1700000000.0,
            n=n,
            mslp=mslp,
            temp=[15.0] * n,
            temp_min=[12.0] * n,
            temp_max=[18.0] * n,
            dpd=[3.0] * n,
            wind=[4.0] * n,
            gust=[None] * n,
            rain=rain,
            strikes=[0.0] * n,
            night_frac=[0.5] * n,
            tz_offset=[0.0] * n,
        )

        rt.history_entity = lambda name, _ts: f"sensor.{name}"  # type: ignore[method-assign]
        rt._fetch_statistics = lambda ids, s, e: ({"sensor.p": {"statistic_id": "sensor.p"}}, {})  # type: ignore[method-assign]
        rt.build_history = lambda *a, **kw: hist_no_gust  # type: ignore[method-assign]

        now = datetime(2026, 6, 21, 12, 0, tzinfo=UTC)
        with patch.object(pattern_runtime, "_recorder_instance", return_value=_FakeRecorder()):
            retry1 = await rt._async_migrate_feature_replay(now)

        # Recoverable rain_3h finishes immediately; missing gust_3h stays pending for retry
        assert retry1 is True
        assert rain_model.w[rain_dp_idx] != 0.0
        assert eng.std.n[dp_slot] >= PATTERN_STD_MIN_N
        assert eng.history_learn["targets"]["rain_3h"]["features_method"] == PATTERN_HISTORY_FEATURES_METHOD
        assert eng.history_learn["targets"]["gust_3h"]["features_method"] == 3
        assert eng.history_learn["features_method"] == 3

        saved_rain_w = rain_model.w[rain_dp_idx]
        saved_std_n = eng.std.n[dp_slot]
        saved_std_var = eng.std.var[dp_slot]

        # Attempt 2: gust history recovers -> gust_3h trains against established scale & finishes migration
        hist_with_gust = HourlyHistory(
            start_ts=1700000000.0,
            n=n,
            mslp=mslp,
            temp=[15.0] * n,
            temp_min=[12.0] * n,
            temp_max=[18.0] * n,
            dpd=[3.0] * n,
            wind=[4.0] * n,
            gust=[16.0 if (i % 6) == 3 else 5.0 for i in range(n)],
            rain=rain,
            strikes=[0.0] * n,
            night_frac=[0.5] * n,
            tz_offset=[0.0] * n,
        )
        rt.build_history = lambda *a, **kw: hist_with_gust  # type: ignore[method-assign]
        with patch.object(pattern_runtime, "_recorder_instance", return_value=_FakeRecorder()):
            retry2 = await rt._async_migrate_feature_replay(now)

        assert retry2 is False
        assert gust_model.w[gust_dp_idx] != 0.0
        assert rain_model.w[rain_dp_idx] == saved_rain_w
        assert eng.std.n[dp_slot] == saved_std_n
        assert eng.std.var[dp_slot] == saved_std_var
        assert eng.history_learn["targets"]["gust_3h"]["features_method"] == PATTERN_HISTORY_FEATURES_METHOD
        assert eng.history_learn["features_method"] == PATTERN_HISTORY_FEATURES_METHOD

    async def test_dp3h_migration_preserves_live_updates_during_executor_job(self):
        import math
        from unittest.mock import AsyncMock, MagicMock, patch

        from custom_components.ws_core.const import PATTERN_CHECKPOINT_INTERVAL_S

        coord = MagicMock()
        coord.hass = MagicMock()
        coord.sources = {}
        coord.elevation_m = 0.0
        coord.entry_options = {}

        rt = PatternRuntime(coord)
        rt.store = MagicMock()
        rt.store.async_save = AsyncMock()
        eng = rt.engine
        dp_slot = POOL_INDEX["dp_3h"]

        # Warm dp_3h scaler and pre-existing live weights before executor replay launches
        eng.std.mean[dp_slot] = 0.0
        eng.std.var[dp_slot] = 2.0
        eng.std.n[dp_slot] = 80

        rain_model = eng.models["rain_3h"]
        rain_dp_idx = rain_model.spec.features.index("dp_3h") + 1
        pre_w = 0.0
        pre_g2 = 0.0
        rain_model.w[rain_dp_idx] = pre_w
        rain_model.g2[rain_dp_idx] = pre_g2
        rain_model.cp_w[rain_dp_idx] = pre_w
        rain_model.cp_g2[rain_dp_idx] = pre_g2
        rain_model.cp_at = 1700000000.0

        gust_model = eng.models["gust_3h"]
        gust_dp_idx = gust_model.spec.features.index("dp_3h") + 1
        gust_model.w[gust_dp_idx] = 0.15
        gust_model.g2[gust_dp_idx] = 20.0

        eng.history_learn = {
            "features_method": 3,
            "features_reset_method": PATTERN_HISTORY_FEATURES_METHOD,
            "targets": {
                "rain_3h": {
                    "status": "ok",
                    "attempted_at": 1000.0,
                    "reason": None,
                    "method": PATTERN_HISTORY_METHOD,
                    "features_method": 3,
                },
                "gust_3h": {
                    "status": "ok",
                    "attempted_at": 1000.0,
                    "reason": None,
                    "method": PATTERN_HISTORY_METHOD,
                    "features_method": 3,
                },
            },
        }

        n = 60
        mslp = [1015.0 - (0.6 * (i % 6)) for i in range(n)]
        rain = [3.0 if (i % 6) == 3 else 0.0 for i in range(n)]
        # rain_3h can replay; gust_3h lacks gust history so it remains pending
        hist = HourlyHistory(
            start_ts=1700000000.0,
            n=n,
            mslp=mslp,
            temp=[15.0] * n,
            temp_min=[12.0] * n,
            temp_max=[18.0] * n,
            dpd=[3.0] * n,
            wind=[4.0] * n,
            gust=[None] * n,
            rain=rain,
            strikes=[0.0] * n,
            night_frac=[0.5] * n,
            tz_offset=[0.0] * n,
        )

        rt.history_entity = lambda name, _ts: f"sensor.{name}"  # type: ignore[method-assign]
        rt._fetch_statistics = lambda ids, s, e: ({"sensor.p": {"statistic_id": "sensor.p"}}, {})  # type: ignore[method-assign]
        rt.build_history = lambda *a, **kw: hist  # type: ignore[method-assign]

        captured: dict[str, Any] = {}

        class _InFlightLiveRecorder:
            async def async_add_executor_job(self, fn, *args):
                res = fn(*args)
                trained, _counts = res
                oracle_eng, _ = PatternEngine.from_dict(
                    trained.to_dict(), trained.thresholds, trained.storm_source, trained.source_fingerprint
                )
                src_rain = trained.models["rain_3h"]
                captured["src_w"] = src_rain.w[rain_dp_idx]
                captured["src_g2"] = src_rain.g2[rain_dp_idx]

                # Simulate live observations and model training with std & non-dp weight drift between samples
                eng.std.update(dp_slot, -3.5)
                std1 = PatternEngine.from_dict(eng.to_dict(), eng.thresholds, eng.storm_source, eng.source_fingerprint)[
                    0
                ].std
                feat: list[float | None] = [None] * N_POOL
                feat[dp_slot] = -3.5
                live_ts = 1700000000.0 + PATTERN_CHECKPOINT_INTERVAL_S + 60.0
                w_before_1 = list(rain_model.w)
                rain_model.train(eng.std, feat, 1.0, live_ts)

                # Mutate std and non-dp weights sharply before the second live sample arrives
                for _ in range(5):
                    eng.std.update(dp_slot, 25.0)
                std2 = PatternEngine.from_dict(eng.to_dict(), eng.thresholds, eng.storm_source, eng.source_fingerprint)[
                    0
                ].std
                feat2: list[float | None] = [None] * N_POOL
                feat2[dp_slot] = -2.5
                w_before_2 = list(rain_model.w)
                rain_model.train(eng.std, feat2, 1.0, live_ts + 60.0)

                captured["live_w"] = rain_model.w[rain_dp_idx]
                captured["live_bias"] = rain_model.w[0]
                captured["live_n_updates"] = rain_model.n_updates
                captured["oracle_eng"] = oracle_eng
                captured["step1"] = (std1, feat, 1.0, live_ts, w_before_1)
                captured["step2"] = (std2, feat2, 1.0, live_ts + 60.0, w_before_2)

                # Also update missing gust_3h concurrently; migration must not overwrite it
                gust_model.train(eng.std, feat, 1.0, live_ts)
                captured["gust_live_w"] = gust_model.w[gust_dp_idx]
                return res

        now = datetime(2026, 6, 21, 12, 0, tzinfo=UTC)
        with patch.object(pattern_runtime, "_recorder_instance", return_value=_InFlightLiveRecorder()):
            retry = await rt._async_migrate_feature_replay(now)

        assert retry is True
        from custom_components.ws_core.const import PATTERN_CHECKPOINT_INTERVAL_S as _CP_S
        from custom_components.ws_core.const import PATTERN_GRAD_CLIP as _CLIP
        from custom_components.ws_core.const import PATTERN_L2 as _L2
        from custom_components.ws_core.pattern_forecast import _sigmoid

        # Independent serial oracle: apply step1 in (std1, w_before_1), then step2 in (std2, w_before_2)
        oracle_rain = captured["oracle_eng"].models["rain_3h"]
        cp_at = 1700000000.0
        for std_i, feat_i, y_i, ts_i, w_i in (captured["step1"], captured["step2"]):
            z_i = oracle_rain.zvec(std_i, feat_i)
            base_s = w_i[0] + sum(
                w * v for j, (w, v) in enumerate(zip(w_i[1:], z_i, strict=True), start=1) if j != rain_dp_idx
            )
            s_i = base_s + oracle_rain.w[rain_dp_idx] * z_i[rain_dp_idx - 1]
            err_i = _sigmoid(s_i) - y_i
            g_i = max(-_CLIP, min(_CLIP, err_i * z_i[rain_dp_idx - 1] + _L2 * oracle_rain.w[rain_dp_idx]))
            oracle_rain._step(rain_dp_idx, g_i)
            if cp_at is None or ts_i - cp_at >= _CP_S:
                oracle_rain.cp_w[rain_dp_idx] = oracle_rain.w[rain_dp_idx]
                oracle_rain.cp_g2[rain_dp_idx] = oracle_rain.g2[rain_dp_idx]
                cp_at = ts_i

        # Also compare against post-hoc context (what broken post-await zvec/w would give) to ensure context matters
        stale_model = PatternEngine.from_dict(
            captured["oracle_eng"].to_dict(),
            captured["oracle_eng"].thresholds,
            captured["oracle_eng"].storm_source,
            captured["oracle_eng"].source_fingerprint,
        )[0].models["rain_3h"]
        stale_model.w[0] = captured["live_bias"]
        for _std_i, feat_i, y_i, _ts_i, _w_i in (captured["step1"], captured["step2"]):
            z_bad = stale_model.zvec(eng.std, feat_i)
            s_bad = stale_model.w[0] + sum(w * v for w, v in zip(stale_model.w[1:], z_bad, strict=True))
            g_bad = max(
                -_CLIP, min(_CLIP, (_sigmoid(s_bad) - y_i) * z_bad[rain_dp_idx - 1] + _L2 * stale_model.w[rain_dp_idx])
            )
            stale_model._step(rain_dp_idx, g_bad)

        naive_linear_w = captured["src_w"] + (captured["live_w"] - pre_w)
        assert captured["live_w"] != pre_w
        assert captured["src_w"] != pre_w
        assert abs(rain_model.w[rain_dp_idx] - naive_linear_w) > 1e-3
        assert abs(rain_model.w[rain_dp_idx] - stale_model.w[rain_dp_idx]) > 1e-4
        assert math.isclose(rain_model.w[rain_dp_idx], oracle_rain.w[rain_dp_idx], rel_tol=0.0, abs_tol=1e-12)
        assert math.isclose(rain_model.g2[rain_dp_idx], oracle_rain.g2[rain_dp_idx], rel_tol=0.0, abs_tol=1e-12)
        assert math.isclose(rain_model.cp_w[rain_dp_idx], oracle_rain.cp_w[rain_dp_idx], rel_tol=0.0, abs_tol=1e-12)
        assert math.isclose(rain_model.cp_g2[rain_dp_idx], oracle_rain.cp_g2[rain_dp_idx], rel_tol=0.0, abs_tol=1e-12)
        assert rain_model.w[0] == captured["live_bias"]
        assert rain_model.n_updates == captured["live_n_updates"]
        assert eng.std.n[dp_slot] == 86
        assert gust_model.w[gust_dp_idx] == captured["gust_live_w"]
        assert eng.history_learn["targets"]["rain_3h"]["features_method"] == PATTERN_HISTORY_FEATURES_METHOD
        assert eng.history_learn["targets"]["gust_3h"]["features_method"] == 3


class TestDowngradeTolerance:
    def test_short_current_replay_reloads_without_pending_migration(self):
        live = PatternEngine(Thresholds())
        trained = _make_engine()
        dp_slot = POOL_INDEX["dp_3h"]
        trained.std.n[dp_slot] = 6
        live.adopt_replay(
            trained,
            {"rain_3h": {"samples": 6, "first": 1000.0, "last": 2000.0}},
            {"rain_3h": {"status": "ok", "reason": None}},
            update_std=True,
            now_ts=3000.0,
        )
        assert live.history_learn["targets"]["rain_3h"]["features_method"] == PATTERN_HISTORY_FEATURES_METHOD
        original = live.to_dict()
        # A preview install had no explicit marker and could lack the alignment stamp as well.
        original.pop("features_migration_pending")
        original["history_learn"].pop("features_method")
        original["history_learn"].pop("features_reset_method")
        original["history_learn"]["targets"]["rain_3h"].pop("features_method")
        loaded, notes = PatternEngine.from_dict(original, live.thresholds)
        assert not notes
        assert loaded.features_migration_pending is False
        assert loaded.std.n[dp_slot] == 6

    async def test_legacy_state_with_no_ok_history_targets_still_gets_scoped_reset(self):
        from unittest.mock import AsyncMock, MagicMock

        old = _make_engine()
        old.history_learn = {
            "targets": {
                "rain_3h": {
                    "status": "unavailable",
                    "attempted_at": 2000.0,
                    "reason": "recorder unavailable",
                    "method": PATTERN_HISTORY_METHOD - 1,
                }
            }
        }
        payload = old.to_dict()
        payload.pop("features_migration_pending")
        restored, notes = PatternEngine.from_dict(payload, old.thresholds)
        assert not notes
        assert restored.features_migration_pending is True
        rt = PatternRuntime.__new__(PatternRuntime)
        rt.engine = restored
        rt.coord = MagicMock(_stopped=False)
        rt._reset_seq = 0
        rt._async_backup_pre_migration_state = AsyncMock(return_value=True)
        rt.async_save = AsyncMock()
        assert not await rt._async_migrate_feature_replay(datetime(2026, 6, 21, tzinfo=UTC))
        rt._async_backup_pre_migration_state.assert_awaited_once()
        assert restored.std.n[POOL_INDEX["dp_3h"]] == 0
        assert restored.std.n[POOL_INDEX["cloud_deficit"]] == 0
        assert restored.features_migration_pending is False
        assert restored.to_dict()["features_migration_pending"] is False

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


class TestPreMigrationBackup:
    """Verify pre-reset storage backup is persisted before one-way v3.0 scoped reset."""

    async def test_pre_v3_backup_saved_on_disk_before_scoped_reset(self, hass):
        from datetime import UTC, datetime
        from unittest.mock import MagicMock

        from homeassistant.helpers.storage import Store

        from custom_components.ws_core.const import PATTERN_STORE_VERSION
        from custom_components.ws_core.pattern_forecast import PatternEngine
        from custom_components.ws_core.pattern_runtime import PatternRuntime

        eng = _make_engine()
        dp_slot = POOL_INDEX["dp_3h"]
        sol_slot = POOL_INDEX["cloud_deficit"]
        eng.std.n[dp_slot] = 100
        eng.std.mean[dp_slot] = 0.3
        eng.std.var[dp_slot] = 1.4
        eng.std.n[sol_slot] = 50
        eng.std.mean[sol_slot] = 0.2
        eng.std.var[sol_slot] = 0.1
        rain_model = eng.models["rain_3h"]
        orig_dp_w = rain_model.w[rain_model.spec.features.index("dp_3h") + 1] = 0.42
        rain_model.w[rain_model.spec.features.index("cloud_deficit") + 1] = -0.15
        eng.history_learn = {
            "status": "ok",
            "targets": {
                "rain_3h": {"status": "ok", "attempted_at": 1000.0, "reason": None, "method": PATTERN_HISTORY_METHOD}
            },
        }

        rt = PatternRuntime.__new__(PatternRuntime)
        rt.coord = MagicMock()
        rt.coord.hass = hass
        rt.coord.elevation_m = 0.0
        rt.coord.sources = {"temperature": "sensor.t", "humidity": "sensor.h", "pressure": "sensor.p"}
        rt.engine = eng
        rt.fingerprint = eng.source_fingerprint
        rt._published = {}
        rt._reset_seq = 0
        rt._history_running = False
        rt._history_queued = False
        rt.store = Store(hass, PATTERN_STORE_VERSION, "ws_core_backup_test_pattern_forecast")
        await rt.store.async_save(eng.to_dict())

        # Trigger migration with transient empty recorder so scoped reset runs without replay completion
        rt.history_entity = lambda name, _ts: None  # type: ignore[method-assign]
        now = datetime(2026, 6, 21, 12, 0, tzinfo=UTC)
        retry = await rt._async_migrate_feature_replay(now)
        assert retry is True  # deferred because history entities not ready
        assert eng.std.n[sol_slot] == 0  # scoped reset ran

        backup_store = Store(hass, PATTERN_STORE_VERSION, "ws_core_backup_test_pattern_forecast_pre_v3_backup")
        backup = await backup_store.async_load()
        assert backup is not None
        assert backup["standardizer"]["n"][dp_slot] == 100
        assert backup["standardizer"]["n"][sol_slot] == 50
        restored, notes = PatternEngine.from_dict(backup, eng.thresholds, eng.storm_source, eng.source_fingerprint)
        assert not notes
        assert restored.models["rain_3h"].w[restored.models["rain_3h"].spec.features.index("dp_3h") + 1] == orig_dp_w

        # Re-running migration must NOT overwrite the pre-migration backup
        await rt._async_migrate_feature_replay(now)
        backup_after = await backup_store.async_load()
        assert backup_after["standardizer"]["n"][sol_slot] == 50

        # If writing the real backup store fails before reset, one-way reset must be deferred
        eng2 = _make_engine()
        eng2.std.n[sol_slot] = 75
        eng2.history_learn = {
            "status": "ok",
            "targets": {
                "rain_3h": {"status": "ok", "attempted_at": 1000.0, "reason": None, "method": PATTERN_HISTORY_METHOD}
            },
        }
        rt2 = PatternRuntime.__new__(PatternRuntime)
        rt2.coord = rt.coord
        rt2.engine = eng2
        rt2.fingerprint = eng2.source_fingerprint
        rt2._published = {}
        rt2._reset_seq = 0
        rt2._history_running = False
        rt2._history_queued = False
        rt2.store = Store(hass, PATTERN_STORE_VERSION, "ws_core_backup_fail_pattern_forecast")

        class _FailingBackupStore:
            async def async_load(self):
                return None

            async def async_save(self, _data):
                raise OSError("disk full")

        rt2.backup_store = _FailingBackupStore()
        retry_failed = await rt2._async_migrate_feature_replay(now)
        assert retry_failed is True
        assert eng2.std.n[sol_slot] == 75  # not mutated when backup save fails!
