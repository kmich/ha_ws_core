"""Unit tests for Weather Windows Decision Engine (v3.0.0)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from custom_components.ws_core.const import (
    KEY_RAIN_RATE_FILT,
    PROFILE_CUSTOM,
    PROFILE_OUTDOOR_DRYING,
)
from custom_components.ws_core.weather_windows import (
    DEFAULT_PROFILES,
    REASON_CALM_AIR,
    REASON_CURRENTLY_RAINING,
    REASON_HEAVY_CLOUDS,
    REASON_HIGH_HUMIDITY,
    REASON_MISSING_DATA,
    REASON_NIGHTTIME,
    REASON_RAIN_AMOUNT,
    REASON_RAIN_RISK,
    REASON_SUITABLE,
    REASON_TOO_COLD,
    STATUS_SUITABLE_NOW,
    STATUS_UNSUITABLE,
    STATUS_WINDOW_UPCOMING,
    WeatherWindowProfile,
    WeatherWindowsEngine,
)


def _make_hourly_forecast(
    start_dt: datetime,
    hours: int = 24,
    temp_c: float = 20.0,
    rain_prob: int = 0,
    rain_mm: float = 0.0,
    humidity: float = 50.0,
    wind_kmh: float = 12.0,
    gust_kmh: float = 20.0,
    cloud_cover: float = 20.0,
) -> list[dict]:
    out = []
    for i in range(hours):
        t = start_dt + timedelta(hours=i)
        out.append(
            {
                "datetime": t.isoformat(),
                "temp_c": temp_c,
                "apparent_temp_c": temp_c,
                "dewpoint_c": 10.0,
                "precip_prob": rain_prob,
                "precip_mm": rain_mm,
                "weathercode": 0,
                "wind_kmh": wind_kmh,
                "gust_kmh": gust_kmh,
                "humidity": humidity,
                "cloud_cover": cloud_cover,
            }
        )
    return out


class TestWeatherWindowsEngine:
    """Test the Weather Windows Decision Engine evaluation logic."""

    @pytest.fixture
    def engine(self) -> WeatherWindowsEngine:
        # Athens, Greece: lat 38.0, lon 23.7
        return WeatherWindowsEngine(lat=38.0, lon=23.7, elevation_m=100.0)

    def test_outdoor_drying_suitable_now(self, engine: WeatherWindowsEngine):
        # Daytime start: summer noon
        start_time = datetime(2026, 6, 21, 11, 0, tzinfo=UTC)
        hourly = _make_hourly_forecast(start_time, hours=6)
        profile = DEFAULT_PROFILES[PROFILE_OUTDOOR_DRYING]

        result = engine.evaluate_profile(profile, hourly, current_data={}, now=start_time)

        assert result.status == STATUS_SUITABLE_NOW
        assert result.next_start == start_time.isoformat()
        assert result.duration_h >= 2
        assert REASON_SUITABLE in result.reason_codes
        assert result.is_truncated is True  # All 6 hours were suitable up to end of data

    def test_rain_probability_blocks_window(self, engine: WeatherWindowsEngine):
        start_time = datetime(2026, 6, 21, 11, 0, tzinfo=UTC)
        hourly = _make_hourly_forecast(start_time, hours=6, rain_prob=45)
        profile = DEFAULT_PROFILES[PROFILE_OUTDOOR_DRYING]

        result = engine.evaluate_profile(profile, hourly, current_data={}, now=start_time)

        assert result.status == STATUS_UNSUITABLE
        assert REASON_RAIN_RISK in result.reason_codes
        assert any(s["suitable"] is False for s in result.slots)

    def test_rain_amount_blocks_window(self, engine: WeatherWindowsEngine):
        start_time = datetime(2026, 6, 21, 11, 0, tzinfo=UTC)
        hourly = _make_hourly_forecast(start_time, hours=6, rain_prob=10, rain_mm=0.8)
        profile = DEFAULT_PROFILES[PROFILE_OUTDOOR_DRYING]

        result = engine.evaluate_profile(profile, hourly, current_data={}, now=start_time)

        assert result.status == STATUS_UNSUITABLE
        assert REASON_RAIN_AMOUNT in result.reason_codes

    def test_too_cold_temperature_blocks_drying(self, engine: WeatherWindowsEngine):
        start_time = datetime(2026, 6, 21, 11, 0, tzinfo=UTC)
        hourly = _make_hourly_forecast(start_time, hours=6, temp_c=5.0)  # below 10°C limit
        profile = DEFAULT_PROFILES[PROFILE_OUTDOOR_DRYING]

        result = engine.evaluate_profile(profile, hourly, current_data={}, now=start_time)

        assert result.status == STATUS_UNSUITABLE
        assert REASON_TOO_COLD in result.reason_codes

    def test_high_humidity_blocks_drying(self, engine: WeatherWindowsEngine):
        start_time = datetime(2026, 6, 21, 11, 0, tzinfo=UTC)
        hourly = _make_hourly_forecast(start_time, hours=6, humidity=85.0)  # above 75%
        profile = DEFAULT_PROFILES[PROFILE_OUTDOOR_DRYING]

        result = engine.evaluate_profile(profile, hourly, current_data={}, now=start_time)

        assert result.status == STATUS_UNSUITABLE
        assert REASON_HIGH_HUMIDITY in result.reason_codes

    def test_calm_wind_blocks_drying(self, engine: WeatherWindowsEngine):
        start_time = datetime(2026, 6, 21, 11, 0, tzinfo=UTC)
        hourly = _make_hourly_forecast(start_time, hours=6, wind_kmh=1.0)  # below 3 km/h
        profile = DEFAULT_PROFILES[PROFILE_OUTDOOR_DRYING]

        result = engine.evaluate_profile(profile, hourly, current_data={}, now=start_time)

        assert result.status == STATUS_UNSUITABLE
        assert REASON_CALM_AIR in result.reason_codes

    def test_heavy_clouds_blocks_drying(self, engine: WeatherWindowsEngine):
        start_time = datetime(2026, 6, 21, 11, 0, tzinfo=UTC)
        hourly = _make_hourly_forecast(start_time, hours=6, cloud_cover=95.0)  # above 80%
        profile = DEFAULT_PROFILES[PROFILE_OUTDOOR_DRYING]

        result = engine.evaluate_profile(profile, hourly, current_data={}, now=start_time)

        assert result.status == STATUS_UNSUITABLE
        assert REASON_HEAVY_CLOUDS in result.reason_codes

    def test_nighttime_blocks_daylight_profile(self, engine: WeatherWindowsEngine):
        # Midnight UTC in Athens (sun is well below horizon)
        night_time = datetime(2026, 6, 21, 23, 0, tzinfo=UTC)
        hourly = _make_hourly_forecast(night_time, hours=4)
        profile = DEFAULT_PROFILES[PROFILE_OUTDOOR_DRYING]

        result = engine.evaluate_profile(profile, hourly, current_data={}, now=night_time)

        assert result.status == STATUS_UNSUITABLE
        assert REASON_NIGHTTIME in result.reason_codes

    def test_upcoming_window_detected(self, engine: WeatherWindowsEngine):
        # Slots 0 and 1 are raining, slots 2, 3, 4 are sunny and favorable
        start_time = datetime(2026, 6, 21, 10, 0, tzinfo=UTC)
        hourly = _make_hourly_forecast(start_time, hours=5)
        hourly[0]["precip_prob"] = 80
        hourly[1]["precip_prob"] = 70

        profile = DEFAULT_PROFILES[PROFILE_OUTDOOR_DRYING]
        result = engine.evaluate_profile(profile, hourly, current_data={}, now=start_time)

        assert result.status == STATUS_WINDOW_UPCOMING
        expected_start = (start_time + timedelta(hours=2)).isoformat()
        assert result.next_start == expected_start
        assert result.duration_h == 3

    def test_live_station_rain_blocks_suitable_now(self, engine: WeatherWindowsEngine):
        start_time = datetime(2026, 6, 21, 11, 0, tzinfo=UTC)
        hourly = _make_hourly_forecast(start_time, hours=6)
        profile = DEFAULT_PROFILES[PROFILE_OUTDOOR_DRYING]

        # Live station detects 2.5 mm/h rain
        current_data = {KEY_RAIN_RATE_FILT: 2.5}
        result = engine.evaluate_profile(profile, hourly, current_data=current_data, now=start_time)

        # Even though NWP forecast says 0 mm, live rain prevents suitable_now
        assert result.status != STATUS_SUITABLE_NOW
        assert REASON_CURRENTLY_RAINING in result.reason_codes

    def test_missing_forecast_variable_is_never_treated_as_safe(self, engine: WeatherWindowsEngine):
        start_time = datetime(2026, 6, 21, 11, 0, tzinfo=UTC)
        hourly = _make_hourly_forecast(start_time, hours=4)
        # Missing temp_c
        for h in hourly:
            h["temp_c"] = None

        profile = DEFAULT_PROFILES[PROFILE_OUTDOOR_DRYING]
        result = engine.evaluate_profile(profile, hourly, current_data={}, now=start_time)

        assert result.status == STATUS_UNSUITABLE
        assert REASON_MISSING_DATA in result.reason_codes

    def test_custom_profile_limits(self, engine: WeatherWindowsEngine):
        start_time = datetime(2026, 6, 21, 11, 0, tzinfo=UTC)
        hourly = _make_hourly_forecast(start_time, hours=4, wind_kmh=40.0)
        custom_profile = WeatherWindowProfile(
            profile_id=PROFILE_CUSTOM,
            name="Wind Surfing",
            description="High wind activity",
            enabled=True,
            min_duration_h=2,
            min_wind_kmh=30.0,
            max_wind_kmh=60.0,
            max_rain_prob_pct=None,
            max_rain_mm=None,
            min_temp_c=15.0,
            max_temp_c=None,
            max_humidity_pct=None,
            max_wind_gust_kmh=None,
            max_cloud_cover_pct=None,
            require_daylight=False,
        )

        result = engine.evaluate_profile(custom_profile, hourly, current_data={}, now=start_time)
        assert result.status == STATUS_SUITABLE_NOW
        assert result.duration_h == 4
