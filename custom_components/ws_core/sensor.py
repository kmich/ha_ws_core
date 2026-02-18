"""Sensors for Weather Station Core -- v0.4.0."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_ENABLE_ACTIVITY_SCORES,
    CONF_ENABLE_EXTENDED_SENSORS,
    CONF_PREFIX,
    DEFAULT_PREFIX,
    DOMAIN,
    KEY_ALERT_MESSAGE,
    KEY_ALERT_STATE,
    KEY_BATTERY_DISPLAY,
    KEY_BATTERY_PCT,
    KEY_CURRENT_CONDITION,
    KEY_DATA_QUALITY,
    KEY_DEW_POINT_C,
    KEY_FEELS_LIKE_C,
    KEY_FIRE_RISK_SCORE,
    KEY_FORECAST,
    KEY_FORECAST_TILES,
    KEY_FROST_POINT_C,
    KEY_HEALTH_DISPLAY,
    KEY_HUMIDITY_LEVEL_DISPLAY,
    KEY_LAUNDRY_SCORE,
    KEY_LUX,
    KEY_NORM_HUMIDITY,
    KEY_NORM_PRESSURE_HPA,
    KEY_NORM_RAIN_TOTAL_MM,
    KEY_NORM_TEMP_C,
    KEY_NORM_WIND_DIR_DEG,
    KEY_NORM_WIND_GUST_MS,
    KEY_NORM_WIND_SPEED_MS,
    KEY_PACKAGE_STATUS,
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
    KEY_SENSOR_QUALITY_FLAGS,
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
        state_class=SensorStateClass.MEASUREMENT,
        attrs_fn=lambda d: {
            "danger_level": d.get("_fire_danger_level"),
            "rain_24h_mm": d.get("_fire_rain_24h_mm"),
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
        state_class=SensorStateClass.MEASUREMENT,
        attrs_fn=lambda d: {
            "level": d.get("_running_level"),
            "recommendation": d.get("_running_recommendation"),
            "feels_like_c": d.get(KEY_FEELS_LIKE_C),
            "uv_index": d.get(KEY_UV),
        },
    ),
]

# Sensor groups for feature toggles
_ACTIVITY_SCORE_KEYS = {KEY_LAUNDRY_SCORE, KEY_STARGAZE_SCORE, KEY_FIRE_RISK_SCORE, KEY_RUNNING_SCORE}
_EXTENDED_SENSOR_KEYS = {
    KEY_ZAMBRETTI_FORECAST,
    KEY_ZAMBRETTI_NUMBER,
    KEY_CURRENT_CONDITION,
    KEY_HUMIDITY_LEVEL_DISPLAY,
    KEY_UV_LEVEL_DISPLAY,
    KEY_TEMP_DISPLAY,
    KEY_RAIN_DISPLAY,
    KEY_PRESSURE_TREND_DISPLAY,
    KEY_HEALTH_DISPLAY,
    KEY_FORECAST_TILES,
    KEY_BATTERY_DISPLAY,
}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    prefix = (entry.options.get(CONF_PREFIX) or entry.data.get(CONF_PREFIX) or DEFAULT_PREFIX).strip().lower()

    opts = {**entry.data, **entry.options}
    activity_enabled = opts.get(CONF_ENABLE_ACTIVITY_SCORES, False)
    extended_enabled = opts.get(CONF_ENABLE_EXTENDED_SENSORS, True)

    filtered: list[WSSensorDescription] = []
    for desc in SENSORS:
        if desc.key in _ACTIVITY_SCORE_KEYS and not activity_enabled:
            continue
        if desc.key in _EXTENDED_SENSOR_KEYS and not extended_enabled:
            continue
        filtered.append(desc)

    entities: list[WSSensor] = [WSSensor(coordinator, entry, desc, prefix) for desc in filtered]
    async_add_entities(entities)


class WSSensor(CoordinatorEntity, SensorEntity):
    """A single derived sensor for Weather Station Core."""

    _DISABLED_BY_DEFAULT = {
        KEY_TEMP_AVG_24H,
        KEY_TEMP_DISPLAY,
        KEY_WIND_DIR_SMOOTH_DEG,
        KEY_BATTERY_DISPLAY,
        KEY_SENSOR_QUALITY_FLAGS,
        KEY_ZAMBRETTI_NUMBER,
    }

    def __init__(self, coordinator, entry: ConfigEntry, desc: WSSensorDescription, prefix: str):
        super().__init__(coordinator)
        self._desc = desc
        self._entry = entry
        self._prefix = prefix

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
        }
        if key in overrides:
            return overrides[key]
        # Fallback: strip common prefixes/suffixes for a clean slug
        return key.replace("_mmph", "").replace("_ms", "").replace("_hpa", "").replace("_c", "")
        k = key.replace("_c", "").replace("_hpah", "").replace("_hpa", "")
        k = k.replace("_mm", "").replace("_ms", "").replace("_deg", "")
        k = k.replace("_mmph_", "_").replace("_mmph", "").replace("_pct", "").replace("_lx", "")
        return k

    @property
    def native_value(self):
        d = self.coordinator.data or {}
        if self._desc.value_fn is not None:
            try:
                return self._desc.value_fn(d)
            except Exception:
                return None
        return d.get(self._desc.key)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        d = self.coordinator.data or {}
        if self._desc.attrs_fn is not None:
            try:
                return {k: v for k, v in (self._desc.attrs_fn(d) or {}).items() if v is not None}
            except Exception:
                return {}
        if self._desc.key in (KEY_DATA_QUALITY, KEY_PACKAGE_STATUS, KEY_ALERT_STATE, KEY_ALERT_MESSAGE):
            return {
                "package_ok": d.get("package_ok"),
                "data_quality": d.get(KEY_DATA_QUALITY),
                "alert_state": d.get(KEY_ALERT_STATE),
            }
        return {}
