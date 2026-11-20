"""Tests for v3.0.0 Home Assistant services, actions, and notification blueprint."""

from __future__ import annotations

import json
import pathlib
import shutil
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import voluptuous as vol
from homeassistant.config_entries import ConfigEntryState
from homeassistant.exceptions import ServiceValidationError
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

try:
    from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
except ImportError:
    from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.ws_core import (
    SERVICE_EXPORT_LEARNING,
    SERVICE_GET_STATION_SUMMARY,
    SERVICE_GET_WEATHER_WINDOWS,
    async_setup_entry,
)
from custom_components.ws_core.const import (
    CONF_FORECAST_LAT,
    CONF_FORECAST_LON,
    CONF_FORECAST_PROVIDER,
    CONF_PREFIX,
    DOMAIN,
    KEY_FORECAST,
    KEY_NORM_TEMP_C,
    PROFILE_CUSTOM,
    PROFILE_OUTDOOR_DRYING,
)
from tests.test_coordinator import _make_coordinator


class TestV3Services:
    """Test get_weather_windows, get_station_summary, export_learning_state, and blueprint."""

    def test_get_station_summary_returns_json_serializable_contract(self):
        coord = _make_coordinator()
        coord.config_entry = None
        coord.forecast_enabled = True
        coord.data = {
            KEY_NORM_TEMP_C: 22.5,
            "pressure_trend_hpah": 0.5,
            "rain_rate_filt": 0.0,
            "rain_today_mm": 1.2,
        }

        summary = coord.get_station_summary()
        assert summary["entry_id"] == "station"
        assert summary["forecast_validity"]["provider"] == "open_meteo"
        assert summary["current_conditions"]["temperature_c"] == 22.5
        assert summary["current_conditions"]["rain_today_mm"] == 1.2
        assert "daily_extremes" in summary
        assert "active_alerts" in summary
        assert "forecast_validity" in summary

        # Must be strictly JSON-serializable
        serialized = json.dumps(summary)
        assert len(serialized) > 50

    def test_get_weather_windows_evaluation(self):
        coord = _make_coordinator()
        coord.forecast_lat = 38.0
        coord.forecast_lon = 23.7
        base_dt = datetime(2026, 6, 21, 11, 0, tzinfo=UTC)
        coord.data = {
            KEY_FORECAST: {
                "hourly": [
                    {
                        "datetime": (base_dt + timedelta(hours=h)).isoformat(),
                        "temp_c": 22.0,
                        "apparent_temp_c": 22.0,
                        "precip_prob": 0,
                        "precip_mm": 0.0,
                        "wind_kmh": 10.0,
                        "gust_kmh": 15.0,
                        "humidity": 45.0,
                        "cloud_cover": 10.0,
                    }
                    for h in range(4)
                ]
            }
        }

        with patch("custom_components.ws_core.coordinator.dt_util.now", return_value=base_dt):
            eval_result = coord.get_weather_windows_evaluation(profile_id=PROFILE_OUTDOOR_DRYING)
        assert eval_result["profile_id"] == PROFILE_OUTDOOR_DRYING
        assert eval_result["status"] == "suitable_now"
        assert "evaluated_limits" in eval_result
        assert len(eval_result["slots"]) == 4

        # Must be strictly JSON-serializable
        serialized = json.dumps(eval_result)
        assert len(serialized) > 50

        # Partial limits override preserves all non-overridden limits on outdoor_drying
        for slot in coord.data[KEY_FORECAST]["hourly"]:
            slot["precip_prob"] = 80
            slot["precip_mm"] = 2.0

        with patch("custom_components.ws_core.coordinator.dt_util.now", return_value=base_dt):
            partial = coord.get_weather_windows_evaluation(
                profile_id=PROFILE_OUTDOOR_DRYING,
                custom_limits={"min_duration_h": 3},
            )
        assert partial["evaluated_limits"]["min_duration_h"] == 3
        assert partial["evaluated_limits"]["max_rain_prob_pct"] == 20.0
        assert partial["evaluated_limits"]["max_rain_mm"] == 0.0
        assert partial["status"] == "unsuitable"

    def test_custom_limits_in_get_weather_windows(self):
        coord = _make_coordinator()
        coord.forecast_lat = 38.0
        coord.forecast_lon = 23.7
        coord.data = {KEY_FORECAST: {"hourly": []}}

        custom_limits = {
            "name": "Astronomy",
            "min_duration_h": 3,
            "max_cloud_cover_pct": 10.0,
            "require_daylight": False,
        }
        # Omitted or 'custom' profile_id applies overrides onto PROFILE_CUSTOM
        res = coord.get_weather_windows_evaluation(profile_id=PROFILE_CUSTOM, custom_limits=custom_limits)
        assert res["profile_id"] == PROFILE_CUSTOM
        assert res["evaluated_limits"]["min_duration_h"] == 3
        assert res["evaluated_limits"]["max_cloud_cover_pct"] == 10.0
        assert res["evaluated_limits"]["require_daylight"] is False

        res_default = coord.get_weather_windows_evaluation(custom_limits=custom_limits)
        assert res_default["profile_id"] == PROFILE_CUSTOM

        # Unknown profile_id is rejected even when limits are passed
        with pytest.raises(ValueError, match="Unknown profile 'astronomy'"):
            coord.get_weather_windows_evaluation(profile_id="astronomy", custom_limits=custom_limits)

    async def test_registered_v3_services_and_schema_validation(self, hass, caplog):
        entry = MockConfigEntry(
            domain=DOMAIN,
            entry_id="station",
            data={
                CONF_PREFIX: "ws",
                CONF_FORECAST_PROVIDER: "open_meteo",
                CONF_FORECAST_LAT: 38.0,
                CONF_FORECAST_LON: 23.7,
            },
            options={},
        )
        entry.add_to_hass(hass)

        mock_integration = MagicMock()
        mock_integration.version = "3.0.0"

        with (
            patch("custom_components.ws_core.async_get_integration", return_value=mock_integration),
            patch("custom_components.ws_core.coordinator.WSStationCoordinator.async_start", AsyncMock()),
            patch.object(hass.config_entries, "async_forward_entry_setups", AsyncMock(return_value=True)),
        ):
            assert await async_setup_entry(hass, entry) is True

        entry.mock_state(hass, ConfigEntryState.LOADED)
        coord = entry.runtime_data
        coord.data = {
            KEY_NORM_TEMP_C: 21.0,
            KEY_FORECAST: {
                "hourly": [
                    {"datetime": "2026-06-21T12:00:00+00:00", "temp_c": 22.0},
                    {"datetime": "2026-06-21T13:00:00+00:00", "temp_c": 23.0},
                ]
            },
        }

        # 1. Registered get_station_summary runs cleanly on a real coordinator
        summary_resp = await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_STATION_SUMMARY,
            {},
            blocking=True,
            return_response=True,
        )
        assert "station" in summary_resp
        assert summary_resp["station"]["forecast_validity"]["provider"] == "open_meteo"
        assert summary_resp["station"]["current_conditions"]["temperature_c"] == 21.0

        # 2. Registered export_learning_state accepts full=False and full=True
        compact = await hass.services.async_call(
            DOMAIN,
            SERVICE_EXPORT_LEARNING,
            {"full": False},
            blocking=True,
            return_response=True,
        )
        full = await hass.services.async_call(
            DOMAIN,
            SERVICE_EXPORT_LEARNING,
            {"full": True},
            blocking=True,
            return_response=True,
        )
        assert "streaks" in compact["station"]
        assert "forecast_outcomes" in full["station"]

        # 2b. Calling export_learning_state without return_response preserves INFO log export
        with caplog.at_level("INFO", logger="custom_components.ws_core"):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_EXPORT_LEARNING,
                {},
                blocking=True,
                return_response=False,
            )
        assert "ws_core learning state export" in caplog.text
        assert "forecast_outcomes" in caplog.text

        # 3. Registered get_weather_windows rejects zero, negative, fractional, and bool min_duration_h
        for bad_duration in (0, -2, 1.5, "1.5", True, 24):
            with pytest.raises(vol.Invalid):
                await hass.services.async_call(
                    DOMAIN,
                    SERVICE_GET_WEATHER_WINDOWS,
                    {"limits": {"min_duration_h": bad_duration}},
                    blocking=True,
                    return_response=True,
                )

        # 4. Registered get_weather_windows rejects non-finite limit values
        for bad_limit in (float("nan"), float("inf"), float("-inf"), "nan", "inf"):
            with pytest.raises(vol.Invalid):
                await hass.services.async_call(
                    DOMAIN,
                    SERVICE_GET_WEATHER_WINDOWS,
                    {"limits": {"max_rain_prob_pct": bad_limit}},
                    blocking=True,
                    return_response=True,
                )

        # 5. Unknown profile_id, unknown entry_id, and contradictory limits raise ServiceValidationError
        with pytest.raises(ServiceValidationError):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_GET_WEATHER_WINDOWS,
                {"profile_id": "unknown_profile"},
                blocking=True,
                return_response=True,
            )
        with pytest.raises(ServiceValidationError):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_GET_WEATHER_WINDOWS,
                {"limits": {"min_temp_c": 30.0, "max_temp_c": 10.0}},
                blocking=True,
                return_response=True,
            )
        for svc, data in (
            (SERVICE_GET_WEATHER_WINDOWS, {"entry_id": "missing_entry"}),
            (SERVICE_GET_STATION_SUMMARY, {"entry_id": "missing_entry"}),
            (SERVICE_EXPORT_LEARNING, {"entry_id": "missing_entry"}),
        ):
            with pytest.raises(ServiceValidationError):
                await hass.services.async_call(DOMAIN, svc, data, blocking=True, return_response=True)

    async def test_weather_window_notification_blueprint_fires_15_min_before_start(self, hass):
        src_bp = (
            pathlib.Path(__file__).resolve().parents[1]
            / "blueprints/automation/ws_core/weather_window_notification.yaml"
        )
        dst_bp = pathlib.Path(hass.config.path("blueprints/automation/ws_core/weather_window_notification.yaml"))
        dst_bp.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_bp, dst_bp)

        notify_calls = []

        async def _capture_notify(call):
            notify_calls.append(dict(call.data))

        hass.services.async_register("notify", "persistent_notification", _capture_notify)

        now = dt_util.utcnow().replace(second=0, microsecond=0)
        window_start = now + timedelta(minutes=20)
        hass.states.async_set(
            "sensor.ws_window_outdoor_drying_next_start",
            window_start.isoformat(),
            {
                "device_class": "timestamp",
                "friendly_name": "Outdoor Laundry Drying Next Start",
            },
        )

        ok = await async_setup_component(
            hass,
            "automation",
            {
                "automation": [
                    {
                        "id": "weather_window_alert",
                        "alias": "Weather Window Alert",
                        "use_blueprint": {
                            "path": "ws_core/weather_window_notification.yaml",
                            "input": {
                                "next_start_sensor": "sensor.ws_window_outdoor_drying_next_start",
                            },
                        },
                    }
                ]
            },
        )
        assert ok is True
        await hass.async_block_till_done()

        # 16 minutes before start -> must not have fired yet
        async_fire_time_changed(hass, window_start - timedelta(minutes=16))
        await hass.async_block_till_done()
        assert notify_calls == []

        # 15 minutes before start -> default -00:15:00 offset fires notification
        async_fire_time_changed(hass, window_start - timedelta(minutes=15))
        await hass.async_block_till_done()
        assert len(notify_calls) == 1
        assert notify_calls[0]["title"] == "Weather Window Starting Soon"
        assert "Outdoor Laundry Drying Next Start" in notify_calls[0]["message"]

    def test_weather_window_notification_blueprint_gates_min_ha_version(self):
        from homeassistant.components.automation.config import AUTOMATION_BLUEPRINT_SCHEMA
        from homeassistant.components.blueprint.models import Blueprint
        from homeassistant.util.yaml import load_yaml

        bp_path = (
            pathlib.Path(__file__).resolve().parents[1]
            / "blueprints/automation/ws_core/weather_window_notification.yaml"
        )
        raw = load_yaml(str(bp_path))
        bp = Blueprint(raw, expected_domain="automation", schema=AUTOMATION_BLUEPRINT_SCHEMA)
        assert bp.metadata["homeassistant"]["min_version"] == "2024.10.0"
        assert bp.validate() is None

        with patch("homeassistant.components.blueprint.models.__version__", "2024.6.0"):
            assert bp.validate() == ["Requires at least Home Assistant 2024.10.0"]
        with patch("homeassistant.components.blueprint.models.__version__", "2024.9.3"):
            assert bp.validate() == ["Requires at least Home Assistant 2024.10.0"]

    def test_get_station_summary_excludes_expired_recommendations(self):
        from custom_components.ws_core.const import KEY_WEATHER_WINDOWS, PROFILE_GARDEN_WORK

        coord = _make_coordinator()
        coord.config_entry = None
        coord.forecast_enabled = True
        coord.entry_options[CONF_FORECAST_PROVIDER] = "open_meteo"
        now = datetime(2026, 6, 21, 12, 0, tzinfo=UTC)

        coord.data = {
            KEY_FORECAST: {
                "hourly": [{"datetime": (now + timedelta(hours=h)).isoformat(), "temp_c": 22.0} for h in range(4)]
            },
            KEY_WEATHER_WINDOWS: {
                PROFILE_OUTDOOR_DRYING: {
                    "status": "suitable_now",
                    "next_start": (now - timedelta(hours=3)).isoformat(),
                    "next_end": (now - timedelta(minutes=5)).isoformat(),
                    "duration_h": 3,
                    "reasons_text": ["Suitable now."],
                },
                PROFILE_GARDEN_WORK: {
                    "status": "window_upcoming",
                    "next_start": (now + timedelta(hours=1)).isoformat(),
                    "next_end": (now + timedelta(hours=4)).isoformat(),
                    "duration_h": 3,
                    "reasons_text": ["Starts in 1h."],
                },
            },
        }

        # 1. Expired forecast cache -> exclude all cached recommendations and report 0h horizon
        coord.runtime.last_forecast_fetch = now - timedelta(hours=13)
        with patch("custom_components.ws_core.coordinator.dt_util.now", return_value=now):
            expired_summary = coord.get_station_summary()
        assert expired_summary["forecast_validity"]["is_expired"] is True
        assert expired_summary["forecast_validity"]["hourly_horizon_h"] == 0
        assert expired_summary["weather_windows"] == {}

        # 2. Fresh forecast cache -> exclude passed recommendation, keep future/active one
        coord.runtime.last_forecast_fetch = now - timedelta(minutes=10)
        with patch("custom_components.ws_core.coordinator.dt_util.now", return_value=now):
            fresh_summary = coord.get_station_summary()
        assert fresh_summary["forecast_validity"]["is_expired"] is False
        assert fresh_summary["forecast_validity"]["hourly_horizon_h"] == 4
        assert PROFILE_OUTDOOR_DRYING not in fresh_summary["weather_windows"]
        assert fresh_summary["weather_windows"][PROFILE_GARDEN_WORK]["status"] == "window_upcoming"

    def test_get_station_summary_reports_usable_hourly_horizon(self):
        coord = _make_coordinator()
        coord.config_entry = None
        coord.forecast_enabled = True
        coord.entry_options[CONF_FORECAST_PROVIDER] = "open_meteo"
        now = datetime(2026, 6, 21, 12, 0, tzinfo=UTC)
        coord.runtime.last_forecast_fetch = now - timedelta(hours=3)

        # Mixed slots: 2 past, 1 malformed, 1 duplicate, 3 distinct active/future -> 3 usable hours
        coord.data = {
            KEY_FORECAST: {
                "hourly": [
                    {"datetime": (now - timedelta(hours=3)).isoformat(), "temp_c": 18.0},
                    {"datetime": (now - timedelta(hours=1)).isoformat(), "temp_c": 19.0},
                    {"datetime": "not-a-timestamp", "temp_c": 20.0},
                    {"datetime": now.isoformat(), "temp_c": 21.0},
                    {"datetime": now.isoformat(), "temp_c": 21.5},
                    {"datetime": (now + timedelta(hours=1)).isoformat(), "temp_c": 22.0},
                    {"datetime": (now + timedelta(hours=2)).isoformat(), "temp_c": 23.0},
                ]
            }
        }
        with patch("custom_components.ws_core.coordinator.dt_util.now", return_value=now):
            mixed_summary = coord.get_station_summary()
        assert mixed_summary["forecast_validity"]["is_expired"] is False
        assert mixed_summary["forecast_validity"]["hourly_horizon_h"] == 3

        # Unexpired fetch cache whose hourly slots have all elapsed -> 0 usable hours
        coord.data = {
            KEY_FORECAST: {
                "hourly": [{"datetime": (now - timedelta(hours=h)).isoformat(), "temp_c": 19.0} for h in (4, 3, 2, 1)]
            }
        }
        with patch("custom_components.ws_core.coordinator.dt_util.now", return_value=now):
            past_summary = coord.get_station_summary()
        assert past_summary["forecast_validity"]["is_expired"] is False
        assert past_summary["forecast_validity"]["hourly_horizon_h"] == 0

    async def test_custom_profile_sensors_render_configured_name(self, hass, enable_custom_integrations):
        from custom_components.ws_core.const import (
            CONF_CUSTOM_WINDOW_NAME,
            CONF_ENABLE_WEATHER_WINDOWS,
            CONF_WEATHER_WINDOW_PROFILES,
        )

        entry = MockConfigEntry(
            domain=DOMAIN,
            entry_id="custom_name_entry",
            data={
                CONF_PREFIX: "ws",
                CONF_ENABLE_WEATHER_WINDOWS: True,
                CONF_WEATHER_WINDOW_PROFILES: [PROFILE_CUSTOM],
                CONF_CUSTOM_WINDOW_NAME: "Drone Flying",
                CONF_FORECAST_LAT: 38.0,
                CONF_FORECAST_LON: 23.7,
            },
            options={},
        )
        entry.add_to_hass(hass)

        with (
            patch("custom_components.ws_core.PLATFORMS", ["sensor"]),
            patch("custom_components.ws_core.coordinator.WSStationCoordinator.async_start", AsyncMock()),
            patch("custom_components.ws_core.coordinator.WSStationCoordinator.async_stop", AsyncMock()),
        ):
            assert await hass.config_entries.async_setup(entry.entry_id)
            await hass.async_block_till_done()

        status_state = hass.states.get("sensor.ws_window_custom_status")
        start_state = hass.states.get("sensor.ws_window_custom_next_start")
        end_state = hass.states.get("sensor.ws_window_custom_next_end")
        assert status_state is not None and start_state is not None and end_state is not None
        assert status_state.attributes["friendly_name"].endswith("Drone Flying Status")
        assert start_state.attributes["friendly_name"].endswith("Drone Flying Next Start")
        assert end_state.attributes["friendly_name"].endswith("Drone Flying Next End")
        assert "Custom Window" not in status_state.attributes["friendly_name"]
        assert "not_assessed_by_provider" in status_state.attributes

        # Disabling Weather Windows removes disabled window entities from the registry on reload
        from homeassistant.helpers import entity_registry as er

        with (
            patch("custom_components.ws_core.PLATFORMS", ["sensor"]),
            patch("custom_components.ws_core.coordinator.WSStationCoordinator.async_start", AsyncMock()),
            patch("custom_components.ws_core.coordinator.WSStationCoordinator.async_stop", AsyncMock()),
        ):
            hass.config_entries.async_update_entry(entry, options={CONF_ENABLE_WEATHER_WINDOWS: False})
            await hass.async_block_till_done()

        reg = er.async_get(hass)
        for suffix in ("status", "next_start", "next_end"):
            assert reg.async_get(f"sensor.ws_window_custom_{suffix}") is None

    async def test_public_actions_share_forecast_coverage_contract(self, hass):
        entry = MockConfigEntry(
            domain=DOMAIN,
            entry_id="station",
            data={
                CONF_PREFIX: "ws",
                CONF_FORECAST_PROVIDER: "open_meteo",
                CONF_FORECAST_LAT: 38.0,
                CONF_FORECAST_LON: 23.7,
            },
            options={},
        )
        entry.add_to_hass(hass)

        mock_integration = MagicMock()
        mock_integration.version = "3.0.0"

        with (
            patch("custom_components.ws_core.async_get_integration", return_value=mock_integration),
            patch("custom_components.ws_core.coordinator.WSStationCoordinator.async_start", AsyncMock()),
            patch.object(hass.config_entries, "async_forward_entry_setups", AsyncMock(return_value=True)),
        ):
            assert await async_setup_entry(hass, entry) is True

        entry.mock_state(hass, ConfigEntryState.LOADED)
        coord = entry.runtime_data

        def _row(dt_val):
            return {
                "datetime": dt_val.isoformat() if isinstance(dt_val, datetime) else dt_val,
                "temp_c": 22.0,
                "apparent_temp_c": 22.0,
                "precip_prob": 0,
                "precip_mm": 0.0,
                "wind_kmh": 10.0,
                "gust_kmh": 15.0,
                "humidity": 45.0,
                "cloud_cover": 10.0,
            }

        async def _call_both(hourly_rows, eval_now):
            coord.runtime.last_forecast_fetch = eval_now - timedelta(minutes=5)
            coord.data = {KEY_FORECAST: {"provider": "open_meteo", "hourly": hourly_rows}}
            with patch("custom_components.ws_core.coordinator.dt_util.now", return_value=eval_now):
                win_resp = await hass.services.async_call(
                    DOMAIN,
                    SERVICE_GET_WEATHER_WINDOWS,
                    {"profile_id": PROFILE_OUTDOOR_DRYING},
                    blocking=True,
                    return_response=True,
                )
                sum_resp = await hass.services.async_call(
                    DOMAIN,
                    SERVICE_GET_STATION_SUMMARY,
                    {},
                    blocking=True,
                    return_response=True,
                )
            return win_resp["station"], sum_resp["station"]

        now_hour = datetime(2026, 6, 21, 12, 0, tzinfo=UTC)

        # 1. Mixed impossible dates/hours, expired, duplicate, valid, exact 24h cutoff, and >24h rows
        mixed_rows = [
            _row("2026-02-30T12:00:00Z"),
            _row("2026-06-21T25:00:00Z"),
            _row("2026-02-30"),
            _row(now_hour - timedelta(hours=2)),
            _row(now_hour - timedelta(hours=1)),
            _row(now_hour),
            _row(now_hour),  # duplicate slot
            _row(now_hour + timedelta(hours=1)),
            _row(now_hour + timedelta(hours=2)),
            _row(now_hour + timedelta(hours=3)),
            _row(now_hour + timedelta(hours=24)),  # exact 24h cutoff -> excluded
            _row(now_hour + timedelta(hours=25)),  # beyond 24h cutoff -> excluded
        ]
        win_mixed, sum_mixed = await _call_both(mixed_rows, now_hour)
        assert win_mixed["horizon_hours"] == 4
        assert sum_mixed["forecast_validity"]["hourly_horizon_h"] == 4
        assert sum_mixed["forecast_validity"]["hourly_horizon_h"] == win_mixed["horizon_hours"]

        # 2. 25 hourly rows starting on the hour, evaluated mid-hour -> both cap at 24 hours
        now_mid = datetime(2026, 6, 21, 12, 30, tzinfo=UTC)
        rows_25 = [_row(now_hour + timedelta(hours=h)) for h in range(25)]
        win_25, sum_25 = await _call_both(rows_25, now_mid)
        assert win_25["horizon_hours"] <= 24
        assert sum_25["forecast_validity"]["hourly_horizon_h"] <= 24
        assert win_25["horizon_hours"] == 24
        assert sum_25["forecast_validity"]["hourly_horizon_h"] == 24

        # 3. Slot at exact 24h cutoff + rows entirely beyond 24h cutoff -> both report 0
        beyond_rows = [
            _row(now_hour + timedelta(hours=24)),
            _row(now_hour + timedelta(hours=25)),
            _row(now_hour + timedelta(hours=26)),
        ]
        win_beyond, sum_beyond = await _call_both(beyond_rows, now_hour)
        assert win_beyond["horizon_hours"] == 0
        assert sum_beyond["forecast_validity"]["hourly_horizon_h"] == 0

        # 4. Single usable forecast hour -> both report 1h coverage while min_duration_h=2 keeps status unknown
        one_usable_rows = [
            _row("2026-02-30T12:00:00Z"),
            _row(now_hour - timedelta(hours=1)),
            _row(now_hour),
            _row(now_hour),
            _row(now_hour + timedelta(hours=24)),
        ]
        win_one, sum_one = await _call_both(one_usable_rows, now_hour)
        assert win_one["status"] == "unknown"
        assert win_one["reason_codes"] == ["insufficient_horizon"]
        assert win_one["horizon_hours"] == 1
        assert sum_one["forecast_validity"]["hourly_horizon_h"] == 1
