"""Tests for WSStationCoordinator compute methods.

These tests validate the coordinator's data transformation pipeline
without requiring a full Home Assistant environment. We mock the HA
state machine and test each _compute_* sub-method in isolation.
"""

import math
import os
import sys
from collections import deque
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from custom_components.ws_core.const import (
    CONF_CLIMATE_REGION,
    CONF_ELEVATION_M,
    CONF_FORECAST_ENABLED,
    CONF_HEMISPHERE,
    CONF_SOURCES,
    CONF_STALENESS_S,
    KEY_ALERT_MESSAGE,
    KEY_ALERT_STATE,
    KEY_DATA_QUALITY,
    KEY_DEW_POINT_C,
    KEY_FEELS_LIKE_C,
    KEY_FROST_POINT_C,
    KEY_HEALTH_DISPLAY,
    KEY_NORM_HUMIDITY,
    KEY_NORM_PRESSURE_HPA,
    KEY_NORM_TEMP_C,
    KEY_NORM_WIND_DIR_DEG,
    KEY_NORM_WIND_GUST_MS,
    KEY_NORM_WIND_SPEED_MS,
    KEY_PACKAGE_OK,
    KEY_PRESSURE_TREND_HPAH,
    KEY_SEA_LEVEL_PRESSURE_HPA,
    KEY_SENSOR_QUALITY_FLAGS,
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
    mock.last_updated = last_updated or datetime.now(timezone.utc)
    return mock


def _make_coordinator(
    temp=22.0, humidity=55.0, pressure=1013.0,
    wind_speed=3.5, wind_gust=6.0, wind_dir=180.0,
    rain_total=5.2, elevation=50.0,
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
        CONF_HEMISPHERE: "Northern",
        CONF_CLIMATE_REGION: "Mediterranean",
        CONF_STALENESS_S: 900,
        CONF_FORECAST_ENABLED: False,
    }

    hass = MagicMock()
    hass.config.latitude = 37.9
    hass.config.longitude = 23.7

    now = datetime.now(timezone.utc)
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
    coord.hemisphere = "Northern"
    coord.climate_region = "Mediterranean"
    coord.staleness_s = 900
    coord.forecast_enabled = False
    coord.forecast_lat = None
    coord.forecast_lon = None
    coord.forecast_interval_min = 30

    from custom_components.ws_core.coordinator import WSStationRuntime
    coord.runtime = WSStationRuntime()

    return coord


# ---------------------------------------------------------------------------
# Tests: Raw Readings
# ---------------------------------------------------------------------------


class TestComputeRawReadings:
    def test_reads_all_sources(self):
        coord = _make_coordinator()
        data = {}
        now = datetime.now(timezone.utc)
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
        tc, *_ = coord._compute_raw_readings(data, datetime.now(timezone.utc))
        assert abs(tc - 25.0) < 0.1, f"77°F should be 25°C, got {tc}"

    def test_missing_sensor_returns_none(self):
        coord = _make_coordinator()
        coord.hass.states.get = lambda eid: None  # all sensors missing
        data = {}
        tc, rh, p, ws, gs, wd, rain, lux, uv = coord._compute_raw_readings(
            data, datetime.now(timezone.utc)
        )
        assert tc is None
        assert rh is None


# ---------------------------------------------------------------------------
# Tests: Derived Temperature
# ---------------------------------------------------------------------------


class TestComputeDerivedTemperature:
    def test_computes_dew_point(self):
        coord = _make_coordinator()
        data = {}
        now = datetime.now(timezone.utc)
        dew = coord._compute_derived_temperature(data, now, 25.0, 60.0, 3.0)
        assert dew is not None
        assert 15.0 < dew < 18.0
        assert KEY_DEW_POINT_C in data

    def test_computes_frost_point(self):
        coord = _make_coordinator()
        data = {}
        coord._compute_derived_temperature(data, datetime.now(timezone.utc), -5.0, 80.0, 2.0)
        assert KEY_FROST_POINT_C in data
        assert data[KEY_FROST_POINT_C] < -5.0

    def test_computes_wet_bulb(self):
        coord = _make_coordinator()
        data = {}
        coord._compute_derived_temperature(data, datetime.now(timezone.utc), 30.0, 50.0, 2.0)
        assert KEY_WET_BULB_C in data
        assert 18.0 < data[KEY_WET_BULB_C] < 25.0

    def test_computes_feels_like(self):
        coord = _make_coordinator()
        data = {}
        coord._compute_derived_temperature(data, datetime.now(timezone.utc), 30.0, 70.0, 5.0)
        assert KEY_FEELS_LIKE_C in data

    def test_handles_none_gracefully(self):
        coord = _make_coordinator()
        data = {}
        dew = coord._compute_derived_temperature(data, datetime.now(timezone.utc), None, None, None)
        assert dew is None
        assert KEY_DEW_POINT_C not in data


# ---------------------------------------------------------------------------
# Tests: Derived Pressure
# ---------------------------------------------------------------------------


class TestComputeDerivedPressure:
    def test_computes_mslp(self):
        coord = _make_coordinator(elevation=100.0)
        data = {}
        now = datetime.now(timezone.utc)
        trend, mslp = coord._compute_derived_pressure(data, now, 20.0, 1000.0, 60.0)
        assert KEY_SEA_LEVEL_PRESSURE_HPA in data
        assert data[KEY_SEA_LEVEL_PRESSURE_HPA] > 1000.0  # MSLP > station pressure at elevation

    def test_pressure_history_accumulates(self):
        coord = _make_coordinator()
        now = datetime.now(timezone.utc)
        for i in range(5):
            data = {}
            t = now + timedelta(minutes=i * 16)
            coord._compute_derived_pressure(data, t, 20.0, 1013.0 + i * 0.1, 60.0)
        assert len(coord.runtime.pressure_history) >= 2

    def test_zambretti_computed(self):
        coord = _make_coordinator()
        data = {KEY_WIND_QUADRANT: "N"}
        now = datetime.now(timezone.utc)
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
        coord._compute_derived_wind(data, datetime.now(timezone.utc), 5.5, 8.0, 270.0)
        assert KEY_WIND_BEAUFORT in data
        assert data[KEY_WIND_BEAUFORT] == 4  # 5.5 m/s is at Beaufort 3/4 boundary

    def test_computes_quadrant(self):
        coord = _make_coordinator()
        data = {}
        coord._compute_derived_wind(data, datetime.now(timezone.utc), 3.0, 5.0, 90.0)
        assert data[KEY_WIND_QUADRANT] == "E"

    def test_smoothes_direction(self):
        coord = _make_coordinator()
        # First reading
        data = {}
        coord._compute_derived_wind(data, datetime.now(timezone.utc), 3.0, 5.0, 0.0)
        # Second reading at 180° should smooth
        data2 = {}
        coord._compute_derived_wind(data2, datetime.now(timezone.utc), 3.0, 5.0, 180.0)
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
        now = datetime.now(timezone.utc)
        coord._compute_health(data, now, missing=[], missing_entities=[])
        assert data[KEY_PACKAGE_OK] is True
        assert data[KEY_HEALTH_DISPLAY] in ("Online", "Degraded")

    def test_missing_sources(self):
        coord = _make_coordinator()
        data = {}
        now = datetime.now(timezone.utc)
        coord._compute_health(data, now, missing=["temperature"], missing_entities=[])
        assert data[KEY_PACKAGE_OK] is False
        assert "ERROR" in data.get(KEY_DATA_QUALITY, "") or "missing" in data.get(KEY_DATA_QUALITY, "").lower()

    def test_alerts_wind(self):
        coord = _make_coordinator()
        coord.entry_options = {"thresh_wind_gust_ms": 10.0}
        data = {KEY_NORM_WIND_GUST_MS: 15.0, "rain_rate_mmph_filtered": 0.0}
        now = datetime.now(timezone.utc)
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
        now = datetime.now(timezone.utc)
        # Add values spanning 26 hours
        for i in range(26):
            WSStationCoordinator._append_and_prune_24h(
                history, now - timedelta(hours=25 - i), float(i)
            )
        # Should have pruned the oldest entries
        vals = WSStationCoordinator._rolling_values(history)
        assert len(vals) <= 25  # 24h window
        assert vals[-1] == 25.0

    def test_rain_accum_handles_reset(self):
        from custom_components.ws_core.coordinator import WSStationCoordinator
        history = deque()
        now = datetime.now(timezone.utc)
        # Simulate: 0, 1, 2, 0 (reset), 1
        for i, val in enumerate([0.0, 1.0, 2.0, 0.0, 1.0]):
            history.append((now + timedelta(minutes=i * 15), val))
        accum = WSStationCoordinator._rain_accum_24h_from_totals(history)
        # Should count 0→1, 1→2, skip 2→0 (reset), 0→1 = total 3mm
        assert abs(accum - 3.0) < 0.1
