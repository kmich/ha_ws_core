"""Integration tests for Weather Station Core.

Tests config flow, coordinator API handling, sensor entity creation,
diagnostics, and alert accumulation -- all with mocked HA environment.
"""

import json
import os
import sys
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from custom_components.ws_core.const import (
    CONF_CLIMATE_REGION,
    CONF_ELEVATION_M,
    CONF_ENABLE_AIR_QUALITY,
    CONF_ENABLE_DISPLAY_SENSORS,
    CONF_ENABLE_LAUNDRY,
    CONF_ENABLE_ZAMBRETTI,
    CONF_FORECAST_ENABLED,
    CONF_HEMISPHERE,
    CONF_NAME,
    CONF_PREFIX,
    CONF_SOURCES,
    CONF_STALENESS_S,
    DEFAULT_NAME,
    DEFAULT_PREFIX,
    DOMAIN,
    KEY_ALERT_MESSAGE,
    KEY_ALERT_STATE,
    KEY_DATA_QUALITY,
    KEY_NORM_TEMP_C,
    KEY_NORM_WIND_GUST_MS,
    KEY_RAIN_RATE_FILT,
    KEY_SENSOR_QUALITY_FLAGS,
    SRC_GUST,
    SRC_HUM,
    SRC_PRESS,
    SRC_RAIN_TOTAL,
    SRC_TEMP,
    SRC_WIND,
    SRC_WIND_DIR,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_state(state_val, unit="", last_updated=None):
    mock = MagicMock()
    mock.state = str(state_val)
    mock.attributes = {"unit_of_measurement": unit}
    mock.last_updated = last_updated or datetime.now(timezone.utc)
    return mock


SOURCES = {
    SRC_TEMP: "sensor.temp",
    SRC_HUM: "sensor.hum",
    SRC_PRESS: "sensor.press",
    SRC_WIND: "sensor.wind",
    SRC_GUST: "sensor.gust",
    SRC_WIND_DIR: "sensor.wind_dir",
    SRC_RAIN_TOTAL: "sensor.rain",
}


def _make_coordinator(**overrides):
    from custom_components.ws_core.coordinator import WSStationCoordinator, WSStationRuntime

    entry_data = {
        CONF_SOURCES: SOURCES,
        CONF_ELEVATION_M: 50.0,
        CONF_HEMISPHERE: "Northern",
        CONF_CLIMATE_REGION: "Mediterranean",
        CONF_STALENESS_S: 900,
        CONF_FORECAST_ENABLED: False,
        CONF_ENABLE_ZAMBRETTI: True,
    }
    entry_data.update(overrides)

    hass = MagicMock()
    hass.config.latitude = 37.9
    hass.config.longitude = 23.7

    now = datetime.now(timezone.utc)
    states = {
        "sensor.temp": _make_state(22.0, "degC", now),
        "sensor.hum": _make_state(55.0, "%", now),
        "sensor.press": _make_state(1013.0, "hPa", now),
        "sensor.wind": _make_state(3.5, "m/s", now),
        "sensor.gust": _make_state(6.0, "m/s", now),
        "sensor.wind_dir": _make_state(180.0, "deg", now),
        "sensor.rain": _make_state(5.2, "mm", now),
        "sun.sun": MagicMock(state="above_horizon", attributes={"elevation": 45, "azimuth": 180}),
    }
    hass.states.get = lambda eid: states.get(eid)

    with patch.object(WSStationCoordinator, "__init__", lambda self, *a, **kw: None):
        coord = WSStationCoordinator.__new__(WSStationCoordinator)

    coord.hass = hass
    coord.entry_data = entry_data
    coord.entry_options = {}
    coord.sources = SOURCES
    coord.units_mode = "auto"
    coord.elevation_m = 50.0
    coord.hemisphere = "Northern"
    coord.climate_region = "Mediterranean"
    coord.staleness_s = 900
    coord.forecast_enabled = False
    coord.forecast_lat = None
    coord.forecast_lon = None
    coord.forecast_interval_min = 30
    coord.runtime = WSStationRuntime()
    return coord, hass, states


# ===========================================================================
# Config Flow: Structure
# ===========================================================================

class TestConfigFlowStructure:
    """Verify config flow step definitions and translation coverage."""

    def test_all_steps_have_translations(self):
        with open("custom_components/ws_core/strings.json") as f:
            strings = json.load(f)
        config_steps = set(strings.get("config", {}).get("step", {}).keys())
        # Every config step should have a title/description and data dict
        for step_id in config_steps:
            step = strings["config"]["step"][step_id]
            assert "title" in step or "data" in step, f"Step '{step_id}' has no title or data"

    def test_no_zambretti_toggle_in_features(self):
        """Zambretti should be non-disableable: no toggle in features step."""
        with open("custom_components/ws_core/strings.json") as f:
            strings = json.load(f)
        features = strings["config"]["step"]["features"]["data"]
        assert "enable_zambretti" not in features, "Zambretti toggle should be removed"

    def test_go_back_in_all_non_user_steps(self):
        """Every config step except 'user' should have _go_back translation."""
        with open("custom_components/ws_core/strings.json") as f:
            strings = json.load(f)
        for step_id, step_data in strings["config"]["step"].items():
            if step_id == "user":
                assert "_go_back" not in step_data.get("data", {}), "user step should NOT have _go_back"
            else:
                assert "_go_back" in step_data.get("data", {}), f"Step '{step_id}' missing _go_back"

    def test_exactly_one_last_step_true(self):
        """Only the alerts step should have last_step=True."""
        with open("custom_components/ws_core/config_flow.py") as f:
            content = f.read()
        assert content.count("last_step=True") == 1

    def test_options_error_section_exists(self):
        """v1.0.1 fix: options.error section for label translation."""
        with open("custom_components/ws_core/strings.json") as f:
            strings = json.load(f)
        assert "error" in strings.get("options", {}), "options.error section missing"

    def test_strings_and_translations_in_sync(self):
        with open("custom_components/ws_core/strings.json") as f:
            s = json.load(f)
        with open("custom_components/ws_core/translations/en.json") as f:
            e = json.load(f)
        assert s == e


# ===========================================================================
# Config Flow: Back Button
# ===========================================================================

class TestConfigFlowBackButton:
    """Verify back button infrastructure."""

    def test_handle_back_exists(self):
        with open("custom_components/ws_core/config_flow.py") as f:
            content = f.read()
        assert "_handle_back" in content
        assert "_show_step" in content
        assert "_step_history" in content

    def test_back_check_in_all_non_user_steps(self):
        """Every non-user step handler should call _handle_back."""
        import re
        with open("custom_components/ws_core/config_flow.py") as f:
            content = f.read()
        # Only check within config flow class
        config_section = content[:content.find("class WSStationOptionsFlowHandler")]
        # Count steps with back check
        steps = re.findall(r"async def async_step_(\w+)", config_section)
        non_user = [s for s in steps if s != "user"]
        back_calls = config_section.count("_handle_back")
        assert back_calls >= len(non_user), (
            f"Expected >= {len(non_user)} _handle_back calls, found {back_calls}"
        )


# ===========================================================================
# Alert Accumulation
# ===========================================================================

class TestAlertAccumulation:
    """Verify alerts accumulate instead of overwriting."""

    def _run_alerts(self, coord, gust=5.0, rain=0.0, temp=20.0,
                    gust_thr=17.0, rain_thr=20.0, freeze_thr=0.0):
        data = {
            KEY_NORM_WIND_GUST_MS: gust,
            KEY_RAIN_RATE_FILT: rain,
            KEY_NORM_TEMP_C: temp,
        }
        coord.entry_options = {
            "thresh_wind_gust_ms": gust_thr,
            "thresh_rain_rate_mmph": rain_thr,
            "thresh_freeze_c": freeze_thr,
        }
        coord._compute_health(data, datetime.now(timezone.utc), [], [])
        return data

    def test_no_alerts(self):
        coord, _, _ = _make_coordinator()
        data = self._run_alerts(coord, gust=5.0, rain=0.0, temp=20.0)
        assert data[KEY_ALERT_STATE] == "clear"
        assert data["_active_alerts"] == []

    def test_single_wind_alert(self):
        coord, _, _ = _make_coordinator()
        data = self._run_alerts(coord, gust=20.0)
        assert data[KEY_ALERT_STATE] == "warning"
        assert len(data["_active_alerts"]) == 1
        assert data["_active_alerts"][0]["type"] == "wind"

    def test_single_freeze_alert(self):
        coord, _, _ = _make_coordinator()
        data = self._run_alerts(coord, temp=-3.0)
        assert data[KEY_ALERT_STATE] == "advisory"
        assert len(data["_active_alerts"]) == 1
        assert "freeze" in data[KEY_ALERT_MESSAGE].lower()

    def test_wind_plus_rain(self):
        coord, _, _ = _make_coordinator()
        data = self._run_alerts(coord, gust=20.0, rain=25.0)
        assert data[KEY_ALERT_STATE] == "warning"
        assert len(data["_active_alerts"]) == 2
        assert "wind" in data[KEY_ALERT_MESSAGE].lower()
        assert "rain" in data[KEY_ALERT_MESSAGE].lower()

    def test_triple_alert(self):
        coord, _, _ = _make_coordinator()
        data = self._run_alerts(coord, gust=20.0, rain=25.0, temp=-2.0)
        assert data[KEY_ALERT_STATE] == "warning"
        assert len(data["_active_alerts"]) == 3
        # Pipe-separated
        assert "|" in data[KEY_ALERT_MESSAGE]

    def test_warning_beats_advisory(self):
        """With wind (warning) + freeze (advisory), state should be 'warning'."""
        coord, _, _ = _make_coordinator()
        data = self._run_alerts(coord, gust=20.0, temp=-2.0)
        assert data[KEY_ALERT_STATE] == "warning"
        assert data["_alert_icon"] == "mdi:weather-windy"

    def test_alert_attributes_populated(self):
        coord, _, _ = _make_coordinator()
        data = self._run_alerts(coord, gust=20.0)
        assert "_alert_icon" in data
        assert "_alert_color" in data
        assert "_active_alerts" in data

    def test_exact_thresholds_trigger(self):
        coord, _, _ = _make_coordinator()
        data = self._run_alerts(coord, gust=17.0, rain=20.0, temp=0.0)
        assert len(data["_active_alerts"]) == 3

    def test_just_below_thresholds_clear(self):
        coord, _, _ = _make_coordinator()
        data = self._run_alerts(coord, gust=16.9, rain=19.9, temp=0.1)
        assert data[KEY_ALERT_STATE] == "clear"
        assert len(data["_active_alerts"]) == 0


# ===========================================================================
# API Response Handling
# ===========================================================================

class TestAPIResponseHandling:
    """Verify coordinator handles bad/missing API responses gracefully."""

    def test_open_meteo_empty_response(self):
        """Coordinator should not crash on empty Open-Meteo response."""
        coord, _, _ = _make_coordinator()
        # Simulate an empty forecast response
        empty_response = {"daily": {}}
        # The coordinator's _fetch_forecast parses response; verify it handles missing keys
        data = {}
        # Call _compute_forecast if it exists
        if hasattr(coord, "_compute_forecast"):
            try:
                coord._compute_forecast(data, datetime.now(timezone.utc), empty_response)
            except (KeyError, TypeError):
                pytest.fail("_compute_forecast crashed on empty response")

    def test_coordinator_handles_none_rain_rate(self):
        """Rain rate can be None (no rain sensor or filtered value)."""
        coord, _, _ = _make_coordinator()
        data = {
            KEY_NORM_WIND_GUST_MS: 5.0,
            KEY_RAIN_RATE_FILT: None,
            KEY_NORM_TEMP_C: 20.0,
        }
        coord.entry_options = {}
        # Should not crash with None rain_rate
        try:
            coord._compute_health(data, datetime.now(timezone.utc), [], [])
        except (TypeError, ValueError):
            pytest.fail("_compute_health crashed on None rain_rate")

    def test_coordinator_handles_string_values(self):
        """Some HA sensors report string values that need float conversion."""
        coord, _, states = _make_coordinator()
        states["sensor.temp"] = _make_state("unavailable", "degC")
        data = {}
        now = datetime.now(timezone.utc)
        tc, *_ = coord._compute_raw_readings(data, now)
        assert tc is None  # Should gracefully return None, not crash


# ===========================================================================
# Sensor Entity Creation
# ===========================================================================

class TestSensorEntities:
    """Verify sensor descriptors and entity registration."""

    def test_feature_toggle_map_no_zambretti(self):
        """Zambretti should NOT be in the feature toggle map (always enabled)."""
        try:
            from custom_components.ws_core.sensor import _FEATURE_TOGGLE_MAP
            from custom_components.ws_core.const import (
                KEY_ZAMBRETTI_FORECAST,
                KEY_ZAMBRETTI_NUMBER,
                KEY_CURRENT_CONDITION,
            )
            assert KEY_ZAMBRETTI_FORECAST not in _FEATURE_TOGGLE_MAP
            assert KEY_ZAMBRETTI_NUMBER not in _FEATURE_TOGGLE_MAP
            assert KEY_CURRENT_CONDITION not in _FEATURE_TOGGLE_MAP
        except (ImportError, AttributeError):
            # Fallback: check source code directly
            with open("custom_components/ws_core/sensor.py") as f:
                content = f.read()
            toggle_block = content[content.find("_FEATURE_TOGGLE_MAP"):content.find("toggle_key = ")]
            assert "KEY_ZAMBRETTI" not in toggle_block

    def test_all_sensor_keys_have_unique_slugs(self):
        """Every sensor slug override should be unique."""
        import re
        with open("custom_components/ws_core/sensor.py") as f:
            content = f.read()
        block = content[content.find("overrides = {"):content.find("return overrides[key]")]
        slugs = re.findall(r':\s*"(\w+)"', block)
        assert len(slugs) == len(set(slugs)), f"Duplicate slugs found: {[s for s in slugs if slugs.count(s) > 1]}"

    def test_no_switch_for_zambretti(self):
        """Zambretti switch should be removed from FEATURE_SWITCHES."""
        try:
            from custom_components.ws_core.switch import FEATURE_SWITCHES
            conf_keys = [sw.conf_key for sw in FEATURE_SWITCHES]
            assert CONF_ENABLE_ZAMBRETTI not in conf_keys
        except (ImportError, AttributeError):
            with open("custom_components/ws_core/switch.py") as f:
                content = f.read()
            assert "CONF_ENABLE_ZAMBRETTI" not in content


# ===========================================================================
# Diagnostics
# ===========================================================================

class TestDiagnostics:
    """Verify diagnostics output."""

    def test_diagnostics_returns_valid_dict(self):
        import asyncio
        from custom_components.ws_core.diagnostics import async_get_config_entry_diagnostics
        from custom_components.ws_core.coordinator import WSStationCoordinator, WSStationRuntime

        hass = MagicMock()
        entry = MagicMock()
        entry.title = "My Weather Station"
        entry.data = {CONF_SOURCES: SOURCES}
        entry.options = {}
        entry.entry_id = "test_entry_123"

        # Create a mock coordinator
        coord = MagicMock(spec=WSStationCoordinator)
        coord.data = {KEY_DATA_QUALITY: "OK", KEY_SENSOR_QUALITY_FLAGS: []}
        coord.runtime = WSStationRuntime()

        hass.data = {DOMAIN: {"test_entry_123": coord}}
        hass.states.get = lambda eid: _make_state("22.0", "degC")

        result = asyncio.run(async_get_config_entry_diagnostics(hass, entry))

        assert isinstance(result, dict)
        assert result["title"] == "My Weather Station"
        assert result["version"] == "1.0.2"
        assert "entry_data" in result
        assert "sensor_stats" in result
        assert "runtime" in result
        assert result["data_quality"] == "OK"

    def test_diagnostics_redacts_coords(self):
        from custom_components.ws_core.diagnostics import _redact_coords

        data = {"forecast_lat": 37.9, "forecast_lon": 23.7, "name": "Test"}
        redacted = _redact_coords(data)
        assert "forecast_lat" not in redacted
        assert "forecast_lon" not in redacted
        assert redacted["name"] == "Test"

    def test_diagnostics_handles_no_coordinator(self):
        import asyncio
        from custom_components.ws_core.diagnostics import async_get_config_entry_diagnostics

        hass = MagicMock()
        entry = MagicMock()
        entry.title = "Test"
        entry.data = {CONF_SOURCES: {}}
        entry.options = {}
        entry.entry_id = "missing"
        hass.data = {DOMAIN: {}}
        hass.states.get = lambda eid: None

        result = asyncio.run(async_get_config_entry_diagnostics(hass, entry))
        assert result["data_quality"] is None
        assert result["runtime"] == {}


# ===========================================================================
# Version Consistency
# ===========================================================================

class TestVersionConsistency:
    def test_manifest_version(self):
        with open("custom_components/ws_core/manifest.json") as f:
            m = json.load(f)
        assert m["version"] == "1.0.2"

    def test_diagnostics_version(self):
        with open("custom_components/ws_core/diagnostics.py") as f:
            content = f.read()
        assert '"1.0.2"' in content

    def test_pyproject_version(self):
        with open("pyproject.toml") as f:
            content = f.read()
        assert 'version = "1.0.2"' in content
