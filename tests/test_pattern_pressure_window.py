"""The 24 h pressure change must survive restarts (live station, 2026-11-21).

Every restart or reload issues one extra, off-grid forecast ("recovery issue"),
which appends one more pressure point. The history was capped by count (97
points = 24 h of 15-min points), so each extra point pushed the oldest one out
early. After a few restarts in a day nothing was left from 24 h ago, the
``dp_24h`` input was missing and every Pattern Forecast target paused with
``waiting_for:dp_24h`` until the extra points aged out (up to about a day).
The history is now kept by time (24.5 h).
"""

from __future__ import annotations

import json

from custom_components.ws_core import pattern_forecast as pf
from custom_components.ws_core.pattern_forecast import Instant, PatternEngine

from .pattern_world import World, make_engine


def _inst() -> Instant:
    return Instant(mslp=1013.0, dp_3h=0.0, temp=14.0, dpd=4.0, night_frac_12h=0.3)


def _three_days() -> PatternEngine:
    eng = make_engine()
    World("rain", 3, seed=1).run(eng)  # three days on the 15-min grid
    return eng


def _with_restarts(eng: PatternEngine, n: int) -> float:
    """n quarter-hour issues, each followed by a restart recovery issue; returns the last mark."""
    ts = eng._last_issue_ts
    for _ in range(n):
        ts += 900.0
        eng.issue(ts, _inst())  # normal quarter-hour issue
        eng.issue(ts + 120.0, _inst())  # recovery issue right after a restart
    return ts


def test_restart_recovery_issues_do_not_lose_the_24h_pressure_reference():
    eng = _three_days()
    assert eng.pressure_change_24h(eng._last_issue_ts + 900.0, 1010.0) is not None
    ts = _with_restarts(eng, 9)  # as on the live station
    assert eng.pressure_change_24h(ts + 900.0, 1010.0) is not None


def test_no_target_waits_for_dp_24h_after_many_restarts():
    # This simulation feeds no live readings between issues, so other short-window
    # inputs may be missing; the bug under test is only the 24 h pressure reference.
    eng = _three_days()
    ts = _with_restarts(eng, 30)
    out = eng.issue(ts + 900.0, _inst())
    assert all(o.get("reason") != "waiting_for:dp_24h" for o in out.values())


def test_history_is_trimmed_by_time_and_stays_bounded():
    eng = _three_days()
    _with_restarts(eng, 40)
    newest = eng.pressure[-1][0]
    assert newest - eng.pressure[0][0] <= pf.PATTERN_PRESSURE_WINDOW_S
    assert newest - eng.pressure[0][0] >= 86400.0  # still reaches back a full day
    assert len(eng.pressure) <= pf.PATTERN_PRESSURE_SLOTS


def test_loading_a_store_drops_points_older_than_the_window():
    eng = _three_days()
    data = json.loads(json.dumps(eng.to_dict()))
    newest = data["pressure_24h"][-1][0]
    data["pressure_24h"] = [[newest - 3 * 86400.0, 1000.0], *data["pressure_24h"]]
    loaded, _ = PatternEngine.from_dict(data, eng.thresholds, eng.storm_source, eng.source_fingerprint, eng.tick_cap_s)
    assert len(loaded.pressure) > 90  # the store itself was accepted
    assert loaded.pressure[0][0] >= newest - pf.PATTERN_PRESSURE_WINDOW_S


def test_seeding_restores_the_24h_reference_after_restarts():
    """The recorder seed at startup refills the 24 h-ago point; a count cap discarded it."""
    eng = _three_days()
    ts = _with_restarts(eng, 9)
    # Simulate a store that only reaches back ~21 h (as the live one after the restarts)
    cutoff = ts - 21 * 3600.0
    while eng.pressure and eng.pressure[0][0] < cutoff:
        eng.pressure.popleft()
    assert eng.pressure_change_24h(ts + 900.0, 1010.0) is None
    seeds = [[ts + 900.0 - 86400.0 + 900.0 * k, 1012.0] for k in range(-4, 13)]
    assert eng.seed_pressure(seeds) > 0
    assert eng.pressure_change_24h(ts + 900.0, 1010.0) is not None
