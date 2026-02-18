"""Unit tests for ws_core meteorological algorithms."""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from custom_components.ws_core.algorithms import (
    calculate_dew_point, calculate_sea_level_pressure, calculate_apparent_temperature,
    wind_speed_to_beaufort, beaufort_description, direction_to_quadrant,
    pressure_trend_display, zambretti_forecast,
    uv_burn_time_minutes, uv_level, laundry_drying_score,
    calculate_us_aqi, aqi_level, pollen_level, pollen_overall,
    calculate_moon_phase, calculate_moon_illumination, moon_display_string,
    heating_degree_hours, cooling_degree_hours,
    et0_hargreaves, et0_penman_monteith,
    KalmanFilter,
)


class TestDewPoint:
    def test_basic(self):
        dp = calculate_dew_point(20.0, 50.0)
        assert 9.0 < dp < 9.5

    def test_100_pct_humidity(self):
        dp = calculate_dew_point(15.0, 100.0)
        assert abs(dp - 15.0) < 0.1


class TestSLP:
    def test_zero_elevation(self):
        slp = calculate_sea_level_pressure(1013.25, 0.0, 15.0)
        assert abs(slp - 1013.25) < 0.1

    def test_altitude_correction(self):
        slp = calculate_sea_level_pressure(1000.0, 100.0, 15.0)
        assert 1010.0 < slp < 1015.0


class TestApparentTemp:
    def test_hot_humid(self):
        at = calculate_apparent_temperature(35.0, 80.0, 0.5)
        assert at > 38.0

    def test_cold_windy(self):
        at = calculate_apparent_temperature(5.0, 60.0, 10.0)
        assert at < 2.0


class TestBeaufort:
    def test_calm(self):
        assert wind_speed_to_beaufort(0.0) == 0

    def test_gale(self):
        assert wind_speed_to_beaufort(20.0) == 8

    def test_hurricane(self):
        assert wind_speed_to_beaufort(35.0) == 12

    def test_description(self):
        assert len(beaufort_description(3)) > 3


class TestWindQuadrant:
    def test_north(self):
        assert direction_to_quadrant(0.0) == "N"
        assert direction_to_quadrant(360.0) == "N"

    def test_south(self):
        assert direction_to_quadrant(180.0) == "S"


class TestPressureTrend:
    def test_rising(self):
        label = pressure_trend_display(3.0)
        assert label  # not empty

    def test_steady(self):
        label = pressure_trend_display(0.1)
        assert label

    def test_falling(self):
        label = pressure_trend_display(-2.5)
        assert label


class TestZambretti:
    def test_returns_tuple(self):
        result = zambretti_forecast(1020.0, 0.5, "SW", 60.0, 6, "Northern", "Mediterranean")
        assert isinstance(result, tuple)
        assert isinstance(result[0], str)

    def test_high_pressure_rising(self):
        forecast, num = zambretti_forecast(1030.0, 1.5, "SW", 50.0, 6, "Northern", "Mediterranean")
        assert num >= 1


class TestUV:
    def test_uv_3_reasonable(self):
        bt = uv_burn_time_minutes(3.0, 2)
        assert bt > 0

    def test_extreme_uv(self):
        bt = uv_burn_time_minutes(11.0, 2)
        assert bt < 40

    def test_level_labels(self):
        assert uv_level(0.5) == "Low"
        assert uv_level(3.0) == "Moderate"
        assert uv_level(6.0) == "High"
        assert uv_level(8.0) == "Very High"
        assert uv_level(11.0) == "Extreme"


class TestLaundry:
    def test_ideal_conditions(self):
        score = laundry_drying_score(
            temp_c=28.0, humidity=30.0, wind_speed_ms=3.0,
            uv_index=7.0, rain_rate_mmph=0.0, rain_probability=5.0,
        )
        assert score >= 70

    def test_rain_kills_score(self):
        score = laundry_drying_score(
            temp_c=22.0, humidity=80.0, wind_speed_ms=2.0,
            uv_index=1.0, rain_rate_mmph=5.0, rain_probability=90.0,
        )
        assert score < 20


class TestAQI:
    def test_good(self):
        aqi = calculate_us_aqi(5.0, 20.0)
        assert aqi is not None and aqi < 51
        assert aqi_level(aqi) == "Good"

    def test_unhealthy(self):
        aqi = calculate_us_aqi(100.0, 200.0)
        assert aqi is not None and aqi >= 150

    def test_none_inputs(self):
        assert calculate_us_aqi(None, None) is None

    def test_levels(self):
        assert aqi_level(0) == "Good"
        assert aqi_level(100) == "Moderate"
        assert aqi_level(200) == "Unhealthy"


class TestPollen:
    def test_none_index(self):
        result = pollen_level(None)
        assert result in ("None", "Unknown")

    def test_zero_index(self):
        assert pollen_level(0) == "None"

    def test_low(self):
        assert pollen_level(2) in ("Low", "Very Low")

    def test_high(self):
        assert pollen_level(4) in ("High", "Very High")

    def test_overall_worst(self):
        overall = pollen_overall(1, 4, 0)
        assert overall in ("High", "Very High")


class TestMoon:
    def test_new_moon_jan_2024(self):
        phase = calculate_moon_phase(2024, 1, 11)
        assert "new" in phase.lower()

    def test_full_moon_jan_2024(self):
        phase = calculate_moon_phase(2024, 1, 25)
        assert "full" in phase.lower()

    def test_illumination_range(self):
        illum = calculate_moon_illumination(2024, 1, 11)
        assert 0.0 <= illum <= 100.0

    def test_display_string(self):
        s = moon_display_string("full_moon", 99.5)
        assert len(s) > 3


class TestDegreeDays:
    def test_hdd_cold(self):
        assert heating_degree_hours(5.0, base_c=18.0) > 0

    def test_hdd_warm(self):
        assert heating_degree_hours(25.0, base_c=18.0) == 0.0

    def test_cdd_hot(self):
        assert cooling_degree_hours(30.0, base_c=18.0) > 0

    def test_cdd_cold(self):
        assert cooling_degree_hours(10.0, base_c=18.0) == 0.0


class TestET0:
    def test_hargreaves_summer(self):
        et0 = et0_hargreaves(
            t_max_c=38.0, t_min_c=24.0, t_mean_c=31.0, lat_deg=38.0, day_of_year=180
        )
        assert 5.0 < et0 < 15.0

    def test_hargreaves_freezing(self):
        et0 = et0_hargreaves(
            t_max_c=-5.0, t_min_c=-10.0, t_mean_c=-7.5, lat_deg=38.0, day_of_year=15
        )
        # In winter near-freezing conditions, ET₀ is very low (< 1 mm/day)
        assert et0 < 1.0

    def test_penman_monteith(self):
        et0 = et0_penman_monteith(
            temp_mean_c=28.0, temp_max_c=34.0, temp_min_c=22.0,
            humidity=55.0, wind_speed_ms=3.0,
            solar_radiation_wm2=600.0, elevation_m=50.0, day_of_year=180,
        )
        assert 4.0 < et0 < 12.0


class TestKalman:
    def test_converges(self):
        kf = KalmanFilter()
        val = None
        for _ in range(40):
            val = kf.update(5.0)
        assert abs(val - 5.0) < 1.0

    def test_filters_spike(self):
        kf = KalmanFilter()
        kf.update(2.0)
        kf.update(2.0)
        val = kf.update(100.0)
        assert val < 80.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
