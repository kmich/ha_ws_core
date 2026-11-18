"""Unit tests for Weather Windows Decision Engine (v3.0.0)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest
from homeassistant.util import dt as dt_util

from custom_components.ws_core.const import (
    CONF_ENABLE_WEATHER_WINDOWS,
    CONF_FORECAST_LAT,
    CONF_FORECAST_LON,
    CONF_WEATHER_WINDOW_PROFILES,
    KEY_FORECAST,
    KEY_RAIN_RATE_FILT,
    PROFILE_CUSTOM,
    PROFILE_GARDEN_WORK,
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
    STATUS_UNKNOWN,
    STATUS_UNSUITABLE,
    STATUS_WINDOW_UPCOMING,
    WeatherWindowProfile,
    WeatherWindowsEngine,
    resolve_profiles,
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

        assert result.status == STATUS_UNKNOWN
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

    def test_future_only_forecast_returns_window_upcoming_not_suitable_now(self, engine: WeatherWindowsEngine):
        now = datetime(2026, 6, 21, 10, 0, tzinfo=UTC)
        forecast_start = now + timedelta(hours=2)
        hourly = _make_hourly_forecast(forecast_start, hours=4)
        profile = DEFAULT_PROFILES[PROFILE_OUTDOOR_DRYING]

        result = engine.evaluate_profile(profile, hourly, current_data={}, now=now)

        assert result.status == STATUS_WINDOW_UPCOMING
        assert result.next_start == forecast_start.isoformat()
        assert result.duration_h == 4

    def test_active_window_remaining_duration_below_minimum_is_not_suitable_now(self, engine: WeatherWindowsEngine):
        # 2-hour window [10:00, 12:00), followed by rain at 12:00 and sunny later [13:00, 15:00)
        slot_start = datetime(2026, 6, 21, 10, 0, tzinfo=UTC)
        hourly = _make_hourly_forecast(slot_start, hours=5)
        hourly[2]["precip_prob"] = 90  # 12:00 unsuitable

        profile = DEFAULT_PROFILES[PROFILE_OUTDOOR_DRYING]
        # Evaluated at 10:45 -> only 1.25h remaining before 12:00 rain (< min_duration_h=2h)
        now = datetime(2026, 6, 21, 10, 45, tzinfo=UTC)
        result = engine.evaluate_profile(profile, hourly, current_data={}, now=now)

        assert result.status == STATUS_WINDOW_UPCOMING
        assert result.next_start == (slot_start + timedelta(hours=3)).isoformat()
        assert result.duration_h == 2

    def test_missing_and_duplicate_forecast_hours_split_windows(self, engine: WeatherWindowsEngine):
        # Unsorted, duplicate 12:00, missing 13:00 and 14:00, contiguous [15:00, 17:00)
        t12 = datetime(2026, 6, 21, 12, 0, tzinfo=UTC)
        t15 = datetime(2026, 6, 21, 15, 0, tzinfo=UTC)
        hourly = [
            _make_hourly_forecast(t15, hours=2)[1],  # 16:00 out of order
            _make_hourly_forecast(t12, hours=1)[0],  # 12:00
            _make_hourly_forecast(t12, hours=1)[0],  # duplicate 12:00
            _make_hourly_forecast(t15, hours=2)[0],  # 15:00
        ]
        # Make 12:00 unsuitable? Wait: even if 12:00 AND 15:00 are dry, a gap MUST NOT bridge!
        # Also test two 1h dry slots separated by missing hours (12:00 and 15:00 only):
        profile = DEFAULT_PROFILES[PROFILE_OUTDOOR_DRYING]
        gap_only = [_make_hourly_forecast(t12, hours=1)[0], _make_hourly_forecast(t15, hours=1)[0]]
        gap_res = engine.evaluate_profile(profile, gap_only, current_data={}, now=t12)
        assert gap_res.status == STATUS_UNSUITABLE
        assert gap_res.windows == []

        # Out-of-order + duplicate + gap between 12:00 and [15:00, 17:00)
        res = engine.evaluate_profile(profile, hourly, current_data={}, now=t12)
        assert len(res.slots) == 3  # deduplicated to [12:00, 15:00, 16:00]
        assert res.status == STATUS_WINDOW_UPCOMING
        assert res.next_start == t15.isoformat()
        assert res.next_end == (t15 + timedelta(hours=2)).isoformat()
        assert res.duration_h == 2

    @pytest.mark.parametrize(
        ("field", "expected_limit"),
        [
            ("gust_kmh", "max_wind_gust_kmh"),
            ("humidity", "max_humidity_pct"),
            ("wind_kmh", "min_wind_kmh"),
            ("temp_c", "min_temp_c"),
            ("precip_prob", "max_rain_prob_pct"),
            ("precip_mm", "max_rain_mm"),
            ("cloud_cover", "max_cloud_cover_pct"),
        ],
    )
    def test_every_enabled_limit_reports_missing_input_as_unassessed(
        self, engine: WeatherWindowsEngine, field: str, expected_limit: str
    ):
        start_time = datetime(2026, 6, 21, 11, 0, tzinfo=UTC)
        hourly = _make_hourly_forecast(start_time, hours=4)
        for slot in hourly:
            slot[field] = None

        profile = DEFAULT_PROFILES[PROFILE_OUTDOOR_DRYING]
        result = engine.evaluate_profile(profile, hourly, current_data={}, now=start_time)

        assert result.status == STATUS_UNKNOWN
        assert REASON_MISSING_DATA in result.reason_codes
        assert all(slot["suitable"] is False for slot in result.slots)
        assert all(expected_limit in slot["unassessed_limits"] for slot in result.slots)
        assert result.data_quality["unassessed_slots"] == 4

    def test_repeated_dst_fall_back_hour_preserved(self):
        berlin = ZoneInfo("Europe/Berlin")
        old_tz = dt_util.get_default_time_zone()
        dt_util.set_default_time_zone(berlin)
        try:
            # 2026-10-25 in Berlin falls back at 03:00 CEST (+02:00) -> 02:00 CET (+01:00).
            # 00:00Z = 02:00+02:00, 01:00Z = 02:00+01:00.
            t0_utc = datetime(2026, 10, 25, 0, 0, tzinfo=UTC)
            t1_utc = datetime(2026, 10, 25, 1, 0, tzinfo=UTC)
            hourly = [
                {
                    "datetime": "2026-10-25T02:00",
                    "utc_datetime": t0_utc.isoformat(),
                    "temp_c": 18.0,
                    "precip_prob": 0,
                    "precip_mm": 0.0,
                    "wind_kmh": 12.0,
                    "gust_kmh": 18.0,
                    "humidity": 60.0,
                    "cloud_cover": 10.0,
                },
                {
                    "datetime": "2026-10-25T02:00",
                    "utc_datetime": t1_utc.isoformat(),
                    "temp_c": 18.0,
                    "precip_prob": 0,
                    "precip_mm": 0.0,
                    "wind_kmh": 12.0,
                    "gust_kmh": 18.0,
                    "humidity": 60.0,
                    "cloud_cover": 10.0,
                },
            ]
            engine = WeatherWindowsEngine(lat=52.52, lon=13.40)
            custom_night_profile = WeatherWindowProfile(
                profile_id=PROFILE_CUSTOM,
                name="Night",
                description="DST test",
                enabled=True,
                min_duration_h=2,
                require_daylight=False,
            )
            res = engine.evaluate_profile(custom_night_profile, hourly, now=t0_utc.astimezone(berlin))

            assert res.status == STATUS_SUITABLE_NOW
            assert len(res.slots) == 2
            assert res.slots[0]["datetime_iso"] == "2026-10-25T02:00:00+02:00"
            assert res.slots[1]["datetime_iso"] == "2026-10-25T02:00:00+01:00"
            assert res.duration_h == 2
            assert res.next_start == "2026-10-25T02:00:00+02:00"
            assert res.next_end == "2026-10-25T03:00:00+01:00"
        finally:
            dt_util.set_default_time_zone(old_tz)

    async def test_profile_selection_custom_only_and_none_selected(self):
        from pytest_homeassistant_custom_component.common import MockConfigEntry

        from custom_components.ws_core import sensor as sensor_platform
        from custom_components.ws_core.const import CONF_PREFIX, DOMAIN
        from custom_components.ws_core.coordinator import WSStationCoordinator

        # 1. Custom profile only
        custom_opts = {
            CONF_PREFIX: "ws",
            CONF_ENABLE_WEATHER_WINDOWS: True,
            CONF_WEATHER_WINDOW_PROFILES: [PROFILE_CUSTOM],
            CONF_FORECAST_LAT: 38.0,
            CONF_FORECAST_LON: 23.7,
        }
        resolved_custom = resolve_profiles(custom_opts)
        assert resolved_custom[PROFILE_CUSTOM].enabled is True
        assert resolved_custom[PROFILE_OUTDOOR_DRYING].enabled is False
        assert resolved_custom[PROFILE_GARDEN_WORK].enabled is False

        hass = MagicMock()
        entry_custom = MockConfigEntry(domain=DOMAIN, entry_id="c1", data=custom_opts, options={})
        coord_custom = WSStationCoordinator(hass, entry_custom)
        entry_custom.runtime_data = coord_custom
        now_hr = dt_util.now().replace(minute=0, second=0, microsecond=0)
        coord_custom.data = {KEY_FORECAST: {"hourly": _make_hourly_forecast(now_hr, 4)}}

        created_custom = []
        await sensor_platform.async_setup_entry(hass, entry_custom, lambda ents: created_custom.extend(ents))
        win_keys_custom = [
            e._desc.key for e in created_custom if getattr(e, "_desc", None) and e._desc.key.startswith("window_")
        ]
        assert win_keys_custom == [
            "window_custom_status",
            "window_custom_next_start",
            "window_custom_next_end",
        ]
        eval_custom = coord_custom.get_weather_windows_evaluation()
        assert list(eval_custom.keys()) == [PROFILE_CUSTOM]

        # 2. No profiles selected
        none_opts = {
            **custom_opts,
            CONF_WEATHER_WINDOW_PROFILES: [],
        }
        entry_none = MockConfigEntry(domain=DOMAIN, entry_id="c2", data=none_opts, options={})
        coord_none = WSStationCoordinator(hass, entry_none)
        entry_none.runtime_data = coord_none
        coord_none.data = coord_custom.data

        created_none = []
        await sensor_platform.async_setup_entry(hass, entry_none, lambda ents: created_none.extend(ents))
        win_keys_none = [
            e._desc.key for e in created_none if getattr(e, "_desc", None) and e._desc.key.startswith("window_")
        ]
        assert win_keys_none == []
        assert coord_none.get_weather_windows_evaluation() == {}

    def test_sensors_and_actions_use_same_local_timezone_for_naive_forecasts(self):
        berlin = ZoneInfo("Europe/Berlin")
        old_tz = dt_util.get_default_time_zone()
        dt_util.set_default_time_zone(berlin)
        try:
            # Naive local forecast timestamps (e.g. Open-Meteo timezone=auto): 12:00..14:00 Berlin (+02:00)
            hourly = [
                {
                    "datetime": f"2026-06-21T{hr:02d}:00",
                    "temp_c": 22.0,
                    "precip_prob": 0,
                    "precip_mm": 0.0,
                    "wind_kmh": 10.0,
                    "gust_kmh": 15.0,
                    "humidity": 50.0,
                    "cloud_cover": 10.0,
                }
                for hr in (12, 13, 14)
            ]
            engine = WeatherWindowsEngine(lat=52.52, lon=13.40)
            profile = DEFAULT_PROFILES[PROFILE_OUTDOOR_DRYING]

            # _compute path passes UTC time; action path passes local dt_util.now()
            utc_now = datetime(2026, 6, 21, 10, 0, tzinfo=UTC)
            local_now = datetime(2026, 6, 21, 12, 0, tzinfo=berlin)

            sensor_res = engine.evaluate_profile(profile, hourly, now=utc_now)
            action_res = engine.evaluate_profile(profile, hourly, now=local_now)

            for res in (sensor_res, action_res):
                assert res.status == STATUS_SUITABLE_NOW
                assert res.next_start == "2026-06-21T12:00:00+02:00"
                assert res.next_end == "2026-06-21T15:00:00+02:00"
                assert res.duration_h == 3
        finally:
            dt_util.set_default_time_zone(old_tz)

    def test_active_window_reports_remaining_duration(self, engine: WeatherWindowsEngine):
        slot_start = datetime(2026, 6, 21, 10, 0, tzinfo=UTC)
        hourly = _make_hourly_forecast(slot_start, hours=3)
        profile = DEFAULT_PROFILES[PROFILE_OUTDOOR_DRYING]

        now = datetime(2026, 6, 21, 10, 30, tzinfo=UTC)
        result = engine.evaluate_profile(profile, hourly, current_data={}, now=now)

        assert result.status == STATUS_SUITABLE_NOW
        assert result.duration_h == 2.5
        assert result.windows[0]["duration_h"] == 2.5
        assert "2.5 hours" in result.reasons_text[0]

    def test_enforces_24_hour_horizon_cutoff(self, engine: WeatherWindowsEngine):
        start_time = datetime(2026, 6, 21, 10, 0, tzinfo=UTC)
        hourly = _make_hourly_forecast(start_time, hours=36)
        # First 24h all rainy, hours 26..30 sunny (>= 24h ahead)
        for i in range(24):
            hourly[i]["precip_prob"] = 90
        profile = DEFAULT_PROFILES[PROFILE_OUTDOOR_DRYING]

        result = engine.evaluate_profile(profile, hourly, current_data={}, now=start_time)

        assert result.horizon_hours == 24
        assert result.status == STATUS_UNSUITABLE
        assert result.windows == []

    def test_window_end_clipped_to_24_hour_cutoff(self, engine: WeatherWindowsEngine):
        slot_start = datetime(2026, 6, 21, 10, 0, tzinfo=UTC)
        now = datetime(2026, 6, 21, 10, 30, tzinfo=UTC)  # 24h cutoff is 2026-06-22T10:30:00+00:00
        profile = DEFAULT_PROFILES[PROFILE_OUTDOOR_DRYING]

        # Case A: Only 09:00 (+1d) and 10:00 (+1d) suitable -> clipped at 10:30 (+1d) = 1.5h < 2h -> rejected
        hourly_short = _make_hourly_forecast(slot_start, hours=25)
        for i in range(23):
            hourly_short[i]["precip_prob"] = 90
        res_short = engine.evaluate_profile(profile, hourly_short, current_data={}, now=now)
        assert res_short.status == STATUS_UNSUITABLE
        assert res_short.windows == []

        # Case B: 08:00 (+1d), 09:00 (+1d), 10:00 (+1d) suitable -> clipped end 10:30 (+1d), duration 2.5h, truncated
        hourly_ok = _make_hourly_forecast(slot_start, hours=25)
        for i in range(22):
            hourly_ok[i]["precip_prob"] = 90
        res_ok = engine.evaluate_profile(profile, hourly_ok, current_data={}, now=now)
        assert res_ok.horizon_hours == 24
        assert res_ok.status == STATUS_WINDOW_UPCOMING
        assert res_ok.next_end == "2026-06-22T10:30:00+00:00"
        assert res_ok.duration_h == 2.5
        assert res_ok.is_truncated is True
