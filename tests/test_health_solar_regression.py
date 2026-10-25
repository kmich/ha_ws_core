"""Regressions for station readiness and period-aligned solar ET0."""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from custom_components.ws_core.const import (
    ET0_RADIATION_SOURCE_SENSOR,
    KEY_DATA_QUALITY,
    KEY_DATA_QUALITY_SCORE,
    KEY_ET0_PM_COVERAGE,
    KEY_ET0_PM_DAILY_MM,
    KEY_ET0_PM_PERIOD,
    KEY_ET0_PM_REASON,
    KEY_HEALTH_DISPLAY,
    KEY_MAX_SOLAR_RADIATION,
    KEY_NORM_HUMIDITY,
    KEY_NORM_TEMP_C,
    KEY_NORM_WIND_SPEED_MS,
    KEY_PACKAGE_OK,
    KEY_PACKAGE_STATUS,
    KEY_PEAK_SUN_HOURS,
    KEY_SENSOR_DRIFT_FLAGS,
    KEY_SOLAR_ENERGY_TODAY_WHM2,
    SRC_SOLAR_RADIATION,
)
from tests.test_coordinator import _make_coordinator, _make_state


def _at(now):
    return patch.object(dt_util, "now", return_value=now)


def _full_coord():
    from custom_components.ws_core.coordinator import WSStationCoordinator

    base = _make_coordinator()
    with patch.object(DataUpdateCoordinator, "__init__", return_value=None):
        return WSStationCoordinator(base.hass, base.entry_data)


def test_all_required_sources_missing_are_not_perfect_quality():
    coord = _full_coord()
    coord.sources = {}
    with patch.object(dt_util, "utcnow", return_value=datetime.now(UTC)):
        data = coord._compute(sample=False)
    assert data[KEY_PACKAGE_OK] is False
    assert "Missing mappings" in data[KEY_PACKAGE_STATUS]
    assert data[KEY_HEALTH_DISPLAY] != "online"
    assert data[KEY_DATA_QUALITY_SCORE] < 100
    assert "missing" in data[KEY_DATA_QUALITY].lower()


def test_one_missing_source_and_stale_numeric_source_report_degraded():
    coord = _full_coord()
    coord.sources.pop("humidity")
    data = coord._compute(sample=False)
    assert data[KEY_DATA_QUALITY_SCORE] < 100
    assert data[KEY_HEALTH_DISPLAY] != "online"

    coord = _full_coord()
    stale = coord.hass.states.get("sensor.temp")
    stale.last_updated = datetime.now(UTC) - timedelta(hours=2)
    data = coord._compute(sample=False)
    assert data[KEY_DATA_QUALITY_SCORE] < 100
    assert "Stale: temp" in data[KEY_PACKAGE_STATUS]
    assert data[KEY_HEALTH_DISPLAY] != "online"


def test_healthy_sources_and_drift_details_have_consistent_score():
    coord = _full_coord()
    data = coord._compute(sample=False)
    assert data[KEY_DATA_QUALITY_SCORE] == 100
    assert data[KEY_SENSOR_DRIFT_FLAGS] == "ok"

    coord._drift_result = ("warning", [{"sensor": "temperature", "direction": "rising"}])
    data = coord._compute(sample=False)
    assert data[KEY_SENSOR_DRIFT_FLAGS] == "warning"
    assert data[KEY_DATA_QUALITY_SCORE] == 90
    assert "drift" in data[KEY_DATA_QUALITY].lower()


def test_combined_missing_stale_and_drift_reasons_are_public():
    coord = _full_coord()
    coord.sources.pop("humidity")
    coord.hass.states.get("sensor.temp").last_updated = datetime.now(UTC) - timedelta(hours=2)
    coord._drift_result = ("warning", [{"sensor": "pressure", "direction": "rising"}])
    data = coord._compute(sample=False)
    assert data["configuration_ready"] is False
    assert data["source_healthy"] is False
    assert data["model_ready"] is False
    assert "missing mappings" in data[KEY_DATA_QUALITY]
    assert "stale readings" in data[KEY_DATA_QUALITY]
    assert "sensor drift" in data[KEY_DATA_QUALITY]
    assert data[KEY_DATA_QUALITY_SCORE] < 70


def test_solar_accumulates_without_temperature_range():
    coord = _full_coord()
    coord.forecast_lat = 37.9
    coord.sources[SRC_SOLAR_RADIATION] = "sensor.solar"
    state = _make_state("500", "W/m²")
    old_get = coord.hass.states.get
    coord.hass.states.get = lambda eid: state if eid == "sensor.solar" else old_get(eid)
    now = datetime(2026, 7, 1, 12, tzinfo=UTC)
    coord._solar_energy_date = "2026-07-01"
    coord._solar_energy_last_ts = now - timedelta(minutes=1)
    with _at(now):
        data = {KEY_NORM_TEMP_C: 25.0, KEY_NORM_HUMIDITY: 50.0}
        coord._compute_et0(data, now)
    assert data[KEY_SOLAR_ENERGY_TODAY_WHM2] == 8
    assert data[KEY_PEAK_SUN_HOURS] == 0.01
    assert KEY_MAX_SOLAR_RADIATION in data


def test_constant_temperature_still_accumulates_and_republish_does_not_sample():
    coord = _full_coord()
    coord.forecast_lat = 37.9
    coord.sources[SRC_SOLAR_RADIATION] = "sensor.solar"
    old_get = coord.hass.states.get
    coord.hass.states.get = lambda eid: _make_state("500") if eid == "sensor.solar" else old_get(eid)
    start = datetime(2026, 7, 1, 12, tzinfo=UTC)
    with _at(start):
        coord._compute_et0({"temp_high_24h": 20.0, "temp_low_24h": 20.0}, start)
    later = start + timedelta(minutes=1)
    with _at(later):
        data = {"temp_high_24h": 20.0, "temp_low_24h": 20.0}
        coord._compute_et0(data, later)
        before = coord._solar_energy_today_whm2
        coord._compute_et0({}, later + timedelta(seconds=30), sample=False)
    assert data[KEY_SOLAR_ENERGY_TODAY_WHM2] == 8
    assert coord._solar_energy_today_whm2 == before


def test_zero_to_positive_radiation_uses_previous_zero_in_trapezoid():
    coord = _full_coord()
    coord.sources[SRC_SOLAR_RADIATION] = "sensor.solar"
    state = _make_state("0")
    old_get = coord.hass.states.get
    coord.hass.states.get = lambda eid: state if eid == "sensor.solar" else old_get(eid)
    start = datetime(2026, 7, 1, 6, tzinfo=UTC)
    coord._compute_solar_energy({}, start, None, True)
    state.state = "600"
    coord._compute_solar_energy({}, start + timedelta(minutes=1), None, True)
    assert coord._solar_energy_today_whm2 == pytest.approx(5.0)
    assert coord._solar_today_meta["energy_whm2"] == pytest.approx(5.0)


def test_stale_numeric_radiation_breaks_coverage():
    coord = _full_coord()
    coord.sources[SRC_SOLAR_RADIATION] = "sensor.solar"
    start = datetime(2026, 7, 1, 6, tzinfo=UTC)
    state = _make_state("400", last_updated=start)
    state.last_reported = start
    old_get = coord.hass.states.get
    coord.hass.states.get = lambda eid: state if eid == "sensor.solar" else old_get(eid)
    coord._compute_solar_energy({}, start, None, True)
    coord._compute_solar_energy({}, start + timedelta(minutes=16), None, True)
    assert coord._solar_energy_last_ts is None
    assert coord._solar_today_meta["coverage_s"] == 0.0


def test_old_positive_irradiation_does_not_make_daily_pm():
    coord = _full_coord()
    coord.forecast_lat = 37.9
    coord.sources[SRC_SOLAR_RADIATION] = "sensor.solar"
    coord._solar_energy_previous_date = "2026-07-01"
    coord._solar_energy_previous_whm2 = 5000.0
    with _at(datetime(2026, 7, 8, 12, tzinfo=UTC)):
        data = coord._compute(sample=False)
    assert data.get(KEY_ET0_PM_DAILY_MM) is None
    assert data[KEY_ET0_PM_REASON] == "stale stored irradiation"


def _covered_meta(day="2026-07-01", hours=23.0, radiation_source=ET0_RADIATION_SOURCE_SENSOR):
    seconds = hours * 3600
    return {
        "schema": 1,
        "date": day,
        "energy_whm2": 4800.0,
        "coverage_s": seconds,
        "met_coverage_s": seconds,
        "temp_sum": 20.0 * seconds,
        "humidity_sum": 55.0 * seconds,
        "wind_sum": 2.0 * seconds,
        "temp_min": 14.0,
        "temp_max": 26.0,
        "source": radiation_source,
        "gaps": 0,
    }


def _pm_coord():
    coord = _full_coord()
    coord.forecast_lat = 37.9
    coord.sources[SRC_SOLAR_RADIATION] = "sensor.solar"
    coord._solar_energy_previous_date = "2026-07-01"
    coord._solar_energy_previous_whm2 = 4800.0
    coord._solar_previous_meta = _covered_meta()
    return coord


def test_completed_day_pm_uses_same_period_inputs_and_numerical_reference():
    coord = _pm_coord()
    # Current conditions deliberately differ from yesterday's averages.
    data = {KEY_NORM_TEMP_C: -5.0, KEY_NORM_HUMIDITY: 99.0, KEY_NORM_WIND_SPEED_MS: 12.0}
    coord._compute_daily_pm(data, datetime(2026, 7, 2, 12, tzinfo=UTC))
    assert data[KEY_ET0_PM_DAILY_MM] == pytest.approx(3.984, abs=0.001)
    assert data[KEY_ET0_PM_PERIOD] == "2026-07-01"
    assert data[KEY_ET0_PM_COVERAGE] == pytest.approx(23 / 24, abs=0.001)
    assert data[KEY_ET0_PM_REASON] == "ok"


@pytest.mark.parametrize(
    "hours,reason",
    [
        (10.0, "insufficient solar coverage"),
        (0.0, "insufficient solar coverage"),
    ],
)
def test_partial_or_absent_coverage_rejects_positive_irradiation(hours, reason):
    coord = _pm_coord()
    coord._solar_previous_meta = _covered_meta(hours=hours)
    data = {}
    coord._compute_daily_pm(data, datetime(2026, 7, 2, 12, tzinfo=UTC))
    assert data.get(KEY_ET0_PM_DAILY_MM) is None
    assert data[KEY_ET0_PM_REASON] == reason


def test_zero_radiation_is_valid_when_observed_all_day():
    coord = _pm_coord()
    coord._solar_energy_previous_whm2 = 0.0
    coord._solar_previous_meta["energy_whm2"] = 0.0
    data = {}
    coord._compute_daily_pm(data, datetime(2026, 7, 2, 12, tzinfo=UTC))
    assert data[KEY_ET0_PM_DAILY_MM] is not None
    assert data[KEY_ET0_PM_REASON] == "ok"


def test_missing_weather_coverage_and_mixed_radiation_are_explained():
    coord = _pm_coord()
    coord._solar_previous_meta["met_coverage_s"] = 3600.0
    data = {}
    coord._compute_daily_pm(data, datetime(2026, 7, 2, 12, tzinfo=UTC))
    assert "same-day" in data[KEY_ET0_PM_REASON]
    coord._solar_previous_meta = _covered_meta(radiation_source="mixed")
    data = {}
    coord._compute_daily_pm(data, datetime(2026, 7, 2, 12, tzinfo=UTC))
    assert data[KEY_ET0_PM_REASON] == "mixed or unknown radiation source"


def test_previous_day_expires_and_dst_day_length_is_local():
    coord = _pm_coord()
    data = {}
    coord._compute_daily_pm(data, datetime(2026, 7, 3, 12, tzinfo=UTC))
    assert data[KEY_ET0_PM_REASON] == "stale stored irradiation"

    athens = ZoneInfo("Europe/Athens")
    for day, next_day, covered_hours, expected_fraction in (
        ("2026-03-29", datetime(2026, 3, 30, 12, tzinfo=UTC), 22.0, 22 / 23),
        ("2026-10-25", datetime(2026, 10, 26, 12, tzinfo=UTC), 24.0, 24 / 25),
    ):
        coord._solar_energy_previous_date = day
        coord._solar_previous_meta = _covered_meta(day=day, hours=covered_hours)
        data = {}
        with patch.object(dt_util, "as_local", side_effect=lambda value: value.astimezone(athens)):
            coord._compute_daily_pm(data, next_day)
        assert data[KEY_ET0_PM_COVERAGE] == pytest.approx(expected_fraction, abs=0.001)
        assert data[KEY_ET0_PM_REASON] == "ok"


def test_source_outage_breaks_interval_and_multi_day_gap_discards_yesterday():
    coord = _pm_coord()
    coord._solar_energy_date = "2026-07-01"
    coord._solar_today_meta = _covered_meta()
    coord._solar_energy_today_whm2 = 4800.0
    coord._solar_energy_last_ts = datetime(2026, 7, 1, 23, 55, tzinfo=UTC)
    coord._solar_last_value = 200.0
    unavailable = _make_state("unavailable")
    coord.hass.states.get = lambda eid: unavailable if eid == "sensor.solar" else None
    coord._compute_solar_energy({}, datetime(2026, 7, 2, 0, 1, tzinfo=UTC), None, True)
    assert coord._solar_energy_previous_date == "2026-07-01"
    assert coord._solar_energy_last_ts is None
    coord._compute_solar_energy({}, datetime(2026, 7, 4, 0, 1, tzinfo=UTC), None, True)
    assert coord._solar_energy_previous_date == ""
    assert coord._solar_energy_previous_whm2 == 0.0


def test_nonsampling_republish_does_not_roll_day_or_break_interval():
    coord = _full_coord()
    coord.sources[SRC_SOLAR_RADIATION] = "sensor.solar"
    old_get = coord.hass.states.get
    coord.hass.states.get = lambda eid: _make_state("unavailable") if eid == "sensor.solar" else old_get(eid)
    coord._solar_energy_date = "2026-07-01"
    coord._solar_energy_today_whm2 = 4800.0
    coord._solar_today_meta = _covered_meta()
    last = datetime(2026, 7, 1, 23, 59, tzinfo=UTC)
    coord._solar_energy_last_ts = last
    coord._solar_last_value = 200.0
    coord._compute_solar_energy({}, datetime(2026, 7, 2, 0, 1, tzinfo=UTC), None, False)
    assert coord._solar_energy_date == "2026-07-01"
    assert coord._solar_energy_previous_date == ""
    assert coord._solar_energy_last_ts == last
    coord._compute_solar_energy({}, datetime(2026, 7, 1, 23, 59, 30, tzinfo=UTC), None, False)
    assert coord._solar_energy_last_ts == last


def test_storage_migration_rejects_legacy_partial_day_and_restores_covered_day():
    at = datetime(2026, 7, 2, 1, tzinfo=UTC)
    legacy = {"solar_energy_date": "2026-07-01", "solar_energy_today_whm2": 10.0}
    coord = _full_coord()
    with _at(at):
        coord._restore_history_state(legacy)
    assert coord._solar_energy_previous_whm2 == 10.0
    assert coord._solar_previous_meta == {}

    covered = dict(
        legacy, solar_today_meta=_covered_meta(), solar_last_value=200.0, solar_last_ts="2026-07-01T23:59:00+00:00"
    )
    restarted = _full_coord()
    with _at(at):
        restarted._restore_history_state(covered)
    assert restarted._solar_previous_meta["date"] == "2026-07-01"
    assert restarted._solar_energy_previous_whm2 == 10.0

    corrupted = dict(covered, solar_today_meta={**_covered_meta(), "coverage_s": "bad"})
    rejected = _full_coord()
    with _at(at):
        rejected._restore_history_state(corrupted)
    assert rejected._solar_previous_meta == {}
