"""Sensors for Weather Station Core -- v1.7.1."""

from __future__ import annotations

import contextlib
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
    # v1.6.2
    CONF_ENABLE_ADVANCED_SENSORS,
    # v0.7.0
    CONF_ENABLE_AIR_QUALITY,
    # v2.0
    CONF_ENABLE_AWEKAS,
    # v1.5.0
    CONF_ENABLE_COMFORT_INDICES,
    CONF_ENABLE_CWOP,
    CONF_ENABLE_DEGREE_DAYS,
    # v1.6.2
    CONF_ENABLE_DIAGNOSTICS,
    CONF_ENABLE_DISPLAY_SENSORS,
    CONF_ENABLE_FIRE_RISK,
    # v1.2.0
    CONF_ENABLE_FOG,
    # v1.6.2
    CONF_ENABLE_FWI_COMPONENTS,
    CONF_ENABLE_INDOOR,
    CONF_ENABLE_LIGHTNING,
    # v0.8.0
    CONF_ENABLE_MOON,
    # v1.7.0
    CONF_ENABLE_NOWCAST,
    CONF_ENABLE_OWM_STATIONS,
    CONF_ENABLE_POLLEN,
    CONF_ENABLE_PWSWEATHER,
    CONF_ENABLE_SEA_TEMP,
    # v2.1
    CONF_ENABLE_SOIL,
    # v0.9.0
    CONF_ENABLE_SOLAR_FORECAST,
    CONF_ENABLE_THUNDERSTORM,
    CONF_ENABLE_VIGICRUES,
    # v1.6.0
    CONF_ENABLE_VIGILANCE_METEO,
    CONF_ENABLE_WEATHERCLOUD,
    CONF_ENABLE_WINDY,
    CONF_ENABLE_WOW,
    CONF_ENABLE_WUNDERGROUND,
    CONF_INDOOR_ROOMS,
    CONF_PREFIX,
    CONF_VIGICRUES_RIVER_NAME,
    CONF_VIGICRUES_STATION_CODE,
    CONF_VIGICRUES_STATION_NAME,
    CONF_VIGICRUES_STATIONS,
    DEFAULT_PREFIX,
    DOMAIN,
    # v1.5.0
    KEY_ABSOLUTE_HUMIDITY,
    KEY_AIR_DENSITY,
    KEY_ALERT_MESSAGE,
    KEY_ALERT_STATE,
    # v0.7.0
    KEY_AQI,
    KEY_AQI_LEVEL,
    KEY_AWEKAS_STATUS,
    KEY_BATTERY_PCT,
    KEY_CDD_SEASON,
    KEY_CDD_TODAY_MM,
    KEY_CHILL_HOURS_SEASON,
    KEY_CHILL_HOURS_TODAY,
    KEY_CLEARNESS_INDEX,
    KEY_CLIMATOLOGY_30D,
    KEY_CLOUD_BASE_M,
    KEY_CLOUD_COVER_PCT,
    KEY_CONDITIONS_SUMMARY,
    KEY_CONSISTENCY_FLAGS,
    KEY_CURRENT_CONDITION,
    KEY_CWOP_STATUS_V2,
    KEY_DATA_QUALITY,
    KEY_DATA_QUALITY_SCORE,
    KEY_DELTA_T,
    KEY_DEW_POINT_C,
    KEY_DOMINANT_WIND_DIR,
    KEY_DRY_STREAK,
    # v0.6.0
    KEY_ET0_DAILY_MM,
    KEY_ET0_HOURLY_MM,
    KEY_ET0_PM_DAILY_MM,
    KEY_FEELS_LIKE_C,
    KEY_FFDI,
    KEY_FFWI,
    KEY_FIRE_DANGER_VIGILANCE,
    KEY_FIRE_RISK_SCORE,
    KEY_FOG_PROBABILITY,
    KEY_FORECAST,
    KEY_FORECAST_AGREEMENT,
    KEY_FORECAST_BLEND_WEIGHT_LOCAL,
    KEY_FORECAST_BRIER_API,
    KEY_FORECAST_BRIER_LOCAL,
    KEY_FORECAST_PROVIDER,
    KEY_FORECAST_SKILL,
    KEY_FORECAST_TILES,
    KEY_FREEZING_LEVEL_M,
    KEY_FROST_POINT_C,
    KEY_FROST_STREAK,
    KEY_FWI,
    KEY_FWI_BUI,
    KEY_FWI_DC,
    KEY_FWI_DMC,
    KEY_FWI_DSR,
    KEY_FWI_FFMC,
    KEY_FWI_ISI,
    KEY_GDD_SEASON_V2,
    KEY_GDD_TODAY_V2,
    KEY_HDD_SEASON,
    KEY_HDD_TODAY_MM,
    KEY_HEALTH_DISPLAY,
    KEY_HEAT_INDEX,
    KEY_HEAT_STREAK,
    KEY_HUMIDEX,
    KEY_HUMIDITY_LEVEL_DISPLAY,
    KEY_INDOOR_CO2_PPM,
    KEY_INDOOR_COMFORT,
    KEY_INDOOR_HUMIDITY,
    KEY_INDOOR_HUMIDITY_DELTA,
    KEY_INDOOR_ROOMS_DATA,
    KEY_INDOOR_TEMP_C,
    KEY_INDOOR_TEMP_DELTA,
    KEY_IRRIGATION_DEFICIT,
    KEY_IRRIGATION_NEED,
    KEY_IRRIGATION_NEED_SCORE,
    KEY_LEAF_WETNESS,
    KEY_LIGHTNING_AZIMUTH,
    KEY_LIGHTNING_CLEARANCE_MIN,
    KEY_LIGHTNING_COUNT_1H,
    KEY_LIGHTNING_DISTANCE_KM,
    KEY_LIGHTNING_PROXIMITY,
    KEY_LIGHTNING_RATE_1H,
    KEY_LUX,
    KEY_MAX_SOLAR_RADIATION,
    KEY_MINUTES_UNTIL_DRY,
    KEY_MINUTES_UNTIL_RAIN,
    KEY_MOON_AGE_DAYS,
    KEY_MOON_DISPLAY,
    KEY_MOON_ILLUMINATION_PCT,
    KEY_MOON_NEXT_FULL,
    KEY_MOON_NEXT_NEW,
    # v0.8.0
    KEY_MOON_PHASE,
    KEY_NEIGHBOR_QC,
    KEY_NET_RADIATION,
    KEY_NO2,
    KEY_NORM_HUMIDITY,
    KEY_NORM_PRESSURE_HPA,
    KEY_NORM_RAIN_TOTAL_MM,
    KEY_NORM_TEMP_C,
    KEY_NORM_WIND_DIR_DEG,
    KEY_NORM_WIND_GUST_MS,
    KEY_NORM_WIND_SPEED_MS,
    KEY_NOWCAST_CONFIDENCE,
    KEY_NOWCAST_INTENSITY,
    KEY_OWM_STATIONS_STATUS,
    KEY_OZONE,
    KEY_PACKAGE_STATUS,
    KEY_PEAK_SUN_HOURS,
    KEY_PM2_5,
    KEY_PM10,
    KEY_POLLEN_GRASS,
    KEY_POLLEN_OVERALL,
    KEY_POLLEN_TREE,
    KEY_POLLEN_WEED,
    KEY_PRESSURE_CHANGE_WINDOW_HPA,
    KEY_PRESSURE_TREND_DISPLAY,
    KEY_PRESSURE_TREND_HPAH,
    KEY_PWS_STATUS,
    KEY_RAIN_ACCUM_1H,
    KEY_RAIN_ACCUM_24H,
    KEY_RAIN_ANOMALY_30D,
    KEY_RAIN_ANOMALY_90D,
    KEY_RAIN_DISPLAY,
    KEY_RAIN_NEXT_60MIN,
    KEY_RAIN_PROBABILITY,
    KEY_RAIN_PROBABILITY_COMBINED,
    KEY_RAIN_RATE_FILT,
    KEY_RAIN_RATE_MAX_24H,
    KEY_RAIN_THIS_MONTH_MM,
    KEY_RAIN_THIS_WEEK_MM,
    KEY_RAIN_THIS_YEAR_MM,
    KEY_RAIN_TODAY_MM,
    KEY_SEA_LEVEL_PRESSURE_HPA,
    KEY_SEA_SURFACE_TEMP,
    KEY_SENSOR_DRIFT_FLAGS,
    KEY_SENSOR_QUALITY_FLAGS,
    KEY_SENSOR_SPIKE,
    KEY_SENSOR_STUCK,
    KEY_SOIL_MOISTURE,
    KEY_SOIL_MOISTURE_DEFICIT,
    KEY_SOIL_TEMP_C,
    KEY_SOLAR_ENERGY_TODAY_WHM2,
    KEY_SOLAR_FORECAST_STATUS,
    # v0.9.0
    KEY_SOLAR_FORECAST_TODAY_KWH,
    KEY_SOLAR_FORECAST_TOMORROW_KWH,
    KEY_SOLAR_LUX_FACTOR,
    KEY_SPECIFIC_HUMIDITY,
    KEY_TEMP_ANOMALY_30D,
    KEY_TEMP_ANOMALY_90D,
    KEY_TEMP_AVG_24H,
    KEY_TEMP_DISPLAY,
    KEY_TEMP_HIGH_24H,
    KEY_TEMP_LOW_24H,
    KEY_THSW_INDEX,
    KEY_THUNDERSTORM_RISK,
    KEY_THW_INDEX,
    KEY_UTCI,
    KEY_UV,
    KEY_UV_LEVEL_DISPLAY,
    KEY_VIGILANCE_MAX_LEVEL,
    KEY_VPD,
    KEY_WBGT,
    KEY_WC_STATUS,
    KEY_WET_BULB_C,
    KEY_WIND_BEAUFORT,
    KEY_WIND_BEAUFORT_DESC,
    KEY_WIND_CHILL,
    KEY_WIND_DIR_SMOOTH_DEG,
    KEY_WIND_DIR_VARIABILITY,
    KEY_WIND_GUST_FACTOR,
    KEY_WIND_GUST_MAX_24H,
    KEY_WIND_QUADRANT,
    KEY_WIND_RUN_KM,
    KEY_WIND_RUN_MONTH_KM,
    KEY_WINDY_STATUS,
    KEY_WOW_STATUS,
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
    translation_key: str | None = None
    native_unit: str | None = None
    state_class: SensorStateClass | None = None
    suggested_display_precision: int | None = None
    value_fn: Callable[[dict[str, Any]], Any] | None = None
    attrs_fn: Callable[[dict[str, Any]], dict[str, Any]] | None = None
    unit_group: str | None = None
    options: list[str] | None = None


# Conversion factors from canonical internal (metric) value to configured unit.
# wind: from m/s; pressure: from hPa; distance: from km; altitude: from m.
# Rain accumulation (mm->in) and rain rate (mm/h->in/h) share the 1/25.4 factor.
_WIND_FACTORS: dict[str, float] = {"m/s": 1.0, "km/h": 3.6, "mph": 2.23694, "kn": 1.94384}
_PRESSURE_FACTORS: dict[str, float] = {"hPa": 1.0, "inHg": 0.02953, "mmHg": 0.75006}
_DISTANCE_FACTORS: dict[str, float] = {"km": 1.0, "mi": 0.621371}
_ALTITUDE_FACTORS: dict[str, float] = {"m": 1.0, "ft": 3.28084}

SENSORS: list[WSSensorDescription] = [
    # =========================================================================
    # CORE MEASUREMENTS
    # =========================================================================
    WSSensorDescription(
        key=KEY_NORM_TEMP_C,
        translation_key="temperature",
        name="WS Temperature",
        icon="mdi:thermometer",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit=UNIT_TEMP_C,
        state_class=SensorStateClass.MEASUREMENT,  # FIX: was TOTAL_INCREASING
        suggested_display_precision=1,
    ),
    WSSensorDescription(
        key=KEY_DEW_POINT_C,
        translation_key="dew_point",
        name="WS Dew Point",
        icon="mdi:weather-fog",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit=UNIT_TEMP_C,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    WSSensorDescription(
        key=KEY_NORM_HUMIDITY,
        translation_key="humidity",
        name="WS Humidity",
        icon="mdi:water-percent",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit="%",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WSSensorDescription(
        key=KEY_NORM_PRESSURE_HPA,
        translation_key="station_pressure",
        name="WS Station Pressure",
        icon="mdi:gauge",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit=UNIT_PRESSURE_HPA,
        state_class=SensorStateClass.MEASUREMENT,
        unit_group="pressure",
    ),
    WSSensorDescription(
        key=KEY_SEA_LEVEL_PRESSURE_HPA,
        translation_key="sea_level_pressure",
        name="WS Sea-Level Pressure",
        icon="mdi:gauge-full",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit=UNIT_PRESSURE_HPA,
        state_class=SensorStateClass.MEASUREMENT,
        unit_group="pressure",
    ),
    WSSensorDescription(
        key=KEY_NORM_WIND_SPEED_MS,
        translation_key="wind_speed",
        name="WS Wind Speed",
        icon="mdi:weather-windy",
        device_class=SensorDeviceClass.WIND_SPEED,
        native_unit=UNIT_WIND_MS,
        state_class=SensorStateClass.MEASUREMENT,
        unit_group="wind",
    ),
    WSSensorDescription(
        key=KEY_NORM_WIND_GUST_MS,
        translation_key="wind_gust",
        name="WS Wind Gust",
        icon="mdi:weather-windy-variant",
        device_class=SensorDeviceClass.WIND_SPEED,
        native_unit=UNIT_WIND_MS,
        state_class=SensorStateClass.MEASUREMENT,
        unit_group="wind",
    ),
    WSSensorDescription(
        key=KEY_NORM_WIND_DIR_DEG,
        translation_key="wind_direction",
        name="WS Wind Direction",
        icon="mdi:compass",
        device_class=SensorDeviceClass.WIND_DIRECTION,
        native_unit="\u00b0",
        state_class=SensorStateClass.MEASUREMENT_ANGLE,
    ),
    WSSensorDescription(
        key=KEY_NORM_RAIN_TOTAL_MM,
        translation_key="rain_total",
        name="WS Rain Total",
        icon="mdi:water",
        device_class=SensorDeviceClass.PRECIPITATION,
        native_unit=UNIT_RAIN_MM,
        state_class=SensorStateClass.TOTAL_INCREASING,  # FIX: cumulative counter
        unit_group="rain",
    ),
    WSSensorDescription(
        key=KEY_RAIN_RATE_FILT,
        translation_key="rain_rate",
        name="WS Rain Rate",
        icon="mdi:weather-pouring",
        device_class=SensorDeviceClass.PRECIPITATION_INTENSITY,
        native_unit="mm/h",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        unit_group="rain_rate",
    ),
    WSSensorDescription(
        key=KEY_LUX,
        translation_key="illuminance",
        name="WS Illuminance",
        icon="mdi:white-balance-sunny",
        device_class=SensorDeviceClass.ILLUMINANCE,
        native_unit="lx",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WSSensorDescription(
        key=KEY_UV,
        translation_key="uv_index",
        name="WS UV Index",
        icon="mdi:weather-sunny-alert",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WSSensorDescription(
        key=KEY_BATTERY_PCT,
        translation_key="battery",
        name="WS Battery",
        icon="mdi:battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit="%",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        attrs_fn=lambda d: {
            "bars": max(1, min(4, -(-int(d.get(KEY_BATTERY_PCT) or 0) // 25)))
            if d.get(KEY_BATTERY_PCT) is not None and d.get(KEY_BATTERY_PCT) > 0
            else 1,
        },
    ),
    WSSensorDescription(
        key=KEY_PRESSURE_TREND_HPAH,
        translation_key="pressure_trend_raw",
        name="WS Pressure Trend Raw",
        icon="mdi:trending-up",
        native_unit="hPa/h",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    WSSensorDescription(
        key=KEY_PRESSURE_CHANGE_WINDOW_HPA,
        translation_key="pressure_change_window",
        name="WS Pressure Change (window)",
        icon="mdi:swap-vertical",
        native_unit="hPa",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        unit_group="pressure",
    ),
    WSSensorDescription(
        key=KEY_DATA_QUALITY,
        translation_key="data_quality_banner",
        name="WS Data Quality Banner",
        icon="mdi:clipboard-check-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    WSSensorDescription(
        key=KEY_PACKAGE_STATUS,
        translation_key="package_status",
        name="WS Package Status",
        icon="mdi:package-variant-closed",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    WSSensorDescription(
        key=KEY_SENSOR_QUALITY_FLAGS,
        translation_key="sensor_quality_flags",
        name="WS Sensor Quality Flags",
        icon="mdi:shield-alert-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: len(d.get(KEY_SENSOR_QUALITY_FLAGS) or []),
        attrs_fn=lambda d: {
            "flags": d.get(KEY_SENSOR_QUALITY_FLAGS) or [],
            "all_clear": len(d.get(KEY_SENSOR_QUALITY_FLAGS) or []) == 0,
        },
    ),
    # v2.0 — Stuck-sensor flags (always computed; gated by diagnostics)
    WSSensorDescription(
        key=KEY_SENSOR_STUCK,
        translation_key="sensor_stuck",
        name="WS Sensor Stuck Flags",
        icon="mdi:shield-lock-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: len(d.get(KEY_SENSOR_STUCK) or []),
        attrs_fn=lambda d: {
            "stuck_sensors": d.get(KEY_SENSOR_STUCK) or [],
            "all_clear": len(d.get(KEY_SENSOR_STUCK) or []) == 0,
        },
    ),
    # v2.0 — Spatial neighbor QC (compare vs Open-Meteo NWP grid)
    WSSensorDescription(
        key=KEY_NEIGHBOR_QC,
        translation_key="neighbor_qc",
        name="WS Neighbor QC Flags",
        icon="mdi:map-check-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: len(d.get(KEY_NEIGHBOR_QC) or []),
        attrs_fn=lambda d: {
            "flags": d.get(KEY_NEIGHBOR_QC) or [],
            "all_clear": len(d.get(KEY_NEIGHBOR_QC) or []) == 0,
        },
    ),
    # v2.0 — Temporal spike (σ-based step-change) detection
    WSSensorDescription(
        key=KEY_SENSOR_SPIKE,
        translation_key="sensor_spike",
        name="WS Sensor Spike Flags",
        icon="mdi:pulse",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: len(d.get(KEY_SENSOR_SPIKE) or []),
        attrs_fn=lambda d: {
            "flags": d.get(KEY_SENSOR_SPIKE) or [],
            "all_clear": len(d.get(KEY_SENSOR_SPIKE) or []) == 0,
        },
    ),
    # v2.0 — Overall data quality score (0-100)
    WSSensorDescription(
        key=KEY_DATA_QUALITY_SCORE,
        translation_key="data_quality_score",
        name="WS Data Quality Score",
        icon="mdi:star-check-outline",
        native_unit=None,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        attrs_fn=lambda d: {
            "quality_flags": len(d.get(KEY_SENSOR_QUALITY_FLAGS) or []),
            "stuck_flags": len(d.get(KEY_SENSOR_STUCK) or []),
            "spike_flags": len(d.get(KEY_SENSOR_SPIKE) or []),
        },
    ),
    WSSensorDescription(
        key=KEY_ALERT_STATE,
        translation_key="alert_state",
        name="WS Alert State",
        icon="mdi:alert-circle-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    WSSensorDescription(
        key=KEY_ALERT_MESSAGE,
        translation_key="alert_message",
        name="WS Alert Message",
        icon="mdi:message-alert-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    WSSensorDescription(
        key=KEY_FORECAST,
        translation_key="forecast_daily",
        name="WS Forecast Daily",
        icon="mdi:weather-partly-cloudy",  # Votre modification préservée ici !
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: (d.get(KEY_FORECAST) or {}).get("provider") if d.get(KEY_FORECAST) else None,
        attrs_fn=lambda d: {"forecast": (d.get(KEY_FORECAST) or {}).get("daily", [])},
    ),
    WSSensorDescription(
        key=KEY_FORECAST_PROVIDER,
        translation_key="forecast_provider",
        name="WS Forecast Provider",
        icon="mdi:cloud-search",
        entity_category=EntityCategory.DIAGNOSTIC,
        attrs_fn=lambda d: {
            "provider_name": d.get("_forecast_provider_name"),
            "forecast_enabled": d.get("_forecast_provider_enabled"),
        },
    ),
]


# =========================================================================
# ADVANCED / COMPLEX SENSORS (Gated by advanced sensor config flag)
# =========================================================================
ADVANCED_SENSORS: list[WSSensorDescription] = [
    WSSensorDescription(
        key=KEY_FEELS_LIKE_C,
        translation_key="apparent_temperature",
        name="WS Apparent Temperature (Feels Like)",
        icon="mdi:thermometer-lines",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit=UNIT_TEMP_C,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    WSSensorDescription(
        key=KEY_WIND_CHILL,
        translation_key="wind_chill",
        name="WS Wind Chill",
        icon="mdi:snowflake",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit=UNIT_TEMP_C,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    WSSensorDescription(
        key=KEY_HEAT_INDEX,
        translation_key="heat_index",
        name="WS Heat Index",
        icon="mdi:thermometer-alert",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit=UNIT_TEMP_C,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    WSSensorDescription(
        key=KEY_HUMIDEX,
        translation_key="humidex",
        name="WS Humidex",
        icon="mdi:thermometer-water",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit=UNIT_TEMP_C,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    WSSensorDescription(
        key=KEY_THW_INDEX,
        translation_key="thw_index",
        name="WS THW Index",
        icon="mdi:thermometer-chevron-up",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit=UNIT_TEMP_C,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    WSSensorDescription(
        key=KEY_THSW_INDEX,
        translation_key="thsw_index",
        name="WS THSW Index",
        icon="mdi:thermometer-high",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit=UNIT_TEMP_C,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    WSSensorDescription(
        key=KEY_WET_BULB_C,
        translation_key="wet_bulb_temperature",
        name="WS Wet Bulb Temperature",
        icon="mdi:thermometer-water",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit=UNIT_TEMP_C,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    WSSensorDescription(
        key=KEY_FROST_POINT_C,
        translation_key="frost_point",
        name="WS Frost Point",
        icon="mdi:snowflake-alert",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit=UNIT_TEMP_C,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    WSSensorDescription(
        key=KEY_DELTA_T,
        translation_key="delta_t",
        name="WS Delta T",
        icon="mdi:triangle-outline",
        native_unit="K",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    WSSensorDescription(
        key=KEY_VPD,
        translation_key="vapor_pressure_deficit",
        name="WS Vapor Pressure Deficit (VPD)",
        icon="mdi:water-minus-outline",
        native_unit="kPa",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    WSSensorDescription(
        key=KEY_ABSOLUTE_HUMIDITY,
        translation_key="absolute_humidity",
        name="WS Absolute Humidity",
        icon="mdi:water-flat",
        native_unit="g/m³",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    WSSensorDescription(
        key=KEY_SPECIFIC_HUMIDITY,
        translation_key="specific_humidity",
        name="WS Specific Humidity",
        icon="mdi:water-sync",
        native_unit="g/kg",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    WSSensorDescription(
        key=KEY_AIR_DENSITY,
        translation_key="air_density",
        name="WS Air Density",
        icon="mdi:weight-kilogram",
        native_unit="kg/m³",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
    ),
    WSSensorDescription(
        key=KEY_CLOUD_BASE_M,
        translation_key="cloud_base",
        name="WS Cloud Base",
        icon="mdi:cloud-arrow-up-outline",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit="m",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        unit_group="altitude",
    ),
    WSSensorDescription(
        key=KEY_FREEZING_LEVEL_M,
        translation_key="freezing_level",
        name="WS Freezing Level",
        icon="mdi:snowflake-melt",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit="m",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        unit_group="altitude",
    ),
    WSSensorDescription(
        key=KEY_WIND_RUN_KM,
        translation_key="wind_run_today",
        name="WS Wind Run Today",
        icon="mdi:run-fast",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit="km",
        state_class=SensorStateClass.TOTAL_INCREASING,
        unit_group="distance",
    ),
    WSSensorDescription(
        key=KEY_WIND_RUN_MONTH_KM,
        translation_key="wind_run_month",
        name="WS Wind Run Month",
        icon="mdi:run-fast",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit="km",
        state_class=SensorStateClass.TOTAL_INCREASING,
        unit_group="distance",
    ),
    WSSensorDescription(
        key=KEY_WIND_BEAUFORT,
        translation_key="wind_beaufort_scale",
        name="WS Wind Beaufort Scale",
        icon="mdi:weather-windy",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WSSensorDescription(
        key=KEY_WIND_BEAUFORT_DESC,
        translation_key="wind_beaufort_desc",
        name="WS Wind Beaufort Description",
        icon="mdi:comment-text-outline",
    ),
    WSSensorDescription(
        key=KEY_WIND_QUADRANT,
        translation_key="wind_quadrant",
        name="WS Wind Quadrant",
        icon="mdi:compass-rose",
    ),
    WSSensorDescription(
        key=KEY_DOMINANT_WIND_DIR,
        translation_key="dominant_wind_direction",
        name="WS Dominant Wind Direction",
        icon="mdi:compass-outline",
        native_unit="\u00b0",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WSSensorDescription(
        key=KEY_WIND_DIR_SMOOTH_DEG,
        translation_key="wind_direction_smoothed",
        name="WS Wind Direction (Smoothed)",
        icon="mdi:compass-off-outline",
        native_unit="\u00b0",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WSSensorDescription(
        key=KEY_WIND_DIR_VARIABILITY,
        translation_key="wind_direction_variability",
        name="WS Wind Direction Variability",
        icon="mdi:arrow-left-right-bold-outline",
        native_unit="\u00b0",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WSSensorDescription(
        key=KEY_WIND_GUST_FACTOR,
        translation_key="wind_gust_factor",
        name="WS Wind Gust Factor",
        icon="mdi:speedometer",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    WSSensorDescription(
        key=KEY_RAIN_ACCUM_1H,
        translation_key="rain_1h",
        name="WS Rain 1h Accumulation",
        icon="mdi:water-accent",
        device_class=SensorDeviceClass.PRECIPITATION,
        native_unit=UNIT_RAIN_MM,
        state_class=SensorStateClass.MEASUREMENT,
        unit_group="rain",
    ),
    WSSensorDescription(
        key=KEY_RAIN_ACCUM_24H,
        translation_key="rain_24h",
        name="WS Rain 24h Accumulation",
        icon="mdi:water-clock",
        device_class=SensorDeviceClass.PRECIPITATION,
        native_unit=UNIT_RAIN_MM,
        state_class=SensorStateClass.MEASUREMENT,
        unit_group="rain",
    ),
    WSSensorDescription(
        key=KEY_RAIN_THIS_WEEK_MM,
        translation_key="rain_week",
        name="WS Rain This Week",
        icon="mdi:water-outline",
        device_class=SensorDeviceClass.PRECIPITATION,
        native_unit=UNIT_RAIN_MM,
        state_class=SensorStateClass.TOTAL_INCREASING,
        unit_group="rain",
    ),
    WSSensorDescription(
        key=KEY_RAIN_THIS_MONTH_MM,
        translation_key="rain_month",
        name="WS Rain This Month",
        icon="mdi:water-percent",
        device_class=SensorDeviceClass.PRECIPITATION,
        native_unit=UNIT_RAIN_MM,
        state_class=SensorStateClass.TOTAL_INCREASING,
        unit_group="rain",
    ),
    WSSensorDescription(
        key=KEY_RAIN_THIS_YEAR_MM,
        translation_key="rain_year",
        name="WS Rain This Year",
        icon="mdi:water-boiler",
        device_class=SensorDeviceClass.PRECIPITATION,
        native_unit=UNIT_RAIN_MM,
        state_class=SensorStateClass.TOTAL_INCREASING,
        unit_group="rain",
    ),
    WSSensorDescription(
        key=KEY_RAIN_TODAY_MM,
        translation_key="rain_today",
        name="WS Rain Today",
        icon="mdi:water-check",
        device_class=SensorDeviceClass.PRECIPITATION,
        native_unit=UNIT_RAIN_MM,
        state_class=SensorStateClass.TOTAL_INCREASING,
        unit_group="rain",
    ),
    WSSensorDescription(
        key=KEY_RAIN_RATE_MAX_24H,
        translation_key="max_rain_rate_24h",
        name="WS Max Rain Rate (24h)",
        icon="mdi:weather-lightning-rainy",
        device_class=SensorDeviceClass.PRECIPITATION_INTENSITY,
        native_unit="mm/h",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        unit_group="rain_rate",
    ),
    WSSensorDescription(
        key=KEY_WIND_GUST_MAX_24H,
        translation_key="max_wind_gust_24h",
        name="WS Max Wind Gust (24h)",
        icon="mdi:weather-windy-variant",
        device_class=SensorDeviceClass.WIND_SPEED,
        native_unit=UNIT_WIND_MS,
        state_class=SensorStateClass.MEASUREMENT,
        unit_group="wind",
    ),
    WSSensorDescription(
        key=KEY_TEMP_AVG_24H,
        translation_key="avg_temperature_24h",
        name="WS Average Temperature (24h)",
        icon="mdi:thermometer-clock",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit=UNIT_TEMP_C,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    WSSensorDescription(
        key=KEY_TEMP_HIGH_24H,
        translation_key="max_temperature_24h",
        name="WS Max Temperature (24h)",
        icon="mdi:thermometer-chevron-up",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit=UNIT_TEMP_C,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    WSSensorDescription(
        key=KEY_TEMP_LOW_24H,
        translation_key="min_temperature_24h",
        name="WS Min Temperature (24h)",
        icon="mdi:thermometer-chevron-down",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit=UNIT_TEMP_C,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    WSSensorDescription(
        key=KEY_DRY_STREAK,
        translation_key="dry_streak",
        name="WS Dry Streak",
        icon="mdi:sun-clock",
        native_unit="d",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WSSensorDescription(
        key=KEY_FROST_STREAK,
        translation_key="frost_streak",
        name="WS Frost Streak",
        icon="mdi:snowflake-clock",
        native_unit="d",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WSSensorDescription(
        key=KEY_HEAT_STREAK,
        translation_key="heat_streak",
        name="WS Heat Wave Streak",
        icon="mdi:fire-alert",
        native_unit="d",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WSSensorDescription(
        key=KEY_CLIMATOLOGY_30D,
        translation_key="climatology_summary",
        name="WS 30-Day Climatology Summary",
        icon="mdi:history",
    ),
    WSSensorDescription(
        key=KEY_TEMP_ANOMALY_30D,
        translation_key="temp_anomaly_30d",
        name="WS 30-Day Temperature Anomaly",
        icon="mdi:thermometer-lines",
        native_unit="K",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    WSSensorDescription(
        key=KEY_TEMP_ANOMALY_90D,
        translation_key="temp_anomaly_90d",
        name="WS 90-Day Temperature Anomaly",
        icon="mdi:thermometer-lines",
        native_unit="K",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    WSSensorDescription(
        key=KEY_RAIN_ANOMALY_30D,
        translation_key="rain_anomaly_30d",
        name="WS 30-Day Precipitation Anomaly",
        icon="mdi:water-percent",
        native_unit="%",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    WSSensorDescription(
        key=KEY_RAIN_ANOMALY_90D,
        translation_key="rain_anomaly_90d",
        name="WS 90-Day Precipitation Anomaly",
        icon="mdi:water-percent",
        native_unit="%",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    WSSensorDescription(
        key=KEY_ZAMBRETTI_NUMBER,
        translation_key="zambretti_code",
        name="WS Zambretti Code",
        icon="mdi:numeric",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    WSSensorDescription(
        key=KEY_ZAMBRETTI_FORECAST,
        translation_key="zambretti_forecast",
        name="WS Zambretti Forecast Text",
        icon="mdi:weather-windy-variant",
    ),
    WSSensorDescription(
        key=KEY_NET_RADIATION,
        translation_key="net_radiation",
        name="WS Net Radiation",
        icon="mdi:radiator",
        native_unit="W/m²",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    WSSensorDescription(
        key=KEY_MAX_SOLAR_RADIATION,
        translation_key="theoretical_max_solar_radiation",
        name="WS Theoretical Max Solar Radiation",
        icon="mdi:sun-wireless",
        native_unit="W/m²",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    WSSensorDescription(
        key=KEY_CLEARNESS_INDEX,
        translation_key="clearness_index",
        name="WS Sky Clearness Index",
        icon="mdi:sun-angle",
        native_unit="%",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    WSSensorDescription(
        key=KEY_SOLAR_LUX_FACTOR,
        translation_key="solar_lux_factor",
        name="WS Solar Radiation-to-Lux Factor",
        icon="mdi:omega",
        native_unit="lx/(W/m²)",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    WSSensorDescription(
        key=KEY_SOLAR_ENERGY_TODAY_WHM2,
        translation_key="solar_energy_today",
        name="WS Solar Irradiation Yield Today",
        icon="mdi:solar-power-variant",
        native_unit="Wh/m²",
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=0,
    ),
    WSSensorDescription(
        key=KEY_PEAK_SUN_HOURS,
        translation_key="peak_sun_hours",
        name="WS Peak Sun Hours Today",
        icon="mdi:sun-clock-outline",
        native_unit="h",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    WSSensorDescription(
        key=KEY_UTCI,
        translation_key="utci",
        name="WS Universal Thermal Climate Index (UTCI)",
        icon="mdi:human-thermal",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit=UNIT_TEMP_C,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    WSSensorDescription(
        key=KEY_WBGT,
        translation_key="wbgt",
        name="WS Wet Bulb Globe Temperature (WBGT)",
        icon="mdi:calendar-alert",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit=UNIT_TEMP_C,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    WSSensorDescription(
        key=KEY_CONSISTENCY_FLAGS,
        translation_key="consistency_flags",
        name="WS Thermodynamic Consistency Flags",
        icon="mdi:check-all",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: len(d.get(KEY_CONSISTENCY_FLAGS) or []),
        attrs_fn=lambda d: {
            "violations": d.get(KEY_CONSISTENCY_FLAGS) or [],
            "consistent": len(d.get(KEY_CONSISTENCY_FLAGS) or []) == 0,
        },
    ),
    # v2.0 — Extended Diagnostic drift flags
    WSSensorDescription(
        key=KEY_SENSOR_DRIFT_FLAGS,
        translation_key="sensor_drift_flags",
        name="WS Sensor Drift/Calibration Flags",
        icon="mdi:gauge-low",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: len(d.get(KEY_SENSOR_DRIFT_FLAGS) or []),
        attrs_fn=lambda d: {
            "drifts": d.get(KEY_SENSOR_DRIFT_FLAGS) or [],
            "all_clear": len(d.get(KEY_SENSOR_DRIFT_FLAGS) or []) == 0,
        },
    ),
]

# =========================================================================
# CONDITIONAL METEO-FRANCE VIGILANCE SENSORS (v1.6.0)
# =========================================================================
VIGILANCE_METEO_SENSORS: list[WSSensorDescription] = [
    WSSensorDescription(
        key=KEY_VIGILANCE_MAX_LEVEL,
        translation_key="vigilance_max_level",
        name="WS Vigilance Météo Max Level",
        icon="mdi:shield-alert",
        attrs_fn=lambda d: {
            "department": d.get("_vigilance_department"),
            "risk_colors": d.get("_vigilance_risk_colors_dict") or {},
            "active_risks_count": len(d.get("_vigilance_active_risks_list") or []),
            "active_risks": d.get("_vigilance_active_risks_list") or [],
        },
    ),
]

# =========================================================================
# CONDITIONAL AIR QUALITY SENSORS (v0.7.0)
# =========================================================================
AIR_QUALITY_SENSORS: list[WSSensorDescription] = [
    WSSensorDescription(
        key=KEY_AQI,
        translation_key="aqi",
        name="WS Air Quality Index (AQI)",
        icon="mdi:air-filter",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WSSensorDescription(
        key=KEY_AQI_LEVEL,
        translation_key="aqi_level",
        name="WS Air Quality Level",
        icon="mdi:smog",
    ),
    WSSensorDescription(
        key=KEY_PM2_5,
        translation_key="pm25",
        name="WS PM2.5",
        icon="mdi:scatter-plot",
        device_class=SensorDeviceClass.PM25,
        native_unit="µg/m³",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WSSensorDescription(
        key=KEY_PM10,
        translation_key="pm10",
        name="WS PM10",
        icon="mdi:scatter-plot",
        device_class=SensorDeviceClass.PM10,
        native_unit="µg/m³",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WSSensorDescription(
        key=KEY_OZONE,
        translation_key="ozone",
        name="WS Ozone (O3)",
        icon="mdi:molecule",
        native_unit="µg/m³",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WSSensorDescription(
        key=KEY_NO2,
        translation_key="no2",
        name="WS Nitrogen Dioxide (NO2)",
        icon="mdi:molecule",
        device_class=SensorDeviceClass.NITROGEN_DIOXIDE,
        native_unit="µg/m³",
        state_class=SensorStateClass.MEASUREMENT,
    ),
]

# =========================================================================
# CONDITIONAL MOON SENSORS (v0.8.0)
# =========================================================================
MOON_SENSORS: list[WSSensorDescription] = [
    WSSensorDescription(
        key=KEY_MOON_PHASE,
        translation_key="moon_phase",
        name="WS Moon Phase",
        icon="mdi:moon-waning-gibbous",
    ),
    WSSensorDescription(
        key=KEY_MOON_ILLUMINATION_PCT,
        translation_key="moon_illumination",
        name="WS Moon Illumination",
        icon="mdi:brightness-4",
        native_unit="%",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WSSensorDescription(
        key=KEY_MOON_AGE_DAYS,
        translation_key="moon_age",
        name="WS Moon Age",
        icon="mdi:calendar-clock",
        native_unit="d",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    WSSensorDescription(
        key=KEY_MOON_DISPLAY,
        translation_key="moon_display_banner",
        name="WS Moon Display Banner",
        icon="mdi:dharmachakra",
    ),
    WSSensorDescription(
        key=KEY_MOON_NEXT_NEW,
        translation_key="next_new_moon",
        name="WS Next New Moon",
        icon="mdi:moon-new",
    ),
    WSSensorDescription(
        key=KEY_MOON_NEXT_FULL,
        translation_key="next_full_moon",
        name="WS Next Full Moon",
        icon="mdi:moon-full",
    ),
]

# =========================================================================
# CONDITIONAL SOLAR FORECAST SENSORS (v0.9.0)
# =========================================================================
SOLAR_FORECAST_SENSORS: list[WSSensorDescription] = [
    WSSensorDescription(
        key=KEY_SOLAR_FORECAST_TODAY_KWH,
        translation_key="solar_forecast_today",
        name="WS Clear-Sky Solar Yield Forecast Today",
        icon="mdi:solar-power",
        native_unit="kWh/m²",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    WSSensorDescription(
        key=KEY_SOLAR_FORECAST_TOMORROW_KWH,
        translation_key="solar_forecast_tomorrow",
        name="WS Clear-Sky Solar Yield Forecast Tomorrow",
        icon="mdi:solar-power",
        native_unit="kWh/m²",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    WSSensorDescription(
        key=KEY_SOLAR_FORECAST_STATUS,
        translation_key="solar_forecast_status",
        name="WS Solar Forecast Status",
        icon="mdi:shield-check-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
]

# =========================================================================
# CONDITIONAL THUNDERSTORM / LIGHTNING SENSORS
# =========================================================================
THUNDERSTORM_SENSORS: list[WSSensorDescription] = [
    WSSensorDescription(
        key=KEY_THUNDERSTORM_RISK,
        translation_key="thunderstorm_risk_score",
        name="WS Thunderstorm Risk Score",
        icon="mdi:cloud-lightning",
        native_unit="%",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
]

LIGHTNING_SENSORS: list[WSSensorDescription] = [
    WSSensorDescription(
        key=KEY_LIGHTNING_COUNT_1H,
        translation_key="lightning_count_1h",
        name="WS Lightning Strike Count (1h)",
        icon="mdi:flash",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WSSensorDescription(
        key=KEY_LIGHTNING_RATE_1H,
        translation_key="lightning_strike_rate_1h",
        name="WS Lightning Strike Rate (1h)",
        icon="mdi:flash-alert-outline",
        native_unit="strikes/h",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WSSensorDescription(
        key=KEY_LIGHTNING_DISTANCE_KM,
        translation_key="lightning_distance_closest",
        name="WS Closest Lightning Distance",
        icon="mdi:ray-start-arrow",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit="km",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        unit_group="distance",
    ),
    WSSensorDescription(
        key=KEY_LIGHTNING_AZIMUTH,
        translation_key="lightning_bearing_closest",
        name="WS Closest Lightning Bearing",
        icon="mdi:compass-rose",
        native_unit="\u00b0",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WSSensorDescription(
        key=KEY_LIGHTNING_PROXIMITY,
        translation_key="lightning_proximity_zone",
        name="WS Lightning Proximity Zone",
        icon="mdi:radar",
    ),
    WSSensorDescription(
        key=KEY_LIGHTNING_CLEARANCE_MIN,
        translation_key="lightning_clearance_timer",
        name="WS Lightning Clearance Timer",
        icon="mdi:timer-sand",
        native_unit="min",
        state_class=SensorStateClass.MEASUREMENT,
    ),
]

# =========================================================================
# CONDITIONAL FOG SENSORS (v1.2.0)
# =========================================================================
FOG_SENSORS: list[WSSensorDescription] = [
    WSSensorDescription(
        key=KEY_FOG_PROBABILITY,
        translation_key="fog_probability",
        name="WS Radiation Fog Probability",
        icon="mdi:weather-fog",
        native_unit="%",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
]

# =========================================================================
# CONDITIONAL EVAPOTRANSPIRATION & AGRI-METEO SENSORS (v0.6.0 / v1.5.0)
# =========================================================================
COMFORT_INDICES_SENSORS: list[WSSensorDescription] = [
    WSSensorDescription(
        key=KEY_ET0_HOURLY_MM,
        translation_key="evapotranspiration_hourly",
        name="WS Reference Evapotranspiration (Hourly)",
        icon="mdi:water-speed",
        device_class=SensorDeviceClass.PRECIPITATION,
        native_unit=UNIT_RAIN_MM,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        unit_group="rain",
    ),
    WSSensorDescription(
        key=KEY_ET0_DAILY_MM,
        translation_key="evapotranspiration_daily",
        name="WS Reference Evapotranspiration Today (FAO-56)",
        icon="mdi:sprout-outline",
        device_class=SensorDeviceClass.PRECIPITATION,
        native_unit=UNIT_RAIN_MM,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        unit_group="rain",
    ),
    WSSensorDescription(
        key=KEY_ET0_PM_DAILY_MM,
        translation_key="evapotranspiration_daily_pm",
        name="WS Reference Evapotranspiration Today (Penman-Monteith)",
        icon="mdi:sprout",
        device_class=SensorDeviceClass.PRECIPITATION,
        native_unit=UNIT_RAIN_MM,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        unit_group="rain",
    ),
    WSSensorDescription(
        key=KEY_IRRIGATION_DEFICIT,
        translation_key="irrigation_deficit_today",
        name="WS Water Deficit Today",
        icon="mdi:water-minus",
        native_unit="mm",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    WSSensorDescription(
        key=KEY_IRRIGATION_NEED,
        translation_key="irrigation_need_status",
        name="WS Irrigation Need Status",
        icon="mdi:sprinkler-variant",
    ),
    WSSensorDescription(
        key=KEY_IRRIGATION_NEED_SCORE,
        translation_key="irrigation_urgency_score",
        name="WS Irrigation Urgency Score",
        icon="mdi:water-alert",
        native_unit="%",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    WSSensorDescription(
        key=KEY_CHILL_HOURS_TODAY,
        translation_key="chill_hours_today",
        name="WS Chill Hours Accumulated Today",
        icon="mdi:snowflake-thermometer",
        native_unit="h",
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=1,
    ),
    WSSensorDescription(
        key=KEY_CHILL_HOURS_SEASON,
        translation_key="chill_hours_season",
        name="WS Chill Hours Accumulated This Season",
        icon="mdi:snowflake-melt",
        native_unit="h",
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=1,
    ),
]

DEGREE_DAYS_SENSORS: list[WSSensorDescription] = [
    WSSensorDescription(
        key=KEY_GDD_TODAY_V2,
        translation_key="gdd_today",
        name="WS Growing Degree Days (GDD) Today",
        icon="mdi:flower-growth",
        native_unit="°C⋅d",
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=1,
    ),
    WSSensorDescription(
        key=KEY_GDD_SEASON_V2,
        translation_key="gdd_season",
        name="WS Growing Degree Days (GDD) This Season",
        icon="mdi:flower-tulip",
        native_unit="°C⋅d",
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=1,
    ),
    WSSensorDescription(
        key=KEY_HDD_TODAY_MM,
        translation_key="hdd_today",
        name="WS Heating Degree Days (HDD) Today",
        icon="mdi:fire",
        native_unit="°C⋅d",
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=1,
    ),
    WSSensorDescription(
        key=KEY_HDD_SEASON,
        translation_key="hdd_season",
        name="WS Heating Degree Days (HDD) This Season",
        icon="mdi:radiator",
        native_unit="°C⋅d",
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=1,
    ),
    WSSensorDescription(
        key=KEY_CDD_TODAY_MM,
        translation_key="cdd_today",
        name="WS Cooling Degree Days (CDD) Today",
        icon="mdi:snowflake",
        native_unit="°C⋅d",
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=1,
    ),
    WSSensorDescription(
        key=KEY_CDD_SEASON,
        translation_key="cdd_season",
        name="WS Cooling Degree Days (CDD) This Season",
        icon="mdi:air-conditioner",
        native_unit="°C⋅d",
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=1,
    ),
]

# =========================================================================
# CONDITIONAL FIRE RISK SENSORS (v1.6.2)
# =========================================================================
FIRE_RISK_SENSORS: list[WSSensorDescription] = [
    WSSensorDescription(
        key=KEY_FIRE_RISK_SCORE,
        translation_key="fire_risk_index",
        name="WS Fire Weather Index (FWI) Combined Risk",
        icon="mdi:fire-alert",
        native_unit="%",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    WSSensorDescription(
        key=KEY_FIRE_DANGER_VIGILANCE,
        translation_key="fire_danger_level",
        name="WS Fire Danger Level",
        icon="mdi:shield-fire",
    ),
    WSSensorDescription(
        key=KEY_FFDI,
        translation_key="ffdi_score",
        name="WS McArthur Forest Fire Danger Index (FFDI)",
        icon="mdi:pine-tree-fire",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
]

# v1.6.2 Can be exposed standalone if FWI components are explicitly requested
FWI_COMPONENTS_SENSORS: list[WSSensorDescription] = [
    WSSensorDescription(
        key=KEY_FWI,
        translation_key="fwi_canadian",
        name="WS Canadian Fire Weather Index (FWI)",
        icon="mdi:fire",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    WSSensorDescription(
        key=KEY_FWI_FFMC,
        translation_key="fwi_ffmc",
        name="WS Fine Fuel Moisture Code (FFMC)",
        icon="mdi:leaf-maple",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    WSSensorDescription(
        key=KEY_FWI_DMC,
        translation_key="fwi_dmc",
        name="WS Duff Moisture Code (DMC)",
        icon="mdi:layers-outline",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    WSSensorDescription(
        key=KEY_FWI_DC,
        translation_key="fwi_dc",
        name="WS Drought Code (DC)",
        icon="mdi:terrain",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    WSSensorDescription(
        key=KEY_FWI_ISI,
        translation_key="fwi_isi",
        name="WS Initial Spread Index (ISI)",
        icon="mdi:windsock",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    WSSensorDescription(
        key=KEY_FWI_BUI,
        translation_key="fwi_bui",
        name="WS Build-Up Index (BUI)",
        icon="mdi:stack-overflow",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    WSSensorDescription(
        key=KEY_FWI_DSR,
        translation_key="fwi_dsr",
        name="WS Daily Severity Rating (DSR)",
        icon="mdi:alert-decagram",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    WSSensorDescription(
        key=KEY_FFWI,
        translation_key="ffwi_score",
        name="WS Fosberg Fire Weather Index (FFWI)",
        icon="mdi:fire-wire",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
]

# =========================================================================
# CONDITIONAL DISPLAY SENSORS (v1.6.2)
# =========================================================================
DISPLAY_SENSORS: list[WSSensorDescription] = [
    WSSensorDescription(
        key=KEY_TEMP_DISPLAY,
        translation_key="formatted_temp",
        name="WS Formatted Temperature",
        icon="mdi:thermometer",
    ),
    WSSensorDescription(
        key=KEY_RAIN_DISPLAY,
        translation_key="formatted_rain",
        name="WS Formatted Rain Today",
        icon="mdi:water",
    ),
    WSSensorDescription(
        key=KEY_PRESSURE_TREND_DISPLAY,
        translation_key="formatted_pressure_trend",
        name="WS Formatted Pressure Trend",
        icon="mdi:trending-neutral",
    ),
    WSSensorDescription(
        key=KEY_UV_LEVEL_DISPLAY,
        translation_key="formatted_uv",
        name="WS Formatted UV Risk Level",
        icon="mdi:weather-sunny-alert",
    ),
    WSSensorDescription(
        key=KEY_HUMIDITY_LEVEL_DISPLAY,
        translation_key="formatted_humidity",
        name="WS Formatted Humidity Comfort",
        icon="mdi:water-percent",
    ),
    WSSensorDescription(
        key=KEY_HEALTH_DISPLAY,
        translation_key="formatted_health_risk",
        name="WS Formatted Environment Health Risk",
        icon="mdi:heart-pulse",
    ),
    WSSensorDescription(
        key=KEY_CONDITIONS_SUMMARY,
        translation_key="formatted_current_conditions",
        name="WS Formatted Current Weather Summary",
        icon="mdi:text-long",
    ),
    WSSensorDescription(
        key=KEY_CURRENT_CONDITION,
        translation_key="current_condition_slug",
        name="WS Current Condition Icon Slug",
        icon="mdi:weather-cloudy",
    ),
]

# =========================================================================
# CONDITIONAL NOWCAST SENSORS (v1.7.0)
# =========================================================================
NOWCAST_SENSORS: list[WSSensorDescription] = [
    WSSensorDescription(
        key=KEY_NOWCAST_INTENSITY,
        translation_key="nowcast_rain_intensity",
        name="WS Nowcast Near-Term Rain Intensity",
        icon="mdi:weather-partly-rainy",
        device_class=SensorDeviceClass.PRECIPITATION_INTENSITY,
        native_unit="mm/h",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    WSSensorDescription(
        key=KEY_NOWCAST_CONFIDENCE,
        translation_key="nowcast_confidence_score",
        name="WS Nowcast Engine Confidence",
        icon="mdi:shield-check",
        native_unit="%",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    WSSensorDescription(
        key=KEY_MINUTES_UNTIL_RAIN,
        translation_key="nowcast_minutes_to_rain",
        name="WS Minutes Until Rain Starts",
        icon="mdi:clock-alert-outline",
        native_unit="min",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WSSensorDescription(
        key=KEY_MINUTES_UNTIL_DRY,
        translation_key="nowcast_minutes_to_dry",
        name="WS Minutes Until Rain Halts",
        icon="mdi:clock-check-outline",
        native_unit="min",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WSSensorDescription(
        key=KEY_RAIN_NEXT_60MIN,
        translation_key="nowcast_rain_next_60m",
        name="WS Expected Rain Vol Next 60 Mins",
        icon="mdi:water-boiler",
        device_class=SensorDeviceClass.PRECIPITATION,
        native_unit=UNIT_RAIN_MM,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    WSSensorDescription(
        key=KEY_RAIN_PROBABILITY_COMBINED,
        translation_key="nowcast_rain_probability_1h",
        name="WS Combined Rain Probability (1h)",
        icon="mdi:weather-rainy",
        native_unit="%",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
]

# =========================================================================
# CONDITIONAL POLLEN SENSORS (v1.7.0)
# =========================================================================
POLLEN_SENSORS: list[WSSensorDescription] = [
    WSSensorDescription(
        key=KEY_POLLEN_OVERALL,
        translation_key="pollen_risk_overall",
        name="WS Overall Pollen Allergenic Risk",
        icon="mdi:flower",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WSSensorDescription(
        key=KEY_POLLEN_TREE,
        translation_key="pollen_risk_tree",
        name="WS Tree Pollen Allergenic Risk",
        icon="mdi:tree",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WSSensorDescription(
        key=KEY_POLLEN_GRASS,
        translation_key="pollen_risk_grass",
        name="WS Grass Pollen Allergenic Risk",
        icon="mdi:grass",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WSSensorDescription(
        key=KEY_POLLEN_WEED,
        translation_key="pollen_risk_weed",
        name="WS Weed Pollen Allergenic Risk",
        icon="mdi:sprout",
        state_class=SensorStateClass.MEASUREMENT,
    ),
]

# =========================================================================
# CONDITIONAL SEA SURFACE TEMPERATURE SENSORS (v1.7.0)
# =========================================================================
SEA_TEMP_SENSORS: list[WSSensorDescription] = [
    WSSensorDescription(
        key=KEY_SEA_SURFACE_TEMP,
        translation_key="sea_surface_temp",
        name="WS Sea Surface Temperature",
        icon="mdi:waves",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit=UNIT_TEMP_C,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
]

# =========================================================================
# CONDITIONAL SOIL SENSORS (v2.1)
# =========================================================================
SOIL_SENSORS: list[WSSensorDescription] = [
    WSSensorDescription(
        key=KEY_SOIL_TEMP_C,
        translation_key="soil_temperature",
        name="WS Soil Temperature",
        icon="mdi:thermometer-water",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit=UNIT_TEMP_C,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    WSSensorDescription(
        key=KEY_SOIL_MOISTURE,
        translation_key="soil_moisture",
        name="WS Soil Moisture (Volumetric)",
        icon="mdi:water-percent",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit="%",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    WSSensorDescription(
        key=KEY_SOIL_MOISTURE_DEFICIT,
        translation_key="soil_moisture_deficit",
        name="WS Soil Moisture Deficit",
        icon="mdi:water-minus-outline",
        native_unit="mm",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    WSSensorDescription(
        key=KEY_LEAF_WETNESS,
        translation_key="leaf_wetness",
        name="WS Leaf Wetness",
        icon="mdi:leaf-water",
        native_unit="%",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
]

# =========================================================================
# CONDITIONAL INGESTION METRICS / EXTERNAL SERVICE TELEMETRY UPLOADER DIAGNOSTICS
# =========================================================================
WUNDERGROUND_DIAG_SENSORS: list[WSSensorDescription] = [
    WSSensorDescription(
        key=KEY_WU_STATUS,
        translation_key="telemetry_wunderground",
        name="WS WeatherUnderground Uploader Status",
        icon="mdi:cloud-upload",
        entity_category=EntityCategory.DIAGNOSTIC,
    )
]
WEATHERCLOUD_DIAG_SENSORS: list[WSSensorDescription] = [
    WSSensorDescription(
        key=KEY_WC_STATUS,
        translation_key="telemetry_weathercloud",
        name="WS WeatherCloud Uploader Status",
        icon="mdi:cloud-upload",
        entity_category=EntityCategory.DIAGNOSTIC,
    )
]
WINDY_DIAG_SENSORS: list[WSSensorDescription] = [
    WSSensorDescription(
        key=KEY_WINDY_STATUS,
        translation_key="telemetry_windy",
        name="WS Windy API Uploader Status",
        icon="mdi:cloud-upload",
        entity_category=EntityCategory.DIAGNOSTIC,
    )
]
WOW_DIAG_SENSORS: list[WSSensorDescription] = [
    WSSensorDescription(
        key=KEY_WOW_STATUS,
        translation_key="telemetry_wow",
        name="WS MetOffice WOW Uploader Status",
        icon="mdi:cloud-upload",
        entity_category=EntityCategory.DIAGNOSTIC,
    )
]
CWOP_DIAG_SENSORS: list[WSSensorDescription] = [
    WSSensorDescription(
        key=KEY_CWOP_STATUS_V2,
        translation_key="telemetry_cwop",
        name="WS CWOP APRS Packet Status",
        icon="mdi:radio-tower",
        entity_category=EntityCategory.DIAGNOSTIC,
    )
]
PWSWEATHER_DIAG_SENSORS: list[WSSensorDescription] = [
    WSSensorDescription(
        key=KEY_PWS_STATUS,
        translation_key="telemetry_pwsweather",
        name="WS PWSWeather API Uploader Status",
        icon="mdi:cloud-upload",
        entity_category=EntityCategory.DIAGNOSTIC,
    )
]
AWEKAS_DIAG_SENSORS: list[WSSensorDescription] = [
    WSSensorDescription(
        key=KEY_AWEKAS_STATUS,
        translation_key="telemetry_awekas",
        name="WS AWEKAS Data Ingestion Status",
        icon="mdi:cloud-upload",
        entity_category=EntityCategory.DIAGNOSTIC,
    )
]
OWM_STATIONS_DIAG_SENSORS: list[WSSensorDescription] = [
    WSSensorDescription(
        key=KEY_OWM_STATIONS_STATUS,
        translation_key="telemetry_owm_stations",
        name="WS OpenMeteo/OWM Stations Telemetry Status",
        icon="mdi:server-network",
        entity_category=EntityCategory.DIAGNOSTIC,
    )
]

# =========================================================================
# CONDITIONAL INTERNAL SENSORS (Gated by indoor configuration flag)
# =========================================================================
INDOOR_SENSORS: list[WSSensorDescription] = [
    WSSensorDescription(
        key=KEY_INDOOR_TEMP_C,
        translation_key="indoor_temperature",
        name="WS Indoor Temperature",
        icon="mdi:home-thermometer",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit=UNIT_TEMP_C,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    WSSensorDescription(
        key=KEY_INDOOR_HUMIDITY,
        translation_key="indoor_humidity",
        name="WS Indoor Humidity",
        icon="mdi:home-water",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit="%",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WSSensorDescription(
        key=KEY_INDOOR_COMFORT,
        translation_key="indoor_comfort_index",
        name="WS Indoor Comfort Index",
        icon="mdi:home-heart",
    ),
    WSSensorDescription(
        key=KEY_INDOOR_CO2_PPM,
        translation_key="indoor_co2",
        name="WS Indoor CO2 Level",
        icon="mdi:molecule-co2",
        device_class=SensorDeviceClass.CO2,
        native_unit="ppm",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    WSSensorDescription(
        key=KEY_INDOOR_TEMP_DELTA,
        translation_key="indoor_temp_delta",
        name="WS Indoor-Outdoor Temp Gradient",
        icon="mdi:arrow-expand-vertical",
        native_unit="K",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    WSSensorDescription(
        key=KEY_INDOOR_HUMIDITY_DELTA,
        translation_key="indoor_humidity_delta",
        name="WS Indoor-Outdoor Humidity Gradient",
        icon="mdi:arrow-expand-vertical",
        native_unit="%",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    WSSensorDescription(
        key=KEY_INDOOR_ROOMS_DATA,
        translation_key="indoor_multiroom_summary",
        name="WS Indoor Rooms Mapping Array",
        icon="mdi:home-floor-3",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: len(d.get(KEY_INDOOR_ROOMS_DATA) or {}),
        attrs_fn=lambda d: {"rooms": d.get(KEY_INDOOR_ROOMS_DATA) or {}},
    ),
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    """Set up Weather Station core sensors from a config entry context."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    # Resolve entity naming prefix
    prefix = entry.options.get(CONF_PREFIX, entry.data.get(CONF_PREFIX, DEFAULT_PREFIX))

    # Evaluate dynamic configuration toggle gates
    config = entry.options

    # Base Core definitions
    descriptions = list(SENSORS)

    # Advanced Core indices
    if config.get(CONF_ENABLE_ADVANCED_SENSORS, True):
        descriptions.extend(ADVANCED_SENSORS)

    # Ingestion / Telemetry upload services (grouped under diagnostic flag control)
    if config.get(CONF_ENABLE_DIAGNOSTICS, False):
        if config.get(CONF_ENABLE_WUNDERGROUND, False):
            descriptions.extend(WUNDERGROUND_DIAG_SENSORS)
        if config.get(CONF_ENABLE_WEATHERCLOUD, False):
            descriptions.extend(WEATHERCLOUD_DIAG_SENSORS)
        if config.get(CONF_ENABLE_WINDY, False):
            descriptions.extend(WINDY_DIAG_SENSORS)
        if config.get(CONF_ENABLE_WOW, False):
            descriptions.extend(WOW_DIAG_SENSORS)
        if config.get(CONF_ENABLE_CWOP, False):
            descriptions.extend(CWOP_DIAG_SENSORS)
        if config.get(CONF_ENABLE_PWSWEATHER, False):
            descriptions.extend(PWSWEATHER_DIAG_SENSORS)
        if config.get(CONF_ENABLE_AWEKAS, False):
            descriptions.extend(AWEKAS_DIAG_SENSORS)
        if config.get(CONF_ENABLE_OWM_STATIONS, False):
            descriptions.extend(OWM_STATIONS_DIAG_SENSORS)

    # Environmental modules
    if config.get(CONF_ENABLE_AIR_QUALITY, False):
        descriptions.extend(AIR_QUALITY_SENSORS)
    if config.get(CONF_ENABLE_MOON, False):
        descriptions.extend(MOON_SENSORS)
    if config.get(CONF_ENABLE_SOLAR_FORECAST, False):
        descriptions.extend(SOLAR_FORECAST_SENSORS)
    if config.get(CONF_ENABLE_THUNDERSTORM, False):
        descriptions.extend(THUNDERSTORM_SENSORS)
    if config.get(CONF_ENABLE_LIGHTNING, False):
        descriptions.extend(LIGHTNING_SENSORS)
    if config.get(CONF_ENABLE_FOG, False):
        descriptions.extend(FOG_SENSORS)
    if config.get(CONF_ENABLE_COMFORT_INDICES, False):
        descriptions.extend(COMFORT_INDICES_SENSORS)
    if config.get(CONF_ENABLE_DEGREE_DAYS, False):
        descriptions.extend(DEGREE_DAYS_SENSORS)
    if config.get(CONF_ENABLE_FIRE_RISK, False):
        descriptions.extend(FIRE_RISK_SENSORS)
    if config.get(CONF_ENABLE_FWI_COMPONENTS, False):
        descriptions.extend(FWI_COMPONENTS_SENSORS)
    if config.get(CONF_ENABLE_DISPLAY_SENSORS, False):
        descriptions.extend(DISPLAY_SENSORS)
    if config.get(CONF_ENABLE_INDOOR, False):
        descriptions.extend(INDOOR_SENSORS)
    if config.get(CONF_ENABLE_NOWCAST, False):
        descriptions.extend(NOWCAST_SENSORS)
    if config.get(CONF_ENABLE_POLLEN, False):
        descriptions.extend(POLLEN_SENSORS)
    if config.get(CONF_ENABLE_SEA_TEMP, False):
        descriptions.extend(SEA_TEMP_SENSORS)
    if config.get(CONF_ENABLE_SOIL, False):
        descriptions.extend(SOIL_SENSORS)
    if config.get(CONF_ENABLE_VIGILANCE_METEO, False):
        descriptions.extend(VIGILANCE_METEO_SENSORS)

    # Map static descriptor structures to entity instances
    entities = [
        WeatherStationSensor(coordinator=coordinator, entry=entry, description=desc, prefix=prefix)
        for desc in descriptions
    ]

    # Handle dynamic sub-structures (MeteoFrance Vigicrues multi-station mapping)
    if config.get(CONF_ENABLE_VIGICRUES, False):
        stations = entry.data.get(CONF_VIGICRUES_STATIONS) or config.get(CONF_VIGICRUES_STATIONS)
        if stations and isinstance(stations, list):
            for st in stations:
                st_code = st.get(CONF_VIGICRUES_STATION_CODE)
                st_name = st.get(CONF_VIGICRUES_STATION_NAME) or st_code
                rv_name = st.get(CONF_VIGICRUES_RIVER_NAME) or "Unknown River"
                if st_code:
                    entities.append(
                        WeatherStationVigicruesSensor(
                            coordinator=coordinator,
                            entry=entry,
                            prefix=prefix,
                            station_code=st_code,
                            station_name=st_name,
                            river_name=rv_name,
                        )
                    )
        else:
            # Fallback legacy configuration format (single implicit station parameters)
            st_code = config.get(CONF_VIGICRUES_STATION_CODE) or entry.data.get(CONF_VIGICRUES_STATION_CODE)
            st_name = config.get(CONF_VIGICRUES_STATION_NAME) or entry.data.get(CONF_VIGICRUES_STATION_NAME)
            rv_name = config.get(CONF_VIGICRUES_RIVER_NAME) or entry.data.get(CONF_VIGICRUES_RIVER_NAME)
            entities.append(
                WeatherStationVigicruesSensor(
                    coordinator=coordinator,
                    entry=entry,
                    prefix=prefix,
                    station_code=st_code,
                    station_name=st_name,
                    river_name=rv_name,
                    config_suffix="legacy" if st_code else "auto",
                )
            )

    # Handle dynamic sub-structures (Multi-room BLE/Zigbee auxiliary internal entities)
    if config.get(CONF_ENABLE_INDOOR, False) and config.get(CONF_INDOOR_ROOMS):
        rooms = config.get(CONF_INDOOR_ROOMS) or []
        for room_slug in rooms:
            room_name = room_slug.replace("_", " ").title()
            entities.extend(
                [
                    WeatherStationRoomSensor(
                        coordinator=coordinator,
                        entry=entry,
                        prefix=prefix,
                        room_slug=room_slug,
                        room_name=room_name,
                        sensor_type="temperature",
                    ),
                    WeatherStationRoomSensor(
                        coordinator=coordinator,
                        entry=entry,
                        prefix=prefix,
                        room_slug=room_slug,
                        room_name=room_name,
                        sensor_type="humidity",
                    ),
                ]
            )

    # Prune obsolete entities matching deprecated schemas from global storage if needed
    clean_obsolete_entities(hass, entry, prefix)

    async_add_entities(entities, update_before_add=False)


def clean_obsolete_entities(hass: HomeAssistant, entry: ConfigEntry, prefix: str) -> None:
    """Remove historical or mutated unique-id entities during runtime upgrade sequences."""
    with contextlib.suppress(Exception):
        ent_reg = er.async_get(hass)
        # Identify old v1.x/v0.x style duplicate structural identifiers
        deprecated_keys = ["ws_pressure_trend_string", "ws_uv_level_string", "ws_comfort_string"]
        for key in deprecated_keys:
            old_unique_id = f"{entry.entry_id}_{key}"
            if entity_id := ent_reg.async_get_entity_id("sensor", DOMAIN, old_unique_id):
                ent_reg.async_remove(entity_id)


class WeatherStationSensor(CoordinatorEntity, RestoreEntity, SensorEntity):
    """Representation of a standard Weather Station engine data point sensor."""

    entity_description: WSSensorDescription
    _attr_has_entity_name = False

    def __init__(self, coordinator, entry: ConfigEntry, description: WSSensorDescription, prefix: str) -> None:
        """Initialize the instance wrapper container structure."""
        super().__init__(coordinator)
        self.entity_description = description
        self._entry = entry

        # Apply standardized integration wide object namespace matching schemas
        slug = description.name.lower().replace(" ", "_").replace("(", "").replace(")", "")
        if prefix and prefix.strip():
            # Stripped duplicate prefixes formatting context
            p_clean = prefix.strip().lower().replace(" ", "_")
            if slug.startswith(p_clean):
                self._attr_suggested_object_id = slug
            else:
                self._attr_suggested_object_id = f"{p_clean}_{slug}"
        else:
            self._attr_suggested_object_id = slug

        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_name = description.name
        self._attr_translation_key = description.translation_key

        # Set up conditional diagnostic grouping boundaries flags
        if description.entity_category:
            self._attr_entity_category = description.entity_category

    async def async_added_to_hass(self) -> None:
        """Run standard hooks alongside targeted state recovery steps."""
        await super().async_added_to_hass()

        # Target historical native states if memory footprint was contextually unaligned
        if (last_state := await self.async_get_last_state()) is not None:
            self._attr_native_value = last_state.state

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Dynamically override unit based on core user configuration settings preferences."""
        desc = self.entity_description
        if not desc.unit_group:
            return desc.native_unit

        # Pull integration display settings block configurations
        opts = self._entry.options
        group = desc.unit_group

        if group == "wind":
            return opts.get("unit_wind", "m/s")
        if group == "pressure":
            return opts.get("unit_pressure", "hPa")
        if group == "distance":
            return opts.get("unit_distance", "km")
        if group == "altitude":
            return opts.get("unit_altitude", "m")
        if group in ("rain", "rain_rate"):
            # Rain metrics mirror rain rate inches transformations factors scaling
            u_rain = opts.get("unit_rain", "mm")
            if group == "rain_rate":
                return "in/h" if u_rain == "in" else "mm/h"
            return u_rain

        return desc.native_unit

    @property
    def native_value(self) -> Any:
        """Compute structural states values using functional extraction pointers layers."""
        if not self.coordinator.data or self.coordinator.data.get(self.entity_description.key) is None:
            return None

        d = self.coordinator.data
        key = self.entity_description.key
        raw_val = d.get(key)

        # Apply specific conversion overrides mapping to explicit extractor lambdas if bound
        if self.entity_description.value_fn:
            return self.entity_description.value_fn(d)

        # Intercept scalar targets for configuration transformation multipliers pipelines
        group = self.entity_description.unit_group
        if not group or not isinstance(raw_val, (int, float)):
            return raw_val

        opts = self._entry.options

        # Implement numeric value adjustments factors mappings
        if group == "wind":
            u_target = opts.get("unit_wind", "m/s")
            return round(raw_val * _WIND_FACTORS.get(u_target, 1.0), 2)

        if group == "pressure":
            u_target = opts.get("unit_pressure", "hPa")
            return round(raw_val * _PRESSURE_FACTORS.get(u_target, 1.0), 1)

        if group == "distance":
            u_target = opts.get("unit_distance", "km")
            return round(raw_val * _DISTANCE_FACTORS.get(u_target, 1.0), 2)

        if group == "altitude":
            u_target = opts.get("unit_altitude", "m")
            return round(raw_val * _ALTITUDE_FACTORS.get(u_target, 1.0), 1)

        if group in ("rain", "rain_rate"):
            u_target = opts.get("unit_rain", "mm")
            if u_target == "in":
                # Convert mm -> inches using explicit canonical scaling factor limits
                return round(raw_val / 25.4, 3)
            return round(raw_val, 2)

        return raw_val

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Inject customized map structures if calculation callbacks are appended."""
        if self.coordinator.data and self.entity_description.attrs_fn:
            with contextlib.suppress(Exception):
                return self.entity_description.attrs_fn(self.coordinator.data)
        return None


class WeatherStationRoomSensor(CoordinatorEntity, SensorEntity):
    """Auxiliary dynamic sensor representing localized sub-room environments data points."""

    _attr_has_entity_name = False

    def __init__(
        self, coordinator, entry: ConfigEntry, prefix: str, room_slug: str, room_name: str, sensor_type: str
    ) -> None:
        """Initialize the multiroom structural instance handles bindings."""
        super().__init__(coordinator)
        self._entry = entry
        self._room_slug = room_slug
        self._sensor_type = sensor_type

        # Build consistent display and targeting configurations arrays
        lbl = "Temperature" if sensor_type == "temperature" else "Humidity"
        self._attr_name = f"WS Indoor {room_name} {lbl}"
        self._attr_unique_id = f"{entry.entry_id}_room_{room_slug}_{sensor_type}"

        slug = f"ws_indoor_{room_slug}_{sensor_type}"
        if prefix and prefix.strip():
            p_clean = prefix.strip().lower().replace(" ", "_")
            self._attr_suggested_object_id = slug if slug.startswith(p_clean) else f"{p_clean}_{slug}"
        else:
            self._attr_suggested_object_id = slug

        if sensor_type == "temperature":
            self._attr_device_class = SensorDeviceClass.TEMPERATURE
            self._attr_native_unit_of_measurement = UNIT_TEMP_C
            self._attr_state_class = SensorStateClass.MEASUREMENT
            self._attr_icon = "mdi:thermometer"
        else:
            self._attr_device_class = SensorDeviceClass.HUMIDITY
            self._attr_native_unit_of_measurement = "%"
            self._attr_state_class = SensorStateClass.MEASUREMENT
            self._attr_icon = "mdi:water-percent"

    @property
    def translation_key(self) -> str:
        """Map target validation properties string values back to localized language blocks."""
        return f"indoor_room_{self._sensor_type}"

    @property
    def native_value(self) -> Any:
        """Traverse nested arrays structural configurations mapping values."""
        d = self.coordinator.data or {}
        rooms_dict = d.get(KEY_INDOOR_ROOMS_DATA) or {}
        room_data = rooms_dict.get(self._room_slug) or {}
        return room_data.get(self._sensor_type)


class WeatherStationVigicruesSensor(CoordinatorEntity, SensorEntity):
    """Dynamic multi station river tracking sensors mirroring regional hydrological indicators."""

    _attr_has_entity_name = False

    def __init__(
        self,
        coordinator,
        entry: ConfigEntry,
        prefix: str,
        station_code: str | None,
        station_name: str | None,
        river_name: str | None,
        config_suffix: str = "multi",
    ) -> None:
        """Initialize explicit regional monitoring data layers mapping targets wrappers."""
        super().__init__(coordinator)
        self._entry = entry
        self._station_code = station_code
        self._station_name = station_name
        self._river_name = river_name
        self._config_suffix = config_suffix

        # Pre-calculate internal schema identification hashes strings bindings
        suffix_hash = station_code if station_code else config_suffix
        self._attr_unique_id = f"{entry.entry_id}_vigicrues_flow_{suffix_hash}"

        self._attr_device_class = None
        self._attr_native_unit_of_measurement = "m³/s"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:river"

        slug_river = river_name.lower().replace(" ", "_") if river_name else "river"
        self._attr_name = f"WS Vigicrues {river_name or 'River'} Flow ({station_name or suffix_hash})"

        slug = (
            f"ws_vigicrues_flow_{station_code.lower()}"
            if station_code
            else f"ws_vigicrues_{slug_river}_flow"
        )
        if prefix and prefix.strip():
            p_clean = prefix.strip().lower().replace(" ", "_")
            self._attr_suggested_object_id = (
                slug if slug.startswith(p_clean) else f"{p_clean}_{slug}"
            )
        else:
            self._attr_suggested_object_id = slug

    @property
    def _resolved_code(self) -> str:
        """Resolve current active monitoring entity codes mapping strings checks flags."""
        if self._station_code:
            return self._station_code
        return (self.coordinator.data or {}).get("_vigicrues_auto_code", "")

    @property
    def translation_key(self) -> str:
        """Assign explicit standard localization tags matching component domain paths."""
        return "vigicrues_river_flow"

    @property
    def translation_placeholders(self) -> dict[str, str]:
        """Inject runtime contextual arguments structures formatting names strings dynamically."""
        d = self.coordinator.data or {}
        code = self._resolved_code
        river = d.get(f"_river_name_{code}") or self._river_name
        station = d.get(f"_river_station_name_{code}") or self._station_name
        return {"river": river or station or "Unknown"}

    @property
    def native_value(self):
        """Extract explicit current native stream discharge flow volumes measurements values."""
        d = self.coordinator.data or {}
        return d.get(f"river_flow_m3s_{self._resolved_code}")

    @property
    def extra_state_attributes(self) -> dict:
        """Expose dynamic geo location attributes parameters records schemas updates mapping grids."""
        d = self.coordinator.data or {}
        code = self._resolved_code
        return {
            "station_code": code,
            "station_name": d.get(f"_river_station_name_{code}") or self._station_name,
            "river_name": d.get(f"_river_name_{code}") or self._river_name,
            "last_update": d.get(f"river_flow_time_{code}"),
        }
