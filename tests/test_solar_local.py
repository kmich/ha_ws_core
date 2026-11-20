"""Local PV forecast (v3.0.0): Open-Meteo GTI scaled by the site's measured PV energy."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from custom_components.ws_core import const as c
from custom_components.ws_core import solar_local as sl
from custom_components.ws_core.__init__ import entry_storage_keys
from custom_components.ws_core.config_flow import _pv_meter_list
from custom_components.ws_core.entity_descriptions import sensor_selected, station_supports
from custom_components.ws_core.solar_local_runtime import SolarLocalRuntime

ATHENS = ZoneInfo("Europe/Athens")
TODAY = date(2026, 11, 20)


def _hour_ts(day: date, hour: int, tz=ATHENS) -> float:
    return datetime(day.year, day.month, day.day, hour, tzinfo=tz).timestamp()


def _om_response(days: dict[date, list[float]]) -> dict:
    """Open-Meteo style hourly GTI: the value stamped t covers the hour before t."""
    times, values = [], []
    for day, hourly in days.items():
        for hour, wh in enumerate(hourly):
            times.append(_hour_ts(day, hour) + 3600)
            values.append(wh)
    return {"hourly": {"time": times, "global_tilted_irradiance": values}}


def _bell(peak: float) -> list[float]:
    """24 hourly values, zero at night, peaking at local noon."""
    return [max(0.0, peak * (1 - abs(h + 0.5 - 12.5) / 5.5)) for h in range(24)]


# --- helpers -------------------------------------------------------------------


@pytest.mark.parametrize(("compass", "om"), [(180, 0), (90, -90), (270, 90), (135, -45), (0, 180)])
def test_open_meteo_azimuth(compass, om):
    assert sl.open_meteo_azimuth(compass) == om


def test_build_url_clamps_past_days_and_uses_panel_geometry():
    url = sl.build_url(37.9, 23.7, 30, 90, 500)
    assert "tilt=30" in url and "azimuth=-90" in url
    assert "past_days=92" in url and "forecast_days=2" in url
    assert "global_tilted_irradiance" in url


@pytest.mark.parametrize(("unit", "kwh"), [("Wh", 1.5), ("kWh", 1500.0), ("MWh", 1_500_000.0), ("W", None)])
def test_energy_to_kwh(unit, kwh):
    assert sl.energy_to_kwh(1500.0, unit) == kwh


def test_pv_meter_list_cleans_selection():
    assert _pv_meter_list(["sensor.b", "", "sensor.a", "sensor.b"]) == ["sensor.a", "sensor.b"]
    assert _pv_meter_list("sensor.a") == ["sensor.a"]
    assert _pv_meter_list(None) == []


# --- parsing ---------------------------------------------------------------------


def test_parse_gti_buckets_by_local_day_and_drops_partial_days():
    day1, day2 = TODAY, TODAY + timedelta(days=1)
    js = _om_response({day1: _bell(500), day2: _bell(300)})
    # A partial previous day (only the last 3 hours) must be left out
    js["hourly"]["time"] = [_hour_ts(day1, 0) - 3 * 3600 + 3600 * i + 3600 for i in range(3)] + js["hourly"]["time"]
    js["hourly"]["global_tilted_irradiance"] = [0.0, 0.0, 0.0] + js["hourly"]["global_tilted_irradiance"]
    daily, series = sl.parse_gti(js, ATHENS)
    assert set(daily) == {day1.isoformat(), day2.isoformat()}
    assert daily[day1.isoformat()] == pytest.approx(sum(_bell(500)), abs=0.1)
    # Series items are (hour start, Wh/m2): the first full-day item starts at local midnight
    assert series[3][0] == _hour_ts(day1, 0)


def test_parse_gti_ignores_bad_values():
    js = {"hourly": {"time": [1, "x", 3], "global_tilted_irradiance": [None, 5, float("nan")]}}
    assert sl.parse_gti(js, ATHENS) == ({}, [])


def _rows(day: date, per_hour: float, hours: int = 24) -> list[dict]:
    return [{"start": _hour_ts(day, h), "change": per_hour} for h in range(hours)]


def test_actual_daily_kwh_sums_meters_and_converts_units():
    d1 = TODAY - timedelta(days=2)
    rows = {"sensor.a": _rows(d1, 0.5), "sensor.b": _rows(d1, 250.0)}
    out = sl.actual_daily_kwh(rows, {"sensor.a": "kWh", "sensor.b": "Wh"}, ATHENS, TODAY)
    assert out == {d1.isoformat(): pytest.approx(12.0 + 6.0)}


def test_actual_daily_kwh_drops_incomplete_days_today_and_resets():
    d1, d2 = TODAY - timedelta(days=2), TODAY - timedelta(days=1)
    rows_a = _rows(d1, 0.5, hours=10) + _rows(d2, 0.5) + _rows(TODAY, 0.5, hours=5)
    rows_a[-6]["change"] = -5000.0  # a counter reset on d2 is ignored, not subtracted
    out = sl.actual_daily_kwh({"sensor.a": rows_a}, {"sensor.a": "kWh"}, ATHENS, TODAY)
    assert set(out) == {d2.isoformat()}
    assert out[d2.isoformat()] == pytest.approx(0.5 * 23)


def test_actual_daily_kwh_needs_every_meter():
    d1 = TODAY - timedelta(days=1)
    rows = {"sensor.a": _rows(d1, 0.5), "sensor.b": _rows(d1, 0.5, hours=4)}
    assert sl.actual_daily_kwh(rows, {"sensor.a": "kWh", "sensor.b": "kWh"}, ATHENS, TODAY) == {}


# --- state ----------------------------------------------------------------------


def test_state_round_trip_and_junk_tolerance():
    st = sl.SolarLocalState.from_dict(
        {"days": {"2026-11-01": {"gti": 4000, "actual": 20, "junk": 1}, 5: {}, "x": "y"}, "meters": ["sensor.a"]}
    )
    assert st.days == {"2026-11-01": {"gti": 4000.0, "actual": 20.0}}
    assert sl.SolarLocalState.from_dict(st.to_dict()).to_dict() == st.to_dict()
    assert sl.SolarLocalState.from_dict(None).days == {}


def test_reset_for_meters_forgets_actuals_only():
    st = sl.SolarLocalState()
    st.meters = ["sensor.a"]
    st.backfilled = True
    st.days = {"2026-11-01": {"gti": 4000.0, "actual": 20.0, "da_local": 19.0}}
    assert st.reset_for_meters(["sensor.a"]) is False
    assert st.reset_for_meters(["sensor.a", "sensor.b"]) is True
    assert st.days == {"2026-11-01": {"gti": 4000.0, "da_local": 19.0}}
    assert st.backfilled is False


def test_prune_keeps_recent_days():
    st = sl.SolarLocalState()
    st.set_value((TODAY - timedelta(days=sl.KEEP_DAYS + 1)).isoformat(), "gti", 1.0)
    st.set_value((TODAY - timedelta(days=3)).isoformat(), "gti", 1.0)
    st.prune(TODAY)
    assert list(st.days) == [(TODAY - timedelta(days=3)).isoformat()]


# --- model ------------------------------------------------------------------------


def _state_with(pairs: list[tuple[float, float]]) -> sl.SolarLocalState:
    st = sl.SolarLocalState()
    for i, (gti, actual) in enumerate(pairs, start=1):
        day = (TODAY - timedelta(days=i)).isoformat()
        st.set_value(day, "gti", gti)
        st.set_value(day, "actual", actual)
    return st


def test_fit_uses_prior_without_data():
    k, n, status = sl.fit_factor(sl.SolarLocalState(), sl.prior_factor(5.0), TODAY)
    assert (k, n, status) == (pytest.approx(4.0), 0, sl.STATUS_PRIOR)


def test_fit_learns_site_factor_and_drops_curtailed_days():
    # True site factor 6.0 kWh per kWh/m2; one curtailed day and one meter outage-like day
    pairs = [(g, 6.0 * g / 1000) for g in (3000, 3500, 4000, 4200, 2800, 3900, 4100, 3600)]
    pairs += [(4500, 9.0), (3800, 40.0)]
    k, n, status = sl.fit_factor(_state_with(pairs), sl.prior_factor(5.0), TODAY)
    assert status == sl.STATUS_TRAINED
    assert n == 8
    assert k == pytest.approx(6.0, rel=1e-6)


def test_fit_shrinks_toward_prior_while_learning():
    pairs = [(4000, 24.0), (4000, 24.0)]
    k, n, status = sl.fit_factor(_state_with(pairs), 4.0, TODAY)
    assert status == sl.STATUS_LEARNING and n == 2
    assert k == pytest.approx((2 * 6.0 + 3 * 4.0) / 5)


def test_fit_ignores_dark_days_and_today():
    st = _state_with([(100, 0.2)] * 10)
    st.set_value(TODAY.isoformat(), "gti", 4000)
    st.set_value(TODAY.isoformat(), "actual", 5)
    assert sl.fit_factor(st, 4.0, TODAY)[2] == sl.STATUS_PRIOR


def test_predict_and_hourly_and_remaining():
    assert sl.predict_kwh(6.0, 4000.0) == 24.0
    assert sl.predict_kwh(6.0, None) is None
    series = [(_hour_ts(TODAY, h), wh) for h, wh in enumerate(_bell(500))]
    series += [(_hour_ts(TODAY + timedelta(days=1), h), wh) for h, wh in enumerate(_bell(500))]
    hourly = sl.hourly_kwh(6.0, series, ATHENS, TODAY, TODAY + timedelta(days=1))
    assert len(hourly) == 48
    total_today = sum(h["kwh"] for h in hourly[:24])
    # Before sunrise everything is still to come; halfway through 12:00 half that hour is left
    assert sl.remaining_kwh(hourly, datetime(2026, 11, 20, 5, tzinfo=ATHENS)) == pytest.approx(total_today, abs=0.01)
    noon = datetime(2026, 11, 20, 12, 30, tzinfo=ATHENS)
    expected = hourly[12]["kwh"] / 2 + sum(h["kwh"] for h in hourly[13:24])
    assert sl.remaining_kwh(hourly, noon.astimezone(UTC)) == pytest.approx(expected, abs=0.01)
    assert sl.remaining_kwh(hourly, datetime(2026, 11, 20, 23, 30, tzinfo=ATHENS)) == 0.0
    assert sl.remaining_kwh([], noon) is None


def test_skill_compares_both_sources_on_the_same_days():
    st = sl.SolarLocalState()
    for i in range(1, 9):
        day = (TODAY - timedelta(days=i)).isoformat()
        actual = 10.0 + i
        st.set_value(day, "actual", actual)
        st.set_value(day, "da_local", actual + 1.0)
        if i <= 6:
            st.set_value(day, "da_fs", actual * 1.5)
    # A same-day record never counts
    st.set_value(TODAY.isoformat(), "actual", 1.0)
    st.set_value(TODAY.isoformat(), "da_local", 99.0)
    out = sl.skill(st, TODAY)
    assert out["local"]["days"] == out["forecast_solar"]["days"] == 6
    assert out["local"]["bias_kwh"] == 1.0 and out["local"]["mae_kwh"] == 1.0
    assert out["local"]["correlation"] == 1.0
    assert out["forecast_solar"]["bias_kwh"] > 5


def test_skill_needs_enough_days():
    st = sl.SolarLocalState()
    st.set_value((TODAY - timedelta(days=1)).isoformat(), "actual", 10.0)
    st.set_value((TODAY - timedelta(days=1)).isoformat(), "da_local", 11.0)
    assert sl.skill(st, TODAY) == {"local": None, "forecast_solar": None}


# --- wiring -----------------------------------------------------------------------


def test_store_is_removed_with_the_entry():
    assert sl.store_key("abc") in entry_storage_keys("abc")


def test_sensors_need_the_toggle_and_a_pv_meter():
    on = {c.CONF_ENABLE_SOLAR_FORECAST: True}
    meters = {**on, c.CONF_SOLAR_PV_ENERGY_ENTITIES: ["sensor.pv"]}
    for key in (c.KEY_SOLAR_LOCAL_TODAY_KWH, c.KEY_SOLAR_LOCAL_TOMORROW_KWH, c.KEY_SOLAR_LOCAL_REMAINING_KWH):
        assert not station_supports(key, on, {})
        assert not sensor_selected(key, on, {})
        assert sensor_selected(key, meters, {})
        assert not sensor_selected(key, {c.CONF_SOLAR_PV_ENERGY_ENTITIES: ["sensor.pv"]}, {})
    # The forecast.solar sensors are unchanged: the toggle alone creates them
    assert sensor_selected(c.KEY_SOLAR_FORECAST_TODAY_KWH, on, {})


# --- runtime ----------------------------------------------------------------------


def _coord(solar_cache=None):
    coord = SimpleNamespace(
        hass=MagicMock(),
        forecast_lat=37.9,
        forecast_lon=23.7,
        solar_panel_tilt=30,
        solar_panel_azimuth=180,
        solar_peak_kw=5.0,
        _solar_cache=solar_cache,
        async_request_refresh=AsyncMock(),
        async_update_listeners=MagicMock(),
    )
    coord.hass.config.components = {"recorder"}
    return coord


async def _run_update(rt, js, rows, units, now):
    rt.store = MagicMock(async_save=AsyncMock())
    executor = MagicMock(async_add_executor_job=AsyncMock(return_value=(rows, units)))
    with (
        patch.object(rt, "_async_fetch_gti", AsyncMock(return_value=js)) as fetch,
        patch("custom_components.ws_core.history_backfill._recorder_instance", return_value=executor),
        patch("custom_components.ws_core.solar_local_runtime.dt_util.get_default_time_zone", return_value=ATHENS),
        patch("custom_components.ws_core.solar_local_runtime.dt_util.now", return_value=now),
    ):
        await rt.async_update()
    return fetch


async def test_runtime_backfills_learns_and_snapshots_day_ahead():
    now = datetime(2026, 11, 20, 20, 0, tzinfo=ATHENS)
    past = [TODAY - timedelta(days=i) for i in range(10, 0, -1)]
    days = {d: _bell(450) for d in past}
    days[TODAY] = _bell(400)
    days[TODAY + timedelta(days=1)] = _bell(500)
    js = _om_response(days)
    gti_day = sum(_bell(450))
    # Measured: site factor 6 kWh per kWh/m2, spread over the daylight hours
    rows = {"sensor.pv": [r for d in past for r in _rows(d, 6.0 * gti_day / 1000 / 24)]}
    fs = {"tomorrow_kwh": 20.0, "fetched_at": datetime(2026, 11, 20, 15, tzinfo=UTC).isoformat()}
    rt = SolarLocalRuntime(_coord(fs), ["sensor.pv"])
    fetch = await _run_update(rt, js, rows, {"sensor.pv": "kWh"}, now)

    fetch.assert_awaited_once_with(sl.BACKFILL_DAYS)
    assert rt.state.backfilled is True
    assert rt.status == sl.STATUS_TRAINED and rt.n_days == 10
    assert rt.k == pytest.approx(6.0, rel=1e-3)
    assert rt.tomorrow_kwh == pytest.approx(6.0 * sum(_bell(500)) / 1000, abs=0.02)
    tomorrow = rt.state.days[(TODAY + timedelta(days=1)).isoformat()]
    assert tomorrow["da_local"] == rt.tomorrow_kwh
    assert tomorrow["da_fs"] == 20.0
    rt.store.async_save.assert_awaited_once()
    rt.coord.async_request_refresh.assert_awaited_once()

    data: dict = {}
    rt.apply(data, now.astimezone(UTC))
    assert data[c.KEY_SOLAR_LOCAL_TODAY_KWH] == rt.today_kwh
    assert data[c.KEY_SOLAR_LOCAL_REMAINING_KWH] == 0.0  # 20:00, the sun is down
    info = data[c.KEY_SOLAR_LOCAL_INFO]
    assert info["model_status"] == sl.STATUS_TRAINED and len(info["hourly"]) == 48
    assert "latitude" not in str(rt.summary())

    # The next refresh only asks for the last day
    fetch = await _run_update(rt, js, rows, {"sensor.pv": "kWh"}, now)
    fetch.assert_awaited_once_with(1)


async def test_runtime_ignores_stale_forecast_solar_and_non_energy_meters():
    now = datetime(2026, 11, 20, 20, 0, tzinfo=ATHENS)
    js = _om_response({TODAY: _bell(400), TODAY + timedelta(days=1): _bell(500)})
    fs = {"tomorrow_kwh": 20.0, "fetched_at": datetime(2026, 11, 18, 15, tzinfo=UTC).isoformat()}
    rt = SolarLocalRuntime(_coord(fs), ["sensor.pv"])
    await _run_update(rt, js, {"sensor.pv": _rows(TODAY - timedelta(days=1), 1.0)}, {"sensor.pv": "W"}, now)
    assert rt.meter_problem == "not_an_energy_meter"
    assert rt.state.backfilled is False  # retried with a backfill on the next refresh
    assert rt.status == sl.STATUS_PRIOR and rt.k == pytest.approx(4.0)
    assert "da_fs" not in rt.state.days[(TODAY + timedelta(days=1)).isoformat()]


async def test_runtime_keeps_last_values_when_fetch_fails():
    rt = SolarLocalRuntime(_coord(), ["sensor.pv"])
    rt.store = MagicMock(async_save=AsyncMock())
    with patch.object(rt, "_async_fetch_gti", AsyncMock(return_value=None)):
        await rt.async_update()
    data: dict = {}
    rt.apply(data, datetime.now(UTC))
    assert data == {}  # nothing learned yet: the sensors stay unknown with a reason
    rt.store.async_save.assert_not_awaited()


def _construct(options: dict):
    from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

    from custom_components.ws_core.coordinator import WSStationCoordinator

    with patch.object(DataUpdateCoordinator, "__init__", lambda self, *a, **kw: None):
        return WSStationCoordinator(MagicMock(), {"entry_id": "abc"}, options)


def test_coordinator_creates_runtime_only_with_toggle_and_meters():
    on = {c.CONF_ENABLE_SOLAR_FORECAST: True}
    assert _construct(on)._solar_local is None
    assert _construct({c.CONF_SOLAR_PV_ENERGY_ENTITIES: ["sensor.pv"]})._solar_local is None
    coord = _construct({**on, c.CONF_SOLAR_PV_ENERGY_ENTITIES: "sensor.pv"})
    assert isinstance(coord._solar_local, SolarLocalRuntime)
    assert coord._solar_local.meters == ["sensor.pv"]
