"""I/O side of the local PV forecast (v3.0.0): Open-Meteo fetch, recorder reads, store.

The model itself lives in ``solar_local.py``. One runtime per coordinator, created
only when the solar forecast feature is on and at least one PV energy meter is
mapped.
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta, tzinfo
from typing import TYPE_CHECKING, Any

import aiohttp
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util

from .const import (
    KEY_SOLAR_LOCAL_INFO,
    KEY_SOLAR_LOCAL_REMAINING_KWH,
    KEY_SOLAR_LOCAL_TODAY_KWH,
    KEY_SOLAR_LOCAL_TOMORROW_KWH,
)
from .solar_local import (
    BACKFILL_DAYS,
    STATUS_PRIOR,
    STORE_VERSION,
    SolarLocalState,
    actual_daily_kwh,
    build_url,
    fit_factor,
    hourly_kwh,
    parse_gti,
    predict_kwh,
    prior_factor,
    remaining_kwh,
    skill,
    store_key,
)

if TYPE_CHECKING:
    from .coordinator import WSStationCoordinator

_LOGGER = logging.getLogger(__name__)

# Days of meter statistics re-read on every refresh after the backfill (late
# statistics compiles and yesterday's final hours are picked up this way).
_RECENT_DAYS = 3


def read_meter_statistics(
    hass: Any, meters: list[str], start: datetime, end: datetime
) -> tuple[dict[str, list[dict]], dict[str, str | None]]:
    """Hourly ``change`` rows and units for the PV meters. Runs on the recorder executor."""
    from homeassistant.components.recorder.statistics import list_statistic_ids, statistics_during_period

    from .pattern_runtime import statistics_unit

    meta = {m["statistic_id"]: m for m in list_statistic_ids(hass, statistic_ids=set(meters))}
    if set(meta) != set(meters):
        return {}, {}
    rows = statistics_during_period(hass, start, end, set(meta), "hour", None, {"change"})
    units = {sid: statistics_unit(m) for sid, m in meta.items()}
    return {sid: list(rows.get(sid) or []) for sid in meters}, units


class SolarLocalRuntime:
    def __init__(self, coord: WSStationCoordinator, meters: list[str]) -> None:
        self.coord = coord
        self.meters = sorted({str(m) for m in meters if m})
        self.state = SolarLocalState()
        self.store: Any = None
        self.k: float | None = None
        self.n_days = 0
        self.status = STATUS_PRIOR
        self.today_kwh: float | None = None
        self.tomorrow_kwh: float | None = None
        self.hourly: list[dict[str, Any]] = []
        self.skill: dict[str, Any] = {}
        self.updated_at: str | None = None
        self.error: str | None = None
        self.meter_problem: str | None = None

    # -- persistence -----------------------------------------------------

    async def async_load(self, entry_id: str) -> None:
        from homeassistant.helpers.storage import Store

        self.store = Store(self.coord.hass, STORE_VERSION, store_key(entry_id))
        try:
            self.state = SolarLocalState.from_dict(await self.store.async_load())
        except Exception as err:  # noqa: BLE001 - a corrupt store starts fresh
            _LOGGER.warning("ws_core: local PV forecast store unreadable (starting fresh): %s", err)
            self.state = SolarLocalState()
        if self.state.reset_for_meters(self.meters):
            _LOGGER.info("ws_core: PV meters changed, local PV forecast will relearn from their history")

    async def _async_save(self) -> None:
        if self.store is not None:
            try:
                await self.store.async_save(self.state.to_dict())
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("ws_core: could not save local PV forecast state: %s", err)

    # -- refresh -----------------------------------------------------------

    async def _async_read_actuals(self, days: int, today: date, tz: tzinfo) -> dict[str, float] | None:
        hass = self.coord.hass
        if "recorder" not in hass.config.components:
            self.meter_problem = "recorder_unavailable"
            return None
        from .history_backfill import _recorder_instance

        start_local = datetime.combine(today - timedelta(days=days), datetime.min.time(), tz)
        end_local = datetime.combine(today, datetime.min.time(), tz)
        try:
            rows, units = await _recorder_instance(hass).async_add_executor_job(
                read_meter_statistics, hass, self.meters, start_local.astimezone(UTC), end_local.astimezone(UTC)
            )
        except Exception as err:  # noqa: BLE001 - recorder missing, DB error, ...
            _LOGGER.debug("ws_core: could not read PV meter statistics: %s", err)
            self.meter_problem = "statistics_unavailable"
            return None
        if not rows:
            self.meter_problem = "no_statistics"
            return {}
        bad_units = [sid for sid, unit in units.items() if str(unit or "").lower() not in ("wh", "kwh", "mwh", "gwh")]
        if bad_units:
            self.meter_problem = "not_an_energy_meter"
            return {}
        out = actual_daily_kwh(rows, units, tz, today)
        # Statistics exist but no day had every meter reporting most of its hours.
        self.meter_problem = None if out else "no_complete_days"
        return out

    async def _async_fetch_gti(self, past_days: int) -> dict[str, Any] | None:
        coord = self.coord
        url = build_url(
            coord.forecast_lat, coord.forecast_lon, coord.solar_panel_tilt, coord.solar_panel_azimuth, past_days
        )
        try:
            session = async_get_clientsession(coord.hass)
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                if resp.status != 200:
                    self.error = f"HTTP {resp.status}"
                    _LOGGER.warning("ws_core local PV forecast fetch failed: HTTP %s", resp.status)
                    return None
                js = await resp.json()
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            self.error = str(err) or type(err).__name__
            _LOGGER.warning("ws_core local PV forecast fetch error: %s", err)
            return None
        return js if isinstance(js, dict) else None

    async def async_update(self) -> None:
        coord = self.coord
        if coord.forecast_lat is None or coord.forecast_lon is None:
            return
        tz = dt_util.get_default_time_zone()
        now = dt_util.now()
        today = now.date()
        tomorrow = today + timedelta(days=1)
        backfill = not self.state.backfilled

        js = await self._async_fetch_gti(BACKFILL_DAYS if backfill else 1)
        if js is None:
            coord.async_update_listeners()
            return
        daily, series = parse_gti(js, tz)
        if not daily:
            self.error = "no_irradiance_in_response"
            return
        self.error = None
        recent = (today - timedelta(days=1)).isoformat()
        for day, gti in daily.items():
            # Older days keep the value they had; a backfill fills what is missing.
            if day >= recent or (backfill and "gti" not in self.state.days.get(day, {})):
                self.state.set_value(day, "gti", gti)

        actual = await self._async_read_actuals(BACKFILL_DAYS if backfill else _RECENT_DAYS, today, tz)
        for day, kwh in (actual or {}).items():
            self.state.set_value(day, "actual", kwh)
        # A backfill that found no usable day is tried again on the next refresh.
        if backfill and actual and self.meter_problem is None:
            self.state.backfilled = True

        self.k, self.n_days, self.status = fit_factor(self.state, prior_factor(coord.solar_peak_kw), today)
        self.today_kwh = predict_kwh(self.k, daily.get(today.isoformat()))
        self.tomorrow_kwh = predict_kwh(self.k, daily.get(tomorrow.isoformat()))
        self.hourly = hourly_kwh(self.k, series, tz, today, tomorrow)

        # Day-ahead snapshots: overwritten on every refresh until the day starts, so the
        # stored value is the last prediction made before it - never a same-day one.
        self.state.set_value(tomorrow.isoformat(), "da_local", self.tomorrow_kwh)
        fs = getattr(coord, "_solar_cache", None) or {}
        fs_tomorrow = fs.get("tomorrow_kwh")
        fetched = fs.get("fetched_at")
        if isinstance(fs_tomorrow, (int, float)) and isinstance(fetched, str):
            fetched_dt = dt_util.parse_datetime(fetched)
            if fetched_dt is not None and dt_util.as_local(fetched_dt).date() == today:
                self.state.set_value(tomorrow.isoformat(), "da_fs", float(fs_tomorrow))

        self.skill = skill(self.state, today)
        self.state.prune(today)
        self.updated_at = dt_util.utcnow().isoformat()
        await self._async_save()
        await coord.async_request_refresh()

    # -- coordinator data --------------------------------------------------

    def apply(self, data: dict[str, Any], now: datetime) -> None:
        if self.k is None:
            return
        data[KEY_SOLAR_LOCAL_TODAY_KWH] = self.today_kwh
        data[KEY_SOLAR_LOCAL_TOMORROW_KWH] = self.tomorrow_kwh
        data[KEY_SOLAR_LOCAL_REMAINING_KWH] = remaining_kwh(self.hourly, now)
        data[KEY_SOLAR_LOCAL_INFO] = {
            "model_status": self.status,
            "days_used": self.n_days,
            "site_factor": round(self.k, 3),
            "prior_site_factor": round(prior_factor(self.coord.solar_peak_kw), 3),
            "pv_meters": list(self.meters),
            "meter_problem": self.meter_problem,
            "last_error": self.error,
            "updated_at": self.updated_at,
            "skill_local": (self.skill or {}).get("local"),
            "skill_forecast_solar": (self.skill or {}).get("forecast_solar"),
            "hourly": self.hourly,
        }

    def summary(self) -> dict[str, Any]:
        """Compact diagnostics payload (no hourly series, no per-day history)."""
        return {
            "meters": list(self.meters),
            "backfilled": self.state.backfilled,
            "stored_days": len(self.state.days),
            "model_status": self.status,
            "days_used": self.n_days,
            "site_factor": None if self.k is None else round(self.k, 3),
            "meter_problem": self.meter_problem,
            "last_error": self.error,
            "skill": self.skill,
        }
