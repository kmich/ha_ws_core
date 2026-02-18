"""Meteorological algorithms for Weather Station Core.

All algorithms are documented with source references, input ranges,
and typical error bounds. Ported from the original ws_station YAML
package (v1.0.0) by Konstantinos, with corrections and additions.

References:
  - Alduchov & Eskridge 1996: Magnus-form dew point constants
  - Buck 1981: Frost point (saturation over ice)
  - Stull 2011: Wet-bulb temperature approximation
  - Steadman 1994 / BOM: Apparent temperature
  - Negretti & Zambra / Zambretti: Barometric forecaster
  - WMO No. 8, No. 306: Pressure tendency, Beaufort scale
  - Van Wagner 1987: Fire weather index structure (simplified)
"""

from __future__ import annotations

import contextlib
import math
from datetime import datetime

# ---------------------------------------------------------------------------
# Moon phase UI helpers
# ---------------------------------------------------------------------------

MOON_ICONS = {
    "new_moon": "mdi:moon-new",
    "waxing_crescent": "mdi:moon-waxing-crescent",
    "first_quarter": "mdi:moon-first-quarter",
    "waxing_gibbous": "mdi:moon-waxing-gibbous",
    "full_moon": "mdi:moon-full",
    "waning_gibbous": "mdi:moon-waning-gibbous",
    "last_quarter": "mdi:moon-last-quarter",
    "waning_crescent": "mdi:moon-waning-crescent",
}

MOON_ILLUMINATION = {
    "new_moon": 0,
    "waxing_crescent": 25,
    "first_quarter": 50,
    "waxing_gibbous": 75,
    "full_moon": 100,
    "waning_gibbous": 75,
    "last_quarter": 50,
    "waning_crescent": 25,
}


# ---------------------------------------------------------------------------
# Dew point, frost point, wet-bulb
# ---------------------------------------------------------------------------


def calculate_dew_point(temp_c: float, humidity: float) -> float:
    """Magnus-formula dew point (Alduchov & Eskridge 1996).

    Uses temperature-dependent constants:
      Over water (T >= 0): a=17.625, b=243.04
      Over ice   (T <  0): a=22.587, b=273.86 (Buck 1981)

    Valid range: -45 C to +60 C, 1%-100% RH.
    Max error < 0.1 C across valid range (over water).
    """
    if temp_c >= 0:
        a, b = 17.625, 243.04
    else:
        a, b = 22.587, 273.86
    rh_clamped = max(1.0, min(100.0, humidity))
    gamma = (a * temp_c) / (b + temp_c) + math.log(rh_clamped / 100.0)
    return round((b * gamma) / (a - gamma), 2)


def calculate_frost_point(temp_c: float, humidity: float) -> float:
    """Frost point using Magnus formula with ice constants (Buck 1981).

    The frost point is the temperature at which air becomes saturated
    with respect to ice. Only physically meaningful below 0 C.
    Above 0 C, returns the standard dew point.

    Constants: a=22.587, b=273.86 (saturation over ice).
    """
    if temp_c >= 0:
        return calculate_dew_point(temp_c, humidity)
    a, b = 22.587, 273.86
    rh_clamped = max(1.0, min(100.0, humidity))
    gamma = (a * temp_c) / (b + temp_c) + math.log(rh_clamped / 100.0)
    return round((b * gamma) / (a - gamma), 2)


def calculate_wet_bulb(temp_c: float, humidity: float) -> float:
    """Wet-bulb temperature approximation (Stull 2011).

    Formula: Tw = T * atan(0.151977 * (RH + 8.313659)^0.5)
             + atan(T + RH) - atan(RH - 1.676331)
             + 0.00391838 * RH^1.5 * atan(0.023101 * RH)
             - 4.686035

    Source: Stull, R. (2011). "Wet-Bulb Temperature from Relative
    Humidity and Air Temperature." J. Appl. Meteor. Climatol., 50,
    2267-2269.

    Valid range: RH 5%-99%, T -20 C to +50 C.
    Max error: +/- 0.3 C within valid range.
    """
    rh = max(5.0, min(99.0, humidity))
    tw = (
        temp_c * math.atan(0.151977 * (rh + 8.313659) ** 0.5)
        + math.atan(temp_c + rh)
        - math.atan(rh - 1.676331)
        + 0.00391838 * rh**1.5 * math.atan(0.023101 * rh)
        - 4.686035
    )
    return round(tw, 2)


# ---------------------------------------------------------------------------
# Sea-level pressure
# ---------------------------------------------------------------------------


def calculate_sea_level_pressure(station_pressure_hpa: float, elevation_m: float, temp_c: float) -> float:
    """Reduce station pressure to mean sea level (MSLP).

    Method: Temperature-corrected hypsometric reduction (WMO No. 8, S3.1.3).
    Formula: MSLP = P_stn * exp(elevation / (T_K * 29.263))

    Accuracy: +/-0.3 hPa below 500 m, +/-1 hPa at 2000 m.
    Limitation: Uses current temperature only; WMO recommends 12h mean
    temperature for better accuracy at high elevations.
    """
    temp_k = temp_c + 273.15
    if temp_k < 1.0:
        temp_k = 1.0  # guard against division by zero
    exponent = elevation_m / (temp_k * 29.263)
    return round(station_pressure_hpa * math.exp(exponent), 1)


# ---------------------------------------------------------------------------
# Apparent / feels-like temperature
# ---------------------------------------------------------------------------


def calculate_apparent_temperature(temp_c: float, humidity: float, wind_speed_ms: float) -> float:
    """Australian Bureau of Meteorology Apparent Temperature.

    Formula: AT = Ta + 0.33*e - 0.70*ws - 4.0
    where e = vapour pressure (hPa), ws = wind speed (m/s).

    Source: Steadman 1994 / BOM operational formula.
    Valid for any temperature range (unlike NWS wind chill/heat index
    which have validity bounds).
    """
    vp = (humidity / 100.0) * 6.105 * math.exp((17.27 * temp_c) / (237.7 + temp_c))
    at = temp_c + (0.33 * vp) - (0.70 * wind_speed_ms) - 4.0
    return round(at, 1)


def feels_like_comfort_level(feels_like_c: float) -> str:
    """Comfort category from apparent temperature."""
    if feels_like_c < -10:
        return "Dangerous Cold"
    if feels_like_c < 0:
        return "Freezing"
    if feels_like_c < 10:
        return "Very Cold"
    if feels_like_c < 15:
        return "Cold"
    if feels_like_c < 20:
        return "Cool"
    if feels_like_c < 25:
        return "Comfortable"
    if feels_like_c < 30:
        return "Warm"
    if feels_like_c < 35:
        return "Hot"
    if feels_like_c < 40:
        return "Very Hot"
    return "Dangerous Heat"


# ---------------------------------------------------------------------------
# Beaufort scale
# ---------------------------------------------------------------------------


def wind_speed_to_beaufort(wind_speed_ms: float) -> int:
    """Convert wind speed (m/s) to Beaufort number (WMO No. 8)."""
    boundaries = [0.3, 1.6, 3.4, 5.5, 8.0, 10.8, 13.9, 17.2, 20.8, 24.5, 28.5, 32.7]
    for i, b in enumerate(boundaries):
        if wind_speed_ms < b:
            return i
    return 12


def beaufort_description(beaufort: int) -> str:
    """WMO Beaufort scale description."""
    descriptions = [
        "Calm",
        "Light Air",
        "Light Breeze",
        "Gentle Breeze",
        "Moderate Breeze",
        "Fresh Breeze",
        "Strong Breeze",
        "Near Gale",
        "Gale",
        "Strong Gale",
        "Storm",
        "Violent Storm",
        "Hurricane",
    ]
    return descriptions[min(beaufort, 12)]


# ---------------------------------------------------------------------------
# Wind direction
# ---------------------------------------------------------------------------


def direction_to_cardinal_16(degrees: float) -> str:
    """Convert degrees to 16-point compass direction."""
    dirs = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    return dirs[int((degrees + 11.25) / 22.5) % 16]


def direction_to_quadrant(degrees: float) -> str:
    """Convert degrees to 4-point quadrant (N/E/S/W)."""
    d = degrees % 360
    if d >= 315 or d < 45:
        return "N"
    if d < 135:
        return "E"
    if d < 225:
        return "S"
    return "W"


def smooth_wind_direction(current_deg: float, previous_deg: float, alpha: float = 0.3) -> float:
    """Circular exponential smoothing for wind direction."""
    diff = current_deg - previous_deg
    if diff > 180:
        diff -= 360
    elif diff < -180:
        diff += 360
    result = previous_deg + alpha * diff
    if result < 0:
        result += 360
    elif result >= 360:
        result -= 360
    return round(result, 1)


# ---------------------------------------------------------------------------
# Pressure trend
# ---------------------------------------------------------------------------


def least_squares_pressure_trend(pressure_readings: list, interval_minutes: int = 15) -> float:
    """Least-squares linear trend over pressure history, extrapolated to 3h."""
    n = len(pressure_readings)
    if n < 2:
        return 0.0
    sum_x = n * (n - 1) / 2
    sum_x2 = n * (n - 1) * (2 * n - 1) / 6
    sum_y = sum(pressure_readings)
    sum_xy = sum(i * pressure_readings[i] for i in range(n))
    denom = (n * sum_x2) - (sum_x * sum_x)
    if denom == 0:
        return 0.0
    slope = ((n * sum_xy) - (sum_x * sum_y)) / denom
    intervals_per_3h = 180 / interval_minutes
    return round(slope * intervals_per_3h, 2)


def pressure_trend_display(trend_3h: float) -> str:
    """Classify 3-hour pressure tendency (WMO No. 306, Table 4680)."""
    if trend_3h >= 1.6:
        return "Rising Rapidly"
    if trend_3h >= 0.8:
        return "Rising"
    if trend_3h > -0.8:
        return "Steady"
    if trend_3h > -1.6:
        return "Falling"
    return "Falling Rapidly"


def pressure_trend_arrow(trend_3h: float) -> str:
    """Arrow symbol for pressure tendency."""
    if trend_3h >= 1.6:
        return "\u2191\u2191"
    if trend_3h >= 0.8:
        return "\u2191"
    if trend_3h > -0.8:
        return "\u2192"
    if trend_3h > -1.6:
        return "\u2193"
    return "\u2193\u2193"


# ---------------------------------------------------------------------------
# Zambretti Forecaster (real Negretti & Zambra lookup table)
# ---------------------------------------------------------------------------

# The 26 Zambretti forecast texts (Z-number 1-26, indices 0-25).
# Original Negretti & Zambra patent, public domain.
ZAMBRETTI_TEXTS = [
    "Settled fine",  # Z=1
    "Fine weather",  # Z=2
    "Becoming fine",  # Z=3
    "Fine, becoming less settled",  # Z=4
    "Fine, possible showers",  # Z=5
    "Fairly fine, improving",  # Z=6
    "Fairly fine, possible showers early",  # Z=7
    "Fairly fine, showery later",  # Z=8
    "Showery early, improving",  # Z=9
    "Changeable, mending",  # Z=10
    "Fairly fine, possible showers",  # Z=11
    "Rather unsettled clearing later",  # Z=12
    "Unsettled, probably improving",  # Z=13
    "Showery, bright intervals",  # Z=14
    "Showery, becoming rather unsettled",  # Z=15
    "Changeable, some rain",  # Z=16
    "Unsettled, short fine intervals",  # Z=17
    "Unsettled, rain later",  # Z=18
    "Unsettled, some rain",  # Z=19
    "Mostly very unsettled",  # Z=20
    "Occasional rain, worsening",  # Z=21
    "Rain at times, very unsettled",  # Z=22
    "Rain at frequent intervals",  # Z=23
    "Rain, very unsettled",  # Z=24
    "Stormy, may improve",  # Z=25
    "Stormy, much rain",  # Z=26
]


def zambretti_forecast(
    mslp: float,
    pressure_trend_3h: float,
    wind_quadrant: str,
    humidity: float,
    month: int,
    hemisphere: str = "Northern",
    climate: str = "Mediterranean",
) -> tuple[str, int]:
    """Zambretti barometric forecaster using the real N&Z lookup method.

    The algorithm maps MSLP to a Z-number (1-26) on a linear scale from
    950-1050 hPa, then applies corrections for:
      - Pressure trend (rising/falling shifts the Z-number)
      - Wind direction (regional patterns shift the Z-number)
      - Season (summer vs winter adjustment)

    Returns: (forecast_text, z_number)

    Source: Negretti & Zambra (1915), as documented in:
      - "Weather Forecasting Using a Barometer" by R.N. Denham
      - Various open-source implementations (pywws, Cumulus)

    Accuracy: ~65-75% for 6-12h forecasts in maritime/Mediterranean
    climates. Less reliable in continental interiors and tropics.
    """
    # Clamp MSLP to scale range
    p = max(950.0, min(1050.0, mslp))

    # Base Z-number: linear map from pressure (high P = low Z = fair)
    # Z ranges 1-26. At 1050 hPa -> Z~1, at 950 hPa -> Z~26
    z_base = 26.0 - ((p - 950.0) / 100.0) * 25.0

    # Seasonal adjustment
    is_winter = (month <= 3 or month >= 10) if hemisphere == "Northern" else (4 <= month <= 9)
    season_adj = 1.0 if is_winter else -1.0

    # Pressure trend adjustment (the core Zambretti insight)
    if pressure_trend_3h > 1.6:
        trend_adj = -4.0  # rapidly rising = much better weather
    elif pressure_trend_3h > 0.8:
        trend_adj = -2.0
    elif pressure_trend_3h > 0.1:
        trend_adj = -1.0
    elif pressure_trend_3h < -1.6:
        trend_adj = 4.0  # rapidly falling = much worse weather
    elif pressure_trend_3h < -0.8:
        trend_adj = 2.0
    elif pressure_trend_3h < -0.1:
        trend_adj = 1.0
    else:
        trend_adj = 0.0

    # Wind direction adjustment (climate-region-aware)
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
    if wind_quadrant in pattern["good"]:
        wind_adj = -1.0
    elif wind_quadrant in pattern["bad"]:
        wind_adj = 1.0
    else:
        wind_adj = 0.0

    # Humidity adjustment (high humidity biases toward unsettled)
    if humidity > 85:
        hum_adj = 1.0
    elif humidity < 40:
        hum_adj = -0.5
    else:
        hum_adj = 0.0

    # Combine
    z_final = z_base + trend_adj + wind_adj + season_adj + hum_adj
    z_number = max(1, min(26, round(z_final)))
    forecast_text = ZAMBRETTI_TEXTS[z_number - 1]
    return forecast_text, z_number


# ---------------------------------------------------------------------------
# Rain probability (climate-region-aware)
# ---------------------------------------------------------------------------

# Regional pressure thresholds for rain likelihood
_RAIN_PRESSURE_PROFILES = {
    "Atlantic Europe": {"low": 1005, "med": 1012, "high": 1020},
    "Mediterranean": {"low": 1008, "med": 1015, "high": 1022},
    "Continental Europe": {"low": 1005, "med": 1013, "high": 1020},
    "Scandinavia": {"low": 1000, "med": 1010, "high": 1018},
    "North America East": {"low": 1005, "med": 1013, "high": 1020},
    "North America West": {"low": 1008, "med": 1015, "high": 1022},
    "Australia": {"low": 1005, "med": 1013, "high": 1020},
    "Custom": {"low": 1005, "med": 1013, "high": 1020},
}

_RAIN_WIND_BIAS = {
    "Atlantic Europe": {"wet": ["W", "S"], "dry": ["E", "N"]},
    "Mediterranean": {"wet": ["S", "W"], "dry": ["N", "E"]},
    "Continental Europe": {"wet": ["W", "S"], "dry": ["E", "N"]},
    "Scandinavia": {"wet": ["S", "W"], "dry": ["N", "E"]},
    "North America East": {"wet": ["S", "E"], "dry": ["N", "W"]},
    "North America West": {"wet": ["W", "S"], "dry": ["E", "N"]},
    "Australia": {"wet": ["N", "W"], "dry": ["S", "E"]},
    "Custom": {"wet": ["S", "W"], "dry": ["N", "E"]},
}


def calculate_rain_probability(
    mslp: float,
    pressure_trend: float,
    humidity: float,
    wind_quadrant: str,
    climate_region: str = "Mediterranean",
) -> int:
    """Heuristic rain probability estimate from local sensor data.

    Uses climate-region-specific pressure thresholds and wind direction
    biases. This is NOT a calibrated probability; treat as an index
    (0-100) indicating relative likelihood of precipitation.

    Disclaimer: Accuracy depends on sensor quality, local topography,
    and climate patterns. Not suitable as a sole forecast source.
    """
    profile = _RAIN_PRESSURE_PROFILES.get(climate_region, _RAIN_PRESSURE_PROFILES["Custom"])
    wind_bias = _RAIN_WIND_BIAS.get(climate_region, _RAIN_WIND_BIAS["Custom"])

    prob = 0

    # Pressure contribution
    if mslp < profile["low"]:
        prob += 35
    elif mslp < profile["med"]:
        prob += 20
    elif mslp < profile["high"]:
        prob += 10

    # Pressure trend contribution
    if pressure_trend < -3:
        prob += 40
    elif pressure_trend < -1.6:
        prob += 25
    elif pressure_trend < -0.8:
        prob += 15
    elif pressure_trend > 1.6:
        prob -= 15

    # Humidity contribution
    if humidity > 85:
        prob += 25
    elif humidity > 75:
        prob += 15
    elif humidity > 65:
        prob += 5
    elif humidity < 50:
        prob -= 10

    # Wind direction (region-specific)
    if wind_quadrant in wind_bias["wet"]:
        prob += 10
    elif wind_quadrant in wind_bias["dry"]:
        prob -= 10

    return max(0, min(100, prob))


def combine_rain_probability(local_prob: float, api_prob, current_hour: int) -> int:
    """Blend local sensor-based probability with API forecast probability.

    Weighting logic: local sensors are most valuable for nowcast (0-3h),
    while NWP model output (API) is better for 6-12h outlook.
    - Hours 6-18 (daytime, convective): local weight 0.5
    - Hours 0-6, 18-24 (stable, frontal): local weight 0.3
    This reflects that local sensors catch convective buildup well
    but frontal systems are better captured by NWP models.
    """
    if api_prob is None:
        return round(local_prob)
    # Daytime convective hours -> trust local sensors more
    local_weight = 0.5 if 6 <= current_hour <= 18 else 0.3
    return round(local_prob * local_weight + float(api_prob) * (1 - local_weight))


def format_rain_display(rain_rate_mmph: float) -> str:
    """Human-readable rain intensity description."""
    if rain_rate_mmph > 10:
        return f"Heavy ({rain_rate_mmph:.1f} mm/h)"
    if rain_rate_mmph > 2:
        return f"Moderate ({rain_rate_mmph:.1f} mm/h)"
    if rain_rate_mmph > 0.5:
        return f"Light ({rain_rate_mmph:.1f} mm/h)"
    if rain_rate_mmph > 0:
        return "Drizzle"
    return "Dry"


# ---------------------------------------------------------------------------
# Kalman filter for rain rate smoothing
# ---------------------------------------------------------------------------


class KalmanFilter:
    """Simple 1D Kalman filter for rain rate de-noising."""

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
        if self.error_variance < 0.1:
            return "excellent"
        if self.error_variance < 0.3:
            return "good"
        if self.error_variance < 0.6:
            return "fair"
        return "uncertain"


# ---------------------------------------------------------------------------
# Current condition classifier (36 conditions)
# ---------------------------------------------------------------------------


def determine_current_condition(
    temp_c,
    humidity,
    wind_speed_ms,
    wind_gust_ms,
    rain_rate_mmph,
    dew_point_c,
    illuminance_lx,
    uv_index,
    zambretti,
    pressure_trend,
    sun_elevation,
    sun_azimuth,
    is_day,
    pm10=0.0,
    is_wet=False,
) -> str:
    """Classify current weather into one of 36 conditions.

    Priority order: severe > precipitation > temperature extremes >
    visibility > wind > astronomical > cloud cover.

    Limitation: Uses raw illuminance as cloud proxy without solar-angle
    normalization. Cloud cover estimates are approximate -- accuracy
    improves with higher sun elevation angles.
    """
    is_rising = sun_azimuth < 180
    is_golden_hour = -4 < sun_elevation < 10 and is_day
    is_sunrise = is_golden_hour and is_rising
    is_sunset = is_golden_hour and not is_rising

    # Severe weather (highest priority)
    if wind_gust_ms > 32 or "Hurricane" in str(zambretti):
        return "hurricane"
    if wind_gust_ms > 25 and pressure_trend < -3:
        return "severe-storm"
    if "Storm" in str(zambretti) and rain_rate_mmph > 10:
        return "thunderstorm"
    if "Storm" in str(zambretti) or (rain_rate_mmph > 5 and wind_gust_ms > 15):
        return "pre-storm"

    # Frozen precipitation
    if temp_c < 0 and (rain_rate_mmph > 0 or is_wet):
        if wind_speed_ms > 8 and rain_rate_mmph > 2:
            return "snow-accumulation"
        return "snowy"
    if 0 <= temp_c < 2 and (rain_rate_mmph > 0 or is_wet) and humidity > 85:
        return "sleet"

    # Liquid precipitation
    if rain_rate_mmph > 10:
        return "heavy-rain"
    if rain_rate_mmph > 2 or (is_wet and rain_rate_mmph > 0.5):
        return "rainy"
    if rain_rate_mmph > 0 or is_wet:
        return "drizzle"

    # Temperature extremes & ice
    if temp_c < -5 and wind_speed_ms > 10:
        return "icy-conditions"

    # Visibility
    if humidity > 95 and (temp_c - (dew_point_c or temp_c)) < 1 and wind_speed_ms < 1.5:
        now_h = datetime.now().hour
        return "misty-morning" if (is_sunrise or 5 <= now_h < 9) else "fog"

    # Air quality
    if pm10 > 150 and illuminance_lx < 50000:
        return "sandstorm"
    if pm10 > 80:
        return "african-dust"

    # Wind
    if wind_gust_ms > 17.2:
        return "windy" if is_day else "windy-night"

    # Temperature extremes
    if temp_c >= 38:
        return "hot"
    if temp_c < -10 and not is_day:
        return "cold"

    # Astronomical
    if is_sunrise:
        return "sunrise"
    if is_sunset:
        return "sunset"
    if is_golden_hour:
        return "golden-hour"

    # Post-rain
    if not is_wet and rain_rate_mmph == 0 and humidity > 80 and illuminance_lx > 30000:
        return "clearing-after-rain"

    # Night
    if not is_day:
        return "clear-night" if humidity < 50 and illuminance_lx < 100 else "overcast-night"

    # Cloud cover from illuminance (approximate, no solar-angle correction)
    if illuminance_lx < 5000:
        return "overcast"
    if illuminance_lx < 20000:
        return "cloudy"
    if illuminance_lx < 60000:
        return "partly-cloudy"
    return "sunny"


CONDITION_DESCRIPTIONS = {
    "hurricane": "Hurricane conditions - seek shelter",
    "severe-storm": "Severe storm - dangerous winds",
    "thunderstorm": "Thunderstorm in progress",
    "pre-storm": "Storm approaching",
    "heavy-rain": "Heavy rainfall",
    "rainy": "Rain",
    "drizzle": "Light drizzle",
    "sleet": "Sleet/freezing rain",
    "snow-accumulation": "Heavy snowfall",
    "snowy": "Snow",
    "icy-conditions": "Icy conditions - use caution",
    "misty-morning": "Misty morning",
    "fog": "Foggy",
    "sandstorm": "Sandstorm",
    "african-dust": "Saharan dust event",
    "windy": "Windy",
    "windy-night": "Windy night",
    "smoke": "Smoky conditions",
    "hazy-sun": "Hazy sunshine",
    "hot": "Extreme heat",
    "cold": "Cold",
    "clearing-after-rain": "Clearing after rain",
    "clear-night": "Clear night",
    "overcast-night": "Overcast night",
    "sunrise": "Sunrise",
    "sunset": "Sunset",
    "golden-hour": "Golden hour",
    "overcast": "Overcast",
    "cloudy": "Cloudy",
    "partly-cloudy": "Partly cloudy",
    "sunny": "Sunny",
}

CONDITION_ICONS = {
    "hurricane": "mdi:weather-hurricane",
    "severe-storm": "mdi:weather-lightning",
    "thunderstorm": "mdi:weather-lightning-rainy",
    "pre-storm": "mdi:weather-cloudy-alert",
    "heavy-rain": "mdi:weather-pouring",
    "rainy": "mdi:weather-rainy",
    "drizzle": "mdi:weather-drizzle",
    "sleet": "mdi:weather-snowy-rainy",
    "snow-accumulation": "mdi:weather-snowy-heavy",
    "snowy": "mdi:weather-snowy",
    "icy-conditions": "mdi:snowflake-alert",
    "misty-morning": "mdi:weather-fog",
    "fog": "mdi:weather-fog",
    "sandstorm": "mdi:weather-dust",
    "african-dust": "mdi:weather-dust",
    "windy": "mdi:weather-windy",
    "windy-night": "mdi:weather-windy",
    "hot": "mdi:thermometer-high",
    "cold": "mdi:thermometer-low",
    "clearing-after-rain": "mdi:weather-partly-rainy",
    "clear-night": "mdi:weather-night",
    "overcast-night": "mdi:weather-night-partly-cloudy",
    "sunrise": "mdi:weather-sunset-up",
    "sunset": "mdi:weather-sunset-down",
    "golden-hour": "mdi:weather-sunset",
    "overcast": "mdi:weather-cloudy",
    "cloudy": "mdi:weather-cloudy",
    "partly-cloudy": "mdi:weather-partly-cloudy",
    "sunny": "mdi:weather-sunny",
}

CONDITION_COLORS = {
    "hurricane": "#DC2626",
    "severe-storm": "#991B1B",
    "thunderstorm": "#F87171",
    "pre-storm": "#FB923C",
    "heavy-rain": "#3B82F6",
    "rainy": "#60A5FA",
    "drizzle": "#93C5FD",
    "sleet": "#A5B4FC",
    "snow-accumulation": "#E0E7FF",
    "snowy": "#F1F5F9",
    "icy-conditions": "#BFDBFE",
    "misty-morning": "#D1D5DB",
    "fog": "#9CA3AF",
    "windy": "#A7F3D0",
    "hot": "#F97316",
    "cold": "#7DD3FC",
    "clearing-after-rain": "#86EFAC",
    "clear-night": "#FEF3C7",
    "overcast-night": "#374151",
    "sunrise": "#FDBA74",
    "sunset": "#FB923C",
    "golden-hour": "#FCD34D",
    "overcast": "#94A3B8",
    "cloudy": "#CBD5E1",
    "partly-cloudy": "#E2E8F0",
    "sunny": "#FBBF24",
}


def get_condition_severity(condition: str) -> str:
    """Return severity level for a weather condition."""
    if condition in ("hurricane", "severe-storm"):
        return "critical"
    if condition in ("thunderstorm", "heavy-rain", "icy-conditions"):
        return "warning"
    if condition in ("pre-storm", "sleet", "snow-accumulation", "hot"):
        return "advisory"
    return "normal"


# ---------------------------------------------------------------------------
# Humidity / UV helpers
# ---------------------------------------------------------------------------


def humidity_level(humidity: float) -> str:
    if humidity > 80:
        return "Very Humid"
    if humidity > 70:
        return "Humid"
    if humidity > 60:
        return "Slightly Humid"
    if humidity > 40:
        return "Comfortable"
    if humidity > 30:
        return "Slightly Dry"
    if humidity > 20:
        return "Dry"
    return "Very Dry"


def uv_level(uv_index: float) -> str:
    if uv_index >= 11:
        return "Extreme"
    if uv_index >= 8:
        return "Very High"
    if uv_index >= 6:
        return "High"
    if uv_index >= 3:
        return "Moderate"
    return "Low"


def uv_recommendation(uv_index: float) -> str:
    if uv_index >= 8:
        return "Avoid sun exposure"
    if uv_index >= 6:
        return "Seek shade, wear sunscreen"
    if uv_index >= 3:
        return "Sunscreen recommended"
    return "No protection needed"


def uv_burn_time_minutes(uv_index: float, skin_type: int = 2) -> int:
    if uv_index <= 0:
        return 200
    sensitivity = {1: 67, 2: 100, 3: 133, 4: 167, 5: 200, 6: 240}
    factor = sensitivity.get(skin_type, 100)
    return min(round(factor / (uv_index * 3)), 200)


# ---------------------------------------------------------------------------
# Activity scores
# ---------------------------------------------------------------------------


def laundry_drying_score(temp_c, humidity, wind_speed_ms, uv_index, rain_rate_mmph, rain_probability=None) -> int:
    """Composite drying score (0-100). Higher = better drying conditions."""
    if rain_rate_mmph > 0:
        return 0
    if rain_probability is not None and rain_probability > 50:
        return 0
    temp_score = min(30, max(0, round(temp_c / 35 * 30)))
    hum_score = min(30, max(0, round((100 - humidity) / 100 * 30)))
    wind_score = min(20, max(0, round(wind_speed_ms / 5 * 20)))
    sun_score = min(20, max(0, round(uv_index / 10 * 20)))
    return temp_score + hum_score + wind_score + sun_score


def laundry_recommendation(score: int, rain_rate_mmph: float, rain_probability) -> str:
    if rain_rate_mmph > 0:
        return "Currently raining - hang indoors!"
    if rain_probability is not None and rain_probability > 50:
        return "Rain expected - hang indoors or wait"
    if score >= 75:
        return "Excellent conditions! Hang outside now."
    if score >= 50:
        return "Good drying weather. Hang outside."
    if score >= 25:
        return "Fair conditions. Will dry slowly outside."
    return "Poor conditions. Better to use dryer or wait."


def laundry_dry_time(score: int, rain_rate_mmph: float) -> str:
    if rain_rate_mmph > 0:
        return "N/A (raining)"
    if score >= 75:
        return "1.5-2.5 hours"
    if score >= 50:
        return "2.5-4 hours"
    if score >= 25:
        return "4-6 hours"
    return "6+ hours (use dryer)"


def running_score(feels_like_c: float, uv_index: float) -> int:
    """Running conditions score (0-100)."""
    temp_score = max(0, min(100, 100 - ((feels_like_c - 15) ** 2) / 4))
    uv_score = max(0, min(100, 100 - (uv_index * 10)))
    return round(temp_score * 0.7 + uv_score * 0.3)


def running_level(score: int) -> str:
    if score >= 80:
        return "Excellent"
    if score >= 60:
        return "Good"
    if score >= 40:
        return "Fair"
    return "Poor"


def running_recommendation(feels_like_c: float, uv_index: float) -> str:
    if feels_like_c < 10:
        return "Too cold for comfortable running. Dress warmly."
    if feels_like_c < 15:
        return "Cool but good running weather. Light layers recommended."
    if feels_like_c < 22 and uv_index < 5:
        return "Perfect running conditions!"
    if feels_like_c < 28 and uv_index < 7:
        return "Warm but manageable. Stay hydrated."
    if feels_like_c < 32:
        return "Hot conditions. Run early morning or evening."
    return "Too hot for safe running. Avoid midday."


def fire_risk_score(temp_c: float, humidity: float, wind_speed_ms: float, rain_24h_mm: float) -> float:
    """Simplified fire risk heuristic (0-50 scale).

    IMPORTANT: This is a simplified heuristic inspired by the structure
    of the Canadian FWI (Van Wagner 1987) but does NOT implement the
    full FWI system, which requires daily-accumulated moisture codes
    (FFMC, DMC, DC). Not suitable for operational fire weather decisions.
    Consult official fire services for fire danger ratings.

    Inputs: current temperature, humidity, wind speed, 24h rainfall.
    Higher values = higher fire risk.
    """
    wind_kmh = wind_speed_ms * 3.6
    ffmc_approx = 85 + (temp_c - 20) * 2 - (humidity - 50) / 2
    ffmc_approx = max(40, min(100, round(ffmc_approx)))
    isi_wind = 0.208 * wind_kmh if wind_kmh < 40 else (12 - (60 / wind_kmh))
    isi = 0.208 * isi_wind * ((ffmc_approx - 40) / 20)
    rain_factor = max(rain_24h_mm + 1, 1)
    drought_factor = 1 + (7 / rain_factor)
    return max(0, min(50, round(isi * drought_factor, 1)))


def fire_danger_level(score: float) -> str:
    if score < 5:
        return "Low"
    if score < 12:
        return "Moderate"
    if score < 24:
        return "High"
    if score < 38:
        return "Very High"
    return "Extreme"


# ---------------------------------------------------------------------------
# Stargazing
# ---------------------------------------------------------------------------


def stargazing_quality(cloud_cover_pct, humidity: float, rain_rate_mmph: float, moon_phase: str) -> str:
    if rain_rate_mmph > 0:
        return "Poor (Raining)"
    if cloud_cover_pct is None:
        cloud_cover_pct = 80 if humidity > 90 else (50 if humidity > 70 else 20)
    moon_penalty = 0
    if "full" in moon_phase:
        moon_penalty = 40
    elif "gibbous" in moon_phase:
        moon_penalty = 25
    elif "quarter" in moon_phase:
        moon_penalty = 15
    elif "crescent" in moon_phase:
        moon_penalty = 5
    base = 90 if cloud_cover_pct < 20 else (60 if cloud_cover_pct < 50 else (30 if cloud_cover_pct < 80 else 10))
    quality_score = max(0, base - moon_penalty)
    if quality_score >= 70:
        return "Excellent"
    if quality_score >= 50:
        return "Good"
    if quality_score >= 30:
        return "Fair"
    return "Poor"


def moon_stargazing_impact(moon_phase: str | None = None, illumination: float | int | None = None) -> str:
    """Stargazing impact classification based on moon brightness."""
    if illumination is None and moon_phase:
        illumination = MOON_ILLUMINATION.get(moon_phase)
    if illumination is None:
        return "unknown"
    illum = float(illumination)
    if illum <= 10:
        return "excellent"
    if illum <= 25:
        return "good"
    if illum <= 50:
        return "fair"
    if illum <= 75:
        return "poor"
    return "bad"


# ---------------------------------------------------------------------------
# Moon phase
# ---------------------------------------------------------------------------


def _julian_day_gregorian(year: int, month: int, day: int) -> float:
    """Julian Day for a Gregorian calendar date at 0h UT."""
    y, m = year, month
    if m <= 2:
        y -= 1
        m += 12
    a = y // 100
    b = 2 - a + (a // 4)
    return int(365.25 * (y + 4716)) + int(30.6001 * (m + 1)) + day + b - 1524.5


def calculate_moon_phase(year: int, month: int, day: int) -> str:
    """Return moon phase label for a given date (UTC). Lightweight approximation."""
    jd = _julian_day_gregorian(year, month, day)
    age = (jd - 2451550.1) % 29.53058867

    if age < 1.85:
        return "new_moon"
    if age < 5.53:
        return "waxing_crescent"
    if age < 9.22:
        return "first_quarter"
    if age < 12.91:
        return "waxing_gibbous"
    if age < 16.61:
        return "full_moon"
    if age < 20.30:
        return "waning_gibbous"
    if age < 23.99:
        return "last_quarter"
    if age < 27.68:
        return "waning_crescent"
    return "new_moon"


# =============================================================================
# DEGREE DAYS  (v0.5.0)
# =============================================================================


def heating_degree_hours(temp_c: float, base_c: float = 18.0) -> float:
    """Return the heating degree-hour contribution for current temperature.

    HDH = max(0, base - temp).  Accumulate over one hour to get HDH/day.
    Divide running sum by 24 to express in degree-day units.
    """
    return max(0.0, base_c - temp_c)


def cooling_degree_hours(temp_c: float, base_c: float = 18.0) -> float:
    """Return the cooling degree-hour contribution for current temperature."""
    return max(0.0, temp_c - base_c)


# =============================================================================
# EXTRATERRESTRIAL RADIATION & ET₀  (v0.6.0 Hargreaves-Samani)
# =============================================================================


def extraterrestrial_radiation_mj(lat_deg: float, day_of_year: int) -> float:
    """Return extraterrestrial radiation Ra in MJ m⁻² day⁻¹.

    Uses FAO-56 equations 21-24.
    """
    phi = math.radians(lat_deg)
    dr = 1 + 0.033 * math.cos(2 * math.pi * day_of_year / 365)
    delta = 0.409 * math.sin(2 * math.pi * day_of_year / 365 - 1.39)
    ws = math.acos(-math.tan(phi) * math.tan(delta))
    Gsc = 0.0820  # solar constant MJ m⁻² min⁻¹
    Ra = (
        (24 * 60 / math.pi)
        * Gsc
        * dr
        * (ws * math.sin(phi) * math.sin(delta) + math.cos(phi) * math.cos(delta) * math.sin(ws))
    )
    return max(0.0, Ra)


def et0_hargreaves(
    t_max_c: float,
    t_min_c: float,
    t_mean_c: float,
    lat_deg: float,
    day_of_year: int,
) -> float:
    """Calculate reference evapotranspiration ET₀ (mm/day) using Hargreaves-Samani.

    Hargreaves & Samani 1985, validated against Penman-Monteith in FAO-56.
    Accuracy: ±15-20% vs full P-M when solar radiation is unavailable.

    Args:
        t_max_c: Daily max temperature °C
        t_min_c: Daily min temperature °C
        t_mean_c: Daily mean temperature °C (or use (max+min)/2)
        lat_deg: Latitude in decimal degrees
        day_of_year: Day of year (1-365)
    Returns:
        ET₀ in mm/day, or 0.0 if inputs are invalid.
    """
    try:
        if None in (t_max_c, t_min_c, t_mean_c):
            return 0.0
        t_range = max(0.0, t_max_c - t_min_c)
        Ra = extraterrestrial_radiation_mj(lat_deg, day_of_year)
        # Hargreaves-Samani: ET₀ = 0.0023 × Ra × (T_mean + 17.8) × √ΔT
        # Convert Ra from MJ to mm/day equivalent: Ra_mm = Ra / 2.45
        Ra_mm = Ra / 2.45
        et0 = 0.0023 * Ra_mm * (t_mean_c + 17.8) * (t_range**0.5)
        return max(0.0, round(et0, 2))
    except Exception:
        return 0.0


def et0_hourly_estimate(et0_daily_mm: float, hour_utc: int) -> float:
    """Distribute daily ET₀ across hours using a sinusoidal solar curve.

    Assumes ~80 % of daily ET₀ occurs during daylight hours 6-18 UTC.
    Returns mm for the current hour.
    """
    if et0_daily_mm <= 0:
        return 0.0
    if 6 <= hour_utc <= 18:
        daytime_hours = 13
        # Sine curve peaked at noon (hour 12)
        angle = math.pi * (hour_utc - 6) / daytime_hours
        weight = math.sin(angle)
        return round(et0_daily_mm * 0.80 * weight / 6.37, 3)
    return 0.0


# =============================================================================
# METAR PARSING  (v0.5.0)
# =============================================================================


def parse_metar_json(report: dict) -> dict:
    """Parse an aviationweather.gov JSON METAR report into a normalised dict.

    Returns keys: temp_c, dewpoint_c, pressure_hpa, wind_ms, wind_dir_deg,
                  raw_text, station_id, age_min.  Missing fields are None.
    """
    result: dict = {
        "station_id": report.get("icaoId") or report.get("stationId"),
        "raw_text": report.get("rawOb") or report.get("rawMETAR"),
        "temp_c": None,
        "dewpoint_c": None,
        "pressure_hpa": None,
        "wind_ms": None,
        "wind_dir_deg": None,
        "age_min": None,
    }

    # Temperature
    temp = report.get("temp")
    if temp is not None:
        with contextlib.suppress(ValueError, TypeError):
            result["temp_c"] = float(temp)

    # Dewpoint
    dewp = report.get("dewp")
    if dewp is not None:
        with contextlib.suppress(ValueError, TypeError):
            result["dewpoint_c"] = float(dewp)

    # Altimeter (inHg) → hPa,  or directly from altimHg/slp
    # Try slp first (sea level pressure in hPa)
    slp = report.get("slp")
    altim = report.get("altim")
    if slp is not None:
        with contextlib.suppress(ValueError, TypeError):
            result["pressure_hpa"] = float(slp)
    elif altim is not None:
        with contextlib.suppress(ValueError, TypeError):
            # altim in inHg → hPa (1 inHg = 33.8639 hPa)
            result["pressure_hpa"] = round(float(altim) * 33.8639, 1)

    # Wind speed (knots) → m/s
    wspd = report.get("wspd")
    if wspd is not None:
        with contextlib.suppress(ValueError, TypeError):
            result["wind_ms"] = round(float(wspd) * 0.514444, 1)

    # Wind direction
    wdir = report.get("wdir")
    if wdir is not None:
        with contextlib.suppress(ValueError, TypeError):
            result["wind_dir_deg"] = int(float(wdir))

    # Observation age in minutes (use obsTime epoch if available)
    import time as _time

    obs_time = report.get("obsTime")
    if obs_time is not None:
        try:
            age_s = _time.time() - float(obs_time)
            result["age_min"] = round(age_s / 60, 0)
        except (ValueError, TypeError):
            pass

    return result


def metar_validation_label(
    delta_temp: float | None,
    delta_pressure: float | None,
    age_min: float | None,
) -> str:
    """Classify local vs METAR agreement.

    Returns one of: "Match" / "Plausible" / "Check sensor" / "Stale METAR" / "No data"
    """
    if delta_temp is None and delta_pressure is None:
        return "No data"
    if age_min is not None and age_min > 90:
        return "Stale METAR"

    temp_ok = delta_temp is None or abs(delta_temp) <= 2.5
    press_ok = delta_pressure is None or abs(delta_pressure) <= 3.0

    if temp_ok and press_ok:
        return "Match"
    if abs(delta_temp or 0) <= 5.0 and abs(delta_pressure or 0) <= 6.0:
        return "Plausible"
    return "Check sensor"


# ===========================================================================
# v0.7.0 — Air Quality helpers
# ===========================================================================

# US EPA AQI breakpoints: (C_low, C_high, AQI_low, AQI_high)
_PM25_BREAKPOINTS = [
    (0.0, 12.0, 0, 50),
    (12.1, 35.4, 51, 100),
    (35.5, 55.4, 101, 150),
    (55.5, 150.4, 151, 200),
    (150.5, 250.4, 201, 300),
    (250.5, 350.4, 301, 400),
    (350.5, 500.4, 401, 500),
]

_PM10_BREAKPOINTS = [
    (0, 54, 0, 50),
    (55, 154, 51, 100),
    (155, 254, 101, 150),
    (255, 354, 151, 200),
    (355, 424, 201, 300),
    (425, 504, 301, 400),
    (505, 604, 401, 500),
]


def _aqi_from_breakpoints(c: float, breakpoints: list) -> int | None:
    """Linear interpolation of US EPA AQI from a concentration value."""
    for c_lo, c_hi, aqi_lo, aqi_hi in breakpoints:
        if c_lo <= c <= c_hi:
            return round(((aqi_hi - aqi_lo) / (c_hi - c_lo)) * (c - c_lo) + aqi_lo)
    return 500 if c > breakpoints[-1][1] else None


def calculate_us_aqi(pm2_5: float | None, pm10: float | None) -> int | None:
    """US EPA AQI — highest of PM2.5 and PM10 sub-indices.

    Returns None when both inputs are None.
    Reference: EPA AQI Technical Assistance Document, 2018.
    """
    sub = []
    if pm2_5 is not None:
        v = _aqi_from_breakpoints(float(pm2_5), _PM25_BREAKPOINTS)
        if v is not None:
            sub.append(v)
    if pm10 is not None:
        v = _aqi_from_breakpoints(float(pm10), _PM10_BREAKPOINTS)
        if v is not None:
            sub.append(v)
    return max(sub) if sub else None


def aqi_level(aqi: int) -> str:
    """US EPA AQI category label."""
    if aqi <= 50:
        return "Good"
    if aqi <= 100:
        return "Moderate"
    if aqi <= 150:
        return "Unhealthy for Sensitive Groups"
    if aqi <= 200:
        return "Unhealthy"
    if aqi <= 300:
        return "Very Unhealthy"
    return "Hazardous"


def aqi_color(aqi: int) -> str:
    """US EPA AQI colour hex."""
    if aqi <= 50:
        return "#00E400"
    if aqi <= 100:
        return "#FFFF00"
    if aqi <= 150:
        return "#FF7E00"
    if aqi <= 200:
        return "#FF0000"
    if aqi <= 300:
        return "#8F3F97"
    return "#7E0023"


def pollen_level(index: int | None) -> str:
    """Tomorrow.io pollen index (0-5) to level label."""
    if index is None:
        return "Unknown"
    labels = ["None", "Very Low", "Low", "Medium", "High", "Very High"]
    return labels[min(int(index), 5)]


def pollen_overall(grass: int | None, tree: int | None, weed: int | None) -> str:
    """Highest single pollen level across all types."""
    vals = [v for v in (grass, tree, weed) if v is not None]
    if not vals:
        return "Unknown"
    return pollen_level(max(vals))


# ===========================================================================
# v0.8.0 — Precise moon illumination
# ===========================================================================


def calculate_moon_illumination(year: int, month: int, day: int) -> float:
    """Moon disk illumination fraction (0.0–1.0).

    Uses Jean Meeus "Astronomical Algorithms" Chapter 48 (simplified).
    Accuracy: ~1% for illumination percentage.
    """
    jd = _julian_day_gregorian(year, month, day) + 0.5  # noon

    # Time in Julian centuries from J2000.0
    T = (jd - 2451545.0) / 36525.0

    # Sun's mean longitude (degrees)
    L0 = 280.46646 + 36000.76983 * T
    # Sun's mean anomaly (degrees)
    M_sun = math.radians(357.52911 + 35999.05029 * T - 0.0001537 * T * T)
    # Sun's equation of centre
    C_sun = (1.914602 - 0.004817 * T - 0.000014 * T * T) * math.sin(M_sun)
    C_sun += (0.019993 - 0.000101 * T) * math.sin(2 * M_sun)
    C_sun += 0.000289 * math.sin(3 * M_sun)
    # Sun's true longitude
    sun_lon = L0 + C_sun

    # Moon's mean longitude
    moon_L = 218.3165 + 481267.8813 * T
    # Moon's mean anomaly
    M_moon = math.radians(134.9634 + 477198.8676 * T)
    # Moon's argument of latitude
    F_moon = math.radians(93.2721 + 483202.0175 * T)

    # Moon's longitude (simplified)
    moon_lon = (
        moon_L
        + 6.2886 * math.sin(M_moon)
        + 1.2740 * math.sin(2 * math.radians(moon_L) - M_moon)
        + 0.6583 * math.sin(2 * math.radians(moon_L))
        + 0.2136 * math.sin(2 * M_moon)
        - 0.1851 * math.sin(M_sun)
        - 0.1143 * math.sin(2 * F_moon)
    )

    # Elongation angle between moon and sun
    elong = (moon_lon - sun_lon) % 360.0
    # Illumination fraction
    illumination = (1 - math.cos(math.radians(elong))) / 2
    return round(max(0.0, min(1.0, illumination)), 3)


def moon_phase_days(year: int, month: int, day: int) -> float:
    """Days since last new moon (synodic age 0–29.53)."""
    jd = _julian_day_gregorian(year, month, day) + 0.5
    # Reference new moon: 2000-01-06 18:14 UTC = JD 2451550.259
    synodic = 29.53058867
    age = (jd - 2451550.259) % synodic
    return round(age, 2)


def moon_next_phase_days(year: int, month: int, day: int, target_age: float) -> float:
    """Days until next occurrence of a moon phase (by synodic age target).

    target_age: 0 = new, 7.38 = first quarter, 14.77 = full, 22.15 = last quarter
    """
    current_age = moon_phase_days(year, month, day)
    synodic = 29.53058867
    diff = (target_age - current_age) % synodic
    return round(diff, 1)


def moon_phase_from_age(age_days: float) -> str:
    """Determine phase name from synodic age (0–29.53 days)."""
    synodic = 29.53058867
    pct = age_days / synodic
    if pct < 0.035 or pct >= 0.965:
        return "new_moon"
    if pct < 0.215:
        return "waxing_crescent"
    if pct < 0.285:
        return "first_quarter"
    if pct < 0.465:
        return "waxing_gibbous"
    if pct < 0.535:
        return "full_moon"
    if pct < 0.715:
        return "waning_gibbous"
    if pct < 0.785:
        return "last_quarter"
    return "waning_crescent"


MOON_PHASE_NAMES = {
    "new_moon": "New Moon",
    "waxing_crescent": "Waxing Crescent",
    "first_quarter": "First Quarter",
    "waxing_gibbous": "Waxing Gibbous",
    "full_moon": "Full Moon",
    "waning_gibbous": "Waning Gibbous",
    "last_quarter": "Last Quarter",
    "waning_crescent": "Waning Crescent",
}

MOON_PHASE_EMOJIS = {
    "new_moon": "🌑",
    "waxing_crescent": "🌒",
    "first_quarter": "🌓",
    "waxing_gibbous": "🌔",
    "full_moon": "🌕",
    "waning_gibbous": "🌖",
    "last_quarter": "🌗",
    "waning_crescent": "🌘",
}


def moon_display_string(phase_key: str, illumination_pct: float) -> str:
    """Human-readable moon display: emoji + name + illumination."""
    emoji = MOON_PHASE_EMOJIS.get(phase_key, "🌙")
    name = MOON_PHASE_NAMES.get(phase_key, phase_key.replace("_", " ").title())
    return f"{emoji} {name} ({illumination_pct:.0f}%)"


# ===========================================================================
# v0.9.0 — Penman-Monteith FAO-56 ET₀
# ===========================================================================


def et0_penman_monteith(
    temp_mean_c: float,
    temp_max_c: float,
    temp_min_c: float,
    humidity: float,
    wind_speed_ms: float,
    solar_radiation_wm2: float,
    elevation_m: float = 0.0,
    day_of_year: int = 180,
) -> float:
    """Reference evapotranspiration via FAO-56 Penman-Monteith method.

    Parameters
    ----------
    temp_mean_c : float
        Mean daily air temperature (°C).
    temp_max_c : float
        Daily maximum temperature (°C). Pass mean if only mean available.
    temp_min_c : float
        Daily minimum temperature (°C). Pass mean if only mean available.
    humidity : float
        Relative humidity (%).
    wind_speed_ms : float
        Wind speed at sensor height, converted to 2 m internally (m/s).
    solar_radiation_wm2 : float
        Incoming solar (shortwave) radiation (W/m²), daily mean.
    elevation_m : float
        Station elevation above sea-level (m).
    day_of_year : int
        Julian day of year (1-365), used for net longwave correction.

    Returns
    -------
    float
        ET₀ in mm/day.  Accuracy: ~5–10% vs lysimeter measurements.

    References
    ----------
    Allen et al. 1998: "Crop Evapotranspiration — Guidelines for Computing
    Crop Water Requirements", FAO Irrigation and Drainage Paper 56.
    """
    if any(v is None for v in (temp_mean_c, humidity, wind_speed_ms, solar_radiation_wm2)):
        return 0.0

    T = float(temp_mean_c)
    T_max = float(temp_max_c)
    T_min = float(temp_min_c)
    RH = float(humidity)
    u_z = float(wind_speed_ms)
    Rs_wm2 = float(solar_radiation_wm2)
    z = float(elevation_m)
    doy = int(day_of_year)

    # Convert Rs from W/m² (mean daily) to MJ/m²/d
    Rs = Rs_wm2 * 86400 / 1e6

    # Psychrometric constant γ (kPa/°C)  FAO56 Eq 8
    P = 101.3 * ((293.0 - 0.0065 * z) / 293.0) ** 5.26
    gamma = 0.000665 * P

    # Slope of saturation vapor pressure curve Δ (kPa/°C)  FAO56 Eq 13
    delta = 4098 * (0.6108 * math.exp((17.27 * T) / (T + 237.3))) / ((T + 237.3) ** 2)

    # Saturation vapor pressure (kPa)  FAO56 Eq 11-12
    es_max = 0.6108 * math.exp((17.27 * T_max) / (T_max + 237.3))
    es_min = 0.6108 * math.exp((17.27 * T_min) / (T_min + 237.3))
    es = (es_max + es_min) / 2.0

    # Actual vapor pressure (kPa)  FAO56 Eq 17
    ea = es * (RH / 100.0)

    # Net shortwave radiation Rns  FAO56 Eq 38 (α=0.23 for reference grass)
    Rns = (1 - 0.23) * Rs

    # Extraterrestrial radiation Ra for net longwave estimate  FAO56 Eq 21
    _phi = math.radians(max(-90, min(90, z)))  # use elevation as lat proxy — caller should pass lat
    # Simplified Ra (mean for mid-latitudes when lat not separately passed)
    Ra = extraterrestrial_radiation_mj(37.0, doy)  # fallback 37°N

    # Clear-sky solar radiation Rso  FAO56 Eq 37
    Rso = (0.75 + 2e-5 * z) * Ra

    # Net longwave radiation Rnl  FAO56 Eq 39
    sigma = 4.903e-9  # Stefan-Boltzmann in MJ K⁻⁴ m⁻² d⁻¹
    T_max_K = T_max + 273.16
    T_min_K = T_min + 273.16
    Rs_Rso = min(Rs / Rso, 1.0) if Rso > 0 else 1.0
    Rnl = sigma * ((T_max_K**4 + T_min_K**4) / 2) * (0.34 - 0.14 * math.sqrt(max(ea, 0.001))) * (1.35 * Rs_Rso - 0.35)

    # Net radiation Rn  FAO56 Eq 40
    Rn = Rns - Rnl

    # Wind speed at 2 m height  FAO56 Eq 47 (assuming 10 m sensor)
    u2 = u_z * (4.87 / math.log(67.8 * 10 - 5.42))

    # FAO56 Eq 6 — Penman-Monteith
    numerator = 0.408 * delta * Rn + gamma * (900 / (T + 273)) * u2 * (es - ea)
    denominator = delta + gamma * (1 + 0.34 * u2)
    et0 = numerator / denominator if denominator > 0 else 0.0
    return round(max(0.0, et0), 3)
