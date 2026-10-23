"""Circular wind-direction history for Pattern Forecast's short startup window."""

from __future__ import annotations

import math


def direction_vectors(
    samples: list[tuple[float, str]], start: float, end: float, max_age: float
) -> dict[float, tuple[float, float]]:
    """Time-weight recorded directions into complete five-minute periods.

    Return mean (sin, cos), not an arithmetic mean of degrees. Opposite winds
    cancel naturally. Unknown/offline intervals and stale held values do not
    count as coverage; at least 80% of a period must be valid.
    """
    samples = sorted((ts, value) for ts, value in samples if math.isfinite(ts) and ts < end)
    result = {}
    first = math.ceil(start / 300.0) * 300.0
    for period in range(int(first), int(end) - 299, 300):
        sin_sum = cos_sum = coverage = 0.0
        for i, (ts, value) in enumerate(samples):
            try:
                angle = float(value)
            except (TypeError, ValueError):
                continue
            if not math.isfinite(angle) or not 0 <= angle <= 360:
                continue
            stop = samples[i + 1][0] if i + 1 < len(samples) else end
            duration = min(stop, period + 300.0, ts + max_age) - max(ts, period)
            if duration <= 0:
                continue
            coverage += duration
            sin_sum += math.sin(math.radians(angle)) * duration
            cos_sum += math.cos(math.radians(angle)) * duration
        if coverage >= 240:
            result[float(period)] = sin_sum / coverage, cos_sum / coverage
    return result
