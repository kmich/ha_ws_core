"""Raise rain totals from recorder statistics without lowering stored records.

Only recorded counter changes are backfilled. Recorder sums and raw station
counters have different zero points, so the live tail must use the raw state
from the same final statistics row. Legacy gust records have no provenance;
hourly averages cannot establish that they are wrong, so they are preserved.
"""

from __future__ import annotations

import contextlib
import logging
import math
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.util import dt as dt_util

from .const import HISTORY_RAIN_JUMP_CAP_MM_PER_H, SRC_RAIN_TOTAL, SRC_RAIN_YEAR

if TYPE_CHECKING:
    from .coordinator import WSStationCoordinator

_LOGGER = logging.getLogger(__name__)

_RAIN_PERIODS = (
    ("week", "_rain_this_week_mm", "_rain_this_week_isoweek", "_rain_this_week_last_total"),
    ("month", "_rain_this_month_mm", "_rain_this_month_key", "_rain_this_month_last_total"),
    ("year", "_rain_this_year_mm", "_rain_this_year_key", "_rain_this_year_last_total"),
)


def _recorder_instance(hass: Any) -> Any:
    """The recorder instance (imported lazily: the recorder is optional)."""
    from homeassistant.components.recorder import get_instance

    return get_instance(hass)


def period_starts(now_local: datetime) -> dict[str, tuple[str, float]]:
    """Key and start timestamp of the current local ISO week, month and year."""
    day = dt_util.start_of_local_day(now_local)
    return {
        "week": (now_local.strftime("%G-W%V"), (day - timedelta(days=day.weekday())).timestamp()),
        "month": (now_local.strftime("%Y-%m"), day.replace(day=1).timestamp()),
        "year": (now_local.strftime("%Y"), day.replace(month=1, day=1).timestamp()),
    }


def first_hour(start_ts: float, period_start_ts: float) -> int:
    """First whole hour inside the period; exclude hours crossing its boundary."""
    return max(0, math.ceil((period_start_ts - start_ts) / 3600.0 - 1e-9))


def hourly_series(rows: list[dict], start_ts: float, n: int, key: str) -> list[float | None]:
    """One statistic of hourly rows indexed by hour from ``start_ts``."""
    out: list[float | None] = [None] * n
    for row in rows:
        start = row.get("start")
        ts = start.timestamp() if isinstance(start, datetime) else start
        v = row.get(key)
        if not isinstance(ts, (int, float)) or not isinstance(v, (int, float)) or not math.isfinite(v):
            continue
        idx = int(round((ts - start_ts) / 3600.0))
        if 0 <= idx < n:
            out[idx] = float(v)
    return out


def rain_deltas(cum: list[float | None]) -> list[float | None]:
    """Counter growth, bridging gaps and dropping resets and excessive jumps."""
    out: list[float | None] = [None] * len(cum)
    prev: int | None = None
    for i, v in enumerate(cum):
        if v is None:
            continue
        if prev is not None:
            d = v - float(cum[prev])  # type: ignore[arg-type]
            out[i] = 0.0 if d < 0 else (None if d > HISTORY_RAIN_JUMP_CAP_MM_PER_H * (i - prev) else d)
        prev = i
    return out


def _unit(meta_entry: dict) -> str:
    return str(meta_entry.get("statistics_unit_of_measurement") or meta_entry.get("unit_of_measurement") or "")


def read_statistics(hass: Any, ids: set[str], start_ts: float, end_ts: float) -> tuple[dict, dict]:
    """Rain metadata and hourly rows. Runs on the recorder executor."""
    from homeassistant.components.recorder.statistics import list_statistic_ids, statistics_during_period

    meta = {m["statistic_id"]: m for m in list_statistic_ids(hass, statistic_ids=ids)}
    if not meta:
        return {}, {}
    rows = statistics_during_period(
        hass,
        datetime.fromtimestamp(start_ts, UTC),
        datetime.fromtimestamp(end_ts, UTC),
        set(meta),
        "hour",
        None,
        {"max", "sum", "state"},
    )
    return meta, rows


def apply_rain(
    coord: WSStationCoordinator, meta: dict, rows: dict, start_ts: float, n: int, periods: dict
) -> list[str]:
    """Raise totals using counter changes attributable to each period."""
    from .pattern_runtime import PatternRuntime

    rain_id = coord.sources.get(SRC_RAIN_TOTAL)
    if not rain_id or rain_id not in meta:
        return []
    unit = _unit(meta[rain_id])
    rain_rows = rows.get(rain_id) or []
    key = PatternRuntime._cumulative_key(meta[rain_id], rain_rows)
    cum = [None if v is None else coord._to_mm(v, unit) for v in hourly_series(rain_rows, start_ts, n, key)]
    known = [i for i, v in enumerate(cum) if v is not None]
    if not known:
        return []
    last_idx = known[-1]
    # A recorder sum is growth since its own zero point, not the station's
    # raw counter. A missing raw state means the live tail cannot be inferred.
    raw_key = "state" if key == "sum" else key
    raw = hourly_series(rain_rows, start_ts, n, raw_key)
    raw_last = None if raw[last_idx] is None else coord._to_mm(raw[last_idx], unit)
    changes = []
    for period, total_attr, key_attr, last_attr in _RAIN_PERIODS:
        if period == "year" and coord.sources.get(SRC_RAIN_YEAR):
            continue
        period_key, period_start = periods[period]
        last_total = getattr(coord, last_attr)
        if getattr(coord, key_attr) != period_key or last_total is None:
            continue
        first = first_hour(start_ts, period_start)
        # Do not assign a gap crossing Monday/month/year boundaries entirely
        # to the new period. Require its own immediately preceding baseline.
        baseline = max(0, first - 1)
        deltas = rain_deltas(cum[baseline:])
        since = sum(d for d in deltas[first - baseline :] if d is not None)
        tail = 0.0
        if last_idx >= baseline and raw_last is not None:
            delta = float(last_total) - raw_last
            if 0.0 <= delta <= HISTORY_RAIN_JUMP_CAP_MM_PER_H * (n - last_idx):
                tail = delta
        total = since + tail
        live = float(getattr(coord, total_attr))
        if total > live + 0.05:
            setattr(coord, total_attr, total)
            changes.append(f"rain this {period} {live:.1f} -> {total:.1f} mm")
    return changes


async def async_backfill_from_statistics(coord: WSStationCoordinator) -> None:
    """Read rain statistics once per startup and raise undercounted totals."""
    hass = coord.hass
    rain_id = coord.sources.get(SRC_RAIN_TOTAL)
    if "recorder" not in hass.config.components or not rain_id:
        return

    now = dt_util.utcnow()
    periods = period_starts(dt_util.as_local(now))
    end_ts = math.floor(now.timestamp() / 3600.0) * 3600.0
    start_ts = math.floor(min(s for _, s in periods.values()) / 3600.0) * 3600.0 - 3600.0
    n = int(round((end_ts - start_ts) / 3600.0))
    try:
        meta, rows = await _recorder_instance(hass).async_add_executor_job(
            read_statistics, hass, {rain_id}, start_ts, end_ts
        )
    except Exception as err:  # noqa: BLE001 - recorder missing, DB error, ...
        _LOGGER.debug("ws_core: no recorder statistics to correct rain totals from: %s", err)
        return

    changes = apply_rain(coord, meta, rows, start_ts, n, periods)
    if not changes:
        return
    _LOGGER.info("ws_core: corrected from recorder statistics: %s", "; ".join(changes))
    if coord._history_store is not None:
        with contextlib.suppress(Exception):
            await coord._history_store.async_save(coord._dump_history_state())
