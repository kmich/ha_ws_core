"""Sensors for Weather Station Core -- v0.5.0."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    # v0.7.0
    CONF_ENABLE_AIR_QUALITY,
    CONF_ENABLE_DEGREE_DAYS,
    CONF_ENABLE_DISPLAY_SENSORS,
    CONF_ENABLE_FIRE_RISK,
    CONF_ENABLE_LAUNDRY,
    CONF_ENABLE_METAR,
    # v0.8.0
    CONF_ENABLE_MOON,
    CONF_ENABLE_POLLEN,
    CONF_ENABLE_RUNNING,
    CONF_ENABLE_SEA_TEMP,
    # v0.9.0
    CONF_ENABLE_SOLAR_FORECAST,
    CONF_ENABLE_STARGAZING,
    CONF_PREFIX,
    DEFAULT_PREFIX,
    DOMAIN,
    KEY_ALERT_MESSAGE,
    KEY_ALERT_STATE,
    # v0.7.0
    KEY_AQI,
    KEY_AQI_LEVEL,
    KEY_BATTERY_DISPLAY,
    KEY_BATTERY_PCT,
    KEY_CDD_RATE,
    KEY_CDD_TODAY,
    KEY_CURRENT_CONDITION,
    KEY_CWOP_STATUS,
    KEY_DATA_QUALITY,
    KEY_DEW_POINT_C,
    # v0.6.0
    KEY_ET0_DAILY_MM,
    KEY_ET0_HOURLY_MM,
    KEY_ET0_PM_DAILY_MM,
    KEY_FEELS_LIKE_C,
    KEY_FIRE_RISK_SCORE,
    KEY_FORECAST,
    KEY_FORECAST_TILES,
    KEY_FROST_POINT_C,
    KEY_HDD_RATE,
    # v0.5.0
    KEY_HDD_TODAY,
    KEY_HEALTH_DISPLAY,
    KEY_HUMIDITY_LEVEL_DISPLAY,
    KEY_LAST_EXPORT_TIME,
    KEY_LAUNDRY_SCORE,
    KEY_LUX,
    KEY_METAR_AGE_MIN,
    KEY_METAR_DELTA_PRESSURE,
    KEY_METAR_DELTA_TEMP,
    KEY_METAR_PRESSURE_HPA,
    KEY_METAR_STATION,
    KEY_METAR_TEMP_C,
    KEY_METAR_VALIDATION,
    KEY_METAR_WIND_DIR,
    KEY_METAR_WIND_MS,
    KEY_MOON_AGE_DAYS,
    KEY_MOON_DISPLAY,
    KEY_MOON_ILLUMINATION_PCT,
    KEY_MOON_NEXT_FULL,
    KEY_MOON_NEXT_NEW,
    # v0.8.0
    KEY_MOON_PHASE,
    KEY_NO2,
    KEY_NORM_HUMIDITY,
    KEY_NORM_PRESSURE_HPA,
    KEY_NORM_RAIN_TOTAL_MM,
    KEY_NORM_TEMP_C,
    KEY_NORM_WIND_DIR_DEG,
    KEY_NORM_WIND_GUST_MS,
    KEY_NORM_WIND_SPEED_MS,
    KEY_OZONE,
    KEY_PACKAGE_STATUS,
    KEY_PM2_5,
    KEY_PM10,
    KEY_POLLEN_GRASS,
    KEY_POLLEN_OVERALL,
    KEY_POLLEN_TREE,
    KEY_POLLEN_WEED,
    KEY_PRESSURE_CHANGE_WINDOW_HPA,
    KEY_PRESSURE_TREND_DISPLAY,
    KEY_PRESSURE_TREND_HPAH,
    KEY_RAIN_ACCUM_1H,
    KEY_RAIN_ACCUM_24H,
    KEY_RAIN_DISPLAY,
    KEY_RAIN_PROBABILITY,
    KEY_RAIN_PROBABILITY_COMBINED,
    KEY_RAIN_RATE_FILT,
    KEY_RAIN_RATE_RAW,
    KEY_RUNNING_SCORE,
    KEY_SEA_LEVEL_PRESSURE_HPA,
    KEY_SEA_SURFACE_TEMP,
    KEY_SENSOR_QUALITY_FLAGS,
    KEY_SOLAR_FORECAST_STATUS,
    # v0.9.0
    KEY_SOLAR_FORECAST_TODAY_KWH,
    KEY_SOLAR_FORECAST_TOMORROW_KWH,
    KEY_STARGAZE_SCORE,
    KEY_TEMP_AVG_24H,
    KEY_TEMP_DISPLAY,
    KEY_TEMP_HIGH_24H,
    KEY_TEMP_LOW_24H,
    KEY_TIME_SINCE_RAIN,
    KEY_UV,
    KEY_UV_LEVEL_DISPLAY,
    KEY_WET_BULB_C,
    KEY_WIND_BEAUFORT,
    KEY_WIND_BEAUFORT_DESC,
    KEY_WIND_DIR_SMOOTH_DEG,
    KEY_WIND_GUST_MAX_24H,
    KEY_WIND_QUADRANT,
    KEY_WU_STATUS,
    KEY_ZAMBRETTI_FORECAST,
    KEY_ZAMBRETTI_NUMBER,
    UNIT_PRESSURE_HPA,
    UNIT_RAIN_MM,
    UNIT_TEMP_C,
    UNIT_WIND_MS,
)


@dataclass(frozen=True, kw_only=True)
class WSSensorDescription:
    """Describes Weather Station sensor entities."""

    key: str
    device_class: SensorDeviceClass | None = None
    entity_category: EntityCategory | None = None
    entity_registry_enabled_default: bool = True
    icon: str | None = None
    name: str | None = None
    native_unit: str | None = None
    state_class: SensorStateClass | None = None
    value_fn: Callable[[dict[str, Any]], Any] | None = None
    attrs_fn: Callable[[dict[str, Any]], dict[str, Any]] | None = None


SENSORS: list[WSSensorDescription] = [
    # =========================================================================
    # CORE MEASUREMENTS
    # =========================================================================
    WSSensorDescription(
        key=KEY_NORM_TEMP_C,
        name="WS Temperature",
        icon="mdi:thermometer",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit=UNIT_TEMP_C,
        state_class=SensorStateClass.MEASUREMENT,  # FIX: was TOTAL_INCREASING
    ),
    WSSensorDescription(
        key=KEY_DEW_POINT_C,
        name="WS Dew Point",
        icon="mdi:weather-fog",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit=UNIT_TEMP_C,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WSSensorDescription(
        key=KEY_NORM_HUMIDITY,
        name="WS Humidity",
        icon="mdi:water-percent",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit="%",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WSSensorDescription(
        key=KEY_NORM_PRESSURE_HPA,
        name="WS Station Pressure",
        icon="mdi:gauge",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit=UNIT_PRESSURE_HPA,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WSSensorDescription(
        key=KEY_SEA_LEVEL_PRESSURE_HPA,
        name="WS Sea-Level Pressure",
        icon="mdi:gauge-full",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit=UNIT_PRESSURE_HPA,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WSSensorDescription(
        key=KEY_NORM_WIND_SPEED_MS,
        name="WS Wind Speed",
        icon="mdi:weather-windy",
        device_class=SensorDeviceClass.WIND_SPEED,
        native_unit=UNIT_WIND_MS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WSSensorDescription(
        key=KEY_NORM_WIND_GUST_MS,
        name="WS Wind Gust",
        icon="mdi:weather-windy-variant",
        device_class=SensorDeviceClass.WIND_SPEED,
        native_unit=UNIT_WIND_MS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WSSensorDescription(
        key=KEY_NORM_WIND_DIR_DEG,
        name="WS Wind Direction",
        icon="mdi:compass",
        device_class=SensorDeviceClass.WIND_DIRECTION,
        native_unit="\u00b0",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WSSensorDescription(
        key=KEY_NORM_RAIN_TOTAL_MM,
        name="WS Rain Total",
        icon="mdi:water",
        device_class=SensorDeviceClass.PRECIPITATION,
        native_unit=UNIT_RAIN_MM,
        state_class=SensorStateClass.TOTAL_INCREASING,  # FIX: cumulative counter
    ),
    WSSensorDescription(
        key=KEY_RAIN_RATE_RAW,
        name="WS Rain Rate Raw",
        icon="mdi:weather-pouring",
        device_class=SensorDeviceClass.PRECIPITATION_INTENSITY,
        native_unit="mm/h",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    WSSensorDescription(
        key=KEY_RAIN_RATE_FILT,
        name="WS Rain Rate",
        icon="mdi:weather-pouring",
        device_class=SensorDeviceClass.PRECIPITATION_INTENSITY,
        native_unit="mm/h",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WSSensorDescription(
        key=KEY_LUX,
        name="WS Illuminance",
        icon="mdi:white-balance-sunny",
        device_class=SensorDeviceClass.ILLUMINANCE,
        native_unit="lx",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WSSensorDescription(
        key=KEY_UV,
        name="WS UV Index",
        icon="mdi:weather-sunny-alert",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WSSensorDescription(
        key=KEY_BATTERY_PCT,
        name="WS Battery",
        icon="mdi:battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit="%",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    WSSensorDescription(
        key=KEY_PRESSURE_TREND_HPAH,
        name="WS Pressure Trend Raw",
        icon="mdi:trending-up",
        native_unit="hPa/h",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    WSSensorDescription(
        key=KEY_PRESSURE_CHANGE_WINDOW_HPA,
        name="WS Pressure Change (window)",
        icon="mdi:swap-vertical",
        native_unit="hPa",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    WSSensorDescription(
        key=KEY_DATA_QUALITY,
        name="WS Data Quality Banner",
        icon="mdi:clipboard-check-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    WSSensorDescription(
        key=KEY_PACKAGE_STATUS,
        name="WS Package Status",
        icon="mdi:package-variant-closed",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    WSSensorDescription(
        key=KEY_SENSOR_QUALITY_FLAGS,
        name="WS Sensor Quality Flags",
        icon="mdi:shield-alert-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: len(d.get(KEY_SENSOR_QUALITY_FLAGS) or []),
        attrs_fn=lambda d: {
            "flags": d.get(KEY_SENSOR_QUALITY_FLAGS) or [],
            "all_clear": len(d.get(KEY_SENSOR_QUALITY_FLAGS) or []) == 0,
        },
    ),
    WSSensorDescription(
        key=KEY_ALERT_STATE,
        name="WS Alert State",
        icon="mdi:alert-circle-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    WSSensorDescription(
        key=KEY_ALERT_MESSAGE,
        name="WS Alert Message",
        icon="mdi:message-alert-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    WSSensorDescription(
        key=KEY_FORECAST,
        name="WS Forecast Daily",
        icon="mdi:calendar-weather",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: (d.get(KEY_FORECAST) or {}).get("provider") if d.get(KEY_FORECAST) else None,
        attrs_fn=lambda d: d.get(KEY_FORECAST) or {},
    ),
    # =========================================================================
    # ADVANCED METEOROLOGICAL SENSORS
    # =========================================================================
    WSSensorDescription(
        key=KEY_FEELS_LIKE_C,
        name="WS Feels Like",
        icon="mdi:thermometer-lines",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit=UNIT_TEMP_C,
        state_class=SensorStateClass.MEASUREMENT,
        attrs_fn=lambda d: {
            "method": "Australian Apparent Temperature (BOM standard)",
            "wind_contribution_ms": round(-0.70 * float(d[KEY_NORM_WIND_SPEED_MS]), 1)
            if d.get(KEY_NORM_WIND_SPEED_MS) is not None
            else None,
            "humidity": d.get(KEY_NORM_HUMIDITY),
            "actual_temp_c": d.get(KEY_NORM_TEMP_C),
        },
    ),
    # Wet-bulb temperature (Stull 2011)
    WSSensorDescription(
        key=KEY_WET_BULB_C,
        name="WS Wet-Bulb Temperature",
        icon="mdi:thermometer-water",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit=UNIT_TEMP_C,
        state_class=SensorStateClass.MEASUREMENT,
        attrs_fn=lambda d: {
            "method": "Stull 2011 approximation (+/- 0.3 C)",
            "reference": "Stull R. (2011) J. Appl. Meteor. Climatol. 50:2267-2269",
        },
    ),
    # Frost point (below 0 C uses ice constants)
    WSSensorDescription(
        key=KEY_FROST_POINT_C,
        name="WS Frost Point",
        icon="mdi:snowflake-thermometer",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit=UNIT_TEMP_C,
        state_class=SensorStateClass.MEASUREMENT,
        attrs_fn=lambda d: {
            "method": "Magnus formula with ice constants (Buck 1981) below 0 C",
            "note": "Equals dew point when temperature is above 0 C",
        },
    ),
    # Zambretti barometric forecast
    WSSensorDescription(
        key=KEY_ZAMBRETTI_FORECAST,
        name="WS Zambretti Forecast",
        icon="mdi:crystal-ball",
        attrs_fn=lambda d: {
            "z_number": d.get(KEY_ZAMBRETTI_NUMBER),
            "mslp_hpa": d.get(KEY_SEA_LEVEL_PRESSURE_HPA),
            "trend_3h_hpa": d.get(KEY_PRESSURE_TREND_HPAH),
            "wind_quadrant": d.get(KEY_WIND_QUADRANT),
            "pressure_trend_display": d.get(KEY_PRESSURE_TREND_DISPLAY),
            "method": "Negretti & Zambra lookup table with climate-region wind corrections",
        },
    ),
    # Zambretti Z-number (numeric, for automations)
    WSSensorDescription(
        key=KEY_ZAMBRETTI_NUMBER,
        name="WS Zambretti Number",
        icon="mdi:numeric",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # Beaufort wind scale
    WSSensorDescription(
        key=KEY_WIND_BEAUFORT,
        name="WS Wind Beaufort",
        icon="mdi:weather-windy",
        state_class=SensorStateClass.MEASUREMENT,
        attrs_fn=lambda d: {
            "description": d.get(KEY_WIND_BEAUFORT_DESC),
            "speed_ms": d.get(KEY_NORM_WIND_SPEED_MS),
            "speed_kmh": round(float(d[KEY_NORM_WIND_SPEED_MS]) * 3.6, 1)
            if d.get(KEY_NORM_WIND_SPEED_MS) is not None
            else None,
            "gust_ms": d.get(KEY_NORM_WIND_GUST_MS),
            "gust_kmh": round(float(d[KEY_NORM_WIND_GUST_MS]) * 3.6, 1)
            if d.get(KEY_NORM_WIND_GUST_MS) is not None
            else None,
        },
    ),
    WSSensorDescription(
        key=KEY_WIND_QUADRANT,
        name="WS Wind Quadrant",
        icon="mdi:compass-rose",
        attrs_fn=lambda d: {
            "degrees": d.get(KEY_WIND_DIR_SMOOTH_DEG) or d.get(KEY_NORM_WIND_DIR_DEG),
            "using_smoothed": d.get(KEY_WIND_DIR_SMOOTH_DEG) is not None,
        },
    ),
    WSSensorDescription(
        key=KEY_WIND_DIR_SMOOTH_DEG,
        name="WS Wind Direction Smoothed",
        icon="mdi:compass",
        native_unit="\u00b0",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # Current weather condition
    WSSensorDescription(
        key=KEY_CURRENT_CONDITION,
        name="WS Current Condition",
        icon="mdi:weather-partly-cloudy",
        attrs_fn=lambda d: {
            "mdi_icon": d.get("_condition_icon"),
            "color": d.get("_condition_color"),
            "description": d.get("_condition_description"),
            "severity": d.get("_condition_severity"),
            "rain_rate": d.get(KEY_RAIN_RATE_FILT),
            "wind_gust": d.get(KEY_NORM_WIND_GUST_MS),
            "temperature": d.get(KEY_NORM_TEMP_C),
        },
    ),
    # Rain probability
    WSSensorDescription(
        key=KEY_RAIN_PROBABILITY,
        name="WS Rain Probability",
        icon="mdi:weather-rainy",
        native_unit="%",
        state_class=SensorStateClass.MEASUREMENT,
        attrs_fn=lambda d: {
            "mslp_hpa": d.get(KEY_SEA_LEVEL_PRESSURE_HPA),
            "pressure_trend_3h": d.get(KEY_PRESSURE_TREND_HPAH),
            "humidity_pct": d.get(KEY_NORM_HUMIDITY),
            "wind_quadrant": d.get(KEY_WIND_QUADRANT),
            "method": "Heuristic index (0-100) based on pressure, trend, humidity, wind. Climate-region-aware.",
            "disclaimer": (
                "This is a heuristic index, NOT a calibrated probability. "
                "Accuracy depends on sensor quality and local climate patterns."
            ),
        },
    ),
    WSSensorDescription(
        key=KEY_RAIN_PROBABILITY_COMBINED,
        name="WS Rain Probability Combined",
        icon="mdi:weather-rainy",
        native_unit="%",
        state_class=SensorStateClass.MEASUREMENT,
        attrs_fn=lambda d: {
            "local_probability_pct": d.get(KEY_RAIN_PROBABILITY),
            "method": "Time-weighted merge: local sensors + Open-Meteo",
        },
    ),
    # Rain / pressure display
    WSSensorDescription(key=KEY_RAIN_DISPLAY, name="WS Rain Display", icon="mdi:weather-rainy"),
    WSSensorDescription(
        key=KEY_RAIN_ACCUM_1H,
        name="WS Rain Last 1h",
        icon="mdi:weather-pouring",
        device_class=SensorDeviceClass.PRECIPITATION,
        native_unit=UNIT_RAIN_MM,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WSSensorDescription(
        key=KEY_RAIN_ACCUM_24H,
        name="WS Rain Last 24h",
        icon="mdi:weather-pouring",
        device_class=SensorDeviceClass.PRECIPITATION,
        native_unit=UNIT_RAIN_MM,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WSSensorDescription(
        key=KEY_TIME_SINCE_RAIN,
        name="WS Time Since Rain",
        icon="mdi:clock-outline",
    ),
    WSSensorDescription(
        key=KEY_PRESSURE_TREND_DISPLAY,
        name="WS Pressure Trend",
        icon="mdi:trending-up",
        attrs_fn=lambda d: {
            "change_3h_hpa": d.get(KEY_PRESSURE_CHANGE_WINDOW_HPA),
            "trend_rate_hpah": d.get(KEY_PRESSURE_TREND_HPAH),
            "mslp_hpa": d.get(KEY_SEA_LEVEL_PRESSURE_HPA),
        },
    ),
    WSSensorDescription(
        key=KEY_HEALTH_DISPLAY,
        name="WS Station Health",
        icon="mdi:heart-pulse",
        attrs_fn=lambda d: {
            "color": d.get("_health_color"),
            "battery_pct": d.get(KEY_BATTERY_PCT),
            "data_quality": d.get(KEY_DATA_QUALITY),
        },
    ),
    WSSensorDescription(
        key=KEY_FORECAST_TILES,
        name="WS Forecast Tiles",
        icon="mdi:calendar-weather",
        value_fn=lambda d: "available" if d.get(KEY_FORECAST_TILES) else "unavailable",
        attrs_fn=lambda d: {
            "tiles": d.get(KEY_FORECAST_TILES) or [],
            "count": len(d.get(KEY_FORECAST_TILES) or []),
        },
    ),
    # =========================================================================
    # 24h ROLLING STATISTICS
    # =========================================================================
    WSSensorDescription(
        key=KEY_TEMP_HIGH_24H,
        name="WS Temperature High 24h",
        icon="mdi:thermometer-high",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit=UNIT_TEMP_C,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WSSensorDescription(
        key=KEY_TEMP_LOW_24H,
        name="WS Temperature Low 24h",
        icon="mdi:thermometer-low",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit=UNIT_TEMP_C,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WSSensorDescription(
        key=KEY_TEMP_AVG_24H,
        name="WS Temperature Average 24h",
        icon="mdi:thermometer",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit=UNIT_TEMP_C,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    WSSensorDescription(
        key=KEY_WIND_GUST_MAX_24H,
        name="WS Wind Gust Max 24h",
        icon="mdi:weather-windy-variant",
        device_class=SensorDeviceClass.WIND_SPEED,
        native_unit=UNIT_WIND_MS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # =========================================================================
    # DISPLAY / LEVEL SENSORS
    # =========================================================================
    WSSensorDescription(key=KEY_HUMIDITY_LEVEL_DISPLAY, name="WS Humidity Level", icon="mdi:water-percent"),
    WSSensorDescription(
        key=KEY_UV_LEVEL_DISPLAY,
        name="WS UV Level",
        icon="mdi:sun-wireless",
        attrs_fn=lambda d: {
            "uv_index": d.get(KEY_UV),
            "recommendation": d.get("_uv_recommendation"),
            "burn_time_fair_skin": d.get("_uv_burn_fair_skin"),
        },
    ),
    WSSensorDescription(
        key=KEY_TEMP_DISPLAY,
        name="WS Temperature Display",
        icon="mdi:thermometer",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # =========================================================================
    # ACTIVITY OPTIMIZATION SENSORS (disabled by default)
    # =========================================================================
    WSSensorDescription(
        key=KEY_LAUNDRY_SCORE,
        name="WS Laundry Drying Score",
        icon="mdi:hanger",
        native_unit="score",
        state_class=SensorStateClass.MEASUREMENT,
        attrs_fn=lambda d: {
            "recommendation": d.get("_laundry_recommendation"),
            "estimated_dry_time": d.get("_laundry_dry_time"),
        },
    ),
    WSSensorDescription(
        key=KEY_STARGAZE_SCORE,
        name="WS Stargazing Quality",
        icon="mdi:telescope",
        attrs_fn=lambda d: {
            "moon_phase": d.get("_moon_phase"),
            "moon_impact": d.get("_moon_stargazing_impact"),
        },
    ),
    WSSensorDescription(
        key=KEY_FIRE_RISK_SCORE,
        name="WS Fire Risk Score",
        icon="mdi:fire",
        native_unit="score",
        state_class=SensorStateClass.MEASUREMENT,
        attrs_fn=lambda d: {
            "danger_level": d.get("_fire_danger_level"),
            "rain_24h_mm": d.get("_fire_rain_24h_mm"),
            "temperature_c": d.get(KEY_NORM_TEMP_C),
            "humidity_pct": d.get(KEY_NORM_HUMIDITY),
            "wind_ms": d.get(KEY_NORM_WIND_SPEED_MS),
            "disclaimer": (
                "Simplified heuristic (0-50 scale). NOT suitable for operational "
                "fire weather decisions. Consult official fire services."
            ),
            "reference": "Inspired by Canadian FWI structure (Van Wagner 1987). "
            "Full FWI requires daily FFMC/DMC/DC moisture codes not available from PWS hardware.",
        },
    ),
    WSSensorDescription(
        key=KEY_RUNNING_SCORE,
        name="WS Running Score",
        icon="mdi:run",
        native_unit="score",
        state_class=SensorStateClass.MEASUREMENT,
        attrs_fn=lambda d: {
            "level": d.get("_running_level"),
            "recommendation": d.get("_running_recommendation"),
            "feels_like_c": d.get(KEY_FEELS_LIKE_C),
            "uv_index": d.get(KEY_UV),
        },
    ),
    # =========================================================================
    # SEA SURFACE TEMPERATURE (Open-Meteo Marine API)
    # =========================================================================
    WSSensorDescription(
        key=KEY_SEA_SURFACE_TEMP,
        name="WS Sea Surface Temperature",
        icon="mdi:waves",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit=UNIT_TEMP_C,
        state_class=SensorStateClass.MEASUREMENT,
        attrs_fn=lambda d: {
            "comfort": d.get("_sea_temp_comfort"),
            "hourly_forecast": d.get("_sea_temp_hourly"),
            "grid_latitude": d.get("_sea_temp_grid_lat"),
            "grid_longitude": d.get("_sea_temp_grid_lon"),
            "disclaimer": d.get("_sea_temp_disclaimer"),
        },
    ),
    # ---------------------------------------------------------------
    # Degree Days  (v0.5.0)
    # ---------------------------------------------------------------
    WSSensorDescription(
        key=KEY_HDD_TODAY,
        name="WS Heating Degree Days (Today)",
        icon="mdi:thermometer-minus",
        native_unit="°C·d",
        state_class=SensorStateClass.TOTAL_INCREASING,
        attrs_fn=lambda d: {
            "hdd_rate_ch": d.get(KEY_HDD_RATE),
            "base_temp_c": d.get("_degree_day_base_c"),
            "description": "Heating degree days accumulated today (resets at midnight)",
        },
    ),
    WSSensorDescription(
        key=KEY_CDD_TODAY,
        name="WS Cooling Degree Days (Today)",
        icon="mdi:thermometer-plus",
        native_unit="°C·d",
        state_class=SensorStateClass.TOTAL_INCREASING,
        attrs_fn=lambda d: {
            "cdd_rate_ch": d.get(KEY_CDD_RATE),
            "base_temp_c": d.get("_degree_day_base_c"),
            "description": "Cooling degree days accumulated today (resets at midnight)",
        },
    ),
    WSSensorDescription(
        key=KEY_HDD_RATE,
        name="WS HDD Rate",
        icon="mdi:thermometer-low",
        native_unit="°C",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        attrs_fn=lambda d: {
            "description": "Instantaneous heating degree-hour rate (use Riemann sum helper for daily totals)"
        },
    ),
    WSSensorDescription(
        key=KEY_CDD_RATE,
        name="WS CDD Rate",
        icon="mdi:thermometer-high",
        native_unit="°C",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        attrs_fn=lambda d: {
            "description": "Instantaneous cooling degree-hour rate (use Riemann sum helper for daily totals)"
        },
    ),
    # ---------------------------------------------------------------
    # METAR Cross-Validation  (v0.5.0)
    # ---------------------------------------------------------------
    WSSensorDescription(
        key=KEY_METAR_VALIDATION,
        name="WS METAR Validation",
        icon="mdi:shield-check",
        attrs_fn=lambda d: {
            "station_id": d.get(KEY_METAR_STATION),
            "metar_temp_c": d.get(KEY_METAR_TEMP_C),
            "metar_pressure_hpa": d.get(KEY_METAR_PRESSURE_HPA),
            "metar_wind_ms": d.get(KEY_METAR_WIND_MS),
            "metar_wind_dir_deg": d.get(KEY_METAR_WIND_DIR),
            "delta_temp_c": d.get(KEY_METAR_DELTA_TEMP),
            "delta_pressure_hpa": d.get(KEY_METAR_DELTA_PRESSURE),
            "metar_age_min": d.get(KEY_METAR_AGE_MIN),
        },
    ),
    WSSensorDescription(
        key=KEY_METAR_TEMP_C,
        name="WS METAR Temperature",
        icon="mdi:thermometer-lines",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit=UNIT_TEMP_C,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    WSSensorDescription(
        key=KEY_METAR_PRESSURE_HPA,
        name="WS METAR Pressure",
        icon="mdi:gauge",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit=UNIT_PRESSURE_HPA,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    WSSensorDescription(
        key=KEY_METAR_DELTA_TEMP,
        name="WS Temp vs METAR Delta",
        icon="mdi:thermometer-alert",
        native_unit=UNIT_TEMP_C,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        attrs_fn=lambda d: {
            "local_temp_c": d.get(KEY_NORM_TEMP_C),
            "metar_temp_c": d.get(KEY_METAR_TEMP_C),
            "station_id": d.get(KEY_METAR_STATION),
        },
    ),
    WSSensorDescription(
        key=KEY_METAR_DELTA_PRESSURE,
        name="WS Pressure vs METAR Delta",
        icon="mdi:gauge-empty",
        native_unit=UNIT_PRESSURE_HPA,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        attrs_fn=lambda d: {
            "local_pressure_hpa": d.get(KEY_SEA_LEVEL_PRESSURE_HPA),
            "metar_pressure_hpa": d.get(KEY_METAR_PRESSURE_HPA),
            "station_id": d.get(KEY_METAR_STATION),
        },
    ),
    # ---------------------------------------------------------------
    # ET₀ Evapotranspiration  (v0.6.0)
    # ---------------------------------------------------------------
    WSSensorDescription(
        key=KEY_ET0_DAILY_MM,
        name="WS ET₀ (Daily)",
        icon="mdi:sprout",
        device_class=SensorDeviceClass.PRECIPITATION,
        native_unit="mm",
        state_class=SensorStateClass.MEASUREMENT,
        attrs_fn=lambda d: {
            "method": "Hargreaves-Samani 1985",
            "et0_hourly_mm": d.get(KEY_ET0_HOURLY_MM),
            "accuracy_note": "±15-20% vs Penman-Monteith; improves with solar radiation sensor",
        },
    ),
    WSSensorDescription(
        key=KEY_ET0_HOURLY_MM,
        name="WS ET₀ (Hourly)",
        icon="mdi:sprout-outline",
        device_class=SensorDeviceClass.PRECIPITATION,
        native_unit="mm",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # ---------------------------------------------------------------
    # Upload / Export Status  (v0.6.0)
    # ---------------------------------------------------------------
    WSSensorDescription(
        key=KEY_CWOP_STATUS,
        name="WS CWOP Upload Status",
        icon="mdi:broadcast",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    WSSensorDescription(
        key=KEY_WU_STATUS,
        name="WS Weather Underground Status",
        icon="mdi:weather-cloudy-clock",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    WSSensorDescription(
        key=KEY_LAST_EXPORT_TIME,
        name="WS Last Export Time",
        icon="mdi:export",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # ---------------------------------------------------------------
    # Air Quality  (v0.7.0, Open-Meteo AQI API)
    # ---------------------------------------------------------------
    WSSensorDescription(
        key=KEY_AQI,
        name="WS Air Quality Index",
        icon="mdi:air-filter",
        native_unit="AQI",
        state_class=SensorStateClass.MEASUREMENT,
        attrs_fn=lambda d: {
            "level": d.get(KEY_AQI_LEVEL),
            "pm2_5_ug_m3": d.get(KEY_PM2_5),
            "pm10_ug_m3": d.get(KEY_PM10),
            "no2_ug_m3": d.get(KEY_NO2),
            "ozone_ug_m3": d.get(KEY_OZONE),
            "scale": "US EPA (0-50 Good, 51-100 Moderate, 101-150 Unhealthy for Sensitive, 151-200 Unhealthy, 201-300 Very Unhealthy, 300+ Hazardous)",
        },
    ),
    WSSensorDescription(
        key=KEY_AQI_LEVEL,
        name="WS Air Quality Level",
        icon="mdi:air-filter",
        attrs_fn=lambda d: {
            "aqi": d.get(KEY_AQI),
            "pm2_5_ug_m3": d.get(KEY_PM2_5),
            "pm10_ug_m3": d.get(KEY_PM10),
        },
    ),
    WSSensorDescription(
        key=KEY_PM2_5,
        name="WS PM2.5",
        icon="mdi:smoke",
        native_unit="µg/m³",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    WSSensorDescription(
        key=KEY_PM10,
        name="WS PM10",
        icon="mdi:smoke",
        native_unit="µg/m³",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # ---------------------------------------------------------------
    # Pollen  (v0.7.0, Tomorrow.io)
    # ---------------------------------------------------------------
    WSSensorDescription(
        key=KEY_POLLEN_OVERALL,
        name="WS Pollen Level",
        icon="mdi:flower-pollen",
        attrs_fn=lambda d: {
            "grass_index": d.get(KEY_POLLEN_GRASS),
            "grass_level": "None" if d.get(KEY_POLLEN_GRASS) == 0 else d.get("_pollen_grass_level"),
            "tree_index": d.get(KEY_POLLEN_TREE),
            "tree_level": "None" if d.get(KEY_POLLEN_TREE) == 0 else d.get("_pollen_tree_level"),
            "weed_index": d.get(KEY_POLLEN_WEED),
            "weed_level": "None" if d.get(KEY_POLLEN_WEED) == 0 else d.get("_pollen_weed_level"),
            "scale": "0=None, 1=Very Low, 2=Low, 3=Medium, 4=High, 5=Very High",
            "source": "Tomorrow.io",
        },
    ),
    WSSensorDescription(
        key=KEY_POLLEN_GRASS,
        name="WS Pollen Grass",
        icon="mdi:flower-pollen-outline",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    WSSensorDescription(
        key=KEY_POLLEN_TREE,
        name="WS Pollen Tree",
        icon="mdi:tree",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    WSSensorDescription(
        key=KEY_POLLEN_WEED,
        name="WS Pollen Weed",
        icon="mdi:flower-pollen-outline",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # ---------------------------------------------------------------
    # Moon  (v0.8.0, calculated)
    # ---------------------------------------------------------------
    WSSensorDescription(
        key=KEY_MOON_DISPLAY,
        name="WS Moon",
        icon="mdi:moon-waxing-crescent",
        attrs_fn=lambda d: {
            "phase": d.get(KEY_MOON_PHASE),
            "illumination_pct": d.get(KEY_MOON_ILLUMINATION_PCT),
            "age_days": d.get(KEY_MOON_AGE_DAYS),
            "days_to_full_moon": d.get(KEY_MOON_NEXT_FULL),
            "days_to_new_moon": d.get(KEY_MOON_NEXT_NEW),
            "method": "Meeus 1998, Astronomical Algorithms Ch. 48 (simplified)",
            "accuracy": "±1% illumination, ±0.5 day phase timing",
        },
    ),
    WSSensorDescription(
        key=KEY_MOON_PHASE,
        name="WS Moon Phase",
        icon="mdi:moon-full",
        attrs_fn=lambda d: {
            "illumination_pct": d.get(KEY_MOON_ILLUMINATION_PCT),
            "age_days": d.get(KEY_MOON_AGE_DAYS),
        },
    ),
    WSSensorDescription(
        key=KEY_MOON_ILLUMINATION_PCT,
        name="WS Moon Illumination",
        icon="mdi:moon-full",
        native_unit="%",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # ---------------------------------------------------------------
    # Solar forecast  (v0.9.0, forecast.solar)
    # ---------------------------------------------------------------
    WSSensorDescription(
        key=KEY_SOLAR_FORECAST_TODAY_KWH,
        name="WS Solar Forecast Today",
        icon="mdi:solar-power",
        native_unit="kWh",
        state_class=SensorStateClass.MEASUREMENT,
        attrs_fn=lambda d: {
            "tomorrow_kwh": d.get(KEY_SOLAR_FORECAST_TOMORROW_KWH),
            "status": d.get(KEY_SOLAR_FORECAST_STATUS),
            "source": "forecast.solar",
        },
    ),
    WSSensorDescription(
        key=KEY_SOLAR_FORECAST_TOMORROW_KWH,
        name="WS Solar Forecast Tomorrow",
        icon="mdi:solar-power-variant",
        native_unit="kWh",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # Penman-Monteith ET₀ (v0.9.0, when solar radiation sensor available)
    WSSensorDescription(
        key=KEY_ET0_PM_DAILY_MM,
        name="WS ET₀ Penman-Monteith (Daily)",
        icon="mdi:water-pump",
        device_class=SensorDeviceClass.PRECIPITATION,
        native_unit="mm",
        state_class=SensorStateClass.MEASUREMENT,
        attrs_fn=lambda d: {
            "method": "FAO-56 Penman-Monteith (Allen et al. 1998)",
            "accuracy_note": "±5-10% vs lysimeter; requires solar radiation sensor",
            "hargreaves_et0": d.get(KEY_ET0_DAILY_MM),
        },
    ),
]

# Sensor-to-feature-toggle mapping for granular control
_FEATURE_TOGGLE_MAP: dict[str, str] = {
    # Display sensors
    KEY_HUMIDITY_LEVEL_DISPLAY: CONF_ENABLE_DISPLAY_SENSORS,
    KEY_UV_LEVEL_DISPLAY: CONF_ENABLE_DISPLAY_SENSORS,
    KEY_TEMP_DISPLAY: CONF_ENABLE_DISPLAY_SENSORS,
    KEY_RAIN_DISPLAY: CONF_ENABLE_DISPLAY_SENSORS,
    KEY_PRESSURE_TREND_DISPLAY: CONF_ENABLE_DISPLAY_SENSORS,
    KEY_HEALTH_DISPLAY: CONF_ENABLE_DISPLAY_SENSORS,
    KEY_FORECAST_TILES: CONF_ENABLE_DISPLAY_SENSORS,
    KEY_BATTERY_DISPLAY: CONF_ENABLE_DISPLAY_SENSORS,
    # Individual activity scores
    KEY_LAUNDRY_SCORE: CONF_ENABLE_LAUNDRY,
    KEY_STARGAZE_SCORE: CONF_ENABLE_STARGAZING,
    KEY_FIRE_RISK_SCORE: CONF_ENABLE_FIRE_RISK,
    KEY_RUNNING_SCORE: CONF_ENABLE_RUNNING,
    # Sea temperature
    KEY_SEA_SURFACE_TEMP: CONF_ENABLE_SEA_TEMP,
    # Degree days  (v0.5.0)
    KEY_HDD_TODAY: CONF_ENABLE_DEGREE_DAYS,
    KEY_CDD_TODAY: CONF_ENABLE_DEGREE_DAYS,
    KEY_HDD_RATE: CONF_ENABLE_DEGREE_DAYS,
    KEY_CDD_RATE: CONF_ENABLE_DEGREE_DAYS,
    # METAR  (v0.5.0)
    KEY_METAR_VALIDATION: CONF_ENABLE_METAR,
    KEY_METAR_TEMP_C: CONF_ENABLE_METAR,
    KEY_METAR_PRESSURE_HPA: CONF_ENABLE_METAR,
    KEY_METAR_DELTA_TEMP: CONF_ENABLE_METAR,
    KEY_METAR_DELTA_PRESSURE: CONF_ENABLE_METAR,
    # Air Quality  (v0.7.0)
    KEY_AQI: CONF_ENABLE_AIR_QUALITY,
    KEY_AQI_LEVEL: CONF_ENABLE_AIR_QUALITY,
    KEY_PM2_5: CONF_ENABLE_AIR_QUALITY,
    KEY_PM10: CONF_ENABLE_AIR_QUALITY,
    KEY_NO2: CONF_ENABLE_AIR_QUALITY,
    KEY_OZONE: CONF_ENABLE_AIR_QUALITY,
    # Pollen  (v0.7.0)
    KEY_POLLEN_OVERALL: CONF_ENABLE_POLLEN,
    KEY_POLLEN_GRASS: CONF_ENABLE_POLLEN,
    KEY_POLLEN_TREE: CONF_ENABLE_POLLEN,
    KEY_POLLEN_WEED: CONF_ENABLE_POLLEN,
    # Moon  (v0.8.0)
    KEY_MOON_DISPLAY: CONF_ENABLE_MOON,
    KEY_MOON_PHASE: CONF_ENABLE_MOON,
    KEY_MOON_ILLUMINATION_PCT: CONF_ENABLE_MOON,
    # Solar forecast  (v0.9.0)
    KEY_SOLAR_FORECAST_TODAY_KWH: CONF_ENABLE_SOLAR_FORECAST,
    KEY_SOLAR_FORECAST_TOMORROW_KWH: CONF_ENABLE_SOLAR_FORECAST,
    KEY_ET0_PM_DAILY_MM: CONF_ENABLE_SOLAR_FORECAST,
}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    prefix = (entry.options.get(CONF_PREFIX) or entry.data.get(CONF_PREFIX) or DEFAULT_PREFIX).strip().lower()

    opts = {**entry.data, **entry.options}

    filtered: list[WSSensorDescription] = []
    for desc in SENSORS:
        toggle_key = _FEATURE_TOGGLE_MAP.get(desc.key)
        if toggle_key is not None and not opts.get(toggle_key, False):
            continue
        filtered.append(desc)

    entities: list[WSSensor] = [WSSensor(coordinator, entry, desc, prefix) for desc in filtered]
    async_add_entities(entities)


class WSSensor(RestoreEntity, CoordinatorEntity, SensorEntity):
    """A single derived sensor for Weather Station Core.

    Mixes in RestoreEntity so that sensors that warm up slowly (24h stats,
    Kalman filter, degree days, ET₀) report their last-known value on HA
    restart until the coordinator computes a fresh value.
    """

    # Keys that benefit from restore (slow-to-warm-up or accumulating sensors)
    _RESTORE_KEYS = {
        KEY_HDD_TODAY,
        KEY_CDD_TODAY,
        KEY_HDD_RATE,
        KEY_CDD_RATE,
        KEY_ET0_DAILY_MM,
        KEY_TEMP_HIGH_24H,
        KEY_TEMP_LOW_24H,
        KEY_TEMP_AVG_24H,
        KEY_WIND_GUST_MAX_24H,
        KEY_RAIN_ACCUM_1H,
        KEY_RAIN_ACCUM_24H,
        KEY_METAR_VALIDATION,
        KEY_METAR_TEMP_C,
        KEY_METAR_PRESSURE_HPA,
        KEY_METAR_DELTA_TEMP,
        KEY_METAR_DELTA_PRESSURE,
    }

    _DISABLED_BY_DEFAULT = {
        KEY_TEMP_AVG_24H,
        KEY_TEMP_DISPLAY,
        KEY_WIND_DIR_SMOOTH_DEG,
        KEY_BATTERY_DISPLAY,
        KEY_SENSOR_QUALITY_FLAGS,
        KEY_ZAMBRETTI_NUMBER,
        # New v0.5.0 diagnostic/rate sensors hidden by default
        KEY_HDD_RATE,
        KEY_CDD_RATE,
        KEY_ET0_HOURLY_MM,
        KEY_METAR_TEMP_C,
        KEY_METAR_PRESSURE_HPA,
        # v0.7.0 diagnostic sub-pollutants
        KEY_PM2_5,
        KEY_PM10,
        KEY_NO2,
        KEY_OZONE,
        KEY_POLLEN_GRASS,
        KEY_POLLEN_TREE,
        KEY_POLLEN_WEED,
        # v0.8.0
        KEY_MOON_ILLUMINATION_PCT,
        # v0.9.0
        KEY_SOLAR_FORECAST_TOMORROW_KWH,
        KEY_ET0_PM_DAILY_MM,
    }

    def __init__(self, coordinator, entry: ConfigEntry, desc: WSSensorDescription, prefix: str):
        super().__init__(coordinator)
        self._desc = desc
        self._entry = entry
        self._prefix = prefix
        self._restored_value: Any = None  # populated by async_added_to_hass for restore-capable sensors

        self._attr_unique_id = f"{entry.entry_id}_{desc.key}"
        self._attr_suggested_object_id = f"{prefix}_{self._slug_for_key(desc.key)}"
        self._attr_name = desc.name
        self._attr_icon = desc.icon
        self._attr_device_class = desc.device_class
        self._attr_native_unit_of_measurement = desc.native_unit
        self._attr_state_class = desc.state_class
        if desc.entity_category is not None:
            self._attr_entity_category = desc.entity_category
        if desc.key in self._DISABLED_BY_DEFAULT:
            self._attr_entity_registry_enabled_default = False

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, self._entry.entry_id)}}

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        desired = None
        if self._desc.key == KEY_DATA_QUALITY:
            desired = f"sensor.{self._prefix}_data_quality_banner"
        elif self._desc.key == KEY_FORECAST:
            desired = f"sensor.{self._prefix}_forecast_daily"
        if desired and self.entity_id and self.entity_id != desired:
            reg = er.async_get(self.hass)
            current = reg.async_get(self.entity_id)
            if current and current.unique_id == self.unique_id and reg.async_get(desired) is None:
                reg.async_update_entity(self.entity_id, new_entity_id=desired)

        # Restore last known value for sensors that are slow to warm up
        if self._desc.key in self._RESTORE_KEYS:
            last_state = await self.async_get_last_state()
            if last_state is not None and last_state.state not in ("unknown", "unavailable", None, ""):
                try:
                    self._restored_value = float(last_state.state)
                except (ValueError, TypeError):
                    self._restored_value = last_state.state
            else:
                self._restored_value = None

    @staticmethod
    def _slug_for_key(key: str) -> str:
        overrides = {
            KEY_DATA_QUALITY: "data_quality_banner",
            KEY_FORECAST: "forecast_daily",
            KEY_NORM_TEMP_C: "temperature",
            KEY_DEW_POINT_C: "dew_point",
            KEY_FROST_POINT_C: "frost_point",
            KEY_WET_BULB_C: "wet_bulb",
            KEY_NORM_HUMIDITY: "humidity",
            KEY_NORM_PRESSURE_HPA: "station_pressure",
            KEY_SEA_LEVEL_PRESSURE_HPA: "sea_level_pressure",
            KEY_NORM_WIND_SPEED_MS: "wind_speed",
            KEY_NORM_WIND_GUST_MS: "wind_gust",
            KEY_NORM_WIND_DIR_DEG: "wind_direction",
            KEY_NORM_RAIN_TOTAL_MM: "rain_total",
            KEY_RAIN_RATE_RAW: "rain_rate_raw",
            KEY_RAIN_RATE_FILT: "rain_rate",
            KEY_BATTERY_PCT: "battery",
            KEY_FEELS_LIKE_C: "feels_like",
            KEY_ZAMBRETTI_FORECAST: "zambretti_forecast",
            KEY_ZAMBRETTI_NUMBER: "zambretti_number",
            KEY_WIND_BEAUFORT: "wind_beaufort",
            KEY_WIND_QUADRANT: "wind_quadrant",
            KEY_WIND_DIR_SMOOTH_DEG: "wind_direction_smooth",
            KEY_CURRENT_CONDITION: "current_condition",
            KEY_RAIN_PROBABILITY: "rain_probability",
            KEY_RAIN_PROBABILITY_COMBINED: "rain_probability_combined",
            KEY_RAIN_DISPLAY: "rain_display",
            KEY_RAIN_ACCUM_1H: "rain_last_1h",
            KEY_RAIN_ACCUM_24H: "rain_last_24h",
            KEY_TIME_SINCE_RAIN: "time_since_rain",
            KEY_PRESSURE_TREND_DISPLAY: "pressure_trend",
            KEY_HEALTH_DISPLAY: "station_health",
            KEY_FORECAST_TILES: "forecast_tiles",
            KEY_TEMP_HIGH_24H: "temperature_high_24h",
            KEY_TEMP_LOW_24H: "temperature_low_24h",
            KEY_TEMP_AVG_24H: "temperature_avg_24h",
            KEY_WIND_GUST_MAX_24H: "wind_gust_max_24h",
            KEY_HUMIDITY_LEVEL_DISPLAY: "humidity_level",
            KEY_UV_LEVEL_DISPLAY: "uv_level",
            KEY_TEMP_DISPLAY: "temperature_display",
            KEY_LAUNDRY_SCORE: "laundry_drying_score",
            KEY_STARGAZE_SCORE: "stargazing_quality",
            KEY_FIRE_RISK_SCORE: "fire_risk_score",
            KEY_SENSOR_QUALITY_FLAGS: "sensor_quality_flags",
            KEY_RUNNING_SCORE: "running_score",
            KEY_LUX: "illuminance",
            KEY_UV: "uv_index",
            KEY_ALERT_STATE: "alert_state",
            KEY_ALERT_MESSAGE: "alert_message",
            KEY_PACKAGE_STATUS: "package_status",
            KEY_PRESSURE_CHANGE_WINDOW_HPA: "pressure_change_window",
            KEY_PRESSURE_TREND_HPAH: "pressure_trend_raw",
            KEY_SEA_SURFACE_TEMP: "sea_surface_temperature",
            # v0.5.0
            KEY_HDD_TODAY: "heating_degree_days_today",
            KEY_CDD_TODAY: "cooling_degree_days_today",
            KEY_HDD_RATE: "hdd_rate",
            KEY_CDD_RATE: "cdd_rate",
            KEY_METAR_VALIDATION: "metar_validation",
            KEY_METAR_TEMP_C: "metar_temperature",
            KEY_METAR_PRESSURE_HPA: "metar_pressure",
            KEY_METAR_DELTA_TEMP: "temp_vs_metar_delta",
            KEY_METAR_DELTA_PRESSURE: "pressure_vs_metar_delta",
            # v0.6.0
            KEY_ET0_DAILY_MM: "et0_daily",
            KEY_ET0_HOURLY_MM: "et0_hourly",
            KEY_CWOP_STATUS: "cwop_upload_status",
            KEY_WU_STATUS: "wu_upload_status",
            KEY_LAST_EXPORT_TIME: "last_export_time",
            # v0.7.0
            KEY_AQI: "air_quality_index",
            KEY_AQI_LEVEL: "air_quality_level",
            KEY_PM2_5: "pm2_5",
            KEY_PM10: "pm10",
            KEY_NO2: "no2",
            KEY_OZONE: "ozone",
            KEY_POLLEN_OVERALL: "pollen_level",
            KEY_POLLEN_GRASS: "pollen_grass",
            KEY_POLLEN_TREE: "pollen_tree",
            KEY_POLLEN_WEED: "pollen_weed",
            # v0.8.0
            KEY_MOON_DISPLAY: "moon",
            KEY_MOON_PHASE: "moon_phase",
            KEY_MOON_ILLUMINATION_PCT: "moon_illumination",
            # v0.9.0
            KEY_SOLAR_FORECAST_TODAY_KWH: "solar_forecast_today",
            KEY_SOLAR_FORECAST_TOMORROW_KWH: "solar_forecast_tomorrow",
            KEY_ET0_PM_DAILY_MM: "et0_penman_monteith",
        }
        if key in overrides:
            return overrides[key]
        # Fallback: strip common prefixes/suffixes for a clean slug
        return key.replace("_mmph", "").replace("_ms", "").replace("_hpa", "").replace("_c", "")

    @property
    def native_value(self):
        d = self.coordinator.data or {}
        if self._desc.value_fn is not None:
            try:
                val = self._desc.value_fn(d)
            except Exception:
                val = None
        else:
            val = d.get(self._desc.key)

        # Fall back to last-restored value for slow-warm-up sensors during startup
        if val is None and self._restored_value is not None and self._desc.key in self._RESTORE_KEYS:
            return self._restored_value

        # Once the coordinator provides a real value, clear the restore cache
        if val is not None and self._restored_value is not None:
            self._restored_value = None

        return val

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        d = self.coordinator.data or {}
        if self._desc.attrs_fn is not None:
            try:
                return {k: v for k, v in (self._desc.attrs_fn(d) or {}).items() if v is not None}
            except Exception:
                return {}
        if self._desc.key == KEY_ALERT_STATE:
            alerts = d.get("_active_alerts", [])
            return {
                "message": d.get(KEY_ALERT_MESSAGE, "All clear"),
                "icon": d.get("_alert_icon", "mdi:check-circle-outline"),
                "color": d.get("_alert_color", "rgba(74,222,128,0.8)"),
                "active_alerts": alerts,
                "alert_count": len(alerts),
            }
        if self._desc.key == KEY_ALERT_MESSAGE:
            return {
                "alert_state": d.get(KEY_ALERT_STATE, "clear"),
                "icon": d.get("_alert_icon", "mdi:check-circle-outline"),
                "color": d.get("_alert_color", "rgba(74,222,128,0.8)"),
            }
        if self._desc.key in (KEY_DATA_QUALITY, KEY_PACKAGE_STATUS):
            return {
                "package_ok": d.get("package_ok"),
                "data_quality": d.get(KEY_DATA_QUALITY),
                "alert_state": d.get(KEY_ALERT_STATE),
            }
        return {}
