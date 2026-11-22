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
RATIO_BAND = (0.7, 1.3)  # keep days near the typical uncurtailed yield
PRIOR_PERFORMANCE_RATIO = 0.80
MIN_HOURS_PER_DAY = 20  # sanity check for the irradiance series and fallback meter coverage
MIN_PRODUCTIVE_GTI_WHM2 = 25.0  # ignore night and low-irradiance twilight for meter coverage

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
        # Three GMT days also cover local tomorrow when it extends into the third UTC day.
        f"&past_days={max(0, min(BACKFILL_DAYS, int(past_days)))}&forecast_days=3"
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
    productive_hours: dict[str, set[int]] | None = None,
) -> dict[str, float]:
    """Measured PV energy per local date, summed over all meters.

    ``rows_by_id`` are hourly long-term statistics rows with a ``change`` value, which
    works for lifetime counters and daily-reset counters alike. A date only counts when
    every meter covers all modeled productive hours. With no irradiance coverage
    for a date, require ``MIN_HOURS_PER_DAY`` rows. Nighttime rows are optional
    when productive hours are known. Today and later are excluded.
    """
    if not rows_by_id:
        return {}
    per_meter: list[dict[str, dict[int, float]]] = []
    for stat_id, rows in rows_by_id.items():
        by_day: dict[str, dict[int, float]] = {}
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
            day = datetime.fromtimestamp(float(ts) + 1800, UTC).astimezone(tz).date()
            if day >= before:
                continue
            key = day.isoformat()
            # A meter reset or replacement shows up as a large negative change: ignore it.
            by_day.setdefault(key, {})[int(ts)] = max(0.0, kwh)
        per_meter.append(by_day)
    days = set.intersection(*(set(by_day) for by_day in per_meter))
    out: dict[str, float] = {}
    for day in days:
        required = (productive_hours or {}).get(day)
        meter_days = [by_day[day] for by_day in per_meter]
        if all(
            required <= readings.keys() if required else len(readings) >= MIN_HOURS_PER_DAY for readings in meter_days
        ):
            out[day] = round(sum(sum(readings.values()) for readings in meter_days), 3)
    return out


def productive_meter_hours(
    series: list[tuple[float, float]], complete_days: dict[str, float], tz: tzinfo
) -> dict[str, set[int]]:
    """Find hours with material irradiance on days covered by the forecast response."""
    hours: dict[str, set[int]] = {}
    for start, irradiance in series:
        if irradiance >= MIN_PRODUCTIVE_GTI_WHM2:
            day = datetime.fromtimestamp(start + 1800, UTC).astimezone(tz).date().isoformat()
            if day in complete_days:
                hours.setdefault(day, set()).add(int(start))
    return hours


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


def fit_factor(state: SolarLocalState, prior: float, today: date) -> tuple[float, int, str, int]:
    """Return the site factor, days used, fitting status, and days rejected.

    Anchor the ratio band to the median of the highest fifth of yields (at least
    seven days). Curtailment and snow reduce yield, so a productive minority can
    still anchor the fit. The median of that group limits the effect of isolated spikes.
    """
    start = (today - timedelta(days=FIT_WINDOW_DAYS)).isoformat()
    end = today.isoformat()
    pairs = [
        (rec["gti"] / 1000.0, rec["actual"])
        for day, rec in state.days.items()
        if start <= day < end and rec.get("gti", 0.0) >= MIN_GTI_WHM2 and rec.get("actual", 0.0) > 0.0
    ]
    if not pairs:
        return prior, 0, STATUS_PRIOR, 0
    ratios = sorted(a / g for g, a in pairs)
    mid = median(ratios[-max(MIN_FIT_DAYS, math.ceil(len(ratios) / 5)) :])
    lo, hi = RATIO_BAND[0] * mid, RATIO_BAND[1] * mid
    kept = [(g, a) for g, a in pairs if lo <= a / g <= hi]
    rejected = len(pairs) - len(kept)
    if not kept:
        return prior, 0, STATUS_PRIOR, rejected
    k_fit = sum(g * a for g, a in kept) / sum(g * g for g, _ in kept)
    n = len(kept)
    if n >= MIN_FIT_DAYS:
        return k_fit, n, STATUS_TRAINED, rejected
    return (n * k_fit + PRIOR_WEIGHT_DAYS * prior) / (n + PRIOR_WEIGHT_DAYS), n, STATUS_LEARNING, rejected


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


def remaining_kwh(hourly: list[dict[str, Any]], now: datetime, tz: tzinfo) -> float | None:
    """Energy still to come today: the rest of the current hour plus later hours."""
    if not hourly:
        return None
    today = now.astimezone(tz).date()
    now_ts = now.timestamp()
    total = 0.0
    found = False
    for item in hourly:
        start = datetime.fromisoformat(item["start"])
        if start.astimezone(tz).date() != today:
            continue
        found = True
        remaining_seconds = min(3600.0, max(0.0, start.timestamp() + 3600.0 - now_ts))
        total += item["kwh"] * remaining_seconds / 3600.0
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
    """Day-ahead skill over the last SKILL_WINDOW_DAYS days.

    Use shared dates when both sources have enough overlapping snapshots.
    Otherwise each source is scored on its own available dates.
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
