"""Fill in rain totals and repair gust records from recorder long-term statistics.

The week / month / year rain totals and the gust records are tracked live, so
they only know what happened while ws_core was running: a total added part-way
through a year starts from zero, and rain that fell while Home Assistant was
down is never counted. A gust record also keeps any glitch it once accepted.

Once per start, after the recorder has settled, this reads the hourly
statistics of the mapped station sensors and:

- raises each rain total to what the station's own rain counter shows for that
  period (it never lowers one), and
- replaces a gust record that only hours with an implausible gust could have set
  (far above that hour's mean wind, e.g. a stuck gust channel) with the highest
  plausible gust of the period.

The read runs on the recorder executor; the results are applied on the event
loop, where the live accumulators live.
"""

from __future__ import annotations

import contextlib
import logging
import math
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.util import dt as dt_util

from .algorithms import gust_is_plausible
from .const import (
    CONF_CAL_WIND_MS,
    GUST_HOURLY_PLAUSIBLE_FACTOR,
    GUST_HOURLY_PLAUSIBLE_MARGIN_MS,
    HISTORY_RAIN_JUMP_CAP_MM_PER_H,
    SRC_GUST,
    SRC_RAIN_TOTAL,
    SRC_RAIN_YEAR,
    SRC_WIND,
)

if TYPE_CHECKING:
    from .coordinator import WSStationCoordinator

_LOGGER = logging.getLogger(__name__)

# A stored gust record "came from" an hour whose statistics max is this close (m/s)
RECORD_TOLERANCE_MS = 0.15

# (period, total, period key, last counter reading) attributes on the coordinator
_RAIN_PERIODS = (
    ("week", "_rain_this_week_mm", "_rain_this_week_isoweek", "_rain_this_week_last_total"),
    ("month", "_rain_this_month_mm", "_rain_this_month_key", "_rain_this_month_last_total"),
    ("year", "_rain_this_year_mm", "_rain_this_year_key", "_rain_this_year_last_total"),
)
# (label, period or None for all-time, record, period key) attributes on the coordinator
_GUST_RECORDS = (
    ("month", "month", "_gust_max_month", "_gust_month_key"),
    ("year", "year", "_gust_max_year", "_gust_year_key"),
    ("all-time", None, "_gust_max_all_time", None),
)


def _recorder_instance(hass: Any) -> Any:
    """The recorder instance (imported lazily: the recorder is optional)."""
    from homeassistant.components.recorder import get_instance

    return get_instance(hass)


def period_starts(now_local: datetime) -> dict[str, tuple[str, float]]:
    """Key and start timestamp of the current local ISO week, month and year.

    The keys match the ones the live accumulators and records use.
    """
    day = dt_util.start_of_local_day(now_local)
    return {
        "week": (now_local.strftime("%G-W%V"), (day - timedelta(days=day.weekday())).timestamp()),
        "month": (now_local.strftime("%Y-%m"), day.replace(day=1).timestamp()),
        "year": (now_local.strftime("%Y"), day.replace(month=1, day=1).timestamp()),
    }


def first_hour(start_ts: float, period_start_ts: float) -> int:
    """Index of the first hour of a series starting at ``start_ts`` that lies within the period."""
    return max(0, math.ceil((period_start_ts - start_ts) / 3600.0 - 1e-9))


def hourly_series(rows: list[dict], start_ts: float, n: int, key: str) -> list[float | None]:
    """One statistic of hourly rows as a list indexed by hour from ``start_ts``."""
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
    """Rain per hour from an hourly running total, bridging hours without statistics.

    The rise since the last known value is booked to the hour it shows up in, so
    rain that fell while Home Assistant was down still counts. A decrease is a
    counter reset (nothing booked); a rise faster than
    HISTORY_RAIN_JUMP_CAP_MM_PER_H is a glitch (dropped).
    """
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


def repaired_gust_record(
    stored: float, gust_max: list[float | None], wind_mean: list[float | None], first: int
) -> float | None:
    """The replacement for a gust record that only implausible hours could have set.

    Looks at the hours from ``first`` on. Returns None when the record stands: an
    hour with a plausible gust reached it, or no hour did (it predates the
    statistics or came from another sensor). Otherwise returns the highest
    plausible gust of those hours, or None when there is none.
    """

    def plausible(g: float, w: float | None) -> bool:
        return gust_is_plausible(g, w, GUST_HOURLY_PLAUSIBLE_FACTOR, GUST_HOURLY_PLAUSIBLE_MARGIN_MS)

    hours = [(g, w) for g, w in zip(gust_max[first:], wind_mean[first:], strict=True) if g is not None]
    setters = [(g, w) for g, w in hours if g >= stored - RECORD_TOLERANCE_MS]
    if not setters or any(plausible(g, w) for g, w in setters):
        return None
    good = [g for g, w in hours if plausible(g, w)]
    return max(good) if good else None


def _unit(meta_entry: dict) -> str:
    return str(meta_entry.get("statistics_unit_of_measurement") or meta_entry.get("unit_of_measurement") or "")


def read_statistics(
    hass: Any, ids: set[str], start_ts: float, end_ts: float, gust_id: str | None
) -> tuple[dict, dict, float | None]:
    """Metadata, hourly rows and the gust max before ``start_ts``. Runs on the recorder executor."""
    from homeassistant.components.recorder.statistics import (
        list_statistic_ids,
        statistic_during_period,
        statistics_during_period,
    )

    meta = {m["statistic_id"]: m for m in list_statistic_ids(hass, statistic_ids=ids)}
    start = datetime.fromtimestamp(start_ts, UTC)
    rows = statistics_during_period(
        hass, start, datetime.fromtimestamp(end_ts, UTC), set(meta), "hour", None, {"mean", "max", "sum", "state"}
    )
    older = None
    if gust_id and gust_id in meta:
        older = statistic_during_period(hass, None, start, gust_id, {"max"}, None).get("max")
    return meta, rows, older


def apply_rain(
    coord: WSStationCoordinator, meta: dict, rows: dict, start_ts: float, n: int, periods: dict
) -> list[str]:
    """Raise the week / month / year rain totals to what the station's counter shows."""
    from .pattern_runtime import PatternRuntime

    rain_id = coord.sources.get(SRC_RAIN_TOTAL)
    if not rain_id or rain_id not in meta:
        return []
    unit = _unit(meta[rain_id])
    key = PatternRuntime._cumulative_key(meta[rain_id], rows.get(rain_id) or [])
    cum = [
        None if v is None else coord._to_mm(v, unit) for v in hourly_series(rows.get(rain_id) or [], start_ts, n, key)
    ]
    known = [v for v in cum if v is not None]
    if not known:
        return []
    deltas = rain_deltas(cum)
    changes = []
    for period, total_attr, key_attr, last_attr in _RAIN_PERIODS:
        if period == "year" and coord.sources.get(SRC_RAIN_YEAR):
            continue  # the station's own year-to-date counter is shown instead
        period_key, period_start = periods[period]
        last_total = getattr(coord, last_attr)
        if getattr(coord, key_attr) != period_key or last_total is None:
            continue
        live = float(getattr(coord, total_attr))
        # Statistics end at the last complete hour; the live counter adds what came after.
        since = sum(d for d in deltas[first_hour(start_ts, period_start) :] if d is not None)
        total = since + max(0.0, float(last_total) - known[-1])
        if total > live + 0.05:
            setattr(coord, total_attr, total)
            changes.append(f"rain this {period} {live:.1f} -> {total:.1f} mm")
    return changes


def apply_gust(
    coord: WSStationCoordinator,
    meta: dict,
    rows: dict,
    older_max: float | None,
    start_ts: float,
    n: int,
    periods: dict,
) -> list[str]:
    """Replace gust records that only implausible hours could have set."""
    gust_id = coord.sources.get(SRC_GUST)
    wind_id = coord.sources.get(SRC_WIND)
    if not gust_id or not wind_id or gust_id not in meta or wind_id not in meta:
        return []
    cal = float(coord.entry_options.get(CONF_CAL_WIND_MS, 0.0))

    def to_ms(v: float | None, unit: str) -> float | None:
        return None if v is None else max(0.0, coord._to_ms(v, unit) + cal)

    gust_unit, wind_unit = _unit(meta[gust_id]), _unit(meta[wind_id])
    gust = [to_ms(v, gust_unit) for v in hourly_series(rows.get(gust_id) or [], start_ts, n, "max")]
    wind = [to_ms(v, wind_unit) for v in hourly_series(rows.get(wind_id) or [], start_ts, n, "mean")]
    older = to_ms(older_max, gust_unit)
    changes = []
    for label, period, record_attr, key_attr in _GUST_RECORDS:
        stored = getattr(coord, record_attr)
        if stored is None:
            continue
        first = 0
        if period is not None:
            period_key, period_start = periods[period]
            if getattr(coord, key_attr) != period_key:
                continue
            first = first_hour(start_ts, period_start)
        repl = repaired_gust_record(float(stored), gust, wind, first)
        if repl is None:
            continue
        if period is None and older is not None:
            repl = max(repl, older)  # all-time also covers the hours before the window
        if repl < float(stored) - RECORD_TOLERANCE_MS:
            setattr(coord, record_attr, repl)
            changes.append(f"{label} gust record {float(stored):.1f} -> {repl:.1f} m/s")
    return changes


async def async_backfill_from_statistics(coord: WSStationCoordinator) -> None:
    """Read the station's statistics for the current year and correct the totals and records."""
    hass = coord.hass
    if "recorder" not in hass.config.components:
        return
    rain_id = coord.sources.get(SRC_RAIN_TOTAL) or None
    wind_id = coord.sources.get(SRC_WIND) or None
    gust_id = (coord.sources.get(SRC_GUST) or None) if wind_id else None  # a gust is judged against the wind
    ids = {e for e in (rain_id, gust_id, wind_id if gust_id else None) if e}
    if not ids:
        return

    now = dt_util.utcnow()
    periods = period_starts(dt_util.as_local(now))
    end_ts = math.floor(now.timestamp() / 3600.0) * 3600.0
    # One hour before the earliest period, so its first hour has a counter value to rise from
    start_ts = math.floor(min(s for _, s in periods.values()) / 3600.0) * 3600.0 - 3600.0
    n = int(round((end_ts - start_ts) / 3600.0))
    try:
        meta, rows, older = await _recorder_instance(hass).async_add_executor_job(
            read_statistics, hass, ids, start_ts, end_ts, gust_id
        )
    except Exception as err:  # noqa: BLE001 - recorder missing, DB error, ...
        _LOGGER.debug("ws_core: no recorder statistics to correct rain totals and records from: %s", err)
        return

    changes = apply_rain(coord, meta, rows, start_ts, n, periods) + apply_gust(
        coord, meta, rows, older, start_ts, n, periods
    )
    if not changes:
        return
    _LOGGER.info("ws_core: corrected from recorder statistics: %s", "; ".join(changes))
    if coord._history_store is not None:
        with contextlib.suppress(Exception):
            await coord._history_store.async_save(coord._dump_history_state())
