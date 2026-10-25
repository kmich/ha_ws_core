"""Explain intentionally empty sensor values without inventing measurements."""

from __future__ import annotations

from typing import Any

from . import const as c


def unknown_status(key: str, coord: Any, data: dict) -> dict[str, str]:
    """Return diagnostic attributes for an unknown value, using configured inputs."""
    reason = "waiting_for_data"
    explanation = "Waiting for a valid reading from the configured source sensors."
    temp = data.get(c.KEY_NORM_TEMP_C)
    humidity = data.get(c.KEY_NORM_HUMIDITY)
    if key in (c.KEY_HEAT_INDEX, c.KEY_THW_INDEX, c.KEY_THSW_INDEX):
        if temp is not None and humidity is not None and (temp < 27 or humidity < 40):
            reason = "outside_valid_range"
            explanation = "This heat index applies only at 27 °C or above and humidity of at least 40%."
        elif key == c.KEY_THSW_INDEX and not coord.sources.get(c.SRC_SOLAR_RADIATION):
            reason = "missing_solar_radiation"
            explanation = "Map a solar radiation sensor in W/m²; illuminance is not used for this comfort index."
    elif key == c.KEY_WIND_CHILL:
        speed = data.get(c.KEY_NORM_WIND_SPEED_MS)
        if temp is not None and speed is not None and (temp > 10 or speed <= 1.34):
            reason = "outside_valid_range"
            explanation = "Wind chill applies only at 10 °C or below with wind above 4.8 km/h."
    elif key in (c.KEY_CLEARNESS_INDEX, c.KEY_CLOUD_COVER_PCT):
        if not coord.sources.get(c.SRC_SOLAR_RADIATION):
            reason = "missing_solar_radiation"
            explanation = "Map a solar radiation sensor in W/m² to estimate clearness and cloud cover."
        else:
            reason = "waiting_for_daylight_or_radiation"
            explanation = "Requires valid solar radiation and the sun at least 5° above the horizon."
    elif key in (c.KEY_SOLAR_ENERGY_TODAY_WHM2, c.KEY_PEAK_SUN_HOURS, c.KEY_NET_RADIATION, c.KEY_ET0_PM_DAILY_MM):
        estimated = getattr(coord, "et0_illuminance_fallback", False) and coord.sources.get(c.SRC_LUX)
        if not (coord.sources.get(c.SRC_SOLAR_RADIATION) or estimated):
            reason = "missing_solar_radiation"
            explanation = (
                "Map solar radiation, or enable the optional illuminance fallback with a mapped lux sensor "
                "for an approximate solar-energy/ET₀ calculation."
            )
        elif key == c.KEY_ET0_PM_DAILY_MM and not getattr(coord, "_solar_energy_previous_whm2", 0.0):
            reason = "waiting_for_daily_radiation"
            explanation = "Waiting for a completed day's solar irradiation to calculate daily Penman–Monteith ET₀."
    elif key in (c.KEY_MINUTES_UNTIL_RAIN, c.KEY_MINUTES_UNTIL_DRY):
        cache = getattr(coord, "_nowcast_cache", None)
        if not getattr(coord, "nowcast_enabled", False):
            reason = "feature_disabled"
            explanation = "Enable Precipitation Nowcast to calculate rain start and stop times."
        elif cache and data.get(c.KEY_NOWCAST_INTENSITY) is not None:
            reason = "no_transition_in_forecast"
            explanation = "No matching rain start or stop is predicted within the available nowcast window."
        else:
            reason = "waiting_for_nowcast"
            explanation = "Waiting for precipitation nowcast data."
    elif key in (c.KEY_LIGHTNING_DISTANCE_KM, c.KEY_LIGHTNING_AZIMUTH, c.KEY_LIGHTNING_PROXIMITY):
        source = c.SRC_LIGHTNING_AZIMUTH if key == c.KEY_LIGHTNING_AZIMUTH else c.SRC_LIGHTNING_DISTANCE
        if not (coord.sources.get(source) or getattr(coord, "_blitzortung_sources", {}).get(source)):
            reason = "missing_lightning_source"
            explanation = "Map the lightning distance/bearing source, or set up the Blitzortung integration."
        else:
            reason = "waiting_for_lightning_location"
            explanation = "The lightning source has not supplied a valid strike distance or bearing."
    elif key == c.KEY_LIGHTNING_CLEARANCE_MIN:
        reason = "no_strike_recorded"
        explanation = "No strike has been observed since this station entry loaded; elapsed clearance is unknown."
    return {"data_status": reason, "reason": reason, "explanation": explanation}
