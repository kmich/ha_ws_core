"""Regression tests for the 2.8.0 correctness, robustness and accuracy fixes."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.ws_core import coordinator as cmod
from custom_components.ws_core.algorithms import (
    calculate_dew_point,
    calculate_frost_point,
    calculate_us_aqi,
    compute_fwi,
    et0_hourly_estimate,
    fwi_indices,
)
from custom_components.ws_core.const import (
    CONF_ENABLE_SOIL,
    KEY_ET0_DAILY_MM,
    KEY_FWI_DC,
    KEY_FWI_DMC,
    KEY_IRRIGATION_NEED,
    KEY_NORM_HUMIDITY,
    KEY_NORM_PRESSURE_HPA,
    KEY_NORM_RAIN_TOTAL_MM,
    KEY_NORM_TEMP_C,
    KEY_NORM_WIND_GUST_MS,
    KEY_RAIN_ACCUM_24H,
    KEY_RAIN_TODAY_MM,
    KEY_SENSOR_STUCK,
    KEY_SOIL_MOISTURE,
    SRC_TEMP,
)
from custom_components.ws_core.coordinator import WSStationCoordinator, _redact_secrets
from custom_components.ws_core.learning_state import LearningState
from tests.test_coordinator import _make_coordinator

T0 = datetime(2026, 1, 10, tzinfo=UTC)


def _at(when: datetime):
    return patch.object(cmod.dt_util, "now", return_value=when)


# ---------------------------------------------------------------------------
# Stuck-sensor detection (previously dead code: state lived on a fresh dict)
# ---------------------------------------------------------------------------


class TestStuckDetection:
    @staticmethod
    def _cycle(coord, minutes: float, temp: float, hum: float, press: float) -> dict:
        data = {KEY_NORM_TEMP_C: temp, KEY_NORM_HUMIDITY: hum, KEY_NORM_PRESSURE_HPA: press}
        coord._compute_data_quality_score(data, T0 + timedelta(minutes=minutes))
        return data

    def test_identical_readings_over_minutes_are_not_stuck(self):
        coord = _make_coordinator()
        for i in range(20):
            data = self._cycle(coord, i * 0.5, 20.0, 55.0, 1013.0)
        assert data[KEY_SENSOR_STUCK] == []

    def test_value_frozen_for_hours_is_stuck(self):
        coord = _make_coordinator()
        for i in range(0, 5 * 60, 10):
            data = self._cycle(coord, i, 20.0, 50.0 + (i % 20), 1000.0 + i * 0.01)
        assert data[KEY_SENSOR_STUCK] == [SRC_TEMP]
        assert data["_temp_stuck"] is True
        assert data["_humidity_stuck"] is False

    def test_movement_resets_the_clock(self):
        coord = _make_coordinator()
        for i in range(0, 5 * 60, 10):
            temp = 20.0 if i < 200 else 21.0
            data = self._cycle(coord, i, temp, 50.0 + (i % 20), 1000.0 + i * 0.01)
        assert data[KEY_SENSOR_STUCK] == []

    def test_saturated_humidity_is_never_stuck(self):
        coord = _make_coordinator()
        for i in range(0, 10 * 60, 10):
            data = self._cycle(coord, i, 10.0 + i * 0.01, 100.0, 1000.0 + i * 0.01)
        assert data[KEY_SENSOR_STUCK] == []


# ---------------------------------------------------------------------------
# Degree-day seasons
# ---------------------------------------------------------------------------


class TestDegreeDaySeasons:
    @staticmethod
    def _coord():
        coord = _make_coordinator()
        coord.degree_days_enabled = True
        return coord

    @staticmethod
    def _run_day(coord, day: datetime, temp: float, samples: int = 24) -> None:
        for h in range(samples):
            now = day + timedelta(hours=h)
            with _at(now):
                coord._compute_degree_days({}, now, temp, None, None)

    def test_season_receives_completed_day_not_first_sample(self):
        coord = self._coord()
        self._run_day(coord, T0, 8.0)  # HDD = 18 - 8 = 10 all day
        self._run_day(coord, T0 + timedelta(days=1), 15.0, samples=1)
        assert coord._hdd_season == pytest.approx(10.0)

    def test_cdd_season_resets_on_new_year(self):
        coord = self._coord()
        coord._cdd_season = 500.0
        coord._cdd_season_key = "2025"
        self._run_day(coord, datetime(2025, 12, 31, tzinfo=UTC), 28.0)
        self._run_day(coord, datetime(2026, 1, 1, tzinfo=UTC), 20.0, samples=1)
        assert coord._cdd_season_key == "2026"
        assert coord._cdd_season == pytest.approx(0.0)

    def test_restart_across_midnight_folds_saved_day(self):
        coord = self._coord()
        after_midnight = datetime(2026, 1, 11, 1, tzinfo=UTC)
        with _at(after_midnight), patch.object(cmod.dt_util, "utcnow", return_value=after_midnight):
            coord._restore_history_state(
                {
                    "hdd_today": 10.0,
                    "hdd_today_date": "2026-01-10",
                    "hdd_today_samples": 100,
                    "hdd_season": 40.0,
                    "hdd_season_key": "2026",
                }
            )
        self._run_day(coord, after_midnight, 15.0, samples=1)
        assert coord._hdd_season == pytest.approx(50.0)


# ---------------------------------------------------------------------------
# History restore / rain-today ordering
# ---------------------------------------------------------------------------


def test_restore_keeps_configured_pressure_window():
    coord = _make_coordinator()
    coord._pressure_history_samples = 24  # 6h window at 15-min sampling
    coord._restore_history_state({"pressure_history": [1000.0] * 30})
    assert coord.runtime.pressure_history.maxlen == 24
    assert len(coord.runtime.pressure_history) == 24


def test_irrigation_score_sees_rain_today():
    coord = _make_coordinator()
    coord.entry_options = {CONF_ENABLE_SOIL: True}
    now = datetime(2026, 6, 1, 12, tzinfo=UTC)
    coord._rain_today_date = "2026-06-01"
    coord._rain_today_mm = 0.0
    coord._rain_today_last_total = 5.0
    data: dict = {KEY_NORM_RAIN_TOTAL_MM: 10.0}
    with _at(now):
        coord._compute_derived_precipitation(data, now, 10.0)
    assert data[KEY_RAIN_TODAY_MM] == pytest.approx(5.0)

    data.update({KEY_SOIL_MOISTURE: 40.0, KEY_ET0_DAILY_MM: 5.0})
    coord._compute_soil(data)
    # 5 mm ET0 fully offset by 5 mm rain and no soil deficit -> no need
    assert data[KEY_IRRIGATION_NEED] == "none"


# ---------------------------------------------------------------------------
# Event entities are kept on the coordinator
# ---------------------------------------------------------------------------


async def test_event_platform_registers_entities_on_coordinator():
    from custom_components.ws_core import event as ev

    coord = MagicMock()
    hass = MagicMock()
    hass.data = {}
    entry = MagicMock()
    entry.entry_id = "e1"
    entry.options = {}
    entry.data = {}
    entry.runtime_data = coord
    added: list = []
    await ev.async_setup_entry(hass, entry, added.extend)

    assert hass.data == {}
    assert set(coord.event_entities) == {"WSRainEvent", "WSFrostEvent", "WSLightningEvent"}


# ---------------------------------------------------------------------------
# Fire Weather Index timing
# ---------------------------------------------------------------------------


class TestFireWeather:
    @staticmethod
    def _coord():
        coord = _make_coordinator()
        coord.fire_risk_enabled = True
        coord._learning_state = LearningState()
        return coord

    @staticmethod
    def _run(coord, when: datetime) -> dict:
        data = {KEY_RAIN_ACCUM_24H: 0.0}
        with _at(when):
            coord._compute_fire_weather(data, 30.0, 20.0, 5.0)
        return data

    def test_codes_advance_once_at_noon_without_extra_drying(self):
        coord = self._coord()
        ls = coord._learning_state
        morning = datetime(2026, 7, 1, 9, tzinfo=UTC)

        data = self._run(coord, morning)
        assert ls.fwi_last_date == ""
        assert data[KEY_FWI_DMC] == pytest.approx(6.0)

        self._run(coord, morning.replace(hour=12, minute=5))
        assert ls.fwi_last_date == "2026-07-01"
        dmc, dc = ls.fwi_dmc, ls.fwi_dc
        assert dmc > 6.0

        for hour in (13, 16, 20, 23):
            data = self._run(coord, morning.replace(hour=hour))
            assert data[KEY_FWI_DMC] == pytest.approx(dmc)
            assert data[KEY_FWI_DC] == pytest.approx(dc)
        assert ls.fwi_dmc == pytest.approx(dmc)

    def test_fwi_indices_match_full_computation(self):
        full = compute_fwi(85.0, 6.0, 15.0, 25.0, 40.0, 20.0, 0.0, 7)
        idx = fwi_indices(full["ffmc"], full["dmc"], full["dc"], 20.0)
        for key in ("isi", "bui", "fwi"):
            assert idx[key] == pytest.approx(full[key], abs=0.2)


# ---------------------------------------------------------------------------
# ET0 timing
# ---------------------------------------------------------------------------


class TestEt0Hourly:
    def test_hours_sum_to_daily_total(self):
        assert sum(et0_hourly_estimate(5.0, h) for h in range(24)) == pytest.approx(5.0, rel=0.01)

    def test_peaks_at_solar_noon_and_zero_at_night(self):
        assert et0_hourly_estimate(5.0, 11) == pytest.approx(et0_hourly_estimate(5.0, 12))
        assert et0_hourly_estimate(5.0, 12) > et0_hourly_estimate(5.0, 8)
        assert et0_hourly_estimate(5.0, 2) == 0.0

    def test_local_solar_hour_uses_longitude(self):
        coord = _make_coordinator()
        coord.forecast_lon = -120.0
        assert coord._local_solar_hour(datetime(2026, 6, 1, 20, tzinfo=UTC)) == pytest.approx(12.0)


# ---------------------------------------------------------------------------
# Vigicrues discharge units
# ---------------------------------------------------------------------------


class _Resp:
    def __init__(self, payload):
        self.status = 200
        self._payload = payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def json(self):
        return self._payload


class _HubEauSession:
    def get(self, url, timeout=None):
        value = 12345.0 if "grandeur_hydro=Q" in url else 1500.0
        return _Resp({"data": [{"resultat_obs": value, "date_obs": "2026-01-01T00:00:00Z"}]})


async def test_vigicrues_flow_converted_from_litres_per_second():
    coord = _make_coordinator()
    coord.forecast_lat, coord.forecast_lon = 43.5, 5.5
    coord._vigicrues_stations = [{"code": "W1", "name": "Station", "river": "River"}]
    coord._vigicrues_caches = {}
    coord._vigicrues_auto_code = None
    coord.async_request_refresh = AsyncMock()
    with patch.object(cmod, "async_get_clientsession", lambda hass: _HubEauSession()):
        await coord._async_fetch_vigicrues()
    assert coord._vigicrues_caches["W1"]["level_m"] == pytest.approx(1.5)
    assert coord._vigicrues_caches["W1"]["flow_m3s"] == pytest.approx(12.345)


# ---------------------------------------------------------------------------
# Secrets, Repairs scoping, weather forecast push
# ---------------------------------------------------------------------------


def test_redact_secrets():
    msg = "401, url='https://api.example/x?appid=SECRETKEY'"
    assert "SECRETKEY" not in _redact_secrets(msg, "SECRETKEY", None, "")


async def test_owm_http_error_does_not_expose_key():
    from custom_components.ws_core.providers.open_weather_map import OpenWeatherMapProvider

    class _Session:
        def get(self, url, timeout=None):
            resp = _Resp({})
            resp.status = 502
            return resp

    with pytest.raises(ValueError) as err:
        await OpenWeatherMapProvider().async_fetch(_Session(), 1.0, 2.0, api_key="SECRETKEY")
    assert "SECRETKEY" not in str(err.value)


def test_repairs_issues_are_scoped_per_entry():
    coord = _make_coordinator()
    coord.entry_data["entry_id"] = "E1"
    with (
        patch.object(cmod.ir, "async_create_issue") as create,
        patch.object(cmod.ir, "async_delete_issue"),
    ):
        coord._compute_health({}, datetime.now(UTC), [], ["temp"])
    issue_ids = [c.args[2] for c in create.call_args_list]
    assert "missing_source_entities_E1" in issue_ids
    assert create.call_args_list[0].kwargs["translation_key"] == "missing_source_entities"


def test_weather_entity_pushes_forecast_updates():
    from custom_components.ws_core.weather import WSStationWeather

    entry = MagicMock()
    ent = WSStationWeather(MagicMock(), entry, "ws")
    ent.hass = MagicMock()
    with patch.object(WSStationWeather, "async_write_ha_state"):
        ent._handle_coordinator_update()
    entry.async_create_task.assert_called_once()
    entry.async_create_task.call_args.args[1].close()


# ---------------------------------------------------------------------------
# Accuracy fixes
# ---------------------------------------------------------------------------


class TestAccuracy:
    def test_frost_point_uses_water_referenced_humidity(self):
        fp = calculate_frost_point(-10.0, 80.0)
        assert fp == pytest.approx(-11.4, abs=0.2)
        assert fp > calculate_dew_point(-10.0, 80.0)

    def test_frost_point_equals_dew_point_above_freezing(self):
        assert calculate_frost_point(10.0, 80.0) == pytest.approx(calculate_dew_point(10.0, 80.0))

    def test_aqi_uses_2024_breakpoints_and_truncation(self):
        assert calculate_us_aqi(9.05, None) == 50
        assert calculate_us_aqi(12.0, None) > 50

    def test_gust_gets_wind_calibration(self):
        coord = _make_coordinator(wind_speed=3.5, wind_gust=6.0)
        coord.entry_options = {"cal_wind_ms": 1.0}
        data: dict = {}
        coord._compute_raw_readings(data, datetime.now(UTC))
        assert data[KEY_NORM_WIND_GUST_MS] == pytest.approx(7.0)

    def test_kpa_and_psi_pressure_units(self):
        assert WSStationCoordinator._to_hpa(101.3, "kPa") == pytest.approx(1013.0)
        assert WSStationCoordinator._to_hpa(14.7, "psi") == pytest.approx(1013.5, abs=0.1)

    def test_zero_lux_is_passed_through(self):
        coord = _make_coordinator()
        with patch.object(cmod, "determine_current_condition", return_value="cloudy") as cond:
            coord._compute_condition({}, 20.0, 50.0, 1.0, 2.0, 0.0, 10.0, 0.0, 0.0)
        assert cond.call_args.kwargs["illuminance_lx"] == 0.0
