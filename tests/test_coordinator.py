"""Tests for WSStationCoordinator compute methods.

These tests validate the coordinator's data transformation pipeline
without requiring a full Home Assistant environment. We mock the HA
state machine and test each _compute_* sub-method in isolation.
"""

import os
import sys
from collections import deque
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from homeassistant.util import dt as dt_util

from custom_components.ws_core.const import (
    CONF_CLIMATE_REGION,
    CONF_ELEVATION_M,
    CONF_FORECAST_ENABLED,
    CONF_HEMISPHERE,
    CONF_SOURCES,
    CONF_STALENESS_S,
    ET0_RADIATION_SOURCE_ILLUMINANCE_ESTIMATE,
    ET0_RADIATION_SOURCE_SENSOR,
    KEY_ALERT_STATE,
    KEY_CONDITIONS_SUMMARY,
    KEY_DATA_QUALITY,
    KEY_DEW_POINT_C,
    KEY_FEELS_LIKE_C,
    KEY_FROST_POINT_C,
    KEY_HEALTH_DISPLAY,
    KEY_NORM_TEMP_C,
    KEY_NORM_WIND_GUST_MS,
    KEY_NORM_WIND_SPEED_MS,
    KEY_NOWCAST_STALE,
    KEY_PACKAGE_OK,
    KEY_RAIN_EXPECTED_1H,
    KEY_RAIN_EXPECTED_SOURCE,
    KEY_RAIN_RATE_FILT,
    KEY_RAIN_THIS_MONTH_MM,
    KEY_RAIN_THIS_YEAR_MM,
    KEY_SEA_LEVEL_PRESSURE_HPA,
    KEY_TEMP_HIGH_ALL_TIME,
    KEY_TEMP_HIGH_MONTH,
    KEY_TEMP_HIGH_WEEK,
    KEY_TEMP_HIGH_YEAR,
    KEY_TEMP_LOW_ALL_TIME,
    KEY_TEMP_LOW_MONTH,
    KEY_TEMP_LOW_WEEK,
    KEY_TEMP_LOW_YEAR,
    KEY_TEMP_MONTH_REF,
    KEY_TEMP_WEEK_REF,
    KEY_TEMP_YEAR_REF,
    KEY_WET_BULB_C,
    KEY_WIND_BEAUFORT,
    KEY_WIND_GUST_MAX_ALL_TIME,
    KEY_WIND_GUST_MAX_MONTH,
    KEY_WIND_GUST_MAX_YEAR,
    KEY_WIND_GUST_MONTH_REF,
    KEY_WIND_GUST_YEAR_REF,
    KEY_WIND_QUADRANT,
    KEY_ZAMBRETTI_FORECAST,
    KEY_ZAMBRETTI_NUMBER,
    RAIN_EXPECTED_SOURCE_LOCAL_FALLBACK,
    RAIN_EXPECTED_SOURCE_NOWCAST,
    SRC_GUST,
    SRC_HUM,
    SRC_LUX,
    SRC_PRESS,
    SRC_RAIN_TOTAL,
    SRC_RAIN_YEAR,
    SRC_SOLAR_RADIATION,
    SRC_TEMP,
    SRC_WIND,
    SRC_WIND_DIR,
)

# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------


def _make_state(state_val: str, unit: str = "", last_updated=None):
    """Create a mock HA state object."""
    mock = MagicMock()
    mock.state = state_val
    mock.attributes = {"unit_of_measurement": unit}
    mock.last_updated = last_updated or datetime.now(UTC)
    return mock


def _make_coordinator(
    temp=22.0,
    humidity=55.0,
    pressure=1013.0,
    wind_speed=3.5,
    wind_gust=6.0,
    wind_dir=180.0,
    rain_total=5.2,
    elevation=50.0,
):
    """Create a WSStationCoordinator with mocked HA state."""
    from custom_components.ws_core.coordinator import WSStationCoordinator

    sources = {
        SRC_TEMP: "sensor.temp",
        SRC_HUM: "sensor.hum",
        SRC_PRESS: "sensor.press",
        SRC_WIND: "sensor.wind",
        SRC_GUST: "sensor.gust",
        SRC_WIND_DIR: "sensor.wind_dir",
        SRC_RAIN_TOTAL: "sensor.rain",
    }

    entry_data = {
        CONF_SOURCES: sources,
        CONF_ELEVATION_M: elevation,
        CONF_HEMISPHERE: "northern",
        CONF_CLIMATE_REGION: "mediterranean",
        CONF_STALENESS_S: 900,
        CONF_FORECAST_ENABLED: False,
    }

    hass = MagicMock()
    hass.config.latitude = 37.9
    hass.config.longitude = 23.7

    now = datetime.now(UTC)
    states = {
        "sensor.temp": _make_state(str(temp), "°C", now),
        "sensor.hum": _make_state(str(humidity), "%", now),
        "sensor.press": _make_state(str(pressure), "hPa", now),
        "sensor.wind": _make_state(str(wind_speed), "m/s", now),
        "sensor.gust": _make_state(str(wind_gust), "m/s", now),
        "sensor.wind_dir": _make_state(str(wind_dir), "°", now),
        "sensor.rain": _make_state(str(rain_total), "mm", now),
        "sun.sun": MagicMock(
            state="above_horizon",
            attributes={"elevation": 45, "azimuth": 180},
        ),
    }
    hass.states.get = lambda eid: states.get(eid)

    # Patch the DataUpdateCoordinator __init__ to avoid HA internals
    with patch.object(WSStationCoordinator, "__init__", lambda self, *a, **kw: None):
        coord = WSStationCoordinator.__new__(WSStationCoordinator)

    coord.hass = hass
    coord.entry_data = entry_data
    coord.entry_options = {}
    coord.sources = sources
    coord.units_mode = "auto"
    coord._temp_unit_conf = "auto"
    coord._wind_unit_conf = "auto"
    coord._pressure_unit_conf = "auto"
    coord._rain_unit_conf = "auto"
    coord._distance_unit_conf = "auto"
    coord._altitude_unit_conf = "auto"
    coord.elevation_m = elevation
    coord.hemisphere = "northern"
    coord.climate_region = "mediterranean"
    coord.staleness_s = 900
    coord.forecast_enabled = False
    coord.forecast_lat = None
    coord.forecast_lon = None
    coord.forecast_interval_min = 30

    # v1.5.0 comfort indices + agrometeorological accumulators
    coord.comfort_indices_enabled = True
    coord._chill_hour_base_c = 7.2
    coord._chill_season_reset_month = 7
    coord._chill_season_reset_day = 1
    coord._wind_run_km = 0.0
    coord._wind_run_date = ""
    coord._wind_run_last_ts = None
    coord._chill_hours_today = 0.0
    coord._chill_hours_today_date = ""
    coord._chill_hours_season = 0.0
    coord._chill_hours_season_date = ""
    coord._chill_hours_last_ts = None

    # v1.6.0 French regional data sources
    coord.vigilance_meteo_enabled = False
    coord._vigilance_cache = None
    coord.vigicrues_enabled = False
    coord._vigicrues_cache = None
    coord._vigicrues_station_code = None
    coord._vigicrues_station_name = None
    coord._vigicrues_river_name = None

    # v1.8.4
    coord.suppress_notifications = False
    coord._missing_sources_since = None

    # v2.0 accumulators / rolling histories (normally set in __init__, which the
    # fixture bypasses).
    from collections import deque

    coord._wind_dir_history_24h = deque()
    coord._rain_rate_history_24h = deque()
    coord._wind_run_month_km = 0.0
    coord._wind_run_month_key = ""
    coord._rain_this_week_mm = 0.0
    coord._rain_this_week_isoweek = ""
    coord._rain_this_week_last_total = None
    coord._rain_this_month_mm = 0.0
    coord._rain_this_month_key = ""
    coord._rain_this_month_last_total = None
    coord._rain_this_year_mm = 0.0
    coord._rain_this_year_key = ""
    coord._rain_this_year_last_total = None
    coord._rain_today_mm = 0.0
    coord._rain_today_date = ""
    coord._rain_today_last_total = None
    coord._rain_prev_day_date = ""
    coord._rain_prev_day_mm = 0.0
    coord._temp_high_year = None
    coord._temp_low_year = None
    coord._temp_year_key = ""
    coord._temp_high_all_time = None
    coord._temp_low_all_time = None
    coord._temp_high_week = None
    coord._temp_low_week = None
    coord._temp_week_isoweek = ""
    coord._temp_high_month = None
    coord._temp_low_month = None
    coord._temp_month_key = ""
    coord._gust_max_month = None
    coord._gust_month_key = ""
    coord._gust_max_year = None
    coord._gust_year_key = ""
    coord._gust_max_all_time = None
    coord._solar_energy_today_whm2 = 0.0
    coord._solar_energy_date = ""
    coord._solar_energy_last_ts = None
    # degree days (off by default)
    coord.degree_days_enabled = False
    coord._hdd_base_c = 18.0
    coord._cdd_base_c = 18.0
    coord._gdd_base_c = 10.0
    coord._gdd_cap_c = 30.0
    coord._hdd_today = 0.0
    coord._hdd_today_date = ""
    coord._hdd_today_samples = 0
    coord._cdd_today = 0.0
    coord._cdd_today_date = ""
    coord._cdd_today_samples = 0
    coord._gdd_today = 0.0
    coord._gdd_today_date = ""
    coord._hdd_season = 0.0
    coord._hdd_season_key = ""
    coord._cdd_season = 0.0
    coord._cdd_season_key = ""
    coord._gdd_season = 0.0
    coord._gdd_season_key = ""
    # v2.0 feature flags (off) + their state
    coord.lightning_enabled = False
    coord._lightning_proximity_km = 15.0
    coord._lightning_count_history_1h = deque()
    coord._lightning_last_count = None
    coord._lightning_last_strike_ts = None
    coord.indoor_enabled = False
    coord._indoor_temp_prev = None
    coord._indoor_hum_prev = None
    coord.weathercloud_enabled = False
    coord.pwsweather_enabled = False
    coord.wow_enabled = False
    coord.awekas_enabled = False
    coord.cwop_enabled = False
    coord.owm_stations_enabled = False
    coord.windy_enabled = False
    coord.mqtt_enabled = False
    coord._neighbor_qc_cache = None
    coord._stuck_ref = {}
    coord.event_entities = {}
    coord._spike_history = {
        "temp": deque(maxlen=48),
        "humidity": deque(maxlen=48),
        "pressure": deque(maxlen=48),
    }

    from custom_components.ws_core.coordinator import WSStationRuntime

    coord.runtime = WSStationRuntime()

    # v2.1 alert hysteresis state
    coord._alert_debounce_raw: dict = {}
    coord._alert_debounce_clear: dict = {}
    coord._alert_active: dict = {}

    # v2.7 snow (opt-in)
    coord.snow_enabled = False
    coord._snow_last_calc_ts = None
    coord._snow_today_cm = 0.0
    coord._snow_today_date = ""
    coord._snow_this_month_cm = 0.0
    coord._snow_this_month_key = ""
    coord._snow_this_year_cm = 0.0
    coord._snow_this_year_key = ""
    coord._snowiest_day_cm = 0.0
    coord._snowiest_day_date = ""

    # v2.9 solar forecast / ET0 illuminance fallback + nowcast staleness
    coord.solar_forecast_enabled = False
    coord.et0_illuminance_fallback = False
    coord._solar_radiation_source = None
    coord._solar_energy_previous_whm2 = 0.0
    coord.nowcast_enabled = False
    coord.nowcast_interval_min = 15
    coord._nowcast_cache = None

    return coord


# ---------------------------------------------------------------------------
# Tests: Raw Readings
# ---------------------------------------------------------------------------


class TestComputeRawReadings:
    def test_reads_all_sources(self):
        coord = _make_coordinator()
        data = {}
        now = datetime.now(UTC)
        tc, rh, p, ws, gs, wd, rain, lux, uv = coord._compute_raw_readings(data, now)

        assert tc == 22.0
        assert rh == 55.0
        assert p == 1013.0
        assert ws == 3.5
        assert gs == 6.0
        assert wd == 180.0
        assert rain == 5.2

    def test_unit_conversion_fahrenheit(self):
        """Verify F → C conversion."""
        coord = _make_coordinator(temp=77.0)
        # Change the unit to F
        coord.hass.states.get("sensor.temp").attributes["unit_of_measurement"] = "°F"
        data = {}
        tc, *_ = coord._compute_raw_readings(data, datetime.now(UTC))
        assert abs(tc - 25.0) < 0.1, f"77°F should be 25°C, got {tc}"

    def test_missing_sensor_returns_none(self):
        coord = _make_coordinator()
        coord.hass.states.get = lambda eid: None  # all sensors missing
        data = {}
        tc, rh, p, ws, gs, wd, rain, lux, uv = coord._compute_raw_readings(data, datetime.now(UTC))
        assert tc is None
        assert rh is None


# ---------------------------------------------------------------------------
# Tests: Derived Temperature
# ---------------------------------------------------------------------------


class TestComputeDerivedTemperature:
    def test_computes_dew_point(self):
        coord = _make_coordinator()
        data = {}
        now = datetime.now(UTC)
        dew = coord._compute_derived_temperature(data, now, 25.0, 60.0, 3.0)
        assert dew is not None
        assert 15.0 < dew < 18.0
        assert KEY_DEW_POINT_C in data

    def test_computes_frost_point(self):
        coord = _make_coordinator()
        data = {}
        coord._compute_derived_temperature(data, datetime.now(UTC), -5.0, 80.0, 2.0)
        assert KEY_FROST_POINT_C in data
        assert data[KEY_FROST_POINT_C] < -5.0

    def test_computes_wet_bulb(self):
        coord = _make_coordinator()
        data = {}
        coord._compute_derived_temperature(data, datetime.now(UTC), 30.0, 50.0, 2.0)
        assert KEY_WET_BULB_C in data
        assert 18.0 < data[KEY_WET_BULB_C] < 25.0

    def test_computes_feels_like(self):
        coord = _make_coordinator()
        data = {}
        coord._compute_derived_temperature(data, datetime.now(UTC), 30.0, 70.0, 5.0)
        assert KEY_FEELS_LIKE_C in data

    def test_handles_none_gracefully(self):
        coord = _make_coordinator()
        data = {}
        dew = coord._compute_derived_temperature(data, datetime.now(UTC), None, None, None)
        assert dew is None
        assert KEY_DEW_POINT_C not in data


# ---------------------------------------------------------------------------
# Tests: Yearly / All-Time Temperature Extremes (issue #124)
# ---------------------------------------------------------------------------


class TestTempYearAllTime:
    def test_first_reading_seeds_year_and_all_time(self):
        coord = _make_coordinator()
        data = {}
        coord._update_temp_year_all_time(data, 18.0)
        assert data[KEY_TEMP_HIGH_YEAR] == 18.0
        assert data[KEY_TEMP_LOW_YEAR] == 18.0
        assert data[KEY_TEMP_HIGH_ALL_TIME] == 18.0
        assert data[KEY_TEMP_LOW_ALL_TIME] == 18.0
        assert data[KEY_TEMP_YEAR_REF] == coord._temp_year_key

    def test_tracks_new_highs_and_lows_within_the_year(self):
        coord = _make_coordinator()
        for temp in (10.0, 25.0, -5.0, 12.0):
            data = {}
            coord._update_temp_year_all_time(data, temp)
        assert data[KEY_TEMP_HIGH_YEAR] == 25.0
        assert data[KEY_TEMP_LOW_YEAR] == -5.0
        assert data[KEY_TEMP_HIGH_ALL_TIME] == 25.0
        assert data[KEY_TEMP_LOW_ALL_TIME] == -5.0

    def test_year_rollover_resets_yearly_but_not_all_time(self):
        coord = _make_coordinator()
        # Seed as if the running extremes belong to last year.
        coord._temp_high_year = 30.0
        coord._temp_low_year = -10.0
        coord._temp_year_key = "2020"
        coord._temp_high_all_time = 35.0
        coord._temp_low_all_time = -15.0

        data = {}
        coord._update_temp_year_all_time(data, 5.0)

        current_year = dt_util.now().strftime("%Y")
        assert coord._temp_year_key == current_year
        # Yearly high/low reset to the first reading of the new year.
        assert data[KEY_TEMP_HIGH_YEAR] == 5.0
        assert data[KEY_TEMP_LOW_YEAR] == 5.0
        # All-time extremes are untouched by the year rollover.
        assert data[KEY_TEMP_HIGH_ALL_TIME] == 35.0
        assert data[KEY_TEMP_LOW_ALL_TIME] == -15.0

    def test_all_time_never_resets_even_when_below_previous_low(self):
        coord = _make_coordinator()
        data = {}
        coord._update_temp_year_all_time(data, 40.0)
        coord._update_temp_year_all_time(data, -20.0)
        # A milder reading afterwards must not erase the recorded extremes.
        coord._update_temp_year_all_time(data, 15.0)
        assert data[KEY_TEMP_HIGH_ALL_TIME] == 40.0
        assert data[KEY_TEMP_LOW_ALL_TIME] == -20.0

    def test_handles_none_gracefully(self):
        coord = _make_coordinator()
        data = {}
        coord._update_temp_year_all_time(data, None)
        assert data == {}
        assert coord._temp_high_year is None
        assert coord._temp_high_all_time is None


# ---------------------------------------------------------------------------
# Tests: Weekly / Monthly Temperature Extremes (issue #127)
# ---------------------------------------------------------------------------


class TestTempWeekMonth:
    def test_first_reading_seeds_week_and_month(self):
        coord = _make_coordinator()
        data = {}
        coord._update_temp_week_month(data, 18.0)
        assert data[KEY_TEMP_HIGH_WEEK] == 18.0
        assert data[KEY_TEMP_LOW_WEEK] == 18.0
        assert data[KEY_TEMP_HIGH_MONTH] == 18.0
        assert data[KEY_TEMP_LOW_MONTH] == 18.0
        assert data[KEY_TEMP_WEEK_REF] == coord._temp_week_isoweek
        assert data[KEY_TEMP_MONTH_REF] == coord._temp_month_key

    def test_tracks_new_highs_and_lows(self):
        coord = _make_coordinator()
        for temp in (10.0, 25.0, -5.0, 12.0):
            data = {}
            coord._update_temp_week_month(data, temp)
        assert data[KEY_TEMP_HIGH_WEEK] == 25.0
        assert data[KEY_TEMP_LOW_WEEK] == -5.0
        assert data[KEY_TEMP_HIGH_MONTH] == 25.0
        assert data[KEY_TEMP_LOW_MONTH] == -5.0

    def test_week_rollover_resets_week_but_not_month(self):
        coord = _make_coordinator()
        coord._temp_high_week = 30.0
        coord._temp_low_week = -10.0
        coord._temp_week_isoweek = "2020-W01"
        coord._temp_high_month = 30.0
        coord._temp_low_month = -10.0
        coord._temp_month_key = dt_util.now().strftime("%Y-%m")

        data = {}
        coord._update_temp_week_month(data, 5.0)

        assert data[KEY_TEMP_HIGH_WEEK] == 5.0
        assert data[KEY_TEMP_LOW_WEEK] == 5.0
        # Month key still matches, so month extremes are untouched by the week rollover.
        assert data[KEY_TEMP_HIGH_MONTH] == 30.0
        assert data[KEY_TEMP_LOW_MONTH] == -10.0

    def test_month_rollover_resets_month(self):
        coord = _make_coordinator()
        coord._temp_high_month = 30.0
        coord._temp_low_month = -10.0
        coord._temp_month_key = "2020-01"

        data = {}
        coord._update_temp_week_month(data, 5.0)

        current_month = dt_util.now().strftime("%Y-%m")
        assert coord._temp_month_key == current_month
        assert data[KEY_TEMP_HIGH_MONTH] == 5.0
        assert data[KEY_TEMP_LOW_MONTH] == 5.0

    def test_handles_none_gracefully(self):
        coord = _make_coordinator()
        data = {}
        coord._update_temp_week_month(data, None)
        assert data == {}
        assert coord._temp_high_week is None
        assert coord._temp_high_month is None


# ---------------------------------------------------------------------------
# Tests: Monthly / Yearly / All-Time Wind Gust Max (issue #127)
# ---------------------------------------------------------------------------


class TestGustMonthYearAllTime:
    def test_first_reading_seeds_all_periods(self):
        coord = _make_coordinator()
        data = {}
        coord._update_gust_month_year_all_time(data, 8.0)
        assert data[KEY_WIND_GUST_MAX_MONTH] == 8.0
        assert data[KEY_WIND_GUST_MAX_YEAR] == 8.0
        assert data[KEY_WIND_GUST_MAX_ALL_TIME] == 8.0
        assert data[KEY_WIND_GUST_MONTH_REF] == coord._gust_month_key
        assert data[KEY_WIND_GUST_YEAR_REF] == coord._gust_year_key

    def test_tracks_new_max(self):
        coord = _make_coordinator()
        for gust in (5.0, 12.0, 3.0, 9.0):
            data = {}
            coord._update_gust_month_year_all_time(data, gust)
        assert data[KEY_WIND_GUST_MAX_MONTH] == 12.0
        assert data[KEY_WIND_GUST_MAX_YEAR] == 12.0
        assert data[KEY_WIND_GUST_MAX_ALL_TIME] == 12.0

    def test_month_rollover_resets_month_not_year_or_all_time(self):
        coord = _make_coordinator()
        coord._gust_max_month = 20.0
        coord._gust_month_key = "2020-01"
        coord._gust_max_year = 20.0
        coord._gust_year_key = dt_util.now().strftime("%Y")
        coord._gust_max_all_time = 25.0

        data = {}
        coord._update_gust_month_year_all_time(data, 4.0)

        assert data[KEY_WIND_GUST_MAX_MONTH] == 4.0
        assert data[KEY_WIND_GUST_MAX_YEAR] == 20.0
        assert data[KEY_WIND_GUST_MAX_ALL_TIME] == 25.0

    def test_all_time_never_resets(self):
        coord = _make_coordinator()
        data = {}
        coord._update_gust_month_year_all_time(data, 40.0)
        coord._update_gust_month_year_all_time(data, 2.0)
        assert data[KEY_WIND_GUST_MAX_ALL_TIME] == 40.0

    def test_handles_none_gracefully(self):
        coord = _make_coordinator()
        data = {}
        coord._update_gust_month_year_all_time(data, None)
        assert data == {}
        assert coord._gust_max_month is None
        assert coord._gust_max_all_time is None


# ---------------------------------------------------------------------------
# Tests: Derived Pressure
# ---------------------------------------------------------------------------


class TestComputeDerivedPressure:
    def test_computes_mslp(self):
        coord = _make_coordinator(elevation=100.0)
        data = {}
        now = datetime.now(UTC)
        trend, mslp = coord._compute_derived_pressure(data, now, 20.0, 1000.0, 60.0)
        assert KEY_SEA_LEVEL_PRESSURE_HPA in data
        assert data[KEY_SEA_LEVEL_PRESSURE_HPA] > 1000.0  # MSLP > station pressure at elevation

    def test_pressure_history_accumulates(self):
        coord = _make_coordinator()
        now = datetime.now(UTC)
        for i in range(5):
            data = {}
            t = now + timedelta(minutes=i * 16)
            coord._compute_derived_pressure(data, t, 20.0, 1013.0 + i * 0.1, 60.0)
        assert len(coord.runtime.pressure_history) >= 2

    def test_zambretti_computed(self):
        coord = _make_coordinator()
        data = {KEY_WIND_QUADRANT: "N"}
        now = datetime.now(UTC)
        coord._compute_derived_pressure(data, now, 20.0, 1013.0, 60.0)
        assert KEY_ZAMBRETTI_FORECAST in data
        assert KEY_ZAMBRETTI_NUMBER in data
        assert data[KEY_ZAMBRETTI_NUMBER] is not None
        assert 1 <= data[KEY_ZAMBRETTI_NUMBER] <= 26


# ---------------------------------------------------------------------------
# Tests: Derived Wind
# ---------------------------------------------------------------------------


class TestComputeDerivedWind:
    def test_computes_beaufort(self):
        coord = _make_coordinator()
        data = {}
        coord._compute_derived_wind(data, datetime.now(UTC), 5.5, 8.0, 270.0)
        assert KEY_WIND_BEAUFORT in data
        assert data[KEY_WIND_BEAUFORT] == 4  # 5.5 m/s is at Beaufort 3/4 boundary

    def test_computes_quadrant(self):
        coord = _make_coordinator()
        data = {}
        coord._compute_derived_wind(data, datetime.now(UTC), 3.0, 5.0, 90.0)
        assert data[KEY_WIND_QUADRANT] == "E"

    def test_smoothes_direction(self):
        coord = _make_coordinator()
        # First reading
        data = {}
        coord._compute_derived_wind(data, datetime.now(UTC), 3.0, 5.0, 0.0)
        # Second reading at 180° should smooth
        data2 = {}
        coord._compute_derived_wind(data2, datetime.now(UTC), 3.0, 5.0, 180.0)
        smooth = coord.runtime.smoothed_wind_dir
        assert smooth is not None
        # Should be between 0 and 180, not a jump
        assert 0 < smooth < 180 or smooth > 300  # accounts for circular averaging


# ---------------------------------------------------------------------------
# Tests: Health / Quality
# ---------------------------------------------------------------------------


class TestComputeHealth:
    def test_all_healthy(self):
        coord = _make_coordinator()
        data = {}
        now = datetime.now(UTC)
        coord._compute_health(data, now, missing=[], missing_entities=[])
        assert data[KEY_PACKAGE_OK] is True
        assert data[KEY_HEALTH_DISPLAY] in ("online", "degraded")

    def test_missing_sources(self):
        coord = _make_coordinator()
        data = {}
        now = datetime.now(UTC)
        coord._compute_health(data, now, missing=["temperature"], missing_entities=[])
        assert data[KEY_PACKAGE_OK] is False
        assert "ERROR" in data.get(KEY_DATA_QUALITY, "") or "missing" in data.get(KEY_DATA_QUALITY, "").lower()

    def test_alerts_wind(self):
        coord = _make_coordinator()
        coord.entry_options = {"thresh_wind_gust_ms": 10.0}
        data = {KEY_NORM_WIND_GUST_MS: 15.0, "rain_rate_mmph_filtered": 0.0}
        now = datetime.now(UTC)
        # Call twice to satisfy ALERT_DEBOUNCE_ON_TICKS = 2
        coord._compute_health(data, now, missing=[], missing_entities=[])
        coord._compute_health(data, now, missing=[], missing_entities=[])
        coord._compute_health(data, now, missing=[], missing_entities=[])
        assert data[KEY_ALERT_STATE] == "warning"


# ---------------------------------------------------------------------------
# Tests: Sensor Quality Validation
# ---------------------------------------------------------------------------


class TestValidateReadings:
    def test_valid_readings_no_flags(self):
        from custom_components.ws_core.coordinator import WSStationCoordinator

        flags = WSStationCoordinator._validate_readings(20.0, 50.0, 1013.0, 5.0, 8.0, 12.0)
        assert flags == []

    def test_extreme_temperature_flagged(self):
        from custom_components.ws_core.coordinator import WSStationCoordinator

        flags = WSStationCoordinator._validate_readings(70.0, 50.0, 1013.0, 5.0, 8.0, 12.0)
        assert any("temperature" in f for f in flags)

    def test_dew_exceeds_temp_flagged(self):
        from custom_components.ws_core.coordinator import WSStationCoordinator

        flags = WSStationCoordinator._validate_readings(20.0, 50.0, 1013.0, 5.0, 8.0, 25.0)
        assert any("dew point" in f for f in flags)

    def test_gust_below_wind_flagged(self):
        from custom_components.ws_core.coordinator import WSStationCoordinator

        flags = WSStationCoordinator._validate_readings(20.0, 50.0, 1013.0, 10.0, 5.0, 12.0)
        assert any("gust" in f for f in flags)

    def test_none_values_no_crash(self):
        from custom_components.ws_core.coordinator import WSStationCoordinator

        flags = WSStationCoordinator._validate_readings(None, None, None, None, None, None)
        assert flags == []

    def test_station_pressure_at_altitude_not_flagged(self):
        """Station pressure at 2195 m (~784 hPa) is normal, not out of range."""
        from custom_components.ws_core.coordinator import WSStationCoordinator

        flags = WSStationCoordinator._validate_readings(10.0, 50.0, 783.9, 1.0, 2.0, 0.0, 2195.0)
        assert not any("pressure" in f for f in flags)

    def test_station_pressure_range_scales_with_elevation(self):
        from custom_components.ws_core.coordinator import WSStationCoordinator

        # The same reading at sea level is far below any real pressure.
        flags = WSStationCoordinator._validate_readings(10.0, 50.0, 783.9, 1.0, 2.0, 0.0, 0.0)
        assert any("pressure" in f for f in flags)
        # A sea-level value fed in at 2195 m is above the station's range.
        flags = WSStationCoordinator._validate_readings(10.0, 50.0, 1016.0, 1.0, 2.0, 0.0, 2195.0)
        assert any("pressure" in f for f in flags)


class TestDisplayUnits:
    """Free-text strings follow the configured units, not hardcoded metric."""

    def test_temp_unit_resolution(self):
        coord = _make_coordinator()
        assert coord.temp_unit == "°C"
        coord._temp_unit_conf = "F"
        assert coord.temp_unit == "°F"
        coord._temp_unit_conf = "auto"
        coord.units_mode = "imperial"
        assert coord.temp_unit == "°F"

    def test_explicit_units_skip_full_auto(self):
        coord = _make_coordinator()
        assert coord.explicit_units() == {}
        coord._wind_unit_conf = "km/h"
        assert coord.explicit_units() == {"wind": "km/h"}
        coord.units_mode = "imperial"
        units = coord.explicit_units()
        assert units["temperature"] == "°F"
        assert units["pressure"] == "inHg"
        assert units["wind"] == "km/h"

    def test_conditions_summary_in_imperial(self):
        coord = _make_coordinator()
        coord.units_mode = "imperial"
        coord.hass.config.language = "en"
        data = {
            KEY_NORM_TEMP_C: 20.0,
            KEY_FEELS_LIKE_C: 25.0,
            KEY_NORM_WIND_SPEED_MS: 4.4704,
            KEY_NORM_WIND_GUST_MS: 8.9408,
            KEY_RAIN_RATE_FILT: 25.4,
        }
        coord._compute_conditions_summary(data)
        summary = data[KEY_CONDITIONS_SUMMARY]
        assert summary.startswith("68.0°F")
        assert "feels like 77.0°F" in summary
        assert "1.00 in/h rain" in summary
        assert "10 mph" in summary
        assert "gusting 20" in summary
        assert "°C" not in summary and "m/s" not in summary


# ---------------------------------------------------------------------------
# Tests: Unit Conversion
# ---------------------------------------------------------------------------


class TestUnitConversion:
    def test_fahrenheit_to_celsius(self):
        from custom_components.ws_core.coordinator import WSStationCoordinator

        assert abs(WSStationCoordinator._to_celsius(212.0, "°F") - 100.0) < 0.1
        assert abs(WSStationCoordinator._to_celsius(32.0, "F") - 0.0) < 0.1

    def test_kelvin_to_celsius(self):
        from custom_components.ws_core.coordinator import WSStationCoordinator

        assert abs(WSStationCoordinator._to_celsius(273.15, "K") - 0.0) < 0.1

    def test_kmh_to_ms(self):
        from custom_components.ws_core.coordinator import WSStationCoordinator

        assert abs(WSStationCoordinator._to_ms(36.0, "km/h") - 10.0) < 0.1

    def test_mph_to_ms(self):
        from custom_components.ws_core.coordinator import WSStationCoordinator

        assert abs(WSStationCoordinator._to_ms(10.0, "mph") - 4.47) < 0.1

    def test_inhg_to_hpa(self):
        from custom_components.ws_core.coordinator import WSStationCoordinator

        assert abs(WSStationCoordinator._to_hpa(29.92, "inHg") - 1013.25) < 0.5

    def test_inches_to_mm(self):
        from custom_components.ws_core.coordinator import WSStationCoordinator

        assert abs(WSStationCoordinator._to_mm(1.0, "in") - 25.4) < 0.1


# ---------------------------------------------------------------------------
# Tests: Rolling Windows
# ---------------------------------------------------------------------------


class TestRollingWindows:
    def test_append_and_prune(self):
        from custom_components.ws_core.coordinator import WSStationCoordinator

        history = deque()
        now = datetime.now(UTC)
        # Add values spanning 26 hours
        for i in range(26):
            WSStationCoordinator._append_and_prune_24h(history, now - timedelta(hours=25 - i), float(i))
        # Should have pruned the oldest entries
        vals = WSStationCoordinator._rolling_values(history)
        assert len(vals) <= 25  # 24h window
        assert vals[-1] == 25.0

    def test_rain_accum_handles_reset(self):
        from custom_components.ws_core.coordinator import WSStationCoordinator

        history = deque()
        now = datetime.now(UTC)
        # Simulate: 0, 1, 2, 0 (reset), 1
        for i, val in enumerate([0.0, 1.0, 2.0, 0.0, 1.0]):
            history.append((now + timedelta(minutes=i * 15), val))
        accum = WSStationCoordinator._rain_accum_24h_from_totals(history)
        # Should count 0→1, 1→2, skip 2→0 (reset), 0→1 = total 3mm
        assert abs(accum - 3.0) < 0.1


class TestYearlyRainSource:
    """Issue #161: station year-to-date totals must not start at zero."""

    def _compute(self, coord, now, total):
        from custom_components.ws_core.const import KEY_NORM_RAIN_TOTAL_MM

        data = {KEY_NORM_RAIN_TOTAL_MM: total}
        with patch.object(dt_util, "now", return_value=now):
            coord._compute_derived_precipitation(data, now, total)
        return data

    def test_station_total_includes_rain_before_installation(self):
        coord = _make_coordinator(rain_total=432.1)
        coord.sources[SRC_RAIN_YEAR] = "sensor.rain"
        now = datetime(2026, 10, 5, tzinfo=UTC)
        data = self._compute(coord, now, 432.1)
        assert data[KEY_RAIN_THIS_YEAR_MM] == 432.1
        assert data[KEY_RAIN_THIS_MONTH_MM] == 0.0

    def test_station_total_overrides_restored_accumulator_and_follows_reset(self):
        coord = _make_coordinator()
        coord.sources[SRC_RAIN_YEAR] = "sensor.yearly"
        state = _make_state("432.1", "mm")
        original_get = coord.hass.states.get
        coord.hass.states.get = lambda eid: state if eid == "sensor.yearly" else original_get(eid)
        coord._rain_this_year_key = "2026"
        coord._rain_this_year_mm = 12.3
        coord._rain_this_year_last_total = 5.2
        assert self._compute(coord, datetime(2026, 12, 31, tzinfo=UTC), 5.2)[KEY_RAIN_THIS_YEAR_MM] == 432.1
        state.state = "0.4"
        assert self._compute(coord, datetime(2027, 1, 1, tzinfo=UTC), 5.6)[KEY_RAIN_THIS_YEAR_MM] == 0.4
        state.state = "0"
        assert self._compute(coord, datetime(2027, 1, 2, tzinfo=UTC), 5.6)[KEY_RAIN_THIS_YEAR_MM] == 0.0

    def test_inches_are_converted_to_mm(self):
        coord = _make_coordinator()
        coord.sources[SRC_RAIN_YEAR] = "sensor.yearly"
        original_get = coord.hass.states.get
        state = _make_state("10", "in")
        coord.hass.states.get = lambda eid: state if eid == "sensor.yearly" else original_get(eid)
        assert self._compute(coord, datetime(2026, 10, 5, tzinfo=UTC), 5.2)[KEY_RAIN_THIS_YEAR_MM] == 254.0

    def test_invalid_station_total_is_unknown_and_recovers(self):
        coord = _make_coordinator()
        coord.sources[SRC_RAIN_YEAR] = "sensor.yearly"
        original_get = coord.hass.states.get
        state = _make_state("unavailable", "mm")
        coord.hass.states.get = lambda eid: state if eid == "sensor.yearly" else original_get(eid)
        now = datetime(2026, 10, 5, tzinfo=UTC)
        for value in ("unavailable", "unknown", "nan", "inf", "-1", "bad"):
            state.state = value
            assert self._compute(coord, now, 5.2)[KEY_RAIN_THIS_YEAR_MM] is None
        state.state = "100.2"
        assert self._compute(coord, now, 5.2)[KEY_RAIN_THIS_YEAR_MM] == 100.2
        coord.hass.states.get = original_get
        assert self._compute(coord, now, 5.2)[KEY_RAIN_THIS_YEAR_MM] is None

    def test_unmapped_counter_still_accumulates_and_resets(self):
        coord = _make_coordinator()
        now = datetime(2026, 10, 5, tzinfo=UTC)
        assert self._compute(coord, now, 400.0)[KEY_RAIN_THIS_YEAR_MM] == 0.0
        assert self._compute(coord, now + timedelta(minutes=1), 402.5)[KEY_RAIN_THIS_YEAR_MM] == 2.5
        assert self._compute(coord, datetime(2027, 1, 1, tzinfo=UTC), 0.4)[KEY_RAIN_THIS_YEAR_MM] == 0.0


class TestRainRateWindow:
    """Regression tests for issue #132 (rain rate sawtooth).

    A single poll-cycle delta on a bucket-tip rain-total sensor spikes and
    decays to zero every cycle because most cycles see no tip at all. Rate
    must instead be averaged over a short sliding window so a steady drizzle
    or downpour reads as a steady rate.
    """

    def test_single_tip_inside_one_poll_no_longer_spikes_to_extreme_rate(self):
        from custom_components.ws_core.const import RAIN_RATE_WINDOW_H
        from custom_components.ws_core.coordinator import WSStationCoordinator

        history = deque()
        now = datetime.now(UTC)
        # 10 minutes of no-rain history, then a single 0.93mm bucket tip
        # lands inside the latest 60s poll cycle. The old instantaneous
        # dv/dt calculation would report 0.93mm / (60s/3600) = 56 mm/h from
        # that single cycle alone (matching the exact figure in issue #132),
        # then 0 mm/h on every subsequent tip-less cycle -- a sawtooth.
        for i in range(10):
            history.append((now - timedelta(minutes=10 - i), 10.0))
        history.append((now, 10.93))
        rate = WSStationCoordinator._rain_rate_from_totals_window(history, now, RAIN_RATE_WINDOW_H)
        assert rate < 10.0, (
            f"a single tip should be smoothed over the window, not read as the instantaneous 56 mm/h spike: got {rate}"
        )

    def test_steady_light_rain_reads_as_steady_rate_not_sawtooth(self):
        """Repeated tips at a constant real-world rate should NOT oscillate cycle to cycle."""
        from custom_components.ws_core.const import RAIN_RATE_WINDOW_H
        from custom_components.ws_core.coordinator import WSStationCoordinator

        history = deque()
        now = datetime.now(UTC)
        total = 0.0
        rates = []
        # One 60s poll per minute for 12 minutes; a 0.2mm tip lands every 3rd
        # cycle (≈4mm/h average), all other cycles see no new tip at all.
        for i in range(12):
            ts = now - timedelta(minutes=12 - i)
            if i % 3 == 0:
                total += 0.2
            history.append((ts, total))
            rates.append(WSStationCoordinator._rain_rate_from_totals_window(history, ts, RAIN_RATE_WINDOW_H))
        # Once the window has a few cycles of history, consecutive rate
        # readings should be close to each other, not swinging between a
        # spike and zero every cycle.
        settled = rates[4:]
        assert max(settled) - min(settled) < 5.0, f"rate oscillated across cycles: {settled}"

    def test_no_rain_stays_zero(self):
        from custom_components.ws_core.const import RAIN_RATE_WINDOW_H
        from custom_components.ws_core.coordinator import WSStationCoordinator

        history = deque()
        now = datetime.now(UTC)
        for i in range(5):
            history.append((now - timedelta(minutes=5 - i), 10.0))
        rate = WSStationCoordinator._rain_rate_from_totals_window(history, now, RAIN_RATE_WINDOW_H)
        assert rate == 0.0

    def test_fewer_than_two_samples_returns_zero(self):
        from custom_components.ws_core.const import RAIN_RATE_WINDOW_H
        from custom_components.ws_core.coordinator import WSStationCoordinator

        now = datetime.now(UTC)
        assert WSStationCoordinator._rain_rate_from_totals_window(deque(), now, RAIN_RATE_WINDOW_H) == 0.0
        history = deque([(now, 1.0)])
        assert WSStationCoordinator._rain_rate_from_totals_window(history, now, RAIN_RATE_WINDOW_H) == 0.0


class TestEntryOptionsMerge:
    """A freshly created config entry has enable_* toggles in entry.data only -
    entry.options starts as {} and is only populated once the user opens
    Configure and saves (see OptionsFlow.async_create_entry). Per-cycle gates
    that read self.entry_options.get(CONF_ENABLE_X, DEFAULT) directly (e.g.
    _compute_soil) must still see a toggle the user enabled in the initial
    wizard - not silently fall back to DEFAULT until Configure is opened once.
    """

    def _construct(self, entry_data: dict, entry_options: dict | None):
        """Run the real WSStationCoordinator.__init__ (not the bypass pattern
        used elsewhere in this file), stubbing out only the DataUpdateCoordinator
        base class's __init__ (which needs real HA event-loop plumbing a
        MagicMock hass can't satisfy) so the merge logic under test actually runs.
        """
        from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

        from custom_components.ws_core.coordinator import WSStationCoordinator

        hass = MagicMock()
        with patch.object(DataUpdateCoordinator, "__init__", lambda self, *a, **kw: None):
            return WSStationCoordinator(hass, entry_data, entry_options)

    def test_options_empty_falls_back_to_data(self):
        from custom_components.ws_core.const import CONF_ENABLE_SOIL

        coord = self._construct({CONF_ENABLE_SOIL: True, "entry_id": "abc"}, {})
        assert coord.entry_options.get(CONF_ENABLE_SOIL) is True

    def test_options_none_falls_back_to_data(self):
        """entry.options can also arrive as None (mirrors WSStationCoordinator's
        own `entry_options: dict | None = None` default)."""
        from custom_components.ws_core.const import CONF_ENABLE_SOIL

        coord = self._construct({CONF_ENABLE_SOIL: True, "entry_id": "abc"}, None)
        assert coord.entry_options.get(CONF_ENABLE_SOIL) is True

    def test_options_override_data_once_configure_is_saved(self):
        """After the user opens Configure and saves, entry.options should win -
        this is the existing, already-correct behaviour the fix must preserve.
        """
        from custom_components.ws_core.const import CONF_ENABLE_SOIL

        coord = self._construct(
            {CONF_ENABLE_SOIL: True, "entry_id": "abc"},
            {CONF_ENABLE_SOIL: False},
        )
        assert coord.entry_options.get(CONF_ENABLE_SOIL) is False

    def test_soil_toggle_enabled_only_in_data_computes_on_first_cycle(self):
        """The actual user-visible regression: _compute_soil (and every other
        per-cycle gate with this shape) must produce a value on the very first
        cycle of a freshly created entry, not sit unavailable until Configure
        is opened once.
        """
        from custom_components.ws_core.const import (
            CONF_ENABLE_SOIL,
            KEY_ET0_DAILY_MM,
            KEY_IRRIGATION_NEED,
            KEY_RAIN_TODAY_MM,
            KEY_SOIL_MOISTURE,
        )

        coord = self._construct({CONF_ENABLE_SOIL: True, "entry_id": "abc"}, {})
        data = {KEY_SOIL_MOISTURE: 25.0, KEY_ET0_DAILY_MM: 3.0, KEY_RAIN_TODAY_MM: 0.0}
        coord._compute_soil(data)
        assert KEY_IRRIGATION_NEED in data  # not skipped by the enable_soil gate


class TestNeighborQcSwitch:
    """enable_neighbor_qc: off switch for the hourly Open-Meteo neighbor-QC fetch.

    The fetch must only be scheduled when something consumes it (the QC flags,
    or opt-in adaptive calibration), and with the switch off the flags sensor
    must read unknown rather than "0 flags, all clear".
    """

    def _construct(self, entry_data: dict):
        from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

        from custom_components.ws_core.coordinator import WSStationCoordinator

        with patch.object(DataUpdateCoordinator, "__init__", lambda self, *a, **kw: None):
            return WSStationCoordinator(MagicMock(), {"entry_id": "abc", **entry_data}, {})

    def _data(self, temp_c=30.0):
        from custom_components.ws_core.const import KEY_NORM_HUMIDITY, KEY_NORM_PRESSURE_HPA, KEY_NORM_TEMP_C

        return {KEY_NORM_TEMP_C: temp_c, KEY_NORM_HUMIDITY: 50.0, KEY_NORM_PRESSURE_HPA: 1013.0}

    def test_on_by_default(self):
        coord = self._construct({})
        assert coord.neighbor_qc_enabled is True
        assert coord._neighbor_qc_fetch_needed() is True

    def test_switched_off_needs_no_fetch(self):
        from custom_components.ws_core.const import CONF_ENABLE_NEIGHBOR_QC

        coord = self._construct({CONF_ENABLE_NEIGHBOR_QC: False})
        assert coord._neighbor_qc_fetch_needed() is False

    def test_auto_calibration_keeps_fetch_alive(self):
        from custom_components.ws_core.const import CONF_ENABLE_AUTO_CALIBRATION, CONF_ENABLE_NEIGHBOR_QC

        coord = self._construct({CONF_ENABLE_NEIGHBOR_QC: False, CONF_ENABLE_AUTO_CALIBRATION: True})
        assert coord._neighbor_qc_fetch_needed() is True

    def test_switched_off_reports_no_flags_even_with_cached_reference(self):
        from custom_components.ws_core.const import (
            CONF_ENABLE_AUTO_CALIBRATION,
            CONF_ENABLE_NEIGHBOR_QC,
            KEY_NEIGHBOR_QC,
        )

        coord = self._construct({CONF_ENABLE_NEIGHBOR_QC: False, CONF_ENABLE_AUTO_CALIBRATION: True})
        # Auto-calibration filled the cache with a reference 15°C away from local.
        coord._neighbor_qc_cache = {"temp_c": 15.0, "humidity": 50.0, "pressure_hpa": 1013.0}
        data = self._data(temp_c=30.0)
        coord._compute_neighbor_qc(data)
        assert data[KEY_NEIGHBOR_QC] is None

    def test_switched_on_still_flags_large_deviation(self):
        from custom_components.ws_core.const import KEY_NEIGHBOR_QC

        coord = self._construct({})
        coord._neighbor_qc_cache = {"temp_c": 15.0, "humidity": 50.0, "pressure_hpa": 1013.0}
        data = self._data(temp_c=30.0)
        coord._compute_neighbor_qc(data)
        assert len(data[KEY_NEIGHBOR_QC]) == 1
        assert data[KEY_NEIGHBOR_QC][0].startswith("temperature:")

    def test_flags_sensor_unknown_when_off_and_zero_when_clear(self):
        from custom_components.ws_core.const import KEY_NEIGHBOR_QC
        from custom_components.ws_core.entity_descriptions import SENSORS

        desc = next(s for s in SENSORS if s.key == KEY_NEIGHBOR_QC)
        assert desc.value_fn({KEY_NEIGHBOR_QC: None}) is None
        assert desc.attrs_fn({KEY_NEIGHBOR_QC: None})["all_clear"] is None
        assert desc.value_fn({KEY_NEIGHBOR_QC: []}) == 0
        assert desc.attrs_fn({KEY_NEIGHBOR_QC: []})["all_clear"] is True

    def test_feature_switch_exists(self):
        from custom_components.ws_core.const import CONF_ENABLE_NEIGHBOR_QC
        from custom_components.ws_core.switch import FEATURE_SWITCHES

        desc = next(sw for sw in FEATURE_SWITCHES if sw.conf_key == CONF_ENABLE_NEIGHBOR_QC)
        assert desc.default is True


class TestComputeSnow:
    """_compute_snow (v2.7, opt-in): precipitation phase + estimated snow
    accumulation, integrated locally from the smoothed liquid rain rate.
    """

    def _data(self, temp_c=-5.0, humidity=90.0, rain_rate=2.0):
        from custom_components.ws_core.const import (
            KEY_NORM_HUMIDITY,
            KEY_NORM_TEMP_C,
            KEY_RAIN_RATE_FILT,
        )

        return {
            KEY_NORM_TEMP_C: temp_c,
            KEY_NORM_HUMIDITY: humidity,
            KEY_RAIN_RATE_FILT: rain_rate,
        }

    def test_disabled_is_a_no_op(self):
        from custom_components.ws_core.const import KEY_SNOW_PHASE

        coord = _make_coordinator()
        coord.snow_enabled = False
        data = self._data()
        coord._compute_snow(data, dt_util.utcnow())
        assert KEY_SNOW_PHASE not in data

    def test_missing_temp_or_humidity_skips(self):
        from custom_components.ws_core.const import (
            KEY_NORM_HUMIDITY,
            KEY_NORM_TEMP_C,
            KEY_RAIN_RATE_FILT,
            KEY_SNOW_PHASE,
        )

        coord = _make_coordinator()
        coord.snow_enabled = True
        data = {KEY_NORM_TEMP_C: None, KEY_NORM_HUMIDITY: 90.0, KEY_RAIN_RATE_FILT: 2.0}
        coord._compute_snow(data, dt_util.utcnow())
        assert KEY_SNOW_PHASE not in data

    def test_no_precip_gives_phase_none(self):
        from custom_components.ws_core.const import KEY_SNOW_FALLING, KEY_SNOW_PHASE

        coord = _make_coordinator()
        coord.snow_enabled = True
        data = self._data(rain_rate=0.0)
        coord._compute_snow(data, dt_util.utcnow())
        assert data[KEY_SNOW_PHASE] == "none"
        assert data[KEY_SNOW_FALLING] is False

    def test_warm_precip_gives_phase_rain(self):
        from custom_components.ws_core.const import KEY_SNOW_FALLING, KEY_SNOW_PHASE

        coord = _make_coordinator()
        coord.snow_enabled = True
        data = self._data(temp_c=15.0, humidity=60.0, rain_rate=3.0)
        coord._compute_snow(data, dt_util.utcnow())
        assert data[KEY_SNOW_PHASE] == "rain"
        assert data[KEY_SNOW_FALLING] is False

    def test_cold_precip_gives_phase_snow_and_falling(self):
        from custom_components.ws_core.const import KEY_SNOW_FALLING, KEY_SNOW_PHASE, KEY_SNOW_RATE_CM_H

        coord = _make_coordinator()
        coord.snow_enabled = True
        data = self._data(temp_c=-5.0, humidity=90.0, rain_rate=2.0)
        coord._compute_snow(data, dt_util.utcnow())
        assert data[KEY_SNOW_PHASE] == "snow"
        assert data[KEY_SNOW_FALLING] is True
        assert data[KEY_SNOW_RATE_CM_H] > 0.0

    def test_first_call_accumulates_nothing_no_prior_timestamp(self):
        from custom_components.ws_core.const import KEY_SNOW_TODAY_CM

        coord = _make_coordinator()
        coord.snow_enabled = True
        data = self._data()
        coord._compute_snow(data, dt_util.utcnow())
        # No elapsed time is known on the very first cycle - nothing to integrate yet.
        assert data[KEY_SNOW_TODAY_CM] == 0.0

    def test_second_call_accumulates_over_elapsed_time(self):
        from custom_components.ws_core.const import KEY_SNOW_TODAY_CM

        coord = _make_coordinator()
        coord.snow_enabled = True
        t0 = dt_util.utcnow()
        coord._compute_snow(self._data(), t0)
        t1 = t0 + timedelta(minutes=10)
        data2 = self._data()
        coord._compute_snow(data2, t1)
        assert data2[KEY_SNOW_TODAY_CM] > 0.0
        # Same amount should also land in the month/year accumulators.
        from custom_components.ws_core.const import KEY_SNOW_THIS_MONTH_CM, KEY_SNOW_THIS_YEAR_CM

        assert data2[KEY_SNOW_THIS_MONTH_CM] == data2[KEY_SNOW_TODAY_CM]
        assert data2[KEY_SNOW_THIS_YEAR_CM] == data2[KEY_SNOW_TODAY_CM]

    def test_a_long_gap_is_capped_not_fully_attributed(self):
        from custom_components.ws_core.const import KEY_SNOW_TODAY_CM

        coord = _make_coordinator()
        coord.snow_enabled = True
        t0 = dt_util.utcnow()
        coord._compute_snow(self._data(), t0)
        # A 6h gap (e.g. HA was stopped) must be capped, not attributed in full.
        t1 = t0 + timedelta(hours=6)
        data2 = self._data()
        coord._compute_snow(data2, t1)
        uncapped_estimate = 2.0 * 6.0  # rain_rate(mm/h) * hours, before SLR
        assert data2[KEY_SNOW_TODAY_CM] < uncapped_estimate

    def test_day_rollover_resets_today_but_not_month_or_year(self):
        from custom_components.ws_core.const import (
            KEY_SNOW_THIS_MONTH_CM,
            KEY_SNOW_THIS_YEAR_CM,
            KEY_SNOW_TODAY_CM,
        )

        coord = _make_coordinator()
        coord.snow_enabled = True
        coord._snow_today_cm = 5.0
        coord._snow_today_date = "2000-01-01"  # deliberately stale
        coord._snow_this_month_cm = 12.0
        coord._snow_this_month_key = dt_util.now().strftime("%Y-%m")
        coord._snow_this_year_cm = 40.0
        coord._snow_this_year_key = dt_util.now().strftime("%Y")
        data = self._data(rain_rate=0.0)  # no new snow this cycle
        coord._compute_snow(data, dt_util.utcnow())
        assert data[KEY_SNOW_TODAY_CM] == 0.0  # rolled over to a new day
        assert data[KEY_SNOW_THIS_MONTH_CM] == 12.0  # untouched
        assert data[KEY_SNOW_THIS_YEAR_CM] == 40.0  # untouched

    def test_snowiest_day_record_tracks_running_daily_total(self):
        from custom_components.ws_core.const import KEY_SNOW_RECORD_DAY_CM, KEY_SNOW_TODAY_CM

        coord = _make_coordinator()
        coord.snow_enabled = True
        t0 = dt_util.utcnow()
        coord._compute_snow(self._data(), t0)
        coord._compute_snow(self._data(), t0 + timedelta(minutes=20))
        data = self._data()
        coord._compute_snow(data, t0 + timedelta(minutes=40))
        # The record mirrors today's accumulating total while it is the wettest day.
        assert data[KEY_SNOW_RECORD_DAY_CM] == data[KEY_SNOW_TODAY_CM] > 0.0
        assert data["_snow_record_day_date"] == dt_util.now().strftime("%Y-%m-%d")

    def test_snowiest_day_record_survives_day_rollover_and_dry_days(self):
        from custom_components.ws_core.const import KEY_SNOW_RECORD_DAY_CM, KEY_SNOW_TODAY_CM

        coord = _make_coordinator()
        coord.snow_enabled = True
        coord._snowiest_day_cm = 25.0
        coord._snowiest_day_date = "2001-02-03"
        coord._snow_today_date = "2000-01-01"  # force a day rollover this cycle
        data = self._data(rain_rate=0.0)  # dry day, nothing new
        coord._compute_snow(data, dt_util.utcnow())
        assert data[KEY_SNOW_TODAY_CM] == 0.0
        assert data[KEY_SNOW_RECORD_DAY_CM] == 25.0  # all-time record untouched
        assert data["_snow_record_day_date"] == "2001-02-03"


class TestDiscoverBlitzortung:
    """_discover_blitzortung scans the whole entity registry; it must tolerate
    entities whose unique_id is not a string (issue #142)."""

    def _entry(self, entity_id, platform, unique_id):
        e = MagicMock()
        e.entity_id = entity_id
        e.platform = platform
        e.unique_id = unique_id
        return e

    def _run(self, entries):
        coord = _make_coordinator()
        coord._blitzortung_sources = {}
        reg = MagicMock()
        reg.entities.values.return_value = entries
        with patch("homeassistant.helpers.entity_registry.async_get", return_value=reg):
            coord._discover_blitzortung()
        return coord

    def test_non_string_unique_id_does_not_raise(self):
        # e.g. a nuki lock stores unique_id as a plain int
        entries = [
            self._entry("lock.front_door", "nuki", 659980332),
            self._entry("sensor.some_number", "template", 42),
        ]
        coord = self._run(entries)  # must not raise AttributeError
        assert coord._blitzortung_sources == {}

    def test_blitzortung_entities_still_auto_detected(self):
        from custom_components.ws_core.const import SRC_LIGHTNING_COUNT, SRC_LIGHTNING_DISTANCE

        entries = [
            self._entry("lock.front_door", "nuki", 659980332),
            self._entry("sensor.blitzortung_lightning_counter", "blitzortung", "abc-counter"),
            self._entry("sensor.blitzortung_lightning_distance", "blitzortung", "abc-distance"),
        ]
        coord = self._run(entries)
        assert coord._blitzortung_sources[SRC_LIGHTNING_COUNT] == "sensor.blitzortung_lightning_counter"
        assert coord._blitzortung_sources[SRC_LIGHTNING_DISTANCE] == "sensor.blitzortung_lightning_distance"


# ---------------------------------------------------------------------------
# Tests: Nowcast staleness + local Zambretti fallback
# ---------------------------------------------------------------------------


class TestComputeNowcast:
    def _coord_with_zambretti(self, z_number):
        coord = _make_coordinator()
        coord.nowcast_enabled = True
        return coord, {KEY_ZAMBRETTI_NUMBER: z_number}

    def test_fresh_cache_uses_nowcast_source(self):
        coord, data = self._coord_with_zambretti(10)
        now_iso = dt_util.now().isoformat()
        coord._nowcast_cache = {
            "fetched_at": now_iso,
            "next_60min_mm": 0.0,
            "minutes_until_rain": None,
            "minutes_until_dry": None,
            "intensity": "none",
            "rain_expected_1h": False,
            "peak_rate_mmph": 0.0,
            "raining_now": False,
        }
        coord._compute_nowcast(data)
        assert data[KEY_NOWCAST_STALE] is False
        assert data[KEY_RAIN_EXPECTED_SOURCE] == RAIN_EXPECTED_SOURCE_NOWCAST
        assert data[KEY_RAIN_EXPECTED_1H] is False

    def test_stale_cache_falls_back_to_zambretti_high_rain_pct(self):
        # Z-number 26 ("Very Unsettled, Rain") sits at the high-rain-probability
        # end of ZAMBRETTI_RAIN_PCT.
        coord, data = self._coord_with_zambretti(26)
        old_iso = (dt_util.now() - timedelta(hours=2)).isoformat()
        coord._nowcast_cache = {"fetched_at": old_iso, "next_60min_mm": 0.0, "rain_expected_1h": False}
        coord._compute_nowcast(data)
        assert data[KEY_NOWCAST_STALE] is True
        assert data[KEY_RAIN_EXPECTED_SOURCE] == RAIN_EXPECTED_SOURCE_LOCAL_FALLBACK
        assert data[KEY_RAIN_EXPECTED_1H] is True

    def test_never_fetched_falls_back_to_zambretti_low_rain_pct(self):
        # Z-number 1 ("Settled Fine") sits at the low-rain-probability end.
        coord, data = self._coord_with_zambretti(1)
        coord._nowcast_cache = None
        coord._compute_nowcast(data)
        assert data[KEY_NOWCAST_STALE] is True
        assert data[KEY_RAIN_EXPECTED_SOURCE] == RAIN_EXPECTED_SOURCE_LOCAL_FALLBACK
        assert data[KEY_RAIN_EXPECTED_1H] is False

    def test_no_nowcast_and_no_zambretti_is_unavailable(self):
        coord, data = self._coord_with_zambretti(None)
        coord._nowcast_cache = None
        coord._compute_nowcast(data)
        assert data[KEY_RAIN_EXPECTED_1H] is None
        assert data[KEY_RAIN_EXPECTED_SOURCE] is None


# ---------------------------------------------------------------------------
# Tests: PM ET0 illuminance fallback for solar radiation
# ---------------------------------------------------------------------------


class TestSolarRadiationForEt0:
    def test_prefers_real_solar_sensor(self):
        coord = _make_coordinator()
        coord.sources = {SRC_SOLAR_RADIATION: "sensor.solar", SRC_LUX: "sensor.lux"}
        coord.et0_illuminance_fallback = True
        coord.hass.states.get = lambda eid: {
            "sensor.solar": _make_state("500.0"),
            "sensor.lux": _make_state("40000"),
        }.get(eid)
        val = coord._get_solar_radiation_for_et0()
        assert val == 500.0
        assert coord._solar_radiation_source == ET0_RADIATION_SOURCE_SENSOR

    def test_falls_back_to_illuminance_when_enabled(self):
        coord = _make_coordinator()
        coord.sources = {SRC_LUX: "sensor.lux"}  # no solar_radiation mapped
        coord.et0_illuminance_fallback = True
        coord.hass.states.get = lambda eid: {"sensor.lux": _make_state("40000")}.get(eid)
        val = coord._get_solar_radiation_for_et0()
        assert val == 40000 * 0.0079
        assert coord._solar_radiation_source == ET0_RADIATION_SOURCE_ILLUMINANCE_ESTIMATE

    def test_no_fallback_when_disabled(self):
        coord = _make_coordinator()
        coord.sources = {SRC_LUX: "sensor.lux"}
        coord.et0_illuminance_fallback = False
        coord.hass.states.get = lambda eid: {"sensor.lux": _make_state("40000")}.get(eid)
        val = coord._get_solar_radiation_for_et0()
        assert val is None
        assert coord._solar_radiation_source is None

    def test_no_fallback_when_no_illuminance_source(self):
        coord = _make_coordinator()
        coord.sources = {}
        coord.et0_illuminance_fallback = True
        val = coord._get_solar_radiation_for_et0()
        assert val is None
        assert coord._solar_radiation_source is None


# ---------------------------------------------------------------------------
# Tests: PM ET0 "unavailable" repair issue
# ---------------------------------------------------------------------------


class TestEt0PmUnavailableIssue:
    def _run(self, solar_forecast_enabled, forecast_lat, sources, et0_present, reason=None):
        coord = _make_coordinator()
        coord.solar_forecast_enabled = solar_forecast_enabled
        coord.forecast_lat = forecast_lat
        coord.sources = sources
        coord.suppress_notifications = False
        from custom_components.ws_core.const import KEY_ET0_PM_DAILY_MM

        data = {KEY_ET0_PM_DAILY_MM: 3.2} if et0_present else {}
        if reason is not None:
            data["et0_pm_reason"] = reason
        now = datetime.now(UTC)
        with (
            patch("custom_components.ws_core.coordinator.ir.async_create_issue") as mock_create,
            patch("custom_components.ws_core.coordinator.ir.async_delete_issue") as mock_delete,
        ):
            coord._compute_health(data, now, missing=[], missing_entities=[])
        return mock_create, mock_delete

    def test_pv_forecast_without_pm_source_does_not_create_issue(self):
        mock_create, _ = self._run(solar_forecast_enabled=True, forecast_lat=37.9, sources={}, et0_present=False)
        keys = [c.args[2] for c in mock_create.call_args_list]
        assert not any(k.startswith("et0_pm_unavailable") for k in keys)

    def test_no_issue_when_solar_forecast_disabled(self):
        mock_create, _ = self._run(solar_forecast_enabled=False, forecast_lat=37.9, sources={}, et0_present=False)
        keys = [c.args[2] for c in mock_create.call_args_list]
        assert not any(k.startswith("et0_pm_unavailable") for k in keys)

    def test_issue_when_configured_source_has_insufficient_coverage(self):
        mock_create, _ = self._run(
            solar_forecast_enabled=False,
            forecast_lat=37.9,
            sources={SRC_SOLAR_RADIATION: "sensor.solar"},
            et0_present=False,
            reason="insufficient solar coverage",
        )
        keys = [c.args[2] for c in mock_create.call_args_list]
        assert any(k.startswith("et0_pm_unavailable") for k in keys)

    def test_no_issue_when_et0_already_computed(self):
        mock_create, _ = self._run(solar_forecast_enabled=True, forecast_lat=37.9, sources={}, et0_present=True)
        keys = [c.args[2] for c in mock_create.call_args_list]
        assert not any(k.startswith("et0_pm_unavailable") for k in keys)


# ---------------------------------------------------------------------------
# Tests: PR 1 lifecycle, forecast retry backoff & task cleanup
# ---------------------------------------------------------------------------


class TestLifecycleAndBackoff:
    def test_cold_start_forecast_failures_back_off_from_last_attempt(self):
        coord = _make_coordinator()
        coord.forecast_enabled = True
        coord._forecast_cache = None
        coord.runtime.last_forecast_fetch = None
        coord.runtime.forecast_consecutive_failures = 5
        coord._unsubs = []
        coord._bg_tasks = set()
        coord._stopped = False

        scheduled = []

        def fake_create_task(coro):
            coro.close()
            t = MagicMock()
            scheduled.append(t)
            return t

        coord.hass.async_create_task = fake_create_task
        t0 = datetime(2026, 11, 17, 12, 0, 0, tzinfo=UTC)

        # First call at t0 schedules a fetch; next two calls 2s apart must back off.
        coord._get_cached_or_schedule_forecast(t0)
        coord.runtime.forecast_inflight = False
        coord._get_cached_or_schedule_forecast(t0 + timedelta(seconds=2))
        coord._get_cached_or_schedule_forecast(t0 + timedelta(seconds=4))
        assert len(scheduled) == 1

    def test_cached_forecast_failure_backs_off_from_last_attempt_not_old_success(self):
        coord = _make_coordinator()
        coord.forecast_enabled = True
        coord._forecast_cache = {"daily": [{"date": "2026-11-17"}]}
        old_success = datetime(2026, 11, 17, 6, 0, 0, tzinfo=UTC)
        coord.runtime.last_forecast_fetch = old_success
        coord.runtime.forecast_consecutive_failures = 2  # 2 * 60 = 120s? or FORECAST_MIN_RETRY_S * 2
        coord._unsubs = []
        coord._bg_tasks = set()
        coord._stopped = False

        scheduled = []

        def fake_create_task(coro):
            coro.close()
            t = MagicMock()
            scheduled.append(t)
            return t

        coord.hass.async_create_task = fake_create_task
        t0 = datetime(2026, 11, 17, 12, 0, 0, tzinfo=UTC)

        coord._get_cached_or_schedule_forecast(t0)
        coord.runtime.forecast_inflight = False
        coord._get_cached_or_schedule_forecast(t0 + timedelta(seconds=5))
        assert len(scheduled) == 1

    async def test_fetch_clears_inflight_flag_on_unexpected_error_and_cancellation(self):
        import asyncio

        coord = _make_coordinator()
        coord.config_entry = None
        coord.forecast_enabled = True
        coord.entry_options["forecast_provider"] = "open_meteo"
        coord.forecast_lat = 37.9
        coord.forecast_lon = 23.7
        coord.runtime.forecast_inflight = True

        with (
            patch("custom_components.ws_core.coordinator.async_get_clientsession", return_value=MagicMock()),
            patch(
                "custom_components.ws_core.coordinator.get_provider",
                side_effect=asyncio.CancelledError(),
            ),
        ):
            with pytest.raises(asyncio.CancelledError):
                await coord._async_fetch_forecast()
        assert coord.runtime.forecast_inflight is False

    async def test_stop_cancels_bg_tasks_and_blocks_late_publish(self):
        import asyncio

        coord = _make_coordinator()
        coord.config_entry = None
        coord.forecast_enabled = True
        coord.entry_options["forecast_provider"] = "open_meteo"
        coord.forecast_lat = 37.9
        coord.forecast_lon = 23.7
        coord.mqtt_enabled = False
        coord._mqtt_discovery_published = False
        coord._learning_store = None
        coord._history_store = None
        coord._pattern = None
        coord._unsubs = []
        coord._bg_tasks = set()
        coord._stopped = False
        coord.async_set_updated_data = MagicMock()
        coord._async_save_history = MagicMock()

        async def _noop_save():
            return None

        coord._async_save_history = _noop_save

        gate = asyncio.Event()

        class SlowProvider:
            PROVIDER_NAME = "Slow"

            async def async_fetch(self, *a, **kw):
                await gate.wait()
                return {"provider": "open_meteo", "daily": [], "hourly": []}

        def real_task(coro):
            return asyncio.create_task(coro)

        coord.hass.async_create_task = real_task
        with (
            patch("custom_components.ws_core.coordinator.async_get_clientsession", return_value=MagicMock()),
            patch("custom_components.ws_core.coordinator.get_provider", return_value=SlowProvider()),
        ):
            coord._get_cached_or_schedule_forecast(datetime.now(UTC))
            assert len(coord._bg_tasks) == 1
            task = next(iter(coord._bg_tasks))
            await asyncio.sleep(0)
            await coord.async_stop()
            await asyncio.sleep(0)
            assert task.cancelled()
            coord.async_set_updated_data.assert_not_called()

    async def test_late_completion_after_stop_does_not_publish(self):
        coord = _make_coordinator()
        coord.config_entry = None
        coord.forecast_enabled = True
        coord.entry_options["forecast_provider"] = "open_meteo"
        coord.forecast_lat = 37.9
        coord.forecast_lon = 23.7
        coord._stopped = True
        coord.async_set_updated_data = MagicMock()

        class FastProvider:
            PROVIDER_NAME = "Fast"

            async def async_fetch(self, *a, **kw):
                return {"provider": "open_meteo", "daily": [], "hourly": []}

        with (
            patch("custom_components.ws_core.coordinator.async_get_clientsession", return_value=MagicMock()),
            patch("custom_components.ws_core.coordinator.get_provider", return_value=FastProvider()),
        ):
            await coord._async_fetch_forecast()
        coord.async_set_updated_data.assert_not_called()
        assert coord.runtime.forecast_inflight is False


class TestForecastTilePadding:
    def test_skips_empty_padding_days(self):
        coord = _make_coordinator()
        daily = [
            {"date": "2026-11-17", "tmax_c": 12.0, "tmin_c": 4.0, "precip_mm": 0.0, "wind_kmh": 10.0, "weathercode": 1},
            {"date": "2026-11-18", "tmax_c": 14.0, "tmin_c": 5.0, "precip_mm": 0.0, "wind_kmh": 8.0, "weathercode": 2},
            {
                "date": "2026-11-19",
                "tmax_c": 11.0,
                "tmin_c": 3.0,
                "precip_mm": 2.0,
                "wind_kmh": 15.0,
                "weathercode": 61,
            },
            {"date": "", "tmax_c": None, "tmin_c": None, "precip_mm": None, "wind_kmh": None, "weathercode": None},
            {"date": "", "tmax_c": None, "tmin_c": None, "precip_mm": None, "wind_kmh": None, "weathercode": None},
        ]
        tiles = coord._build_forecast_tiles(daily)
        assert len(tiles) == 3
        assert all(t["date"] for t in tiles)


class TestForecastValidity:
    def test_expired_cache_and_past_date_do_not_feed_rain_blend(self):
        from custom_components.ws_core.const import (
            KEY_FORECAST,
            KEY_FORECAST_AGREEMENT,
            KEY_RAIN_PROBABILITY,
            KEY_RAIN_PROBABILITY_COMBINED,
        )

        coord = _make_coordinator(humidity=70.0, pressure=1012.0)
        coord.forecast_enabled = True
        coord.entry_options["forecast_provider"] = "open_meteo"
        coord.config_entry = None
        coord._learning_state = MagicMock()
        coord._learning_state.forecast_outcomes = []
        coord._learning_state.blend_local = 0.5
        coord._learning_state.blend_openmeteo = 0.5

        now = datetime(2026, 11, 17, 14, 0, tzinfo=UTC)
        # Cached forecast from Nov 1 claiming 100% rain prob -> expired on Nov 17
        coord._forecast_cache = {
            "provider": "open_meteo",
            "daily": [{"date": "2026-11-01", "tmax_c": 15.0, "tmin_c": 8.0, "precip_prob": 100}],
            "hourly": [],
        }
        coord.runtime.last_forecast_fetch = datetime(2026, 11, 1, 12, 0, tzinfo=UTC)

        data: dict = {}
        coord._compute_rain_probability(data, mslp=1012.0, trend_3h=0.0, rh=70.0, now=now)
        assert data[KEY_RAIN_PROBABILITY_COMBINED] == data[KEY_RAIN_PROBABILITY]
        assert data["_forecast_status"] == "local_only"

        # Midnight rollover: cache fetched recently (1h ago at 23:00 yesterday),
        # but only yesterday's date row is present.
        coord.runtime.last_forecast_fetch = now - timedelta(hours=1)
        coord._forecast_cache = {
            "provider": "open_meteo",
            "daily": [{"date": "2026-11-16", "tmax_c": 15.0, "tmin_c": 8.0, "precip_prob": 100}],
            "hourly": [],
        }
        data2: dict = {}
        coord._compute_rain_probability(data2, mslp=1012.0, trend_3h=0.0, rh=70.0, now=now)
        assert data2[KEY_RAIN_PROBABILITY_COMBINED] == data2[KEY_RAIN_PROBABILITY]
        assert data2["_forecast_status"] == "local_only"

        # Forecast agreement must also not run on expired cache
        data2["zambretti_number"] = 10
        coord._compute_forecast_agreement(data2, now=now)
        assert KEY_FORECAST_AGREEMENT not in data2

        # Fresh cache with today's date blends normally and reports ok/degraded
        coord._forecast_cache = {
            "provider": "open_meteo",
            "daily": [{"date": "2026-11-17", "tmax_c": 15.0, "tmin_c": 8.0, "precip_prob": 100}],
            "hourly": [],
        }
        data3: dict = {}
        coord._compute_rain_probability(data3, mslp=1012.0, trend_3h=0.0, rh=70.0, now=now)
        assert data3[KEY_RAIN_PROBABILITY_COMBINED] > data3[KEY_RAIN_PROBABILITY]
        assert data3["_forecast_status"] == "ok"

        # _compute() also drops expired rows from KEY_FORECAST when stale
        from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

        from custom_components.ws_core.coordinator import WSStationCoordinator

        with patch.object(DataUpdateCoordinator, "__init__", lambda self, *a, **kw: None):
            real_coord = WSStationCoordinator(
                coord.hass, {"entry_id": "fv", "sources": coord.sources, "forecast_enabled": True}, {}
            )
        real_coord._forecast_cache = {
            "provider": "open_meteo",
            "daily": [{"date": "2026-11-01", "tmax_c": 15.0, "tmin_c": 8.0, "precip_prob": 100}],
            "hourly": [{"datetime": "2026-11-01T12:00", "temp_c": 15.0}],
        }
        real_coord.runtime.last_forecast_fetch = datetime(2026, 11, 1, 12, 0, tzinfo=UTC)
        with patch.object(real_coord, "_get_cached_or_schedule_forecast", return_value=real_coord._forecast_cache):
            full = real_coord._compute(sample=False)
        assert full.get(KEY_FORECAST) in (None, {"provider": "open_meteo", "daily": [], "hourly": []}) or not (
            (full.get(KEY_FORECAST) or {}).get("daily")
        )

        # Fresh cache across midnight where daily rows aged out still retains valid hourly rows
        recent_fc = {
            "provider": "open_meteo",
            "daily": [{"date": "2026-11-16", "tmax_c": 15.0, "tmin_c": 8.0, "precip_prob": 20}],
            "hourly": [{"datetime": "2026-11-17T01:00", "temp_c": 12.0}],
        }
        real_coord.runtime.last_forecast_fetch = now - timedelta(hours=1)
        published = real_coord._published_forecast(recent_fc, now=now)
        assert published is not None
        assert published["daily"] == []
        assert published["hourly"] == [{"datetime": "2026-11-17T01:00", "temp_c": 12.0}]


class TestSoilMoistureUnits:
    """Soil moisture unit handling and ambiguous_soil_moisture_unit Repairs issue."""

    @staticmethod
    def _build_real_coord(soil_state, soil_unit: str = "auto"):
        from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

        from custom_components.ws_core.const import (
            CONF_ENABLE_SOIL,
            CONF_SOIL_MOISTURE_UNIT,
            SRC_SOIL_MOISTURE,
        )
        from custom_components.ws_core.coordinator import WSStationCoordinator

        stub = _make_coordinator()
        sources = {**stub.sources, SRC_SOIL_MOISTURE: "sensor.soil"}
        orig_get = stub.hass.states.get
        stub.hass.states.get = lambda eid: soil_state if eid == "sensor.soil" else orig_get(eid)
        with patch.object(DataUpdateCoordinator, "__init__", lambda self, *a, **kw: None):
            coord = WSStationCoordinator(
                stub.hass,
                {
                    "entry_id": "soil_test",
                    "sources": sources,
                    CONF_ENABLE_SOIL: True,
                    CONF_SOIL_MOISTURE_UNIT: soil_unit,
                },
                {},
            )
        coord.suppress_notifications = False
        return coord

    def test_percent_unit_not_multiplied_and_no_issue(self):
        from types import SimpleNamespace

        from custom_components.ws_core.const import KEY_SOIL_MOISTURE

        coord = self._build_real_coord(SimpleNamespace(state="1.0", attributes={"unit_of_measurement": "%"}))
        with (
            patch("custom_components.ws_core.coordinator.ir.async_create_issue") as mock_create,
            patch("custom_components.ws_core.coordinator.ir.async_delete_issue") as mock_delete,
        ):
            data = coord._compute(sample=False)

        assert data[KEY_SOIL_MOISTURE] == 1.0
        created_ids = [c.args[2] for c in mock_create.call_args_list]
        assert not any(iid.startswith("ambiguous_soil_moisture_unit") for iid in created_ids)
        deleted_ids = [c.args[2] for c in mock_delete.call_args_list]
        assert any(iid.startswith("ambiguous_soil_moisture_unit") for iid in deleted_ids)

    def test_fraction_unit_multiplied_without_issue(self):
        from types import SimpleNamespace

        from custom_components.ws_core.const import KEY_SOIL_MOISTURE

        coord = self._build_real_coord(SimpleNamespace(state="0.35", attributes={"unit_of_measurement": "m³/m³"}))
        with (
            patch("custom_components.ws_core.coordinator.ir.async_create_issue") as mock_create,
            patch("custom_components.ws_core.coordinator.ir.async_delete_issue") as mock_delete,
        ):
            data = coord._compute(sample=False)

        assert data[KEY_SOIL_MOISTURE] == 35.0
        created_ids = [c.args[2] for c in mock_create.call_args_list]
        assert not any(iid.startswith("ambiguous_soil_moisture_unit") for iid in created_ids)
        deleted_ids = [c.args[2] for c in mock_delete.call_args_list]
        assert any(iid.startswith("ambiguous_soil_moisture_unit") for iid in deleted_ids)

    def test_missing_unit_auto_keeps_legacy_and_raises_issue_until_explicit(self):
        from types import SimpleNamespace

        from custom_components.ws_core.const import (
            CONF_SOIL_MOISTURE_UNIT,
            ENTRY_REPAIR_ISSUES,
            KEY_SOIL_MOISTURE,
        )

        assert "ambiguous_soil_moisture_unit" in ENTRY_REPAIR_ISSUES

        coord = self._build_real_coord(SimpleNamespace(state="1.0", attributes={}), soil_unit="auto")
        with (
            patch("custom_components.ws_core.coordinator.ir.async_create_issue") as mock_create,
            patch("custom_components.ws_core.coordinator.ir.async_delete_issue"),
        ):
            data = coord._compute(sample=False)

        assert data[KEY_SOIL_MOISTURE] == 100.0
        created_ids = [c.args[2] for c in mock_create.call_args_list]
        assert any(iid.startswith("ambiguous_soil_moisture_unit") for iid in created_ids)

        # Switching soil_moisture_unit to explicit "percent" resolves ambiguity and clears issue
        coord.entry_options[CONF_SOIL_MOISTURE_UNIT] = "percent"
        with (
            patch("custom_components.ws_core.coordinator.ir.async_create_issue") as mock_create2,
            patch("custom_components.ws_core.coordinator.ir.async_delete_issue") as mock_delete2,
        ):
            data2 = coord._compute(sample=False)

        assert data2[KEY_SOIL_MOISTURE] == 1.0
        created_ids2 = [c.args[2] for c in mock_create2.call_args_list]
        assert not any(iid.startswith("ambiguous_soil_moisture_unit") for iid in created_ids2)
        deleted_ids2 = [c.args[2] for c in mock_delete2.call_args_list]
        assert any(iid.startswith("ambiguous_soil_moisture_unit") for iid in deleted_ids2)


class TestPR5CalibrationAndClimatology:
    """PR 5: Open-Meteo neighbor QC elevation check, one-time bias reset, 30d climatology."""

    async def test_neighbor_qc_sends_elevation_and_skips_mismatched_temp_pressure(self):
        from custom_components.ws_core.const import (
            CONF_ENABLE_AUTO_CALIBRATION,
            KEY_NORM_HUMIDITY,
            KEY_NORM_PRESSURE_HPA,
            KEY_NORM_TEMP_C,
        )
        from custom_components.ws_core.learning_state import LearningState

        coord = _make_coordinator()
        coord.forecast_lat = 46.5
        coord.forecast_lon = 10.2
        coord.elevation_m = 200.0
        coord.config_entry = None
        coord.entry_options = {CONF_ENABLE_AUTO_CALIBRATION: True}
        coord._learning_state = LearningState()
        coord.data = {
            KEY_NORM_TEMP_C: 20.0,
            KEY_NORM_HUMIDITY: 55.0,
            KEY_NORM_PRESSURE_HPA: 990.0,
        }

        requested_urls: list[str] = []

        class FakeResp:
            def __init__(self, status: int, payload: dict):
                self.status = status
                self._payload = payload

            async def json(self):
                return self._payload

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

        class FakeSession:
            def __init__(self, payload: dict):
                self._payload = payload

            def get(self, url, timeout=None):
                requested_urls.append(url)
                return FakeResp(200, self._payload)

        # Returned model terrain height is 550m (>1m away from station 200m)
        mismatched_payload = {
            "elevation": 550.0,
            "current": {"temperature_2m": 16.0, "relative_humidity_2m": 50.0, "surface_pressure": 950.0},
        }
        with patch(
            "custom_components.ws_core.coordinator.async_get_clientsession",
            return_value=FakeSession(mismatched_payload),
        ):
            await coord._async_fetch_neighbor_qc()

        assert requested_urls
        assert "elevation=200.0" in requested_urls[0]
        assert coord._neighbor_qc_cache["elevation"] == 550.0
        # Temperature and pressure must not update when elevation differs by > 1 m
        assert coord._learning_state.cal_bias_temp_c is None
        assert coord._learning_state.cal_bias_pressure_hpa is None
        assert coord._learning_state.cal_bias_humidity == 5.0

        # When returned elevation matches station within 1 m, temp and pressure DO update
        matched_payload = {
            "elevation": 200.4,
            "current": {"temperature_2m": 19.0, "relative_humidity_2m": 50.0, "surface_pressure": 989.0},
        }
        with patch(
            "custom_components.ws_core.coordinator.async_get_clientsession",
            return_value=FakeSession(matched_payload),
        ):
            await coord._async_fetch_neighbor_qc()

        assert coord._learning_state.cal_bias_temp_c == 1.0
        assert coord._learning_state.cal_bias_pressure_hpa == 1.0

    async def test_auto_calibration_performs_one_time_bias_reset_on_first_run(self):
        from custom_components.ws_core.const import (
            CONF_ENABLE_AUTO_CALIBRATION,
            KEY_NORM_HUMIDITY,
            KEY_NORM_PRESSURE_HPA,
            KEY_NORM_TEMP_C,
        )
        from custom_components.ws_core.learning_state import CALIBRATION_BIAS_REF_VERSION, LearningState

        coord = _make_coordinator()
        coord.elevation_m = 200.0
        coord.config_entry = None
        coord.entry_options = {CONF_ENABLE_AUTO_CALIBRATION: True}
        coord._learning_state = LearningState(
            solar_lux_factor=125.0,
            cal_bias_temp_c=4.0,
            cal_bias_humidity=10.0,
            cal_bias_pressure_hpa=-5.0,
            cal_bias_n=200,
            cal_bias_ref_version=0,
            cal_last_auto_apply_date="2026-11-10",
        )
        coord.data = {
            KEY_NORM_TEMP_C: 20.0,
            KEY_NORM_HUMIDITY: 55.0,
            KEY_NORM_PRESSURE_HPA: 990.0,
        }

        await coord._maybe_update_auto_calibration(
            {"temp_c": 20.0, "humidity": 55.0, "pressure_hpa": 990.0, "elevation": 200.0}
        )

        # Legacy bias (n=200, temp=4.0) was cleared before folding the new zero-delta sample
        assert coord._learning_state.cal_bias_ref_version == CALIBRATION_BIAS_REF_VERSION
        assert coord._learning_state.cal_bias_n == 1
        assert coord._learning_state.cal_bias_temp_c == 0.0
        assert coord._learning_state.solar_lux_factor == 125.0
        assert coord._learning_state.cal_last_auto_apply_date == "2026-11-10"

    def test_compute_climatology_uses_strict_30_day_window(self):
        from custom_components.ws_core.const import (
            KEY_CLIMATOLOGY_30D,
            KEY_NORM_TEMP_C,
            KEY_RAIN_ANOMALY_30D,
            KEY_TEMP_ANOMALY_30D,
        )
        from custom_components.ws_core.learning_state import LearningState

        coord = _make_coordinator()
        # 60 older cool/dry days followed by 30 warm/wet days
        older_days = [
            {"date": f"2026-08-{i + 1:02d}", "t_high": 10.0, "t_low": 0.0, "rain_total": 0.0} for i in range(60)
        ]
        recent_days = [
            {"date": f"2026-10-{i + 1:02d}", "t_high": 30.0, "t_low": 20.0, "rain_total": 10.0} for i in range(30)
        ]
        coord._learning_state = LearningState(climatology_days=older_days + recent_days)

        data = {KEY_NORM_TEMP_C: 25.0, "_rain_today_mm": 10.0}
        coord._compute_climatology(data)

        assert data[KEY_CLIMATOLOGY_30D] == 30
        assert data[KEY_TEMP_ANOMALY_30D] == 0.0
        assert data[KEY_RAIN_ANOMALY_30D] == 0.0


class TestPR6Fixes:
    """PR 6: solar midnight rollover gap, blitzortung throttle, missing extremes, repairs."""

    def test_solar_energy_publishes_zero_after_midnight_before_sample_tick(self):
        from custom_components.ws_core.const import KEY_PEAK_SUN_HOURS, KEY_SOLAR_ENERGY_TODAY_WHM2

        coord = _make_coordinator()
        now_utc = datetime(2026, 11, 17, 0, 0, 5, tzinfo=UTC)
        local_yesterday = (dt_util.as_local(now_utc).date() - timedelta(days=1)).isoformat()
        coord._solar_energy_date = local_yesterday
        coord._solar_energy_today_whm2 = 2450.0
        coord._solar_energy_previous_whm2 = 1800.0
        coord._solar_energy_previous_date = ""
        coord._solar_today_meta = {"date": local_yesterday, "energy_whm2": 2450.0}
        coord._solar_previous_meta = {}
        coord._get_solar_radiation_for_et0 = MagicMock(return_value=0.0)

        data: dict = {}
        coord._compute_solar_energy(data, now_utc, max_solar=0.0, sample=False)

        assert data[KEY_SOLAR_ENERGY_TODAY_WHM2] == 0.0
        assert data[KEY_PEAK_SUN_HOURS] == 0.0
        # Must not roll state before the sample tick
        assert coord._solar_energy_date == local_yesterday
        assert coord._solar_energy_today_whm2 == 2450.0

    def test_blitzortung_discovery_skipped_for_physical_source_and_throttled(self):
        from custom_components.ws_core.const import SRC_LIGHTNING_COUNT

        # Physical lightning sensor mapped -> no registry scan at all
        coord = _make_coordinator()
        coord.lightning_enabled = True
        coord._lightning_proximity_km = 25.0
        coord._lightning_count_history_1h = deque()
        coord._lightning_last_count = None
        coord._lightning_last_strike_ts = None
        coord._lightning_last_near_strike_ts = None
        coord._blitzortung_sources = {}
        coord._last_blitz_scan_ts = None
        coord.sources = {**coord.sources, SRC_LIGHTNING_COUNT: "sensor.wh57_count"}

        with patch.object(coord, "_discover_blitzortung") as mock_scan:
            coord._compute_lightning({}, datetime.now(UTC))
            coord._compute_lightning({}, datetime.now(UTC))
            mock_scan.assert_not_called()

        # No physical lightning source -> rate-limited to once per 300s
        coord.sources.pop(SRC_LIGHTNING_COUNT, None)
        fake_mono = [1000.0]
        with (
            patch("custom_components.ws_core.coordinator.time.monotonic", side_effect=lambda: fake_mono[0]),
            patch.object(coord, "_discover_blitzortung") as mock_scan2,
        ):
            coord._compute_lightning({}, datetime.now(UTC))
            fake_mono[0] = 1060.0
            coord._compute_lightning({}, datetime.now(UTC))
            fake_mono[0] = 1299.0
            coord._compute_lightning({}, datetime.now(UTC))
            assert mock_scan2.call_count == 1
            fake_mono[0] = 1301.0
            coord._compute_lightning({}, datetime.now(UTC))
            assert mock_scan2.call_count == 2

    def test_period_extremes_survive_missing_temperature_and_gust(self):
        from custom_components.ws_core.const import (
            KEY_TEMP_HIGH_ALL_TIME,
            KEY_TEMP_HIGH_MONTH,
            KEY_TEMP_HIGH_WEEK,
            KEY_TEMP_HIGH_YEAR,
            KEY_TEMP_LOW_ALL_TIME,
            KEY_TEMP_LOW_MONTH,
            KEY_TEMP_LOW_WEEK,
            KEY_TEMP_LOW_YEAR,
            KEY_TEMP_MONTH_REF,
            KEY_TEMP_WEEK_REF,
            KEY_TEMP_YEAR_REF,
            KEY_WIND_GUST_MAX_ALL_TIME,
            KEY_WIND_GUST_MAX_MONTH,
            KEY_WIND_GUST_MAX_YEAR,
            KEY_WIND_GUST_MONTH_REF,
            KEY_WIND_GUST_YEAR_REF,
        )

        coord = _make_coordinator()
        now_local = dt_util.now()
        year_key = now_local.strftime("%Y")
        week_key = now_local.strftime("%G-W%V")
        month_key = now_local.strftime("%Y-%m")

        coord._temp_year_key = year_key
        coord._temp_high_year = 34.5
        coord._temp_low_year = -2.1
        coord._temp_high_all_time = 41.2
        coord._temp_low_all_time = -8.4
        coord._temp_week_isoweek = week_key
        coord._temp_high_week = 22.0
        coord._temp_low_week = 5.0
        coord._temp_month_key = month_key
        coord._temp_high_month = 25.0
        coord._temp_low_month = 3.0
        coord._gust_month_key = month_key
        coord._gust_max_month = 18.5
        coord._gust_year_key = year_key
        coord._gust_max_year = 24.0
        coord._gust_max_all_time = 29.5

        data: dict = {}
        coord._update_temp_year_all_time(data, None)
        coord._update_temp_week_month(data, None)
        coord._update_gust_month_year_all_time(data, None)

        assert data[KEY_TEMP_HIGH_YEAR] == 34.5
        assert data[KEY_TEMP_LOW_YEAR] == -2.1
        assert data[KEY_TEMP_YEAR_REF] == year_key
        assert data[KEY_TEMP_HIGH_ALL_TIME] == 41.2
        assert data[KEY_TEMP_LOW_ALL_TIME] == -8.4
        assert data[KEY_TEMP_HIGH_WEEK] == 22.0
        assert data[KEY_TEMP_LOW_WEEK] == 5.0
        assert data[KEY_TEMP_WEEK_REF] == week_key
        assert data[KEY_TEMP_HIGH_MONTH] == 25.0
        assert data[KEY_TEMP_LOW_MONTH] == 3.0
        assert data[KEY_TEMP_MONTH_REF] == month_key
        assert data[KEY_WIND_GUST_MAX_MONTH] == 18.5
        assert data[KEY_WIND_GUST_MONTH_REF] == month_key
        assert data[KEY_WIND_GUST_MAX_YEAR] == 24.0
        assert data[KEY_WIND_GUST_YEAR_REF] == year_key
        assert data[KEY_WIND_GUST_MAX_ALL_TIME] == 29.5

    def test_repair_issues_registered_and_cleared_on_suppress_and_disable(self):
        from custom_components.ws_core.const import DOMAIN, ENTRY_REPAIR_ISSUES

        assert "et0_pm_unavailable" in ENTRY_REPAIR_ISSUES
        assert "ambiguous_soil_moisture_unit" in ENTRY_REPAIR_ISSUES

        coord = _make_coordinator()
        coord.forecast_enabled = False
        coord.runtime.forecast_consecutive_failures = 5
        coord.forecast_lat = None
        coord._missing_sources_since = None
        coord.suppress_notifications = True
        coord._source_is_stale = lambda k, now: False
        coord._alert_debounce_raw = {}
        coord._alert_debounce_clear = {}
        coord._alert_active = {}
        coord._eval_alert = MagicMock(return_value=False)

        with (
            patch("custom_components.ws_core.coordinator.HAS_REPAIRS", True),
            patch("custom_components.ws_core.coordinator.ir.async_delete_issue") as mock_delete,
        ):
            coord._compute_health({}, datetime.now(UTC), [], [], sample=False)

        deleted = {c.args[2] for c in mock_delete.call_args_list if c.args[:2] == (coord.hass, DOMAIN)}
        for name in ENTRY_REPAIR_ISSUES:
            assert coord._issue_id(name) in deleted

        # Disabling forecast must also clear forecast_api_failures even with suppress=False
        coord.suppress_notifications = False
        with (
            patch("custom_components.ws_core.coordinator.HAS_REPAIRS", True),
            patch("custom_components.ws_core.coordinator.ir.async_create_issue") as mock_create,
            patch("custom_components.ws_core.coordinator.ir.async_delete_issue") as mock_delete2,
        ):
            coord._compute_health({}, datetime.now(UTC), [], [], sample=False)

        created2 = [c.args[2] for c in mock_create.call_args_list]
        assert not any(iid.startswith("forecast_api_failures") for iid in created2)
        deleted2 = {c.args[2] for c in mock_delete2.call_args_list}
        assert coord._issue_id("forecast_api_failures") in deleted2
        assert coord._issue_id("large_calibration_offset") in deleted2
