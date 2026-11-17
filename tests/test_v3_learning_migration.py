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
        solar_slots = [POOL_INDEX[f] for f in ("cloud_deficit", "solar_ok", "last_day_clearness", "last_day_clearness_ok")]

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
