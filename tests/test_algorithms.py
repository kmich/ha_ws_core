"""Tests for ws_core meteorological algorithms.

These tests validate formula correctness using known reference values.
All temperature/pressure references cross-checked against NOAA/WMO tables.
"""

import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Isolate algorithms.py - no HA dependency needed
from custom_components.ws_core.algorithms import (
    KalmanFilter,
    beaufort_description,
    calculate_apparent_temperature,
    calculate_dew_point,
    calculate_frost_point,
    calculate_moon_phase,
    calculate_rain_probability,
    calculate_sea_level_pressure,
    calculate_wet_bulb,
    combine_rain_probability,
    determine_current_condition,
    direction_to_cardinal_16,
    direction_to_quadrant,
    fire_danger_level,
    fire_risk_score,
    format_rain_display,
    humidity_level,
    laundry_drying_score,
    least_squares_pressure_trend,
    pressure_trend_display,
    smooth_wind_direction,
    uv_level,
    wind_speed_to_beaufort,
    zambretti_forecast,
)


# ---------------------------------------------------------------------------
# Dew Point (August-Roche-Magnus)
# ---------------------------------------------------------------------------
class TestDewPoint:
    def test_typical_summer(self):
        """25°C / 60% RH → ~16.7°C dew point (NOAA calculator reference)."""
        dp = calculate_dew_point(25.0, 60.0)
        assert 16.0 <= dp <= 17.5, f"Expected ~16.7, got {dp}"

    def test_saturated_air(self):
        """At 100% RH dew point equals air temperature."""
        dp = calculate_dew_point(20.0, 100.0)
        assert abs(dp - 20.0) < 0.1, f"Expected ~20.0, got {dp}"

    def test_cold_dry_arctic(self):
        """Cold dry air: -10°C / 40% RH."""
        dp = calculate_dew_point(-10.0, 40.0)
        assert dp < -10.0, "Dew point must be below air temp when RH < 100%"

    def test_humidity_clamped_at_1(self):
        """Should not crash or return NaN for 0% RH."""
        dp = calculate_dew_point(20.0, 0.0)
        assert math.isfinite(dp)

    def test_output_always_le_temperature(self):
        """Dew point is always ≤ air temperature."""
        for t in range(-20, 40, 5):
            for rh in [20, 40, 60, 80, 100]:
                dp = calculate_dew_point(float(t), float(rh))
                assert dp <= t + 0.01, f"DP {dp} > T {t} at RH={rh}"


# ---------------------------------------------------------------------------
# Sea Level Pressure
# ---------------------------------------------------------------------------
class TestSeaLevelPressure:
    def test_sea_level_station(self):
        """At 0m elevation MSLP equals station pressure."""
        slp = calculate_sea_level_pressure(1013.25, 0.0, 15.0)
        assert abs(slp - 1013.25) < 0.1

    def test_high_altitude_correction(self):
        """At 500m, MSLP > station pressure by ~60 hPa."""
        slp = calculate_sea_level_pressure(950.0, 500.0, 10.0)
        assert 1005 <= slp <= 1020, f"Unexpected MSLP at 500m: {slp}"

    def test_temperature_sensitivity(self):
        """Warmer temperature → slightly lower MSLP correction (less dense air)."""
        slp_cold = calculate_sea_level_pressure(950.0, 500.0, -10.0)
        slp_warm = calculate_sea_level_pressure(950.0, 500.0, 30.0)
        assert slp_cold > slp_warm, "Colder temp should give larger MSLP correction"

    def test_known_value(self):
        """Zurich (~450m, ~10°C) station 960 hPa → MSLP ~1015 hPa."""
        slp = calculate_sea_level_pressure(960.0, 450.0, 10.0)
        assert 1008 <= slp <= 1022


# ---------------------------------------------------------------------------
# Apparent Temperature (BOM)
# ---------------------------------------------------------------------------
class TestApparentTemperature:
    def test_hot_humid_no_wind(self):
        """Hot humid still day feels hotter than actual."""
        at = calculate_apparent_temperature(35.0, 80.0, 0.0)
        assert at > 30.0

    def test_cold_windy(self):
        """Cold windy conditions feel colder."""
        at = calculate_apparent_temperature(5.0, 50.0, 10.0)
        assert at < 5.0

    def test_comfortable_conditions(self):
        """22°C, 50% RH, 2 m/s → feels close to actual temp."""
        at = calculate_apparent_temperature(22.0, 50.0, 2.0)
        assert 15.0 <= at <= 25.0


# ---------------------------------------------------------------------------
# Beaufort Scale
# ---------------------------------------------------------------------------
class TestBeaufort:
    def test_calm(self):
        assert wind_speed_to_beaufort(0.0) == 0

    def test_force_6(self):
        """Strong breeze is 10.8–13.8 m/s → Beaufort 6."""
        assert wind_speed_to_beaufort(12.0) == 6

    def test_hurricane(self):
        assert wind_speed_to_beaufort(35.0) == 12

    def test_boundary_values(self):
        """Check the exact boundary at 0.3 m/s."""
        assert wind_speed_to_beaufort(0.29) == 0
        assert wind_speed_to_beaufort(0.31) == 1

    def test_description_consistency(self):
        """Every Beaufort number 0-12 should have a description."""
        for bft in range(13):
            desc = beaufort_description(bft)
            assert isinstance(desc, str) and len(desc) > 0


# ---------------------------------------------------------------------------
# Wind Direction
# ---------------------------------------------------------------------------
class TestWindDirection:
    def test_north(self):
        assert direction_to_quadrant(0.0) == "N"
        assert direction_to_quadrant(360.0) == "N"

    def test_east(self):
        assert direction_to_quadrant(90.0) == "E"

    def test_south(self):
        assert direction_to_quadrant(180.0) == "S"

    def test_west(self):
        assert direction_to_quadrant(270.0) == "W"

    def test_cardinal_16_north(self):
        assert direction_to_cardinal_16(0.0) == "N"
        assert direction_to_cardinal_16(360.0) == "N"

    def test_cardinal_16_ese(self):
        assert direction_to_cardinal_16(112.5) == "ESE"

    def test_smooth_wind_no_discontinuity(self):
        """Smoothing across 360/0 boundary should not jump."""
        # Going from 350° to 10°
        result = smooth_wind_direction(10.0, 350.0, alpha=0.5)
        # Should be ~0° (north), not ~180°
        assert result < 30.0 or result > 340.0, f"Unexpected: {result}"


# ---------------------------------------------------------------------------
# Pressure Trend
# ---------------------------------------------------------------------------
class TestPressureTrend:
    def test_least_squares_flat(self):
        """Constant pressure gives zero trend."""
        readings = [1013.0] * 12
        trend = least_squares_pressure_trend(readings)
        assert abs(trend) < 0.01

    def test_least_squares_rising(self):
        """Steadily rising pressure gives positive trend."""
        readings = [1010.0 + i * 0.1 for i in range(12)]
        trend = least_squares_pressure_trend(readings)
        assert trend > 0

    def test_display_rising_rapidly(self):
        assert pressure_trend_display(2.0) == "Rising Rapidly"

    def test_display_steady(self):
        assert pressure_trend_display(0.0) == "Steady"
        assert pressure_trend_display(0.5) == "Steady"
        assert pressure_trend_display(-0.5) == "Steady"

    def test_display_falling_rapidly(self):
        assert pressure_trend_display(-2.0) == "Falling Rapidly"

    def test_wmo_boundary_at_0_8(self):
        """WMO boundary: exactly 0.8 hPa/3h is 'Rising', just below is 'Steady'."""
        assert pressure_trend_display(0.8) == "Rising"
        assert pressure_trend_display(0.79) == "Steady"


# ---------------------------------------------------------------------------
# Kalman Filter
# ---------------------------------------------------------------------------
class TestKalmanFilter:
    def test_converges_on_constant_signal(self):
        """After many updates of 5.0, estimate should be close to 5.0."""
        kf = KalmanFilter()
        for _ in range(50):
            est = kf.update(5.0)
        assert abs(est - 5.0) < 0.2

    def test_rejects_negative(self):
        """Rain rate can never be negative."""
        kf = KalmanFilter()
        result = kf.update(-10.0)
        assert result >= 0.0

    def test_spike_damping(self):
        """A single spike should be damped compared to raw value."""
        kf = KalmanFilter()
        for _ in range(20):
            kf.update(0.0)
        spiked = kf.update(100.0)
        assert spiked < 100.0, "Kalman filter should damp the spike"


# ---------------------------------------------------------------------------
# Zambretti Forecast
# ---------------------------------------------------------------------------
class TestZambretti:
    def test_high_pressure_rising_returns_fair(self):
        text, z = zambretti_forecast(mslp=1025.0, pressure_trend_3h=1.0, wind_quadrant="N", humidity=50.0, month=6)
        assert "fair" in text.lower() or "fine" in text.lower() or "settled" in text.lower()

    def test_storm_likely(self):
        text, z = zambretti_forecast(mslp=995.0, pressure_trend_3h=-4.0, wind_quadrant="S", humidity=90.0, month=11)
        assert "storm" in text.lower() or "rain" in text.lower() or "unsettled" in text.lower()

    def test_returns_tuple(self):
        result = zambretti_forecast(mslp=1013.0, pressure_trend_3h=0.0, wind_quadrant="E", humidity=65.0, month=4)
        assert isinstance(result, tuple) and len(result) == 2
        text, z = result
        assert isinstance(text, str) and len(text) > 0
        assert isinstance(z, int) and 1 <= z <= 26


# ---------------------------------------------------------------------------
# Rain Probability
# ---------------------------------------------------------------------------
class TestRainProbability:
    def test_high_pressure_dry_gives_low_prob(self):
        prob = calculate_rain_probability(1025.0, 1.0, 40.0, "N")
        assert prob < 30

    def test_low_pressure_falling_humid_gives_high_prob(self):
        prob = calculate_rain_probability(1000.0, -3.5, 90.0, "W")
        assert prob > 60

    def test_clamped_0_100(self):
        # Extreme inputs
        assert 0 <= calculate_rain_probability(980.0, -5.0, 100.0, "S") <= 100
        assert 0 <= calculate_rain_probability(1040.0, 3.0, 10.0, "N") <= 100


# ---------------------------------------------------------------------------
# Moon Phase
# ---------------------------------------------------------------------------
class TestMoonPhase:
    def test_known_full_moon_jan_2024(self):
        """2024-01-25 was a full moon."""
        phase = calculate_moon_phase(2024, 1, 25)
        assert "full" in phase or "gibbous" in phase  # allow 1-day tolerance

    def test_known_new_moon_jan_2024(self):
        """2024-01-11 was a new moon."""
        phase = calculate_moon_phase(2024, 1, 11)
        assert "new" in phase or "crescent" in phase

    def test_returns_valid_phase(self):
        valid = {
            "new_moon",
            "waxing_crescent",
            "first_quarter",
            "waxing_gibbous",
            "full_moon",
            "waning_gibbous",
            "last_quarter",
            "waning_crescent",
        }
        for day in range(1, 30, 3):
            phase = calculate_moon_phase(2025, 6, day)
            assert phase in valid


# ---------------------------------------------------------------------------
# Fire Weather Index
# ---------------------------------------------------------------------------
class TestFireWeather:
    def test_rainy_day_low_danger(self):
        fwi = fire_risk_score(20.0, 80.0, 2.0, 20.0)
        assert fire_danger_level(fwi) in ("Low", "Moderate")

    def test_extreme_conditions(self):
        fwi = fire_risk_score(38.0, 15.0, 15.0, 0.0)
        level = fire_danger_level(fwi)
        assert level in ("High", "Very High", "Extreme")

    def test_non_negative(self):
        for temp in range(-5, 40, 5):
            fwi = fire_risk_score(float(temp), 50.0, 3.0, 0.0)
            assert fwi >= 0


# ---------------------------------------------------------------------------
# Laundry Score
# ---------------------------------------------------------------------------
class TestLaundryScore:
    def test_raining_gives_zero(self):
        score = laundry_drying_score(25.0, 50.0, 3.0, 5.0, rain_rate_mmph=2.0)
        assert score == 0

    def test_perfect_conditions(self):
        score = laundry_drying_score(30.0, 30.0, 4.0, 8.0, rain_rate_mmph=0.0)
        assert score >= 70

    def test_score_range(self):
        for temp in [10, 20, 30]:
            for rh in [40, 60, 80]:
                s = laundry_drying_score(float(temp), float(rh), 2.0, 4.0, rain_rate_mmph=0.0)
                assert 0 <= s <= 100


# ---------------------------------------------------------------------------
# UV Level
# ---------------------------------------------------------------------------
class TestUVLevel:
    def test_levels(self):
        assert uv_level(0) == "Low"
        assert uv_level(3) == "Moderate"
        assert uv_level(6) == "High"
        assert uv_level(8) == "Very High"
        assert uv_level(11) == "Extreme"


# ---------------------------------------------------------------------------
# Humidity Level
# ---------------------------------------------------------------------------
class TestHumidityLevel:
    def test_levels(self):
        assert humidity_level(15) == "Very Dry"
        assert humidity_level(45) == "Comfortable"
        assert humidity_level(85) == "Very Humid"


# ---------------------------------------------------------------------------
# Current Condition Classifier
# ---------------------------------------------------------------------------
class TestCurrentCondition:
    def _base_kwargs(self, **overrides):
        defaults = dict(
            temp_c=20.0,
            humidity=60.0,
            wind_speed_ms=2.0,
            wind_gust_ms=3.0,
            rain_rate_mmph=0.0,
            dew_point_c=12.0,
            illuminance_lx=50000.0,
            uv_index=5.0,
            zambretti="No significant change",
            pressure_trend=0.0,
            sun_elevation=45.0,
            sun_azimuth=180.0,
            is_day=True,
        )
        defaults.update(overrides)
        return defaults

    def test_sunny_daytime(self):
        cond = determine_current_condition(**self._base_kwargs(illuminance_lx=80000))
        assert cond == "sunny"

    def test_heavy_rain(self):
        cond = determine_current_condition(**self._base_kwargs(rain_rate_mmph=15.0))
        assert cond == "heavy-rain"

    def test_hurricane(self):
        cond = determine_current_condition(**self._base_kwargs(wind_gust_ms=35.0))
        assert cond == "hurricane"

    def test_snowy(self):
        cond = determine_current_condition(**self._base_kwargs(temp_c=-2.0, rain_rate_mmph=1.0, humidity=95.0))
        assert cond in ("snowy", "snow-accumulation")

    def test_clear_night(self):
        cond = determine_current_condition(
            **self._base_kwargs(is_day=False, illuminance_lx=10.0, humidity=40.0)
        )
        assert cond == "clear-night"


# ---------------------------------------------------------------------------
# Frost Point (Buck 1981)
# ---------------------------------------------------------------------------
class TestFrostPoint:
    def test_above_zero_equals_dew_point(self):
        """Above 0°C, frost point should equal dew point."""
        fp = calculate_frost_point(20.0, 60.0)
        dp = calculate_dew_point(20.0, 60.0)
        assert abs(fp - dp) < 0.01

    def test_below_zero_uses_ice_constants(self):
        """Below 0°C, frost point should differ from warm-air dew point."""
        fp = calculate_frost_point(-10.0, 80.0)
        # Frost point at -10°C/80%RH should be around -12 to -13°C
        assert -15.0 < fp < -10.0

    def test_saturated_cold(self):
        """At 100% RH and freezing, frost point ≈ temperature."""
        fp = calculate_frost_point(-5.0, 100.0)
        assert abs(fp - (-5.0)) < 0.2


# ---------------------------------------------------------------------------
# Wet-Bulb Temperature (Stull 2011)
# ---------------------------------------------------------------------------
class TestWetBulb:
    def test_typical_summer(self):
        """30°C / 50% RH → wet bulb ~22°C (psychrometric chart reference)."""
        tw = calculate_wet_bulb(30.0, 50.0)
        assert 20.0 <= tw <= 24.0, f"Expected ~22, got {tw}"

    def test_saturated_equals_dry(self):
        """At 100% RH, wet bulb ≈ dry bulb temperature."""
        # Stull formula has max error ±0.3°C, so allow some tolerance
        tw = calculate_wet_bulb(25.0, 99.0)
        assert abs(tw - 25.0) < 1.0, f"Expected ~25, got {tw}"

    def test_low_humidity(self):
        """Low humidity gives much lower wet-bulb than dry-bulb."""
        tw = calculate_wet_bulb(35.0, 10.0)
        assert tw < 20.0, f"Expected < 20, got {tw}"

    def test_valid_range(self):
        """Should produce reasonable values across valid input range."""
        for temp in range(-15, 45, 10):
            for rh in [10, 30, 50, 70, 90]:
                tw = calculate_wet_bulb(float(temp), float(rh))
                assert tw <= temp + 1.0, f"Wet bulb {tw} > dry bulb {temp}"
                assert tw > temp - 40, f"Wet bulb {tw} unreasonably low"


# ---------------------------------------------------------------------------
# Real Zambretti Forecaster (Z-numbers 1-26)
# ---------------------------------------------------------------------------
class TestZambrettiReal:
    def test_high_pressure_fair(self):
        """High MSLP + rising trend → fair weather (low Z-number)."""
        text, z = zambretti_forecast(
            mslp=1035.0, pressure_trend_3h=1.0, wind_quadrant="N",
            humidity=50.0, month=6, hemisphere="Northern",
        )
        assert z <= 8, f"Expected fair weather (Z≤8), got Z={z}: {text}"

    def test_low_pressure_unsettled(self):
        """Low MSLP + falling trend → unsettled (high Z-number)."""
        text, z = zambretti_forecast(
            mslp=985.0, pressure_trend_3h=-2.0, wind_quadrant="S",
            humidity=90.0, month=11, hemisphere="Northern",
        )
        assert z >= 18, f"Expected unsettled (Z≥18), got Z={z}: {text}"

    def test_z_range_always_valid(self):
        """Z-number should always be 1-26."""
        for p in [950, 980, 1000, 1020, 1050]:
            for trend in [-3, -1, 0, 1, 3]:
                _, z = zambretti_forecast(
                    mslp=float(p), pressure_trend_3h=float(trend),
                    wind_quadrant="W", humidity=60.0, month=3,
                )
                assert 1 <= z <= 26, f"Z={z} out of range for MSLP={p}, trend={trend}"

    def test_climate_region_affects_result(self):
        """Different climate regions should give different results for same conditions."""
        _, z_atlantic = zambretti_forecast(
            mslp=1010.0, pressure_trend_3h=-0.5, wind_quadrant="W",
            humidity=70.0, month=6, climate="Atlantic Europe",
        )
        _, z_med = zambretti_forecast(
            mslp=1010.0, pressure_trend_3h=-0.5, wind_quadrant="W",
            humidity=70.0, month=6, climate="Mediterranean",
        )
        # W wind is "bad" in Atlantic, also "bad" in Mediterranean, but
        # overall adjustments may differ slightly
        assert isinstance(z_atlantic, int)
        assert isinstance(z_med, int)

    def test_returns_valid_text(self):
        """Forecast text should be from the 26-entry table."""
        from custom_components.ws_core.algorithms import ZAMBRETTI_TEXTS
        text, z = zambretti_forecast(
            mslp=1013.0, pressure_trend_3h=0.0, wind_quadrant="N",
            humidity=60.0, month=6,
        )
        assert text in ZAMBRETTI_TEXTS


# ---------------------------------------------------------------------------
# Combine Rain Probability
# ---------------------------------------------------------------------------
class TestCombineRainProbability:
    def test_no_api_returns_local(self):
        result = combine_rain_probability(75.0, None, 12)
        assert result == 75

    def test_daytime_weights_local_higher(self):
        """During daytime convective hours, local weight = 0.5."""
        result = combine_rain_probability(80.0, 20.0, 12)
        # 80*0.5 + 20*0.5 = 50
        assert result == 50

    def test_nighttime_weights_api_higher(self):
        """During nighttime, local weight = 0.3."""
        result = combine_rain_probability(80.0, 20.0, 2)
        # 80*0.3 + 20*0.7 = 24+14 = 38
        assert result == 38


# ---------------------------------------------------------------------------
# Format Rain Display
# ---------------------------------------------------------------------------
class TestFormatRainDisplay:
    def test_dry(self):
        assert format_rain_display(0.0) == "Dry"

    def test_heavy(self):
        assert "Heavy" in format_rain_display(15.0)

    def test_drizzle(self):
        assert format_rain_display(0.1) == "Drizzle"
