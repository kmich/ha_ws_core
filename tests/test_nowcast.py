"""Tests for the precipitation nowcast derivation (derive_nowcast)."""

from __future__ import annotations

import os
import sys
from datetime import UTC, datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from custom_components.ws_core.algorithms import derive_nowcast


def _buckets(start: datetime, mm_per_bucket: list[float]) -> tuple[list[str], list[float]]:
    """Build 15-minute (time, precip) arrays starting at `start`."""
    times = [(start + timedelta(minutes=15 * i)).isoformat() for i in range(len(mm_per_bucket))]
    return times, mm_per_bucket


class TestDeriveNowcast:
    def test_rain_starts_in_30_min(self):
        # now sits at the start of bucket 0 (dry, dry, wet, wet)
        now = datetime(2026, 5, 22, 12, 0)
        times, precip = _buckets(now, [0.0, 0.0, 0.5, 0.8])
        r = derive_nowcast(times, precip, now)
        assert r["raining_now"] is False
        assert r["minutes_until_rain"] == 30
        assert r["minutes_until_dry"] is None
        assert r["next_60min_mm"] == 1.3
        assert r["intensity"] in ("light", "moderate")

    def test_raining_now_stops_in_30_min(self):
        now = datetime(2026, 5, 22, 12, 0)
        times, precip = _buckets(now, [0.6, 0.4, 0.0, 0.0])
        r = derive_nowcast(times, precip, now)
        assert r["raining_now"] is True
        assert r["minutes_until_rain"] == 0
        assert r["minutes_until_dry"] == 30

    def test_dry_window_returns_none(self):
        now = datetime(2026, 5, 22, 12, 0)
        times, precip = _buckets(now, [0.0, 0.0, 0.0, 0.0])
        r = derive_nowcast(times, precip, now)
        assert r["raining_now"] is False
        assert r["minutes_until_rain"] is None
        assert r["minutes_until_dry"] is None
        assert r["next_60min_mm"] == 0.0
        assert r["intensity"] == "none"

    def test_trace_below_threshold_is_dry(self):
        now = datetime(2026, 5, 22, 12, 0)
        times, precip = _buckets(now, [0.0, 0.05, 0.09, 0.0])
        r = derive_nowcast(times, precip, now)
        assert r["minutes_until_rain"] is None
        assert r["intensity"] == "none"

    def test_heavy_intensity_classification(self):
        now = datetime(2026, 5, 22, 12, 0)
        # 2.5 mm in a 15-min bucket = 10 mm/h => heavy
        times, precip = _buckets(now, [0.0, 2.5, 0.0, 0.0])
        r = derive_nowcast(times, precip, now)
        assert r["peak_rate_mmph"] == 10.0
        assert r["intensity"] == "heavy"
        assert r["minutes_until_rain"] == 15

    def test_now_between_buckets_uses_containing_bucket(self):
        # now is 7 minutes into the first (wet) bucket -> raining now
        base = datetime(2026, 5, 22, 12, 0)
        now = base + timedelta(minutes=7)
        times, precip = _buckets(base, [0.5, 0.0, 0.0, 0.0])
        r = derive_nowcast(times, precip, now)
        assert r["raining_now"] is True
        assert r["minutes_until_dry"] == 8  # bucket 1 starts at 12:15, now=12:07

    def test_empty_input_safe(self):
        now = datetime(2026, 5, 22, 12, 0)
        r = derive_nowcast([], [], now)
        assert r["raining_now"] is False
        assert r["minutes_until_rain"] is None
        assert r["next_60min_mm"] == 0.0

    def test_tz_aware_now_is_coerced(self):

        now = datetime(2026, 5, 22, 12, 0, tzinfo=UTC)
        times, precip = _buckets(datetime(2026, 5, 22, 12, 0), [0.0, 0.3, 0.0, 0.0])
        r = derive_nowcast(times, precip, now)
        assert r["minutes_until_rain"] == 15

    def test_mismatched_array_lengths_safe(self):
        now = datetime(2026, 5, 22, 12, 0)
        times = [(now + timedelta(minutes=15 * i)).isoformat() for i in range(4)]
        precip = [0.0, 0.5]  # shorter than times
        r = derive_nowcast(times, precip, now)
        assert r["minutes_until_rain"] == 15
