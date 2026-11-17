"""Weather Windows Decision Engine for Home Assistant (v3.0.0).

Finds suitable intervals in the next 24-48 hours based on profile constraints,
NWP hourly forecasts, and live local station observations.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from homeassistant.util import dt as dt_util

from .algorithms import solar_elevation_deg
from .const import (
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


@dataclass
class WindowSlotEvaluation:
    """Evaluation of a single hourly forecast slot."""

    datetime_iso: str
    suitable: bool
    reasons: list[str] = field(default_factory=list)
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
        self.profiles: dict[str, WeatherWindowProfile] = dict(profiles or DEFAULT_PROFILES)

    def evaluate_profile(
        self,
        profile: WeatherWindowProfile,
        hourly_forecast: list[dict[str, Any]] | None,
        current_data: dict[str, Any] | None = None,
        now: datetime | None = None,
    ) -> WeatherDecisionResult:
        """Evaluate a profile against forecast and live station conditions."""
        eval_now = now or dt_util.now()
        evaluated_at_iso = eval_now.astimezone(UTC).isoformat()
        current = current_data or {}

        limits_dict = {
            "min_duration_h": profile.min_duration_h,
            "max_rain_prob_pct": profile.max_rain_prob_pct,
            "max_rain_mm": profile.max_rain_mm,
            "min_temp_c": profile.min_temp_c,
            "max_temp_c": profile.max_temp_c,
            "max_humidity_pct": profile.max_humidity_pct,
            "min_wind_kmh": profile.min_wind_kmh,
            "max_wind_kmh": profile.max_wind_kmh,
            "max_wind_gust_kmh": profile.max_wind_gust_kmh,
            "max_cloud_cover_pct": profile.max_cloud_cover_pct,
            "require_daylight": profile.require_daylight,
        }

        if not hourly_forecast or len(hourly_forecast) < 2:
            return WeatherDecisionResult(
                profile_id=profile.profile_id,
                status=STATUS_UNKNOWN,
                evaluated_at=evaluated_at_iso,
                reason_codes=[REASON_INSUFFICIENT_HORIZON],
                reasons_text=["Insufficient hourly forecast data available to evaluate windows."],
                evaluated_limits=limits_dict,
                data_quality={"available_slots": len(hourly_forecast) if hourly_forecast else 0},
            )

        # 1. Filter and evaluate each hourly slot
        slot_evals: list[WindowSlotEvaluation] = []
        for item in hourly_forecast:
            dt_s = item.get("datetime")
            if not dt_s:
                continue
            slot_dt = dt_util.parse_datetime(str(dt_s))
            if slot_dt is None:
                continue
            slot_dt = slot_dt.replace(tzinfo=eval_now.tzinfo) if slot_dt.tzinfo is None else dt_util.as_local(slot_dt)

            # Skip slots strictly in the past
            if (slot_dt - eval_now).total_seconds() < -1800.0:
                continue

            slot_eval = self._evaluate_slot(item, slot_dt, profile)
            slot_evals.append(slot_eval)

        if not slot_evals:
            return WeatherDecisionResult(
                profile_id=profile.profile_id,
                status=STATUS_UNKNOWN,
                evaluated_at=evaluated_at_iso,
                reason_codes=[REASON_INSUFFICIENT_HORIZON],
                reasons_text=["All forecast hours are in the past."],
                evaluated_limits=limits_dict,
                data_quality={"available_slots": 0},
            )

        # 2. Extract contiguous suitable windows
        windows: list[IdentifiedWindow] = self._find_contiguous_windows(slot_evals, profile.min_duration_h)

        # 3. Check live observations at station now
        live_rain_rate = current.get(KEY_RAIN_RATE_FILT)
        live_gust_ms = current.get(KEY_NORM_WIND_GUST_MS)
        live_blockers: list[str] = []
        live_blocker_texts: list[str] = []

        if live_rain_rate is not None and float(live_rain_rate) > 0.05:
            live_blockers.append(REASON_CURRENTLY_RAINING)
            live_blocker_texts.append(f"Rain is currently falling at the station ({float(live_rain_rate):.1f} mm/h).")

        if live_gust_ms is not None and profile.max_wind_gust_kmh is not None:
            live_gust_kmh = float(live_gust_ms) * 3.6
            if live_gust_kmh > profile.max_wind_gust_kmh:
                live_blockers.append(REASON_CURRENT_GUST_HIGH)
                live_blocker_texts.append(
                    f"Current wind gust ({live_gust_kmh:.0f} km/h) exceeds limit ({profile.max_wind_gust_kmh:.0f} km/h)."
                )

        # 4. Formulate decision status and next suitable window
        first_slot = slot_evals[0]
        status = STATUS_UNSUITABLE
        next_start: str | None = None
        next_end: str | None = None
        duration_h: int | None = None
        is_truncated = False
        reasons: list[str] = []
        reasons_text: list[str] = []

        # Is slot 0 suitable now?
        if windows and windows[0].start_iso == first_slot.datetime_iso:
            if live_blockers:
                status = STATUS_UNSUITABLE
                reasons.extend(live_blockers)
                reasons_text.extend(live_blocker_texts)
                # Next future window (if any)
                if len(windows) > 1:
                    status = STATUS_WINDOW_UPCOMING
                    next_start = windows[1].start_iso
                    next_end = windows[1].end_iso
                    duration_h = windows[1].duration_h
                    is_truncated = windows[1].is_truncated
            else:
                status = STATUS_SUITABLE_NOW
                next_start = windows[0].start_iso
                next_end = windows[0].end_iso
                duration_h = windows[0].duration_h
                is_truncated = windows[0].is_truncated
                reasons.append(REASON_SUITABLE)
                reasons_text.append(
                    f"Conditions meet all limits for {profile.name} starting now for at least {duration_h} hours."
                )
        elif windows:
            status = STATUS_WINDOW_UPCOMING
            next_start = windows[0].start_iso
            next_end = windows[0].end_iso
            duration_h = windows[0].duration_h
            is_truncated = windows[0].is_truncated
            reasons.append(REASON_WINDOW_UPCOMING)
            reasons_text.append(f"Next suitable window starts at {next_start} for {duration_h} hours.")
        else:
            status = STATUS_UNSUITABLE
            # Collect most frequent blockers across the horizon
            blocker_counts: dict[str, int] = {}
            for s in slot_evals:
                for r in s.reasons:
                    blocker_counts[r] = blocker_counts.get(r, 0) + 1
            top_blockers = sorted(blocker_counts.keys(), key=lambda k: -blocker_counts[k])[:3]
            reasons.extend(top_blockers)
            for b in top_blockers:
                reasons_text.append(self._format_blocker_text(b, profile))

        if is_truncated:
            reasons.append(REASON_HORIZON_TRUNCATED)
            reasons_text.append("Window extends to the end of the available forecast horizon.")

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
            },
        )

    def _evaluate_slot(
        self,
        item: dict[str, Any],
        slot_dt: datetime,
        profile: WeatherWindowProfile,
    ) -> WindowSlotEvaluation:
        """Evaluate a single hourly slot against profile limits."""
        temp_c = item.get("temp_c")
        rain_prob = item.get("precip_prob")
        rain_mm = item.get("precip_mm")
        humidity = item.get("humidity")
        wind_kmh = item.get("wind_kmh")
        gust_kmh = item.get("gust_kmh")
        cloud_cover = item.get("cloud_cover")

        sol_elev = solar_elevation_deg(self.lat, self.lon, slot_dt)
        reasons: list[str] = []

        # 1. Daylight requirement
        if profile.require_daylight and sol_elev <= 0.0:
            reasons.append(REASON_NIGHTTIME)

        # 2. Precipitation check (probability & accumulation)
        # "Never treat a missing forecast variable as zero or safe"
        if profile.max_rain_prob_pct is not None:
            if rain_prob is None and rain_mm is None:
                reasons.append(REASON_MISSING_DATA)
            elif rain_prob is not None and float(rain_prob) > profile.max_rain_prob_pct:
                reasons.append(REASON_RAIN_RISK)

        if profile.max_rain_mm is not None and rain_mm is not None and float(rain_mm) > profile.max_rain_mm:
            reasons.append(REASON_RAIN_AMOUNT)

        # 3. Temperature bounds
        if profile.min_temp_c is not None:
            if temp_c is None:
                reasons.append(REASON_MISSING_DATA)
            elif float(temp_c) < profile.min_temp_c:
                reasons.append(REASON_TOO_COLD)

        if profile.max_temp_c is not None and temp_c is not None and float(temp_c) > profile.max_temp_c:
            reasons.append(REASON_TOO_HOT)

        # 4. Humidity bounds
        if profile.max_humidity_pct is not None and humidity is not None and float(humidity) > profile.max_humidity_pct:
            reasons.append(REASON_HIGH_HUMIDITY)

        if profile.min_humidity_pct is not None and humidity is not None and float(humidity) < profile.min_humidity_pct:
            reasons.append(REASON_LOW_HUMIDITY)

        # 5. Wind & Gust
        if profile.min_wind_kmh is not None and wind_kmh is not None and float(wind_kmh) < profile.min_wind_kmh:
            reasons.append(REASON_CALM_AIR)

        if profile.max_wind_kmh is not None and wind_kmh is not None and float(wind_kmh) > profile.max_wind_kmh:
            reasons.append(REASON_HIGH_WIND)

        if profile.max_wind_gust_kmh is not None and gust_kmh is not None and float(gust_kmh) > profile.max_wind_gust_kmh:
            reasons.append(REASON_HIGH_GUST)

        # 6. Cloud cover (proxy for sunshine)
        if profile.max_cloud_cover_pct is not None and cloud_cover is not None and float(cloud_cover) > profile.max_cloud_cover_pct:
            reasons.append(REASON_HEAVY_CLOUDS)

        suitable = len(reasons) == 0
        if suitable:
            reasons.append(REASON_SUITABLE)

        return WindowSlotEvaluation(
            datetime_iso=slot_dt.isoformat(),
            suitable=suitable,
            reasons=reasons,
            temp_c=float(temp_c) if temp_c is not None else None,
            rain_prob=int(rain_prob) if rain_prob is not None else None,
            rain_mm=float(rain_mm) if rain_mm is not None else None,
            humidity=float(humidity) if humidity is not None else None,
            wind_kmh=float(wind_kmh) if wind_kmh is not None else None,
            gust_kmh=float(gust_kmh) if gust_kmh is not None else None,
            cloud_cover=float(cloud_cover) if cloud_cover is not None else None,
            solar_elevation=round(sol_elev, 1),
        )

    @staticmethod
    def _find_contiguous_windows(
        slots: list[WindowSlotEvaluation], min_duration_h: int
    ) -> list[IdentifiedWindow]:
        """Find contiguous blocks of suitable hours meeting min_duration_h."""
        windows: list[IdentifiedWindow] = []
        current_streak: list[WindowSlotEvaluation] = []

        for s in slots:
            if s.suitable:
                current_streak.append(s)
            else:
                if len(current_streak) >= min_duration_h:
                    start_dt = dt_util.parse_datetime(current_streak[0].datetime_iso)
                    end_dt = dt_util.parse_datetime(current_streak[-1].datetime_iso)
                    if start_dt and end_dt:
                        end_window = end_dt + timedelta(hours=1)
                        windows.append(
                            IdentifiedWindow(
                                start_iso=start_dt.isoformat(),
                                end_iso=end_window.isoformat(),
                                duration_h=len(current_streak),
                                is_truncated=False,
                            )
                        )
                current_streak = []

        # Handle window extending to the end of available horizon
        if len(current_streak) >= min_duration_h:
            start_dt = dt_util.parse_datetime(current_streak[0].datetime_iso)
            end_dt = dt_util.parse_datetime(current_streak[-1].datetime_iso)
            if start_dt and end_dt:
                end_window = end_dt + timedelta(hours=1)
                windows.append(
                    IdentifiedWindow(
                        start_iso=start_dt.isoformat(),
                        end_iso=end_window.isoformat(),
                        duration_h=len(current_streak),
                        is_truncated=True,  # Horizon truncated
                    )
                )

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
        return reason
