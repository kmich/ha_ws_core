"""Meteorological algorithms for Weather Station Core.

All algorithms based on the original ws_station YAML package (v1.0.0-hotfix17)
by Konstantinos. Ported to Python for use in the HACS integration.
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any


def calculate_dew_point(temp_c: float, humidity: float) -> float:
    a = 17.27
    b = 237.7
    alpha = ((a * temp_c) / (b + temp_c)) + math.log(humidity / 100.0)
    return round((b * alpha) / (a - alpha), 2)


def calculate_sea_level_pressure(station_pressure_hpa: float, elevation_m: float, temp_c: float) -> float:
    temp_k = temp_c + 273.15
    exponent = elevation_m / (temp_k * 29.263)
    return round(station_pressure_hpa * math.exp(exponent), 1)


def calculate_apparent_temperature(temp_c: float, humidity: float, wind_speed_ms: float) -> float:
    vp = (humidity / 100) * 6.105 * math.exp((17.27 * temp_c) / (237.7 + temp_c))
    at = temp_c + (0.33 * vp) - (0.70 * wind_speed_ms) - 4.0
    return round(at, 1)


def feels_like_comfort_level(feels_like_c: float) -> str:
    if feels_like_c < -10: return "Dangerous Cold"
    elif feels_like_c < 0: return "Freezing"
    elif feels_like_c < 10: return "Very Cold"
    elif feels_like_c < 15: return "Cold"
    elif feels_like_c < 20: return "Cool"
    elif feels_like_c < 25: return "Comfortable"
    elif feels_like_c < 30: return "Warm"
    elif feels_like_c < 35: return "Hot"
    elif feels_like_c < 40: return "Very Hot"
    else: return "Dangerous Heat"


def wind_speed_to_beaufort(wind_speed_ms: float) -> int:
    if wind_speed_ms < 0.3: return 0
    elif wind_speed_ms < 1.6: return 1
    elif wind_speed_ms < 3.4: return 2
    elif wind_speed_ms < 5.5: return 3
    elif wind_speed_ms < 8.0: return 4
    elif wind_speed_ms < 10.8: return 5
    elif wind_speed_ms < 13.9: return 6
    elif wind_speed_ms < 17.2: return 7
    elif wind_speed_ms < 20.8: return 8
    elif wind_speed_ms < 24.5: return 9
    elif wind_speed_ms < 28.5: return 10
    elif wind_speed_ms < 32.7: return 11
    else: return 12


def beaufort_description(beaufort: int) -> str:
    descriptions = ["Calm","Light Air","Light Breeze","Gentle Breeze","Moderate Breeze",
                    "Fresh Breeze","Strong Breeze","Near Gale","Gale","Strong Gale",
                    "Storm","Violent Storm","Hurricane"]
    return descriptions[beaufort] if beaufort < 13 else "Hurricane"


def direction_to_cardinal_16(degrees: float) -> str:
    dirs = ["N","NNE","NE","ENE","E","ESE","SE","SSE","S","SSW","SW","WSW","W","WNW","NW","NNW"]
    return dirs[int((degrees + 11.25) / 22.5) % 16]


def direction_to_quadrant(degrees: float) -> str:
    degrees = degrees % 360
    if degrees >= 315 or degrees < 45: return "N"
    elif degrees < 135: return "E"
    elif degrees < 225: return "S"
    else: return "W"


def smooth_wind_direction(current_deg: float, previous_deg: float, alpha: float = 0.3) -> float:
    diff = current_deg - previous_deg
    if diff > 180: diff -= 360
    elif diff < -180: diff += 360
    result = previous_deg + alpha * diff
    if result < 0: result += 360
    elif result >= 360: result -= 360
    return round(result, 1)


def least_squares_pressure_trend(pressure_readings: list, interval_minutes: int = 15) -> float:
    n = len(pressure_readings)
    if n < 2: return 0.0
    sum_x = n * (n - 1) / 2
    sum_x_squared = n * (n - 1) * (2 * n - 1) / 6
    sum_y = sum(pressure_readings)
    sum_xy = sum(i * pressure_readings[i] for i in range(n))
    denominator = (n * sum_x_squared) - (sum_x * sum_x)
    if denominator == 0: return 0.0
    numerator = (n * sum_xy) - (sum_x * sum_y)
    slope_per_interval = numerator / denominator
    intervals_per_3h = 180 / interval_minutes
    return round(slope_per_interval * intervals_per_3h, 2)


def pressure_trend_display(trend_3h: float) -> str:
    if trend_3h >= 1.6: return "Rising Rapidly"
    elif trend_3h >= 0.8: return "Rising"
    elif trend_3h > -0.8: return "Steady"
    elif trend_3h > -1.6: return "Falling"
    else: return "Falling Rapidly"


def pressure_trend_arrow(trend_3h: float) -> str:
    if trend_3h >= 1.6: return "↑↑"
    elif trend_3h >= 0.8: return "↑"
    elif trend_3h > -0.8: return "→"
    elif trend_3h > -1.6: return "↓"
    else: return "↓↓"


def zambretti_forecast(mslp: float, pressure_trend_3h: float, wind_quadrant: str,
                       humidity: float, month: int, hemisphere: str = "Northern",
                       climate: str = "Mediterranean") -> str:
    if hemisphere == "Northern":
        is_summer = 4 <= month <= 9
    else:
        is_summer = month >= 10 or month <= 3
    p_high = 1024 if is_summer else 1020
    p_low = 1010 if is_summer else 1008
    wind_patterns = {
        "Atlantic Europe": {"good": ["E", "N"], "bad": ["W", "S"]},
        "Mediterranean": {"good": ["N", "E"], "bad": ["S", "W"]},
        "Continental Europe": {"good": ["E", "N"], "bad": ["W", "S"]},
        "Scandinavia": {"good": ["E", "N"], "bad": ["S", "W"]},
        "North America East": {"good": ["N", "W"], "bad": ["S", "E"]},
        "North America West": {"good": ["E", "N"], "bad": ["W", "S"]},
        "Australia": {"good": ["S", "E"], "bad": ["N", "W"]},
        "Custom": {"good": ["N", "E"], "bad": ["S", "W"]},
    }
    pattern = wind_patterns.get(climate, wind_patterns["Mediterranean"])
    wind_good = wind_quadrant in pattern["good"]
    wind_bad = wind_quadrant in pattern["bad"]
    rising = pressure_trend_3h > 1.6
    falling = pressure_trend_3h < -1.6
    rapid_fall = pressure_trend_3h < -3.0
    rapid_rise = pressure_trend_3h > 3.0
    if rapid_fall and mslp < p_low: return "Storm likely"
    elif rapid_fall: return "Rain likely soon"
    elif falling and mslp < p_low: return "Rain expected"
    elif falling and mslp < p_high and wind_bad: return "Becoming unsettled"
    elif falling and humidity > 75: return "Clouds increasing"
    elif falling: return "Change coming"
    elif rapid_rise and mslp > p_high: return "Settled fine weather"
    elif rising and mslp > p_high: return "Fair weather continuing"
    elif rising and mslp > p_low and wind_good: return "Fine weather"
    elif rising and mslp > p_low: return "Improving"
    elif rising: return "Clearing"
    elif mslp > p_high and wind_good: return "Fine summer weather" if is_summer else "Fine weather"
    elif mslp > p_high: return "Fair"
    elif mslp < p_low and humidity > 80: return "Unsettled, rain likely"
    elif mslp < p_low: return "Unsettled"
    else: return "No significant change"


def calculate_rain_probability(mslp: float, pressure_trend: float, humidity: float, wind_quadrant: str) -> int:
    prob = 0
    if mslp < 1005: prob += 35
    elif mslp < 1010: prob += 20
    elif mslp < 1015: prob += 10
    if pressure_trend < -3: prob += 40
    elif pressure_trend < -1.6: prob += 25
    elif pressure_trend < -0.8: prob += 15
    elif pressure_trend > 1.6: prob -= 15
    if humidity > 85: prob += 25
    elif humidity > 75: prob += 15
    elif humidity > 65: prob += 5
    elif humidity < 50: prob -= 10
    if wind_quadrant in ["S", "W"]: prob += 10
    elif wind_quadrant == "N": prob -= 10
    return max(0, min(100, prob))


def combine_rain_probability(local_prob: float, api_prob, current_hour: int) -> int:
    if api_prob is None: return round(local_prob)
    local_weight = 0.7 if current_hour < 12 else 0.4
    return round(local_prob * local_weight + api_prob * (1 - local_weight))


def format_rain_display(rain_rate_mmph: float) -> str:
    if rain_rate_mmph > 10: return f"Heavy ({rain_rate_mmph:.1f} mm/h)"
    elif rain_rate_mmph > 2: return f"Moderate ({rain_rate_mmph:.1f} mm/h)"
    elif rain_rate_mmph > 0.5: return f"Light ({rain_rate_mmph:.1f} mm/h)"
    elif rain_rate_mmph > 0: return "Drizzle"
    else: return "Dry"


class KalmanFilter:
    def __init__(self, process_noise=0.01, measurement_noise=0.5, initial_estimate=0.0, initial_error_variance=0.5):
        self.process_noise = process_noise
        self.measurement_noise = measurement_noise
        self.estimate = initial_estimate
        self.error_variance = initial_error_variance

    def update(self, measurement: float) -> float:
        predicted_error_var = self.error_variance + self.process_noise
        kalman_gain = predicted_error_var / (predicted_error_var + self.measurement_noise)
        self.estimate = self.estimate + kalman_gain * (measurement - self.estimate)
        self.error_variance = (1 - kalman_gain) * predicted_error_var
        return max(0.0, round(self.estimate, 1))

    def filter_quality(self) -> str:
        if self.error_variance < 0.1: return "excellent"
        elif self.error_variance < 0.3: return "good"
        elif self.error_variance < 0.6: return "fair"
        else: return "uncertain"


def determine_current_condition(temp_c, humidity, wind_speed_ms, wind_gust_ms, rain_rate_mmph,
                                 dew_point_c, illuminance_lx, uv_index, zambretti,
                                 pressure_trend, sun_elevation, sun_azimuth, is_day,
                                 pm10=0.0, is_wet=False) -> str:
    is_rising = sun_azimuth < 180
    is_golden_hour = -4 < sun_elevation < 10 and is_day
    is_sunrise = is_golden_hour and is_rising
    is_sunset = is_golden_hour and not is_rising
    if wind_gust_ms > 32 or "Hurricane" in zambretti: return "hurricane"
    elif wind_gust_ms > 25 and pressure_trend < -3: return "severe-storm"
    elif "Storm" in zambretti and rain_rate_mmph > 10: return "thunderstorm"
    elif "Storm" in zambretti or (rain_rate_mmph > 5 and wind_gust_ms > 15): return "pre-storm"
    elif temp_c < 2 and (rain_rate_mmph > 0 or is_wet) and humidity > 85: return "sleet"
    elif temp_c < 0 and (rain_rate_mmph > 0 or is_wet):
        return "snow-accumulation" if (wind_speed_ms > 8 and rain_rate_mmph > 2) else "snowy"
    elif rain_rate_mmph > 10: return "heavy-rain"
    elif rain_rate_mmph > 2 or (is_wet and rain_rate_mmph > 0.5): return "rainy"
    elif rain_rate_mmph > 0 or is_wet: return "drizzle"
    elif temp_c < -5 and wind_speed_ms > 10: return "icy-conditions"
    elif humidity > 95 and (temp_c - dew_point_c) < 1 and wind_speed_ms < 1.5:
        now_h = datetime.now().hour
        return "misty-morning" if (is_sunrise or 5 <= now_h < 9) else "fog"
    elif pm10 > 150 and illuminance_lx < 50000: return "sandstorm"
    elif pm10 > 80: return "african-dust"
    elif wind_gust_ms > 17.2: return "windy" if is_day else "windy-night"
    elif temp_c >= 38: return "hot"
    elif temp_c < -10 and not is_day: return "cold"
    elif is_sunrise: return "sunrise"
    elif is_sunset: return "sunset"
    elif is_golden_hour: return "golden-hour"
    elif not is_wet and rain_rate_mmph == 0 and humidity > 80 and illuminance_lx > 30000: return "clearing-after-rain"
    elif not is_day:
        return "clear-night" if humidity < 50 and illuminance_lx < 100 else "overcast-night"
    elif illuminance_lx < 5000: return "overcast"
    elif illuminance_lx < 20000: return "cloudy"
    elif illuminance_lx < 60000: return "partly-cloudy"
    else: return "sunny"


CONDITION_DESCRIPTIONS = {
    "hurricane": "Hurricane conditions - seek shelter", "severe-storm": "Severe storm - dangerous winds",
    "thunderstorm": "Thunderstorm in progress", "pre-storm": "Storm approaching",
    "heavy-rain": "Heavy rainfall", "rainy": "Rain", "drizzle": "Light drizzle",
    "sleet": "Sleet/freezing rain", "snow-accumulation": "Heavy snowfall", "snowy": "Snow",
    "icy-conditions": "Icy conditions - use caution", "misty-morning": "Misty morning",
    "fog": "Foggy", "sandstorm": "Sandstorm", "african-dust": "Saharan dust event",
    "windy": "Windy", "windy-night": "Windy night", "smoke": "Smoky conditions",
    "hazy-sun": "Hazy sunshine", "hot": "Extreme heat", "cold": "Cold",
    "clearing-after-rain": "Clearing after rain", "clear-night": "Clear night",
    "overcast-night": "Overcast night", "sunrise": "Sunrise", "sunset": "Sunset",
    "golden-hour": "Golden hour", "overcast": "Overcast", "cloudy": "Cloudy",
    "partly-cloudy": "Partly cloudy", "sunny": "Sunny",
}

CONDITION_ICONS = {
    "hurricane": "mdi:weather-hurricane", "severe-storm": "mdi:weather-lightning",
    "thunderstorm": "mdi:weather-lightning-rainy", "pre-storm": "mdi:weather-cloudy-alert",
    "heavy-rain": "mdi:weather-pouring", "rainy": "mdi:weather-rainy",
    "drizzle": "mdi:weather-drizzle", "sleet": "mdi:weather-snowy-rainy",
    "snow-accumulation": "mdi:weather-snowy-heavy", "snowy": "mdi:weather-snowy",
    "icy-conditions": "mdi:snowflake-alert", "misty-morning": "mdi:weather-fog",
    "fog": "mdi:weather-fog", "sandstorm": "mdi:weather-dust", "african-dust": "mdi:weather-dust",
    "windy": "mdi:weather-windy", "windy-night": "mdi:weather-windy",
    "hot": "mdi:thermometer-high", "cold": "mdi:thermometer-low",
    "clearing-after-rain": "mdi:weather-partly-rainy", "clear-night": "mdi:weather-night",
    "overcast-night": "mdi:weather-night-partly-cloudy", "sunrise": "mdi:weather-sunset-up",
    "sunset": "mdi:weather-sunset-down", "golden-hour": "mdi:weather-sunset",
    "overcast": "mdi:weather-cloudy", "cloudy": "mdi:weather-cloudy",
    "partly-cloudy": "mdi:weather-partly-cloudy", "sunny": "mdi:weather-sunny",
}

CONDITION_COLORS = {
    "hurricane": "#DC2626", "severe-storm": "#991B1B", "thunderstorm": "#F87171",
    "pre-storm": "#FB923C", "heavy-rain": "#3B82F6", "rainy": "#60A5FA",
    "drizzle": "#93C5FD", "sleet": "#A5B4FC", "snow-accumulation": "#E0E7FF",
    "snowy": "#F1F5F9", "icy-conditions": "#BFDBFE", "misty-morning": "#D1D5DB",
    "fog": "#9CA3AF", "windy": "#A7F3D0", "hot": "#F97316", "cold": "#7DD3FC",
    "clearing-after-rain": "#86EFAC", "clear-night": "#FEF3C7", "overcast-night": "#374151",
    "sunrise": "#FDBA74", "sunset": "#FB923C", "golden-hour": "#FCD34D",
    "overcast": "#94A3B8", "cloudy": "#CBD5E1", "partly-cloudy": "#E2E8F0", "sunny": "#FBBF24",
}


def get_condition_severity(condition: str) -> str:
    if condition in ["hurricane", "severe-storm"]: return "critical"
    elif condition in ["thunderstorm", "heavy-rain", "icy-conditions"]: return "warning"
    elif condition in ["pre-storm", "sleet", "snow-accumulation", "hot"]: return "advisory"
    else: return "normal"


def humidity_level(humidity: float) -> str:
    if humidity > 80: return "Very Humid"
    elif humidity > 70: return "Humid"
    elif humidity > 60: return "Slightly Humid"
    elif humidity > 40: return "Comfortable"
    elif humidity > 30: return "Slightly Dry"
    elif humidity > 20: return "Dry"
    else: return "Very Dry"


def uv_level(uv_index: float) -> str:
    if uv_index >= 11: return "Extreme"
    elif uv_index >= 8: return "Very High"
    elif uv_index >= 6: return "High"
    elif uv_index >= 3: return "Moderate"
    else: return "Low"


def uv_recommendation(uv_index: float) -> str:
    if uv_index >= 8: return "Avoid sun exposure"
    elif uv_index >= 6: return "Seek shade, wear sunscreen"
    elif uv_index >= 3: return "Sunscreen recommended"
    else: return "No protection needed"


def uv_burn_time_minutes(uv_index: float, skin_type: int = 2) -> int:
    if uv_index <= 0: return 200
    sensitivity = {1: 67, 2: 100, 3: 133, 4: 167, 5: 200, 6: 240}
    factor = sensitivity.get(skin_type, 100)
    return min(round(factor / (uv_index * 3)), 200)


def laundry_drying_score(temp_c, humidity, wind_speed_ms, uv_index, rain_rate_mmph, rain_probability=None) -> int:
    if rain_rate_mmph > 0: return 0
    if rain_probability is not None and rain_probability > 50: return 0
    temp_score = min(30, max(0, round(temp_c / 35 * 30)))
    hum_score = min(30, max(0, round((100 - humidity) / 100 * 30)))
    wind_score = min(20, max(0, round(wind_speed_ms / 5 * 20)))
    sun_score = min(20, max(0, round(uv_index / 10 * 20)))
    return temp_score + hum_score + wind_score + sun_score


def laundry_recommendation(score: int, rain_rate_mmph: float, rain_probability) -> str:
    if rain_rate_mmph > 0: return "Currently raining - hang indoors!"
    if rain_probability is not None and rain_probability > 50: return "Rain expected - hang indoors or wait"
    if score >= 75: return "Excellent conditions! Hang outside now."
    elif score >= 50: return "Good drying weather. Hang outside."
    elif score >= 25: return "Fair conditions. Will dry slowly outside."
    else: return "Poor conditions. Better to use dryer or wait."


def laundry_dry_time(score: int, rain_rate_mmph: float) -> str:
    if rain_rate_mmph > 0: return "N/A (raining)"
    if score >= 75: return "1.5-2.5 hours"
    elif score >= 50: return "2.5-4 hours"
    elif score >= 25: return "4-6 hours"
    else: return "6+ hours (use dryer)"


def running_score(feels_like_c: float, uv_index: float) -> int:
    temp_score = max(0, min(100, 100 - ((feels_like_c - 15) ** 2) / 4))
    uv_score = max(0, min(100, 100 - (uv_index * 10)))
    return round(temp_score * 0.7 + uv_score * 0.3)


def running_level(score: int) -> str:
    if score >= 80: return "Excellent"
    elif score >= 60: return "Good"
    elif score >= 40: return "Fair"
    else: return "Poor"


def running_recommendation(feels_like_c: float, uv_index: float) -> str:
    if feels_like_c < 10: return "Too cold for comfortable running. Dress warmly."
    elif feels_like_c < 15: return "Cool but good running weather. Light layers recommended."
    elif feels_like_c < 22 and uv_index < 5: return "Perfect running conditions!"
    elif feels_like_c < 28 and uv_index < 7: return "Warm but manageable. Stay hydrated."
    elif feels_like_c < 32: return "Hot conditions. Run early morning or evening."
    else: return "Too hot for safe running. Avoid midday."


def fire_weather_index(temp_c: float, humidity: float, wind_speed_ms: float, rain_24h_mm: float) -> float:
    wind_kmh = wind_speed_ms * 3.6
    ffmc_base = 85 + (temp_c - 20) * 2 - (humidity - 50) / 2
    ffmc = max(40, min(100, round(ffmc_base)))
    isi_wind = 0.208 * wind_kmh if wind_kmh < 40 else (12 - (60 / wind_kmh))
    isi = 0.208 * isi_wind * ((ffmc - 40) / 20)
    rain_factor = max(rain_24h_mm + 1, 1)
    drought_factor = 1 + (7 / rain_factor)
    return max(0, min(50, round(isi * drought_factor, 1)))


def fire_danger_level(fwi: float) -> str:
    if fwi < 5: return "Low"
    elif fwi < 12: return "Moderate"
    elif fwi < 24: return "High"
    elif fwi < 38: return "Very High"
    else: return "Extreme"


def stargazing_quality(cloud_cover_pct, humidity: float, rain_rate_mmph: float, moon_phase: str) -> str:
    if rain_rate_mmph > 0: return "Poor (Raining)"
    if cloud_cover_pct is None:
        cloud_cover_pct = 80 if humidity > 90 else (50 if humidity > 70 else 20)
    moon_penalty = 0
    if "full" in moon_phase: moon_penalty = 40
    elif "gibbous" in moon_phase: moon_penalty = 25
    elif "quarter" in moon_phase: moon_penalty = 15
    elif "crescent" in moon_phase: moon_penalty = 5
    base = 90 if cloud_cover_pct < 20 else (60 if cloud_cover_pct < 50 else (30 if cloud_cover_pct < 80 else 10))
    quality_score = max(0, base - moon_penalty)
    if quality_score >= 70: return "Excellent"
    elif quality_score >= 50: return "Good"
    elif quality_score >= 30: return "Fair"
    else: return "Poor"


def calculate_moon_phase(year: int, month: int, day: int) -> str:
    jd = int(365.25 * (year + 4716)) + int(30.6001 * (month + 1)) + day - 1524.5
    d = (jd - 2451550.1) % 29.53058867
    if d < 1.85: return "new_moon"
    elif d < 5.53: return "waxing_crescent"
    elif d < 9.22: return "first_quarter"
    elif d < 12.91: return "waxing_gibbous"
    elif d < 16.61: return "full_moon"
    elif d < 20.30: return "waning_gibbous"
    elif d < 23.99: return "last_quarter"
    elif d < 27.68: return "waning_crescent"
    else: return "new_moon"


MOON_ILLUMINATION = {"new_moon": 0, "waxing_crescent": 25, "first_quarter": 50,
                     "waxing_gibbous": 75, "full_moon": 100, "waning_gibbous": 75,
                     "last_quarter": 50, "waning_crescent": 25}

MOON_ICONS = {"new_moon": "mdi:moon-new", "waxing_crescent": "mdi:moon-waxing-crescent",
              "first_quarter": "mdi:moon-first-quarter", "waxing_gibbous": "mdi:moon-waxing-gibbous",
              "full_moon": "mdi:moon-full", "waning_gibbous": "mdi:moon-waning-gibbous",
              "last_quarter": "mdi:moon-last-quarter", "waning_crescent": "mdi:moon-waning-crescent"}


def moon_stargazing_impact(moon_phase: str) -> str:
    if moon_phase == "new_moon": return "Perfect (No moon interference)"
    elif "crescent" in moon_phase: return "Excellent (Minimal interference)"
    elif "quarter" in moon_phase: return "Good (Moderate moon)"
    elif "gibbous" in moon_phase: return "Fair (Bright moon)"
    elif moon_phase == "full_moon": return "Poor (Full moon washes out stars)"
    else: return "Unknown"
