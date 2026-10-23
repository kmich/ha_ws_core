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
from typing import TYPE_CHECKING, Any

from homeassistant.util import dt as dt_util

from .algorithms import calculate_clearness_index, night_fraction_ahead
from .const import (
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
    PATTERN_ISSUE_INTERVAL_MIN,
    PATTERN_SOURCE_INTERNET,
    PATTERN_SOURCE_LOCAL,
    PATTERN_STORE_VERSION,
    PATTERN_TARGET_KEYS,
    SRC_LIGHTNING_COUNT,
    SRC_LIGHTNING_DISTANCE,
    SRC_LUX,
)
from .pattern_forecast import (
    POOL,
    TARGETS,
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

# Observation input groups an upstream quality flag can take out
_FLAG_BY_NAME = {
    "temperature": "temp",
    "temp": "temp",
    "humidity": "hum",
    "pressure": "press",
    "rain_rate": "rain",
}


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
        self.history_task: Any = None

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
            "history_learn": eng.history_learn.get("targets", {}) if eng.history_learn else {},
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
