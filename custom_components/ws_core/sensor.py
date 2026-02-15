"""Sensors for Weather Station Core."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DEFAULT_PREFIX,
    CONF_PREFIX,
    DOMAIN,
    KEY_ALERT_MESSAGE,
    KEY_ALERT_STATE,
    KEY_BATTERY_PCT,
    KEY_DATA_QUALITY,
    KEY_DEW_POINT_C,
    KEY_FORECAST,
    KEY_LUX,
    KEY_LAUNDRY_SCORE,
    KEY_STARGAZE_SCORE,
    KEY_FIRE_SCORE,
    KEY_PRESSURE_TREND_HPAH,
    KEY_PRESSURE_CHANGE_WINDOW_HPA,
    KEY_NORM_HUMIDITY,
    KEY_NORM_PRESSURE_HPA,
    KEY_SEA_LEVEL_PRESSURE_HPA,
    KEY_NORM_RAIN_TOTAL_MM,
    KEY_NORM_TEMP_C,
    KEY_NORM_WIND_DIR_DEG,
    KEY_NORM_WIND_GUST_MS,
    KEY_NORM_WIND_SPEED_MS,
    KEY_PACKAGE_STATUS,
    KEY_RAIN_RATE_FILT,
    KEY_RAIN_RATE_RAW,
    KEY_UV,
    UNIT_PRESSURE_HPA,
    UNIT_RAIN_MM,
    UNIT_TEMP_C,
    UNIT_WIND_MS,
)


@dataclass(frozen=True)
class WSSensorDescription:
    key: str
    name: str
    icon: str | None = None
    device_class: SensorDeviceClass | None = None
    native_unit: str | None = None
    state_class: SensorStateClass | None = None
    entity_category: EntityCategory | None = None
    value_fn: Callable[[dict[str, Any]], Any] | None = None
    attrs_fn: Callable[[dict[str, Any]], dict[str, Any]] | None = None


SENSORS: list[WSSensorDescription] = [
    # Core measurements
    WSSensorDescription(
        key=KEY_NORM_TEMP_C,
        name="WS Temperature",
        icon="mdi:thermometer",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit=UNIT_TEMP_C,
        state_class=SensorStateClass.MEASUREMENT,
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
        native_unit="°",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WSSensorDescription(
        key=KEY_NORM_RAIN_TOTAL_MM,
        name="WS Rain Total",
        icon="mdi:water",
        device_class=SensorDeviceClass.PRECIPITATION,
        native_unit=UNIT_RAIN_MM,
        # Many stations reset this counter; keep it as a plain measurement.
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WSSensorDescription(
        key=KEY_RAIN_RATE_RAW,
        name="WS Rain Rate Raw",
        icon="mdi:weather-pouring",
        native_unit="mm/h",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WSSensorDescription(
        key=KEY_RAIN_RATE_FILT,
        name="WS Rain Rate Filtered",
        icon="mdi:weather-pouring",
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
    # Diagnostics / derived
    WSSensorDescription(
        key=KEY_PRESSURE_TREND_HPAH,
        name="WS Pressure Trend (avg)",
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
    # Optional activity proxies (disabled by default; enable in entity registry or options)
    WSSensorDescription(
        key=KEY_LAUNDRY_SCORE,
        name="WS Laundry Drying Score",
        icon="mdi:tshirt-crew-outline",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    WSSensorDescription(
        key=KEY_STARGAZE_SCORE,
        name="WS Stargazing Quality",
        icon="mdi:telescope",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    WSSensorDescription(
        key=KEY_FIRE_SCORE,
        name="WS Fire Weather Proxy",
        icon="mdi:fire",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # Status & alerts
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
        attrs_fn=lambda d: (d.get(KEY_FORECAST) or {}),
    ),
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    prefix = (entry.options.get(CONF_PREFIX) or entry.data.get(CONF_PREFIX) or DEFAULT_PREFIX).strip().lower()

    entities: list[WSSensor] = [WSSensor(coordinator, entry, desc, prefix) for desc in SENSORS]
    async_add_entities(entities)


class WSSensor(CoordinatorEntity, SensorEntity):
    """A single derived sensor."""

    def __init__(self, coordinator, entry: ConfigEntry, desc: WSSensorDescription, prefix: str):
        super().__init__(coordinator)
        self.entity_description = desc
        self._entry = entry
        self._prefix = prefix

        self._attr_unique_id = f"{entry.entry_id}_{desc.key}"
        key_slug = self._slug_for_key(desc.key)
        self._attr_suggested_object_id = f"{prefix}_{key_slug}"

        self._attr_name = desc.name
        self._attr_icon = desc.icon
        self._attr_device_class = desc.device_class
        self._attr_native_unit_of_measurement = desc.native_unit
        self._attr_state_class = desc.state_class
        if desc.entity_category is not None:
            self._attr_entity_category = desc.entity_category

        # Disable activity proxies by default (users can enable explicitly)
        if desc.key in (KEY_LAUNDRY_SCORE, KEY_STARGAZE_SCORE, KEY_FIRE_SCORE):
            self._attr_entity_registry_enabled_default = False

    async def async_added_to_hass(self) -> None:
        """Best-effort entity-id migration for the shipped vanilla dashboard."""
        await super().async_added_to_hass()

        desired = None
        if self.entity_description.key == KEY_DATA_QUALITY:
            desired = f"sensor.{self._prefix}_data_quality_banner"
        elif self.entity_description.key == KEY_FORECAST:
            desired = f"sensor.{self._prefix}_forecast_daily"

        if desired and self.entity_id and self.entity_id != desired:
            reg = er.async_get(self.hass)
            current = reg.async_get(self.entity_id)
            if current and current.unique_id == self.unique_id:
                # Avoid collisions: only rename if the desired entity_id is unused.
                if reg.async_get(desired) is None:
                    reg.async_update_entity(self.entity_id, new_entity_id=desired)

    @staticmethod
    def _slug_for_key(key: str) -> str:
        # Ensure stable object_ids and match the included dashboard naming.
        if key == KEY_DATA_QUALITY:
            return "data_quality_banner"
        if key == KEY_FORECAST:
            return "forecast_daily"

        k = key
        k = k.replace("_c", "")
        k = k.replace("_hpah", "")
        k = k.replace("_hpa", "")
        k = k.replace("_mm", "")
        k = k.replace("_ms", "")
        k = k.replace("_deg", "")
        k = k.replace("_mmph_", "_")
        k = k.replace("_mmph", "")
        k = k.replace("_pct", "")
        k = k.replace("_lx", "")
        return k

    @property
    def native_value(self):
        d = self.coordinator.data or {}
        desc: WSSensorDescription = self.entity_description
        if desc.value_fn is not None:
            return desc.value_fn(d)
        return d.get(desc.key)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        d = self.coordinator.data or {}
        desc: WSSensorDescription = self.entity_description
        if desc.attrs_fn is not None:
            try:
                return desc.attrs_fn(d) or {}
            except Exception:
                return {}
        if desc.key in (KEY_DATA_QUALITY, KEY_PACKAGE_STATUS, KEY_ALERT_STATE, KEY_ALERT_MESSAGE):
            return {
                "package_ok": d.get("package_ok"),
                "data_quality": d.get("data_quality"),
                "alert_state": d.get("alert_state"),
            }
        return {}
