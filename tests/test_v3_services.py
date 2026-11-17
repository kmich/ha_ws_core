"""Tests for v3.0.0 Home Assistant services and actions."""

from __future__ import annotations

import json

from custom_components.ws_core.const import (
    KEY_FORECAST,
    KEY_NORM_TEMP_C,
    PROFILE_OUTDOOR_DRYING,
)
from tests.test_coordinator import _make_coordinator


class TestV3Services:
    """Test get_weather_windows, get_station_summary, and export_learning_state."""

    def test_get_station_summary_returns_json_serializable_contract(self):
        coord = _make_coordinator()
        coord.data = {
            KEY_NORM_TEMP_C: 22.5,
            "pressure_trend_hpah": 0.5,
            "rain_rate_filt": 0.0,
            "rain_today_mm": 1.2,
        }
        coord.forecast_provider_id = "open_meteo"

        summary = coord.get_station_summary()
        assert summary["entry_id"] == "station"
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
        coord.data = {
            KEY_FORECAST: {
                "hourly": [
                    {
                        "datetime": "2026-06-21T12:00:00+00:00",
                        "temp_c": 22.0,
                        "apparent_temp_c": 22.0,
                        "precip_prob": 0,
                        "precip_mm": 0.0,
                        "wind_kmh": 10.0,
                        "gust_kmh": 15.0,
                        "humidity": 45.0,
                        "cloud_cover": 10.0,
                    },
                    {
                        "datetime": "2026-06-21T13:00:00+00:00",
                        "temp_c": 23.0,
                        "apparent_temp_c": 23.0,
                        "precip_prob": 0,
                        "precip_mm": 0.0,
                        "wind_kmh": 12.0,
                        "gust_kmh": 16.0,
                        "humidity": 42.0,
                        "cloud_cover": 10.0,
                    },
                ]
            }
        }

        eval_result = coord.get_weather_windows_evaluation(profile_id=PROFILE_OUTDOOR_DRYING)
        assert eval_result["profile_id"] == PROFILE_OUTDOOR_DRYING
        assert "status" in eval_result
        assert "evaluated_limits" in eval_result
        assert "slots" in eval_result

        # Must be strictly JSON-serializable
        serialized = json.dumps(eval_result)
        assert len(serialized) > 50

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
        res = coord.get_weather_windows_evaluation(profile_id="astronomy", custom_limits=custom_limits)
        assert res["profile_id"] == "astronomy"
        assert res["evaluated_limits"]["min_duration_h"] == 3
        assert res["evaluated_limits"]["max_cloud_cover_pct"] == 10.0
        assert res["evaluated_limits"]["require_daylight"] is False
