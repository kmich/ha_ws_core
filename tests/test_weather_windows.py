"""Unit tests for Weather Windows Decision Engine (v3.0.0)."""

from __future__ import annotations

from dataclasses import replace
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
    KEY_NORM_WIND_GUST_MS,
    KEY_RAIN_RATE_FILT,
    KEY_WEATHER_WINDOWS,
    PROFILE_CUSTOM,
    PROFILE_GARDEN_WORK,
    PROFILE_OUTDOOR_DRYING,
    SRC_GUST,
    SRC_RAIN_TOTAL,
)
from custom_components.ws_core.weather_windows import (
    DEFAULT_PROFILES,
    REASON_CALM_AIR,
    REASON_CURRENT_GUST_HIGH,
    REASON_CURRENTLY_RAINING,
    REASON_FORECAST_TOO_COARSE,
    REASON_FORECAST_UNAVAILABLE,
    REASON_HEAVY_CLOUDS,
    REASON_HIGH_HUMIDITY,
    REASON_INSUFFICIENT_HORIZON,
    REASON_MISSING_DATA,
    REASON_NIGHTTIME,
    REASON_NOT_ASSESSED_BY_PROVIDER,
    REASON_RAIN_AMOUNT,
    REASON_RAIN_RISK,
    REASON_SUITABLE,
    REASON_TOO_COLD,
    REASON_WINDOW_INTERRUPTED,
    STATUS_SUITABLE_NOW,
    STATUS_UNKNOWN,
    STATUS_UNSUITABLE,
    STATUS_WINDOW_UPCOMING,
    WeatherWindowProfile,
    WeatherWindowsEngine,
    apply_profile_overrides,
    parse_forecast_slot_utc,
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
        # Only two rows, 3 hours apart: not an hourly series, so it cannot be assessed
        assert gap_res.status == STATUS_UNKNOWN
        assert REASON_FORECAST_TOO_COARSE in gap_res.reason_codes
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
        # Partial per-slot gaps (missing only on hours 0..1 while hours 2..3 exist)
        # must remain unassessed gaps -> STATUS_UNKNOWN rather than treated as safe.
        start_time = datetime(2026, 6, 21, 11, 0, tzinfo=UTC)
        hourly = _make_hourly_forecast(start_time, hours=4)
        hourly[0][field] = None
        hourly[1][field] = None

        profile = DEFAULT_PROFILES[PROFILE_OUTDOOR_DRYING]
        result = engine.evaluate_profile(profile, hourly, current_data={}, now=start_time)

        assert result.status == STATUS_UNKNOWN
        assert REASON_MISSING_DATA in result.reason_codes
        assert result.slots[0]["suitable"] is False
        assert result.slots[1]["suitable"] is False
        assert expected_limit in result.slots[0]["unassessed_limits"]
        assert expected_limit in result.slots[1]["unassessed_limits"]
        assert result.data_quality["unassessed_slots"] == 2

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
        try:
            from pytest_homeassistant.common import MockConfigEntry
        except ImportError:
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
        for ent in created_custom:
            if getattr(ent, "_desc", None) and ent._desc.key.startswith("window_custom_"):
                assert ent.translation_placeholders == {"profile_name": "Custom Activity"}
        status_ent = next(
            e for e in created_custom if getattr(e, "_desc", None) and e._desc.key == "window_custom_status"
        )
        attrs = status_ent._desc.attrs_fn({KEY_WEATHER_WINDOWS: {PROFILE_CUSTOM: {"duration_h": 2.37}}})
        # Remaining duration changes every minute, so it is not a state attribute (recorder churn)
        assert "duration_h" not in attrs
        # Fixed states, offered as choices in automations
        from homeassistant.components.sensor import SensorDeviceClass

        assert status_ent._desc.device_class == SensorDeviceClass.ENUM
        assert status_ent._desc.options == ["suitable_now", "window_upcoming", "unsuitable", "unknown"]
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
        # The sentence names the end time, not a remaining duration that changes every minute
        assert "until 13:00" in result.reasons_text[0]
        later = engine.evaluate_profile(profile, hourly, current_data={}, now=now + timedelta(minutes=9))
        assert later.reasons_text == result.reasons_text

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
        now = datetime(2026, 6, 21, 10, 30, tzinfo=UTC)  # 24h cutoff floors to 2026-06-22T10:00:00+00:00
        profile = DEFAULT_PROFILES[PROFILE_OUTDOOR_DRYING]

        # Case A: Only 09:00 (+1d) and 10:00 (+1d) suitable; 10:00 (+1d) is past the floored cutoff -> 1h < 2h
        hourly_short = _make_hourly_forecast(slot_start, hours=25)
        for i in range(23):
            hourly_short[i]["precip_prob"] = 90
        res_short = engine.evaluate_profile(profile, hourly_short, current_data={}, now=now)
        assert res_short.status == STATUS_UNSUITABLE
        assert res_short.windows == []

        # Case B: 08:00 (+1d) and 09:00 (+1d) suitable up to the floored cutoff -> end 10:00 (+1d), 2h, truncated
        hourly_ok = _make_hourly_forecast(slot_start, hours=25)
        for i in range(22):
            hourly_ok[i]["precip_prob"] = 90
        res_ok = engine.evaluate_profile(profile, hourly_ok, current_data={}, now=now)
        assert res_ok.horizon_hours == 24
        assert res_ok.status == STATUS_WINDOW_UPCOMING
        assert res_ok.next_end == "2026-06-22T10:00:00+00:00"
        assert res_ok.duration_h == 2

        # The end stays put as the clock advances within the hour (no per-minute timestamp churn)
        res_later = engine.evaluate_profile(profile, hourly_ok, current_data={}, now=now + timedelta(minutes=17))
        assert res_later.next_end == res_ok.next_end
        assert res_ok.is_truncated is True

    def test_expired_forecast_returns_unknown_from_evaluation_action(self):
        from unittest.mock import patch

        from custom_components.ws_core.const import PROFILE_OUTDOOR_DRYING
        from tests.test_coordinator import _make_coordinator

        coord = _make_coordinator()
        coord.forecast_lat = 38.0
        coord.forecast_lon = 23.7
        now = datetime(2026, 6, 21, 12, 0, tzinfo=UTC)
        coord.data = {
            KEY_FORECAST: {
                "daily": [{"date": "2026-06-21", "tmax_c": 25.0}],
                "hourly": _make_hourly_forecast(now, hours=4),
            }
        }

        coord.runtime.last_forecast_fetch = now - timedelta(minutes=10)
        with patch("custom_components.ws_core.coordinator.dt_util.now", return_value=now):
            fresh = coord.get_weather_windows_evaluation(profile_id=PROFILE_OUTDOOR_DRYING)
        assert fresh["status"] == STATUS_SUITABLE_NOW

        coord.runtime.last_forecast_fetch = now - timedelta(hours=13)
        with patch("custom_components.ws_core.coordinator.dt_util.now", return_value=now):
            res = coord.get_weather_windows_evaluation(profile_id=PROFILE_OUTDOOR_DRYING)
        assert res["status"] == STATUS_UNKNOWN
        assert res["windows"] == []

    def test_live_rain_respects_disabled_limits_and_unsuitable_prioritizes_real_blockers(
        self, engine: WeatherWindowsEngine
    ):
        start_time = datetime(2026, 6, 21, 11, 0, tzinfo=UTC)
        hourly = _make_hourly_forecast(start_time, hours=4)

        # Profile with rain limits disabled -> live rain does not block
        no_rain_limit_profile = WeatherWindowProfile(
            profile_id=PROFILE_CUSTOM,
            name="Rain Tolerant",
            description="No rain limits",
            enabled=True,
            min_duration_h=2,
            max_rain_prob_pct=None,
            max_rain_mm=None,
            require_daylight=False,
        )
        res_ok = engine.evaluate_profile(
            no_rain_limit_profile,
            hourly,
            current_data={KEY_RAIN_RATE_FILT: 1.5},
            now=start_time,
        )
        assert res_ok.status == STATUS_SUITABLE_NOW
        assert REASON_CURRENTLY_RAINING not in res_ok.reason_codes

        # Unsuitable due to real threshold failures (too cold + nighttime) + missing gust_kmh (e.g. Met.no):
        # top_blockers must report real threshold failures, not REASON_MISSING_DATA.
        night_start = datetime(2026, 6, 21, 22, 0, tzinfo=UTC)
        cold_hourly = _make_hourly_forecast(night_start, hours=4, temp_c=2.0)
        for slot in cold_hourly:
            slot["gust_kmh"] = None
        drying = DEFAULT_PROFILES[PROFILE_OUTDOOR_DRYING]
        res_cold = engine.evaluate_profile(drying, cold_hourly, current_data={}, now=night_start)
        assert res_cold.status == STATUS_UNSUITABLE
        assert REASON_TOO_COLD in res_cold.reason_codes
        assert REASON_MISSING_DATA not in res_cold.reason_codes

    def test_daylight_checked_through_end_of_slot(self, engine: WeatherWindowsEngine):
        # Athens (38.0, 23.7) on 2026-06-21: sunset occurs ~17:51 UTC (17:00 is +8.05 deg, 18:00 is -2.38 deg).
        # Starting at 16:00 UTC with 2 suitable-weather hours [16:00..18:00) must reject 17:00..18:00 for sunset.
        start_time = datetime(2026, 6, 21, 16, 0, tzinfo=UTC)
        hourly = _make_hourly_forecast(start_time, hours=3)
        drying = DEFAULT_PROFILES[PROFILE_OUTDOOR_DRYING]

        result = engine.evaluate_profile(drying, hourly, current_data={}, now=start_time)
        assert result.status == STATUS_UNSUITABLE
        assert REASON_NIGHTTIME in result.reason_codes
        assert result.slots[0]["suitable"] is True
        assert REASON_NIGHTTIME in result.slots[1]["reasons"]

    def test_publishes_confirmed_future_window_when_current_slot_is_unknown(self, engine: WeatherWindowsEngine):
        from custom_components.ws_core.weather_windows import REASON_WINDOW_UPCOMING

        now = datetime(2026, 6, 21, 10, 0, tzinfo=UTC)
        hourly = _make_hourly_forecast(now, hours=4)
        # Current and +1h slots have missing wind gust -> unassessed, while [12:00..14:00) is confirmed suitable
        hourly[0]["gust_kmh"] = None
        hourly[1]["gust_kmh"] = None

        drying = DEFAULT_PROFILES[PROFILE_OUTDOOR_DRYING]
        result = engine.evaluate_profile(drying, hourly, current_data={}, now=now)

        assert result.status == STATUS_UNKNOWN
        assert REASON_MISSING_DATA in result.reason_codes
        assert REASON_WINDOW_UPCOMING in result.reason_codes
        assert result.next_start == (now + timedelta(hours=2)).isoformat()
        assert result.next_end == (now + timedelta(hours=4)).isoformat()
        assert result.duration_h == 2

    def test_resolve_profiles_applies_configured_custom_limits_and_drives_coordinator(self):
        from unittest.mock import patch

        try:
            from pytest_homeassistant.common import MockConfigEntry
        except ImportError:
            from pytest_homeassistant_custom_component.common import MockConfigEntry

        from custom_components.ws_core.const import (
            CONF_CUSTOM_MAX_CLOUD_COVER_PCT,
            CONF_CUSTOM_MAX_RAIN_MM,
            CONF_CUSTOM_MAX_RAIN_PROB_PCT,
            CONF_CUSTOM_MIN_DURATION_H,
            CONF_CUSTOM_MIN_TEMP_C,
            CONF_CUSTOM_REQUIRE_DAYLIGHT,
            CONF_CUSTOM_WINDOW_NAME,
            CONF_ENABLE_WEATHER_WINDOWS,
            CONF_PREFIX,
            DOMAIN,
        )
        from custom_components.ws_core.coordinator import WSStationCoordinator

        opts = {
            CONF_PREFIX: "ws",
            CONF_ENABLE_WEATHER_WINDOWS: True,
            CONF_WEATHER_WINDOW_PROFILES: [PROFILE_CUSTOM],
            CONF_FORECAST_LAT: 38.0,
            CONF_FORECAST_LON: 23.7,
            CONF_CUSTOM_WINDOW_NAME: "Midnight Stargazing",
            CONF_CUSTOM_MIN_DURATION_H: 3,
            CONF_CUSTOM_MIN_TEMP_C: 5.0,
            CONF_CUSTOM_MAX_RAIN_PROB_PCT: 15.0,
            CONF_CUSTOM_MAX_RAIN_MM: None,
            CONF_CUSTOM_MAX_CLOUD_COVER_PCT: 20.0,
            CONF_CUSTOM_REQUIRE_DAYLIGHT: False,
        }
        profiles = resolve_profiles(opts)
        custom = profiles[PROFILE_CUSTOM]
        assert custom.enabled is True
        assert custom.name == "Midnight Stargazing"
        assert custom.min_duration_h == 3
        assert custom.max_rain_mm is None
        assert custom.max_cloud_cover_pct == 20.0
        assert custom.require_daylight is False

        entry = MockConfigEntry(domain=DOMAIN, entry_id="custom1", data=opts, options={})
        coord = WSStationCoordinator(MagicMock(), entry)
        night = datetime(2026, 6, 21, 23, 0, tzinfo=UTC)
        coord.data = {
            KEY_FORECAST: {
                "hourly": [
                    {
                        "datetime": (night + timedelta(hours=h)).isoformat(),
                        "temp_c": 14.0,
                        "precip_prob": 5,
                        "precip_mm": None,  # allowed because custom_max_rain_mm was cleared to None
                        "humidity": 65.0,
                        "wind_kmh": 8.0,
                        "gust_kmh": 15.0,
                        "cloud_cover": 10.0,
                    }
                    for h in range(4)
                ]
            }
        }
        with patch("custom_components.ws_core.coordinator.dt_util.now", return_value=night):
            eval_all = coord.get_weather_windows_evaluation()
        assert list(eval_all.keys()) == [PROFILE_CUSTOM]
        assert eval_all[PROFILE_CUSTOM]["status"] == STATUS_SUITABLE_NOW
        assert eval_all[PROFILE_CUSTOM]["duration_h"] == 4
        assert eval_all[PROFILE_CUSTOM]["evaluated_limits"]["max_rain_mm"] is None
        assert eval_all[PROFILE_CUSTOM]["evaluated_limits"]["require_daylight"] is False

    async def test_weather_windows_uses_hass_config_coords_fallback_and_preserves_zero(self):
        from unittest.mock import AsyncMock, patch

        from tests.test_coordinator import _make_coordinator

        coord = _make_coordinator()
        coord.config_entry = None
        coord.forecast_enabled = True
        coord.weather_windows_enabled = True
        coord._weather_windows_engine = None
        coord.entry_options["forecast_provider"] = "open_meteo"
        coord.forecast_lat = None
        coord.forecast_lon = None
        coord.hass.config.latitude = 38.0
        coord.hass.config.longitude = 23.7
        coord.async_set_updated_data = MagicMock()

        now = datetime(2026, 6, 21, 11, 0, tzinfo=UTC)
        hourly = _make_hourly_forecast(now, hours=4)
        coord.data = {KEY_FORECAST: {"hourly": hourly}}

        assert coord._effective_forecast_coords() == (38.0, 23.7)

        mock_provider = MagicMock()
        mock_provider.PROVIDER_NAME = "Open-Meteo"
        mock_provider.async_fetch = AsyncMock(return_value={"hourly": hourly, "daily": []})

        with (
            patch("custom_components.ws_core.coordinator.async_get_clientsession", return_value=MagicMock()),
            patch("custom_components.ws_core.coordinator.get_provider", return_value=mock_provider),
            patch("custom_components.ws_core.coordinator.dt_util.now", return_value=now),
            patch.object(coord, "_compute", return_value=coord.data),
        ):
            coord._compute_weather_windows(coord.data, now)
            assert coord.data[KEY_WEATHER_WINDOWS][PROFILE_OUTDOOR_DRYING]["status"] == STATUS_SUITABLE_NOW
            assert coord._get_weather_windows_engine().lat == 38.0
            assert coord._get_weather_windows_engine().lon == 23.7

            await coord._async_fetch_forecast()
            assert mock_provider.async_fetch.await_args.args[1:3] == (38.0, 23.7)

            # Explicit 0.0 equator/prime-meridian coordinates must not fall back to hass.config
            coord.forecast_lat = 0.0
            coord.forecast_lon = 0.0
            mock_provider.async_fetch.reset_mock()
            assert coord._effective_forecast_coords() == (0.0, 0.0)
            await coord._async_fetch_forecast()
            assert mock_provider.async_fetch.await_args.args[1:3] == (0.0, 0.0)
            assert coord._get_weather_windows_engine().lat == 0.0
            assert coord._get_weather_windows_engine().lon == 0.0

    def test_compute_timing_includes_weather_windows(self):
        from unittest.mock import patch

        from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

        from custom_components.ws_core.const import CONF_FORECAST_ENABLED
        from custom_components.ws_core.coordinator import WSStationCoordinator
        from tests.test_coordinator import _make_coordinator

        base = _make_coordinator()
        with patch.object(DataUpdateCoordinator, "__init__", lambda self, *a, **kw: None):
            coord = WSStationCoordinator(
                base.hass,
                {
                    "entry_id": "timing_test",
                    "sources": base.sources,
                    CONF_FORECAST_ENABLED: False,
                    CONF_FORECAST_LAT: 38.0,
                    CONF_FORECAST_LON: 23.7,
                },
                {},
            )

        clock = [100.0]

        def _fake_monotonic() -> float:
            return clock[0]

        def _slow_eval(data, now):
            clock[0] += 0.025
            data["weather_windows"] = {PROFILE_OUTDOOR_DRYING: {"status": STATUS_UNKNOWN}}

        with (
            patch("custom_components.ws_core.coordinator.time.monotonic", side_effect=_fake_monotonic),
            patch.object(coord, "_compute_weather_windows", side_effect=_slow_eval) as mock_ww,
        ):
            data = coord._compute(sample=False)

        assert mock_ww.call_count == 1
        assert "weather_windows" in data
        assert coord.runtime.last_compute_ms >= 25.0

    def test_parse_slot_utc_handles_datetime_objects_and_numeric_timestamps(self):
        tz = UTC
        dt_aware = datetime(2026, 6, 21, 14, 0, tzinfo=UTC)
        dt_naive = datetime(2026, 6, 21, 14, 0)
        ts_num = 1782050400.0  # 2026-06-21T14:00:00Z

        # Datetime objects
        assert parse_forecast_slot_utc({"datetime": dt_aware}, tz) == dt_aware
        assert parse_forecast_slot_utc({"datetime": dt_naive}, tz) == dt_aware
        assert parse_forecast_slot_utc({"utc_datetime": dt_aware}, tz) == dt_aware

        # Numeric timestamps
        assert parse_forecast_slot_utc({"datetime": ts_num}, tz) == datetime.fromtimestamp(ts_num, tz=UTC)
        assert parse_forecast_slot_utc({"utc_datetime": int(ts_num)}, tz) == datetime.fromtimestamp(ts_num, tz=UTC)
        assert parse_forecast_slot_utc({"datetime": 0}, tz) == datetime.fromtimestamp(0, tz=UTC)

        # Invalid/empty/non-finite/overflow
        assert parse_forecast_slot_utc({"datetime": None}, tz) is None
        assert parse_forecast_slot_utc({"datetime": "invalid-date"}, tz) is None
        assert parse_forecast_slot_utc({"datetime": True}, tz) is None
        assert parse_forecast_slot_utc({"datetime": float("nan")}, tz) is None
        assert parse_forecast_slot_utc({"datetime": float("inf")}, tz) is None
        assert parse_forecast_slot_utc({"datetime": 1e20}, tz) is None
        # Calendar-invalid timestamps (must return None rather than raising ValueError)
        assert parse_forecast_slot_utc({"datetime": "2026-02-30T12:00:00Z"}, tz) is None
        assert parse_forecast_slot_utc({"datetime": "2026-06-21T25:00:00Z"}, tz) is None
        assert parse_forecast_slot_utc({"datetime": "2026-06-21T12:65:00+00:00"}, tz) is None
        assert parse_forecast_slot_utc({"datetime": "2026-02-30"}, tz) is None

    def test_minimum_slot_check_uses_filtered_coverage(self, engine: WeatherWindowsEngine):
        now = datetime(2026, 6, 21, 12, 0, tzinfo=UTC)
        valid_slot = _make_hourly_forecast(now, hours=1)[0]
        mixed_one_usable = [
            {"datetime": "2026-02-30T12:00:00Z", "temp_c": 22.0},
            {**valid_slot, "datetime": (now - timedelta(hours=2)).isoformat()},
            valid_slot,
            valid_slot,  # duplicate
            {**valid_slot, "datetime": (now + timedelta(hours=24)).isoformat()},
        ]

        # Profile with min_duration_h=2 requires at least 2 usable slots after filtering
        res_two = engine.evaluate_profile(DEFAULT_PROFILES[PROFILE_OUTDOOR_DRYING], mixed_one_usable, now=now)
        assert res_two.status == "unknown"
        assert res_two.reason_codes == ["insufficient_horizon"]
        assert res_two.horizon_hours == 1
        assert res_two.data_quality == {"available_slots": 1}

        # Profile with min_duration_h=1 only needs 1 usable filtered slot
        prof_one = replace(DEFAULT_PROFILES[PROFILE_OUTDOOR_DRYING], min_duration_h=1)
        res_one = engine.evaluate_profile(prof_one, mixed_one_usable, now=now)
        assert res_one.status == STATUS_SUITABLE_NOW
        assert res_one.horizon_hours == 1

    def test_provider_omitted_variables_assessed_honestly(self, engine: WeatherWindowsEngine):
        start_time = datetime(2026, 6, 21, 11, 0, tzinfo=UTC)

        # 1. Met.no shape: precip_mm + cloud_cover present; precip_prob & gust_kmh absent across all hours
        met_hourly = _make_hourly_forecast(start_time, hours=4)
        for slot in met_hourly:
            slot["precip_prob"] = None
            slot["gust_kmh"] = None

        res_met_dry = engine.evaluate_profile(DEFAULT_PROFILES[PROFILE_OUTDOOR_DRYING], met_hourly, now=start_time)
        assert res_met_dry.status == STATUS_SUITABLE_NOW
        assert res_met_dry.not_assessed_by_provider == ["max_wind_gust_kmh"]
        assert REASON_NOT_ASSESSED_BY_PROVIDER in res_met_dry.reason_codes
        assert res_met_dry.data_quality["not_assessed_by_provider"] == ["max_wind_gust_kmh"]

        # Rain on Met.no via precip_mm still blocks
        met_hourly_wet = _make_hourly_forecast(start_time, hours=4, rain_mm=1.2)
        for slot in met_hourly_wet:
            slot["precip_prob"] = None
            slot["gust_kmh"] = None
        res_met_wet = engine.evaluate_profile(DEFAULT_PROFILES[PROFILE_OUTDOOR_DRYING], met_hourly_wet, now=start_time)
        assert res_met_wet.status == STATUS_UNSUITABLE
        assert REASON_RAIN_AMOUNT in res_met_wet.reason_codes
        assert res_met_wet.not_assessed_by_provider == ["max_wind_gust_kmh"]

        # 2. NWS shape: precip_prob present; precip_mm, gust_kmh, cloud_cover absent across all hours
        nws_hourly = _make_hourly_forecast(start_time, hours=4)
        for slot in nws_hourly:
            slot["precip_mm"] = None
            slot["gust_kmh"] = None
            slot["cloud_cover"] = None

        res_nws_dry = engine.evaluate_profile(DEFAULT_PROFILES[PROFILE_OUTDOOR_DRYING], nws_hourly, now=start_time)
        assert res_nws_dry.status == STATUS_SUITABLE_NOW
        assert res_nws_dry.not_assessed_by_provider == ["max_wind_gust_kmh", "max_cloud_cover_pct"]
        assert REASON_NOT_ASSESSED_BY_PROVIDER in res_nws_dry.reason_codes

        res_nws_garden = engine.evaluate_profile(DEFAULT_PROFILES[PROFILE_GARDEN_WORK], nws_hourly, now=start_time)
        assert res_nws_garden.status == STATUS_SUITABLE_NOW
        assert res_nws_garden.not_assessed_by_provider == ["max_wind_gust_kmh"]

        # 3. Core required inputs: missing BOTH rain signals across all hours stays UNKNOWN
        no_rain_signal = _make_hourly_forecast(start_time, hours=4)
        for slot in no_rain_signal:
            slot["precip_prob"] = None
            slot["precip_mm"] = None
        res_no_rain_sig = engine.evaluate_profile(
            replace(DEFAULT_PROFILES[PROFILE_OUTDOOR_DRYING], max_rain_prob_pct=None, max_rain_mm=None),
            no_rain_signal,
            now=start_time,
        )
        assert res_no_rain_sig.status == STATUS_UNKNOWN
        assert REASON_MISSING_DATA in res_no_rain_sig.reason_codes

    def test_live_gust_hold_hysteresis_and_no_next_start_shift_or_churn(self):
        eng = WeatherWindowsEngine(lat=38.0, lon=23.7)
        t0 = datetime(2026, 6, 21, 9, 0, tzinfo=UTC)
        hourly = _make_hourly_forecast(t0, hours=6)
        profile = DEFAULT_PROFILES[PROFILE_OUTDOOR_DRYING]

        # Open window [09:00..15:00): initially calm -> suitable_now
        r0 = eng.evaluate_profile(profile, hourly, current_data={KEY_NORM_WIND_GUST_MS: 4.0}, now=t0)
        assert r0.status == STATUS_SUITABLE_NOW
        assert r0.next_start == t0.isoformat()

        # Single gust burst 50 km/h (13.9 m/s) at 09:01 -> hold prevents flipping to window_upcoming @ 10:00
        r_spike = eng.evaluate_profile(
            profile, hourly, current_data={KEY_NORM_WIND_GUST_MS: 13.9}, now=t0 + timedelta(minutes=1)
        )
        assert r_spike.status == STATUS_SUITABLE_NOW
        assert r_spike.next_start == t0.isoformat()

        # Gust continues across >= 3 min hold (09:01..09:04) -> activates gust blocker without shifting next_start
        eng.evaluate_profile(profile, hourly, current_data={KEY_NORM_WIND_GUST_MS: 14.0}, now=t0 + timedelta(minutes=2))
        r_held = eng.evaluate_profile(
            profile, hourly, current_data={KEY_NORM_WIND_GUST_MS: 14.5}, now=t0 + timedelta(minutes=4)
        )
        assert r_held.status == STATUS_UNSUITABLE
        # The interrupted forecast window keeps its original times (no re-armed 10:00 start)
        assert r_held.next_start == t0.isoformat()
        assert r_held.next_end == r0.next_end
        assert REASON_CURRENT_GUST_HIGH in r_held.reason_codes
        assert REASON_WINDOW_INTERRUPTED in r_held.reason_codes

        # Fluctuating live gust values must produce identical static reasons_text (no recorder churn)
        r_held2 = eng.evaluate_profile(
            profile, hourly, current_data={KEY_NORM_WIND_GUST_MS: 17.0}, now=t0 + timedelta(minutes=5)
        )
        assert r_held2.reasons_text == r_held.reasons_text
        assert "61" not in " ".join(r_held2.reasons_text)

        # Drops below threshold at 09:06, stays blocked during 5-min off-hold, clears at 09:11
        r_cooling = eng.evaluate_profile(
            profile, hourly, current_data={KEY_NORM_WIND_GUST_MS: 4.0}, now=t0 + timedelta(minutes=6)
        )
        assert r_cooling.status == STATUS_UNSUITABLE
        r_still_holding = eng.evaluate_profile(
            profile, hourly, current_data={KEY_NORM_WIND_GUST_MS: 4.0}, now=t0 + timedelta(minutes=10)
        )
        assert r_still_holding.status == STATUS_UNSUITABLE
        r_cleared = eng.evaluate_profile(
            profile, hourly, current_data={KEY_NORM_WIND_GUST_MS: 4.0}, now=t0 + timedelta(minutes=11)
        )
        assert r_cleared.status == STATUS_SUITABLE_NOW
        assert r_cleared.next_start == t0.isoformat()

        # Live rain inside an already-open [09:00..15:00) window also blocks without inventing next_start=10:00
        r_rain = eng.evaluate_profile(
            profile, hourly, current_data={KEY_RAIN_RATE_FILT: 2.5}, now=t0 + timedelta(minutes=12)
        )
        assert r_rain.status == STATUS_UNSUITABLE
        assert r_rain.next_start == t0.isoformat()
        assert REASON_CURRENTLY_RAINING in r_rain.reason_codes
        assert REASON_WINDOW_INTERRUPTED in r_rain.reason_codes
        assert "2.5" not in " ".join(r_rain.reasons_text)

        # Whereas if [09:00..10:00) was forecast rain and [10:00..15:00) is clean -> window_upcoming @ 10:00
        hourly_future = _make_hourly_forecast(t0, hours=6)
        hourly_future[0]["precip_prob"] = 90
        r_future = eng.evaluate_profile(profile, hourly_future, current_data={KEY_RAIN_RATE_FILT: 2.5}, now=t0)
        assert r_future.status == STATUS_WINDOW_UPCOMING
        assert r_future.next_start == (t0 + timedelta(hours=1)).isoformat()

    def test_short_forecast_horizon_returns_unknown_when_all_hours_pass(self, engine: WeatherWindowsEngine):
        start_time = datetime(2026, 6, 21, 11, 0, tzinfo=UTC)
        hourly_3h = _make_hourly_forecast(start_time, hours=3)
        prof_4h = replace(DEFAULT_PROFILES[PROFILE_OUTDOOR_DRYING], min_duration_h=4)

        res = engine.evaluate_profile(prof_4h, hourly_3h, current_data={}, now=start_time)
        assert res.status == STATUS_UNKNOWN
        assert REASON_INSUFFICIENT_HORIZON in res.reason_codes

        # Mid-hour evaluation: 4 hourly slots [11:00..15:00) at 11:30 = 3.5h < 4h, all passing -> unknown
        res_mid = engine.evaluate_profile(
            prof_4h,
            _make_hourly_forecast(start_time, hours=4),
            current_data={},
            now=start_time + timedelta(minutes=30),
        )
        assert res_mid.status == STATUS_UNKNOWN
        assert REASON_INSUFFICIENT_HORIZON in res_mid.reason_codes

        # Whereas if an hour genuinely fails temperature limit -> unsuitable
        hourly_cold = _make_hourly_forecast(start_time, hours=3)
        hourly_cold[0]["temp_c"] = 2.0
        res_cold = engine.evaluate_profile(prof_4h, hourly_cold, current_data={}, now=start_time)
        assert res_cold.status == STATUS_UNSUITABLE
        assert REASON_TOO_COLD in res_cold.reason_codes

    def test_stale_live_gust_and_rain_ignored(self):
        from tests.test_coordinator import _make_coordinator

        now = datetime(2026, 6, 21, 11, 0, tzinfo=UTC)
        old = now - timedelta(hours=4)
        coord = _make_coordinator(wind_speed=2.0, wind_gust=20.0)
        coord.staleness_s = 3600
        coord.forecast_lat = 38.0
        coord.forecast_lon = 23.7
        coord.weather_windows_enabled = True
        coord.hass.states.get(coord.sources[SRC_GUST]).last_reported = old
        coord.hass.states.get(coord.sources[SRC_GUST]).last_updated = old
        coord.hass.states.get(coord.sources[SRC_RAIN_TOTAL]).last_reported = old
        coord.hass.states.get(coord.sources[SRC_RAIN_TOTAL]).last_updated = old

        hourly = _make_hourly_forecast(now, hours=4)
        coord.data = {
            KEY_FORECAST: {"hourly": hourly},
            KEY_NORM_WIND_GUST_MS: 20.0,
            KEY_RAIN_RATE_FILT: 3.0,
            "_stale_sources": [],
        }
        coord._compute_weather_windows(coord.data, now)
        res = coord.data[KEY_WEATHER_WINDOWS][PROFILE_OUTDOOR_DRYING]
        assert res["status"] == STATUS_SUITABLE_NOW
        assert REASON_CURRENT_GUST_HIGH not in res["reason_codes"]
        assert REASON_CURRENTLY_RAINING not in res["reason_codes"]

    def test_localized_and_unit_formatted_window_reasons(self):
        now = datetime(2026, 6, 21, 11, 0, tzinfo=UTC)
        cold_hourly = _make_hourly_forecast(now, hours=4, temp_c=2.0, wind_kmh=40.0, rain_mm=5.0)
        eng_us = WeatherWindowsEngine(
            lat=38.0, lon=23.7, language="en", temp_unit="°F", wind_unit="mph", rain_unit="in"
        )
        res_us = eng_us.evaluate_profile(DEFAULT_PROFILES[PROFILE_OUTDOOR_DRYING], cold_hourly, now=now)
        text_us = " ".join(res_us.reasons_text)
        assert "°C" not in text_us
        assert "km/h" not in text_us
        assert "50.0°F" in text_us or "18.6 mph" in text_us or "0.00 in" in text_us

        eng_fr = WeatherWindowsEngine(lat=38.0, lon=23.7, language="fr")
        res_fr = eng_fr.evaluate_profile(
            DEFAULT_PROFILES[PROFILE_OUTDOOR_DRYING], _make_hourly_forecast(now, hours=4), now=now
        )
        assert "Conditions meet" not in res_fr.reasons_text[0]
        assert "créneau" in res_fr.reasons_text[0].lower() or "limites" in res_fr.reasons_text[0].lower()


class TestReleaseReviewFixes:
    """Regression tests for the v3.0.0 release review (interrupted windows, hold, text stability)."""

    @staticmethod
    def _sustain_gust(eng: WeatherWindowsEngine, profile, hourly, t0: datetime, gust_ms: float = 14.0):
        res = None
        for minute in (0, 1, 2, 4):
            res = eng.evaluate_profile(
                profile, hourly, current_data={KEY_NORM_WIND_GUST_MS: gust_ms}, now=t0 + timedelta(minutes=minute)
            )
        return res

    def test_full_day_window_stays_visible_while_live_gust_blocks_it(self):
        eng = WeatherWindowsEngine(lat=38.0, lon=23.7)
        t0 = datetime(2026, 6, 21, 9, 30, tzinfo=UTC)
        hourly = _make_hourly_forecast(t0.replace(minute=0), hours=25)
        profile = DEFAULT_PROFILES[PROFILE_OUTDOOR_DRYING]

        calm = eng.evaluate_profile(profile, hourly, current_data={KEY_NORM_WIND_GUST_MS: 3.0}, now=t0)
        assert calm.status == STATUS_SUITABLE_NOW

        blocked = self._sustain_gust(eng, profile, hourly, t0 + timedelta(minutes=1))
        assert blocked.status == STATUS_UNSUITABLE
        assert REASON_CURRENT_GUST_HIGH in blocked.reason_codes
        assert REASON_WINDOW_INTERRUPTED in blocked.reason_codes
        # Same day, same window: not "next window tomorrow morning"
        assert blocked.next_start == calm.next_start
        assert blocked.next_end == calm.next_end
        assert blocked.windows[0]["start_iso"] == calm.windows[0]["start_iso"]
        assert blocked.windows[0]["end_iso"] == calm.windows[0]["end_iso"]
        assert "tomorrow" not in " ".join(blocked.reasons_text)

    def test_action_evaluation_reads_but_never_resets_the_gust_hold(self):
        eng = WeatherWindowsEngine(lat=38.0, lon=23.7)
        t0 = datetime(2026, 6, 21, 9, 30, tzinfo=UTC)
        hourly = _make_hourly_forecast(t0.replace(minute=0), hours=8)
        profile = DEFAULT_PROFILES[PROFILE_OUTDOOR_DRYING]
        assert self._sustain_gust(eng, profile, hourly, t0).status == STATUS_UNSUITABLE

        gust = {KEY_NORM_WIND_GUST_MS: 14.0}
        t_svc = t0 + timedelta(minutes=5)
        # Same limits: the action sees the active hold
        same = eng.evaluate_profile(profile, hourly, current_data=gust, now=t_svc, update_live_hold=False)
        assert same.status == STATUS_UNSUITABLE
        # Different gust limit: evaluated without the hold, and the hold itself is untouched
        relaxed = apply_profile_overrides(profile, {"max_wind_gust_kmh": 60}, profile_id=profile.profile_id)
        svc = eng.evaluate_profile(relaxed, hourly, current_data=gust, now=t_svc, update_live_hold=False)
        assert svc.status == STATUS_SUITABLE_NOW
        after = eng.evaluate_profile(profile, hourly, current_data=gust, now=t_svc + timedelta(minutes=1))
        assert after.status == STATUS_UNSUITABLE
        assert REASON_CURRENT_GUST_HIGH in after.reason_codes

    def test_action_with_a_tighter_gust_limit_keeps_the_sustained_hold(self):
        eng = WeatherWindowsEngine(lat=38.0, lon=23.7)
        t0 = datetime(2026, 6, 21, 9, 30, tzinfo=UTC)
        hourly = _make_hourly_forecast(t0.replace(minute=0), hours=8)
        profile = DEFAULT_PROFILES[PROFILE_OUTDOOR_DRYING]
        assert self._sustain_gust(eng, profile, hourly, t0).status == STATUS_UNSUITABLE

        gust = {KEY_NORM_WIND_GUST_MS: 14.0}  # 50.4 km/h, above the 45 km/h profile limit
        t_svc = t0 + timedelta(minutes=5)
        tighter = apply_profile_overrides(profile, {"max_wind_gust_kmh": 30}, profile_id=profile.profile_id)
        svc = eng.evaluate_profile(tighter, hourly, current_data=gust, now=t_svc, update_live_hold=False)
        assert svc.status == STATUS_UNSUITABLE
        assert REASON_CURRENT_GUST_HIGH in svc.reason_codes
        # A looser limit than the tracked one has no sustained evidence and is not held
        looser = apply_profile_overrides(profile, {"max_wind_gust_kmh": 50}, profile_id=profile.profile_id)
        svc = eng.evaluate_profile(looser, hourly, current_data=gust, now=t_svc, update_live_hold=False)
        assert REASON_CURRENT_GUST_HIGH not in svc.reason_codes

    def test_upcoming_window_text_uses_local_clock_and_tomorrow(self):
        eng = WeatherWindowsEngine(lat=38.0, lon=23.7)
        now = datetime(2026, 6, 21, 20, 0, tzinfo=UTC)
        hourly = _make_hourly_forecast(now, hours=24)
        res = eng.evaluate_profile(DEFAULT_PROFILES[PROFILE_GARDEN_WORK], hourly, now=now)
        assert res.status == STATUS_WINDOW_UPCOMING
        text = " ".join(res.reasons_text)
        assert "tomorrow" in text
        assert "T0" not in text and "+00:00" not in text  # no raw ISO timestamps

    def test_profile_names_and_field_labels_are_localized(self):
        now = datetime(2026, 6, 21, 9, 0, tzinfo=UTC)
        metno = _make_hourly_forecast(now, hours=6)
        for slot in metno:
            slot["precip_prob"] = None
            slot["gust_kmh"] = None
        eng_fr = WeatherWindowsEngine(lat=38.0, lon=23.7, language="fr")
        res = eng_fr.evaluate_profile(DEFAULT_PROFILES[PROFILE_OUTDOOR_DRYING], metno, now=now)
        text = " ".join(res.reasons_text)
        assert "Séchage du linge en extérieur" in text
        assert "rafales" in text
        assert "wind gusts" not in text

        renamed = replace(DEFAULT_PROFILES[PROFILE_CUSTOM], name="Bike ride", enabled=True, require_daylight=False)
        res_named = eng_fr.evaluate_profile(renamed, _make_hourly_forecast(now, hours=6, temp_c=20.0), now=now)
        assert "Bike ride" in res_named.reasons_text[0]

    def test_window_text_tables_cover_every_language(self):
        from custom_components.ws_core import localize

        en_keys = set(localize._WINDOW_TEXT["en"])
        for lang, table in localize._WINDOW_TEXT.items():
            assert set(table) == en_keys, lang
            assert set(localize._WINDOW_FIELD_LABELS[lang]) == set(localize._WINDOW_FIELD_LABELS["en"]), lang
        assert localize.window_field_labels("de-AT", ["max_wind_gust_kmh"]) == "Windböen"
        assert localize.window_text("xx", "pn_prefix", provider="NWS") == "Provider notice (NWS):"


class TestDeepReviewFixes:
    """Regression tests for the v3.0.0 deep review (forecast shape, stable starts, duration cap)."""

    def test_three_hourly_rows_are_unknown_not_unsuitable(self):
        eng = WeatherWindowsEngine(lat=37.9, lon=23.7)
        now = datetime(2026, 6, 21, 6, 30, tzinfo=UTC)
        three_hourly = [
            _make_hourly_forecast(now.replace(minute=0) + timedelta(hours=3 * i), hours=1)[0] for i in range(9)
        ]
        res = eng.evaluate_profile(DEFAULT_PROFILES[PROFILE_OUTDOOR_DRYING], three_hourly, now=now)
        assert res.status == STATUS_UNKNOWN
        assert res.reason_codes == [REASON_FORECAST_TOO_COARSE]
        assert res.data_quality["typical_step_h"] == 3
        assert "3 hours apart" in res.reasons_text[0]

    def test_single_missing_hour_is_still_an_hourly_series(self):
        eng = WeatherWindowsEngine(lat=37.9, lon=23.7)
        now = datetime(2026, 6, 21, 6, 30, tzinfo=UTC)
        hourly = _make_hourly_forecast(now.replace(minute=0), hours=12)
        del hourly[6]
        res = eng.evaluate_profile(DEFAULT_PROFILES[PROFILE_OUTDOOR_DRYING], hourly, now=now)
        assert REASON_FORECAST_TOO_COARSE not in res.reason_codes
        assert res.status == STATUS_SUITABLE_NOW

    def test_no_forecast_reports_forecast_unavailable(self):
        eng = WeatherWindowsEngine(lat=37.9, lon=23.7)
        now = datetime(2026, 6, 21, 9, 0, tzinfo=UTC)
        for empty in (None, []):
            res = eng.evaluate_profile(DEFAULT_PROFILES[PROFILE_OUTDOOR_DRYING], empty, now=now)
            assert res.status == STATUS_UNKNOWN
            assert res.reason_codes == [REASON_FORECAST_UNAVAILABLE]
        # Rows that exist but all lie outside the horizon keep the horizon reason
        stale = _make_hourly_forecast(now - timedelta(hours=30), hours=5)
        res_stale = eng.evaluate_profile(DEFAULT_PROFILES[PROFILE_OUTDOOR_DRYING], stale, now=now)
        assert res_stale.reason_codes == [REASON_INSUFFICIENT_HORIZON]

    def test_open_window_keeps_its_start_across_hours(self):
        eng = WeatherWindowsEngine(lat=37.9, lon=23.7)
        t0 = datetime(2026, 6, 21, 6, 0, tzinfo=UTC)
        hourly = _make_hourly_forecast(t0, hours=30)
        profile = DEFAULT_PROFILES[PROFILE_OUTDOOR_DRYING]
        first = eng.evaluate_profile(profile, hourly, now=t0 + timedelta(minutes=5))
        assert first.status == STATUS_SUITABLE_NOW
        starts = {
            eng.evaluate_profile(profile, hourly, now=t0 + timedelta(minutes=m)).next_start for m in range(5, 300, 15)
        }
        assert starts == {first.next_start}

        # Action evaluations read the remembered start but never create or move it
        fresh = WeatherWindowsEngine(lat=37.9, lon=23.7)
        svc = fresh.evaluate_profile(profile, hourly, now=t0 + timedelta(hours=2, minutes=5), update_live_hold=False)
        assert svc.next_start == (t0 + timedelta(hours=2)).isoformat()
        assert fresh._open_window_start == {}

    def test_open_window_start_resets_after_the_window_closes(self):
        eng = WeatherWindowsEngine(lat=37.9, lon=23.7)
        t0 = datetime(2026, 6, 21, 6, 0, tzinfo=UTC)
        hourly = _make_hourly_forecast(t0, hours=30)
        hourly[3]["precip_prob"] = 90  # 09:00-10:00 UTC wet: first window 06:00-09:00
        profile = DEFAULT_PROFILES[PROFILE_OUTDOOR_DRYING]
        assert eng.evaluate_profile(profile, hourly, now=t0 + timedelta(minutes=5)).next_start == t0.isoformat()
        later = eng.evaluate_profile(profile, hourly, now=t0 + timedelta(hours=4, minutes=5))
        assert later.status == STATUS_SUITABLE_NOW
        assert later.next_start == (t0 + timedelta(hours=4)).isoformat()

    def test_minimum_duration_is_capped_at_23_hours(self):
        from custom_components.ws_core.const import CONF_CUSTOM_MIN_DURATION_H
        from custom_components.ws_core.weather_windows import MAX_MIN_DURATION_H

        assert MAX_MIN_DURATION_H == 23
        opts = {CONF_WEATHER_WINDOW_PROFILES: [PROFILE_CUSTOM], CONF_CUSTOM_MIN_DURATION_H: 24}
        assert resolve_profiles(opts)[PROFILE_CUSTOM].min_duration_h == 23
        capped = apply_profile_overrides(DEFAULT_PROFILES[PROFILE_CUSTOM], {"min_duration_h": 40})
        assert capped.min_duration_h == 23


def test_repeated_naive_hour_at_dst_fall_back_is_the_second_occurrence():
    """Naive local times list 02:00 twice when clocks go back; no hour may go missing."""
    tz = ZoneInfo("Europe/Berlin")
    old_tz = dt_util.get_default_time_zone()
    dt_util.set_default_time_zone(tz)
    try:
        now = datetime(2026, 10, 24, 22, 30, tzinfo=UTC)
        rows = []
        for i in range(26):
            local = (now.replace(minute=0) + timedelta(hours=i)).astimezone(tz)
            rows.append(
                {
                    "datetime": local.isoformat()[:19],  # naive local time, as some entities send it
                    "temp_c": 12.0,
                    "precip_prob": 0,
                    "precip_mm": 0.0,
                    "humidity": 60.0,
                    "wind_kmh": 10.0,
                    "gust_kmh": 15.0,
                    "cloud_cover": 10.0,
                }
            )
        profile = replace(DEFAULT_PROFILES[PROFILE_CUSTOM], enabled=True, require_daylight=False, min_temp_c=0.0)
        res = WeatherWindowsEngine(lat=52.5, lon=13.4).evaluate_profile(profile, rows, now=dt_util.as_local(now))
        assert res.horizon_hours == 24
        assert len(res.windows) == 1  # one continuous window, not split at the repeated hour
        assert res.status == STATUS_SUITABLE_NOW
        # A naive time repeated outside the DST change is still a plain duplicate
        dup = [*rows[:5], rows[2]]
        res_dup = WeatherWindowsEngine(lat=52.5, lon=13.4).evaluate_profile(profile, dup, now=dt_util.as_local(now))
        assert len(res_dup.slots) == 5
    finally:
        dt_util.set_default_time_zone(old_tz)
