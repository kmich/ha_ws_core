"""Coordinator for Weather Station Core — v0.3.1.

The _compute() method is broken into focused sub-methods:
  _compute_raw_readings()          Unit conversion of all source sensors
  _compute_derived_temperature()   Dew point, feels-like, 24h stats
  _compute_derived_pressure()      MSLP, pressure trend, Zambretti
  _compute_derived_wind()          Beaufort, quadrant, smoothing
  _compute_derived_precipitation() Rain rate, Kalman filter, rain display
  _compute_condition()             36-condition classifier
  _compute_rain_probability()      Local + API probability
  _compute_activity_scores()       Laundry, fire, running, stargazing
  _compute_health()                Staleness, package status, alerts
  _compute()                       Orchestrator — calls all sub-methods
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import timedelta
import math
import logging
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_interval
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .algorithms import (
    KalmanFilter,
    CONDITION_COLORS,
    CONDITION_DESCRIPTIONS,
    CONDITION_ICONS,
    MOON_ILLUMINATION,
    MOON_ICONS,
    beaufort_description,
    calculate_apparent_temperature,
    calculate_dew_point,
    calculate_moon_phase,
    calculate_rain_probability,
    calculate_sea_level_pressure,
    combine_rain_probability,
    determine_current_condition,
    direction_to_quadrant,
    fire_danger_level,
    fire_weather_index,
    format_rain_display,
    get_condition_severity,
    humidity_level,
    laundry_dry_time,
    laundry_drying_score,
    laundry_recommendation,
    least_squares_pressure_trend,
    moon_stargazing_impact,
    pressure_trend_arrow,
    pressure_trend_display,
    running_level,
    running_recommendation,
    running_score,
    smooth_wind_direction,
    stargazing_quality,
    uv_burn_time_minutes,
    uv_level,
    uv_recommendation,
    wind_speed_to_beaufort,
    zambretti_forecast,
)
from .const import (
    CONF_CLIMATE_REGION,
    CONF_ELEVATION_M,
    CONF_FORECAST_ENABLED,
    CONF_FORECAST_INTERVAL_MIN,
    CONF_FORECAST_LAT,
    CONF_FORECAST_LON,
    CONF_HEMISPHERE,
    CONF_SOURCES,
    CONF_STALENESS_S,
    CONF_UNITS_MODE,
    DEFAULT_CLIMATE_REGION,
    DEFAULT_FORECAST_INTERVAL_MIN,
    DEFAULT_HEMISPHERE,
    DEFAULT_STALENESS_S,
    KEY_ALERT_MESSAGE,
    KEY_ALERT_STATE,
    KEY_BATTERY_PCT,
    KEY_BATTERY_DISPLAY,
    KEY_CURRENT_CONDITION,
    KEY_DATA_QUALITY,
    KEY_DEW_POINT_C,
    KEY_FEELS_LIKE_C,
    KEY_FIRE_SCORE,
    KEY_FORECAST,
    KEY_FORECAST_TILES,
    KEY_HEALTH_DISPLAY,
    KEY_HUMIDITY_LEVEL_DISPLAY,
    KEY_LAUNDRY_SCORE,
    KEY_LUX,
    KEY_NORM_HUMIDITY,
    KEY_NORM_PRESSURE_HPA,
    KEY_NORM_RAIN_TOTAL_MM,
    KEY_NORM_TEMP_C,
    KEY_NORM_WIND_DIR_DEG,
    KEY_NORM_WIND_GUST_MS,
    KEY_NORM_WIND_SPEED_MS,
    KEY_PACKAGE_OK,
    KEY_PACKAGE_STATUS,
    KEY_PRESSURE_CHANGE_WINDOW_HPA,
    KEY_PRESSURE_TREND_DISPLAY,
    KEY_PRESSURE_TREND_HPAH,
    KEY_RAIN_DISPLAY,
    KEY_RAIN_PROBABILITY,
    KEY_RAIN_PROBABILITY_COMBINED,
    KEY_RAIN_RATE_FILT,
    KEY_RAIN_RATE_RAW,
    KEY_RUNNING_SCORE,
    KEY_SEA_LEVEL_PRESSURE_HPA,
    KEY_SENSOR_QUALITY_FLAGS,
    KEY_STARGAZE_SCORE,
    KEY_TEMP_AVG_24H,
    KEY_TEMP_DISPLAY,
    KEY_TEMP_HIGH_24H,
    KEY_TEMP_LOW_24H,
    KEY_UV,
    KEY_UV_LEVEL_DISPLAY,
    KEY_WIND_BEAUFORT,
    KEY_WIND_BEAUFORT_DESC,
    KEY_WIND_DIR_SMOOTH_DEG,
    KEY_WIND_GUST_MAX_24H,
    KEY_WIND_QUADRANT,
    KEY_ZAMBRETTI_FORECAST,
    MAGNUS_A,
    MAGNUS_B,
    PRESSURE_HISTORY_INTERVAL_MIN,
    PRESSURE_HISTORY_SAMPLES,
    PRESSURE_TREND_FALLING,
    PRESSURE_TREND_FALLING_RAPID,
    PRESSURE_TREND_RISING,
    PRESSURE_TREND_RISING_RAPID,
    RAIN_RATE_PHYSICAL_CAP_MMPH,
    REQUIRED_SOURCES,
    SLP_GAS_CONSTANT_RATIO,
    SRC_BATTERY,
    SRC_DEW_POINT,
    SRC_GUST,
    SRC_HUM,
    SRC_LUX,
    SRC_PRESS,
    SRC_RAIN_TOTAL,
    SRC_TEMP,
    SRC_UV,
    SRC_WIND,
    SRC_WIND_DIR,
    VALID_HUMIDITY_MAX,
    VALID_HUMIDITY_MIN,
    VALID_PRESSURE_MAX_HPA,
    VALID_PRESSURE_MIN_HPA,
    VALID_TEMP_MAX_C,
    VALID_TEMP_MIN_C,
    WIND_SMOOTH_ALPHA,
)

_LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Runtime state
# ---------------------------------------------------------------------------

@dataclass
class WSStationRuntime:
    """Mutable runtime state that persists across compute cycles."""

    # Rain tracking
    last_rain_total_mm: float | None = None
    last_rain_ts: Any | None = None
    last_rain_rate_filt: float = 0.0

    # Pressure tracking
    pressure_history: deque = field(
        default_factory=lambda: deque(maxlen=PRESSURE_HISTORY_SAMPLES)
    )
    pressure_history_ts: Any | None = None

    # Wind direction smoothing
    smoothed_wind_dir: float | None = None

    # Kalman filter for rain rate
    kalman: KalmanFilter = field(default_factory=KalmanFilter)

    # 24h rolling windows (timestamp-based; resilient to update interval changes)
    # Stored as deque[(datetime, value)] and pruned to the last 24 hours.
    temp_history_24h: deque = field(default_factory=deque)
    gust_history_24h: deque = field(default_factory=deque)
    rain_total_history_24h: deque = field(default_factory=deque)

    # Forecast cache
    last_forecast_fetch: Any | None = None
    forecast_inflight: bool = False

    # MSLP cached for Zambretti
    last_mslp: float | None = None


# ---------------------------------------------------------------------------
# Coordinator
# ---------------------------------------------------------------------------

class WSStationCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Keeps all derived values up to date."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry_data: dict[str, Any],
        entry_options: dict[str, Any] | None = None,
    ):
        self.hass = hass
        self.entry_data = entry_data
        self.entry_options = entry_options or {}
        self.runtime = WSStationRuntime()

        self.sources: dict[str, str] = dict(entry_data.get(CONF_SOURCES, {}))

        def _get(key: str, default: Any) -> Any:
            return self.entry_options.get(key, entry_data.get(key, default))

        self.units_mode = str(_get(CONF_UNITS_MODE, "auto"))
        self.elevation_m = float(_get(CONF_ELEVATION_M, 0.0))
        self.hemisphere = str(_get(CONF_HEMISPHERE, DEFAULT_HEMISPHERE))
        self.climate_region = str(_get(CONF_CLIMATE_REGION, DEFAULT_CLIMATE_REGION))
        self.staleness_s = int(_get(CONF_STALENESS_S, DEFAULT_STALENESS_S))
        self.forecast_enabled = bool(_get(CONF_FORECAST_ENABLED, True))
        self.forecast_lat = _get(CONF_FORECAST_LAT, None)
        self.forecast_lon = _get(CONF_FORECAST_LON, None)
        self.forecast_interval_min = int(_get(CONF_FORECAST_INTERVAL_MIN, DEFAULT_FORECAST_INTERVAL_MIN))

        super().__init__(
            hass,
            logger=_LOGGER,
            name="WS Station",
            update_interval=timedelta(seconds=60),
        )
        self._unsubs: list = []

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def async_start(self) -> None:
        entity_ids = [eid for eid in self.sources.values() if eid]
        if entity_ids:
            self._unsubs.append(
                async_track_state_change_event(self.hass, entity_ids, self._handle_source_change)
            )
        self._unsubs.append(
            async_track_time_interval(self.hass, self._handle_tick, timedelta(seconds=60))
        )
        await self.async_refresh()

    async def async_stop(self) -> None:
        for u in self._unsubs:
            try:
                u()
            except Exception:
                pass
        self._unsubs.clear()

    @callback
    def _handle_source_change(self, event) -> None:
        self.async_set_updated_data(self._compute())

    @callback
    def _handle_tick(self, _now) -> None:
        self.async_set_updated_data(self._compute())

    async def _async_update_data(self) -> dict[str, Any]:
        return self._compute()

    # ------------------------------------------------------------------
    # Unit conversion helpers
    # ------------------------------------------------------------------
    # Rolling window helpers (24h timestamp-based)
    # ------------------------------------------------------------------

    @staticmethod
    def _append_and_prune_24h(history: deque, now: Any, value: float) -> None:
        """Append (now,value) and prune entries older than 24 hours."""
        history.append((now, value))
        cutoff = now - timedelta(hours=24)
        while history and history[0][0] < cutoff:
            history.popleft()

    @staticmethod
    def _rolling_values(history: deque) -> list[float]:
        return [v for _, v in history]

    @staticmethod
    def _rain_accum_24h_from_totals(history: deque) -> float:
        """Compute 24h rain accumulation from a cumulative rain-total history."""
        vals = [v for _, v in history]
        total = 0.0
        for prev, cur in zip(vals, vals[1:]):
            dv = cur - prev
            if dv < -0.1:  # counter reset protection
                dv = 0.0
            if dv > 0:
                total += dv
        return total


    # ------------------------------------------------------------------

    @staticmethod
    def _uom(hass: HomeAssistant, eid: str | None) -> str:
        if not eid:
            return ""
        st = hass.states.get(eid)
        return str(st.attributes.get("unit_of_measurement") or "") if st else ""

    @staticmethod
    def _num(hass: HomeAssistant, eid: str | None) -> float | None:
        if not eid:
            return None
        st = hass.states.get(eid)
        if st is None:
            return None
        try:
            v = float(st.state)
        except (ValueError, TypeError):
            return None
        if math.isnan(v) or math.isinf(v):
            return None
        return v

    @staticmethod
    def _to_celsius(v: float, unit: str) -> float:
        u = unit.lower().replace(" ", "")
        if u in ("f", "°f") or ("f" in u and "°" in u):
            return (v - 32.0) * 5.0 / 9.0
        if u in ("k", "kelvin"):
            return v - 273.15
        return v

    @staticmethod
    def _to_ms(v: float, unit: str) -> float:
        u = unit.lower().replace(" ", "")
        if u in ("km/h", "kmh", "kph"):
            return v / 3.6
        if u == "mph":
            return v * 0.44704
        if u in ("kn", "knot", "knots"):
            return v * 0.514444
        return v

    @staticmethod
    def _to_hpa(v: float, unit: str) -> float:
        u = unit.lower().replace(" ", "")
        if u == "pa":
            return v / 100.0
        if u == "inhg":
            return v * 33.8638866667
        if u in ("mmhg", "torr"):
            return v * 1.33322
        return v

    @staticmethod
    def _to_mm(v: float, unit: str) -> float:
        u = unit.lower().replace(" ", "")
        if u in ("in", "inch", "inches"):
            return v * 25.4
        return v

    # ------------------------------------------------------------------
    # Sensor quality / physics validation
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_readings(
        tc: float | None,
        rh: float | None,
        pressure_hpa: float | None,
        wind_ms: float | None,
        gust_ms: float | None,
        dew_c: float | None,
    ) -> list[str]:
        """Return list of quality warning strings for suspect readings."""
        flags: list[str] = []
        if tc is not None and not (VALID_TEMP_MIN_C <= tc <= VALID_TEMP_MAX_C):
            flags.append(f"temperature {tc:.1f}°C outside physical range")
        if rh is not None and not (VALID_HUMIDITY_MIN <= rh <= VALID_HUMIDITY_MAX):
            flags.append(f"humidity {rh:.0f}% outside valid range")
        if pressure_hpa is not None and not (VALID_PRESSURE_MIN_HPA <= pressure_hpa <= VALID_PRESSURE_MAX_HPA):
            flags.append(f"pressure {pressure_hpa:.1f} hPa outside physical range")
        # Cross-checks
        if tc is not None and dew_c is not None and dew_c > tc + 0.5:
            flags.append("dew point exceeds temperature (check humidity sensor)")
        if wind_ms is not None and gust_ms is not None and gust_ms < wind_ms * 0.9:
            flags.append("wind gust below wind speed (check anemometer)")
        return flags

    # ------------------------------------------------------------------
    # Sub-methods
    # ------------------------------------------------------------------

    def _compute_raw_readings(
        self, data: dict, now: Any
    ) -> tuple[float | None, ...]:
        """Read and unit-convert all source sensors. Returns (tc, rh, pressure_hpa, wind_ms, gust_ms, wind_dir, rain_total_mm, lux, uv, bat)."""
        hass = self.hass

        def num(key: str) -> float | None:
            return self._num(hass, self.sources.get(key))

        def uom(key: str) -> str:
            return self._uom(hass, self.sources.get(key))

        t_raw = num(SRC_TEMP)
        tc = round(self._to_celsius(t_raw, uom(SRC_TEMP)), 2) if t_raw is not None else None
        if tc is not None:
            data[KEY_NORM_TEMP_C] = tc

        h_raw = num(SRC_HUM)
        rh = round(h_raw, 1) if h_raw is not None else None
        if rh is not None:
            data[KEY_NORM_HUMIDITY] = rh

        p_raw = num(SRC_PRESS)
        pressure_hpa = round(self._to_hpa(p_raw, uom(SRC_PRESS)), 1) if p_raw is not None else None
        if pressure_hpa is not None:
            data[KEY_NORM_PRESSURE_HPA] = pressure_hpa

        ws_raw = num(SRC_WIND)
        wind_ms = round(self._to_ms(ws_raw, uom(SRC_WIND)), 2) if ws_raw is not None else None
        if wind_ms is not None:
            data[KEY_NORM_WIND_SPEED_MS] = wind_ms

        wg_raw = num(SRC_GUST)
        gust_ms = round(self._to_ms(wg_raw, uom(SRC_GUST)), 2) if wg_raw is not None else None
        if gust_ms is not None:
            data[KEY_NORM_WIND_GUST_MS] = gust_ms

        wd_raw = num(SRC_WIND_DIR)
        wind_dir = round(float(wd_raw), 1) if wd_raw is not None else None
        if wind_dir is not None:
            data[KEY_NORM_WIND_DIR_DEG] = wind_dir

        rtot_raw = num(SRC_RAIN_TOTAL)
        rain_total_mm = round(self._to_mm(rtot_raw, uom(SRC_RAIN_TOTAL)), 2) if rtot_raw is not None else None
        if rain_total_mm is not None:
            data[KEY_NORM_RAIN_TOTAL_MM] = rain_total_mm

        lux_raw = num(SRC_LUX)
        lux = round(lux_raw, 1) if lux_raw is not None else None
        if lux is not None:
            data[KEY_LUX] = lux

        uv_raw = num(SRC_UV)
        uv = round(uv_raw, 2) if uv_raw is not None else None
        if uv is not None:
            data[KEY_UV] = uv

        bat_raw = num(SRC_BATTERY)
        if bat_raw is not None:
            data[KEY_BATTERY_PCT] = round(bat_raw)
            data[KEY_BATTERY_DISPLAY] = f"{int(bat_raw)}%"

        # Optional: external dew point sensor
        dp_ext = num(SRC_DEW_POINT)
        if dp_ext is not None:
            dp_c = round(self._to_celsius(dp_ext, self._uom(hass, self.sources.get(SRC_DEW_POINT))), 2)
            data[KEY_DEW_POINT_C] = dp_c

        return tc, rh, pressure_hpa, wind_ms, gust_ms, wind_dir, rain_total_mm, lux, uv

    def _compute_derived_temperature(
        self, data: dict, now: Any, tc: float | None, rh: float | None, wind_ms: float | None
    ) -> float | None:
        """Dew point, feels-like, 24h temperature stats. Returns dew_c."""
        rt = self.runtime

        # Compute dew point if not already set by external sensor
        dew_c: float | None = data.get(KEY_DEW_POINT_C)
        if dew_c is None and tc is not None and rh is not None:
            rh_clamped = max(1.0, min(100.0, float(rh)))
            gamma = (MAGNUS_A * float(tc)) / (MAGNUS_B + float(tc)) + math.log(rh_clamped / 100.0)
            dew_c = round((MAGNUS_B * gamma) / (MAGNUS_A - gamma), 2)
            data[KEY_DEW_POINT_C] = dew_c

        # Apparent temperature (Australian BOM)
        if tc is not None and rh is not None and wind_ms is not None:
            data[KEY_FEELS_LIKE_C] = calculate_apparent_temperature(
                float(tc), float(rh), float(wind_ms)
            )

        # 24h rolling stats
        if tc is not None:
            self._append_and_prune_24h(rt.temp_history_24h, now, float(tc))
        if rt.temp_history_24h:
            temps = self._rolling_values(rt.temp_history_24h)
            data[KEY_TEMP_HIGH_24H] = round(max(temps), 1)
            data[KEY_TEMP_LOW_24H] = round(min(temps), 1)
            data[KEY_TEMP_AVG_24H] = round(sum(temps) / len(temps), 1)

        # Display strings
        if tc is not None:
            data[KEY_TEMP_DISPLAY] = f"{float(tc):.1f}°C"
        if rh is not None:
            data[KEY_HUMIDITY_LEVEL_DISPLAY] = humidity_level(float(rh))
        if uv := data.get(KEY_UV):
            data[KEY_UV_LEVEL_DISPLAY] = uv_level(float(uv))

        return dew_c

    def _compute_derived_pressure(
        self, data: dict, now: Any, tc: float | None, pressure_hpa: float | None,
        rh: float | None
    ) -> tuple[float, float]:
        """MSLP, pressure history, trend, Zambretti. Returns (trend_3h, mslp_or_0)."""
        rt = self.runtime

        mslp: float | None = None
        if pressure_hpa is not None and tc is not None:
            mslp = calculate_sea_level_pressure(float(pressure_hpa), self.elevation_m, float(tc))
            data[KEY_SEA_LEVEL_PRESSURE_HPA] = mslp
            rt.last_mslp = mslp

        # Pressure history (sampled every PRESSURE_HISTORY_INTERVAL_MIN minutes)
        if pressure_hpa is not None:
            if rt.pressure_history_ts is None:
                rt.pressure_history.append(float(pressure_hpa))
                rt.pressure_history_ts = now
            else:
                elapsed_min = (now - rt.pressure_history_ts).total_seconds() / 60.0
                if elapsed_min >= PRESSURE_HISTORY_INTERVAL_MIN:
                    rt.pressure_history.append(float(pressure_hpa))
                    rt.pressure_history_ts = now

            if len(rt.pressure_history) >= 2:
                trend_3h = least_squares_pressure_trend(list(rt.pressure_history))
                data[KEY_PRESSURE_TREND_HPAH] = trend_3h
                data[KEY_PRESSURE_CHANGE_WINDOW_HPA] = round(
                    rt.pressure_history[-1] - rt.pressure_history[0], 2
                )
            else:
                data[KEY_PRESSURE_TREND_HPAH] = 0.0
                data[KEY_PRESSURE_CHANGE_WINDOW_HPA] = 0.0

        trend_3h: float = data.get(KEY_PRESSURE_TREND_HPAH, 0.0)
        data[KEY_PRESSURE_TREND_DISPLAY] = pressure_trend_display(float(trend_3h))

        # Zambretti forecast (uses hemisphere + climate region from config)
        wind_quad = data.get(KEY_WIND_QUADRANT, "N")
        if mslp is not None and rh is not None:
            zambretti = zambretti_forecast(
                mslp=mslp,
                pressure_trend_3h=float(trend_3h),
                wind_quadrant=str(wind_quad),
                humidity=float(rh),
                month=dt_util.now().month,
                hemisphere=self.hemisphere,
                climate=self.climate_region,
            )
            data[KEY_ZAMBRETTI_FORECAST] = zambretti
        else:
            data[KEY_ZAMBRETTI_FORECAST] = "No significant change"

        return trend_3h, (mslp or 0.0)

    def _compute_derived_wind(
        self, data: dict, now: Any, wind_ms: float | None, gust_ms: float | None, wind_dir: float | None
    ) -> None:
        """Beaufort, quadrant, smoothed direction, 24h gust max."""
        rt = self.runtime

        # Wind direction smoothing
        if wind_dir is not None:
            if rt.smoothed_wind_dir is None:
                rt.smoothed_wind_dir = float(wind_dir)
            else:
                rt.smoothed_wind_dir = smooth_wind_direction(
                    float(wind_dir), rt.smoothed_wind_dir, alpha=WIND_SMOOTH_ALPHA
                )
            data[KEY_WIND_DIR_SMOOTH_DEG] = rt.smoothed_wind_dir

        smooth_dir = data.get(KEY_WIND_DIR_SMOOTH_DEG, wind_dir)
        if smooth_dir is not None:
            data[KEY_WIND_QUADRANT] = direction_to_quadrant(float(smooth_dir))

        if wind_ms is not None:
            bft = wind_speed_to_beaufort(float(wind_ms))
            data[KEY_WIND_BEAUFORT] = bft
            data[KEY_WIND_BEAUFORT_DESC] = beaufort_description(bft)

        # 24h gust max
        if gust_ms is not None:
            self._append_and_prune_24h(rt.gust_history_24h, now, float(gust_ms))
        if rt.gust_history_24h:
            gust_vals = self._rolling_values(rt.gust_history_24h)
            if gust_vals:
                data[KEY_WIND_GUST_MAX_24H] = round(max(gust_vals), 1)

    def _compute_derived_precipitation(
        self, data: dict, now: Any, rain_total_mm: float | None
    ) -> float:
        """Rain rate (Kalman-filtered), rain display. Returns rain_rate (filtered)."""
        rt = self.runtime

        if rain_total_mm is not None:
            self._append_and_prune_24h(rt.rain_total_history_24h, now, float(rain_total_mm))

            if rt.last_rain_total_mm is None or rt.last_rain_ts is None:
                rt.last_rain_total_mm = float(rain_total_mm)
                rt.last_rain_ts = now
                data[KEY_RAIN_RATE_RAW] = 0.0
                data[KEY_RAIN_RATE_FILT] = 0.0
            else:
                dv = float(rain_total_mm) - float(rt.last_rain_total_mm)
                dt_h = max(1e-6, (now - rt.last_rain_ts).total_seconds() / 3600.0)
                if dv < -0.1:
                    dv = 0.0  # counter reset protection
                raw = max(0.0, min(dv / dt_h, RAIN_RATE_PHYSICAL_CAP_MMPH))
                filtered = rt.kalman.update(raw)
                rt.last_rain_total_mm = float(rain_total_mm)
                rt.last_rain_ts = now
                data[KEY_RAIN_RATE_RAW] = round(raw, 2)
                data[KEY_RAIN_RATE_FILT] = filtered

        rain_rate: float = data.get(KEY_RAIN_RATE_FILT, 0.0)
        data[KEY_RAIN_DISPLAY] = format_rain_display(float(rain_rate))
        return rain_rate

    def _compute_condition(
        self, data: dict, tc: float | None, rh: float | None,
        wind_ms: float | None, gust_ms: float | None, rain_rate: float,
        dew_c: float | None, lux: float | None, uv: float | None,
    ) -> str:
        """Determine current weather condition (36-condition classifier)."""
        sun_state = self.hass.states.get("sun.sun")
        sun_elev = 0.0
        sun_azimuth = 180.0
        is_day = True
        if sun_state:
            sun_elev = float(sun_state.attributes.get("elevation", 0))
            sun_azimuth = float(sun_state.attributes.get("azimuth", 180))
            is_day = sun_state.state == "above_horizon"

        if tc is None or rh is None:
            return "sunny" if is_day else "clear-night"

        condition = determine_current_condition(
            temp_c=float(tc),
            humidity=float(rh),
            wind_speed_ms=float(wind_ms or 0),
            wind_gust_ms=float(gust_ms or 0),
            rain_rate_mmph=float(rain_rate),
            dew_point_c=float(dew_c or 0),
            illuminance_lx=float(lux or 50000),
            uv_index=float(uv or 0),
            zambretti=str(data.get(KEY_ZAMBRETTI_FORECAST, "")),
            pressure_trend=float(data.get(KEY_PRESSURE_TREND_HPAH, 0)),
            sun_elevation=sun_elev,
            sun_azimuth=sun_azimuth,
            is_day=is_day,
        )
        data[KEY_CURRENT_CONDITION] = condition
        data["_condition_icon"] = CONDITION_ICONS.get(condition, "mdi:weather-partly-cloudy")
        data["_condition_color"] = CONDITION_COLORS.get(condition, "#FCD34D")
        data["_condition_description"] = CONDITION_DESCRIPTIONS.get(condition, condition)
        data["_condition_severity"] = get_condition_severity(condition)
        return condition

    def _compute_rain_probability(
        self, data: dict, mslp: float, trend_3h: float, rh: float | None
    ) -> None:
        """Local + API-blended rain probability."""
        wind_quad = data.get(KEY_WIND_QUADRANT, "N")
        if mslp and rh is not None:
            local_prob = calculate_rain_probability(
                mslp=float(mslp),
                pressure_trend=float(trend_3h),
                humidity=float(rh),
                wind_quadrant=str(wind_quad),
            )
            data[KEY_RAIN_PROBABILITY] = local_prob

            # Blend with API precipitation probability if available
            api_prob = None
            fc = getattr(self, "_forecast_cache", None)
            if fc and fc.get("daily"):
                pp = (fc["daily"][0] or {}).get("precip_prob")
                if pp is not None:
                    api_prob = int(pp)

            combined = combine_rain_probability(local_prob, api_prob, dt_util.now().hour)
            data[KEY_RAIN_PROBABILITY_COMBINED] = combined

    def _compute_activity_scores(
        self, data: dict, tc: float | None, rh: float | None,
        wind_ms: float | None, rain_rate: float, uv: float | None
    ) -> None:
        """Laundry, stargazing, fire weather, running activity scores."""
        feels_like = data.get(KEY_FEELS_LIKE_C)

        # Laundry drying
        if tc is not None and rh is not None and wind_ms is not None:
            rain_prob = data.get(KEY_RAIN_PROBABILITY_COMBINED)
            l_score = laundry_drying_score(
                temp_c=float(tc), humidity=float(rh), wind_speed_ms=float(wind_ms),
                uv_index=float(uv or 0), rain_rate_mmph=float(rain_rate),
                rain_probability=float(rain_prob) if rain_prob is not None else None,
            )
            data[KEY_LAUNDRY_SCORE] = l_score
            data["_laundry_recommendation"] = laundry_recommendation(
                l_score, float(rain_rate), float(rain_prob) if rain_prob is not None else None
            )
            data["_laundry_dry_time"] = laundry_dry_time(l_score, float(rain_rate))

        # Stargazing
        if rh is not None:
            moon_phase = self._get_moon_phase()
            sg_quality = stargazing_quality(
                cloud_cover_pct=None, humidity=float(rh),
                rain_rate_mmph=float(rain_rate), moon_phase=moon_phase,
            )
            data[KEY_STARGAZE_SCORE] = sg_quality
            data["_moon_phase"] = moon_phase
            data["_moon_stargazing_impact"] = moon_stargazing_impact(moon_phase)

        # Fire Weather Index — uses real 24h rain accumulation
        if tc is not None and rh is not None and wind_ms is not None:
            rt = self.runtime
            rain_24h = self._rain_accum_24h_from_totals(rt.rain_total_history_24h)
            fwi = fire_weather_index(float(tc), float(rh), float(wind_ms), rain_24h)
            data[KEY_FIRE_SCORE] = fwi
            data["_fire_danger_level"] = fire_danger_level(fwi)
            data["_fire_rain_24h_mm"] = round(rain_24h, 1)

        # Running conditions
        if feels_like is not None and uv is not None:
            r_score = running_score(float(feels_like), float(uv))
            data[KEY_RUNNING_SCORE] = r_score
            data["running_score"] = r_score
            data["_running_level"] = running_level(r_score)
            data["_running_recommendation"] = running_recommendation(float(feels_like), float(uv))

        # UV exposure details
        if uv is not None:
            data["_uv_recommendation"] = uv_recommendation(float(uv))
            data["_uv_burn_fair_skin"] = f"{uv_burn_time_minutes(float(uv), 2)} minutes"

    def _compute_health(
        self, data: dict, now: Any, missing: list, missing_entities: list
    ) -> None:
        """Staleness, package status, data quality, configurable alerts."""
        # Staleness check
        stale = []
        for k, eid in self.sources.items():
            if not eid:
                continue
            st = self.hass.states.get(eid)
            if st is None:
                continue
            if (now - st.last_updated).total_seconds() > self.staleness_s:
                stale.append(k)

        n_unavailable = len(missing_entities)
        n_healthy = len(self.sources) - n_unavailable - len(stale)

        station_health = (
            "Offline"  if n_unavailable >= 3 else
            "Online"   if n_healthy >= len(REQUIRED_SOURCES) else
            "Degraded" if n_healthy >= 1 else
            "Stale"
        )
        health_color = {
            "Online":   "rgba(74,222,128,0.8)",
            "Degraded": "rgba(251,191,36,0.9)",
            "Stale":    "rgba(249,115,22,0.9)",
            "Offline":  "rgba(239,68,68,0.9)",
        }.get(station_health, "rgba(239,68,68,0.9)")

        data[KEY_HEALTH_DISPLAY] = station_health
        data["_health_color"] = health_color

        # Package status
        ok = not missing and not missing_entities
        parts: list[str] = []
        if missing:
            parts.append("Missing mappings: " + ", ".join(missing))
        if missing_entities:
            parts.append("Entities not found: " + ", ".join(missing_entities))
        if stale:
            parts.append("Stale: " + ", ".join(stale))
        data[KEY_PACKAGE_OK] = bool(ok)
        data[KEY_PACKAGE_STATUS] = " | ".join(parts) if parts else "OK"

        if missing or missing_entities:
            dq = "ERROR: Weather station not configured (missing sources)"
        elif stale:
            dq = f"WARN: Stale data from {', '.join(stale)}"
        else:
            dq = "OK"
        data[KEY_DATA_QUALITY] = dq

        # Configurable alerts
        gust_thr  = float(self.entry_options.get("thresh_wind_gust_ms",  17.0))
        rain_thr  = float(self.entry_options.get("thresh_rain_rate_mmph", 20.0))
        freeze_thr = float(self.entry_options.get("thresh_freeze_c",       0.0))

        gust_ms  = data.get(KEY_NORM_WIND_GUST_MS)
        rain_rate = data.get(KEY_RAIN_RATE_FILT, 0.0)
        tc        = data.get(KEY_NORM_TEMP_C)

        alert_state = "clear"
        alert_msg = "All clear"
        if gust_ms is not None and float(gust_ms) >= gust_thr:
            alert_state = "warning"
            alert_msg = f"Extreme wind: {gust_ms:.1f} m/s"
        if float(rain_rate) >= rain_thr:
            alert_state = "warning"
            alert_msg = f"Heavy rain: {rain_rate:.1f} mm/h"
        if tc is not None and float(tc) <= freeze_thr:
            alert_state = "advisory" if alert_state == "clear" else alert_state
            alert_msg = f"Freeze risk: {tc:.1f}°C"

        data[KEY_ALERT_STATE] = alert_state
        data[KEY_ALERT_MESSAGE] = alert_msg

    # ------------------------------------------------------------------
    # Main orchestrator
    # ------------------------------------------------------------------

    def _compute(self) -> dict[str, Any]:
        data: dict[str, Any] = {}
        now = dt_util.utcnow()

        # Validation
        missing = [k for k in REQUIRED_SOURCES if not self.sources.get(k)]
        missing_entities = [
            k for k in REQUIRED_SOURCES
            if self.sources.get(k) and self.hass.states.get(self.sources[k]) is None
        ]

        # 1. Raw readings
        tc, rh, pressure_hpa, wind_ms, gust_ms, wind_dir, rain_total_mm, lux, uv = (
            self._compute_raw_readings(data, now)
        )

        # 2. Wind (quadrant needed before Zambretti)
        self._compute_derived_wind(data, now, wind_ms, gust_ms, wind_dir)

        # 3. Precipitation
        rain_rate = self._compute_derived_precipitation(data, now, rain_total_mm)

        # 4. Temperature + dew point
        dew_c = self._compute_derived_temperature(data, now, tc, rh, wind_ms)

        # 5. Pressure + Zambretti
        trend_3h, mslp = self._compute_derived_pressure(data, now, tc, pressure_hpa, rh)

        # 6. Rain probability
        self._compute_rain_probability(data, mslp, trend_3h, rh)

        # 7. Sensor quality validation
        flags = self._validate_readings(tc, rh, pressure_hpa, wind_ms, gust_ms, dew_c)
        data[KEY_SENSOR_QUALITY_FLAGS] = flags

        # 8. Current condition classifier
        self._compute_condition(data, tc, rh, wind_ms, gust_ms, rain_rate, dew_c, lux, uv)

        # 9. Activity scores
        self._compute_activity_scores(data, tc, rh, wind_ms, rain_rate, uv)

        # 10. Health, alerts
        self._compute_health(data, now, missing, missing_entities)

        # 11. Forecast
        if self.forecast_enabled:
            data[KEY_FORECAST] = self._get_cached_or_schedule_forecast(now)
        else:
            data[KEY_FORECAST] = None

        fc = getattr(self, "_forecast_cache", None)
        if fc and fc.get("daily"):
            data[KEY_FORECAST_TILES] = self._build_forecast_tiles(fc["daily"])

        return data

    # ------------------------------------------------------------------
    # Moon / forecast helpers
    # ------------------------------------------------------------------

    def _get_moon_phase(self) -> str:
        for entity_id in ("sensor.moon_phase", "sensor.moon"):
            st = self.hass.states.get(entity_id)
            if st and st.state not in ("unknown", "unavailable", "none", ""):
                phase = st.state.replace(" ", "_").lower()
                if phase in MOON_ILLUMINATION:
                    return phase
        now = dt_util.now()
        return calculate_moon_phase(now.year, now.month, now.day)

    def _build_forecast_tiles(self, daily: list) -> list:
        labels = ["Today", "Tomorrow", "Day 3", "Day 4", "Day 5"]
        return [
            {
                "label": labels[i] if i < len(labels) else f"Day {i+1}",
                "date": day.get("date", ""),
                "tmax": day.get("tmax_c"),
                "tmin": day.get("tmin_c"),
                "precip_mm": day.get("precip_mm"),
                "wind_kmh": day.get("wind_kmh"),
                "weathercode": day.get("weathercode"),
            }
            for i, day in enumerate(daily[:5])
        ]

    def _get_cached_or_schedule_forecast(self, now: Any) -> dict[str, Any] | None:
        cached = getattr(self, "_forecast_cache", None)
        last = self.runtime.last_forecast_fetch
        if cached is not None and last is not None:
            age_min = (now - last).total_seconds() / 60.0
            if age_min < max(5, self.forecast_interval_min):
                return cached

        if not self.forecast_enabled:
            return cached

        rt = self.runtime
        if rt.forecast_inflight:
            return cached

        try:
            rt.forecast_inflight = True
            self.hass.async_create_task(self._async_fetch_forecast())
        except Exception:
            rt.forecast_inflight = False
        return cached

    async def _async_fetch_forecast(self) -> None:
        rt = self.runtime
        if not self.forecast_enabled:
            rt.forecast_inflight = False
            return
        lat = self.forecast_lat or float(self.hass.config.latitude)
        lon = self.forecast_lon or float(self.hass.config.longitude)

        url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}"
            "&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,"
            "windspeed_10m_max,weathercode,precipitation_probability_max"
            "&timezone=auto"
        )
        from homeassistant.helpers.aiohttp_client import async_get_clientsession
        session = async_get_clientsession(self.hass)
        try:
            async with session.get(url, timeout=20) as resp:
                if resp.status != 200:
                    rt.forecast_inflight = False
                    return
                js = await resp.json()
        except Exception:
            rt.forecast_inflight = False
            return

        daily = js.get("daily") or {}
        times = daily.get("time") or []
        tmax  = daily.get("temperature_2m_max") or []
        tmin  = daily.get("temperature_2m_min") or []
        pr    = daily.get("precipitation_sum") or []
        ws    = daily.get("windspeed_10m_max") or []
        wc    = daily.get("weathercode") or []
        pp    = daily.get("precipitation_probability_max") or []

        out = [
            {
                "date":       times[i],
                "tmax_c":     tmax[i] if i < len(tmax) else None,
                "tmin_c":     tmin[i] if i < len(tmin) else None,
                "precip_mm":  pr[i]   if i < len(pr)   else None,
                "wind_kmh":   ws[i]   if i < len(ws)   else None,
                "weathercode": wc[i]  if i < len(wc)   else None,
                "precip_prob": pp[i]  if i < len(pp)   else None,
            }
            for i in range(min(len(times), 7))
        ]

        self._forecast_cache = {"daily": out, "provider": "open-meteo", "lat": lat, "lon": lon}
        self.runtime.last_forecast_fetch = dt_util.utcnow()
        self.async_set_updated_data(self._compute())
        rt.forecast_inflight = False
