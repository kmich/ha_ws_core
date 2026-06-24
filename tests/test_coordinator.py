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

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from custom_components.ws_core.const import (
    CONF_CLIMATE_REGION,
    CONF_ELEVATION_M,
    CONF_FORECAST_ENABLED,
    CONF_HEMISPHERE,
    CONF_SOURCES,
    CONF_STALENESS_S,
    KEY_ALERT_STATE,
    KEY_DATA_QUALITY,
    KEY_DEW_POINT_C,
    KEY_FEELS_LIKE_C,
    KEY_FROST_POINT_C,
    KEY_HEALTH_DISPLAY,
    KEY_NORM_WIND_GUST_MS,
    KEY_PACKAGE_OK,
    KEY_SEA_LEVEL_PRESSURE_HPA,
    KEY_WET_BULB_C,
    KEY_WIND_BEAUFORT,
    KEY_WIND_QUADRANT,
    KEY_ZAMBRETTI_FORECAST,
    KEY_ZAMBRETTI_NUMBER,
    SRC_GUST,
    SRC_HUM,
    SRC_PRESS,
    SRC_RAIN_TOTAL,
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
