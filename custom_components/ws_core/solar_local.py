"""Local PV forecast: Open-Meteo tilted-plane irradiance scaled to this site (v3.0.0).

forecast.solar estimates PV output from a generic system model. This module learns
how much energy *this* installation actually produces per unit of forecast
irradiance on the panel plane, from the PV energy meters already in Home
Assistant's long-term statistics, and applies that factor to Open-Meteo's
hourly global tilted irradiance (GTI) forecast.

Model (per local calendar day):

    pv_kwh = k * gti_kwh_per_m2

``k`` behaves like "effective kWp times performance ratio". It starts from the
configured peak power (``kWp * 0.80``), and is refit from (forecast GTI, measured
PV energy) day pairs as they accumulate. On first start the last 92 days are
backfilled from Open-Meteo's past-days forecasts and the recorder, so a site with
existing history is calibrated immediately.

Skill is reported honestly: only day-ahead snapshots (the last prediction made
before the target day started) are compared with the measured energy, for both
this model and forecast.solar, so neither number can benefit from same-day data.

Everything here is pure and synchronous; the coordinator does the I/O.
"""

from __future__ import annotations

import math
from datetime import UTC, date, datetime, timedelta, tzinfo
from statistics import median
from typing import Any

STORE_VERSION = 1
KEEP_DAYS = 120
BACKFILL_DAYS = 92  # Open-Meteo forecast API maximum for past_days
FIT_WINDOW_DAYS = 60
SKILL_WINDOW_DAYS = 30
MIN_FIT_DAYS = 7  # below this the fit is shrunk toward the prior
PRIOR_WEIGHT_DAYS = 3.0
MIN_SKILL_DAYS = 5
MIN_GTI_WHM2 = 300.0  # ignore near-dark days for fitting: ratios are noise there
RATIO_BAND = (0.7, 1.3)  # around the median: drops outages, curtailment and snow days
PRIOR_PERFORMANCE_RATIO = 0.80
MIN_HOURS_PER_DAY = 20  # a forecast or meter day needs this many hours to count

STATUS_PRIOR = "prior"
STATUS_LEARNING = "learning"
STATUS_TRAINED = "trained"

_ENERGY_TO_KWH = {"wh": 0.001, "kwh": 1.0, "mwh": 1000.0, "gwh": 1_000_000.0}


def store_key(entry_id: str) -> str:
    return f"ws_core_{entry_id}_solar_local"


def open_meteo_azimuth(compass_deg: float) -> float:
    """Compass azimuth (0=N, 90=E, 180=S) to Open-Meteo's (0=S, -90=E, 90=W)."""
    az = (float(compass_deg) - 180.0) % 360.0
    return az - 360.0 if az > 180.0 else az


def build_url(lat: float, lon: float, tilt: float, compass_azimuth: float, past_days: int) -> str:
    return (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        "&hourly=global_tilted_irradiance"
        f"&tilt={float(tilt):g}&azimuth={open_meteo_azimuth(compass_azimuth):g}"
        f"&past_days={max(0, min(BACKFILL_DAYS, int(past_days)))}&forecast_days=2"
        "&timeformat=unixtime&timezone=GMT"
    )


def energy_to_kwh(value: float, unit: str | None) -> float | None:
    factor = _ENERGY_TO_KWH.get(str(unit or "").strip().lower())
    return None if factor is None else float(value) * factor


def prior_factor(peak_kw: float) -> float:
    return max(0.01, float(peak_kw)) * PRIOR_PERFORMANCE_RATIO


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def parse_gti(js: dict[str, Any], tz: tzinfo) -> tuple[dict[str, float], list[tuple[float, float]]]:
    """Daily GTI sums (Wh/m2) per local date and the hourly series.

    Open-Meteo radiation values are means over the preceding hour, so the value
    stamped ``t`` is the energy (Wh/m2) of the hour ``[t - 1h, t]``. Hourly items are
    returned as ``(hour_start_utc_ts, wh_m2)``. Days with fewer than
    ``MIN_HOURS_PER_DAY`` valid hours (the partial first day of a response) are left out.
    """
    hourly = js.get("hourly") or {}
    times = hourly.get("time") or []
    values = hourly.get("global_tilted_irradiance") or []
    sums: dict[str, float] = {}
    counts: dict[str, int] = {}
    series: list[tuple[float, float]] = []
    for t, v in zip(times, values, strict=False):
        if not isinstance(t, (int, float)) or not isinstance(v, (int, float)) or not math.isfinite(v):
            continue
        start = float(t) - 3600.0
        wh = max(0.0, float(v))
        series.append((start, wh))
        day = datetime.fromtimestamp(start + 1800.0, UTC).astimezone(tz).date().isoformat()
        sums[day] = sums.get(day, 0.0) + wh
        counts[day] = counts.get(day, 0) + 1
    daily = {d: round(s, 1) for d, s in sums.items() if counts[d] >= MIN_HOURS_PER_DAY}
    return daily, series


def actual_daily_kwh(
    rows_by_id: dict[str, list[dict[str, Any]]],
    units: dict[str, str | None],
    tz: tzinfo,
    before: date,
) -> dict[str, float]:
    """Measured PV energy per local date, summed over all meters.

    ``rows_by_id`` are hourly long-term statistics rows with a ``change`` value, which
    works for lifetime counters and daily-reset counters alike. A date only counts when
    every meter has at least ``MIN_HOURS_PER_DAY`` hourly rows for it (so an outage does
    not look like a dark day), and dates on or after ``before`` (today) are left out.
    """
    if not rows_by_id:
        return {}
    per_meter: list[tuple[dict[str, float], dict[str, int]]] = []
    for stat_id, rows in rows_by_id.items():
        sums: dict[str, float] = {}
        counts: dict[str, int] = {}
        unit = units.get(stat_id)
        for row in rows or ():
            start = row.get("start")
            ts = start.timestamp() if isinstance(start, datetime) else start
            change = row.get("change")
            if not isinstance(ts, (int, float)) or not isinstance(change, (int, float)) or not math.isfinite(change):
                continue
            kwh = energy_to_kwh(change, unit)
            if kwh is None:
                continue
            day = datetime.fromtimestamp(float(ts), UTC).astimezone(tz).date()
            if day >= before:
                continue
            key = day.isoformat()
            # A meter reset or replacement shows up as a large negative change: ignore it.
            sums[key] = sums.get(key, 0.0) + max(0.0, kwh)
            counts[key] = counts.get(key, 0) + 1
        per_meter.append((sums, counts))
    if len(per_meter) != len(rows_by_id):
        return {}
    days = set(per_meter[0][0])
    for sums, _ in per_meter[1:]:
        days &= set(sums)
    out: dict[str, float] = {}
    for day in days:
        if all(counts.get(day, 0) >= MIN_HOURS_PER_DAY for _, counts in per_meter):
            out[day] = round(sum(sums[day] for sums, _ in per_meter), 3)
    return out


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


class SolarLocalState:
    """Rolling per-day records. Keys of a day record (all optional):

    ``gti``       forecast GTI sum for that day, Wh/m2 (latest fetch that covered it)
    ``actual``    measured PV energy, kWh
    ``da_local``  this model's last prediction made before the day started, kWh
    ``da_fs``     forecast.solar's last prediction made before the day started, kWh
    """

    def __init__(self) -> None:
        self.days: dict[str, dict[str, float]] = {}
        self.meters: list[str] = []
        self.backfilled: bool = False
        # [lat, lon, tilt, compass azimuth] the stored ``gti`` sums were fetched for
        self.site: list[float] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"days": self.days, "meters": self.meters, "backfilled": self.backfilled, "site": self.site}

    @classmethod
    def from_dict(cls, data: Any) -> SolarLocalState:
        st = cls()
        if not isinstance(data, dict):
            return st
        raw_days = data.get("days")
        if isinstance(raw_days, dict):
            for day, rec in raw_days.items():
                if isinstance(day, str) and isinstance(rec, dict):
                    clean = {
                        k: float(v)
                        for k, v in rec.items()
                        if k in ("gti", "actual", "da_local", "da_fs")
                        and isinstance(v, (int, float))
                        and math.isfinite(v)
                    }
                    if clean:
                        st.days[day] = clean
        meters = data.get("meters")
        if isinstance(meters, list):
            st.meters = [str(m) for m in meters]
        st.backfilled = bool(data.get("backfilled", False))
        site = data.get("site")
        if (
            isinstance(site, list)
            and len(site) == 4
            and all(isinstance(v, (int, float)) and math.isfinite(v) for v in site)
        ):
            st.site = [float(v) for v in site]
        return st

    def reset_for_site(self, site: list[float]) -> bool:
        """Forget the irradiance history if the panel geometry or location changed.

        Each stored ``gti`` sum is for the plane it was fetched for. Fitting the site
        factor on one plane and forecasting on another skews every forecast (a tilt
        change from 30 to 18 degrees moved a November forecast by about 13%), so the
        sums are dropped and refetched by a new backfill. Measured energy and the
        day-ahead snapshots stay. A store without a recorded site counts as changed.
        """
        wanted = [round(float(v), 3) for v in site]
        if self.site == wanted:
            return False
        self.site = wanted
        had_gti = False
        for rec in self.days.values():
            had_gti = rec.pop("gti", None) is not None or had_gti
        if had_gti:
            self.backfilled = False
        return had_gti

    def reset_for_meters(self, meters: list[str]) -> bool:
        """Forget measured energy and the backfill flag if the meter set changed."""
        wanted = sorted(meters)
        if wanted == sorted(self.meters):
            return False
        for rec in self.days.values():
            rec.pop("actual", None)
        self.meters = wanted
        self.backfilled = False
        return True

    def set_value(self, day: str, key: str, value: float | None) -> None:
        if value is None or not math.isfinite(value):
            return
        self.days.setdefault(day, {})[key] = round(float(value), 3)

    def prune(self, today: date) -> None:
        cutoff = (today - timedelta(days=KEEP_DAYS)).isoformat()
        for day in [d for d in self.days if d < cutoff]:
            del self.days[day]


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------


def fit_factor(state: SolarLocalState, prior: float, today: date) -> tuple[float, int, str]:
    """Site factor ``k`` (kWh per kWh/m2 of GTI), the number of days used, and a status.

    Least squares through the origin over the last ``FIT_WINDOW_DAYS`` complete days,
    after dropping days whose ratio falls outside ``RATIO_BAND`` of the median ratio
    (meter outages, export or battery-full curtailment, snow on the panels). With fewer
    than ``MIN_FIT_DAYS`` days the result is shrunk toward the prior.
    """
    start = (today - timedelta(days=FIT_WINDOW_DAYS)).isoformat()
    end = today.isoformat()
    pairs = [
        (rec["gti"] / 1000.0, rec["actual"])
        for day, rec in state.days.items()
        if start <= day < end and rec.get("gti", 0.0) >= MIN_GTI_WHM2 and rec.get("actual", 0.0) > 0.0
    ]
    if not pairs:
        return prior, 0, STATUS_PRIOR
    mid = median(a / g for g, a in pairs)
    lo, hi = RATIO_BAND[0] * mid, RATIO_BAND[1] * mid
    kept = [(g, a) for g, a in pairs if lo <= a / g <= hi]
    if not kept:
        return prior, 0, STATUS_PRIOR
    k_fit = sum(g * a for g, a in kept) / sum(g * g for g, _ in kept)
    n = len(kept)
    if n >= MIN_FIT_DAYS:
        return k_fit, n, STATUS_TRAINED
    return (n * k_fit + PRIOR_WEIGHT_DAYS * prior) / (n + PRIOR_WEIGHT_DAYS), n, STATUS_LEARNING


def predict_kwh(k: float, gti_whm2: float | None) -> float | None:
    if gti_whm2 is None:
        return None
    return round(k * gti_whm2 / 1000.0, 2)


def hourly_kwh(
    k: float, series: list[tuple[float, float]], tz: tzinfo, first_day: date, last_day: date
) -> list[dict[str, Any]]:
    """Hourly forecast (local start time, kWh) for the local dates first_day..last_day."""
    out: list[dict[str, Any]] = []
    for start, wh in series:
        local = datetime.fromtimestamp(start, UTC).astimezone(tz)
        if first_day <= local.date() <= last_day:
            out.append({"start": local.isoformat(), "kwh": round(k * wh / 1000.0, 3)})
    return out


def remaining_kwh(hourly: list[dict[str, Any]], now: datetime) -> float | None:
    """Energy still to come today: the rest of the current hour plus later hours."""
    if not hourly:
        return None
    now_local = now.astimezone(datetime.fromisoformat(hourly[0]["start"]).tzinfo)
    today = now_local.date()
    total = 0.0
    found = False
    for item in hourly:
        start = datetime.fromisoformat(item["start"])
        if start.date() != today:
            continue
        found = True
        end = start + timedelta(hours=1)
        if end <= now:
            continue
        if start >= now:
            total += item["kwh"]
        else:
            total += item["kwh"] * (end - now).total_seconds() / 3600.0
    return round(total, 2) if found else None


def _stats(pairs: list[tuple[float, float]]) -> dict[str, Any] | None:
    """MAE, bias and Pearson correlation of (forecast, actual) pairs."""
    n = len(pairs)
    if n < MIN_SKILL_DAYS:
        return None
    errs = [f - a for f, a in pairs]
    out: dict[str, Any] = {
        "days": n,
        "mae_kwh": round(sum(abs(e) for e in errs) / n, 2),
        "bias_kwh": round(sum(errs) / n, 2),
        "correlation": None,
    }
    mf = sum(f for f, _ in pairs) / n
    ma = sum(a for _, a in pairs) / n
    vf = sum((f - mf) ** 2 for f, _ in pairs)
    va = sum((a - ma) ** 2 for _, a in pairs)
    if vf > 0 and va > 0:
        cov = sum((f - mf) * (a - ma) for f, a in pairs)
        out["correlation"] = round(cov / math.sqrt(vf * va), 3)
    return out


def skill(state: SolarLocalState, today: date) -> dict[str, Any]:
    """Day-ahead skill over the last SKILL_WINDOW_DAYS days, scored on the same days.

    Only days where both sources have a day-ahead snapshot are compared, when both
    exist at all, so the two sets of numbers describe the same weather.
    """
    start = (today - timedelta(days=SKILL_WINDOW_DAYS)).isoformat()
    end = today.isoformat()
    recs = [rec for day, rec in sorted(state.days.items()) if start <= day < end and "actual" in rec]
    both = [rec for rec in recs if "da_local" in rec and "da_fs" in rec]
    if len(both) >= MIN_SKILL_DAYS:
        local = _stats([(r["da_local"], r["actual"]) for r in both])
        fs = _stats([(r["da_fs"], r["actual"]) for r in both])
    else:
        local = _stats([(r["da_local"], r["actual"]) for r in recs if "da_local" in r])
        fs = _stats([(r["da_fs"], r["actual"]) for r in recs if "da_fs" in r])
    return {"local": local, "forecast_solar": fs}


__all__ = [
    "BACKFILL_DAYS",
    "STATUS_LEARNING",
    "STATUS_PRIOR",
    "STATUS_TRAINED",
    "STORE_VERSION",
    "SolarLocalState",
    "actual_daily_kwh",
    "build_url",
    "energy_to_kwh",
    "fit_factor",
    "hourly_kwh",
    "open_meteo_azimuth",
    "parse_gti",
    "predict_kwh",
    "prior_factor",
    "remaining_kwh",
    "skill",
    "store_key",
]
