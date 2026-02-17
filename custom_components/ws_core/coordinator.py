"""Enhanced coordinator for WS Station - v0.2.0.

Full restoration of all meteorological algorithms from the original
weather_station.yaml package (v1.0.0-hotfix17).
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
    calculate_moon_phase,
    calculate_rain_probability,
    calculate_sea_level_pressure,
    combine_rain_probability,
    determine_current_condition,
    direction_to_cardinal_16,
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
    CONF_ELEVATION_M,
    CONF_FORECAST_ENABLED,
    CONF_FORECAST_INTERVAL_MIN,
    CONF_FORECAST_LAT,
    CONF_FORECAST_LON,
    CONF_SOURCES,
    CONF_STALENESS_S,
    CONF_UNITS_MODE,
    DEFAULT_FORECAST_INTERVAL_MIN,
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
    KEY_SEA_LEVEL_PRESSURE_HPA,
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
    REQUIRED_SOURCES,
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
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class WSStationRuntime:
    """Mutable runtime state that persists across compute cycles."""

    # Rain tracking
    last_rain_total_mm: float | None = None
    last_rain_ts: Any | None = None
    last_rain_rate_filt: float = 0.0

    # Pressure tracking
    last_pressure_hpa: float | None = None
    last_pressure_ts: Any | None = None

    # Pressure history deque for least-squares trend (12 samples x 15 min = 3h)
    pressure_history: deque = field(default_factory=lambda: deque(maxlen=12))
    pressure_history_ts: Any | None = None

    # Wind direction smoothing
    smoothed_wind_dir: float | None = None

    # Kalman filter for rain rate
    kalman: KalmanFilter = field(default_factory=KalmanFilter)

    # 24h rolling windows
    temp_history_24h: deque = field(default_factory=lambda: deque(maxlen=1440))
    gust_history_24h: deque = field(default_factory=lambda: deque(maxlen=1440))

    # Forecast cache
    last_forecast_fetch: Any | None = None

    # MSLP (cached for Zambretti)
    last_mslp: float | None = None


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

        sources = dict(entry_data.get(CONF_SOURCES, {}))
        self.sources = sources

        self.units_mode = (
            self.entry_options.get(CONF_UNITS_MODE)
            or entry_data.get(CONF_UNITS_MODE)
            or "auto"
        )
        self.elevation_m = float(
            self.entry_options.get(CONF_ELEVATION_M, entry_data.get(CONF_ELEVATION_M, 0.0))
        )
        self.staleness_s = int(
            self.entry_options.get(CONF_STALENESS_S, entry_data.get(CONF_STALENESS_S, DEFAULT_STALENESS_S))
        )
        self.forecast_enabled = bool(
            self.entry_options.get(CONF_FORECAST_ENABLED, entry_data.get(CONF_FORECAST_ENABLED, True))
        )
        self.forecast_lat = self.entry_options.get(CONF_FORECAST_LAT, entry_data.get(CONF_FORECAST_LAT))
        self.forecast_lon = self.entry_options.get(CONF_FORECAST_LON, entry_data.get(CONF_FORECAST_LON))
        self.forecast_interval_min = int(
            self.entry_options.get(CONF_FORECAST_INTERVAL_MIN, entry_data.get(CONF_FORECAST_INTERVAL_MIN, DEFAULT_FORECAST_INTERVAL_MIN))
        )

        super().__init__(
            hass,
            logger=_LOGGER,
            name="WS Station",
            update_interval=timedelta(seconds=60),
        )

        self._unsubs: list = []

    async def async_start(self) -> None:
        """Start listeners."""
        entity_ids = [eid for eid in self.sources.values() if eid]
        if entity_ids:
            unsub = async_track_state_change_event(self.hass, entity_ids, self._handle_source_change)
            self._unsubs.append(unsub)
        unsub2 = async_track_time_interval(self.hass, self._handle_tick, timedelta(seconds=60))
        self._unsubs.append(unsub2)
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

    @staticmethod
    def _uom(hass: HomeAssistant, eid: str | None) -> str:
        if not eid:
            return ""
        st = hass.states.get(eid)
        if st is None:
            return ""
        return str(st.attributes.get("unit_of_measurement") or "")

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
        if u in ("mph",):
            return v * 0.44704
        if u in ("kn", "knot", "knots"):
            return v * 0.514444
        return v  # assume m/s

    @staticmethod
    def _to_hpa(v: float, unit: str) -> float:
        u = unit.lower().replace(" ", "")
        if u == "pa":
            return v / 100.0
        if u in ("inhg",):
            return v * 33.8638866667
        if u in ("mmhg", "torr"):
            return v * 1.33322
        return v  # assume hPa/mbar

    @staticmethod
    def _to_mm(v: float, unit: str) -> float:
        u = unit.lower().replace(" ", "")
        if u in ("in", "inch", "inches"):
            return v * 25.4
        return v  # assume mm

    # ------------------------------------------------------------------
    # Main compute method
    # ------------------------------------------------------------------

    def _compute(self) -> dict[str, Any]:  # noqa: C901 (intentionally long)
        data: dict[str, Any] = {}
        now = dt_util.utcnow()
        hass = self.hass
        rt = self.runtime

        # ---- Validation ----
        missing = [k for k in REQUIRED_SOURCES if not self.sources.get(k)]
        missing_entities = [
            k for k in REQUIRED_SOURCES
            if self.sources.get(k) and hass.states.get(self.sources[k]) is None
        ]

        def num(key: str) -> float | None:
            return self._num(hass, self.sources.get(key))

        def uom(key: str) -> str:
            return self._uom(hass, self.sources.get(key))

        # ---- Raw readings with unit conversion ----
        t_raw = num(SRC_TEMP)
        if t_raw is not None:
            data[KEY_NORM_TEMP_C] = round(self._to_celsius(t_raw, uom(SRC_TEMP)), 2)

        h_raw = num(SRC_HUM)
        if h_raw is not None:
            data[KEY_NORM_HUMIDITY] = round(h_raw, 1)

        p_raw = num(SRC_PRESS)
        if p_raw is not None:
            data[KEY_NORM_PRESSURE_HPA] = round(self._to_hpa(p_raw, uom(SRC_PRESS)), 1)

        ws_raw = num(SRC_WIND)
        if ws_raw is not None:
            data[KEY_NORM_WIND_SPEED_MS] = round(self._to_ms(ws_raw, uom(SRC_WIND)), 2)

        wg_raw = num(SRC_GUST)
        if wg_raw is not None:
            data[KEY_NORM_WIND_GUST_MS] = round(self._to_ms(wg_raw, uom(SRC_GUST)), 2)

        wd_raw = num(SRC_WIND_DIR)
        if wd_raw is not None:
            data[KEY_NORM_WIND_DIR_DEG] = round(float(wd_raw), 1)

        rtot_raw = num(SRC_RAIN_TOTAL)
        if rtot_raw is not None:
            data[KEY_NORM_RAIN_TOTAL_MM] = round(self._to_mm(rtot_raw, uom(SRC_RAIN_TOTAL)), 2)

        lux_raw = num(SRC_LUX)
        if lux_raw is not None:
            data[KEY_LUX] = round(lux_raw, 1)

        uv_raw = num(SRC_UV)
        if uv_raw is not None:
            data[KEY_UV] = round(uv_raw, 2)

        bat_raw = num(SRC_BATTERY)
        if bat_raw is not None:
            data[KEY_BATTERY_PCT] = round(bat_raw, 0)

        # ---- Shortcuts ----
        tc = data.get(KEY_NORM_TEMP_C)
        rh = data.get(KEY_NORM_HUMIDITY)
        pressure_hpa = data.get(KEY_NORM_PRESSURE_HPA)
        wind_ms = data.get(KEY_NORM_WIND_SPEED_MS)
        gust_ms = data.get(KEY_NORM_WIND_GUST_MS)
        wind_dir = data.get(KEY_NORM_WIND_DIR_DEG)
        lux = data.get(KEY_LUX)
        uv = data.get(KEY_UV)

        # ---- Dew point ----
        dp_raw = num(SRC_DEW_POINT)
        if dp_raw is not None:
            data[KEY_DEW_POINT_C] = round(self._to_celsius(dp_raw, uom(SRC_DEW_POINT)), 2)
        elif tc is not None and rh is not None:
            rh_clamped = max(1.0, min(100.0, float(rh)))
            a, b = 17.62, 243.12
            gamma = (a * float(tc)) / (b + float(tc)) + math.log(rh_clamped / 100.0)
            dp = (b * gamma) / (a - gamma)
            data[KEY_DEW_POINT_C] = round(dp, 2)
        dew_c = data.get(KEY_DEW_POINT_C)

        # ---- MSLP (humidity-corrected sea level pressure) ----
        mslp = None
        if pressure_hpa is not None and tc is not None:
            mslp = calculate_sea_level_pressure(float(pressure_hpa), self.elevation_m, float(tc))
            data[KEY_SEA_LEVEL_PRESSURE_HPA] = mslp
            rt.last_mslp = mslp

        # ---- Pressure history & trend (least-squares over 3h) ----
        if pressure_hpa is not None:
            # Add to 15-min sampled history
            if rt.pressure_history_ts is None:
                rt.pressure_history.append(float(pressure_hpa))
                rt.pressure_history_ts = now
            else:
                elapsed = (now - rt.pressure_history_ts).total_seconds()
                if elapsed >= 900:  # 15 minutes
                    rt.pressure_history.append(float(pressure_hpa))
                    rt.pressure_history_ts = now

            # Least-squares trend
            if len(rt.pressure_history) >= 2:
                trend_3h = least_squares_pressure_trend(list(rt.pressure_history))
                data[KEY_PRESSURE_TREND_HPAH] = trend_3h
                # Simple window change (first vs last reading)
                data[KEY_PRESSURE_CHANGE_WINDOW_HPA] = round(
                    rt.pressure_history[-1] - rt.pressure_history[0], 2
                )
            else:
                data[KEY_PRESSURE_TREND_HPAH] = 0.0
                data[KEY_PRESSURE_CHANGE_WINDOW_HPA] = 0.0

        trend_3h = data.get(KEY_PRESSURE_TREND_HPAH, 0.0)
        pressure_change = data.get(KEY_PRESSURE_CHANGE_WINDOW_HPA, 0.0)

        # ---- Wind direction smoothing ----
        if wind_dir is not None:
            if rt.smoothed_wind_dir is None:
                rt.smoothed_wind_dir = float(wind_dir)
            else:
                rt.smoothed_wind_dir = smooth_wind_direction(float(wind_dir), rt.smoothed_wind_dir)
            data[KEY_WIND_DIR_SMOOTH_DEG] = rt.smoothed_wind_dir

        smooth_dir = data.get(KEY_WIND_DIR_SMOOTH_DEG, wind_dir)

        # ---- Wind quadrant & Beaufort ----
        if smooth_dir is not None:
            data[KEY_WIND_QUADRANT] = direction_to_quadrant(float(smooth_dir))
        elif wind_dir is not None:
            data[KEY_WIND_QUADRANT] = direction_to_quadrant(float(wind_dir))

        if wind_ms is not None:
            bft = wind_speed_to_beaufort(float(wind_ms))
            data[KEY_WIND_BEAUFORT] = bft
            data[KEY_WIND_BEAUFORT_DESC] = beaufort_description(bft)

        # ---- Apparent temperature (Australian BOM standard) ----
        if tc is not None and rh is not None and wind_ms is not None:
            data[KEY_FEELS_LIKE_C] = calculate_apparent_temperature(
                float(tc), float(rh), float(wind_ms)
            )

        # ---- Rain rate (Kalman-filtered) ----
        rain_total_mm = data.get(KEY_NORM_RAIN_TOTAL_MM)
        if rain_total_mm is not None:
            if rt.last_rain_total_mm is None or rt.last_rain_ts is None:
                rt.last_rain_total_mm = float(rain_total_mm)
                rt.last_rain_ts = now
                data[KEY_RAIN_RATE_RAW] = 0.0
                data[KEY_RAIN_RATE_FILT] = 0.0
            else:
                dv = float(rain_total_mm) - float(rt.last_rain_total_mm)
                dt_h = max(1e-6, (now - rt.last_rain_ts).total_seconds() / 3600.0)
                if dv < -0.1:
                    dv = 0.0  # counter reset
                raw = max(0.0, min(dv / dt_h, 500.0))
                filtered = rt.kalman.update(raw)
                rt.last_rain_total_mm = float(rain_total_mm)
                rt.last_rain_ts = now
                data[KEY_RAIN_RATE_RAW] = round(raw, 2)
                data[KEY_RAIN_RATE_FILT] = filtered

        rain_rate = data.get(KEY_RAIN_RATE_FILT, 0.0)

        # ---- 24h rolling statistics ----
        if tc is not None:
            rt.temp_history_24h.append(float(tc))
        if gust_ms is not None:
            rt.gust_history_24h.append(float(gust_ms))

        if rt.temp_history_24h:
            temps = list(rt.temp_history_24h)
            data[KEY_TEMP_HIGH_24H] = round(max(temps), 1)
            data[KEY_TEMP_LOW_24H] = round(min(temps), 1)
            data[KEY_TEMP_AVG_24H] = round(sum(temps) / len(temps), 1)
        if rt.gust_history_24h:
            data[KEY_WIND_GUST_MAX_24H] = round(max(rt.gust_history_24h), 1)

        # ---- Zambretti forecast ----
        wind_quad = data.get(KEY_WIND_QUADRANT, "N")
        if mslp is not None and rh is not None:
            zambretti = zambretti_forecast(
                mslp=mslp,
                pressure_trend_3h=float(trend_3h),
                wind_quadrant=str(wind_quad),
                humidity=float(rh),
                month=dt_util.now().month,
            )
            data[KEY_ZAMBRETTI_FORECAST] = zambretti
        else:
            data[KEY_ZAMBRETTI_FORECAST] = "No significant change"

        zambretti = data.get(KEY_ZAMBRETTI_FORECAST, "")

        # ---- Rain probability ----
        if mslp is not None and rh is not None:
            local_prob = calculate_rain_probability(
                mslp=float(mslp),
                pressure_trend=float(trend_3h),
                humidity=float(rh),
                wind_quadrant=str(wind_quad),
            )
            data[KEY_RAIN_PROBABILITY] = local_prob

            # Get API rain probability from forecast cache if available
            api_prob = None
            forecast_cache = getattr(self, "_forecast_cache", None)
            if forecast_cache and forecast_cache.get("daily"):
                first_day = forecast_cache["daily"][0]
                api_precip = first_day.get("precip_mm")
                if api_precip is not None:
                    # Rough conversion: >5mm precip implies ~80% probability
                    api_prob = min(100, round(float(api_precip) * 15))

            combined = combine_rain_probability(local_prob, api_prob, dt_util.now().hour)
            data[KEY_RAIN_PROBABILITY_COMBINED] = combined

        # ---- Rain display ----
        data[KEY_RAIN_DISPLAY] = format_rain_display(float(rain_rate))

        # ---- Pressure trend display ----
        data[KEY_PRESSURE_TREND_DISPLAY] = pressure_trend_display(float(trend_3h))

        # ---- Current condition (36 conditions) ----
        sun_state = hass.states.get("sun.sun")
        sun_elev = 0.0
        sun_azimuth = 180.0
        is_day = True
        if sun_state:
            sun_elev = float(sun_state.attributes.get("elevation", 0))
            sun_azimuth = float(sun_state.attributes.get("azimuth", 180))
            is_day = sun_state.state == "above_horizon"

        if tc is not None and rh is not None:
            condition = determine_current_condition(
                temp_c=float(tc),
                humidity=float(rh),
                wind_speed_ms=float(wind_ms or 0),
                wind_gust_ms=float(gust_ms or 0),
                rain_rate_mmph=float(rain_rate),
                dew_point_c=float(dew_c or 0),
                illuminance_lx=float(lux or 50000),
                uv_index=float(uv or 0),
                zambretti=str(zambretti),
                pressure_trend=float(trend_3h),
                sun_elevation=sun_elev,
                sun_azimuth=sun_azimuth,
                is_day=is_day,
            )
            data[KEY_CURRENT_CONDITION] = condition
            # Populate condition metadata for sensor attributes
            from .algorithms import CONDITION_ICONS, CONDITION_COLORS, CONDITION_DESCRIPTIONS, get_condition_severity
            data["_condition_icon"] = CONDITION_ICONS.get(condition, "mdi:weather-partly-cloudy")
            data["_condition_color"] = CONDITION_COLORS.get(condition, "#FCD34D")
            data["_condition_description"] = CONDITION_DESCRIPTIONS.get(condition, condition)
            data["_condition_severity"] = get_condition_severity(condition)

        # ---- Display/level sensors ----
        if rh is not None:
            data[KEY_HUMIDITY_LEVEL_DISPLAY] = humidity_level(float(rh))
        if uv is not None:
            data[KEY_UV_LEVEL_DISPLAY] = uv_level(float(uv))
        if tc is not None:
            data[KEY_TEMP_DISPLAY] = f"{float(tc):.1f}°C"
        if bat_raw is not None:
            data[KEY_BATTERY_DISPLAY] = f"{int(bat_raw)}%"

        # ---- Station health ----
        stale = []
        for k, eid in self.sources.items():
            if not eid:
                continue
            st = hass.states.get(eid)
            if st is None:
                continue
            age = (now - st.last_updated).total_seconds()
            if age > self.staleness_s:
                stale.append(k)

        n_unavailable = len(missing_entities)
        n_healthy = len(self.sources) - n_unavailable - len(stale)

        if n_unavailable >= 3:
            station_health = "Offline"
        elif n_healthy >= len(REQUIRED_SOURCES):
            station_health = "Online"
        elif n_healthy >= 1:
            station_health = "Degraded"
        else:
            station_health = "Stale"

        health_color = {
            "Online": "rgba(74,222,128,0.8)",
            "Degraded": "rgba(251,191,36,0.9)",
            "Stale": "rgba(249,115,22,0.9)",
            "Offline": "rgba(239,68,68,0.9)",
        }.get(station_health, "rgba(239,68,68,0.9)")

        data[KEY_HEALTH_DISPLAY] = station_health
        # Store color as attribute dict that sensor.py can expose
        data["_health_color"] = health_color

        # ---- Package status ----
        ok = not missing and not missing_entities
        status_parts: list[str] = []
        if missing:
            status_parts.append("Missing mappings: " + ", ".join(missing))
        if missing_entities:
            status_parts.append("Entities not found: " + ", ".join(missing_entities))
        if stale:
            status_parts.append("Stale: " + ", ".join(stale))
        data[KEY_PACKAGE_OK] = bool(ok)
        data[KEY_PACKAGE_STATUS] = " | ".join(status_parts) if status_parts else "OK"

        if missing or missing_entities:
            dq = "ERROR: Weather station not configured (missing sources)"
        elif stale:
            dq = f"WARN: Stale data from {', '.join(stale)}"
        else:
            dq = "OK"
        data[KEY_DATA_QUALITY] = dq

        # ---- Alerts ----
        gust_thr = float(self.entry_options.get("thresh_wind_gust_ms", 17.0))
        rain_thr = float(self.entry_options.get("thresh_rain_rate_mmph", 20.0))
        freeze_thr = float(self.entry_options.get("thresh_freeze_c", 0.0))

        alert_state = "clear"
        alert_msg = "All clear"
        if gust_ms is not None and float(gust_ms) >= gust_thr:
            alert_state = "warning"
            alert_msg = f"High wind gusts: {gust_ms:.1f} m/s"
        if rain_rate is not None and float(rain_rate) >= rain_thr:
            alert_state = "warning"
            alert_msg = f"Heavy rain rate: {rain_rate:.1f} mm/h"
        if tc is not None and float(tc) <= freeze_thr:
            if alert_state == "clear":
                alert_state = "advisory"
            alert_msg = f"Freeze risk: {tc:.1f} °C"

        data[KEY_ALERT_STATE] = alert_state
        data[KEY_ALERT_MESSAGE] = alert_msg

        # ---- Activity scores ----
        feels_like = data.get(KEY_FEELS_LIKE_C)

        # Laundry
        if tc is not None and rh is not None and wind_ms is not None:
            fc_rain_prob = data.get(KEY_RAIN_PROBABILITY_COMBINED)
            l_score = laundry_drying_score(
                temp_c=float(tc),
                humidity=float(rh),
                wind_speed_ms=float(wind_ms),
                uv_index=float(uv or 0),
                rain_rate_mmph=float(rain_rate),
                rain_probability=float(fc_rain_prob) if fc_rain_prob is not None else None,
            )
            data[KEY_LAUNDRY_SCORE] = l_score
            data["_laundry_recommendation"] = laundry_recommendation(
                l_score, float(rain_rate), float(fc_rain_prob) if fc_rain_prob is not None else None
            )
            data["_laundry_dry_time"] = laundry_dry_time(l_score, float(rain_rate))

        # Stargazing
        if rh is not None:
            moon_phase = self._get_moon_phase()
            sg_quality = stargazing_quality(
                cloud_cover_pct=None,
                humidity=float(rh),
                rain_rate_mmph=float(rain_rate),
                moon_phase=moon_phase,
            )
            data[KEY_STARGAZE_SCORE] = sg_quality
            data["_moon_phase"] = moon_phase
            data["_moon_stargazing_impact"] = moon_stargazing_impact(moon_phase)

        # Fire weather
        if tc is not None and rh is not None and wind_ms is not None:
            rain_24h = 0.0
            fwi = fire_weather_index(float(tc), float(rh), float(wind_ms), rain_24h)
            data[KEY_FIRE_SCORE] = fwi
            data["_fire_danger_level"] = fire_danger_level(fwi)

        # Running
        if feels_like is not None and uv is not None:
            r_score = running_score(float(feels_like), float(uv))
            data["_running_score"] = r_score
            data["_running_level"] = running_level(r_score)
            data["_running_recommendation"] = running_recommendation(float(feels_like), float(uv))

        # UV exposure
        if uv is not None:
            data["_uv_level"] = uv_level(float(uv))
            data["_uv_recommendation"] = uv_recommendation(float(uv))
            data["_uv_burn_fair_skin"] = f"{uv_burn_time_minutes(float(uv), 2)} minutes"

        # ---- Forecast ----
        if self.forecast_enabled:
            data[KEY_FORECAST] = self._get_cached_or_schedule_forecast(now)
        else:
            data[KEY_FORECAST] = None

        # ---- Forecast tiles ----
        forecast_cache = getattr(self, "_forecast_cache", None)
        if forecast_cache and forecast_cache.get("daily"):
            data[KEY_FORECAST_TILES] = self._build_forecast_tiles(forecast_cache["daily"])

        return data

    def _get_moon_phase(self) -> str:
        """Get moon phase from HA sensor or calculate from date."""
        # Try HA moon integration first
        for entity_id in ("sensor.moon_phase", "sensor.moon"):
            st = self.hass.states.get(entity_id)
            if st and st.state not in ("unknown", "unavailable", "none", ""):
                phase = st.state.replace(" ", "_").lower()
                if phase in MOON_ILLUMINATION:
                    return phase

        # Fallback: calculate from date
        now = dt_util.now()
        return calculate_moon_phase(now.year, now.month, now.day)

    def _build_forecast_tiles(self, daily: list) -> list:
        """Build formatted forecast tile data for dashboard."""
        tiles = []
        day_labels = ["Today", "Tomorrow", "Day 3", "Day 4", "Day 5"]
        for i, day in enumerate(daily[:5]):
            tiles.append({
                "label": day_labels[i] if i < len(day_labels) else f"Day {i+1}",
                "date": day.get("date", ""),
                "tmax": day.get("tmax_c"),
                "tmin": day.get("tmin_c"),
                "precip_mm": day.get("precip_mm"),
                "wind_kmh": day.get("wind_kmh"),
                "weathercode": day.get("weathercode"),
            })
        return tiles

    def _get_cached_or_schedule_forecast(self, now) -> dict[str, Any] | None:
        cached = getattr(self, "_forecast_cache", None)
        last = self.runtime.last_forecast_fetch
        if cached is not None and last is not None:
            age_min = (now - last).total_seconds() / 60.0
            if age_min < max(5, self.forecast_interval_min):
                return cached
        try:
            self.hass.async_create_task(self._async_fetch_forecast())
        except Exception:
            pass
        return cached

    async def _async_fetch_forecast(self) -> None:
        if not self.forecast_enabled:
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
                    return
                js = await resp.json()
        except Exception:
            return

        daily = js.get("daily") or {}
        times = daily.get("time") or []
        tmax = daily.get("temperature_2m_max") or []
        tmin = daily.get("temperature_2m_min") or []
        pr = daily.get("precipitation_sum") or []
        ws = daily.get("windspeed_10m_max") or []
        wc = daily.get("weathercode") or []
        pp = daily.get("precipitation_probability_max") or []

        out = []
        for i in range(min(len(times), 7)):
            out.append({
                "date": times[i],
                "tmax_c": tmax[i] if i < len(tmax) else None,
                "tmin_c": tmin[i] if i < len(tmin) else None,
                "precip_mm": pr[i] if i < len(pr) else None,
                "wind_kmh": ws[i] if i < len(ws) else None,
                "weathercode": wc[i] if i < len(wc) else None,
                "precip_prob": pp[i] if i < len(pp) else None,
            })

        self._forecast_cache = {"daily": out, "provider": "open-meteo", "lat": lat, "lon": lon}
        self.runtime.last_forecast_fetch = dt_util.utcnow()
        self.async_set_updated_data(self._compute())
