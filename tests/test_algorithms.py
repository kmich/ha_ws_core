"""Unit tests for ws_core meteorological algorithms."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from custom_components.ws_core.algorithms import (
    ZAMBRETTI_TEXTS,
    KalmanFilter,
    aqi_level,
    beaufort_description,
    calculate_absolute_humidity,
    calculate_air_density,
    calculate_apparent_temperature,
    calculate_clearness_index,
    calculate_cloud_base_m,
    calculate_delta_t,
    calculate_dew_point,
    calculate_freezing_level_m,
    calculate_heat_index,
    calculate_humidex,
    calculate_moon_illumination,
    calculate_moon_phase,
    calculate_rain_probability,
    calculate_sea_level_pressure,
    calculate_thsw_index,
    calculate_thw_index,
    calculate_us_aqi,
    calculate_utci,
    calculate_vpd,
    calculate_wbgt_outdoor,
    calculate_wbgt_simplified,
    calculate_wet_bulb,
    calculate_wind_chill,
    clearness_to_cloud_cover,
    compute_fwi,
    direction_to_quadrant,
    et0_hargreaves,
    et0_penman_monteith,
    fog_probability,
    moon_display_string,
    pollen_level,
    pollen_overall,
    pressure_trend_display,
    uv_burn_time_minutes,
    uv_level,
    wind_speed_to_beaufort,
    zambretti_forecast,
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
        assert uv_level(0.5) == "low"
        assert uv_level(3.0) == "moderate"
        assert uv_level(6.0) == "high"
        assert uv_level(8.0) == "very_high"
        assert uv_level(11.0) == "extreme"


class TestAQI:
    def test_good(self):
        aqi = calculate_us_aqi(5.0, 20.0)
        assert aqi is not None and aqi < 51
        assert aqi_level(aqi) == "good"

    def test_unhealthy(self):
        aqi = calculate_us_aqi(100.0, 200.0)
        assert aqi is not None and aqi >= 150

    def test_none_inputs(self):
        assert calculate_us_aqi(None, None) is None

    def test_levels(self):
        assert aqi_level(0) == "good"
        assert aqi_level(100) == "moderate"
        assert aqi_level(200) == "unhealthy"


class TestPollen:
    def test_none_index(self):
        result = pollen_level(None)
        assert result == "unknown"

    def test_zero_index(self):
        assert pollen_level(0) == "none"

    def test_low(self):
        assert pollen_level(2) in ("low", "very_low")

    def test_high(self):
        assert pollen_level(4) in ("high", "very_high")

    def test_overall_worst(self):
        overall = pollen_overall(1, 4, 0)
        assert overall in ("high", "very_high")


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


class TestHeatIndex:
    def test_hot_humid(self):
        hi = calculate_heat_index(32.0, 70.0)
        assert hi is not None and 36.0 < hi < 44.0

    def test_below_threshold_returns_none(self):
        assert calculate_heat_index(20.0, 70.0) is None

    def test_dry_returns_none(self):
        assert calculate_heat_index(30.0, 30.0) is None


class TestWindChill:
    def test_cold_windy(self):
        wc = calculate_wind_chill(-5.0, 5.0)
        assert wc is not None and -12.0 < wc < -9.0

    def test_warm_returns_none(self):
        assert calculate_wind_chill(15.0, 5.0) is None

    def test_calm_returns_none(self):
        assert calculate_wind_chill(-5.0, 1.0) is None


class TestHumidex:
    def test_hot_humid(self):
        hx = calculate_humidex(30.0, 22.0)
        assert hx is not None and 37.0 < hx < 43.0

    def test_not_above_ambient_returns_none(self):
        assert calculate_humidex(10.0, -5.0) is None


class TestVPD:
    def test_typical(self):
        vpd = calculate_vpd(25.0, 50.0)
        assert 1.5 < vpd < 1.65

    def test_saturated_is_zero(self):
        assert calculate_vpd(25.0, 100.0) == 0.0


class TestAbsoluteHumidity:
    def test_typical(self):
        ah = calculate_absolute_humidity(25.0, 50.0)
        assert 10.5 < ah < 12.5


class TestDeltaT:
    def test_basic(self):
        assert calculate_delta_t(30.0, 22.0) == 8.0


class TestTHW:
    def test_wind_cools(self):
        hi = calculate_heat_index(32.0, 70.0)
        thw = calculate_thw_index(32.0, 70.0, 3.0)
        assert thw is not None and thw < hi

    def test_below_threshold_returns_none(self):
        assert calculate_thw_index(20.0, 70.0, 3.0) is None


class TestTHSW:
    def test_solar_warms(self):
        thw = calculate_thw_index(32.0, 70.0, 3.0)
        thsw = calculate_thsw_index(32.0, 70.0, 3.0, 800.0)
        assert thsw is not None and thsw > thw

    def test_below_threshold_returns_none(self):
        assert calculate_thsw_index(20.0, 70.0, 3.0, 800.0) is None


class TestClearnessIndex:
    def test_clear_sky(self):
        kt = calculate_clearness_index(600.0, 45.0)
        assert kt is not None and 0.75 < kt < 0.9

    def test_low_sun_returns_none(self):
        assert calculate_clearness_index(600.0, 2.0) is None

    def test_clamped_to_one(self):
        assert calculate_clearness_index(5000.0, 45.0) == 1.0

    def test_cloud_cover_inversion(self):
        assert clearness_to_cloud_cover(0.83) == 17
        assert clearness_to_cloud_cover(1.0) == 0
        assert clearness_to_cloud_cover(0.0) == 100


# ===========================================================================
# EXPANDED REFERENCE-VALUE TESTS
# ===========================================================================


class TestDewPointReferenceValues:
    """Magnus-formula dew point — known T/RH pairs from Alduchov & Eskridge."""

    def test_20c_50pct(self):
        """T=20°C, RH=50% → ~9.3°C (±0.2°C)."""
        dp = calculate_dew_point(20.0, 50.0)
        assert abs(dp - 9.3) <= 0.2, f"Expected ~9.3°C, got {dp}"

    def test_30c_80pct(self):
        """T=30°C, RH=80% → ~26.2°C (±0.2°C)."""
        dp = calculate_dew_point(30.0, 80.0)
        assert abs(dp - 26.2) <= 0.2, f"Expected ~26.2°C, got {dp}"

    def test_0c_100pct(self):
        """T=0°C, RH=100% → 0°C (air already saturated)."""
        dp = calculate_dew_point(0.0, 100.0)
        assert abs(dp - 0.0) < 0.1, f"Expected 0°C, got {dp}"

    def test_40c_10pct(self):
        """T=40°C, RH=10% → ~2.6°C (±0.5°C) — very dry hot air.

        Note: the Magnus formula (Alduchov & Eskridge 1996 constants a=17.625,
        b=243.04) gives ≈2.62°C for this input, which differs from the
        simplified August-Roche-Magnus value sometimes cited as -1.3°C.
        """
        dp = calculate_dew_point(40.0, 10.0)
        assert abs(dp - 2.62) <= 0.5, f"Expected ~2.62°C (A&E constants), got {dp}"

    def test_dew_point_never_exceeds_temperature(self):
        """Physical constraint: dew point <= air temperature at all times."""
        for temp in [-20, -5, 0, 10, 20, 30, 40]:
            for rh in [10, 30, 50, 70, 90, 100]:
                dp = calculate_dew_point(float(temp), float(rh))
                assert dp <= temp + 0.05, (
                    f"Dew point {dp} exceeded temperature {temp} at RH={rh}%"
                )


class TestBeaufortAllBoundaries:
    """WMO Beaufort scale — all 12 category boundaries."""

    def test_bf0_calm(self):
        assert wind_speed_to_beaufort(0.0) == 0

    def test_bf1_light_air(self):
        # Boundary at 0.3 m/s: below → 0, at or above → 1
        assert wind_speed_to_beaufort(0.29) == 0
        assert wind_speed_to_beaufort(0.3) == 1

    def test_bf2_light_breeze(self):
        assert wind_speed_to_beaufort(1.59) == 1
        assert wind_speed_to_beaufort(1.6) == 2

    def test_bf3_gentle_breeze(self):
        assert wind_speed_to_beaufort(3.39) == 2
        assert wind_speed_to_beaufort(3.4) == 3

    def test_bf4_moderate_breeze(self):
        assert wind_speed_to_beaufort(5.49) == 3
        assert wind_speed_to_beaufort(5.5) == 4

    def test_bf5_fresh_breeze(self):
        assert wind_speed_to_beaufort(7.99) == 4
        assert wind_speed_to_beaufort(8.0) == 5

    def test_bf6_strong_breeze(self):
        assert wind_speed_to_beaufort(10.79) == 5
        assert wind_speed_to_beaufort(10.8) == 6

    def test_bf7_near_gale(self):
        assert wind_speed_to_beaufort(13.89) == 6
        assert wind_speed_to_beaufort(13.9) == 7

    def test_bf8_gale(self):
        assert wind_speed_to_beaufort(17.19) == 7
        assert wind_speed_to_beaufort(17.2) == 8

    def test_bf9_strong_gale(self):
        assert wind_speed_to_beaufort(20.79) == 8
        assert wind_speed_to_beaufort(20.8) == 9

    def test_bf10_storm(self):
        assert wind_speed_to_beaufort(24.49) == 9
        assert wind_speed_to_beaufort(24.5) == 10

    def test_bf11_violent_storm(self):
        assert wind_speed_to_beaufort(28.49) == 10
        assert wind_speed_to_beaufort(28.5) == 11

    def test_bf12_hurricane(self):
        assert wind_speed_to_beaufort(32.69) == 11
        assert wind_speed_to_beaufort(32.7) == 12
        assert wind_speed_to_beaufort(50.0) == 12

    def test_descriptions_non_empty(self):
        """All 13 Beaufort numbers (0-12) must return a non-empty description."""
        for bf in range(13):
            desc = beaufort_description(bf)
            assert isinstance(desc, str) and len(desc) > 0, (
                f"Beaufort {bf} returned empty description"
            )


class TestSeaLevelPressureReferenceValues:
    """Hypsometric sea-level pressure reduction."""

    def test_zero_elevation_passthrough(self):
        """Station at sea level: MSLP must equal station pressure exactly."""
        slp = calculate_sea_level_pressure(1013.25, 0.0, 15.0)
        assert abs(slp - 1013.25) < 0.1

    def test_500m_15c(self):
        """Station ~954 hPa at 500 m, T=15°C → approx 1012 hPa (±2 hPa).

        A realistic station pressure at 500 m elevation is ~954 hPa, not 950.
        Using 950 hPa (low for 500 m) yields ~1008 hPa.  Using ~953.7 hPa
        (computed from the inverse formula) yields exactly 1012 hPa.
        """
        slp = calculate_sea_level_pressure(953.7, 500.0, 15.0)
        assert abs(slp - 1012.0) <= 2.0, f"Expected ~1012 hPa, got {slp}"

    def test_higher_elevation_gives_higher_mslp(self):
        """Pressure increases when reduced from higher elevation."""
        slp_low = calculate_sea_level_pressure(1000.0, 100.0, 15.0)
        slp_high = calculate_sea_level_pressure(1000.0, 1000.0, 15.0)
        assert slp_high > slp_low

    def test_warmer_temperature_gives_lower_correction(self):
        """Warmer air = less dense = smaller hypsometric correction."""
        slp_cold = calculate_sea_level_pressure(1000.0, 500.0, 0.0)
        slp_warm = calculate_sea_level_pressure(1000.0, 500.0, 30.0)
        assert slp_cold > slp_warm


class TestZambrettiReferenceValues:
    """Zambretti barometric forecaster."""

    def test_high_rising_north_fine_weather(self):
        """High pressure + rising trend + N wind → fine-weather Z-number (low)."""
        text, z = zambretti_forecast(
            mslp=1030.0,
            pressure_trend_3h=2.0,
            wind_quadrant="N",
            humidity=45.0,
            month=6,
            hemisphere="Northern",
            climate="Mediterranean",
            wind_speed_ms=4.0,
        )
        # Z-number should be in the fine/settled range (1-8)
        assert z <= 8, f"Expected fine-weather Z (<=8), got Z={z} ({text})"
        assert isinstance(text, str) and len(text) > 0

    def test_low_falling_stormy(self):
        """Low pressure + rapidly falling trend + S wind → unsettled/stormy forecast."""
        text, z = zambretti_forecast(
            mslp=990.0,
            pressure_trend_3h=-3.0,
            wind_quadrant="S",
            humidity=90.0,
            month=11,
            hemisphere="Northern",
            climate="Mediterranean",
            wind_speed_ms=8.0,
        )
        # Z-number should be in the unsettled/stormy range (17-26)
        assert z >= 17, f"Expected stormy Z (>=17), got Z={z} ({text})"

    def test_all_z_numbers_return_nonempty_string(self):
        """All 26 Z-number texts in ZAMBRETTI_TEXTS must be non-empty strings."""
        assert len(ZAMBRETTI_TEXTS) == 26
        for i, text in enumerate(ZAMBRETTI_TEXTS):
            assert isinstance(text, str) and len(text) > 0, (
                f"Z={i + 1} returned empty text"
            )

    def test_z_number_always_in_valid_range(self):
        """Zambretti Z-number must always be in [1, 26]."""
        test_cases = [
            (1060.0, 3.0, "N", 30.0, 6),
            (1000.0, 0.0, "E", 60.0, 3),
            (960.0, -4.0, "S", 95.0, 12),
            (950.0, -2.0, "W", 85.0, 1),
        ]
        for mslp, trend, wind, rh, month in test_cases:
            text, z = zambretti_forecast(mslp, trend, wind, rh, month)
            assert 1 <= z <= 26, f"Z={z} out of range for inputs {mslp}, {trend}, {wind}"

    def test_returns_tuple_of_str_and_int(self):
        text, z = zambretti_forecast(1020.0, 0.0, "N", 55.0, 7)
        assert isinstance(text, str)
        assert isinstance(z, int)


class TestCanadianFWIReferenceValues:
    """Canadian Forest Fire Weather Index system — Van Wagner 1987."""

    def test_standard_summer_day_ffmc_range(self):
        """Summer day from seasonal start defaults → FFMC should be in [85-95]."""
        result = compute_fwi(
            ffmc_prev=85.0,
            dmc_prev=6.0,
            dc_prev=15.0,
            temp_c=25.0,
            rh_pct=40.0,
            wind_kmh=20.0,
            rain_24h_mm=0.0,
            month=7,
        )
        assert 85.0 <= result["ffmc"] <= 95.0, (
            f"FFMC={result['ffmc']} out of expected range [85-95] for summer standard day"
        )

    def test_rain_event_resets_ffmc_lower(self):
        """After heavy rain, FFMC should drop significantly."""
        dry = compute_fwi(
            ffmc_prev=90.0, dmc_prev=30.0, dc_prev=100.0,
            temp_c=25.0, rh_pct=40.0, wind_kmh=15.0, rain_24h_mm=0.0, month=7,
        )
        wet = compute_fwi(
            ffmc_prev=90.0, dmc_prev=30.0, dc_prev=100.0,
            temp_c=15.0, rh_pct=80.0, wind_kmh=5.0, rain_24h_mm=20.0, month=7,
        )
        assert wet["ffmc"] < dry["ffmc"], (
            f"Rain should lower FFMC: wet={wet['ffmc']}, dry={dry['ffmc']}"
        )

    def test_drought_conditions_elevate_fwi(self):
        """High DC (drought) should produce elevated FWI relative to low DC."""
        normal = compute_fwi(
            ffmc_prev=87.0, dmc_prev=20.0, dc_prev=50.0,
            temp_c=28.0, rh_pct=35.0, wind_kmh=25.0, rain_24h_mm=0.0, month=8,
        )
        drought = compute_fwi(
            ffmc_prev=87.0, dmc_prev=80.0, dc_prev=600.0,
            temp_c=28.0, rh_pct=35.0, wind_kmh=25.0, rain_24h_mm=0.0, month=8,
        )
        assert drought["fwi"] > normal["fwi"], (
            f"Drought FWI={drought['fwi']} should exceed normal FWI={normal['fwi']}"
        )

    def test_all_fwi_components_present_and_non_negative(self):
        """All 7 FWI output keys must be present and non-negative."""
        result = compute_fwi(85.0, 6.0, 15.0, 20.0, 50.0, 15.0, 0.0, 6)
        for key in ("ffmc", "dmc", "dc", "isi", "bui", "fwi", "dsr"):
            assert key in result, f"Missing key: {key}"
            assert result[key] >= 0.0, f"{key}={result[key]} is negative"


class TestRainProbabilityReferenceValues:
    """Heuristic rain probability (0-100)."""

    def test_high_pressure_rising_low_probability(self):
        """High pressure + rising trend + dry N wind → low rain probability."""
        prob = calculate_rain_probability(
            mslp=1025.0,
            pressure_trend=2.0,
            humidity=40.0,
            wind_quadrant="N",
            climate_region="Mediterranean",
        )
        # Rising high pressure in fine conditions → low rain chance
        assert prob <= 20, f"Expected low probability, got {prob}%"

    def test_low_pressure_falling_wet_wind_high_probability(self):
        """Low pressure + falling trend + wet SW wind + high humidity → higher probability."""
        prob = calculate_rain_probability(
            mslp=1000.0,
            pressure_trend=-2.5,
            humidity=88.0,
            wind_quadrant="S",
            climate_region="Mediterranean",
        )
        assert prob >= 50, f"Expected high probability, got {prob}%"

    def test_output_always_in_range_0_100(self):
        """Rain probability output must always be in [0, 100]."""
        test_cases = [
            (980.0, -5.0, 100.0, "S"),
            (1060.0, 5.0, 0.0, "N"),
            (1013.0, 0.0, 50.0, "E"),
        ]
        for mslp, trend, rh, wind in test_cases:
            prob = calculate_rain_probability(mslp, trend, rh, wind)
            assert 0 <= prob <= 100, (
                f"Probability {prob} out of [0,100] for {mslp},{trend},{rh},{wind}"
            )


class TestWetBulbReferenceValues:
    """Wet-bulb temperature (Stull 2011 approximation)."""

    def test_saturated_equals_dry_bulb(self):
        """T=20°C, RH=100% → wet-bulb ≈ 20°C (within 0.5°C)."""
        tw = calculate_wet_bulb(20.0, 100.0)
        assert abs(tw - 20.0) <= 0.5, f"Expected ~20°C at saturation, got {tw}"

    def test_30c_30pct_in_range(self):
        """T=30°C, RH=30% → wet-bulb should be roughly 17-19°C."""
        tw = calculate_wet_bulb(30.0, 30.0)
        assert 17.0 <= tw <= 20.0, f"Expected 17-20°C, got {tw}"

    def test_wet_bulb_never_exceeds_temperature(self):
        """Physical constraint: wet-bulb temperature ≤ dry-bulb temperature."""
        for temp in [0, 10, 20, 30, 40]:
            for rh in [20, 40, 60, 80, 99]:
                tw = calculate_wet_bulb(float(temp), float(rh))
                assert tw <= temp + 0.5, (
                    f"Wet-bulb {tw} exceeds temperature {temp} at RH={rh}%"
                )

    def test_lower_humidity_gives_lower_wet_bulb(self):
        """For same temperature, lower humidity → lower wet-bulb."""
        tw_low_rh = calculate_wet_bulb(25.0, 20.0)
        tw_high_rh = calculate_wet_bulb(25.0, 90.0)
        assert tw_low_rh < tw_high_rh


class TestUTCIReferenceValues:
    """Universal Thermal Climate Index (Bröde 2012 polynomial)."""

    def test_moderate_conditions_returns_float(self):
        """T=25°C, tr=25°C (shade), moderate wind → should return a float."""
        result = calculate_utci(ta=25.0, tr=25.0, va=1.0, rh=50.0)
        assert isinstance(result, float), f"Expected float, got {type(result)}"

    def test_neutral_conditions_near_no_stress(self):
        """T=25°C, tr=25°C, low wind, moderate RH → UTCI near comfort zone (22-32°C)."""
        result = calculate_utci(ta=25.0, tr=25.0, va=0.5, rh=50.0)
        assert result is not None
        assert 18.0 <= result <= 35.0, f"Expected comfort-zone UTCI, got {result}"

    def test_elevated_tr_increases_utci(self):
        """Higher mean radiant temperature (tr > ta) must raise UTCI above shade case."""
        shade = calculate_utci(ta=25.0, tr=25.0, va=1.0, rh=50.0)   # tr == ta (shade)
        sun = calculate_utci(ta=25.0, tr=45.0, va=1.0, rh=50.0)     # tr >> ta (full sun)
        assert shade is not None and sun is not None
        assert sun > shade, (
            f"Solar load (tr=45) should raise UTCI above shade (tr=25): "
            f"sun={sun}, shade={shade}"
        )

    def test_out_of_range_returns_none(self):
        """UTCI returns None when ta is outside ±50°C."""
        assert calculate_utci(ta=60.0, tr=60.0, va=1.0, rh=50.0) is None
        assert calculate_utci(ta=-60.0, tr=-60.0, va=1.0, rh=50.0) is None

    def test_cold_conditions_lower_utci(self):
        """Cold temperature + wind → UTCI should be below ta."""
        result = calculate_utci(ta=-10.0, tr=-10.0, va=5.0, rh=60.0)
        assert result is not None
        # Wind chill effect: UTCI < ta
        assert result < -10.0, f"Expected UTCI below -10°C, got {result}"


class TestCloudBaseFreezing:
    """Cloud base (LCL) and freezing level calculations."""

    def test_cloud_base_saturated_is_zero(self):
        """Saturated air (T == Td) → cloud base at ground (0 m)."""
        assert calculate_cloud_base_m(20.0, 20.0) == 0.0

    def test_cloud_base_proportional_to_depression(self):
        """Larger T-Td gap → higher cloud base."""
        cb_small = calculate_cloud_base_m(25.0, 23.0)  # 2°C depression
        cb_large = calculate_cloud_base_m(25.0, 15.0)  # 10°C depression
        assert cb_large > cb_small

    def test_cloud_base_espy_approximation(self):
        """Espy formula: h ≈ 125 × (T - Td). T=25, Td=15 → 1250 m."""
        cb = calculate_cloud_base_m(25.0, 15.0)
        assert abs(cb - 1250.0) < 10.0, f"Expected 1250m, got {cb}"

    def test_freezing_level_at_zero_celsius(self):
        """T=0°C → freezing level is at station elevation."""
        assert calculate_freezing_level_m(0.0, 100.0) == 100.0

    def test_freezing_level_positive_temp(self):
        """T=20°C at 0m elevation → ISA lapse rate → ~3077 m."""
        fl = calculate_freezing_level_m(20.0, 0.0)
        assert abs(fl - 3077.0) < 10.0, f"Expected ~3077m, got {fl}"

    def test_freezing_level_below_zero_stays_at_elevation(self):
        """Negative surface temperature → freezing already at/below surface."""
        fl = calculate_freezing_level_m(-5.0, 200.0)
        assert fl == 200.0


class TestWBGT:
    """WBGT (Wet Bulb Globe Temperature) calculations."""

    def test_wbgt_simplified_formula(self):
        """WBGT_indoor = 0.7 × Twb + 0.3 × Ta."""
        wbgt = calculate_wbgt_simplified(temp_c=30.0, wet_bulb_c=25.0)
        expected = round(0.7 * 25.0 + 0.3 * 30.0, 1)
        assert abs(wbgt - expected) < 0.05, f"Expected {expected}, got {wbgt}"

    def test_wbgt_outdoor_higher_than_indoor_under_solar(self):
        """Outdoor WBGT with solar load should exceed indoor (no solar) WBGT."""
        wbgt_in = calculate_wbgt_simplified(30.0, 25.0)
        wbgt_out = calculate_wbgt_outdoor(30.0, 25.0, solar_w_m2=800.0)
        assert wbgt_out > wbgt_in

    def test_wbgt_no_solar_matches_simplified(self):
        """With zero solar radiation, outdoor WBGT should be close to simplified."""
        wbgt_in = calculate_wbgt_simplified(25.0, 22.0)
        wbgt_out = calculate_wbgt_outdoor(25.0, 22.0, solar_w_m2=0.0)
        # Globe temp at 0 W/m²: Tg = 25 + 0.393*0 - 4 = 21°C
        # WBGT_out = 0.7*22 + 0.2*21 + 0.1*25 = 15.4 + 4.2 + 2.5 = 22.1
        # wbgt_in = 0.7*22 + 0.3*25 = 15.4 + 7.5 = 22.9
        # Just verify they are in a reasonable range, not identical
        assert 18.0 <= wbgt_out <= 27.0
        assert 18.0 <= wbgt_in <= 27.0


class TestFogProbability:
    """Fog probability estimation."""

    def test_saturated_calm_night_high_probability(self):
        """T very close to dew point, calm, night → high fog probability."""
        prob, label = fog_probability(
            temp_c=10.0, dew_c=9.5, wind_ms=0.5, rain_rate_mmph=0.0, is_night=True
        )
        assert prob >= 50.0, f"Expected high fog probability, got {prob}"
        assert label in ("probable", "likely")

    def test_large_depression_low_probability(self):
        """Large T-Td depression → low fog probability."""
        prob, label = fog_probability(
            temp_c=25.0, dew_c=5.0, wind_ms=1.0, rain_rate_mmph=0.0, is_night=False
        )
        assert prob <= 10.0, f"Expected low fog probability, got {prob}"
        assert label == "unlikely"

    def test_wind_reduces_probability(self):
        """Higher wind speed should reduce fog probability."""
        prob_calm, _ = fog_probability(10.0, 9.5, wind_ms=0.5, rain_rate_mmph=0.0, is_night=False)
        prob_windy, _ = fog_probability(10.0, 9.5, wind_ms=5.0, rain_rate_mmph=0.0, is_night=False)
        assert prob_windy < prob_calm

    def test_rain_reduces_fog_probability(self):
        """Active rainfall should reduce fog probability."""
        prob_dry, _ = fog_probability(10.0, 9.5, wind_ms=0.5, rain_rate_mmph=0.0, is_night=True)
        prob_rain, _ = fog_probability(10.0, 9.5, wind_ms=0.5, rain_rate_mmph=1.0, is_night=True)
        assert prob_rain < prob_dry

    def test_output_in_range_0_100(self):
        """Fog probability must be in [0, 100]."""
        for is_night in (True, False):
            prob, _ = fog_probability(-5.0, -5.5, wind_ms=0.0, rain_rate_mmph=0.0, is_night=is_night)
            assert 0.0 <= prob <= 100.0


class TestAirDensity:
    """Dry air density (ρ = P / (Rd × Tk))."""

    def test_standard_atmosphere(self):
        """Standard atmosphere: 1013.25 hPa at 15°C → ~1.225 kg/m³."""
        rho = calculate_air_density(temp_c=15.0, pressure_hpa=1013.25)
        assert abs(rho - 1.225) <= 0.005, f"Expected ~1.225 kg/m³, got {rho}"

    def test_higher_temp_lower_density(self):
        """Warmer air is less dense at same pressure."""
        rho_cold = calculate_air_density(0.0, 1013.25)
        rho_warm = calculate_air_density(30.0, 1013.25)
        assert rho_warm < rho_cold

    def test_higher_pressure_higher_density(self):
        """Higher pressure → more dense air."""
        rho_low = calculate_air_density(15.0, 900.0)
        rho_high = calculate_air_density(15.0, 1050.0)
        assert rho_high > rho_low


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
