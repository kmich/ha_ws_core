"""Coordinator for WS Station."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import timedelta
import math
import logging
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_interval
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    CONF_ELEVATION_M,
    CONF_FORECAST_ENABLED,
    CONF_FORECAST_INTERVAL_MIN,
    CONF_FORECAST_LAT,
    CONF_FORECAST_LON,
    CONF_SOURCES,
    CONF_STALENESS_S,
    CONF_UNITS_MODE,
    CONF_THRESH_FREEZE_C,
    CONF_THRESH_RAIN_RATE_MMPH,
    CONF_THRESH_WIND_GUST_MS,
    CONF_RAIN_FILTER_ALPHA,
    CONF_PRESSURE_TREND_WINDOW_H,
    CONF_ENABLE_ACTIVITY_SCORES,
    CONF_RAIN_PENALTY_LIGHT_MMPH,
    CONF_RAIN_PENALTY_HEAVY_MMPH,
    DEFAULT_FORECAST_INTERVAL_MIN,
    DEFAULT_STALENESS_S,
    DEFAULT_THRESH_FREEZE_C,
    DEFAULT_THRESH_RAIN_RATE_MMPH,
    DEFAULT_THRESH_WIND_GUST_MS,
    DEFAULT_RAIN_FILTER_ALPHA,
    DEFAULT_PRESSURE_TREND_WINDOW_H,
    DEFAULT_ENABLE_ACTIVITY_SCORES,
    DEFAULT_RAIN_PENALTY_LIGHT_MMPH,
    DEFAULT_RAIN_PENALTY_HEAVY_MMPH,
    KEY_ALERT_MESSAGE,
    KEY_ALERT_STATE,
    KEY_BATTERY_PCT,
    KEY_DATA_QUALITY,
    KEY_DEW_POINT_C,
    KEY_FORECAST,
    KEY_LAUNDRY_SCORE,
    KEY_STARGAZE_SCORE,
    KEY_FIRE_SCORE,
    KEY_PRESSURE_TREND_HPAH,
    KEY_PRESSURE_CHANGE_WINDOW_HPA,
    KEY_LUX,
    KEY_NORM_HUMIDITY,
    KEY_NORM_PRESSURE_HPA,
    KEY_SEA_LEVEL_PRESSURE_HPA,
    KEY_NORM_RAIN_TOTAL_MM,
    KEY_NORM_TEMP_C,
    KEY_NORM_WIND_DIR_DEG,
    KEY_NORM_WIND_GUST_MS,
    KEY_NORM_WIND_SPEED_MS,
    KEY_PACKAGE_OK,
    KEY_PACKAGE_STATUS,
    KEY_RAIN_RATE_FILT,
    KEY_RAIN_RATE_RAW,
    KEY_UV,
    REQUIRED_SOURCES,
    OPTIONAL_SOURCES,
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
    last_rain_total_mm: float | None = None
    last_rain_ts: Any | None = None
    last_rain_rate_filt: float = 0.0

    pressure_samples: list[tuple[Any, float]] = field(default_factory=list)

    last_forecast_fetch: Any | None = None
    last_forecast_success: Any | None = None
    last_forecast_error: str | None = None
    last_forecast_http_status: int | None = None


class WSStationCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Keeps derived values up to date."""

    def __init__(self, hass: HomeAssistant, entry_data: dict[str, Any], entry_options: dict[str, Any] | None = None):
        self.hass = hass
        self.entry_data = entry_data
        self.entry_options = entry_options or {}
        self.runtime = WSStationRuntime()

        self.sources = dict(entry_data.get(CONF_SOURCES, {}))

        # Basic settings
        self.units_mode = (self.entry_options.get(CONF_UNITS_MODE) or entry_data.get(CONF_UNITS_MODE) or "auto")
        self.elevation_m = float(self.entry_options.get(CONF_ELEVATION_M, entry_data.get(CONF_ELEVATION_M, 0.0)))
        self.staleness_s = int(self.entry_options.get(CONF_STALENESS_S, entry_data.get(CONF_STALENESS_S, DEFAULT_STALENESS_S)))

        # Alert/heuristic settings (stored in canonical metric)
        self.gust_thr_ms = float(self.entry_options.get(CONF_THRESH_WIND_GUST_MS, DEFAULT_THRESH_WIND_GUST_MS))
        self.rain_thr_mmph = float(self.entry_options.get(CONF_THRESH_RAIN_RATE_MMPH, DEFAULT_THRESH_RAIN_RATE_MMPH))
        self.freeze_thr_c = float(self.entry_options.get(CONF_THRESH_FREEZE_C, DEFAULT_THRESH_FREEZE_C))
        self.rain_filter_alpha = float(self.entry_options.get(CONF_RAIN_FILTER_ALPHA, DEFAULT_RAIN_FILTER_ALPHA))
        self.pressure_trend_window_h = int(self.entry_options.get(CONF_PRESSURE_TREND_WINDOW_H, DEFAULT_PRESSURE_TREND_WINDOW_H))
        self.enable_activity_scores = bool(self.entry_options.get(CONF_ENABLE_ACTIVITY_SCORES, DEFAULT_ENABLE_ACTIVITY_SCORES))
        self.rain_penalty_light_mmph = float(self.entry_options.get(CONF_RAIN_PENALTY_LIGHT_MMPH, DEFAULT_RAIN_PENALTY_LIGHT_MMPH))
        self.rain_penalty_heavy_mmph = float(self.entry_options.get(CONF_RAIN_PENALTY_HEAVY_MMPH, DEFAULT_RAIN_PENALTY_HEAVY_MMPH))

        # Forecast
        self.forecast_enabled = bool(self.entry_options.get(CONF_FORECAST_ENABLED, entry_data.get(CONF_FORECAST_ENABLED, True)))
        self.forecast_lat = self.entry_options.get(CONF_FORECAST_LAT, entry_data.get(CONF_FORECAST_LAT))
        self.forecast_lon = self.entry_options.get(CONF_FORECAST_LON, entry_data.get(CONF_FORECAST_LON))
        self.forecast_interval_min = int(self.entry_options.get(CONF_FORECAST_INTERVAL_MIN, entry_data.get(CONF_FORECAST_INTERVAL_MIN, DEFAULT_FORECAST_INTERVAL_MIN)))

        self._forecast_lock = asyncio.Lock()
        self._forecast_task: asyncio.Task | None = None
        self._forecast_cache: dict[str, Any] | None = None

        super().__init__(
            hass,
            logger=_LOGGER,
            name="WS Station",
            update_interval=timedelta(seconds=60),
        )

        self._unsubs: list[callable] = []

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

    @staticmethod
    def _clean_uom(unit: str) -> str:
        return (unit or "").strip().lower().replace(" ", "")

    def _compute(self) -> dict[str, Any]:
        data: dict[str, Any] = {}
        now = dt_util.utcnow()

        # Validate required sources
        missing = [k for k in REQUIRED_SOURCES if not self.sources.get(k)]
        missing_entities = [k for k in REQUIRED_SOURCES if self.sources.get(k) and self.hass.states.get(self.sources[k]) is None]

        def num_state(eid: str | None) -> float | None:
            if not eid:
                return None
            st = self.hass.states.get(eid)
            if st is None:
                return None
            if st.state in ("unknown", "unavailable", None):
                return None
            try:
                v = float(st.state)
            except Exception:
                return None
            if math.isnan(v) or math.isinf(v):
                return None
            return v

        def uom(eid: str | None) -> str:
            if not eid:
                return ""
            st = self.hass.states.get(eid)
            if st is None:
                return ""
            return str(st.attributes.get("unit_of_measurement") or "")

        # Unit conversions to canonical internal. Return None if input is not meaningful.
        def to_celsius(v: float, unit: str) -> float | None:
            u = self._clean_uom(unit)
            if u in ("°f", "f", "degf", "fahrenheit"):
                return (v - 32.0) * 5.0 / 9.0
            if u in ("°c", "c", "degc", "celsius", ""):
                return v
            if u in ("k", "kelvin"):
                if v < 0:
                    return None
                return v - 273.15
            # fallback: detect °f-like strings
            if "fahrenheit" in u or u.endswith("°f") or u.endswith("degf"):
                return (v - 32.0) * 5.0 / 9.0
            if "kelvin" in u:
                if v < 0:
                    return None
                return v - 273.15
            return v

        def to_ms(v: float, unit: str) -> float:
            u = self._clean_uom(unit)
            if u in ("m/s", "mps", "ms", "meterpersecond", "metrepersecond") or "m/s" in u:
                return v
            if u in ("km/h", "kmh", "kph"):
                return v / 3.6
            if u in ("mph",):
                return v * 0.44704
            if u in ("kn", "knot", "knots"):
                return v * 0.514444
            return v

        def to_hpa(v: float, unit: str) -> float:
            u = self._clean_uom(unit)
            if u in ("hpa", "mbar", "mb"):
                return v
            if u == "pa":
                return v / 100.0
            if u == "kpa":
                return v * 10.0
            if u in ("inhg",):
                return v * 33.8638866667
            if u in ("mmhg", "torr"):
                return v * 1.33322
            return v

        def to_mm(v: float, unit: str) -> float:
            u = self._clean_uom(unit)
            if u in ("mm", ""):
                return v
            if u in ("cm",):
                return v * 10.0
            if u in ("m",):
                return v * 1000.0
            if u in ("in", "inch", "inches"):
                return v * 25.4
            return v

        # Canonical sensors
        t_raw = num_state(self.sources.get(SRC_TEMP))
        h_raw = num_state(self.sources.get(SRC_HUM))
        p_raw = num_state(self.sources.get(SRC_PRESS))
        ws_raw = num_state(self.sources.get(SRC_WIND))
        wg_raw = num_state(self.sources.get(SRC_GUST))
        wd_raw = num_state(self.sources.get(SRC_WIND_DIR))
        rtot_raw = num_state(self.sources.get(SRC_RAIN_TOTAL))

        if t_raw is not None:
            tc = to_celsius(t_raw, uom(self.sources.get(SRC_TEMP)))
            if tc is not None:
                data[KEY_NORM_TEMP_C] = round(tc, 2)
        if h_raw is not None:
            data[KEY_NORM_HUMIDITY] = round(h_raw, 1)
        if p_raw is not None:
            data[KEY_NORM_PRESSURE_HPA] = round(to_hpa(p_raw, uom(self.sources.get(SRC_PRESS))), 1)
        if ws_raw is not None:
            data[KEY_NORM_WIND_SPEED_MS] = round(to_ms(ws_raw, uom(self.sources.get(SRC_WIND))), 2)
        if wg_raw is not None:
            data[KEY_NORM_WIND_GUST_MS] = round(to_ms(wg_raw, uom(self.sources.get(SRC_GUST))), 2)
        if wd_raw is not None:
            data[KEY_NORM_WIND_DIR_DEG] = round(float(wd_raw), 1)
        if rtot_raw is not None:
            data[KEY_NORM_RAIN_TOTAL_MM] = round(to_mm(rtot_raw, uom(self.sources.get(SRC_RAIN_TOTAL))), 2)

        # Optional direct sensors
        lux_raw = num_state(self.sources.get(SRC_LUX))
        if lux_raw is not None:
            data[KEY_LUX] = round(lux_raw, 1)
        uv_raw = num_state(self.sources.get(SRC_UV))
        if uv_raw is not None:
            data[KEY_UV] = round(uv_raw, 2)
        bat_raw = num_state(self.sources.get(SRC_BATTERY))
        if bat_raw is not None:
            data[KEY_BATTERY_PCT] = round(bat_raw, 0)

        # Dew point: use source if configured, else compute
        dp_raw = num_state(self.sources.get(SRC_DEW_POINT))
        if dp_raw is not None:
            dpc = to_celsius(dp_raw, uom(self.sources.get(SRC_DEW_POINT)))
            if dpc is not None:
                data[KEY_DEW_POINT_C] = round(dpc, 2)
        else:
            if data.get(KEY_NORM_TEMP_C) is not None and data.get(KEY_NORM_HUMIDITY) is not None:
                tc = float(data[KEY_NORM_TEMP_C])
                rh = max(1.0, min(100.0, float(data[KEY_NORM_HUMIDITY])))
                a, b = 17.62, 243.12
                gamma = (a * tc) / (b + tc) + math.log(rh / 100.0)
                dp = (b * gamma) / (a - gamma)
                data[KEY_DEW_POINT_C] = round(dp, 2)

        # Sea-level pressure reduction (approx.)
        station_p = data.get(KEY_NORM_PRESSURE_HPA)
        if station_p is not None and self.elevation_m:
            # Hypsometric approximation using station temperature if available, else 15°C.
            tc = float(data.get(KEY_NORM_TEMP_C, 15.0))
            tk = tc + 273.15
            if tk > 1.0:
                g = 9.80665
                R = 287.05
                z = float(self.elevation_m)
                p0 = float(station_p) * math.exp((g * z) / (R * tk))
                data[KEY_SEA_LEVEL_PRESSURE_HPA] = round(p0, 1)

        # Pressure trend: compute rate over a rolling window (default 3h) + change over window (hPa)
        pressure_hpa = data.get(KEY_NORM_PRESSURE_HPA)
        if pressure_hpa is not None:
            # Sample no more often than every ~2 minutes to limit buffer growth.
            samples = self.runtime.pressure_samples
            if not samples or (now - samples[-1][0]).total_seconds() >= 120:
                samples.append((now, float(pressure_hpa)))

            window_h = max(1, int(self.pressure_trend_window_h or 3))
            cutoff = now - timedelta(hours=window_h) - timedelta(minutes=10)
            # purge old
            while samples and samples[0][0] < cutoff:
                samples.pop(0)

            target = now - timedelta(hours=window_h)
            # Find sample closest to target time
            best = None
            best_dt = None
            for ts, pv in samples:
                dts = abs((ts - target).total_seconds())
                if best is None or dts < best_dt:
                    best = (ts, pv)
                    best_dt = dts

            if best is not None and best_dt is not None:
                delta = float(pressure_hpa) - float(best[1])
                data[KEY_PRESSURE_CHANGE_WINDOW_HPA] = round(delta, 2)
                data[KEY_PRESSURE_TREND_HPAH] = round(delta / float(window_h), 2)

        # Activity heuristics (0..100). These are optional and disabled by default.
        if self.enable_activity_scores:
            tc = data.get(KEY_NORM_TEMP_C)
            rh = data.get(KEY_NORM_HUMIDITY)
            wind_ms = data.get(KEY_NORM_WIND_SPEED_MS)
            lux = data.get(KEY_LUX)

            # Laundry drying score
            if tc is not None and rh is not None and wind_ms is not None:
                score = 100.0
                score -= max(0.0, min(60.0, (float(rh) - 40.0) / 60.0 * 60.0))
                score += max(0.0, min(25.0, float(wind_ms) / 8.0 * 25.0))
                score += max(0.0, min(15.0, float(tc) / 25.0 * 15.0))
                data[KEY_LAUNDRY_SCORE] = int(max(0.0, min(100.0, score)))

            # Stargazing quality (requires illuminance)
            if lux is not None and rh is not None:
                dark = 1.0 - (math.log10(float(lux) + 1.0) / math.log10(1000.0))
                dark = max(0.0, min(1.0, dark))
                score = 70.0 * dark
                score -= max(0.0, min(30.0, (float(rh) - 60.0) / 40.0 * 30.0))
                if wind_ms is not None:
                    score -= max(0.0, min(15.0, (float(wind_ms) - 6.0) / 8.0 * 15.0))
                data[KEY_STARGAZE_SCORE] = int(max(0.0, min(100.0, score)))

            # Fire "dryness" proxy score (simple heuristic, not FWI)
            if tc is not None and rh is not None and wind_ms is not None:
                score = 0.0
                score += max(0.0, min(40.0, (float(tc) - 20.0) / 20.0 * 40.0))
                score += max(0.0, min(40.0, (60.0 - float(rh)) / 50.0 * 40.0))
                score += max(0.0, min(20.0, float(wind_ms) / 12.0 * 20.0))
                data[KEY_FIRE_SCORE] = int(max(0.0, min(100.0, score)))

        # Rain rate from cumulative total (mm)
        rain_total_mm = data.get(KEY_NORM_RAIN_TOTAL_MM)
        if rain_total_mm is not None:
            last_v = self.runtime.last_rain_total_mm
            last_ts = self.runtime.last_rain_ts
            if last_v is None or last_ts is None:
                self.runtime.last_rain_total_mm = float(rain_total_mm)
                self.runtime.last_rain_ts = now
                data[KEY_RAIN_RATE_RAW] = 0.0
                data[KEY_RAIN_RATE_FILT] = round(self.runtime.last_rain_rate_filt, 2)
            else:
                dv = float(rain_total_mm) - float(last_v)
                dt_h = max(1e-6, (now - last_ts).total_seconds() / 3600.0)

                # Handle counter reset or negative deltas
                if dv < -0.1:
                    dv = 0.0
                    self.runtime.last_rain_total_mm = float(rain_total_mm)
                    self.runtime.last_rain_ts = now

                raw = max(0.0, dv / dt_h)
                raw = min(raw, 500.0)  # safety cap

                # EMA filter (alpha configurable)
                alpha = float(self.rain_filter_alpha)
                alpha = max(0.05, min(1.0, alpha))
                filt = alpha * raw + (1 - alpha) * float(self.runtime.last_rain_rate_filt)
                self.runtime.last_rain_rate_filt = float(filt)

                data[KEY_RAIN_RATE_RAW] = round(raw, 2)
                data[KEY_RAIN_RATE_FILT] = round(filt, 2)

                # update baseline
                self.runtime.last_rain_total_mm = float(rain_total_mm)
                self.runtime.last_rain_ts = now

                # Apply rain penalty to activity proxies (tapered, not hard-zero)
                if self.enable_activity_scores:
                    rr = float(data.get(KEY_RAIN_RATE_FILT) or data.get(KEY_RAIN_RATE_RAW) or 0.0)
                    light = max(0.0, float(self.rain_penalty_light_mmph))
                    heavy = max(light + 0.1, float(self.rain_penalty_heavy_mmph))
                    if rr > light:
                        if rr >= heavy:
                            factor = 0.0
                        else:
                            factor = 1.0 - ((rr - light) / (heavy - light))
                        factor = max(0.0, min(1.0, factor))

                        if KEY_LAUNDRY_SCORE in data:
                            data[KEY_LAUNDRY_SCORE] = int(round(float(data[KEY_LAUNDRY_SCORE]) * factor))
                        if KEY_STARGAZE_SCORE in data:
                            data[KEY_STARGAZE_SCORE] = int(round(float(data[KEY_STARGAZE_SCORE]) * factor))

                        # Fire proxy: rain reduces risk strongly
                        if KEY_FIRE_SCORE in data:
                            data[KEY_FIRE_SCORE] = int(round(float(data[KEY_FIRE_SCORE]) * factor))

        # Package status (missing, stale)
        stale: list[str] = []
        for k, eid in self.sources.items():
            if not eid:
                continue
            st = self.hass.states.get(eid)
            if st is None:
                continue
            age = (now - st.last_updated).total_seconds()
            if age > self.staleness_s:
                stale.append(k)

        required_stale = [k for k in stale if k in REQUIRED_SOURCES]
        optional_stale = [k for k in stale if k in OPTIONAL_SOURCES]

        ok = (not missing) and (not missing_entities)
        status_parts: list[str] = []
        if missing:
            status_parts.append("Missing mappings: " + ", ".join(missing))
        if missing_entities:
            status_parts.append("Entities not found: " + ", ".join(missing_entities))
        if required_stale:
            status_parts.append("Stale (required): " + ", ".join(required_stale))
        if optional_stale:
            status_parts.append("Stale (optional): " + ", ".join(optional_stale))

        data[KEY_PACKAGE_OK] = bool(ok)
        data[KEY_PACKAGE_STATUS] = "OK" if not status_parts else " | ".join(status_parts)

        # Data quality banner: clear state, actionable messaging
        if missing or missing_entities:
            dq = "ERROR: Weather station not configured (missing required sources)"
        elif required_stale:
            dq = f"WARN: Stale required data from {', '.join(required_stale)}"
        elif optional_stale:
            dq = f"WARN: Stale optional data from {', '.join(optional_stale)}"
        else:
            dq = "OK"
        data[KEY_DATA_QUALITY] = dq

        # Alerts (simple, local thresholds in canonical metric)
        gust_ms = data.get(KEY_NORM_WIND_GUST_MS)
        rain_rate = data.get(KEY_RAIN_RATE_FILT)
        temp_c = data.get(KEY_NORM_TEMP_C)

        gust_thr = float(self.gust_thr_ms)
        rain_thr = float(self.rain_thr_mmph)
        freeze_thr = float(self.freeze_thr_c)

        state = "clear"
        msg = "All clear"
        if gust_ms is not None and float(gust_ms) >= gust_thr:
            state = "warning"
            msg = f"High wind gusts: {float(gust_ms):.1f} m/s (threshold {gust_thr:.1f} m/s)"
        if rain_rate is not None and float(rain_rate) >= rain_thr:
            state = "warning"
            msg = f"Heavy rain rate: {float(rain_rate):.1f} mm/h (threshold {rain_thr:.1f} mm/h)"
        if temp_c is not None and float(temp_c) <= freeze_thr:
            state = "advisory" if state == "clear" else state
            msg = f"Freeze risk: {float(temp_c):.1f} °C (threshold {freeze_thr:.1f} °C)"

        data[KEY_ALERT_STATE] = state
        data[KEY_ALERT_MESSAGE] = msg

        # Forecast
        if self.forecast_enabled:
            data[KEY_FORECAST] = self._get_cached_or_schedule_forecast(now)
        else:
            data[KEY_FORECAST] = None

        return data

    def _forecast_meta(self) -> dict[str, Any]:
        return {
            "provider": "open-meteo",
            "last_success": self.runtime.last_forecast_success.isoformat() if self.runtime.last_forecast_success else None,
            "last_error": self.runtime.last_forecast_error,
            "http_status": self.runtime.last_forecast_http_status,
            "lat": self.forecast_lat,
            "lon": self.forecast_lon,
        }

    def _get_cached_or_schedule_forecast(self, now) -> dict[str, Any] | None:
        cached = self._forecast_cache
        last = self.runtime.last_forecast_fetch
        if cached is not None and last is not None:
            age_min = (now - last).total_seconds() / 60.0
            if age_min < max(5, self.forecast_interval_min):
                # ensure meta is updated
                cached = dict(cached)
                cached.update(self._forecast_meta())
                return cached

        # schedule at most one inflight task
        if self._forecast_task is None or self._forecast_task.done():
            try:
                self._forecast_task = self.hass.async_create_task(self._async_fetch_forecast())
            except Exception:
                pass

        if cached is not None:
            cached = dict(cached)
            cached.update(self._forecast_meta())
            return cached

        # No cached data yet; still expose meta so users can see failures
        meta = self._forecast_meta()
        return meta

    async def _async_fetch_forecast(self) -> None:
        if not self.forecast_enabled:
            return

        async with self._forecast_lock:
            now = dt_util.utcnow()
            # Respect refresh interval even inside lock
            last = self.runtime.last_forecast_fetch
            if last is not None:
                age_min = (now - last).total_seconds() / 60.0
                if age_min < max(5, self.forecast_interval_min):
                    return

            lat = self.forecast_lat
            lon = self.forecast_lon
            if lat is None or lon is None:
                lat = float(self.hass.config.latitude)
                lon = float(self.hass.config.longitude)

            url = (
                "https://api.open-meteo.com/v1/forecast"
                f"?latitude={lat}&longitude={lon}"
                "&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,windspeed_10m_max,weathercode"
                "&timezone=auto"
            )

            from homeassistant.helpers.aiohttp_client import async_get_clientsession

            session = async_get_clientsession(self.hass)

            try:
                async with session.get(url, timeout=20) as resp:
                    self.runtime.last_forecast_http_status = int(resp.status)
                    if resp.status != 200:
                        self.runtime.last_forecast_error = f"HTTP {resp.status}"
                        self.runtime.last_forecast_fetch = dt_util.utcnow()
                        self.async_set_updated_data(self._compute())
                        return
                    js = await resp.json()
            except Exception as e:
                self.runtime.last_forecast_error = f"{type(e).__name__}: {e}"
                self.runtime.last_forecast_fetch = dt_util.utcnow()
                self.async_set_updated_data(self._compute())
                return

            daily = js.get("daily") or {}
            times = daily.get("time") or []
            tmax = daily.get("temperature_2m_max") or []
            tmin = daily.get("temperature_2m_min") or []
            pr = daily.get("precipitation_sum") or []
            ws = daily.get("windspeed_10m_max") or []
            wc = daily.get("weathercode") or []

            out: list[dict[str, Any]] = []
            for i in range(min(len(times), 7)):
                out.append(
                    {
                        "date": times[i],
                        "tmax_c": tmax[i] if i < len(tmax) else None,
                        "tmin_c": tmin[i] if i < len(tmin) else None,
                        "precip_mm": pr[i] if i < len(pr) else None,
                        "wind_kmh": ws[i] if i < len(ws) else None,
                        "weathercode": wc[i] if i < len(wc) else None,
                    }
                )

            self._forecast_cache = {"daily": out}
            self.runtime.last_forecast_fetch = dt_util.utcnow()
            self.runtime.last_forecast_success = dt_util.utcnow()
            self.runtime.last_forecast_error = None

            # push update
            self.async_set_updated_data(self._compute())
