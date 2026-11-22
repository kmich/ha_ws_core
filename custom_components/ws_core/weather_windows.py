"""Weather Windows Decision Engine for Home Assistant (v3.0.0).

Finds suitable intervals in the next 24 hours based on profile constraints,
NWP hourly forecasts, and live local station observations.
"""

from __future__ import annotations

import logging
import math
from collections import deque
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, fields, replace
from datetime import UTC, datetime, timedelta, tzinfo
from typing import Any

from homeassistant.util import dt as dt_util

from . import localize
from .algorithms import solar_elevation_deg
from .const import (
    CONF_CUSTOM_MAX_CLOUD_COVER_PCT,
    CONF_CUSTOM_MAX_HUMIDITY_PCT,
    CONF_CUSTOM_MAX_RAIN_MM,
    CONF_CUSTOM_MAX_RAIN_PROB_PCT,
    CONF_CUSTOM_MAX_TEMP_C,
    CONF_CUSTOM_MAX_WIND_GUST_KMH,
    CONF_CUSTOM_MAX_WIND_KMH,
    CONF_CUSTOM_MIN_DURATION_H,
    CONF_CUSTOM_MIN_HUMIDITY_PCT,
    CONF_CUSTOM_MIN_TEMP_C,
    CONF_CUSTOM_MIN_WIND_KMH,
    CONF_CUSTOM_REQUIRE_DAYLIGHT,
    CONF_CUSTOM_WINDOW_NAME,
    CONF_WEATHER_WINDOW_PROFILES,
    DEFAULT_WEATHER_WINDOW_PROFILES,
    KEY_NORM_WIND_GUST_MS,
    KEY_RAIN_RATE_FILT,
    PROFILE_CUSTOM,
    PROFILE_GARDEN_WORK,
    PROFILE_OUTDOOR_DRYING,
    SRC_GUST,
    SRC_RAIN_TOTAL,
    SRC_WIND,
)

_LOGGER = logging.getLogger(__name__)

MAX_HORIZON_HOURS = 24
# The horizon ends on the last full local hour and the current hour is partly elapsed, so a
# 24-hour minimum could never be met; longer stored values are clamped to this.
MAX_MIN_DURATION_H = MAX_HORIZON_HOURS - 1
# Rows further apart than this are not an hourly series (for example 3-hourly entity data).
_HOURLY_STEP_TOLERANCE_S = 3601.0
_ONE_HOUR = timedelta(hours=1)
_LIVE_GUST_ON_HOLD_S = 180.0
_LIVE_GUST_OFF_HOLD_S = 300.0
_LIVE_HOLD_STALE_GAP_S = 1800.0
# Record the onset and clear holds, plus the freshness interval across an outage.
_GUST_SAMPLE_WINDOW_S = _LIVE_HOLD_STALE_GAP_S + _LIVE_GUST_ON_HOLD_S + _LIVE_GUST_OFF_HOLD_S
_NON_LIMIT_FIELDS = frozenset(("profile_id", "name", "description", "enabled"))

_NUMERIC_LIMIT_FIELDS: tuple[str, ...] = (
    "max_rain_prob_pct",
    "max_rain_mm",
    "min_temp_c",
    "max_temp_c",
    "min_humidity_pct",
    "max_humidity_pct",
    "min_wind_kmh",
    "max_wind_kmh",
    "max_wind_gust_kmh",
    "max_cloud_cover_pct",
)

_WIND_KMH_FACTORS: dict[str, float] = {
    "km/h": 1.0,
    "m/s": 1.0 / 3.6,
    "mph": 0.62137119,
    "kn": 0.5399568,
}


# Decision status outcomes
STATUS_SUITABLE_NOW = "suitable_now"
STATUS_WINDOW_UPCOMING = "window_upcoming"
STATUS_UNSUITABLE = "unsuitable"
STATUS_UNKNOWN = "unknown"
WINDOW_STATUSES: tuple[str, ...] = (STATUS_SUITABLE_NOW, STATUS_WINDOW_UPCOMING, STATUS_UNSUITABLE, STATUS_UNKNOWN)

# Reason codes
REASON_SUITABLE = "suitable"
REASON_WINDOW_UPCOMING = "window_upcoming"
REASON_WINDOW_INTERRUPTED = "window_interrupted"
REASON_CURRENTLY_RAINING = "currently_raining"
REASON_CURRENT_GUST_HIGH = "current_gust_high"
REASON_RAIN_RISK = "rain_risk"
REASON_RAIN_AMOUNT = "rain_amount"
REASON_TOO_COLD = "too_cold"
REASON_TOO_HOT = "too_hot"
REASON_HIGH_HUMIDITY = "high_humidity"
REASON_LOW_HUMIDITY = "low_humidity"
REASON_CALM_AIR = "calm_air"
REASON_HIGH_WIND = "high_wind"
REASON_HIGH_GUST = "high_gust"
REASON_HEAVY_CLOUDS = "heavy_clouds"  # Cloud cover proxy for sunshine
REASON_NIGHTTIME = "nighttime"
REASON_MISSING_DATA = "missing_data"
REASON_NOT_ASSESSED_BY_PROVIDER = "not_assessed_by_provider"
REASON_INSUFFICIENT_HORIZON = "insufficient_horizon"
REASON_SHORT_WINDOW = "short_window"
REASON_FORECAST_UNAVAILABLE = "forecast_unavailable"
REASON_FORECAST_TOO_COARSE = "forecast_too_coarse"
REASON_FORECAST_TOO_FINE = "forecast_too_fine"
REASON_HORIZON_TRUNCATED = "horizon_truncated"


@dataclass
class WeatherWindowProfile:
    """Configurable limits for an activity profile."""

    profile_id: str
    name: str
    description: str
    enabled: bool = True
    min_duration_h: int = 2
    max_rain_prob_pct: float | None = 20.0
    max_rain_mm: float | None = 0.0
    min_temp_c: float | None = 10.0
    max_temp_c: float | None = None
    min_humidity_pct: float | None = None
    max_humidity_pct: float | None = 75.0
    min_wind_kmh: float | None = 3.0
    max_wind_kmh: float | None = None
    max_wind_gust_kmh: float | None = 45.0
    max_cloud_cover_pct: float | None = 80.0  # Proxy for sunshine
    require_daylight: bool = True


DEFAULT_PROFILES: dict[str, WeatherWindowProfile] = {
    PROFILE_OUTDOOR_DRYING: WeatherWindowProfile(
        profile_id=PROFILE_OUTDOOR_DRYING,
        name="Outdoor Laundry Drying",
        description="Dry laundry outdoors with favorable temperature, wind, and low rain risk",
        enabled=True,
        min_duration_h=2,
        max_rain_prob_pct=20.0,
        max_rain_mm=0.0,
        min_temp_c=10.0,
        max_temp_c=38.0,
        min_humidity_pct=None,
        max_humidity_pct=75.0,
        min_wind_kmh=3.0,
        max_wind_kmh=35.0,
        max_wind_gust_kmh=45.0,
        max_cloud_cover_pct=80.0,
        require_daylight=True,
    ),
    PROFILE_GARDEN_WORK: WeatherWindowProfile(
        profile_id=PROFILE_GARDEN_WORK,
        name="Garden Work",
        description="Mow, prune, or tend the garden without rain, extreme cold, heat, or high winds",
        enabled=True,
        min_duration_h=2,
        max_rain_prob_pct=30.0,
        max_rain_mm=0.1,
        min_temp_c=8.0,
        max_temp_c=32.0,
        min_humidity_pct=None,
        max_humidity_pct=90.0,
        min_wind_kmh=None,
        max_wind_kmh=25.0,
        max_wind_gust_kmh=40.0,
        max_cloud_cover_pct=None,
        require_daylight=True,
    ),
    PROFILE_CUSTOM: WeatherWindowProfile(
        profile_id=PROFILE_CUSTOM,
        name="Custom Activity",
        description="User-defined activity window limits",
        enabled=False,
        min_duration_h=2,
        max_rain_prob_pct=25.0,
        max_rain_mm=0.0,
        min_temp_c=12.0,
        max_temp_c=30.0,
        min_humidity_pct=None,
        max_humidity_pct=80.0,
        min_wind_kmh=None,
        max_wind_kmh=30.0,
        max_wind_gust_kmh=50.0,
        max_cloud_cover_pct=None,
        require_daylight=False,
    ),
}


def resolve_profiles(config: Mapping[str, Any] | None = None) -> dict[str, WeatherWindowProfile]:
    """Resolve enabled weather window profiles and configured custom limits from config/options."""
    if (
        config is not None
        and CONF_WEATHER_WINDOW_PROFILES in config
        and config[CONF_WEATHER_WINDOW_PROFILES] is not None
    ):
        raw = config[CONF_WEATHER_WINDOW_PROFILES]
    else:
        raw = DEFAULT_WEATHER_WINDOW_PROFILES
    selected = {raw} if isinstance(raw, str) else set(raw)

    base_custom = DEFAULT_PROFILES[PROFILE_CUSTOM]
    custom_profile = base_custom
    if config is not None:
        overrides: dict[str, Any] = {}
        for nested_key in ("custom_profile", "custom_window_limits", "custom_limits"):
            nested = config.get(nested_key)
            if isinstance(nested, Mapping):
                overrides.update(nested)
        for flat_key, target_key in (
            ("custom_name", "name"),
            (CONF_CUSTOM_WINDOW_NAME, "name"),
            ("min_duration_h", "min_duration_h"),
            (CONF_CUSTOM_MIN_DURATION_H, "min_duration_h"),
            ("require_daylight", "require_daylight"),
            (CONF_CUSTOM_REQUIRE_DAYLIGHT, "require_daylight"),
        ):
            if flat_key in config:
                overrides[target_key] = config[flat_key]
        prefixed_numeric = {
            "max_rain_prob_pct": CONF_CUSTOM_MAX_RAIN_PROB_PCT,
            "max_rain_mm": CONF_CUSTOM_MAX_RAIN_MM,
            "min_temp_c": CONF_CUSTOM_MIN_TEMP_C,
            "max_temp_c": CONF_CUSTOM_MAX_TEMP_C,
            "min_humidity_pct": CONF_CUSTOM_MIN_HUMIDITY_PCT,
            "max_humidity_pct": CONF_CUSTOM_MAX_HUMIDITY_PCT,
            "min_wind_kmh": CONF_CUSTOM_MIN_WIND_KMH,
            "max_wind_kmh": CONF_CUSTOM_MAX_WIND_KMH,
            "max_wind_gust_kmh": CONF_CUSTOM_MAX_WIND_GUST_KMH,
            "max_cloud_cover_pct": CONF_CUSTOM_MAX_CLOUD_COVER_PCT,
        }
        for field_name, conf_key in prefixed_numeric.items():
            if conf_key in config:
                overrides[field_name] = config[conf_key]
            elif field_name in config:
                overrides[field_name] = config[field_name]
        if overrides:
            try:
                custom_profile = apply_profile_overrides(base_custom, overrides, profile_id=PROFILE_CUSTOM)
            except ValueError as err:
                _LOGGER.debug("Ignoring invalid stored custom profile overrides (%s): %s", overrides, err)
                custom_profile = base_custom

    resolved = {pid: replace(prof, enabled=(pid in selected)) for pid, prof in DEFAULT_PROFILES.items()}
    resolved[PROFILE_CUSTOM] = replace(custom_profile, enabled=(PROFILE_CUSTOM in selected))
    return resolved


def _coerce_positive_int(val: Any) -> int:
    """Validate integer >= 1, rejecting booleans, fractions, and non-finite floats."""
    if isinstance(val, bool):
        raise ValueError("min_duration_h must be an integer >= 1")
    if isinstance(val, int):
        out = val
    elif isinstance(val, float):
        if not math.isfinite(val) or not val.is_integer():
            raise ValueError("min_duration_h must be a whole integer >= 1")
        out = int(val)
    elif isinstance(val, str):
        try:
            out = int(val.strip())
        except ValueError as err:
            raise ValueError("min_duration_h must be a whole integer >= 1") from err
    else:
        raise ValueError("min_duration_h must be a whole integer >= 1")
    if out < 1:
        raise ValueError("min_duration_h must be >= 1")
    return min(out, MAX_MIN_DURATION_H)


def apply_profile_overrides(
    base: WeatherWindowProfile,
    overrides: Mapping[str, Any],
    profile_id: str | None = None,
) -> WeatherWindowProfile:
    """Create a profile by applying partial overrides onto ``base`` while keeping omitted limits."""
    changes: dict[str, Any] = {"enabled": True}
    if profile_id is not None:
        changes["profile_id"] = profile_id
    if "name" in overrides and overrides["name"] is not None:
        cleaned_name = str(overrides["name"]).strip()
        if cleaned_name:
            changes["name"] = cleaned_name
    if "min_duration_h" in overrides and overrides["min_duration_h"] is not None:
        changes["min_duration_h"] = _coerce_positive_int(overrides["min_duration_h"])
    for field_name in _NUMERIC_LIMIT_FIELDS:
        if field_name not in overrides:
            continue
        raw_val = overrides[field_name]
        if raw_val is None:
            changes[field_name] = None
            continue
        if isinstance(raw_val, bool):
            raise ValueError(f"{field_name} must be a finite number")
        try:
            num = float(raw_val)
        except (TypeError, ValueError) as err:
            raise ValueError(f"{field_name} must be a finite number") from err
        if not math.isfinite(num):
            raise ValueError(f"{field_name} must be finite")
        if field_name.endswith("_pct") and not 0 <= num <= 100:
            raise ValueError(f"{field_name} must be between 0 and 100")
        if (field_name.endswith("_kmh") or field_name == "max_rain_mm") and num < 0:
            raise ValueError(f"{field_name} must be non-negative")
        changes[field_name] = num
    if "require_daylight" in overrides and overrides["require_daylight"] is not None:
        changes["require_daylight"] = bool(overrides["require_daylight"])
    updated = replace(base, **changes)
    if updated.min_temp_c is not None and updated.max_temp_c is not None and updated.min_temp_c > updated.max_temp_c:
        raise ValueError("min_temp_c cannot exceed max_temp_c")
    if (
        updated.min_humidity_pct is not None
        and updated.max_humidity_pct is not None
        and updated.min_humidity_pct > updated.max_humidity_pct
    ):
        raise ValueError("min_humidity_pct cannot exceed max_humidity_pct")
    if (
        updated.min_wind_kmh is not None
        and updated.max_wind_kmh is not None
        and updated.min_wind_kmh > updated.max_wind_kmh
    ):
        raise ValueError("min_wind_kmh cannot exceed max_wind_kmh")
    if (
        updated.min_wind_kmh is not None
        and updated.max_wind_gust_kmh is not None
        and updated.min_wind_kmh > updated.max_wind_gust_kmh
    ):
        raise ValueError("min_wind_kmh cannot exceed max_wind_gust_kmh")
    return updated


def _as_finite_float(val: Any) -> float | None:
    """Convert non-bool numeric inputs to finite float, else None."""
    t = type(val)
    if t is float:
        return val if math.isfinite(val) else None
    if t is int:
        return float(val)
    if val is None or t is bool:
        return None
    try:
        num = float(val)
    except (TypeError, ValueError):
        return None
    return num if math.isfinite(num) else None


@dataclass
class WeatherDecisionResult:
    """Standardized decision engine result contract (v3.0.0)."""

    profile_id: str
    status: str
    evaluated_at: str
    next_start: str | None = None
    next_end: str | None = None
    duration_h: int | float | None = None
    remaining_h: int | float | None = None
    horizon_hours: int = 0
    is_truncated: bool = False
    reason_codes: list[str] = field(default_factory=list)
    reasons_text: list[str] = field(default_factory=list)
    not_assessed_by_provider: list[str] = field(default_factory=list)
    evaluated_limits: dict[str, Any] = field(default_factory=dict)
    windows: list[dict[str, Any]] = field(default_factory=list)
    slots: list[dict[str, Any]] = field(default_factory=list)
    data_quality: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert result to JSON-serializable dictionary."""
        return {
            "profile_id": self.profile_id,
            "status": self.status,
            "evaluated_at": self.evaluated_at,
            "next_start": self.next_start,
            "next_end": self.next_end,
            "duration_h": self.duration_h,
            "remaining_h": self.remaining_h,
            "horizon_hours": self.horizon_hours,
            "is_truncated": self.is_truncated,
            "reason_codes": self.reason_codes,
            "reasons_text": self.reasons_text,
            "not_assessed_by_provider": self.not_assessed_by_provider,
            "evaluated_limits": self.evaluated_limits,
            "windows": self.windows,
            "slots": self.slots,
            "data_quality": self.data_quality,
        }


_MISSING = object()


def _parse_raw_dt_str(key: str, dt_cache: dict[str, datetime | None] | None = None) -> datetime | None:
    """Parse an ISO or Home Assistant datetime string, optionally caching results."""
    if dt_cache is not None and key in dt_cache:
        return dt_cache[key]
    parsed: datetime | None = None
    if "T" in key or " " in key:
        try:
            parsed = datetime.fromisoformat(key)
        except ValueError:
            parsed = None
    if parsed is None:
        try:
            parsed = dt_util.parse_datetime(key)
        except ValueError:
            parsed = None
    if dt_cache is not None:
        if len(dt_cache) > 512:
            dt_cache.clear()
        dt_cache[key] = parsed
    return parsed


def _resolve_eval_clock(now: datetime | None = None) -> tuple[tzinfo, datetime, float]:
    """Resolve (display_tz, now_utc, now_ts) consistently across decision engine and summary."""
    eval_now = now or dt_util.now()
    display_tz = dt_util.get_default_time_zone()
    if eval_now.tzinfo is not None and eval_now.tzinfo is not UTC:
        display_tz = eval_now.tzinfo
    now_utc = (
        eval_now.replace(tzinfo=display_tz).astimezone(UTC) if eval_now.tzinfo is None else eval_now.astimezone(UTC)
    )
    return display_tz, now_utc, now_utc.timestamp()


def _horizon_end_utc(now_utc: datetime, display_tz: tzinfo) -> datetime:
    """Return the evaluation horizon end: now + 24 h, floored to the local hour.

    Flooring keeps window end times stable within an hour, so a window that runs to the
    end of the horizon does not move its end time (and its timestamp sensor) every minute.
    """
    local_end = (now_utc + timedelta(hours=MAX_HORIZON_HOURS)).astimezone(display_tz)
    return local_end.replace(minute=0, second=0, microsecond=0).astimezone(UTC)


def parse_forecast_slot_utc(
    item: Mapping[str, Any],
    display_tz: tzinfo,
    dt_cache: dict[str, datetime | None] | None = None,
) -> datetime | None:
    """Parse an hourly forecast item timestamp into UTC, preserving DST distinct hours."""
    raw_dt = item.get("utc_datetime")
    if raw_dt is None or raw_dt == "":
        raw_dt = item.get("datetime")
    if raw_dt is None or raw_dt == "":
        return None
    if isinstance(raw_dt, datetime):
        return _forecast_datetime_utc(raw_dt, display_tz)
    if isinstance(raw_dt, (int, float)):
        if isinstance(raw_dt, bool) or not math.isfinite(raw_dt):
            return None
        try:
            return datetime.fromtimestamp(raw_dt, tz=UTC)
        except (OverflowError, OSError, ValueError):
            return None
    parsed = _parse_raw_dt_str(raw_dt if type(raw_dt) is str else str(raw_dt), dt_cache)
    if parsed is None:
        return None
    return _forecast_datetime_utc(parsed, display_tz)


def _forecast_datetime_utc(parsed: datetime, display_tz: tzinfo, *, fold: int = 0) -> datetime | None:
    """Preserve repeated local hours and reject nonexistent spring-forward hours."""
    if parsed.tzinfo is not None:
        return parsed.astimezone(UTC)
    if display_tz is UTC:
        return parsed.replace(tzinfo=UTC)
    instant = parsed.replace(tzinfo=display_tz, fold=fold).astimezone(UTC)
    return instant if instant.astimezone(display_tz).replace(tzinfo=None) == parsed else None


def _collect_horizon_slots(
    hourly_forecast: list[dict[str, Any]],
    now_ts: float,
    display_tz: tzinfo,
    slot_time_cache: dict[tuple[str, tzinfo], tuple[datetime, float, str] | None] | None = None,
    dt_cache: dict[str, datetime | None] | None = None,
    horizon_end_ts: float | None = None,
) -> dict[float, tuple[datetime, str, Mapping[str, Any]]]:
    """Parse, deduplicate, and filter hourly slots to [now - 1h, horizon end)."""
    deduped: dict[float, tuple[datetime, str, Mapping[str, Any]]] = {}
    end_ts = horizon_end_ts if horizon_end_ts is not None else now_ts + MAX_HORIZON_HOURS * 3600.0
    is_utc_display = display_tz is UTC
    seen_raw: set[str] = set()
    for item in hourly_forecast:
        if not isinstance(item, Mapping):
            continue
        raw_dt = item.get("utc_datetime")
        if raw_dt is None or raw_dt == "":
            raw_dt = item.get("datetime")
        if raw_dt is None or raw_dt == "":
            continue
        repeated_naive: datetime | None = None
        if type(raw_dt) is str:
            if raw_dt in seen_raw:
                again = _parse_raw_dt_str(raw_dt, dt_cache)
                if again is not None and again.tzinfo is None:
                    repeated_naive = again
            seen_raw.add(raw_dt)
        if repeated_naive is not None:
            slot_utc = _forecast_datetime_utc(repeated_naive, display_tz, fold=1)
            if slot_utc is None:
                continue
            slot_ts = slot_utc.timestamp()
            display_iso = slot_utc.isoformat() if is_utc_display else slot_utc.astimezone(display_tz).isoformat()
        elif type(raw_dt) is str and slot_time_cache is not None:
            cache_key = (raw_dt, display_tz)
            cached_t = slot_time_cache.get(cache_key, _MISSING)
            if cached_t is _MISSING:
                parsed = _parse_raw_dt_str(raw_dt, dt_cache)
                slot_utc = _forecast_datetime_utc(parsed, display_tz) if parsed is not None else None
                if slot_utc is None:
                    if len(slot_time_cache) > 512:
                        slot_time_cache.clear()
                    slot_time_cache[cache_key] = None
                    continue
                slot_ts = slot_utc.timestamp()
                display_iso = slot_utc.isoformat() if is_utc_display else slot_utc.astimezone(display_tz).isoformat()
                if len(slot_time_cache) > 512:
                    slot_time_cache.clear()
                slot_time_cache[cache_key] = (slot_utc, slot_ts, display_iso)
            elif cached_t is None:
                continue
            else:
                slot_utc, slot_ts, display_iso = cached_t
        else:
            slot_utc = parse_forecast_slot_utc(item, display_tz, dt_cache)
            if slot_utc is None:
                continue
            slot_ts = slot_utc.timestamp()
            display_iso = slot_utc.isoformat() if is_utc_display else slot_utc.astimezone(display_tz).isoformat()
        if slot_ts + 3600.0 - now_ts <= 0.0:
            continue
        if slot_ts >= end_ts:
            continue
        if slot_ts not in deduped:
            deduped[slot_ts] = (slot_utc, display_iso, item)
    return deduped


def count_usable_hourly_horizon_h(
    hourly_forecast: list[dict[str, Any]] | None,
    now: datetime | None = None,
) -> int:
    """Count distinct usable hourly forecast slots within the 24-hour evaluation horizon."""
    if not hourly_forecast:
        return 0
    display_tz, now_utc, now_ts = _resolve_eval_clock(now)
    horizon_end_ts = _horizon_end_utc(now_utc, display_tz).timestamp()
    deduped = _collect_horizon_slots(hourly_forecast, now_ts, display_tz, dt_cache={}, horizon_end_ts=horizon_end_ts)
    return min(len(deduped), MAX_HORIZON_HOURS)


def _extract_contiguous_windows(
    flags: list[bool],
    prepared_slots: list[tuple[Any, ...]],
    min_span_s: float,
    now_ts: float,
    horizon_end_ts: float,
    horizon_end_utc: datetime,
    last_slot_ts: float,
    display_tz: tzinfo,
    is_utc_display: bool,
    remembered: dict[str, Any] | None,
) -> list[tuple[float, float, dict[str, Any]]]:
    """Extract contiguous suitable/potential intervals meeting ``min_span_s``."""
    out: list[tuple[float, float, dict[str, Any]]] = []
    n_slots = len(prepared_slots)
    idx = 0
    while idx < n_slots:
        if not flags[idx]:
            idx += 1
            continue
        streak_start_idx = idx
        while (
            idx + 1 < n_slots
            and flags[idx + 1]
            and abs((prepared_slots[idx + 1][1] - prepared_slots[idx][1]) - 3600.0) <= 1.0
        ):
            idx += 1
        s_slot = prepared_slots[streak_start_idx]
        e_slot = prepared_slots[idx]
        s_ts: float = s_slot[1]
        raw_e_ts: float = e_slot[1] + 3600.0
        e_ts = raw_e_ts if raw_e_ts <= horizon_end_ts else horizon_end_ts
        start_iso = s_slot[2]
        if (
            remembered is not None
            and s_ts <= now_ts < e_ts
            and remembered["start_ts"] < s_ts
            and remembered["end_ts"] >= s_ts - 1.0
        ):
            s_ts, start_iso = remembered["start_ts"], remembered["start_iso"]
        span_s = e_ts - s_ts
        if span_s >= min_span_s:
            raw_h = round(span_s / 3600.0, 2)
            dur_h: int | float = int(raw_h) if raw_h.is_integer() else raw_h
            next_idx = idx + 1
            if e_ts != horizon_end_ts and next_idx < n_slots and abs(prepared_slots[next_idx][1] - raw_e_ts) < 1.0:
                end_iso: str = prepared_slots[next_idx][2]
            else:
                end_dt = horizon_end_utc if e_ts == horizon_end_ts else (e_slot[0] + _ONE_HOUR)
                end_iso = end_dt.isoformat() if is_utc_display else end_dt.astimezone(display_tz).isoformat()
            out.append(
                (
                    s_ts,
                    e_ts,
                    {
                        "start_iso": start_iso,
                        "end_iso": end_iso,
                        "duration_h": dur_h,
                        "remaining_h": round((e_ts - max(s_ts, now_ts)) / 3600.0, 2),
                        "is_truncated": e_slot[1] == last_slot_ts or raw_e_ts > horizon_end_ts,
                    },
                )
            )
        idx += 1
    return out


class WeatherWindowsEngine:
    """Evaluates weather windows across configured profiles."""

    def __init__(
        self,
        lat: float,
        lon: float,
        elevation_m: float = 0.0,
        profiles: dict[str, WeatherWindowProfile] | None = None,
        *,
        language: str = "en",
        temp_unit: str = "°C",
        wind_unit: str = "km/h",
        rain_unit: str = "mm",
    ) -> None:
        self.lat = lat
        self.lon = lon
        self.elevation_m = elevation_m
        self.profiles: dict[str, WeatherWindowProfile] = dict(profiles if profiles is not None else DEFAULT_PROFILES)
        self.language = language
        self.temp_unit = temp_unit
        self.wind_unit = wind_unit
        self.rain_unit = rain_unit
        self._solar_coord: tuple[float, float] | None = None
        self._solar_cache: dict[datetime, float] = {}
        self._parse_dt_cache: dict[str, datetime | None] = {}
        self._slot_time_cache: dict[tuple[str, tzinfo], tuple[datetime, float, str] | None] = {}
        self._gust_hold_state: dict[str, dict[str, Any]] = {}
        self._gust_samples: deque[tuple[float, float | None]] = deque()
        self._open_window_start: dict[str, dict[str, Any]] = {}

    def _sync_solar_cache(self, lat_f: float, lon_f: float) -> dict[datetime, float]:
        """Return solar elevation cache cleared only when rounded coordinates change."""
        coord_key = (round(lat_f, 5), round(lon_f, 5))
        if self._solar_coord != coord_key:
            self._solar_coord = coord_key
            self._solar_cache.clear()
        return self._solar_cache

    @staticmethod
    def _validate_profile(profile: WeatherWindowProfile) -> dict[str, Any]:
        """Validate profile thresholds and return the evaluated limits mapping."""
        if (
            isinstance(profile.min_duration_h, bool)
            or not isinstance(profile.min_duration_h, int)
            or profile.min_duration_h < 1
        ):
            raise ValueError("min_duration_h must be an integer >= 1")
        for field_name in _NUMERIC_LIMIT_FIELDS:
            threshold = getattr(profile, field_name)
            if threshold is not None and (isinstance(threshold, bool) or not math.isfinite(float(threshold))):
                raise ValueError(f"{field_name} must be finite")
        return {
            "min_duration_h": profile.min_duration_h,
            "max_rain_prob_pct": profile.max_rain_prob_pct,
            "max_rain_mm": profile.max_rain_mm,
            "min_temp_c": profile.min_temp_c,
            "max_temp_c": profile.max_temp_c,
            "min_humidity_pct": profile.min_humidity_pct,
            "max_humidity_pct": profile.max_humidity_pct,
            "min_wind_kmh": profile.min_wind_kmh,
            "max_wind_kmh": profile.max_wind_kmh,
            "max_wind_gust_kmh": profile.max_wind_gust_kmh,
            "max_cloud_cover_pct": profile.max_cloud_cover_pct,
            "require_daylight": profile.require_daylight,
        }

    def _prepare_evaluation(
        self,
        hourly_forecast: list[dict[str, Any]] | None,
        current_data: dict[str, Any] | None,
        now: datetime | None,
    ) -> dict[str, Any]:
        """Parse and normalize hourly forecast and live station state once across profiles."""
        display_tz, now_utc, now_ts = _resolve_eval_clock(now)
        evaluated_at_iso = now_utc.isoformat()
        horizon_end_utc = _horizon_end_utc(now_utc, display_tz)
        horizon_end_ts = horizon_end_utc.timestamp()

        current = current_data or {}
        stale_raw = current.get("_stale_sources") or current.get("stale_sources")
        stale_set = {str(s) for s in stale_raw} if stale_raw else set()
        live_rain_rate = (
            None
            if stale_set & {SRC_RAIN_TOTAL, "rain", "rain_rate"}
            else _as_finite_float(current.get(KEY_RAIN_RATE_FILT))
        )
        live_gust_ms = (
            None
            if stale_set & {SRC_GUST, SRC_WIND, "gust", "wind"}
            else _as_finite_float(current.get(KEY_NORM_WIND_GUST_MS))
        )

        has_forecast_rows = bool(hourly_forecast)
        prepared_slots: list[tuple[Any, ...]] = []
        current_hour_estimated = False
        has_temp = False
        has_rain_prob = False
        has_rain_mm = False
        has_humidity = False
        has_wind = False
        has_gust = False
        has_cloud = False

        if hourly_forecast:
            deduped = _collect_horizon_slots(
                hourly_forecast,
                now_ts,
                display_tz,
                slot_time_cache=self._slot_time_cache,
                dt_cache=self._parse_dt_cache,
                horizon_end_ts=horizon_end_ts,
            )

            if deduped:
                lat_f = float(self.lat)
                lon_f = float(self.lon)
                solar_cache = self._sync_solar_cache(lat_f, lon_f)
                prev_end_ts: float | None = None
                prev_end_elev: float | None = None

                for slot_ts in sorted(deduped):
                    slot_utc, display_iso, item = deduped[slot_ts]
                    raw_end_ts = slot_ts + 3600.0
                    eff_start_ts = slot_ts if slot_ts >= now_ts else now_ts
                    eff_end_ts = raw_end_ts if raw_end_ts <= horizon_end_ts else horizon_end_ts

                    if prev_end_ts == eff_start_ts and prev_end_elev is not None:
                        sol_elev_start = prev_end_elev
                    else:
                        eff_start_dt = slot_utc if eff_start_ts == slot_ts else now_utc
                        sol_elev_start = solar_cache.get(eff_start_dt)
                        if sol_elev_start is None:
                            sol_elev_start = solar_elevation_deg(lat_f, lon_f, eff_start_dt)
                            if len(solar_cache) > 512:
                                solar_cache.clear()
                            solar_cache[eff_start_dt] = sol_elev_start

                    eff_end_dt = (slot_utc + _ONE_HOUR) if eff_end_ts == raw_end_ts else horizon_end_utc
                    sol_elev_end = solar_cache.get(eff_end_dt)
                    if sol_elev_end is None:
                        sol_elev_end = solar_elevation_deg(lat_f, lon_f, eff_end_dt)
                        if len(solar_cache) > 512:
                            solar_cache.clear()
                        solar_cache[eff_end_dt] = sol_elev_end

                    prev_end_ts = eff_end_ts
                    prev_end_elev = sol_elev_end
                    sol_elev = sol_elev_start if sol_elev_start < sol_elev_end else sol_elev_end
                    is_night = sol_elev_start <= 0.0 or sol_elev_end <= 0.0
                    sol_elev_rounded = round(sol_elev, 1)

                    temp_c = _as_finite_float(item.get("temp_c"))
                    rain_prob = _as_finite_float(item.get("precip_prob"))
                    rain_mm = _as_finite_float(item.get("precip_mm"))
                    humidity = _as_finite_float(item.get("humidity"))
                    wind_kmh = _as_finite_float(item.get("wind_kmh"))
                    gust_kmh = _as_finite_float(item.get("gust_kmh"))
                    cloud_cover = _as_finite_float(item.get("cloud_cover"))
                    is_current = slot_ts <= now_ts < raw_end_ts
                    if is_current and item.get("estimated_from_next_hour"):
                        current_hour_estimated = True

                    if temp_c is not None:
                        has_temp = True
                    if rain_prob is not None:
                        has_rain_prob = True
                    if rain_mm is not None:
                        has_rain_mm = True
                    if humidity is not None:
                        has_humidity = True
                    if wind_kmh is not None:
                        has_wind = True
                    if gust_kmh is not None:
                        has_gust = True
                    if cloud_cover is not None:
                        has_cloud = True

                    prepared_slots.append(
                        (
                            slot_utc,
                            slot_ts,
                            display_iso,
                            temp_c,
                            rain_prob,
                            rain_mm,
                            humidity,
                            wind_kmh,
                            gust_kmh,
                            cloud_cover,
                            is_night,
                            sol_elev_rounded,
                            is_current,
                        )
                    )

        return {
            "now_utc": now_utc,
            "now_ts": now_ts,
            "display_tz": display_tz,
            "evaluated_at_iso": evaluated_at_iso,
            "horizon_end_utc": horizon_end_utc,
            "horizon_end_ts": horizon_end_ts,
            "live_rain_rate": live_rain_rate,
            "live_gust_ms": live_gust_ms,
            "has_forecast_rows": has_forecast_rows,
            "current_hour_estimated": current_hour_estimated,
            "available_vars": {
                "temp_c": has_temp,
                "precip_prob": has_rain_prob,
                "precip_mm": has_rain_mm,
                "humidity": has_humidity,
                "wind_kmh": has_wind,
                "gust_kmh": has_gust,
                "cloud_cover": has_cloud,
            },
            "slots": prepared_slots,
        }

    def evaluate_profiles(
        self,
        profiles: Iterable[WeatherWindowProfile],
        hourly_forecast: list[dict[str, Any]] | None,
        current_data: dict[str, Any] | None = None,
        now: datetime | None = None,
        *,
        update_live_hold: bool = True,
    ) -> dict[str, dict[str, Any]]:
        """Evaluate multiple profiles in one pass over parsed forecast slots (returns dict contracts).

        ``update_live_hold=False`` reads the tracked state (live gust hold, open-window start)
        without changing it, so on-demand action calls cannot alter what the sensors track.
        """
        prof_list = list(profiles)
        if not prof_list:
            return {}
        prepared = self._prepare_evaluation(hourly_forecast, current_data, now)
        return {
            prof.profile_id: self._evaluate_prepared_profile(
                prof, prepared, as_dict=True, update_live_hold=update_live_hold
            )
            for prof in prof_list
        }

    def evaluate_profile(
        self,
        profile: WeatherWindowProfile,
        hourly_forecast: list[dict[str, Any]] | None,
        current_data: dict[str, Any] | None = None,
        now: datetime | None = None,
        *,
        update_live_hold: bool = True,
    ) -> WeatherDecisionResult:
        """Evaluate a profile against forecast and live station conditions."""
        prepared = self._prepare_evaluation(hourly_forecast, current_data, now)
        return self._evaluate_prepared_profile(profile, prepared, as_dict=False, update_live_hold=update_live_hold)

    @staticmethod
    def _new_gust_hold(threshold: float, exceeds: bool, now_ts: float) -> dict[str, Any]:
        return {
            "threshold": threshold,
            "active": False,
            "exceeded_since": now_ts if exceeds else None,
            "clear_since": None,
            "last_ts": now_ts,
        }

    @staticmethod
    def _gust_hold_fresh(state: dict[str, Any] | None, threshold: float, now_ts: float) -> bool:
        return (
            state is not None
            and state["threshold"] == threshold
            and state["last_ts"] <= now_ts
            and (now_ts - state["last_ts"]) <= _LIVE_HOLD_STALE_GAP_S
        )

    @staticmethod
    def _step_gust_hold(state: dict[str, Any], exceeds: bool, now_ts: float) -> None:
        """Advance one onset/clear hold by one station reading."""
        if not state["active"]:
            if exceeds:
                if state["exceeded_since"] is None:
                    state["exceeded_since"] = now_ts
                elif (now_ts - state["exceeded_since"]) >= _LIVE_GUST_ON_HOLD_S:
                    state["active"] = True
                    state["clear_since"] = None
            else:
                state["exceeded_since"] = None
        elif exceeds:
            state["clear_since"] = None
        else:
            if state["clear_since"] is None:
                state["clear_since"] = now_ts
            elif (now_ts - state["clear_since"]) >= _LIVE_GUST_OFF_HOLD_S:
                state["active"] = False
                state["exceeded_since"] = None
                state["clear_since"] = None
        state["last_ts"] = now_ts

    def _record_gust_sample(self, live_gust_ms: float | None, now_ts: float) -> None:
        """Keep recent station gusts so an action can test any gust limit against them."""
        samples = self._gust_samples
        if samples and now_ts < samples[-1][0]:
            samples.clear()  # the clock went back: the history no longer lines up
        if samples and samples[-1][0] == now_ts:
            samples[-1] = (now_ts, live_gust_ms)  # several profiles evaluate the same reading
        else:
            samples.append((now_ts, live_gust_ms))
        cutoff = now_ts - _GUST_SAMPLE_WINDOW_S
        while samples and samples[0][0] < cutoff:
            samples.popleft()

    def _replay_gust_hold(self, threshold: float, live_gust_ms: float | None, now_ts: float) -> bool:
        """Hold state for ``threshold`` rebuilt from the recent station gusts plus this reading."""
        readings = [(ts, g) for ts, g in self._gust_samples if ts < now_ts]
        readings.append((now_ts, live_gust_ms))
        state: dict[str, Any] | None = None
        for ts, gust in readings:
            if gust is None:
                if self._gust_hold_fresh(state, threshold, ts):
                    state["exceeded_since"] = state["clear_since"] = None
                else:
                    state = None
                continue
            exceeds = (gust * 3.6) > threshold
            if state is None or (ts - state["last_ts"]) > _LIVE_HOLD_STALE_GAP_S:
                state = self._new_gust_hold(threshold, exceeds, ts)
            else:
                self._step_gust_hold(state, exceeds, ts)
        return bool(state and state["active"])

    def _resolve_live_gust_active(
        self,
        profile: WeatherWindowProfile,
        live_gust_ms: float | None,
        now_ts: float,
        *,
        update: bool = True,
    ) -> bool:
        """Apply onset/clear hold hysteresis to instantaneous station gusts.

        With ``update=False`` (actions) nothing tracked is created, reset or advanced. The
        sensor's hold is used when it was tracked for the same limit; for any other limit the
        hold is rebuilt from the last few minutes of station gusts, so a limit supplied by the
        caller is judged on the same sustained evidence.
        """
        threshold = profile.max_wind_gust_kmh
        if update:
            self._record_gust_sample(live_gust_ms, now_ts)
        if threshold is None:
            if update:
                self._gust_hold_state.pop(profile.profile_id, None)
            return False
        state = self._gust_hold_state.get(profile.profile_id)
        fresh = self._gust_hold_fresh(state, threshold, now_ts)
        if not update:
            return bool(state["active"]) if fresh else self._replay_gust_hold(threshold, live_gust_ms, now_ts)
        if live_gust_ms is None:
            if fresh:
                # An outage counts toward neither a sustained gust nor a calm hold.
                state["exceeded_since"] = state["clear_since"] = None
                return bool(state["active"])
            self._gust_hold_state.pop(profile.profile_id, None)
            return False

        exceeds = (live_gust_ms * 3.6) > threshold
        if not fresh:
            self._gust_hold_state[profile.profile_id] = self._new_gust_hold(threshold, exceeds, now_ts)
            return False
        self._step_gust_hold(state, exceeds, now_ts)
        return bool(state["active"])

    def _remembered_window(self, profile_id: str, now_ts: float, limits: tuple[Any, ...]) -> dict[str, Any] | None:
        """Use a recent window only for evaluations with the same limits."""
        prev = self._open_window_start.get(profile_id)
        if (
            prev is not None
            and prev.get("limits") == limits
            and 0.0 <= now_ts - prev["last_ts"] <= _LIVE_HOLD_STALE_GAP_S
        ):
            return prev
        return None

    @staticmethod
    def _limits_key(profile: WeatherWindowProfile) -> tuple[Any, ...]:
        """Every limit of a profile, for comparing what two evaluations were judged on."""
        return tuple(getattr(profile, f.name) for f in fields(profile) if f.name not in _NON_LIMIT_FIELDS)

    def _txt(self, key: str, **fmt: object) -> str:
        """Return localized explanation string using engine language."""
        return localize.window_text(self.language, key, **fmt)

    def _txt_at(self, key: str, field_name: str, iso: str, prepared: Mapping[str, Any], **fmt: object) -> str:
        """Localized text with ``field_name`` as local HH:MM, using the ``_tomorrow`` variant when due."""
        display_tz: tzinfo = prepared["display_tz"]
        try:
            local_dt = datetime.fromisoformat(iso).astimezone(display_tz)
        except (TypeError, ValueError):
            return self._txt(key, **{field_name: iso}, **fmt)
        today = prepared["now_utc"].astimezone(display_tz).date()
        variant = f"{key}_tomorrow" if local_dt.date() > today else key
        return self._txt(variant, **{field_name: local_dt.strftime("%H:%M")}, **fmt)

    def _profile_display_name(self, profile: WeatherWindowProfile) -> str:
        """Return the localized built-in profile name unless the user renamed it."""
        default = DEFAULT_PROFILES.get(profile.profile_id)
        if default is not None and profile.name == default.name:
            return self._txt(f"profile_{profile.profile_id}")
        return profile.name

    def _fmt_temp_limit(self, c: float | None) -> str:
        val = 0.0 if c is None else float(c)
        if self.temp_unit == "°F":
            return f"{val * 9.0 / 5.0 + 32.0:.1f}°F"
        return f"{val}°C"

    def _fmt_wind_limit(self, kmh: float | None) -> str:
        val = 0.0 if kmh is None else float(kmh)
        factor = _WIND_KMH_FACTORS.get(self.wind_unit)
        if factor is not None and self.wind_unit != "km/h":
            return f"{val * factor:.1f} {self.wind_unit}"
        return f"{val} km/h"

    def _fmt_rain_limit(self, mm: float | None) -> str:
        val = 0.0 if mm is None else float(mm)
        if self.rain_unit == "in":
            return f"{val / 25.4:.2f} in"
        return f"{val} mm"

    def _evaluate_prepared_profile(
        self,
        profile: WeatherWindowProfile,
        prepared: dict[str, Any],
        *,
        as_dict: bool = False,
        update_live_hold: bool = True,
    ) -> Any:
        """Evaluate a single profile against a pre-parsed evaluation context."""
        limits_dict = self._validate_profile(profile)
        evaluated_at_iso: str = prepared["evaluated_at_iso"]
        prepared_slots: list[tuple[Any, ...]] = prepared["slots"]
        available_slots = len(prepared_slots)

        now_ts: float = prepared["now_ts"]
        limits_key = self._limits_key(profile)
        remembered = self._remembered_window(profile.profile_id, now_ts, limits_key)
        live_rain_rate: float | None = prepared["live_rain_rate"]
        live_gust_ms: float | None = prepared["live_gust_ms"]
        gust_unavailable = profile.max_wind_gust_kmh is not None and live_gust_ms is None

        live_blockers: list[str] = []
        live_blocker_texts: list[str] = []
        if (
            live_rain_rate is not None
            and (profile.max_rain_mm is not None or profile.max_rain_prob_pct is not None)
            and live_rain_rate > max(0.05, float(profile.max_rain_mm or 0.0))
        ):
            live_blockers.append(REASON_CURRENTLY_RAINING)
            live_blocker_texts.append(self._txt("currently_raining"))
        if self._resolve_live_gust_active(profile, live_gust_ms, now_ts, update=update_live_hold):
            live_blockers.append(REASON_CURRENT_GUST_HIGH)
            live_blocker_texts.append(
                self._txt("current_gust_high", limit=self._fmt_wind_limit(profile.max_wind_gust_kmh))
            )

        steps = [prepared_slots[i + 1][1] - prepared_slots[i][1] for i in range(available_slots - 1)]
        unavailable_reason: tuple[str, str] | None = None
        early_quality: dict[str, Any] = {"available_slots": available_slots, "gust_unavailable": gust_unavailable}
        if not prepared["has_forecast_rows"]:
            unavailable_reason = REASON_FORECAST_UNAVAILABLE, self._txt("forecast_unavailable")
        elif not prepared_slots:
            unavailable_reason = REASON_INSUFFICIENT_HORIZON, self._txt("no_horizon_in_window")
        elif remembered is None and available_slots < min(2, profile.min_duration_h):
            unavailable_reason = REASON_INSUFFICIENT_HORIZON, self._txt("insufficient_data")
        elif any(step < 3599.0 for step in steps):
            early_quality["typical_step_h"] = round(min(steps) / 3600.0, 2)
            unavailable_reason = REASON_FORECAST_TOO_FINE, self._txt("forecast_too_fine")
        elif sum(st > _HOURLY_STEP_TOLERANCE_S for st in steps) * 2 > len(steps):
            typical_h = round(sorted(steps)[len(steps) // 2] / 3600.0, 1)
            early_quality["typical_step_h"] = typical_h
            unavailable_reason = REASON_FORECAST_TOO_COARSE, self._txt("forecast_too_coarse", hours=f"{typical_h:g}")

        if unavailable_reason is not None:
            code, message = unavailable_reason
            payload = WeatherDecisionResult(
                profile_id=profile.profile_id,
                status=STATUS_UNSUITABLE if live_blockers else STATUS_UNKNOWN,
                evaluated_at=evaluated_at_iso,
                horizon_hours=min(available_slots, MAX_HORIZON_HOURS),
                reason_codes=[*live_blockers, code],
                reasons_text=[*live_blocker_texts, message],
                evaluated_limits=limits_dict,
                data_quality=early_quality,
            )
            return payload.to_dict() if as_dict else payload

        display_tz: tzinfo = prepared["display_tz"]
        horizon_end_utc: datetime = prepared["horizon_end_utc"]
        horizon_end_ts: float = prepared["horizon_end_ts"]
        avail: dict[str, bool] = prepared["available_vars"]

        # Bind limits to local variables for provider checks and inner loop
        req_daylight = profile.require_daylight
        p_max_rp = profile.max_rain_prob_pct
        p_max_rm = profile.max_rain_mm
        p_min_t = profile.min_temp_c
        p_max_t = profile.max_temp_c
        p_min_h = profile.min_humidity_pct
        p_max_h = profile.max_humidity_pct
        p_min_w = profile.min_wind_kmh
        p_max_w = profile.max_wind_kmh
        p_max_g = profile.max_wind_gust_kmh
        p_max_c = profile.max_cloud_cover_pct

        # Determine which limits the provider never supplies across the horizon
        has_rain_prob = avail["precip_prob"]
        has_rain_mm = avail["precip_mm"]
        has_humidity = avail["humidity"]
        has_wind = avail["wind_kmh"]
        has_gust = avail["gust_kmh"]
        has_cloud = avail["cloud_cover"]

        substitutions: dict[str, str] = {}
        if p_max_rp is not None and not has_rain_prob and has_rain_mm:
            substitutions["max_rain_prob_pct"] = "max_rain_mm"
            p_max_rm = 0.0 if p_max_rm is None else p_max_rm
        if p_max_rm is not None and not has_rain_mm and has_rain_prob:
            substitutions["max_rain_mm"] = "max_rain_prob_pct"
            p_max_rp = 0.0 if p_max_rp is None else p_max_rp
        reason_profile = (
            replace(profile, max_rain_prob_pct=p_max_rp, max_rain_mm=p_max_rm) if substitutions else profile
        )
        eval_rain_prob = p_max_rp is not None and has_rain_prob
        eval_rain_mm = p_max_rm is not None and has_rain_mm
        eval_min_h = p_min_h is not None and has_humidity
        eval_max_h = p_max_h is not None and has_humidity
        eval_min_w = p_min_w is not None and has_wind
        eval_max_w = p_max_w is not None and has_wind
        eval_max_g = p_max_g is not None and has_gust
        eval_max_c = p_max_c is not None and has_cloud

        not_assessed_by_provider: list[str] = []
        if p_max_rp is not None and not has_rain_prob:
            not_assessed_by_provider.append("max_rain_prob_pct")
        if p_max_rm is not None and not has_rain_mm:
            not_assessed_by_provider.append("max_rain_mm")
        if not avail["temp_c"]:
            if p_min_t is not None:
                not_assessed_by_provider.append("min_temp_c")
            if p_max_t is not None:
                not_assessed_by_provider.append("max_temp_c")
        if not has_humidity:
            if p_min_h is not None:
                not_assessed_by_provider.append("min_humidity_pct")
            if p_max_h is not None:
                not_assessed_by_provider.append("max_humidity_pct")
        if not has_wind:
            if p_min_w is not None:
                not_assessed_by_provider.append("min_wind_kmh")
            if p_max_w is not None:
                not_assessed_by_provider.append("max_wind_kmh")
        if p_max_g is not None and not has_gust:
            not_assessed_by_provider.append("max_wind_gust_kmh")
        if p_max_c is not None and not has_cloud:
            not_assessed_by_provider.append("max_cloud_cover_pct")

        slot_dicts: list[dict[str, Any]] = []
        suit_flags: list[bool] = []
        forecast_suit_flags: list[bool] = []
        pot_flags: list[bool] = []
        unassessed_slots = 0
        current_slot_raw_end_ts: float | None = None
        current_slot_blocked = False
        current_slot_suitable = False
        has_forecast_limit_blocker = False

        for (
            _slot_utc,
            _slot_ts,
            display_iso,
            temp_c,
            rain_prob,
            rain_mm,
            humidity,
            wind_kmh,
            gust_kmh,
            cloud_cover,
            is_night,
            sol_elev_rounded,
            is_current,
        ) in prepared_slots:
            reasons_slot: list[str] = []
            unassessed: list[str] = []

            if req_daylight and is_night:
                reasons_slot.append(REASON_NIGHTTIME)

            # Only limits set on this profile require temperature or rain data.
            if temp_c is None:
                if p_min_t is not None:
                    unassessed.append("min_temp_c")
                if p_max_t is not None:
                    unassessed.append("max_temp_c")
            else:
                if p_min_t is not None and temp_c < p_min_t:
                    reasons_slot.append(REASON_TOO_COLD)
                if p_max_t is not None and temp_c > p_max_t:
                    reasons_slot.append(REASON_TOO_HOT)

            if rain_prob is None and rain_mm is None:
                if p_max_rp is not None:
                    unassessed.append("max_rain_prob_pct")
                if p_max_rm is not None:
                    unassessed.append("max_rain_mm")
            else:
                if eval_rain_prob:
                    if rain_prob is None:
                        unassessed.append("max_rain_prob_pct")
                    elif rain_prob > p_max_rp:
                        reasons_slot.append(REASON_RAIN_RISK)
                if eval_rain_mm:
                    if rain_mm is None:
                        unassessed.append("max_rain_mm")
                    elif rain_mm > p_max_rm:
                        reasons_slot.append(REASON_RAIN_AMOUNT)

            if eval_min_h:
                if humidity is None:
                    unassessed.append("min_humidity_pct")
                elif humidity < p_min_h:
                    reasons_slot.append(REASON_LOW_HUMIDITY)
            if eval_max_h:
                if humidity is None:
                    unassessed.append("max_humidity_pct")
                elif humidity > p_max_h:
                    reasons_slot.append(REASON_HIGH_HUMIDITY)
            if eval_min_w:
                if wind_kmh is None:
                    unassessed.append("min_wind_kmh")
                elif wind_kmh < p_min_w:
                    reasons_slot.append(REASON_CALM_AIR)
            if eval_max_w:
                if wind_kmh is None:
                    unassessed.append("max_wind_kmh")
                elif wind_kmh > p_max_w:
                    reasons_slot.append(REASON_HIGH_WIND)
            if eval_max_g:
                if gust_kmh is None:
                    unassessed.append("max_wind_gust_kmh")
                elif gust_kmh > p_max_g:
                    reasons_slot.append(REASON_HIGH_GUST)
            if eval_max_c:
                if cloud_cover is None:
                    unassessed.append("max_cloud_cover_pct")
                elif cloud_cover > p_max_c:
                    reasons_slot.append(REASON_HEAVY_CLOUDS)

            if reasons_slot:
                has_forecast_limit_blocker = True
                if is_current:
                    current_slot_blocked = True
            if unassessed:
                unassessed_slots += 1
                reasons_slot.append(REASON_MISSING_DATA)

            forecast_suitable = not reasons_slot
            if is_current:
                current_slot_raw_end_ts = _slot_ts + 3600.0
            if is_current and live_blockers:
                suitable = False
                for blocker in live_blockers:
                    if blocker not in reasons_slot:
                        reasons_slot.append(blocker)
            else:
                suitable = forecast_suitable
                if suitable:
                    reasons_slot.append(REASON_SUITABLE)

            suit_flags.append(suitable)
            if is_current:
                current_slot_suitable = suitable
            forecast_suit_flags.append(forecast_suitable)
            pot_flags.append(suitable or (len(reasons_slot) == 1 and reasons_slot[0] == REASON_MISSING_DATA))
            slot_dicts.append(
                {
                    "datetime_iso": display_iso,
                    "suitable": suitable,
                    "reasons": reasons_slot,
                    "unassessed_limits": unassessed,
                    "temp_c": temp_c,
                    "rain_prob": rain_prob,
                    "rain_mm": rain_mm,
                    "humidity": humidity,
                    "wind_kmh": wind_kmh,
                    "gust_kmh": gust_kmh,
                    "cloud_cover": cloud_cover,
                    "solar_elevation": sol_elev_rounded,
                }
            )

        # Extract contiguous windows using float timestamps
        min_dur_h = profile.min_duration_h
        min_span_s = min_dur_h * 3600.0 - 1e-3
        last_slot_ts: float = prepared_slots[-1][1]
        is_utc_display = display_tz is UTC

        window_bounds = _extract_contiguous_windows(
            suit_flags,
            prepared_slots,
            min_span_s,
            now_ts,
            horizon_end_ts,
            horizon_end_utc,
            last_slot_ts,
            display_tz,
            is_utc_display,
            remembered,
        )
        # A live blocker inside a forecast window that is open now interrupts that window. Report the
        # forecast window as it stands (start in the past, real end) instead of hiding it or
        # re-arming a later start, so the timestamp sensors stay put and nothing re-triggers.
        interrupted: tuple[float, float, dict[str, Any]] | None = None
        forecast_bounds: list[tuple[float, float, dict[str, Any]]] = []
        if live_blockers and current_slot_raw_end_ts is not None:
            forecast_bounds = _extract_contiguous_windows(
                forecast_suit_flags,
                prepared_slots,
                min_span_s,
                now_ts,
                horizon_end_ts,
                horizon_end_utc,
                last_slot_ts,
                display_tz,
                is_utc_display,
                remembered,
            )
            if forecast_bounds and forecast_bounds[0][0] <= now_ts < forecast_bounds[0][1]:
                interrupted = forecast_bounds[0]

        if unassessed_slots == 0:
            potential_bounds = window_bounds
        elif window_bounds and window_bounds[0][0] <= now_ts < window_bounds[0][1]:
            potential_bounds = []
        else:
            potential_bounds = _extract_contiguous_windows(
                pot_flags,
                prepared_slots,
                min_span_s,
                now_ts,
                horizon_end_ts,
                horizon_end_utc,
                last_slot_ts,
                display_tz,
                is_utc_display,
                remembered,
            )

        # Formulate decision status and next suitable window
        status = STATUS_UNSUITABLE
        next_start: str | None = None
        next_end: str | None = None
        duration_h: int | float | None = None
        remaining_h: int | float | None = None
        is_truncated = False
        reasons: list[str] = []
        reasons_text: list[str] = []

        open_window: tuple[float, float, dict[str, Any]] | None = None
        if interrupted is not None:
            iw = interrupted[2]
            open_window = interrupted
            status = STATUS_UNSUITABLE
            next_start = iw["start_iso"]
            next_end = iw["end_iso"]
            duration_h = iw["duration_h"]
            remaining_h = iw["remaining_h"]
            is_truncated = iw["is_truncated"]
            reasons.extend(live_blockers)
            reasons_text.extend(live_blocker_texts)
            reasons.append(REASON_WINDOW_INTERRUPTED)
            reasons_text.append(self._txt_at("window_interrupted", "end", iw["end_iso"], prepared))
        elif window_bounds:
            w0_start_ts, w0_end_ts, w0 = window_bounds[0]
            if w0_start_ts <= now_ts < w0_end_ts:
                open_window = window_bounds[0]
                status = STATUS_SUITABLE_NOW
                next_start = w0["start_iso"]
                next_end = w0["end_iso"]
                duration_h = w0["duration_h"]
                remaining_h = w0["remaining_h"]
                is_truncated = w0["is_truncated"]
                reasons.append(REASON_SUITABLE)
                reasons_text.append(
                    self._txt_at(
                        "suitable_now", "end", w0["end_iso"], prepared, name=self._profile_display_name(profile)
                    )
                )
            elif potential_bounds and not live_blockers and potential_bounds[0][0] <= now_ts < potential_bounds[0][1]:
                status = STATUS_UNKNOWN
                next_start = w0["start_iso"]
                next_end = w0["end_iso"]
                duration_h = w0["duration_h"]
                remaining_h = w0["remaining_h"]
                is_truncated = w0["is_truncated"]
                reasons.append(REASON_MISSING_DATA)
                reasons_text.append(self._format_blocker_text(REASON_MISSING_DATA, profile))
                reasons.append(REASON_WINDOW_UPCOMING)
                reasons_text.append(self._txt_at("window_upcoming", "start", w0["start_iso"], prepared, dur=duration_h))
            else:
                status = STATUS_WINDOW_UPCOMING
                next_start = w0["start_iso"]
                next_end = w0["end_iso"]
                duration_h = w0["duration_h"]
                remaining_h = w0["remaining_h"]
                is_truncated = w0["is_truncated"]
                if live_blockers:
                    reasons.extend(live_blockers)
                    reasons_text.extend(live_blocker_texts)
                reasons.append(REASON_WINDOW_UPCOMING)
                reasons_text.append(self._txt_at("window_upcoming", "start", w0["start_iso"], prepared, dur=duration_h))
        elif potential_bounds:
            status = STATUS_UNKNOWN
            reasons.append(REASON_MISSING_DATA)
            reasons_text.append(self._format_blocker_text(REASON_MISSING_DATA, profile))
        else:
            blocker_counts: dict[str, int] = {}
            for s in slot_dicts:
                for r in s["reasons"]:
                    if r in (REASON_SUITABLE, REASON_MISSING_DATA) or r in live_blockers:
                        continue
                    blocker_counts[r] = blocker_counts.get(r, 0) + 1

            has_slot_gap = any(
                abs((prepared_slots[i + 1][1] - prepared_slots[i][1]) - 3600.0) > 1.0
                for i in range(available_slots - 1)
            )
            contiguous_span_s = min(last_slot_ts + 3600.0, horizon_end_ts) - prepared_slots[0][1]
            has_limit_blocker = has_forecast_limit_blocker or bool(live_blockers)
            short_horizon_only = (
                not has_limit_blocker
                and unassessed_slots == 0
                and (available_slots < min_dur_h or (not has_slot_gap and contiguous_span_s < min_span_s))
            )

            if short_horizon_only:
                status = STATUS_UNKNOWN
                reasons.append(REASON_INSUFFICIENT_HORIZON)
                reasons_text.append(self._format_blocker_text(REASON_INSUFFICIENT_HORIZON, profile))
            elif (not live_blockers and has_slot_gap) or (not has_limit_blocker and unassessed_slots > 0):
                status = STATUS_UNKNOWN
                reasons.append(REASON_MISSING_DATA)
                reasons_text.append(self._format_blocker_text(REASON_MISSING_DATA, profile))
            else:
                status = STATUS_UNSUITABLE
                if live_blockers:
                    reasons.extend(live_blockers)
                    reasons_text.extend(live_blocker_texts)

                top_blockers = (
                    [REASON_SHORT_WINDOW]
                    if current_slot_suitable
                    else sorted(blocker_counts.keys(), key=lambda k: -blocker_counts[k])[:3]
                )
                for b in top_blockers:
                    if b not in reasons:
                        reasons.append(b)
                        reasons_text.append(self._format_blocker_text(b, reason_profile))

                if not reasons and unassessed_slots > 0:
                    reasons.append(REASON_MISSING_DATA)
                    reasons_text.append(self._format_blocker_text(REASON_MISSING_DATA, profile))

                if not reasons:
                    reasons.append(REASON_INSUFFICIENT_HORIZON)
                    reasons_text.append(self._format_blocker_text(REASON_INSUFFICIENT_HORIZON, profile))

        if is_truncated:
            reasons.append(REASON_HORIZON_TRUNCATED)
            reasons_text.append(self._txt("horizon_truncated"))

        if not_assessed_by_provider:
            reasons.append(REASON_NOT_ASSESSED_BY_PROVIDER)
            field_list = localize.window_field_labels(self.language, not_assessed_by_provider)
            reasons_text.append(self._txt("not_assessed_by_provider", fields=field_list))

        windows = [w for _, _, w in (forecast_bounds if interrupted is not None else window_bounds)]
        if status == STATUS_UNKNOWN and live_blockers:
            reasons[:0] = live_blockers
            reasons_text[:0] = live_blocker_texts
        if update_live_hold:
            if open_window is not None:
                start_ts, end_ts, window = open_window
                self._open_window_start[profile.profile_id] = {
                    "start_ts": start_ts,
                    "start_iso": window["start_iso"],
                    "end_ts": end_ts,
                    "last_ts": now_ts,
                    "limits": limits_key,
                }
            elif current_slot_blocked or remembered is None or now_ts >= remembered["end_ts"]:
                self._open_window_start.pop(profile.profile_id, None)
        horizon_hours = min(len(slot_dicts), MAX_HORIZON_HOURS)
        result_dict = {
            "profile_id": profile.profile_id,
            "status": status,
            "evaluated_at": evaluated_at_iso,
            "next_start": next_start,
            "next_end": next_end,
            "duration_h": duration_h,
            "remaining_h": remaining_h,
            "horizon_hours": horizon_hours,
            "is_truncated": is_truncated,
            "reason_codes": reasons,
            "reasons_text": reasons_text,
            "not_assessed_by_provider": not_assessed_by_provider,
            "evaluated_limits": limits_dict,
            "windows": windows,
            "slots": slot_dicts,
            "data_quality": {
                "horizon_hours": horizon_hours,
                "is_truncated": is_truncated,
                "unassessed_slots": unassessed_slots,
                "substituted_by": substitutions,
                "gust_unavailable": gust_unavailable,
                "not_assessed_by_provider": list(not_assessed_by_provider),
                # The source had no row for the hour in progress; the next hour's row stands in.
                "current_hour_estimated": bool(prepared.get("current_hour_estimated")),
            },
        }
        return result_dict if as_dict else WeatherDecisionResult(**result_dict)

    def _format_blocker_text(self, reason: str, profile: WeatherWindowProfile) -> str:
        """Provide clear localized, unit-aware explanation for a blocker reason code."""
        if reason == REASON_SHORT_WINDOW:
            return self._txt("short_window", hours=profile.min_duration_h)
        if reason == REASON_NIGHTTIME:
            return self._txt("nighttime")
        if reason == REASON_RAIN_RISK:
            return self._txt("rain_risk", limit=profile.max_rain_prob_pct)
        if reason == REASON_RAIN_AMOUNT:
            return self._txt("rain_amount", limit=self._fmt_rain_limit(profile.max_rain_mm))
        if reason == REASON_TOO_COLD:
            return self._txt("too_cold", limit=self._fmt_temp_limit(profile.min_temp_c))
        if reason == REASON_TOO_HOT:
            return self._txt("too_hot", limit=self._fmt_temp_limit(profile.max_temp_c))
        if reason == REASON_HIGH_HUMIDITY:
            return self._txt("high_humidity", limit=profile.max_humidity_pct)
        if reason == REASON_LOW_HUMIDITY:
            return self._txt("low_humidity", limit=profile.min_humidity_pct)
        if reason == REASON_CALM_AIR:
            return self._txt("calm_air", limit=self._fmt_wind_limit(profile.min_wind_kmh))
        if reason == REASON_HIGH_WIND:
            return self._txt("high_wind", limit=self._fmt_wind_limit(profile.max_wind_kmh))
        if reason == REASON_HIGH_GUST:
            return self._txt("high_gust", limit=self._fmt_wind_limit(profile.max_wind_gust_kmh))
        if reason == REASON_HEAVY_CLOUDS:
            return self._txt("heavy_clouds", limit=profile.max_cloud_cover_pct)
        if reason == REASON_MISSING_DATA:
            return self._txt("missing_data")
        if reason == REASON_INSUFFICIENT_HORIZON:
            return self._txt("insufficient_horizon", dur=profile.min_duration_h)
        return reason
