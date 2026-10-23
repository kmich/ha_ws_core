"""Coordinator-side wiring for Pattern Forecast.

``pattern_forecast.py`` is a pure engine (numbers in, numbers out). This module
is the thin Home Assistant layer around it: it reads the coordinator's already
normalized readings, feeds the engine on the 60 s sample tick, issues forecasts
on the 15-minute marks, loads/saves the engine's own Store and turns engine
output into the dictionaries the sensors read.

Local-first: the only inputs are the configured source sensors. The single
exception is the labelled Blitzortung opt-in for the storm target
(``pattern_sources.storm_source``); nothing here reads forecast caches, nowcast
data or any other network-fed value.
"""

from __future__ import annotations

import logging
import math
from datetime import UTC, datetime
from functools import partial
from typing import TYPE_CHECKING, Any

from homeassistant.util import dt as dt_util

from .algorithms import (
    calculate_clearness_index,
    calculate_dew_point,
    calculate_sea_level_pressure,
    night_fraction_ahead,
)
from .const import (
    CONF_CAL_HUMIDITY,
    CONF_CAL_PRESSURE_HPA,
    CONF_CAL_TEMP_C,
    CONF_CAL_WIND_MS,
    CONF_LIGHTNING_PROXIMITY_KM,
    CONF_PATTERN_STORM_INTERNET_LIGHTNING,
    CONF_TEMP_UNIT,
    CONF_THRESH_FREEZE_C,
    CONF_THRESH_HEAT_DAY_C,
    CONF_THRESH_WIND_GUST_MS,
    DEFAULT_LIGHTNING_PROXIMITY_KM,
    DEFAULT_PATTERN_STORM_INTERNET_LIGHTNING,
    DEFAULT_TEMP_UNIT,
    DEFAULT_THRESH_FREEZE_C,
    DEFAULT_THRESH_HEAT_DAY_C,
    DEFAULT_THRESH_WIND_GUST_MS,
    KEY_DEW_POINT_C,
    KEY_LUX,
    KEY_NORM_RAIN_TOTAL_MM,
    KEY_NORM_TEMP_C,
    KEY_NORM_WIND_DIR_DEG,
    KEY_NORM_WIND_GUST_MS,
    KEY_NORM_WIND_SPEED_MS,
    KEY_PATTERN_FORECAST_SKILL,
    KEY_PATTERN_FORECAST_STATUS,
    KEY_PATTERN_OUTPUTS,
    KEY_PATTERN_SKILL_ATTRS,
    KEY_PATTERN_STATUS_ATTRS,
    KEY_PRESSURE_TREND_HPAH,
    KEY_RAIN_PROBABILITY,
    KEY_SEA_LEVEL_PRESSURE_HPA,
    KEY_SENSOR_QUALITY_FLAGS,
    KEY_SENSOR_SPIKE,
    KEY_SENSOR_STUCK,
    KEY_TEMP_HIGH_24H,
    KEY_TEMP_LOW_24H,
    KEY_THUNDERSTORM_RISK,
    LUX_TO_WM2_FACTOR,
    PATTERN_BIN_COUNT,
    PATTERN_HISTORY_DAYS,
    PATTERN_ISSUE_INTERVAL_MIN,
    PATTERN_RAIN_JUMP_CAP_MM,
    PATTERN_SOURCE_INTERNET,
    PATTERN_SOURCE_LOCAL,
    PATTERN_STORE_VERSION,
    PATTERN_STRIKE_JUMP_CAP,
    PATTERN_TARGET_KEYS,
    SRC_GUST,
    SRC_HUM,
    SRC_LIGHTNING_COUNT,
    SRC_LIGHTNING_DISTANCE,
    SRC_LUX,
    SRC_PRESS,
    SRC_RAIN_TOTAL,
    SRC_TEMP,
    SRC_WIND,
    SRC_WIND_DIR,
)
from .pattern_forecast import (
    POOL,
    TARGETS,
    HourlyHistory,
    Instant,
    Observation,
    PatternEngine,
    Thresholds,
    async_load_engine,
    async_save_engine,
)
from .pattern_sources import find_blitzortung_entities, source_fingerprint, storm_source

if TYPE_CHECKING:
    from .coordinator import WSStationCoordinator

_LOGGER = logging.getLogger(__name__)

_ISSUE_S = PATTERN_ISSUE_INTERVAL_MIN * 60
_BLITZ_RESCAN_S = 900.0
_KT_EMA_TICKS = 60.0  # ~1 h of 60 s ticks: "clearness of the last daylight hour"

# Recorder statistics each kind of target needs to replay (inputs of its feature mask and label)
_HISTORY_NEEDS: dict[str, tuple[str, ...]] = {
    "rain": ("temp", "hum", "press", "rain"),
    "frost": ("temp", "hum", "press", "wind", "rain"),
    "heat": ("temp", "hum", "press", "rain"),
    "gust": ("temp", "press", "wind", "gust"),
    "storm": ("temp", "hum", "press", "gust", "rain", "lightning"),
}
_HISTORY_SOURCE_KEY = {
    "temp": SRC_TEMP,
    "hum": SRC_HUM,
    "press": SRC_PRESS,
    "wind": SRC_WIND,
    "gust": SRC_GUST,
    "rain": SRC_RAIN_TOTAL,
}
_CUMULATIVE_INPUTS = ("rain", "lightning")
# Inputs of the 15-min history bins, seeded at startup from 5-minute statistics
_RECENT_INPUTS = ("temp", "hum", "wind", "dir", "gust", "rain", "lightning")
_BIN_S = PATTERN_ISSUE_INTERVAL_MIN * 60.0
_PERIOD_S = 300.0  # recorder short-term statistics period
# A 5-minute mean of a direction is only trusted when the period's min and max
# are this close: a wider spread may straddle north, where an arithmetic mean
# of degrees is meaningless (350 and 10 average to 180).
_DIR_MAX_SPREAD_DEG = 90.0

# Observation input groups an upstream quality flag can take out
_FLAG_BY_NAME = {
    "temperature": "temp",
    "temp": "temp",
    "humidity": "hum",
    "pressure": "press",
    "rain_rate": "rain",
}


def _recorder_instance(hass: Any) -> Any:
    """The recorder instance (imported lazily: the recorder is only needed for the replay)."""
    from homeassistant.components.recorder import get_instance

    return get_instance(hass)


def _iso(ts: float | None) -> str | None:
    return None if ts is None else datetime.fromtimestamp(ts, UTC).isoformat()


class PatternRuntime:
    """One per coordinator when ``enable_pattern_forecast`` is on."""

    def __init__(self, coord: WSStationCoordinator) -> None:
        self.coord = coord
        opts = coord.entry_options
        self.internet_opt_in = bool(
            opts.get(CONF_PATTERN_STORM_INTERNET_LIGHTNING, DEFAULT_PATTERN_STORM_INTERNET_LIGHTNING)
        )
        self.storm_source: str | None = storm_source(coord.sources, self.internet_opt_in)
        self.fingerprint = source_fingerprint(coord.sources, coord.elevation_m)
        self.engine = PatternEngine(self.thresholds(), self.storm_source, self.fingerprint)
        self.store: Any = None
        self._last_bucket: int | None = None
        self._blitz: dict[str, str] = {}
        self._blitz_checked: float | None = None
        self._last_local_strikes: float | None = None
        self._kt_ema: float | None = None
        self._published: dict[str, Any] = {}
        self._error_logged = False
        self._history_running = False

    # ------------------------------------------------------------------
    # configuration
    # ------------------------------------------------------------------

    def thresholds(self) -> Thresholds:
        o = self.coord.entry_options
        return Thresholds(
            frost_c=float(o.get(CONF_THRESH_FREEZE_C, DEFAULT_THRESH_FREEZE_C)),
            heat_c=float(o.get(CONF_THRESH_HEAT_DAY_C, DEFAULT_THRESH_HEAT_DAY_C)),
            gust_ms=float(o.get(CONF_THRESH_WIND_GUST_MS, DEFAULT_THRESH_WIND_GUST_MS)),
            storm_km=float(o.get(CONF_LIGHTNING_PROXIMITY_KM, DEFAULT_LIGHTNING_PROXIMITY_KM)),
        )

    # ------------------------------------------------------------------
    # storage
    # ------------------------------------------------------------------

    def make_store(self, entry_id: Any) -> Any:
        """The engine's own Store, separate from the learning store (independent reset)."""
        from homeassistant.helpers.storage import Store

        return Store(self.coord.hass, PATTERN_STORE_VERSION, f"ws_core_{entry_id}_pattern_forecast")

    async def async_load(self, store: Any) -> None:
        """Load the engine; a missing, corrupt or mismatched store starts fresh."""
        self.store = store
        self.engine = await async_load_engine(store, self.thresholds(), self.storm_source, self.fingerprint)

    async def async_save(self) -> None:
        if self.store is not None:
            await async_save_engine(self.store, self.engine)

    async def async_reset(self) -> None:
        """Delete the store and return every target to ``collecting``."""
        self.engine.reset_all()
        self._published = {}
        self._last_bucket = None
        if self.store is not None:
            try:
                await self.store.async_remove()
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning("ws_core pattern forecast: could not delete the store: %s", err)

    # ------------------------------------------------------------------
    # reading the station
    # ------------------------------------------------------------------

    @staticmethod
    def _flagged_inputs(data: dict) -> set[str]:
        """Input groups (temp/hum/press/rain/wind/gust) the existing detectors flag."""
        flagged: set[str] = set()
        for d in data.get("_drift_details") or []:
            if isinstance(d, dict) and (g := _FLAG_BY_NAME.get(str(d.get("sensor")))):
                flagged.add(g)
        for name in data.get(KEY_SENSOR_STUCK) or []:
            if g := _FLAG_BY_NAME.get(str(name)):
                flagged.add(g)
        for text in data.get(KEY_SENSOR_SPIKE) or []:
            if g := _FLAG_BY_NAME.get(str(text).split(":", 1)[0]):
                flagged.add(g)
        for text in data.get(KEY_SENSOR_QUALITY_FLAGS) or []:
            t = str(text)
            if t.startswith("wind gust below"):
                flagged.update({"wind", "gust"})
            elif t.startswith("dew point"):
                flagged.add("hum")
            elif g := _FLAG_BY_NAME.get(t.split(" ", 1)[0]):
                flagged.add(g)
        return flagged

    def _num(self, eid: str | None) -> float | None:
        return self.coord._num(self.coord.hass, eid)

    def _available(self, eid: str | None) -> bool:
        st = self.coord.hass.states.get(eid) if eid else None
        return st is not None and st.state != "unavailable"

    def _blitz_entities(self, ts: float) -> dict[str, str]:
        """Blitzortung counter/distance, rescanned at most every 15 min while missing."""
        if not self._blitz and (self._blitz_checked is None or ts - self._blitz_checked >= _BLITZ_RESCAN_S):
            self._blitz_checked = ts
            try:
                self._blitz = find_blitzortung_entities(self.coord.hass)
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("ws_core pattern forecast: Blitzortung scan failed: %s", err)
                self._blitz = {}
        return self._blitz

    def _strikes(self, ts: float) -> tuple[float | None, float | None]:
        """(cumulative strike count, latest distance km) of the active storm source."""
        if self.storm_source == PATTERN_SOURCE_LOCAL:
            count_eid = self.coord.sources.get(SRC_LIGHTNING_COUNT)
            dist_eid = self.coord.sources.get(SRC_LIGHTNING_DISTANCE)
            st = self.coord.hass.states.get(count_eid) if count_eid else None
            total = self._num(count_eid)
            if total is not None:
                self._last_local_strikes = total
            elif st is not None and st.state in ("unknown", "") and self._last_local_strikes is not None:
                # Many detectors report "unknown" while idle: that is "no new strikes",
                # unlike "unavailable" (device offline), which stays invalid.
                total = self._last_local_strikes
            return total, self._num(dist_eid)
        if self.storm_source == PATTERN_SOURCE_INTERNET:
            ent = self._blitz_entities(ts)
            count_eid = ent.get(SRC_LIGHTNING_COUNT)
            if not count_eid or not self._available(count_eid):
                return None, None  # feed not visible: the tick is invalid, never "no storm"
            return self._num(count_eid), self._num(ent.get(SRC_LIGHTNING_DISTANCE))
        return None, None

    def _sun(self, data: dict) -> tuple[float | None, float | None]:
        """(sun elevation, clearness index Kt) from the sun entity and the solar/lux sensor."""
        hass = self.coord.hass
        sun = hass.states.get("sun.sun")
        if sun is None:
            return None, None
        try:
            elev = float(sun.attributes.get("elevation"))
        except (TypeError, ValueError):
            return None, None
        solar = self.coord._get_solar_radiation()
        if solar is None:
            lux = data.get(KEY_LUX)
            if lux is None and self.coord.sources.get(SRC_LUX):
                lux = self._num(self.coord.sources.get(SRC_LUX))
            if lux is not None:
                solar = float(lux) * LUX_TO_WM2_FACTOR
        if solar is None:
            return elev, None
        return elev, calculate_clearness_index(float(solar), elev)

    def _lat_lon(self) -> tuple[float | None, float | None]:
        c = self.coord
        try:
            lat = c.forecast_lat if c.forecast_lat is not None else c.hass.config.latitude
            lon = c.forecast_lon if c.forecast_lon is not None else c.hass.config.longitude
            return float(lat), float(lon)
        except (TypeError, ValueError):
            return None, None

    # ------------------------------------------------------------------
    # the per-compute hook
    # ------------------------------------------------------------------

    def update(self, data: dict, now: datetime, sample: bool) -> None:
        """Feed the engine on sample ticks, issue on the 15-minute marks, publish."""
        try:
            if sample:
                self._tick(data, now)
                self._rebuild_published()
            self._publish(data)
        except Exception:  # noqa: BLE001 - a forecasting bug must never break the weather package
            if not self._error_logged:
                self._error_logged = True
                _LOGGER.exception("ws_core pattern forecast failed; the rest of the integration is unaffected")

    def _tick(self, data: dict, now: datetime) -> None:
        eng = self.engine
        ts = now.timestamp()
        flagged = self._flagged_inputs(data)
        tz_off = (dt_util.as_local(now).utcoffset() or dt_util.now().utcoffset()).total_seconds()

        def val(key: str, group: str | None = None) -> float | None:
            v = data.get(key)
            return None if (v is None or (group and group in flagged)) else float(v)

        temp = val(KEY_NORM_TEMP_C, "temp")
        dew = val(KEY_DEW_POINT_C, "hum")
        dpd = None if (temp is None or dew is None) else temp - dew
        speed = val(KEY_NORM_WIND_SPEED_MS, "wind")
        direction = val(KEY_NORM_WIND_DIR_DEG, "wind")
        u = v = None
        if speed is not None and direction is not None:
            ang = math.radians(direction)
            u, v = -speed * math.sin(ang), -speed * math.cos(ang)
        strikes, strike_km = self._strikes(ts)
        eng.observe(
            ts,
            Observation(
                temp=temp,
                dpd=dpd,
                wind_u=u,
                wind_v=v,
                wind_speed=speed,
                gust=val(KEY_NORM_WIND_GUST_MS, "gust"),
                rain_total=val(KEY_NORM_RAIN_TOTAL_MM, "rain"),
                strikes_total=strikes,
                strike_km=strike_km,
            ),
            tz_off,
        )

        elev, kt = self._sun(data)
        if kt is not None and elev is not None and elev >= 10.0:
            self._kt_ema = kt if self._kt_ema is None else self._kt_ema + (kt - self._kt_ema) / _KT_EMA_TICKS

        bucket = int(ts // _ISSUE_S)
        if bucket == self._last_bucket or ts - bucket * _ISSUE_S >= 300.0:
            return  # not an issue mark (or this one is already done)
        self._last_bucket = bucket
        lat, lon = self._lat_lon()
        local = dt_util.as_local(now)
        press_ok = "press" not in flagged
        inst = Instant(
            mslp=val(KEY_SEA_LEVEL_PRESSURE_HPA) if press_ok else None,
            dp_3h=val(KEY_PRESSURE_TREND_HPAH) if press_ok else None,
            temp=temp,
            dpd=dpd,
            t_max_24h=val(KEY_TEMP_HIGH_24H, "temp"),
            t_min_24h=val(KEY_TEMP_LOW_24H, "temp"),
            cloud_deficit=0.0 if kt is None else max(0.0, min(1.0, 1.0 - kt)),
            solar_ok=kt is not None,
            last_day_clearness=self._kt_ema if (elev is not None and elev >= 5.0) else None,
            night_frac_12h=None if lat is None or lon is None else night_fraction_ahead(lat, lon, now),
            local_hour=local.hour + local.minute / 60.0,
        )
        heur: dict[str, float] = {}
        rp = data.get(KEY_RAIN_PROBABILITY)
        if rp is not None:
            heur.update({t: float(rp) / 100.0 for t in ("rain_1h", "rain_3h", "rain_6h")})
        ts_risk = data.get(KEY_THUNDERSTORM_RISK)
        if ts_risk is not None:
            heur["storm_3h"] = float(ts_risk) / 100.0
        eng.issue(ts, inst, tz_off, hourly=bucket % 4 == 0, heuristics=heur)

    # ------------------------------------------------------------------
    # output
    # ------------------------------------------------------------------

    def _threshold_display(self, kind: str) -> tuple[float, str]:
        from .entity_descriptions import _DISTANCE_FACTORS, _WIND_FACTORS

        c = self.coord
        th = self.engine.thresholds
        if kind == "rain":
            return (round(th.rain_mm / 25.4, 3), "in") if c.rain_unit == "in" else (th.rain_mm, "mm")
        if kind in ("frost", "heat"):
            c_val = th.frost_c if kind == "frost" else th.heat_c
            conf = str(c.entry_options.get(CONF_TEMP_UNIT, DEFAULT_TEMP_UNIT))
            fahrenheit = conf == "F" or (conf == "auto" and c._is_imperial())
            return (round(c_val * 9.0 / 5.0 + 32.0, 1), "°F") if fahrenheit else (c_val, "°C")
        if kind == "gust":
            return round(th.gust_ms * _WIND_FACTORS.get(c.wind_unit, 1.0), 1), c.wind_unit
        return round(th.storm_km * _DISTANCE_FACTORS.get(c.distance_unit, 1.0), 1), c.distance_unit

    def _target_attrs(self, tid: str) -> dict[str, Any]:
        eng = self.engine
        o = eng.output(tid)
        thr, unit = self._threshold_display(o["target"])
        attrs: dict[str, Any] = {
            "target": o["target"],
            "horizon_h": o["horizon_h"],
            "data_source": eng.data_source(tid),
            "threshold": thr,
            "threshold_unit": unit,
            "maturity": o["maturity"],
            "brier_skill": o["brier_skill"],
            "usual_rate": o["usual_rate"],
            "issued_at": _iso(o["issued_at"]),
            "valid_until": _iso(o["valid_until"]),
            "top_factors": o["top_factors"],
            "samples_trained": o["samples_trained"],
        }
        if o["model_maturity"] == "collecting":
            attrs["progress_pct"] = o["progress_pct"]
        if o["reason"]:
            attrs["reason"] = o["reason"]
        return attrs

    def _rebuild_published(self) -> None:
        eng = self.engine
        probs: dict[str, int | None] = {}
        outputs: dict[str, dict[str, Any]] = {}
        per_target: dict[str, Any] = {}
        skill: dict[str, Any] = {}
        for tid in eng.active_target_ids():
            o = eng.output(tid)
            probs[tid] = o["probability"]
            outputs[tid] = self._target_attrs(tid)
            sk = eng.skill(tid)
            per_target[tid] = {
                "maturity": o["maturity"],
                "progress_pct": o["progress_pct"],
                "events_live": o["events_live"],
                "events_from_history": o["events_from_history"],
                "events_required": o["events_required"],
                "bss": sk["bss"],
            }
            skill[tid] = sk
        status_attrs: dict[str, Any] = {
            "per_target": per_target,
            "history_learn": self._history_attrs(),
            "internet_inputs": eng.internet_inputs(),
            "last_trained_at": _iso(eng.last_trained_at),
            "storm_target": self._storm_target_text(),
        }
        self._published = {
            "probs": probs,
            "outputs": outputs,
            "status": eng.overall_status(),
            "skilled": eng.skilled_count(),
            "status_attrs": status_attrs,
            "skill_attrs": {"per_target": skill},
        }

    def _history_attrs(self) -> dict[str, Any]:
        """Learning-from-history result: overall status/span/reason plus one entry per target."""
        hl = self.engine.history_learn
        if not hl:
            return {}
        return {
            "status": hl.get("status"),
            "span_days": hl.get("span_days"),
            "reason": hl.get("reason"),
            "done_at": _iso(hl.get("done_at")),
            "per_target": {
                tid: {"status": e.get("status"), "reason": e.get("reason"), "samples": e.get("samples", 0)}
                for tid, e in (hl.get("targets") or {}).items()
            },
        }

    def _storm_target_text(self) -> str:
        if self.storm_source == PATTERN_SOURCE_LOCAL:
            return "local lightning detector"
        if self.storm_source == PATTERN_SOURCE_INTERNET:
            return "internet lightning (Blitzortung)" if self._blitz else "waiting for the Blitzortung integration"
        return "not created: no lightning detector mapped and internet lightning is off"

    def _publish(self, data: dict) -> None:
        pub = self._published
        if not pub:
            if self.engine.models:
                self._rebuild_published()
                pub = self._published
            else:
                return
        for tid, p in pub["probs"].items():
            data[PATTERN_TARGET_KEYS[tid]] = p
        data[KEY_PATTERN_OUTPUTS] = pub["outputs"]
        data[KEY_PATTERN_FORECAST_STATUS] = pub["status"]
        data[KEY_PATTERN_FORECAST_SKILL] = pub["skilled"]
        data[KEY_PATTERN_STATUS_ATTRS] = pub["status_attrs"]
        data[KEY_PATTERN_SKILL_ATTRS] = pub["skill_attrs"]

    # ------------------------------------------------------------------
    # learning from history (recorder long-term statistics)
    # ------------------------------------------------------------------

    def history_entity(self, name: str, ts: float) -> str | None:
        """Entity whose statistics feed one replay input (None when nothing is mapped)."""
        if name != "lightning":
            return self.coord.sources.get(_HISTORY_SOURCE_KEY[name]) or None
        if self.storm_source == PATTERN_SOURCE_LOCAL:
            return self.coord.sources.get(SRC_LIGHTNING_COUNT) or None
        if self.storm_source == PATTERN_SOURCE_INTERNET:
            return self._blitz_entities(ts).get(SRC_LIGHTNING_COUNT)
        return None

    def _fetch_statistics(
        self, entity_ids: set[str], start: datetime, end: datetime, period: str = "hour"
    ) -> tuple[dict, dict]:
        """Statistics ("hour" long-term or "5minute" short-term) and metadata.

        Synchronous: runs on the recorder executor.
        """
        from homeassistant.components.recorder.statistics import list_statistic_ids, statistics_during_period

        meta = {m["statistic_id"]: m for m in list_statistic_ids(self.coord.hass, statistic_ids=entity_ids)}
        rows = statistics_during_period(
            self.coord.hass, start, end, set(meta), period, None, {"mean", "min", "max", "sum", "state"}
        )
        return meta, rows

    def recent_entity(self, name: str, ts: float) -> str | None:
        """Entity whose 5-minute statistics feed one input of the history bins."""
        if name == "dir":
            return self.coord.sources.get(SRC_WIND_DIR) or None
        return self.history_entity(name, ts)

    def build_recent_bins(self, plan: dict[str, str | None], meta: dict, rows: dict, now_ts: float) -> list[dict]:
        """5-minute statistics -> 15-min history bins shaped like the live ones.

        Bin ``B`` covers ``[B - 15 min, B)``: temperature and dew point depression
        are the last 5-minute mean (live keeps the last reading), wind and speed
        the mean of the bin's periods, gust their max, and rain / strikes the rise
        of the running total over the bin (a decrease is a reset, a jump is unknown).
        Only complete periods are used, so a period still being recorded never
        stands in for live data.
        """
        c = self.coord
        o = c.entry_options
        cal_t = float(o.get(CONF_CAL_TEMP_C, 0.0))
        cal_h = float(o.get(CONF_CAL_HUMIDITY, 0.0))
        cal_w = float(o.get(CONF_CAL_WIND_MS, 0.0))

        def unit(name: str) -> str:
            eid = plan.get(name)
            return str((meta.get(eid) or {}).get("unit_of_measurement") or "") if eid else ""

        def by_start(name: str) -> dict[float, dict]:
            eid = plan.get(name)
            out: dict[float, dict] = {}
            for r in (rows.get(eid) or []) if eid else []:
                ts = self._row_ts(r)
                if ts is not None and ts + _PERIOD_S <= now_ts:
                    out[ts] = r
            return out

        def num(row: dict | None, key: str) -> float | None:
            v = None if row is None else row.get(key)
            return float(v) if isinstance(v, (int, float)) and math.isfinite(v) else None

        temp, hum, wind, dirs, gust = (by_start(n) for n in ("temp", "hum", "wind", "dir", "gust"))
        dir_circular = (meta.get(plan.get("dir") or "") or {}).get("mean_type") == 2

        def cumulative_end(name: str, conv: Any) -> dict[float, float]:
            """Running total at the end of each period."""
            eid = plan.get(name)
            if not eid:
                return {}
            per = by_start(name)
            key = self._cumulative_key(meta.get(eid) or {}, list(per.values()))
            out = {}
            for ts, r in per.items():
                v = num(r, key)
                if v is not None:
                    out[ts] = conv(v)
            return out

        rain_end = cumulative_end("rain", lambda v: c._to_mm(v, unit("rain")))
        strike_end = cumulative_end("lightning", lambda v: v)

        def rise(ends: dict[float, float], b: float, cap: float) -> float | None:
            a, z = ends.get(b - _BIN_S - _PERIOD_S), ends.get(b - _PERIOD_S)
            if a is None or z is None:
                return None
            d = z - a
            return 0.0 if d < 0 else (None if d > cap else round(d, 4))

        last = math.floor(now_ts / _BIN_S) * _BIN_S
        bins: list[dict] = []
        for k in range(PATTERN_BIN_COUNT - 1, -1, -1):
            b = last - k * _BIN_S
            periods = [b - _BIN_S + i * _PERIOD_S for i in range(3)]
            t_raw = num(temp.get(periods[-1]), "mean")
            t = None if t_raw is None else round(c._to_celsius(t_raw, unit("temp")) + cal_t, 2)
            h = num(hum.get(periods[-1]), "mean")
            d = None
            if t is not None and h is not None:
                h = max(0.0, min(100.0, h + cal_h))
                if h > 0:
                    d = round(max(0.0, t - calculate_dew_point(t, h)), 2)
            # Like live ticks, a period counts for wind only with both a speed and a
            # trustworthy direction; u, v and speed are averaged over those periods.
            ss, us, vs = [], [], []
            for p in periods:
                sp = num(wind.get(p), "mean")
                drow = dirs.get(p)
                dm, dlo, dhi = num(drow, "mean"), num(drow, "min"), num(drow, "max")
                if sp is None or dm is None:
                    continue
                if not (dir_circular or (dlo is not None and dhi is not None and dhi - dlo <= _DIR_MAX_SPREAD_DEG)):
                    continue
                sp = max(0.0, c._to_ms(sp, unit("wind")) + cal_w)
                ang = math.radians(dm)
                ss.append(sp)
                us.append(-sp * math.sin(ang))
                vs.append(-sp * math.cos(ang))
            gusts = [g for g in (num(gust.get(p), "max") for p in periods) if g is not None]
            bin_ = {
                "ts": b,
                "t": t,
                "d": d,
                "u": sum(us) / len(us) if us else None,
                "v": sum(vs) / len(vs) if vs else None,
                "s": sum(ss) / len(ss) if ss else None,
                "g": max(0.0, c._to_ms(max(gusts), unit("gust")) + cal_w) if gusts else None,
                "r": rise(rain_end, b, PATTERN_RAIN_JUMP_CAP_MM),
                "k": rise(strike_end, b, PATTERN_STRIKE_JUMP_CAP) if self.storm_source else None,
                "n": 5 * len(ss),
            }
            if any(bin_[key] is not None for key in ("t", "d", "s", "g", "r")):
                bins.append(bin_)
        return bins

    def _recent_job(self, plan: dict[str, str | None], now_ts: float) -> list[dict]:
        """Read the last ~3.5 h of 5-minute statistics. Runs on the recorder executor."""
        ids = {e for e in plan.values() if e}
        if not ids:
            return []
        start_ts = math.floor(now_ts / _BIN_S) * _BIN_S - PATTERN_BIN_COUNT * _BIN_S - _PERIOD_S
        meta, rows = self._fetch_statistics(
            ids, datetime.fromtimestamp(start_ts, UTC), datetime.fromtimestamp(now_ts, UTC), period="5minute"
        )
        return self.build_recent_bins(plan, meta, rows, now_ts)

    async def _async_seed_recent(self, now: datetime) -> int:
        """Seed the 15-min history bins from the recorder (every startup, before any replay)."""
        ts = now.timestamp()
        plan = {name: self.recent_entity(name, ts) for name in _RECENT_INPUTS}
        try:
            bins = await _recorder_instance(self.coord.hass).async_add_executor_job(partial(self._recent_job, plan, ts))
        except Exception as err:  # noqa: BLE001 - recorder missing or busy: warm up live instead
            _LOGGER.debug("ws_core pattern forecast: no short-term statistics to seed from: %s", err)
            return 0
        wet = [b["ts"] for b in bins if (b.get("r") or 0.0) > 0.0]
        if wet:
            self.engine.seed_last_rain(max(wet))
        return self.engine.seed_bins(bins)

    @staticmethod
    def _row_ts(row: dict) -> float | None:
        start = row.get("start")
        if isinstance(start, datetime):
            return start.timestamp()
        return float(start) if isinstance(start, (int, float)) else None

    def _series(self, rows: list[dict], start_ts: float, n: int, key: str, convert: Any) -> list[float | None]:
        out: list[float | None] = [None] * n
        for row in rows:
            ts = self._row_ts(row)
            v = row.get(key)
            if ts is None or v is None:
                continue
            idx = int(round((ts - start_ts) / 3600.0))
            if 0 <= idx < n and isinstance(v, (int, float)) and math.isfinite(v):
                out[idx] = convert(float(v))
        return out

    @staticmethod
    def _offset_s(ts: float, tz: Any) -> float:
        off = datetime.fromtimestamp(ts, tz).utcoffset()
        return 0.0 if off is None else off.total_seconds()

    @staticmethod
    def _cumulative_key(meta_entry: dict, rows: list[dict]) -> str:
        """Which hourly statistic holds a cumulative counter's running total.

        ``sum`` for total/total_increasing sensors, else the stored ``state``. Many
        stations (e.g. the Shelly WS90) report their rain total with
        state_class: measurement, so the recorder keeps only mean/min/max; for a
        running total the hourly ``max`` is its value at the end of the hour.
        """
        if meta_entry.get("has_sum"):
            return "sum"
        if any(r.get("state") is not None for r in rows):
            return "state"
        return "max"

    @staticmethod
    def _hourly_delta(cum: list[float | None], cap: float) -> list[float | None]:
        """Per-hour change of a cumulative counter: a decrease is a reset (0), a jump is invalid."""
        out: list[float | None] = [None] * len(cum)
        for i in range(1, len(cum)):
            if cum[i] is None or cum[i - 1] is None:
                continue
            d = cum[i] - cum[i - 1]
            out[i] = 0.0 if d < 0 else (None if d > cap else d)
        return out

    def build_history(
        self, plan: dict[str, str | None], meta: dict, rows: dict, start_ts: float, n: int, need_night: bool
    ) -> HourlyHistory:
        """Hourly statistics -> HourlyHistory, through the same normalization as live data."""
        c = self.coord
        o = c.entry_options
        cal_t = float(o.get(CONF_CAL_TEMP_C, 0.0))
        cal_h = float(o.get(CONF_CAL_HUMIDITY, 0.0))
        cal_p = float(o.get(CONF_CAL_PRESSURE_HPA, 0.0))
        cal_w = float(o.get(CONF_CAL_WIND_MS, 0.0))

        def unit(name: str) -> str:
            eid = plan.get(name)
            return str((meta.get(eid) or {}).get("unit_of_measurement") or "") if eid else ""

        def rws(name: str) -> list[dict]:
            eid = plan.get(name)
            return rows.get(eid) or [] if eid else []

        def temp_conv(v: float) -> float:
            return round(c._to_celsius(v, unit("temp")) + cal_t, 2)

        temp = self._series(rws("temp"), start_ts, n, "mean", temp_conv)
        tmin = self._series(rws("temp"), start_ts, n, "min", temp_conv)
        tmax = self._series(rws("temp"), start_ts, n, "max", temp_conv)
        hum = self._series(rws("hum"), start_ts, n, "mean", lambda v: max(0.0, min(100.0, v + cal_h)))
        press = self._series(rws("press"), start_ts, n, "mean", lambda v: c._to_hpa(v, unit("press")) + cal_p)
        wind = self._series(rws("wind"), start_ts, n, "mean", lambda v: max(0.0, c._to_ms(v, unit("wind")) + cal_w))
        gust = self._series(rws("gust"), start_ts, n, "max", lambda v: max(0.0, c._to_ms(v, unit("gust")) + cal_w))

        def cumulative(name: str, conv: Any) -> list[float | None]:
            eid = plan.get(name)
            if not eid:
                return [None] * n
            key = self._cumulative_key(meta.get(eid) or {}, rws(name))
            return self._series(rws(name), start_ts, n, key, conv)

        rain = self._hourly_delta(cumulative("rain", lambda v: c._to_mm(v, unit("rain"))), PATTERN_RAIN_JUMP_CAP_MM)
        strikes = self._hourly_delta(cumulative("lightning", lambda v: v), PATTERN_STRIKE_JUMP_CAP)

        mslp: list[float | None] = [None] * n
        dpd: list[float | None] = [None] * n
        for j in range(n):
            if temp[j] is not None and press[j] is not None:
                recent = [v for v in temp[max(0, j - 11) : j + 1] if v is not None]
                mean_t = sum(recent) / len(recent) if len(recent) >= 6 else None
                mslp[j] = calculate_sea_level_pressure(press[j], c.elevation_m, temp[j], mean_temp_c=mean_t)
            if temp[j] is not None and hum[j] is not None:
                dpd[j] = max(0.0, temp[j] - calculate_dew_point(temp[j], hum[j]))

        tz = dt_util.get_default_time_zone()
        tz_offset = [self._offset_s(start_ts + (j + 1) * 3600.0, tz) for j in range(n)]
        night: list[float | None] = [None] * n
        lat, lon = self._lat_lon()
        if need_night and lat is not None and lon is not None:
            for j in range(n):
                t = datetime.fromtimestamp(start_ts + (j + 1) * 3600.0, UTC)
                night[j] = night_fraction_ahead(lat, lon, t, hours=12.0, step_min=60)
        return HourlyHistory(
            start_ts=start_ts,
            n=n,
            mslp=mslp,
            temp=temp,
            temp_min=tmin,
            temp_max=tmax,
            dpd=dpd,
            wind=wind,
            gust=gust,
            rain=rain,
            strikes=strikes,
            night_frac=night,
            tz_offset=tz_offset,
        )

    def _history_job(
        self, snapshot: dict, targets: list[str], plan: dict[str, str | None], update_std: bool, start_ts: float, n: int
    ) -> dict[str, Any]:
        """Fetch, normalize and train a COPY of the engine. Runs on the recorder executor."""
        trainer, _ = PatternEngine.from_dict(snapshot, self.engine.thresholds, self.storm_source, self.fingerprint)
        ids = {e for e in plan.values() if e}
        start = datetime.fromtimestamp(start_ts, UTC)
        end = datetime.fromtimestamp(start_ts + n * 3600.0, UTC)
        meta, rows = self._fetch_statistics(ids, start, end) if ids else ({}, {})

        statuses: dict[str, dict[str, Any]] = {}
        replayable: list[str] = []
        for tid in targets:
            kind = trainer.models[tid].spec.kind
            problems = []
            for name in _HISTORY_NEEDS[kind]:
                eid = plan.get(name)
                if not eid:
                    problems.append(f"no sensor mapped for {name}")
                elif eid not in meta:
                    problems.append(f"no statistics for {eid}")
                elif name in _CUMULATIVE_INPUTS and not (meta[eid].get("has_sum") or rows.get(eid)):
                    problems.append(f"no cumulative statistics for {eid}")
            if problems:
                statuses[tid] = {
                    "status": "unavailable",
                    "reason": "history: unavailable (" + "; ".join(problems) + ")",
                    "samples": 0,
                    "events": 0,
                }
            else:
                replayable.append(tid)
        report: dict[str, dict[str, Any]] = {}
        pressure_seed: list[list[float]] = []
        last_rain_ts: float | None = None
        if replayable:
            need_night = any(trainer.models[t].spec.kind == "frost" for t in replayable)
            hist = self.build_history(plan, meta, rows, start_ts, n, need_night)
            pressure_seed = PatternEngine.pressure_seed_from_history(hist)
            wet = [j for j, r in enumerate(hist.rain) if r is not None and r > 0.0]
            if wet:
                last_rain_ts = hist.start_ts + (wet[-1] + 1) * 3600.0
            report = trainer.replay(hist, replayable, update_std)
            for tid in replayable:
                r = report[tid]
                if r["samples"] == 0:
                    statuses[tid] = {
                        "status": "too_short",
                        "reason": "history: too short (no complete hours of statistics)",
                        "samples": 0,
                        "events": r["events"],
                    }
                else:
                    statuses[tid] = {"status": "ok", "reason": None, "samples": r["samples"], "events": r["events"]}
        return {
            "trained": trainer,
            "report": report,
            "statuses": statuses,
            "pressure_seed": pressure_seed,
            "last_rain_ts": last_rain_ts,
        }

    async def async_learn_history(self) -> None:
        """Warm start from the recorder, then replay a year of statistics where needed.

        Every run (startup, reset, threshold change) first seeds the 15-min history
        bins from the last ~3 h of 5-minute statistics, so the 1 h / 3 h inputs exist
        straight away. Targets that have not learned yet then replay up to a year of
        hourly statistics: the read and the training run on the recorder executor
        against a copy of the engine, and the result is swapped in here on the event
        loop. Replayed samples never count toward ``skilled``.
        """
        if self._history_running:
            return
        self._history_running = True
        try:
            now = dt_util.utcnow()
            bins = await self._async_seed_recent(now)
            if bins:
                _LOGGER.info("ws_core pattern forecast: seeded %d recent 15-min history bins from the recorder", bins)
            eng = self.engine
            targets = eng.targets_needing_replay(now.timestamp())
            if not targets:
                if bins:
                    await self.async_save()
                return
            update_std = eng.std_is_cold()
            end_ts = math.floor(now.timestamp() / 3600.0) * 3600.0
            n = PATTERN_HISTORY_DAYS * 24
            start_ts = end_ts - n * 3600.0
            plan = {
                name: self.history_entity(name, end_ts)
                for name in sorted({x for t in targets for x in _HISTORY_NEEDS[eng.models[t].spec.kind]})
            }
            job = partial(self._history_job, eng.to_dict(), targets, plan, update_std, start_ts, n)
            try:
                result = await _recorder_instance(self.coord.hass).async_add_executor_job(job)
            except Exception as err:  # noqa: BLE001 - recorder missing, DB error, ...
                _LOGGER.warning("ws_core pattern forecast: learning from history failed: %s", err)
                reason = f"history: unavailable (recorder error: {type(err).__name__})"
                result = {
                    "trained": eng,
                    "report": {},
                    "statuses": {
                        t: {"status": "unavailable", "reason": reason, "samples": 0, "events": 0} for t in targets
                    },
                }
            eng.adopt_replay(result["trained"], result["report"], result["statuses"], update_std, now.timestamp())
            # The 24 h pressure change needs a reading from a day ago; seed it from the
            # replayed hours so forecasts do not wait a day after being switched on.
            seeded = eng.seed_pressure(result.get("pressure_seed") or [])
            eng.seed_last_rain(result.get("last_rain_ts"))
            self._rebuild_published()
            _LOGGER.info(
                "ws_core pattern forecast: learned from history (%s), seeded %d pressure readings",
                {t: s["status"] for t, s in result["statuses"].items()},
                seeded,
            )
            await self.async_save()
        finally:
            self._history_running = False

    # ------------------------------------------------------------------
    # services / diagnostics
    # ------------------------------------------------------------------

    def summary(self) -> dict[str, Any]:
        """Maturity and skill per target plus the named weights (export service, diagnostics)."""
        eng = self.engine
        out: dict[str, Any] = {}
        for tid in eng.active_target_ids():
            o = eng.output(tid)
            sk = eng.skill(tid)
            out[tid] = {
                "maturity": o["maturity"],
                "progress_pct": o["progress_pct"],
                "samples_trained": o["samples_trained"],
                "events_live": o["events_live"],
                "events_from_history": o["events_from_history"],
                "bss": sk["bss"],
                "bss_vs_persistence": sk["bss_vs_persistence"],
                "usual_rate": o["usual_rate"],
                "weights": eng.named_weights(tid),
            }
        return out

    def diagnostics(self) -> dict[str, Any]:
        """Diagnostics-download section: no location data."""
        eng = self.engine
        return {
            "enabled": True,
            "status": eng.overall_status(),
            "storm_source": eng.storm_source,
            "internet_lightning_in_use": bool(eng.internet_inputs()),
            "internet_inputs": eng.internet_inputs(),
            "targets": self.summary(),
            "standardizer": {
                name: {
                    "mean": round(eng.std.mean[i], 4),
                    "std": round(math.sqrt(max(eng.std.var[i], 0.0)), 4),
                    "n": eng.std.n[i],
                }
                for i, name in enumerate(POOL)
            },
            "history_learn": eng.history_learn,
            "pending": len(eng.pending),
            "targets_registered": [t.target_id for t in TARGETS],
        }
