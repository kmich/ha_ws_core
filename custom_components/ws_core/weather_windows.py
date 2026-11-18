"""Weather Windows Decision Engine for Home Assistant (v3.0.0).

Finds suitable intervals in the next 24-48 hours based on profile constraints,
NWP hourly forecasts, and live local station observations.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, field, replace
from datetime import UTC, datetime, timedelta, tzinfo
from typing import Any

from homeassistant.util import dt as dt_util

from .algorithms import solar_elevation_deg
from .const import (
    CONF_WEATHER_WINDOW_PROFILES,
    DEFAULT_WEATHER_WINDOW_PROFILES,
    KEY_NORM_WIND_GUST_MS,
    KEY_RAIN_RATE_FILT,
    PROFILE_CUSTOM,
    PROFILE_GARDEN_WORK,
    PROFILE_OUTDOOR_DRYING,
)

_LOGGER = logging.getLogger(__name__)

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
    """Resolve enabled weather window profiles from config/options."""
    if (
        config is not None
        and CONF_WEATHER_WINDOW_PROFILES in config
        and config[CONF_WEATHER_WINDOW_PROFILES] is not None
    ):
        raw = config[CONF_WEATHER_WINDOW_PROFILES]
    else:
        raw = DEFAULT_WEATHER_WINDOW_PROFILES
    selected = {raw} if isinstance(raw, str) else set(raw)
    return {pid: replace(prof, enabled=(pid in selected)) for pid, prof in DEFAULT_PROFILES.items()}


def _as_finite_float(val: Any) -> float | None:
    """Convert non-bool numeric inputs to finite float, else None."""
    if val is None or isinstance(val, bool):
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


@dataclass
class IdentifiedWindow:
    """A contiguous interval of suitable hours."""

    start_iso: str
    end_iso: str
    duration_h: int
    is_truncated: bool = False


@dataclass
class WeatherDecisionResult:
    """Standardized decision engine result contract (v3.0.0)."""

    profile_id: str
    status: str
    evaluated_at: str
    next_start: str | None = None
    next_end: str | None = None
    duration_h: int | None = None
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
        return asdict(self)


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

    def evaluate_profile(
        self,
        profile: WeatherWindowProfile,
        hourly_forecast: list[dict[str, Any]] | None,
        current_data: dict[str, Any] | None = None,
        now: datetime | None = None,
    ) -> WeatherDecisionResult:
        """Evaluate a profile against forecast and live station conditions."""
        if profile.min_duration_h < 1:
            raise ValueError("min_duration_h must be >= 1")

        eval_now = now or dt_util.now()
        display_tz = eval_now.tzinfo or dt_util.get_default_time_zone()
        now_utc = (
            eval_now.replace(tzinfo=display_tz).astimezone(UTC) if eval_now.tzinfo is None else eval_now.astimezone(UTC)
        )
        evaluated_at_iso = now_utc.isoformat()
        current = current_data or {}

        limits_dict = {
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

        if not hourly_forecast or len(hourly_forecast) < min(2, profile.min_duration_h):
            return WeatherDecisionResult(
                profile_id=profile.profile_id,
                status=STATUS_UNKNOWN,
                evaluated_at=evaluated_at_iso,
                reason_codes=[REASON_INSUFFICIENT_HORIZON],
                reasons_text=["Insufficient hourly forecast data available to evaluate windows."],
                evaluated_limits=limits_dict,
                data_quality={"available_slots": len(hourly_forecast) if hourly_forecast else 0},
            )

        # 1. Parse timestamps in UTC, skip finished intervals, deduplicate, and sort ascending
        deduped: dict[datetime, dict[str, Any]] = {}
        for item in hourly_forecast:
            slot_utc = self._parse_slot_utc(item, display_tz)
            if slot_utc is None:
                continue
            # Keep current in-progress hour and future hours; discard intervals ended at/before now
            if (slot_utc + timedelta(hours=1) - now_utc).total_seconds() <= 0.0:
                continue
            deduped.setdefault(slot_utc, item)

        if not deduped:
            return WeatherDecisionResult(
                profile_id=profile.profile_id,
                status=STATUS_UNKNOWN,
                evaluated_at=evaluated_at_iso,
                reason_codes=[REASON_INSUFFICIENT_HORIZON],
                reasons_text=["All forecast hours are in the past."],
                evaluated_limits=limits_dict,
                data_quality={"available_slots": 0},
            )

        evaluated_pairs: list[tuple[datetime, WindowSlotEvaluation]] = []
        for slot_utc in sorted(deduped):
            item = deduped[slot_utc]
            display_iso = slot_utc.astimezone(display_tz).isoformat()
            slot_eval = self._evaluate_slot(item, slot_utc, display_iso, profile)
            evaluated_pairs.append((slot_utc, slot_eval))

        # 2. Check live observations at station now and apply them to the current interval
        live_rain_rate = _as_finite_float(current.get(KEY_RAIN_RATE_FILT))
        live_gust_ms = _as_finite_float(current.get(KEY_NORM_WIND_GUST_MS))
        live_blockers: list[str] = []
        live_blocker_texts: list[str] = []

        if live_rain_rate is not None and live_rain_rate > 0.05:
            live_blockers.append(REASON_CURRENTLY_RAINING)
            live_blocker_texts.append(f"Rain is currently falling at the station ({live_rain_rate:.1f} mm/h).")

        if live_gust_ms is not None and profile.max_wind_gust_kmh is not None:
            live_gust_kmh = live_gust_ms * 3.6
            if live_gust_kmh > profile.max_wind_gust_kmh:
                live_blockers.append(REASON_CURRENT_GUST_HIGH)
                live_blocker_texts.append(
                    f"Current wind gust ({live_gust_kmh:.0f} km/h) exceeds limit ({profile.max_wind_gust_kmh:.0f} km/h)."
                )

        if live_blockers:
            for slot_utc, slot_eval in evaluated_pairs:
                if slot_utc <= now_utc < slot_utc + timedelta(hours=1):
                    slot_eval.suitable = False
                    slot_eval.reasons = [r for r in slot_eval.reasons if r != REASON_SUITABLE]
                    for blocker in live_blockers:
                        if blocker not in slot_eval.reasons:
                            slot_eval.reasons.append(blocker)

        # 3. Extract confirmed contiguous windows & candidate unassessed windows
        window_bounds = self._extract_windows(
            evaluated_pairs,
            profile.min_duration_h,
            now_utc,
            display_tz,
            predicate=lambda s: s.suitable,
        )
        potential_bounds = self._extract_windows(
            evaluated_pairs,
            profile.min_duration_h,
            now_utc,
            display_tz,
            predicate=lambda s: s.suitable or s.reasons == [REASON_MISSING_DATA],
        )

        # 4. Formulate decision status and next suitable window
        status = STATUS_UNSUITABLE
        next_start: str | None = None
        next_end: str | None = None
        duration_h: int | None = None
        is_truncated = False
        reasons: list[str] = []
        reasons_text: list[str] = []

        if window_bounds:
            w0_start_utc, w0_end_utc, w0 = window_bounds[0]
            if w0_start_utc <= now_utc < w0_end_utc:
                status = STATUS_SUITABLE_NOW
                next_start = w0.start_iso
                next_end = w0.end_iso
                duration_h = w0.duration_h
                is_truncated = w0.is_truncated
                reasons.append(REASON_SUITABLE)
                reasons_text.append(
                    f"Conditions meet all limits for {profile.name} starting now for at least {duration_h} hours."
                )
            elif potential_bounds and not live_blockers and potential_bounds[0][0] <= now_utc < potential_bounds[0][1]:
                # Current slot is unassessed due solely to missing inputs; cannot claim upcoming vs now safely.
                status = STATUS_UNKNOWN
                reasons.append(REASON_MISSING_DATA)
                reasons_text.append(self._format_blocker_text(REASON_MISSING_DATA, profile))
            else:
                status = STATUS_WINDOW_UPCOMING
                next_start = w0.start_iso
                next_end = w0.end_iso
                duration_h = w0.duration_h
                is_truncated = w0.is_truncated
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
            for _, s in evaluated_pairs:
                for r in s.reasons:
                    if r == REASON_SUITABLE or r in live_blockers:
                        continue
                    blocker_counts[r] = blocker_counts.get(r, 0) + 1
            top_blockers = sorted(blocker_counts.keys(), key=lambda k: -blocker_counts[k])[:3]
            for b in top_blockers:
                if b not in reasons:
                    reasons.append(b)
                    reasons_text.append(self._format_blocker_text(b, profile))

            if not reasons:
                reasons.append(REASON_INSUFFICIENT_HORIZON)
                reasons_text.append(self._format_blocker_text(REASON_INSUFFICIENT_HORIZON, profile))

        if is_truncated:
            reasons.append(REASON_HORIZON_TRUNCATED)
            reasons_text.append("Window extends to the end of the available forecast horizon.")

        slot_evals = [s for _, s in evaluated_pairs]
        windows = [w for _, _, w in window_bounds]
        return WeatherDecisionResult(
            profile_id=profile.profile_id,
            status=status,
            evaluated_at=evaluated_at_iso,
            next_start=next_start,
            next_end=next_end,
            duration_h=duration_h,
            horizon_hours=len(slot_evals),
            is_truncated=is_truncated,
            reason_codes=reasons,
            reasons_text=reasons_text,
            evaluated_limits=limits_dict,
            windows=[asdict(w) for w in windows],
            slots=[asdict(s) for s in slot_evals],
            data_quality={
                "horizon_hours": len(slot_evals),
                "is_truncated": is_truncated,
                "unassessed_slots": sum(1 for s in slot_evals if s.unassessed_limits),
            },
        )

    @staticmethod
    def _parse_slot_utc(item: dict[str, Any], display_tz: tzinfo) -> datetime | None:
        """Parse an hourly forecast item timestamp into UTC, preserving DST distinct hours."""
        raw_dt = item.get("utc_datetime") or item.get("datetime")
        if not raw_dt:
            return None
        parsed = dt_util.parse_datetime(str(raw_dt))
        if parsed is None:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=display_tz)
        return parsed.astimezone(UTC)

    def _evaluate_slot(
        self,
        item: dict[str, Any],
        slot_utc: datetime,
        display_iso: str,
        profile: WeatherWindowProfile,
    ) -> WindowSlotEvaluation:
        """Evaluate a single hourly slot against every enabled profile limit."""
        temp_c = _as_finite_float(item.get("temp_c"))
        rain_prob = _as_finite_float(item.get("precip_prob"))
        rain_mm = _as_finite_float(item.get("precip_mm"))
        humidity = _as_finite_float(item.get("humidity"))
        wind_kmh = _as_finite_float(item.get("wind_kmh"))
        gust_kmh = _as_finite_float(item.get("gust_kmh"))
        cloud_cover = _as_finite_float(item.get("cloud_cover"))

        sol_elev = solar_elevation_deg(self.lat, self.lon, slot_utc)
        reasons: list[str] = []

        # 1. Daylight requirement
        if profile.require_daylight and sol_elev <= 0.0:
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
        windows: list[tuple[datetime, datetime, IdentifiedWindow]] = []
        current_streak: list[tuple[datetime, WindowSlotEvaluation]] = []

        def _flush(streak: list[tuple[datetime, WindowSlotEvaluation]]) -> None:
            if not streak:
                return
            start_utc = streak[0][0]
            end_utc = streak[-1][0] + timedelta(hours=1)
            duration_h = round((end_utc - start_utc).total_seconds() / 3600.0)
            if duration_h < min_duration_h:
                return
            if start_utc <= now_utc < end_utc:
                remaining_s = (end_utc - now_utc).total_seconds()
                if remaining_s < min_duration_h * 3600.0 - 1e-3:
                    return
            is_truncated = streak[-1][0] == last_slot_utc
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
