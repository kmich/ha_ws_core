"""Coordinator for Weather Station Core -- v0.5.0.

The _compute() method is broken into focused sub-methods:
  _compute_raw_readings()          Unit conversion of all source sensors
  _compute_derived_temperature()   Dew point, frost point, wet-bulb, feels-like, 24h stats
  _compute_derived_pressure()      MSLP, pressure trend, Zambretti
  _compute_derived_wind()          Beaufort, quadrant, smoothing
  _compute_derived_precipitation() Rain rate, Kalman filter, rain display
  _compute_condition()             36-condition classifier
  _compute_rain_probability()      Local + API probability
  _compute_activity_scores()       Laundry, fire risk, running, stargazing
  _compute_degree_days()           HDD/CDD daily accumulators  [v0.5.0]
  _compute_et0()                   ET₀ Hargreaves-Samani       [v0.6.0]
  _compute_health()                Staleness, package status, alerts
  _compute()                       Orchestrator -- calls all sub-methods
  _async_fetch_metar()             Aviation METAR cross-validation [v0.5.0]
  _async_fetch_cwop()              CWOP APRS-IS upload         [v0.6.0]
  _async_fetch_wunderground()      Weather Underground upload  [v0.6.0]
  _async_export_data()             CSV/JSON file export        [v0.6.0]
"""

from __future__ import annotations

import contextlib
import logging
import math
from collections import deque
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_interval
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

try:
    from homeassistant.helpers import issue_registry as ir

    HAS_REPAIRS = True
except ImportError:
    HAS_REPAIRS = False

from .algorithms import (
    CONDITION_COLORS,
    CONDITION_DESCRIPTIONS,
    CONDITION_ICONS,
    MOON_ILLUMINATION,
    KalmanFilter,
    beaufort_description,
    calculate_apparent_temperature,
    calculate_dew_point,
    calculate_frost_point,
    calculate_moon_phase,
    calculate_rain_probability,
    calculate_wet_bulb,
    combine_rain_probability,
    determine_current_condition,
    direction_to_quadrant,
    et0_hargreaves,
    et0_hourly_estimate,
    fire_danger_level,
    fire_risk_score,
    format_rain_display,
    get_condition_severity,
    heating_degree_hours,
    cooling_degree_hours,
    humidity_level,
    laundry_dry_time,
    laundry_drying_score,
    laundry_recommendation,
    least_squares_pressure_trend,
    metar_validation_label,
    moon_stargazing_impact,
    parse_metar_json,
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
    CONF_ENABLE_SEA_TEMP,
    CONF_FORECAST_ENABLED,
    CONF_FORECAST_INTERVAL_MIN,
    CONF_FORECAST_LAT,
    CONF_FORECAST_LON,
    CONF_HEMISPHERE,
    CONF_SEA_TEMP_LAT,
    CONF_SEA_TEMP_LON,
    CONF_SOURCES,
    CONF_STALENESS_S,
    CONF_UNITS_MODE,
    DEFAULT_CLIMATE_REGION,
    DEFAULT_FORECAST_INTERVAL_MIN,
    DEFAULT_HEMISPHERE,
    DEFAULT_STALENESS_S,
    FORECAST_MAX_RETRY_S,
    FORECAST_MIN_RETRY_S,
    KEY_ALERT_MESSAGE,
    KEY_ALERT_STATE,
    KEY_BATTERY_DISPLAY,
    KEY_BATTERY_PCT,
    KEY_CURRENT_CONDITION,
    KEY_DATA_QUALITY,
    KEY_DEW_POINT_C,
    KEY_FEELS_LIKE_C,
    KEY_FIRE_RISK_SCORE,
    KEY_FORECAST,
    KEY_FORECAST_TILES,
    KEY_FROST_POINT_C,
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
    KEY_RAIN_ACCUM_1H,
    KEY_RAIN_ACCUM_24H,
    KEY_RAIN_DISPLAY,
    KEY_RAIN_PROBABILITY,
    KEY_RAIN_PROBABILITY_COMBINED,
    KEY_RAIN_RATE_FILT,
    KEY_RAIN_RATE_RAW,
    KEY_RUNNING_SCORE,
    KEY_SEA_LEVEL_PRESSURE_HPA,
    KEY_SEA_SURFACE_TEMP,
    KEY_SENSOR_QUALITY_FLAGS,
    KEY_STARGAZE_SCORE,
    KEY_TEMP_AVG_24H,
    KEY_TEMP_DISPLAY,
    KEY_TEMP_HIGH_24H,
    KEY_TEMP_LOW_24H,
    KEY_TIME_SINCE_RAIN,
    KEY_UV,
    KEY_UV_LEVEL_DISPLAY,
    KEY_WET_BULB_C,
    KEY_WIND_BEAUFORT,
    KEY_WIND_BEAUFORT_DESC,
    KEY_WIND_DIR_SMOOTH_DEG,
    KEY_WIND_GUST_MAX_24H,
    KEY_WIND_QUADRANT,
    KEY_ZAMBRETTI_FORECAST,
    KEY_ZAMBRETTI_NUMBER,
    PRESSURE_HISTORY_INTERVAL_MIN,
    PRESSURE_HISTORY_SAMPLES,
    RAIN_RATE_PHYSICAL_CAP_MMPH,
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
    STALENESS_CHECK_SOURCES,
    VALID_HUMIDITY_MAX,
    VALID_HUMIDITY_MIN,
    VALID_PRESSURE_MAX_HPA,
    VALID_PRESSURE_MIN_HPA,
    VALID_TEMP_MAX_C,
    VALID_TEMP_MIN_C,
    WIND_SMOOTH_ALPHA,
    # v0.5.0 new
    CONF_ENABLE_DEGREE_DAYS,
    CONF_DEGREE_DAY_BASE_C,
    CONF_ENABLE_METAR,
    CONF_METAR_ICAO,
    CONF_METAR_INTERVAL_MIN,
    DEFAULT_ENABLE_DEGREE_DAYS,
    DEFAULT_DEGREE_DAY_BASE_C,
    DEFAULT_ENABLE_METAR,
    DEFAULT_METAR_INTERVAL_MIN,
    KEY_HDD_TODAY,
    KEY_CDD_TODAY,
    KEY_HDD_RATE,
    KEY_CDD_RATE,
    KEY_METAR_TEMP_C,
    KEY_METAR_PRESSURE_HPA,
    KEY_METAR_WIND_MS,
    KEY_METAR_WIND_DIR,
    KEY_METAR_CONDITION,
    KEY_METAR_DELTA_TEMP,
    KEY_METAR_DELTA_PRESSURE,
    KEY_METAR_VALIDATION,
    KEY_METAR_STATION,
    KEY_METAR_AGE_MIN,
    # v0.6.0 new
    CONF_ENABLE_CWOP,
    CONF_CWOP_CALLSIGN,
    CONF_CWOP_PASSCODE,
    CONF_CWOP_INTERVAL_MIN,
    CONF_ENABLE_WUNDERGROUND,
    CONF_WU_STATION_ID,
    CONF_WU_API_KEY,
    CONF_WU_INTERVAL_MIN,
    CONF_ENABLE_EXPORT,
    CONF_EXPORT_PATH,
    CONF_EXPORT_FORMAT,
    CONF_EXPORT_INTERVAL_MIN,
    DEFAULT_ENABLE_CWOP,
    DEFAULT_CWOP_INTERVAL_MIN,
    DEFAULT_ENABLE_WUNDERGROUND,
    DEFAULT_WU_INTERVAL_MIN,
    DEFAULT_ENABLE_EXPORT,
    DEFAULT_EXPORT_FORMAT,
    DEFAULT_EXPORT_INTERVAL_MIN,
    CONF_FORECAST_LAT,
    CONF_FORECAST_LON,
    KEY_ET0_DAILY_MM,
    KEY_ET0_HOURLY_MM,
    KEY_CWOP_STATUS,
    KEY_WU_STATUS,
    KEY_LAST_EXPORT_TIME,
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
    last_rain_event_ts: Any | None = None

    # Pressure tracking
    pressure_history: deque = field(default_factory=lambda: deque(maxlen=PRESSURE_HISTORY_SAMPLES))
    pressure_history_ts: Any | None = None

    # Wind direction smoothing
    smoothed_wind_dir: float | None = None

    # Kalman filter for rain rate
    kalman: KalmanFilter = field(default_factory=KalmanFilter)

    # 24h rolling windows (timestamp-based)
    temp_history_24h: deque = field(default_factory=deque)
    gust_history_24h: deque = field(default_factory=deque)
    rain_total_history_24h: deque = field(default_factory=deque)

    # Forecast cache
    last_forecast_fetch: Any | None = None
    last_sea_temp_fetch: Any | None = None
    forecast_inflight: bool = False
    forecast_consecutive_failures: int = 0

    # MSLP cached for Zambretti
    last_mslp: float | None = None

    # Compute timing (for diagnostics)
    last_compute_ms: float = 0.0


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

        # Sea surface temperature (Open-Meteo Marine API)
        self.sea_temp_enabled = bool(_get(CONF_ENABLE_SEA_TEMP, False))
        self.sea_temp_lat = _get(CONF_SEA_TEMP_LAT, None)
        self.sea_temp_lon = _get(CONF_SEA_TEMP_LON, None)
        self._sea_temp_cache: dict[str, Any] | None = None

        # Degree days (v0.5.0)
        self.degree_days_enabled = bool(_get(CONF_ENABLE_DEGREE_DAYS, DEFAULT_ENABLE_DEGREE_DAYS))
        self.degree_day_base_c = float(_get(CONF_DEGREE_DAY_BASE_C, DEFAULT_DEGREE_DAY_BASE_C))
        self._hdd_today: float = 0.0
        self._cdd_today: float = 0.0
        self._degree_day_date: str = ""
        self._degree_day_last_ts: Any = None  # datetime of last accumulation tick

        # METAR cross-validation (v0.5.0)
        self.metar_enabled = bool(_get(CONF_ENABLE_METAR, DEFAULT_ENABLE_METAR))
        self.metar_icao: str = str(_get(CONF_METAR_ICAO, "") or "")
        self.metar_interval_min = int(_get(CONF_METAR_INTERVAL_MIN, DEFAULT_METAR_INTERVAL_MIN))
        self._metar_cache: dict[str, Any] | None = None
        self._metar_last_fetch: Any = None

        # v0.6.0 CWOP upload
        self.cwop_enabled = bool(_get(CONF_ENABLE_CWOP, DEFAULT_ENABLE_CWOP))
        self.cwop_callsign: str = str(_get(CONF_CWOP_CALLSIGN, "") or "")
        self.cwop_passcode: str = str(_get(CONF_CWOP_PASSCODE, "-1") or "-1")
        self.cwop_interval_min = int(_get(CONF_CWOP_INTERVAL_MIN, DEFAULT_CWOP_INTERVAL_MIN))
        self._cwop_last_upload: Any = None
        self._cwop_status: str = "Disabled"

        # v0.6.0 Weather Underground upload
        self.wu_enabled = bool(_get(CONF_ENABLE_WUNDERGROUND, DEFAULT_ENABLE_WUNDERGROUND))
        self.wu_station_id: str = str(_get(CONF_WU_STATION_ID, "") or "")
        self.wu_api_key: str = str(_get(CONF_WU_API_KEY, "") or "")
        self.wu_interval_min = int(_get(CONF_WU_INTERVAL_MIN, DEFAULT_WU_INTERVAL_MIN))
        self._wu_last_upload: Any = None
        self._wu_status: str = "Disabled"

        # v0.6.0 CSV/JSON export
        self.export_enabled = bool(_get(CONF_ENABLE_EXPORT, DEFAULT_ENABLE_EXPORT))
        self.export_path: str = str(_get(CONF_EXPORT_PATH, "/config/ws_core_export") or "/config/ws_core_export")
        self.export_format: str = str(_get(CONF_EXPORT_FORMAT, DEFAULT_EXPORT_FORMAT))
        self.export_interval_min = int(_get(CONF_EXPORT_INTERVAL_MIN, DEFAULT_EXPORT_INTERVAL_MIN))
        self._export_last_time: Any = None

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
            self._unsubs.append(async_track_state_change_event(self.hass, entity_ids, self._handle_source_change))
        self._unsubs.append(async_track_time_interval(self.hass, self._handle_tick, timedelta(seconds=60)))

        # METAR periodic fetch (v0.5.0)
        if self.metar_enabled and self.metar_icao:
            self._unsubs.append(
                async_track_time_interval(
                    self.hass,
                    lambda _now: self.hass.async_create_task(self._async_fetch_metar()),
                    timedelta(minutes=self.metar_interval_min),
                )
            )
            self.hass.async_create_task(self._async_fetch_metar())

        # CWOP periodic upload (v0.6.0)
        if self.cwop_enabled and self.cwop_callsign:
            self._unsubs.append(
                async_track_time_interval(
                    self.hass,
                    lambda _now: self.hass.async_create_task(self._async_upload_cwop()),
                    timedelta(minutes=self.cwop_interval_min),
                )
            )

        # Weather Underground periodic upload (v0.6.0)
        if self.wu_enabled and self.wu_station_id and self.wu_api_key:
            self._unsubs.append(
                async_track_time_interval(
                    self.hass,
                    lambda _now: self.hass.async_create_task(self._async_upload_wunderground()),
                    timedelta(minutes=self.wu_interval_min),
                )
            )

        # CSV/JSON export (v0.6.0)
        if self.export_enabled:
            self._unsubs.append(
                async_track_time_interval(
                    self.hass,
                    lambda _now: self.hass.async_create_task(self._async_export_data()),
                    timedelta(minutes=self.export_interval_min),
                )
            )

        await self.async_refresh()

    async def async_stop(self) -> None:
        for u in self._unsubs:
            with contextlib.suppress(Exception):
                u()
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
    # Rolling window helpers (24h timestamp-based)
    # ------------------------------------------------------------------

    @staticmethod
    def _append_and_prune_24h(history: deque, now: Any, value: float) -> None:
        history.append((now, value))
        cutoff = now - timedelta(hours=24)
        while history and history[0][0] < cutoff:
            history.popleft()

    @staticmethod
    def _rolling_values(history: deque) -> list[float]:
        return [v for _, v in history]

    @staticmethod
    def _rain_accum_24h_from_totals(history: deque) -> float:
        vals = [v for _, v in history]
        total = 0.0
        for prev, cur in zip(vals, vals[1:], strict=False):
            dv = cur - prev
            if dv < -0.1:
                dv = 0.0
            if dv > 0:
                total += dv
        return total

    @staticmethod
    def _rain_accum_window_from_totals(history: deque, now: Any, window_h: float) -> float:
        """Rain accumulation over a sliding window (e.g. 1h)."""
        from datetime import timedelta

        cutoff = now - timedelta(hours=window_h)
        vals = [(ts, v) for ts, v in history if ts >= cutoff]
        total = 0.0
        for (_, prev), (_, cur) in zip(vals, vals[1:], strict=False):
            dv = cur - prev
            if dv < -0.1:
                dv = 0.0
            if dv > 0:
                total += dv
        return total

    # ------------------------------------------------------------------
    # Unit conversion helpers
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
        if u in ("f", "\u00b0f") or ("f" in u and "\u00b0" in u):
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
        flags: list[str] = []
        if tc is not None and not (VALID_TEMP_MIN_C <= tc <= VALID_TEMP_MAX_C):
            flags.append(f"temperature {tc:.1f}\u00b0C outside physical range")
        if rh is not None and not (VALID_HUMIDITY_MIN <= rh <= VALID_HUMIDITY_MAX):
            flags.append(f"humidity {rh:.0f}% outside valid range")
        if pressure_hpa is not None and not (VALID_PRESSURE_MIN_HPA <= pressure_hpa <= VALID_PRESSURE_MAX_HPA):
            flags.append(f"pressure {pressure_hpa:.1f} hPa outside physical range")
        if tc is not None and dew_c is not None and dew_c > tc + 0.5:
            flags.append("dew point exceeds temperature (check humidity sensor)")
        if wind_ms is not None and gust_ms is not None and gust_ms < wind_ms * 0.9:
            flags.append("wind gust below wind speed (check anemometer)")
        return flags

    # ------------------------------------------------------------------
    # Sub-methods
    # ------------------------------------------------------------------

    def _compute_raw_readings(self, data: dict, now: Any) -> tuple[float | None, ...]:
        """Read and unit-convert all source sensors."""
        hass = self.hass

        def num(key: str) -> float | None:
            return self._num(hass, self.sources.get(key))

        def uom(key: str) -> str:
            return self._uom(hass, self.sources.get(key))

        t_raw = num(SRC_TEMP)
        tc = round(self._to_celsius(t_raw, uom(SRC_TEMP)), 2) if t_raw is not None else None
        if tc is not None:
            tc = round(tc + float(self.entry_options.get("cal_temp_c", 0.0)), 2)
            data[KEY_NORM_TEMP_C] = tc

        h_raw = num(SRC_HUM)
        rh = round(h_raw, 1) if h_raw is not None else None
        if rh is not None:
            rh = round(max(0.0, min(100.0, rh + float(self.entry_options.get("cal_humidity", 0.0)))), 1)
            data[KEY_NORM_HUMIDITY] = rh

        p_raw = num(SRC_PRESS)
        pressure_hpa = round(self._to_hpa(p_raw, uom(SRC_PRESS)), 1) if p_raw is not None else None
        if pressure_hpa is not None:
            pressure_hpa = round(pressure_hpa + float(self.entry_options.get("cal_pressure_hpa", 0.0)), 1)
            data[KEY_NORM_PRESSURE_HPA] = pressure_hpa

        ws_raw = num(SRC_WIND)
        wind_ms = round(self._to_ms(ws_raw, uom(SRC_WIND)), 2) if ws_raw is not None else None
        if wind_ms is not None:
            wind_ms = round(max(0.0, wind_ms + float(self.entry_options.get("cal_wind_ms", 0.0))), 2)
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
        """Dew point, frost point, wet-bulb, feels-like, 24h stats. Returns dew_c."""
        rt = self.runtime

        # Compute dew point if not already set by external sensor
        dew_c: float | None = data.get(KEY_DEW_POINT_C)
        if dew_c is None and tc is not None and rh is not None:
            dew_c = calculate_dew_point(float(tc), float(rh))
            data[KEY_DEW_POINT_C] = dew_c

        # Frost point (uses ice constants below 0 C)
        if tc is not None and rh is not None:
            data[KEY_FROST_POINT_C] = calculate_frost_point(float(tc), float(rh))

        # Wet-bulb temperature (Stull 2011)
        if tc is not None and rh is not None:
            data[KEY_WET_BULB_C] = calculate_wet_bulb(float(tc), float(rh))

        # Apparent temperature (Australian BOM)
        if tc is not None and rh is not None and wind_ms is not None:
            data[KEY_FEELS_LIKE_C] = calculate_apparent_temperature(float(tc), float(rh), float(wind_ms))

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
            data[KEY_TEMP_DISPLAY] = f"{float(tc):.1f}\u00b0C"
        if rh is not None:
            data[KEY_HUMIDITY_LEVEL_DISPLAY] = humidity_level(float(rh))
        if uv := data.get(KEY_UV):
            data[KEY_UV_LEVEL_DISPLAY] = uv_level(float(uv))

        return dew_c

    def _compute_derived_pressure(
        self, data: dict, now: Any, tc: float | None, pressure_hpa: float | None, rh: float | None
    ) -> tuple[float, float]:
        """MSLP, pressure history, trend, Zambretti. Returns (trend_3h, mslp_or_0)."""
        from .algorithms import calculate_sea_level_pressure

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
                data[KEY_PRESSURE_CHANGE_WINDOW_HPA] = round(rt.pressure_history[-1] - rt.pressure_history[0], 2)
            else:
                data[KEY_PRESSURE_TREND_HPAH] = 0.0
                data[KEY_PRESSURE_CHANGE_WINDOW_HPA] = 0.0

        trend_3h: float = data.get(KEY_PRESSURE_TREND_HPAH, 0.0)
        data[KEY_PRESSURE_TREND_DISPLAY] = pressure_trend_display(float(trend_3h))

        # Zambretti forecast (real N&Z lookup table)
        wind_quad = data.get(KEY_WIND_QUADRANT, "N")
        if mslp is not None and rh is not None:
            forecast_text, z_number = zambretti_forecast(
                mslp=mslp,
                pressure_trend_3h=float(trend_3h),
                wind_quadrant=str(wind_quad),
                humidity=float(rh),
                month=dt_util.now().month,
                hemisphere=self.hemisphere,
                climate=self.climate_region,
            )
            data[KEY_ZAMBRETTI_FORECAST] = forecast_text
            data[KEY_ZAMBRETTI_NUMBER] = z_number
        else:
            data[KEY_ZAMBRETTI_FORECAST] = "Insufficient data"
            data[KEY_ZAMBRETTI_NUMBER] = None

        return trend_3h, (mslp or 0.0)

    def _compute_derived_wind(
        self, data: dict, now: Any, wind_ms: float | None, gust_ms: float | None, wind_dir: float | None
    ) -> None:
        """Beaufort, quadrant, smoothed direction, 24h gust max."""
        rt = self.runtime

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

        if gust_ms is not None:
            self._append_and_prune_24h(rt.gust_history_24h, now, float(gust_ms))
        if rt.gust_history_24h:
            gust_vals = self._rolling_values(rt.gust_history_24h)
            if gust_vals:
                data[KEY_WIND_GUST_MAX_24H] = round(max(gust_vals), 1)

    def _compute_derived_precipitation(self, data: dict, now: Any, rain_total_mm: float | None) -> float:
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
                    dv = 0.0
                raw = max(0.0, min(dv / dt_h, RAIN_RATE_PHYSICAL_CAP_MMPH))
                filtered = rt.kalman.update(raw)
                rt.last_rain_total_mm = float(rain_total_mm)
                rt.last_rain_ts = now
                data[KEY_RAIN_RATE_RAW] = round(raw, 2)
                data[KEY_RAIN_RATE_FILT] = filtered

        rain_rate: float = data.get(KEY_RAIN_RATE_FILT, 0.0)
        data[KEY_RAIN_DISPLAY] = format_rain_display(float(rain_rate))

        # Rain accumulations (1h / 24h)
        if rt.rain_total_history_24h:
            data[KEY_RAIN_ACCUM_1H] = round(self._rain_accum_window_from_totals(rt.rain_total_history_24h, now, 1.0), 1)
            data[KEY_RAIN_ACCUM_24H] = round(self._rain_accum_24h_from_totals(rt.rain_total_history_24h), 1)

        # Track last rain event and compute time since
        if float(rain_rate) > 0.0:
            rt.last_rain_event_ts = now
        if rt.last_rain_event_ts is not None:
            delta = now - rt.last_rain_event_ts
            total_s = int(delta.total_seconds())
            if total_s < 60:
                data[KEY_TIME_SINCE_RAIN] = "Just now"
            elif total_s < 3600:
                data[KEY_TIME_SINCE_RAIN] = f"{total_s // 60}m ago"
            elif total_s < 86400:
                h = total_s // 3600
                data[KEY_TIME_SINCE_RAIN] = f"{h}h ago"
            else:
                d = total_s // 86400
                data[KEY_TIME_SINCE_RAIN] = f"{d}d ago"
        else:
            data[KEY_TIME_SINCE_RAIN] = "No rain recorded"

        return rain_rate

    def _compute_condition(
        self,
        data: dict,
        tc: float | None,
        rh: float | None,
        wind_ms: float | None,
        gust_ms: float | None,
        rain_rate: float,
        dew_c: float | None,
        lux: float | None,
        uv: float | None,
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

    def _compute_rain_probability(self, data: dict, mslp: float, trend_3h: float, rh: float | None) -> None:
        """Local + API-blended rain probability."""
        wind_quad = data.get(KEY_WIND_QUADRANT, "N")
        if mslp and rh is not None:
            local_prob = calculate_rain_probability(
                mslp=float(mslp),
                pressure_trend=float(trend_3h),
                humidity=float(rh),
                wind_quadrant=str(wind_quad),
                climate_region=self.climate_region,
            )
            data[KEY_RAIN_PROBABILITY] = local_prob

            api_prob = None
            fc = getattr(self, "_forecast_cache", None)
            if fc and fc.get("daily"):
                pp = (fc["daily"][0] or {}).get("precip_prob")
                if pp is not None:
                    api_prob = int(pp)

            combined = combine_rain_probability(local_prob, api_prob, dt_util.now().hour)
            data[KEY_RAIN_PROBABILITY_COMBINED] = combined

    def _compute_activity_scores(
        self, data: dict, tc: float | None, rh: float | None, wind_ms: float | None, rain_rate: float, uv: float | None
    ) -> None:
        """Laundry, stargazing, fire risk, running activity scores."""
        feels_like = data.get(KEY_FEELS_LIKE_C)

        # Laundry drying
        if tc is not None and rh is not None and wind_ms is not None:
            rain_prob = data.get(KEY_RAIN_PROBABILITY_COMBINED)
            l_score = laundry_drying_score(
                temp_c=float(tc),
                humidity=float(rh),
                wind_speed_ms=float(wind_ms),
                uv_index=float(uv or 0),
                rain_rate_mmph=float(rain_rate),
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
                cloud_cover_pct=None,
                humidity=float(rh),
                rain_rate_mmph=float(rain_rate),
                moon_phase=moon_phase,
            )
            data[KEY_STARGAZE_SCORE] = sg_quality
            data["_moon_phase"] = moon_phase
            data["_moon_stargazing_impact"] = moon_stargazing_impact(moon_phase)

        # Fire Risk Score (renamed from Fire Weather Index)
        if tc is not None and rh is not None and wind_ms is not None:
            rain_24h = data.get(KEY_RAIN_ACCUM_24H, 0.0)
            frs = fire_risk_score(float(tc), float(rh), float(wind_ms), rain_24h)
            data[KEY_FIRE_RISK_SCORE] = frs
            data["_fire_danger_level"] = fire_danger_level(frs)
            data["_fire_rain_24h_mm"] = round(rain_24h, 1)

        # Running conditions
        if feels_like is not None and uv is not None:
            r_score = running_score(float(feels_like), float(uv))
            data[KEY_RUNNING_SCORE] = r_score
            data["_running_level"] = running_level(r_score)
            data["_running_recommendation"] = running_recommendation(float(feels_like), float(uv))

        # UV exposure details
        if uv is not None:
            data["_uv_recommendation"] = uv_recommendation(float(uv))
            data["_uv_burn_fair_skin"] = f"{uv_burn_time_minutes(float(uv), 2)} minutes"

    def _compute_degree_days(self, data: dict, now: Any) -> None:
        """Accumulate heating/cooling degree days for today.  (v0.5.0)

        HDD/CDD accumulate as degree-hours, reset at local midnight.
        The hourly rate sensors (hdd_rate, cdd_rate) always reflect the
        instantaneous contribution — useful for Riemann-sum utility meters.
        """
        if not self.degree_days_enabled:
            return
        temp_c: float | None = data.get(KEY_NORM_TEMP_C)
        if temp_c is None:
            return

        base = self.degree_day_base_c
        date_str = now.strftime("%Y-%m-%d")

        # Reset at midnight
        if date_str != self._degree_day_date:
            self._hdd_today = 0.0
            self._cdd_today = 0.0
            self._degree_day_date = date_str
            self._degree_day_last_ts = now

        # Accumulate degree-hours since last tick
        if self._degree_day_last_ts is not None:
            elapsed_h = (now - self._degree_day_last_ts).total_seconds() / 3600.0
            elapsed_h = min(elapsed_h, 1.5)  # cap at 1.5h to guard against cold-start spikes
            self._hdd_today += heating_degree_hours(temp_c, base) * elapsed_h
            self._cdd_today += cooling_degree_hours(temp_c, base) * elapsed_h
        self._degree_day_last_ts = now

        # Publish: convert degree-hours → degree-days (divide by 24)
        data[KEY_HDD_TODAY] = round(self._hdd_today / 24.0, 3)
        data[KEY_CDD_TODAY] = round(self._cdd_today / 24.0, 3)
        # Instantaneous rates in °C·h⁻¹ (for Riemann sum integrations)
        data[KEY_HDD_RATE] = round(heating_degree_hours(temp_c, base), 2)
        data[KEY_CDD_RATE] = round(cooling_degree_hours(temp_c, base), 2)

    def _compute_et0(self, data: dict, now: Any) -> None:
        """Calculate ET₀ (reference evapotranspiration) via Hargreaves-Samani.  (v0.6.0)

        Requires: today's temp high/low from 24h stats + location.
        Falls back gracefully if 24h stats aren't populated yet (first hour of runtime).
        """
        lat = self.forecast_lat
        if lat is None:
            return
        try:
            lat_f = float(lat)
        except (TypeError, ValueError):
            return

        t_max = data.get(KEY_TEMP_HIGH_24H)
        t_min = data.get(KEY_TEMP_LOW_24H)
        t_mean = data.get(KEY_NORM_TEMP_C)

        # Hargreaves needs valid t_max, t_min, t_mean
        if None in (t_max, t_min, t_mean):
            return
        if t_max <= t_min:  # pathological — sensor noise
            return

        doy = now.timetuple().tm_yday
        et0_daily = et0_hargreaves(
            t_max_c=float(t_max),
            t_min_c=float(t_min),
            t_mean_c=float(t_mean),
            lat_deg=lat_f,
            day_of_year=doy,
        )
        data[KEY_ET0_DAILY_MM] = et0_daily
        data[KEY_ET0_HOURLY_MM] = et0_hourly_estimate(et0_daily, now.hour)

    def _compute_health(self, data: dict, now: Any, missing: list, missing_entities: list) -> None:
        """Staleness, package status, data quality, configurable alerts."""
        stale = []
        for k, eid in self.sources.items():
            if not eid:
                continue
            # Only check frequently-updating core sensors for staleness.
            # Exclude rain_total (static when dry), UV (zero at night), battery
            # (slow-reporting), etc.
            if k not in STALENESS_CHECK_SOURCES:
                continue
            st = self.hass.states.get(eid)
            if st is None:
                continue
            if (now - st.last_updated).total_seconds() > self.staleness_s:
                stale.append(k)

        n_unavailable = len(missing_entities)
        n_healthy = len(self.sources) - n_unavailable - len(stale)

        station_health = (
            "Offline"
            if n_unavailable >= 3
            else "Online"
            if n_healthy >= len(REQUIRED_SOURCES)
            else "Degraded"
            if n_healthy >= 1
            else "Stale"
        )
        health_color = {
            "Online": "rgba(74,222,128,0.8)",
            "Degraded": "rgba(251,191,36,0.9)",
            "Stale": "rgba(249,115,22,0.9)",
            "Offline": "rgba(239,68,68,0.9)",
        }.get(station_health, "rgba(239,68,68,0.9)")

        data[KEY_HEALTH_DISPLAY] = station_health
        data["_health_color"] = health_color

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
        gust_thr = float(self.entry_options.get("thresh_wind_gust_ms", 17.0))
        rain_thr = float(self.entry_options.get("thresh_rain_rate_mmph", 20.0))
        freeze_thr = float(self.entry_options.get("thresh_freeze_c", 0.0))

        gust_ms = data.get(KEY_NORM_WIND_GUST_MS)
        rain_rate = data.get(KEY_RAIN_RATE_FILT, 0.0)
        tc = data.get(KEY_NORM_TEMP_C)

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
            alert_msg = f"Freeze risk: {tc:.1f}\u00b0C"

        data[KEY_ALERT_STATE] = alert_state
        data[KEY_ALERT_MESSAGE] = alert_msg

        # HA Repairs integration: create/clear issues for missing sources
        if HAS_REPAIRS:
            from .const import DOMAIN

            if missing_entities:
                ir.async_create_issue(
                    self.hass,
                    DOMAIN,
                    "missing_source_entities",
                    is_fixable=False,
                    severity=ir.IssueSeverity.ERROR,
                    translation_key="missing_source_entities",
                    translation_placeholders={"entities": ", ".join(missing_entities)},
                )
            else:
                ir.async_delete_issue(self.hass, DOMAIN, "missing_source_entities")

            if stale:
                ir.async_create_issue(
                    self.hass,
                    DOMAIN,
                    "stale_sensors",
                    is_fixable=False,
                    severity=ir.IssueSeverity.WARNING,
                    translation_key="stale_sensors",
                    translation_placeholders={"sensors": ", ".join(stale)},
                )
            else:
                ir.async_delete_issue(self.hass, DOMAIN, "stale_sensors")

            if self.runtime.forecast_consecutive_failures >= 3:
                ir.async_create_issue(
                    self.hass,
                    DOMAIN,
                    "forecast_api_failures",
                    is_fixable=False,
                    severity=ir.IssueSeverity.WARNING,
                    translation_key="forecast_api_failures",
                    translation_placeholders={"failures": str(self.runtime.forecast_consecutive_failures)},
                )
            else:
                ir.async_delete_issue(self.hass, DOMAIN, "forecast_api_failures")

    # ------------------------------------------------------------------
    # Main orchestrator
    # ------------------------------------------------------------------

    def _compute(self) -> dict[str, Any]:
        import time

        t0 = time.monotonic()
        data: dict[str, Any] = {}
        now = dt_util.utcnow()

        missing = [k for k in REQUIRED_SOURCES if not self.sources.get(k)]
        missing_entities = [
            k for k in REQUIRED_SOURCES if self.sources.get(k) and self.hass.states.get(self.sources[k]) is None
        ]

        tc, rh, pressure_hpa, wind_ms, gust_ms, wind_dir, rain_total_mm, lux, uv = self._compute_raw_readings(data, now)
        self._compute_derived_wind(data, now, wind_ms, gust_ms, wind_dir)
        rain_rate = self._compute_derived_precipitation(data, now, rain_total_mm)
        dew_c = self._compute_derived_temperature(data, now, tc, rh, wind_ms)
        trend_3h, mslp = self._compute_derived_pressure(data, now, tc, pressure_hpa, rh)
        self._compute_rain_probability(data, mslp, trend_3h, rh)

        flags = self._validate_readings(tc, rh, pressure_hpa, wind_ms, gust_ms, dew_c)
        data[KEY_SENSOR_QUALITY_FLAGS] = flags

        self._compute_condition(data, tc, rh, wind_ms, gust_ms, rain_rate, dew_c, lux, uv)
        self._compute_activity_scores(data, tc, rh, wind_ms, rain_rate, uv)
        self._compute_degree_days(data, now)
        self._compute_et0(data, now)
        self._compute_health(data, now, missing, missing_entities)

        if self.forecast_enabled:
            data[KEY_FORECAST] = self._get_cached_or_schedule_forecast(now)
        else:
            data[KEY_FORECAST] = None

        # Sea temperature: independent fetch schedule (every forecast interval)
        if self.sea_temp_enabled:
            self._schedule_sea_temp_fetch(now)

        fc = getattr(self, "_forecast_cache", None)
        if fc and fc.get("daily"):
            data[KEY_FORECAST_TILES] = self._build_forecast_tiles(fc["daily"])

        # Sea surface temperature
        if self.sea_temp_enabled and self._sea_temp_cache:
            data[KEY_SEA_SURFACE_TEMP] = self._sea_temp_cache.get("current_c")
            data["_sea_temp_comfort"] = self._sea_temp_cache.get("comfort")
            data["_sea_temp_hourly"] = self._sea_temp_cache.get("hourly")
            data["_sea_temp_grid_lat"] = self._sea_temp_cache.get("grid_lat")
            data["_sea_temp_grid_lon"] = self._sea_temp_cache.get("grid_lon")
            data["_sea_temp_disclaimer"] = self._sea_temp_cache.get("disclaimer")

        # METAR cross-validation (v0.5.0)
        if self.metar_enabled and self._metar_cache:
            m = self._metar_cache
            data[KEY_METAR_TEMP_C] = m.get("temp_c")
            data[KEY_METAR_PRESSURE_HPA] = m.get("pressure_hpa")
            data[KEY_METAR_WIND_MS] = m.get("wind_ms")
            data[KEY_METAR_WIND_DIR] = m.get("wind_dir_deg")
            data[KEY_METAR_STATION] = m.get("station_id")
            data[KEY_METAR_AGE_MIN] = m.get("age_min")
            # Compute deltas against local readings
            local_temp = data.get(KEY_NORM_TEMP_C)
            local_press = data.get(KEY_SEA_LEVEL_PRESSURE_HPA) or data.get(KEY_NORM_PRESSURE_HPA)
            metar_temp = m.get("temp_c")
            metar_press = m.get("pressure_hpa")
            delta_t = round(float(local_temp) - float(metar_temp), 1) if (local_temp is not None and metar_temp is not None) else None
            delta_p = round(float(local_press) - float(metar_press), 1) if (local_press is not None and metar_press is not None) else None
            data[KEY_METAR_DELTA_TEMP] = delta_t
            data[KEY_METAR_DELTA_PRESSURE] = delta_p
            data[KEY_METAR_VALIDATION] = metar_validation_label(delta_t, delta_p, m.get("age_min"))

        # Upload/export status (v0.6.0)
        data[KEY_CWOP_STATUS] = self._cwop_status
        data[KEY_WU_STATUS] = self._wu_status
        data[KEY_LAST_EXPORT_TIME] = (
            self._export_last_time.isoformat() if self._export_last_time else None
        )

        self.runtime.last_compute_ms = round((time.monotonic() - t0) * 1000, 1)
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
                "label": labels[i] if i < len(labels) else f"Day {i + 1}",
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
            # Exponential backoff: normal interval unless consecutive failures
            failures = self.runtime.forecast_consecutive_failures
            if failures > 0:
                backoff_s = min(
                    FORECAST_MAX_RETRY_S,
                    FORECAST_MIN_RETRY_S * (2 ** min(failures - 1, 6)),
                )
                min_interval_s = backoff_s
            else:
                min_interval_s = max(300, self.forecast_interval_min * 60)

            age_s = (now - last).total_seconds()
            if age_s < min_interval_s:
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

    def _schedule_sea_temp_fetch(self, now: Any) -> None:
        """Schedule a sea temp fetch if cache is stale or empty."""
        rt = self.runtime
        if getattr(rt, "sea_temp_inflight", False):
            return
        last = rt.last_sea_temp_fetch
        if last is not None and self._sea_temp_cache is not None:
            age_s = (now - last).total_seconds()
            # Reuse forecast interval; sea temp changes slowly
            min_interval_s = max(300, self.forecast_interval_min * 60)
            if age_s < min_interval_s:
                return
        rt.sea_temp_inflight = True
        self.hass.async_create_task(self._async_fetch_sea_temp())

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
            "windspeed_10m_max,windgusts_10m_max,weathercode,precipitation_probability_max"
            "&hourly=temperature_2m,apparent_temperature,dewpoint_2m,"
            "precipitation_probability,precipitation,"
            "weathercode,windspeed_10m,windgusts_10m,"
            "relativehumidity_2m,cloudcover"
            "&forecast_hours=24"
            "&timezone=auto"
        )
        from homeassistant.helpers.aiohttp_client import async_get_clientsession

        session = async_get_clientsession(self.hass)
        try:
            async with session.get(url, timeout=20) as resp:
                if resp.status != 200:
                    _LOGGER.warning("Open-Meteo returned HTTP %s", resp.status)
                    rt.forecast_consecutive_failures += 1
                    rt.forecast_inflight = False
                    return
                js = await resp.json()
        except Exception as exc:
            _LOGGER.warning("Open-Meteo fetch failed: %s", exc)
            rt.forecast_consecutive_failures += 1
            rt.forecast_inflight = False
            return

        daily = js.get("daily") or {}
        times = daily.get("time") or []
        tmax = daily.get("temperature_2m_max") or []
        tmin = daily.get("temperature_2m_min") or []
        pr = daily.get("precipitation_sum") or []
        ws = daily.get("windspeed_10m_max") or []
        wg = daily.get("windgusts_10m_max") or []
        wc = daily.get("weathercode") or []
        pp = daily.get("precipitation_probability_max") or []

        out = [
            {
                "date": times[i],
                "tmax_c": tmax[i] if i < len(tmax) else None,
                "tmin_c": tmin[i] if i < len(tmin) else None,
                "precip_mm": pr[i] if i < len(pr) else None,
                "wind_kmh": ws[i] if i < len(ws) else None,
                "gust_kmh": wg[i] if i < len(wg) else None,
                "weathercode": wc[i] if i < len(wc) else None,
                "precip_prob": pp[i] if i < len(pp) else None,
            }
            for i in range(min(len(times), 7))
        ]

        # Parse hourly data (next 24h)
        hourly = js.get("hourly") or {}
        h_times = hourly.get("time") or []
        h_temp = hourly.get("temperature_2m") or []
        h_app = hourly.get("apparent_temperature") or []
        h_dew = hourly.get("dewpoint_2m") or []
        h_pp = hourly.get("precipitation_probability") or []
        h_precip = hourly.get("precipitation") or []
        h_wc = hourly.get("weathercode") or []
        h_ws = hourly.get("windspeed_10m") or []
        h_wg = hourly.get("windgusts_10m") or []
        h_rh = hourly.get("relativehumidity_2m") or []
        h_cc = hourly.get("cloudcover") or []

        hourly_out = [
            {
                "datetime": h_times[i],
                "temp_c": h_temp[i] if i < len(h_temp) else None,
                "apparent_temp_c": h_app[i] if i < len(h_app) else None,
                "dewpoint_c": h_dew[i] if i < len(h_dew) else None,
                "precip_prob": h_pp[i] if i < len(h_pp) else None,
                "precip_mm": h_precip[i] if i < len(h_precip) else None,
                "weathercode": h_wc[i] if i < len(h_wc) else None,
                "wind_kmh": h_ws[i] if i < len(h_ws) else None,
                "gust_kmh": h_wg[i] if i < len(h_wg) else None,
                "humidity": h_rh[i] if i < len(h_rh) else None,
                "cloud_cover": h_cc[i] if i < len(h_cc) else None,
            }
            for i in range(min(len(h_times), 24))
        ]

        self._forecast_cache = {
            "daily": out,
            "hourly": hourly_out,
            "provider": "open-meteo",
            "lat": lat,
            "lon": lon,
        }
        self.runtime.last_forecast_fetch = dt_util.utcnow()
        rt.forecast_consecutive_failures = 0
        self.async_set_updated_data(self._compute())
        rt.forecast_inflight = False

    async def _async_fetch_sea_temp(self) -> None:
        """Fetch sea surface temperature from Open-Meteo Marine API."""
        rt = self.runtime
        try:
            lat = self.sea_temp_lat or float(self.hass.config.latitude)
            lon = self.sea_temp_lon or float(self.hass.config.longitude)

            url = (
                "https://marine-api.open-meteo.com/v1/marine"
                f"?latitude={lat}&longitude={lon}"
                "&current=sea_surface_temperature"
                "&hourly=sea_surface_temperature"
                "&forecast_hours=24"
                "&cell_selection=sea"
                "&timezone=auto"
            )
            from homeassistant.helpers.aiohttp_client import async_get_clientsession

            session = async_get_clientsession(self.hass)
            async with session.get(url, timeout=20) as resp:
                if resp.status != 200:
                    _LOGGER.warning("Open-Meteo Marine returned HTTP %s", resp.status)
                    return
                js = await resp.json()

            # Try current block first, fall back to first hourly value
            current = js.get("current") or {}
            sst_c = current.get("sea_surface_temperature")

            # Parse hourly SST
            hourly = js.get("hourly") or {}
            h_times = hourly.get("time") or []
            h_sst = hourly.get("sea_surface_temperature") or []
            hourly_out = [
                {"datetime": h_times[i], "sst_c": h_sst[i]}
                for i in range(min(len(h_times), 24))
                if i < len(h_sst) and h_sst[i] is not None
            ]

            # Fallback: if current block didn't have SST, use first hourly value
            if sst_c is None and h_sst:
                for v in h_sst:
                    if v is not None:
                        sst_c = v
                        break

            if sst_c is None:
                _LOGGER.warning("Open-Meteo Marine returned no SST data for %.4f,%.4f", lat, lon)
                return

            # Swimming comfort label
            if sst_c < 16:
                comfort = "Cold"
            elif sst_c < 20:
                comfort = "Cool"
            elif sst_c < 24:
                comfort = "Comfortable"
            elif sst_c < 28:
                comfort = "Warm"
            else:
                comfort = "Hot"

            self._sea_temp_cache = {
                "current_c": round(sst_c, 1) if sst_c is not None else None,
                "comfort": comfort,
                "hourly": hourly_out,
                "grid_lat": js.get("latitude"),
                "grid_lon": js.get("longitude"),
                "disclaimer": (
                    "Satellite-derived SST for nearest sea grid cell. "
                    "Coastal accuracy limited by grid resolution (~5 km). "
                    "Not a direct measurement."
                ),
            }
            rt.last_sea_temp_fetch = dt_util.utcnow()
            self.async_set_updated_data(self._compute())

        except Exception as exc:
            _LOGGER.warning("Open-Meteo Marine fetch failed: %s", exc)
        finally:
            rt.sea_temp_inflight = False

    # ------------------------------------------------------------------
    # METAR cross-validation  (v0.5.0)
    # ------------------------------------------------------------------

    async def _async_fetch_metar(self) -> None:
        """Fetch METAR from aviationweather.gov and update cache."""
        if not self.metar_icao:
            return
        icao = self.metar_icao.upper().strip()
        url = f"https://aviationweather.gov/api/data/metar?ids={icao}&format=json&taf=false"
        try:
            session = self.hass.helpers.aiohttp_client.async_get_clientsession()
            async with session.get(url, timeout=15) as resp:
                if resp.status != 200:
                    _LOGGER.warning("METAR fetch failed HTTP %d for %s", resp.status, icao)
                    return
                reports = await resp.json()
                if not reports:
                    _LOGGER.debug("No METAR reports found for %s", icao)
                    return
                self._metar_cache = parse_metar_json(reports[0])
                self._metar_last_fetch = dt_util.utcnow()
                _LOGGER.debug("METAR %s fetched: %s", icao, self._metar_cache.get("raw_text", ""))
                self.async_set_updated_data(self._compute())
        except Exception as exc:
            _LOGGER.warning("METAR fetch error for %s: %s", icao, exc)

    # ------------------------------------------------------------------
    # CWOP APRS-IS upload  (v0.6.0)
    # ------------------------------------------------------------------

    async def _async_upload_cwop(self) -> None:
        """Upload observation to CWOP via APRS-IS TCP."""
        import asyncio
        data = self.data
        if not data:
            return
        callsign = self.cwop_callsign.upper().strip()
        if not callsign:
            return

        lat = self.forecast_lat
        lon = self.forecast_lon
        if lat is None or lon is None:
            _LOGGER.warning("CWOP upload: lat/lon not configured")
            return

        # Format APRS packet
        def _aprs_lat(deg: float) -> str:
            d = abs(deg)
            dd = int(d)
            mm = (d - dd) * 60
            hem = "N" if deg >= 0 else "S"
            return f"{dd:02d}{mm:05.2f}{hem}"

        def _aprs_lon(deg: float) -> str:
            d = abs(deg)
            dd = int(d)
            mm = (d - dd) * 60
            hem = "E" if deg >= 0 else "W"
            return f"{dd:03d}{mm:05.2f}{hem}"

        now_utc = dt_util.utcnow()
        time_str = now_utc.strftime("%d%H%Mz")

        temp_c = data.get(KEY_NORM_TEMP_C)
        temp_f = round(float(temp_c) * 9 / 5 + 32) if temp_c is not None else 0
        wind_dir = data.get(KEY_NORM_WIND_DIR_DEG) or 0
        wind_ms = data.get(KEY_NORM_WIND_SPEED_MS) or 0
        wind_kt = round(float(wind_ms) * 1.94384)
        gust_ms = data.get(KEY_NORM_WIND_GUST_MS) or 0
        gust_kt = round(float(gust_ms) * 1.94384)
        humidity = data.get(KEY_NORM_HUMIDITY)
        h_str = f"h{round(float(humidity)):02d}" if humidity is not None else ""
        rain_1h = data.get(KEY_RAIN_ACCUM_1H) or 0
        rain_24h = data.get(KEY_RAIN_ACCUM_24H) or 0
        rain_1h_hun = round(float(rain_1h) * 3.93701)  # mm → 1/100 inch
        rain_24h_hun = round(float(rain_24h) * 3.93701)
        press = data.get(KEY_SEA_LEVEL_PRESSURE_HPA) or data.get(KEY_NORM_PRESSURE_HPA)
        b_str = f"b{round(float(press) * 10):05d}" if press is not None else ""

        aprs_lat = _aprs_lat(float(lat))
        aprs_lon = _aprs_lon(float(lon))
        packet = (
            f"{callsign}>APRS,TCPIP*:@{time_str}{aprs_lat}/{aprs_lon}_"
            f"{int(wind_dir):03d}/{wind_kt:03d}g{gust_kt:03d}"
            f"t{temp_f:03d}r{rain_1h_hun:03d}p{rain_24h_hun:03d}"
            f"{h_str}{b_str}ws_core"
        )

        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection("cwop.aprs.net", 14580), timeout=15
            )
            # Read banner
            await asyncio.wait_for(reader.read(512), timeout=5)
            # Login
            login_str = f"user {callsign} pass {self.cwop_passcode} vers ws_core 0.6.0\r\n"
            writer.write(login_str.encode())
            await writer.drain()
            await asyncio.sleep(1)
            # Send packet
            writer.write(f"{packet}\r\n".encode())
            await writer.drain()
            writer.close()
            self._cwop_last_upload = dt_util.utcnow()
            self._cwop_status = f"OK {self._cwop_last_upload.strftime('%H:%M')}"
            _LOGGER.debug("CWOP upload OK: %s", packet)
        except Exception as exc:
            self._cwop_status = f"Error: {exc}"
            _LOGGER.warning("CWOP upload failed: %s", exc)

    # ------------------------------------------------------------------
    # Weather Underground upload  (v0.6.0)
    # ------------------------------------------------------------------

    async def _async_upload_wunderground(self) -> None:
        """Upload observation to Weather Underground Personal Weather Station API."""
        data = self.data
        if not data or not self.wu_station_id or not self.wu_api_key:
            return

        now_utc = dt_util.utcnow()
        date_utc = now_utc.strftime("%Y-%m-%d %H:%M:%S")

        temp_c = data.get(KEY_NORM_TEMP_C)
        dew_c = data.get(KEY_DEW_POINT_C)
        humidity = data.get(KEY_NORM_HUMIDITY)
        press = data.get(KEY_SEA_LEVEL_PRESSURE_HPA) or data.get(KEY_NORM_PRESSURE_HPA)
        wind_dir = data.get(KEY_NORM_WIND_DIR_DEG) or 0
        wind_ms = data.get(KEY_NORM_WIND_SPEED_MS) or 0
        gust_ms = data.get(KEY_NORM_WIND_GUST_MS) or 0
        rain_1h = data.get(KEY_RAIN_ACCUM_1H) or 0
        rain_24h = data.get(KEY_RAIN_ACCUM_24H) or 0

        def _c_to_f(c: float) -> float:
            return round(c * 9 / 5 + 32, 1)

        def _ms_to_mph(ms: float) -> float:
            return round(float(ms) * 2.23694, 1)

        def _mm_to_in(mm: float) -> float:
            return round(float(mm) / 25.4, 3)

        def _hpa_to_inhg(hpa: float) -> float:
            return round(float(hpa) / 33.8639, 2)

        params = {
            "ID": self.wu_station_id,
            "PASSWORD": self.wu_api_key,
            "dateutc": date_utc,
            "winddir": int(wind_dir),
            "windspeedmph": _ms_to_mph(wind_ms),
            "windgustmph": _ms_to_mph(gust_ms),
            "rainin": _mm_to_in(rain_1h),
            "dailyrainin": _mm_to_in(rain_24h),
            "action": "updateraw",
            "softwaretype": "ws_core_0.6.0",
        }
        if temp_c is not None:
            params["tempf"] = _c_to_f(float(temp_c))
        if dew_c is not None:
            params["dewptf"] = _c_to_f(float(dew_c))
        if humidity is not None:
            params["humidity"] = int(float(humidity))
        if press is not None:
            params["baromin"] = _hpa_to_inhg(float(press))

        url = "https://weatherstation.wunderground.com/weatherstation/updateweatherstation.php"
        try:
            session = self.hass.helpers.aiohttp_client.async_get_clientsession()
            async with session.get(url, params=params, timeout=15) as resp:
                body = await resp.text()
                if resp.status == 200 and "success" in body.lower():
                    self._wu_last_upload = now_utc
                    self._wu_status = f"OK {self._wu_last_upload.strftime('%H:%M')}"
                    _LOGGER.debug("WUnderground upload OK")
                else:
                    self._wu_status = f"Error HTTP {resp.status}: {body[:60]}"
                    _LOGGER.warning("WUnderground upload failed HTTP %d: %s", resp.status, body[:120])
        except Exception as exc:
            self._wu_status = f"Error: {exc}"
            _LOGGER.warning("WUnderground upload error: %s", exc)

    # ------------------------------------------------------------------
    # CSV / JSON export  (v0.6.0)
    # ------------------------------------------------------------------

    async def _async_export_data(self) -> None:
        """Write current observations to CSV and/or JSON on disk."""
        import asyncio
        import csv
        import json
        import os

        data = self.data
        if not data:
            return

        def _do_export() -> None:
            now = dt_util.utcnow()
            row = {
                "timestamp_utc": now.isoformat(),
                "temperature_c": data.get(KEY_NORM_TEMP_C),
                "humidity_pct": data.get(KEY_NORM_HUMIDITY),
                "dew_point_c": data.get(KEY_DEW_POINT_C),
                "wet_bulb_c": data.get(KEY_WET_BULB_C),
                "frost_point_c": data.get(KEY_FROST_POINT_C),
                "feels_like_c": data.get(KEY_FEELS_LIKE_C),
                "station_pressure_hpa": data.get(KEY_NORM_PRESSURE_HPA),
                "sea_level_pressure_hpa": data.get(KEY_SEA_LEVEL_PRESSURE_HPA),
                "pressure_trend_hpah": data.get(KEY_PRESSURE_TREND_HPAH),
                "wind_speed_ms": data.get(KEY_NORM_WIND_SPEED_MS),
                "wind_gust_ms": data.get(KEY_NORM_WIND_GUST_MS),
                "wind_direction_deg": data.get(KEY_NORM_WIND_DIR_DEG),
                "rain_total_mm": data.get(KEY_NORM_RAIN_TOTAL_MM),
                "rain_rate_mmph": data.get(KEY_RAIN_RATE_FILT),
                "rain_1h_mm": data.get(KEY_RAIN_ACCUM_1H),
                "rain_24h_mm": data.get(KEY_RAIN_ACCUM_24H),
                "illuminance_lx": data.get(KEY_LUX),
                "uv_index": data.get(KEY_UV),
                "hdd_today": data.get(KEY_HDD_TODAY),
                "cdd_today": data.get(KEY_CDD_TODAY),
                "et0_daily_mm": data.get(KEY_ET0_DAILY_MM),
                "current_condition": data.get(KEY_CURRENT_CONDITION),
                "zambretti_forecast": data.get(KEY_ZAMBRETTI_FORECAST),
                "rain_probability_combined": data.get(KEY_RAIN_PROBABILITY_COMBINED),
            }

            fmt = self.export_format.lower()
            export_dir = self.export_path
            os.makedirs(export_dir, exist_ok=True)
            date_str = now.strftime("%Y%m%d")

            if fmt in ("csv", "both"):
                csv_path = os.path.join(export_dir, f"ws_core_{date_str}.csv")
                write_header = not os.path.exists(csv_path)
                with open(csv_path, "a", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=list(row.keys()))
                    if write_header:
                        writer.writeheader()
                    writer.writerow(row)

            if fmt in ("json", "both"):
                json_path = os.path.join(export_dir, f"ws_core_{date_str}.json")
                existing = []
                if os.path.exists(json_path):
                    try:
                        with open(json_path) as f:
                            existing = json.load(f)
                    except Exception:
                        existing = []
                existing.append(row)
                with open(json_path, "w") as f:
                    json.dump(existing, f, indent=2)

        try:
            await asyncio.get_event_loop().run_in_executor(None, _do_export)
            self._export_last_time = dt_util.utcnow()
            _LOGGER.debug("ws_core data exported to %s", self.export_path)
        except Exception as exc:
            _LOGGER.warning("ws_core export failed: %s", exc)
