"""Weather Windows Decision Engine for Home Assistant (v3.0.0).

Finds suitable intervals in the next 24-48 hours based on profile constraints,
NWP hourly forecasts, and live local station observations.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta, tzinfo
from typing import Any

from homeassistant.util import dt as dt_util

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
)

_LOGGER = logging.getLogger(__name__)

MAX_HORIZON_HOURS = 24
_ONE_HOUR = timedelta(hours=1)

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

# Decision status outcomes
STATUS_SUITABLE_NOW = "suitable_now"
STATUS_WINDOW_UPCOMING = "window_upcoming"
STATUS_UNSUITABLE = "unsuitable"
STATUS_UNKNOWN = "unknown"

# Reason codes
REASON_SUITABLE = "suitable"
REASON_WINDOW_UPCOMING = "window_upcoming"
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
REASON_INSUFFICIENT_HORIZON = "insufficient_horizon"
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
    return out


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
        changes[field_name] = num
    if "require_daylight" in overrides and overrides["require_daylight"] is not None:
        changes["require_daylight"] = bool(overrides["require_daylight"])
    return replace(base, **changes)


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
class WindowSlotEvaluation:
    """Evaluation of a single hourly forecast slot."""

    datetime_iso: str
    suitable: bool
    reasons: list[str] = field(default_factory=list)
    unassessed_limits: list[str] = field(default_factory=list)
    temp_c: float | None = None
    rain_prob: int | None = None
    rain_mm: float | None = None
    humidity: float | None = None
    wind_kmh: float | None = None
    gust_kmh: float | None = None
    cloud_cover: float | None = None
    solar_elevation: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert slot evaluation to dictionary without recursive asdict copies."""
        return {
            "datetime_iso": self.datetime_iso,
            "suitable": self.suitable,
            "reasons": self.reasons,
            "unassessed_limits": self.unassessed_limits,
            "temp_c": self.temp_c,
            "rain_prob": self.rain_prob,
            "rain_mm": self.rain_mm,
            "humidity": self.humidity,
            "wind_kmh": self.wind_kmh,
            "gust_kmh": self.gust_kmh,
            "cloud_cover": self.cloud_cover,
            "solar_elevation": self.solar_elevation,
        }


@dataclass
class IdentifiedWindow:
    """A contiguous interval of suitable hours."""

    start_iso: str
    end_iso: str
    duration_h: int | float
    is_truncated: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert identified window to dictionary without recursive asdict copies."""
        return {
            "start_iso": self.start_iso,
            "end_iso": self.end_iso,
            "duration_h": self.duration_h,
            "is_truncated": self.is_truncated,
        }


@dataclass
class WeatherDecisionResult:
    """Standardized decision engine result contract (v3.0.0)."""

    profile_id: str
    status: str
    evaluated_at: str
    next_start: str | None = None
    next_end: str | None = None
    duration_h: int | float | None = None
    horizon_hours: int = 0
    is_truncated: bool = False
    reason_codes: list[str] = field(default_factory=list)
    reasons_text: list[str] = field(default_factory=list)
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
            "horizon_hours": self.horizon_hours,
            "is_truncated": self.is_truncated,
            "reason_codes": self.reason_codes,
            "reasons_text": self.reasons_text,
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
        if raw_dt.tzinfo is None:
            raw_dt = raw_dt.replace(tzinfo=display_tz)
        return raw_dt.astimezone(UTC)
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
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=display_tz)
    return parsed.astimezone(UTC)


def _collect_horizon_slots(
    hourly_forecast: list[dict[str, Any]],
    now_ts: float,
    display_tz: tzinfo,
    slot_time_cache: dict[tuple[str, tzinfo], tuple[datetime, float, str] | None] | None = None,
    dt_cache: dict[str, datetime | None] | None = None,
) -> dict[float, tuple[datetime, str, Mapping[str, Any]]]:
    """Parse, deduplicate, and filter hourly slots to [now - 1h, now + 24h)."""
    deduped: dict[float, tuple[datetime, str, Mapping[str, Any]]] = {}
    max_h_s = MAX_HORIZON_HOURS * 3600.0
    is_utc_display = display_tz is UTC
    for item in hourly_forecast:
        if not isinstance(item, Mapping):
            continue
        raw_dt = item.get("utc_datetime")
        if raw_dt is None or raw_dt == "":
            raw_dt = item.get("datetime")
        if raw_dt is None or raw_dt == "":
            continue
        if type(raw_dt) is str and slot_time_cache is not None:
            cache_key = (raw_dt, display_tz)
            cached_t = slot_time_cache.get(cache_key, _MISSING)
            if cached_t is _MISSING:
                parsed = _parse_raw_dt_str(raw_dt, dt_cache)
                if parsed is None:
                    if len(slot_time_cache) > 512:
                        slot_time_cache.clear()
                    slot_time_cache[cache_key] = None
                    continue
                slot_utc = (
                    parsed.replace(tzinfo=display_tz).astimezone(UTC)
                    if parsed.tzinfo is None
                    else parsed.astimezone(UTC)
                )
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
        if slot_ts - now_ts >= max_h_s:
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
    display_tz, _now_utc, now_ts = _resolve_eval_clock(now)
    deduped = _collect_horizon_slots(hourly_forecast, now_ts, display_tz, dt_cache={})
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
        span_s = e_ts - (s_ts if s_ts >= now_ts else now_ts)
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
                        "start_iso": s_slot[2],
                        "end_iso": end_iso,
                        "duration_h": dur_h,
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
    ) -> None:
        self.lat = lat
        self.lon = lon
        self.elevation_m = elevation_m
        self.profiles: dict[str, WeatherWindowProfile] = dict(profiles if profiles is not None else DEFAULT_PROFILES)
        self._solar_coord: tuple[float, float] | None = None
        self._solar_cache: dict[datetime, float] = {}
        self._parse_dt_cache: dict[str, datetime | None] = {}
        self._slot_time_cache: dict[tuple[str, tzinfo], tuple[datetime, float, str] | None] = {}

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
        horizon_end_utc = now_utc + timedelta(hours=MAX_HORIZON_HOURS)
        horizon_end_ts = horizon_end_utc.timestamp()

        current = current_data or {}
        live_rain_rate = _as_finite_float(current.get(KEY_RAIN_RATE_FILT))
        live_gust_ms = _as_finite_float(current.get(KEY_NORM_WIND_GUST_MS))

        hourly_count = len(hourly_forecast) if hourly_forecast else 0
        prepared_slots: list[tuple[Any, ...]] = []
        if hourly_forecast:
            deduped = _collect_horizon_slots(
                hourly_forecast,
                now_ts,
                display_tz,
                slot_time_cache=self._slot_time_cache,
                dt_cache=self._parse_dt_cache,
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
                    rain_prob_int = int(rain_prob) if rain_prob is not None else None
                    is_current = slot_ts <= now_ts < raw_end_ts

                    prepared_slots.append(
                        (
                            slot_utc,
                            slot_ts,
                            display_iso,
                            temp_c,
                            rain_prob_int,
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
            "hourly_count": hourly_count,
            "slots": prepared_slots,
        }

    def evaluate_profiles(
        self,
        profiles: Iterable[WeatherWindowProfile],
        hourly_forecast: list[dict[str, Any]] | None,
        current_data: dict[str, Any] | None = None,
        now: datetime | None = None,
    ) -> dict[str, dict[str, Any]]:
        """Evaluate multiple profiles in one pass over parsed forecast slots (returns dict contracts)."""
        prof_list = list(profiles)
        if not prof_list:
            return {}
        prepared = self._prepare_evaluation(hourly_forecast, current_data, now)
        return {prof.profile_id: self._evaluate_prepared_profile(prof, prepared, as_dict=True) for prof in prof_list}

    def evaluate_profile(
        self,
        profile: WeatherWindowProfile,
        hourly_forecast: list[dict[str, Any]] | None,
        current_data: dict[str, Any] | None = None,
        now: datetime | None = None,
    ) -> WeatherDecisionResult:
        """Evaluate a profile against forecast and live station conditions."""
        prepared = self._prepare_evaluation(hourly_forecast, current_data, now)
        return self._evaluate_prepared_profile(profile, prepared, as_dict=False)

    def _evaluate_prepared_profile(
        self,
        profile: WeatherWindowProfile,
        prepared: dict[str, Any],
        *,
        as_dict: bool = False,
    ) -> Any:
        """Evaluate a single profile against a pre-parsed evaluation context."""
        limits_dict = self._validate_profile(profile)
        evaluated_at_iso: str = prepared["evaluated_at_iso"]
        hourly_count: int = prepared["hourly_count"]
        prepared_slots: list[tuple[Any, ...]] = prepared["slots"]

        if hourly_count < min(2, profile.min_duration_h):
            payload = {
                "profile_id": profile.profile_id,
                "status": STATUS_UNKNOWN,
                "evaluated_at": evaluated_at_iso,
                "next_start": None,
                "next_end": None,
                "duration_h": None,
                "horizon_hours": 0,
                "is_truncated": False,
                "reason_codes": [REASON_INSUFFICIENT_HORIZON],
                "reasons_text": ["Insufficient hourly forecast data available to evaluate windows."],
                "evaluated_limits": limits_dict,
                "windows": [],
                "slots": [],
                "data_quality": {"available_slots": hourly_count},
            }
            return payload if as_dict else WeatherDecisionResult(**payload)

        if not prepared_slots:
            payload = {
                "profile_id": profile.profile_id,
                "status": STATUS_UNKNOWN,
                "evaluated_at": evaluated_at_iso,
                "next_start": None,
                "next_end": None,
                "duration_h": None,
                "horizon_hours": 0,
                "is_truncated": False,
                "reason_codes": [REASON_INSUFFICIENT_HORIZON],
                "reasons_text": ["No forecast hours within the 24-hour evaluation window."],
                "evaluated_limits": limits_dict,
                "windows": [],
                "slots": [],
                "data_quality": {"available_slots": 0},
            }
            return payload if as_dict else WeatherDecisionResult(**payload)

        now_ts: float = prepared["now_ts"]
        display_tz: tzinfo = prepared["display_tz"]
        horizon_end_utc: datetime = prepared["horizon_end_utc"]
        horizon_end_ts: float = prepared["horizon_end_ts"]
        live_rain_rate: float | None = prepared["live_rain_rate"]
        live_gust_ms: float | None = prepared["live_gust_ms"]

        # Precompute live blockers for this profile
        live_blockers: list[str] = []
        live_blocker_texts: list[str] = []
        if (
            live_rain_rate is not None
            and (profile.max_rain_mm is not None or profile.max_rain_prob_pct is not None)
            and live_rain_rate > max(0.05, float(profile.max_rain_mm or 0.0))
        ):
            live_blockers.append(REASON_CURRENTLY_RAINING)
            live_blocker_texts.append(f"Rain is currently falling at the station ({live_rain_rate:.1f} mm/h).")

        if live_gust_ms is not None and profile.max_wind_gust_kmh is not None:
            live_gust_kmh = live_gust_ms * 3.6
            if live_gust_kmh > profile.max_wind_gust_kmh:
                live_blockers.append(REASON_CURRENT_GUST_HIGH)
                live_blocker_texts.append(
                    f"Current wind gust ({live_gust_kmh:.0f} km/h) exceeds limit ({profile.max_wind_gust_kmh:.0f} km/h)."
                )

        # Bind limits to local variables for the inner loop
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

        slot_dicts: list[dict[str, Any]] = []
        suit_flags: list[bool] = []
        pot_flags: list[bool] = []
        unassessed_slots = 0

        for (
            _slot_utc,
            _slot_ts,
            display_iso,
            temp_c,
            rain_prob_int,
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

            if p_max_rp is not None:
                if rain_prob is None:
                    unassessed.append("max_rain_prob_pct")
                elif rain_prob > p_max_rp:
                    reasons_slot.append(REASON_RAIN_RISK)
            if p_max_rm is not None:
                if rain_mm is None:
                    unassessed.append("max_rain_mm")
                elif rain_mm > p_max_rm:
                    reasons_slot.append(REASON_RAIN_AMOUNT)
            if p_min_t is not None:
                if temp_c is None:
                    unassessed.append("min_temp_c")
                elif temp_c < p_min_t:
                    reasons_slot.append(REASON_TOO_COLD)
            if p_max_t is not None:
                if temp_c is None:
                    unassessed.append("max_temp_c")
                elif temp_c > p_max_t:
                    reasons_slot.append(REASON_TOO_HOT)
            if p_min_h is not None:
                if humidity is None:
                    unassessed.append("min_humidity_pct")
                elif humidity < p_min_h:
                    reasons_slot.append(REASON_LOW_HUMIDITY)
            if p_max_h is not None:
                if humidity is None:
                    unassessed.append("max_humidity_pct")
                elif humidity > p_max_h:
                    reasons_slot.append(REASON_HIGH_HUMIDITY)
            if p_min_w is not None:
                if wind_kmh is None:
                    unassessed.append("min_wind_kmh")
                elif wind_kmh < p_min_w:
                    reasons_slot.append(REASON_CALM_AIR)
            if p_max_w is not None:
                if wind_kmh is None:
                    unassessed.append("max_wind_kmh")
                elif wind_kmh > p_max_w:
                    reasons_slot.append(REASON_HIGH_WIND)
            if p_max_g is not None:
                if gust_kmh is None:
                    unassessed.append("max_wind_gust_kmh")
                elif gust_kmh > p_max_g:
                    reasons_slot.append(REASON_HIGH_GUST)
            if p_max_c is not None:
                if cloud_cover is None:
                    unassessed.append("max_cloud_cover_pct")
                elif cloud_cover > p_max_c:
                    reasons_slot.append(REASON_HEAVY_CLOUDS)

            if unassessed:
                unassessed_slots += 1
                reasons_slot.append(REASON_MISSING_DATA)

            if is_current and live_blockers:
                suitable = False
                for blocker in live_blockers:
                    if blocker not in reasons_slot:
                        reasons_slot.append(blocker)
            else:
                suitable = not reasons_slot
                if suitable:
                    reasons_slot.append(REASON_SUITABLE)

            suit_flags.append(suitable)
            pot_flags.append(suitable or (len(reasons_slot) == 1 and reasons_slot[0] == REASON_MISSING_DATA))
            slot_dicts.append(
                {
                    "datetime_iso": display_iso,
                    "suitable": suitable,
                    "reasons": reasons_slot,
                    "unassessed_limits": unassessed,
                    "temp_c": temp_c,
                    "rain_prob": rain_prob_int,
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
        )
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
            )

        # Formulate decision status and next suitable window
        status = STATUS_UNSUITABLE
        next_start: str | None = None
        next_end: str | None = None
        duration_h: int | float | None = None
        is_truncated = False
        reasons: list[str] = []
        reasons_text: list[str] = []

        if window_bounds:
            w0_start_ts, w0_end_ts, w0 = window_bounds[0]
            if w0_start_ts <= now_ts < w0_end_ts:
                status = STATUS_SUITABLE_NOW
                next_start = w0["start_iso"]
                next_end = w0["end_iso"]
                duration_h = w0["duration_h"]
                is_truncated = w0["is_truncated"]
                reasons.append(REASON_SUITABLE)
                reasons_text.append(
                    f"Conditions meet all limits for {profile.name} starting now for at least {duration_h} hours."
                )
            elif potential_bounds and not live_blockers and potential_bounds[0][0] <= now_ts < potential_bounds[0][1]:
                status = STATUS_UNKNOWN
                next_start = w0["start_iso"]
                next_end = w0["end_iso"]
                duration_h = w0["duration_h"]
                is_truncated = w0["is_truncated"]
                reasons.append(REASON_MISSING_DATA)
                reasons_text.append(self._format_blocker_text(REASON_MISSING_DATA, profile))
                reasons.append(REASON_WINDOW_UPCOMING)
                reasons_text.append(f"Next suitable window starts at {next_start} for {duration_h} hours.")
            else:
                status = STATUS_WINDOW_UPCOMING
                next_start = w0["start_iso"]
                next_end = w0["end_iso"]
                duration_h = w0["duration_h"]
                is_truncated = w0["is_truncated"]
                if live_blockers:
                    reasons.extend(live_blockers)
                    reasons_text.extend(live_blocker_texts)
                reasons.append(REASON_WINDOW_UPCOMING)
                reasons_text.append(f"Next suitable window starts at {next_start} for {duration_h} hours.")
        elif potential_bounds:
            status = STATUS_UNKNOWN
            reasons.append(REASON_MISSING_DATA)
            reasons_text.append(self._format_blocker_text(REASON_MISSING_DATA, profile))
        else:
            status = STATUS_UNSUITABLE
            if live_blockers:
                reasons.extend(live_blockers)
                reasons_text.extend(live_blocker_texts)

            blocker_counts: dict[str, int] = {}
            for s in slot_dicts:
                for r in s["reasons"]:
                    if r in (REASON_SUITABLE, REASON_MISSING_DATA) or r in live_blockers:
                        continue
                    blocker_counts[r] = blocker_counts.get(r, 0) + 1
            top_blockers = sorted(blocker_counts.keys(), key=lambda k: -blocker_counts[k])[:3]
            for b in top_blockers:
                if b not in reasons:
                    reasons.append(b)
                    reasons_text.append(self._format_blocker_text(b, profile))

            if not reasons and any(REASON_MISSING_DATA in s["reasons"] for s in slot_dicts):
                reasons.append(REASON_MISSING_DATA)
                reasons_text.append(self._format_blocker_text(REASON_MISSING_DATA, profile))

            if not reasons:
                reasons.append(REASON_INSUFFICIENT_HORIZON)
                reasons_text.append(self._format_blocker_text(REASON_INSUFFICIENT_HORIZON, profile))

        if is_truncated:
            reasons.append(REASON_HORIZON_TRUNCATED)
            reasons_text.append("Window extends to the end of the available forecast horizon.")

        windows = [w for _, _, w in window_bounds]
        horizon_hours = min(len(slot_dicts), MAX_HORIZON_HOURS)
        result_dict = {
            "profile_id": profile.profile_id,
            "status": status,
            "evaluated_at": evaluated_at_iso,
            "next_start": next_start,
            "next_end": next_end,
            "duration_h": duration_h,
            "horizon_hours": horizon_hours,
            "is_truncated": is_truncated,
            "reason_codes": reasons,
            "reasons_text": reasons_text,
            "evaluated_limits": limits_dict,
            "windows": windows,
            "slots": slot_dicts,
            "data_quality": {
                "horizon_hours": horizon_hours,
                "is_truncated": is_truncated,
                "unassessed_slots": unassessed_slots,
            },
        }
        return result_dict if as_dict else WeatherDecisionResult(**result_dict)

    def _parse_raw_dt_str(self, key: str) -> datetime | None:
        """Parse and cache an ISO or Home Assistant datetime string."""
        return _parse_raw_dt_str(key, self._parse_dt_cache)

    def _parse_slot_utc(self, item: dict[str, Any], display_tz: tzinfo) -> datetime | None:
        """Parse an hourly forecast item timestamp into UTC, preserving DST distinct hours."""
        return parse_forecast_slot_utc(item, display_tz, self._parse_dt_cache)

    def _cached_solar_elevation(self, dt_utc: datetime) -> float:
        """Cache solar elevation by rounded coordinates and UTC timestamp across profiles."""
        solar_cache = self._sync_solar_cache(float(self.lat), float(self.lon))
        val = solar_cache.get(dt_utc)
        if val is None:
            val = solar_elevation_deg(self.lat, self.lon, dt_utc)
            if len(solar_cache) > 512:
                solar_cache.clear()
            solar_cache[dt_utc] = val
        return val

    def _evaluate_slot(
        self,
        item: dict[str, Any],
        slot_utc: datetime,
        display_iso: str,
        profile: WeatherWindowProfile,
        *,
        now_utc: datetime | None = None,
        horizon_end_utc: datetime | None = None,
    ) -> WindowSlotEvaluation:
        """Evaluate a single hourly slot against every enabled profile limit."""
        temp_c = _as_finite_float(item.get("temp_c"))
        rain_prob = _as_finite_float(item.get("precip_prob"))
        rain_mm = _as_finite_float(item.get("precip_mm"))
        humidity = _as_finite_float(item.get("humidity"))
        wind_kmh = _as_finite_float(item.get("wind_kmh"))
        gust_kmh = _as_finite_float(item.get("gust_kmh"))
        cloud_cover = _as_finite_float(item.get("cloud_cover"))

        effective_start_utc = max(slot_utc, now_utc) if now_utc is not None else slot_utc
        raw_end_utc = slot_utc + timedelta(hours=1)
        effective_end_utc = min(raw_end_utc, horizon_end_utc) if horizon_end_utc is not None else raw_end_utc
        sol_elev_start = self._cached_solar_elevation(effective_start_utc)
        sol_elev_end = self._cached_solar_elevation(effective_end_utc)
        sol_elev = min(sol_elev_start, sol_elev_end)
        reasons: list[str] = []

        # 1. Daylight requirement across the full effective window interval [start, end]
        if profile.require_daylight and (sol_elev_start <= 0.0 or sol_elev_end <= 0.0):
            reasons.append(REASON_NIGHTTIME)

        # 2. Evaluate every enabled numeric limit uniformly; missing inputs mark slot unassessed.
        limit_checks: tuple[tuple[str, float | None, str, str], ...] = (
            ("max_rain_prob_pct", rain_prob, "gt", REASON_RAIN_RISK),
            ("max_rain_mm", rain_mm, "gt", REASON_RAIN_AMOUNT),
            ("min_temp_c", temp_c, "lt", REASON_TOO_COLD),
            ("max_temp_c", temp_c, "gt", REASON_TOO_HOT),
            ("min_humidity_pct", humidity, "lt", REASON_LOW_HUMIDITY),
            ("max_humidity_pct", humidity, "gt", REASON_HIGH_HUMIDITY),
            ("min_wind_kmh", wind_kmh, "lt", REASON_CALM_AIR),
            ("max_wind_kmh", wind_kmh, "gt", REASON_HIGH_WIND),
            ("max_wind_gust_kmh", gust_kmh, "gt", REASON_HIGH_GUST),
            ("max_cloud_cover_pct", cloud_cover, "gt", REASON_HEAVY_CLOUDS),
        )
        unassessed: list[str] = []
        for limit_name, val, op, blocker in limit_checks:
            threshold = getattr(profile, limit_name)
            if threshold is None:
                continue
            if val is None:
                unassessed.append(limit_name)
                continue
            if (op == "gt" and val > threshold) or (op == "lt" and val < threshold):
                reasons.append(blocker)

        if unassessed:
            reasons.append(REASON_MISSING_DATA)

        suitable = not reasons
        if suitable:
            reasons.append(REASON_SUITABLE)

        return WindowSlotEvaluation(
            datetime_iso=display_iso,
            suitable=suitable,
            reasons=reasons,
            unassessed_limits=unassessed,
            temp_c=temp_c,
            rain_prob=int(rain_prob) if rain_prob is not None else None,
            rain_mm=rain_mm,
            humidity=humidity,
            wind_kmh=wind_kmh,
            gust_kmh=gust_kmh,
            cloud_cover=cloud_cover,
            solar_elevation=round(sol_elev, 1),
        )

    @staticmethod
    def _extract_windows(
        evaluated_pairs: list[tuple[datetime, WindowSlotEvaluation]],
        min_duration_h: int,
        now_utc: datetime,
        display_tz: tzinfo,
        predicate: Callable[[WindowSlotEvaluation], bool],
    ) -> list[tuple[datetime, datetime, IdentifiedWindow]]:
        """Extract contiguous 1-hour windows meeting duration requirements, splitting on gaps."""
        if not evaluated_pairs:
            return []

        last_slot_utc = evaluated_pairs[-1][0]
        horizon_end_utc = now_utc + timedelta(hours=MAX_HORIZON_HOURS)
        windows: list[tuple[datetime, datetime, IdentifiedWindow]] = []
        current_streak: list[tuple[datetime, WindowSlotEvaluation]] = []

        def _flush(streak: list[tuple[datetime, WindowSlotEvaluation]]) -> None:
            if not streak:
                return
            start_utc = streak[0][0]
            raw_end_utc = streak[-1][0] + timedelta(hours=1)
            end_utc = min(raw_end_utc, horizon_end_utc)
            effective_start_utc = max(start_utc, now_utc)
            span_s = (end_utc - effective_start_utc).total_seconds()
            if span_s < min_duration_h * 3600.0 - 1e-3:
                return
            raw_h = round(span_s / 3600.0, 2)
            duration_h: int | float = int(raw_h) if raw_h.is_integer() else raw_h
            is_truncated = streak[-1][0] == last_slot_utc or raw_end_utc > horizon_end_utc
            windows.append(
                (
                    start_utc,
                    end_utc,
                    IdentifiedWindow(
                        start_iso=start_utc.astimezone(display_tz).isoformat(),
                        end_iso=end_utc.astimezone(display_tz).isoformat(),
                        duration_h=duration_h,
                        is_truncated=is_truncated,
                    ),
                )
            )

        for slot_utc, slot_eval in evaluated_pairs:
            if predicate(slot_eval):
                if current_streak and abs((slot_utc - current_streak[-1][0]).total_seconds() - 3600.0) > 1.0:
                    _flush(current_streak)
                    current_streak = []
                current_streak.append((slot_utc, slot_eval))
            else:
                _flush(current_streak)
                current_streak = []

        _flush(current_streak)
        return windows

    @staticmethod
    def _format_blocker_text(reason: str, profile: WeatherWindowProfile) -> str:
        """Provide clear human-readable explanation for a blocker reason code."""
        if reason == REASON_NIGHTTIME:
            return "Sun is below horizon (daylight required)."
        if reason == REASON_RAIN_RISK:
            return f"Forecast rain probability exceeds {profile.max_rain_prob_pct}%."
        if reason == REASON_RAIN_AMOUNT:
            return f"Forecast precipitation exceeds {profile.max_rain_mm} mm."
        if reason == REASON_TOO_COLD:
            return f"Temperature is below {profile.min_temp_c}°C."
        if reason == REASON_TOO_HOT:
            return f"Temperature exceeds {profile.max_temp_c}°C."
        if reason == REASON_HIGH_HUMIDITY:
            return f"Relative humidity exceeds {profile.max_humidity_pct}%."
        if reason == REASON_LOW_HUMIDITY:
            return f"Relative humidity is below {profile.min_humidity_pct}%."
        if reason == REASON_CALM_AIR:
            return f"Wind is calm (< {profile.min_wind_kmh} km/h)."
        if reason == REASON_HIGH_WIND:
            return f"Wind speed exceeds {profile.max_wind_kmh} km/h."
        if reason == REASON_HIGH_GUST:
            return f"Wind gusts exceed {profile.max_wind_gust_kmh} km/h."
        if reason == REASON_HEAVY_CLOUDS:
            return f"Cloud cover exceeds {profile.max_cloud_cover_pct}% (sunshine proxy)."
        if reason == REASON_MISSING_DATA:
            return "Required forecast variable is missing from provider."
        if reason == REASON_INSUFFICIENT_HORIZON:
            return f"No continuous suitable interval meets the {profile.min_duration_h}-hour minimum duration."
        return reason
