"""Number entities for Weather Station Core.

Exposes numeric configuration parameters (thresholds, calibration offsets)
as HA number entities on the device page so users can adjust them without
entering the config flow.  Changes write back to entry.options and trigger
a coordinator reload.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_CAL_HUMIDITY,
    CONF_CAL_PRESSURE_HPA,
    CONF_CAL_TEMP_C,
    CONF_CAL_WIND_MS,
    CONF_PREFIX,
    CONF_PRESSURE_TREND_WINDOW_H,
    CONF_RAIN_FILTER_ALPHA,
    CONF_RAIN_PENALTY_HEAVY_MMPH,
    CONF_RAIN_PENALTY_LIGHT_MMPH,
    CONF_STALENESS_S,
    CONF_THRESH_FREEZE_C,
    CONF_THRESH_RAIN_RATE_MMPH,
    CONF_THRESH_WIND_GUST_MS,
    DEFAULT_CAL_HUMIDITY,
    DEFAULT_CAL_PRESSURE_HPA,
    DEFAULT_CAL_TEMP_C,
    DEFAULT_CAL_WIND_MS,
    DEFAULT_PREFIX,
    DEFAULT_PRESSURE_TREND_WINDOW_H,
    DEFAULT_RAIN_FILTER_ALPHA,
    DEFAULT_RAIN_PENALTY_HEAVY_MMPH,
    DEFAULT_RAIN_PENALTY_LIGHT_MMPH,
    DEFAULT_STALENESS_S,
    DEFAULT_THRESH_FREEZE_C,
    DEFAULT_THRESH_RAIN_RATE_MMPH,
    DEFAULT_THRESH_WIND_GUST_MS,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class WSNumberDesc:
    """Descriptor for a config-backed number entity."""

    key: str
    conf_key: str
    default: float
    name: str
    icon: str
    native_min: float
    native_max: float
    native_step: float
    native_unit: str | None = None
    mode: NumberMode = NumberMode.BOX


PARAM_NUMBERS: tuple[WSNumberDesc, ...] = (
    WSNumberDesc(
        key="thresh_wind_gust",
        conf_key=CONF_THRESH_WIND_GUST_MS,
        default=DEFAULT_THRESH_WIND_GUST_MS,
        name="Wind Gust Alert Threshold",
        icon="mdi:weather-windy",
        native_min=0.0,
        native_max=120.0,
        native_step=0.1,
        native_unit="m/s",
    ),
    WSNumberDesc(
        key="thresh_rain_rate",
        conf_key=CONF_THRESH_RAIN_RATE_MMPH,
        default=DEFAULT_THRESH_RAIN_RATE_MMPH,
        name="Rain Rate Alert Threshold",
        icon="mdi:weather-pouring",
        native_min=0.0,
        native_max=200.0,
        native_step=0.5,
        native_unit="mm/h",
    ),
    WSNumberDesc(
        key="thresh_freeze",
        conf_key=CONF_THRESH_FREEZE_C,
        default=DEFAULT_THRESH_FREEZE_C,
        name="Freeze Warning Threshold",
        icon="mdi:snowflake-alert",
        native_min=-30.0,
        native_max=10.0,
        native_step=0.5,
        native_unit="\u00b0C",
    ),
    WSNumberDesc(
        key="cal_temp",
        conf_key=CONF_CAL_TEMP_C,
        default=DEFAULT_CAL_TEMP_C,
        name="Temperature Calibration Offset",
        icon="mdi:thermometer-alert",
        native_min=-10.0,
        native_max=10.0,
        native_step=0.1,
        native_unit="\u00b0C",
    ),
    WSNumberDesc(
        key="cal_humidity",
        conf_key=CONF_CAL_HUMIDITY,
        default=DEFAULT_CAL_HUMIDITY,
        name="Humidity Calibration Offset",
        icon="mdi:water-percent-alert",
        native_min=-20.0,
        native_max=20.0,
        native_step=0.5,
        native_unit="%",
    ),
    WSNumberDesc(
        key="cal_pressure",
        conf_key=CONF_CAL_PRESSURE_HPA,
        default=DEFAULT_CAL_PRESSURE_HPA,
        name="Pressure Calibration Offset",
        icon="mdi:gauge-low",
        native_min=-10.0,
        native_max=10.0,
        native_step=0.1,
        native_unit="hPa",
    ),
    WSNumberDesc(
        key="cal_wind",
        conf_key=CONF_CAL_WIND_MS,
        default=DEFAULT_CAL_WIND_MS,
        name="Wind Speed Calibration Offset",
        icon="mdi:windsock",
        native_min=-5.0,
        native_max=5.0,
        native_step=0.1,
        native_unit="m/s",
    ),
    WSNumberDesc(
        key="staleness_timeout",
        conf_key=CONF_STALENESS_S,
        default=float(DEFAULT_STALENESS_S),
        name="Sensor Staleness Timeout",
        icon="mdi:timer-alert-outline",
        native_min=60.0,
        native_max=3600.0,
        native_step=60.0,
        native_unit="s",
    ),
    WSNumberDesc(
        key="rain_filter_alpha",
        conf_key=CONF_RAIN_FILTER_ALPHA,
        default=DEFAULT_RAIN_FILTER_ALPHA,
        name="Rain-rate Filter Smoothing",
        icon="mdi:tune-variant",
        native_min=0.05,
        native_max=1.0,
        native_step=0.05,
        mode=NumberMode.SLIDER,
    ),
    WSNumberDesc(
        key="pressure_trend_window",
        conf_key=CONF_PRESSURE_TREND_WINDOW_H,
        default=float(DEFAULT_PRESSURE_TREND_WINDOW_H),
        name="Pressure Trend Window",
        icon="mdi:chart-timeline-variant",
        native_min=1.0,
        native_max=12.0,
        native_step=1.0,
        native_unit="h",
    ),
    WSNumberDesc(
        key="rain_penalty_light",
        conf_key=CONF_RAIN_PENALTY_LIGHT_MMPH,
        default=DEFAULT_RAIN_PENALTY_LIGHT_MMPH,
        name="Rain Penalty Start Threshold",
        icon="mdi:weather-rainy",
        native_min=0.0,
        native_max=5.0,
        native_step=0.1,
        native_unit="mm/h",
    ),
    WSNumberDesc(
        key="rain_penalty_heavy",
        conf_key=CONF_RAIN_PENALTY_HEAVY_MMPH,
        default=DEFAULT_RAIN_PENALTY_HEAVY_MMPH,
        name="Rain Penalty Maximum Threshold",
        icon="mdi:weather-pouring",
        native_min=0.1,
        native_max=50.0,
        native_step=0.5,
        native_unit="mm/h",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up config-backed number entities."""
    prefix = (
        entry.options.get(CONF_PREFIX)
        or entry.data.get(CONF_PREFIX)
        or DEFAULT_PREFIX
    ).strip().lower()

    entities: list[WSConfigNumber] = [
        WSConfigNumber(entry, prefix, desc) for desc in PARAM_NUMBERS
    ]
    async_add_entities(entities)


class WSConfigNumber(NumberEntity):
    """A number entity backed by a config entry option."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_has_entity_name = False

    def __init__(
        self,
        entry: ConfigEntry,
        prefix: str,
        desc: WSNumberDesc,
    ) -> None:
        self._entry = entry
        self._desc = desc
        self._attr_unique_id = f"{entry.entry_id}_{desc.key}"
        self._attr_suggested_object_id = f"{prefix}_{desc.key}"
        self._attr_name = desc.name
        self._attr_icon = desc.icon
        self._attr_native_min_value = desc.native_min
        self._attr_native_max_value = desc.native_max
        self._attr_native_step = desc.native_step
        self._attr_native_unit_of_measurement = desc.native_unit
        self._attr_mode = desc.mode

    @property
    def device_info(self) -> dict[str, Any]:
        return {"identifiers": {(DOMAIN, self._entry.entry_id)}}

    @property
    def native_value(self) -> float:
        return float(
            self._entry.options.get(
                self._desc.conf_key,
                self._entry.data.get(self._desc.conf_key, self._desc.default),
            )
        )

    async def async_set_native_value(self, value: float) -> None:
        """Write the new value to entry.options and reload."""
        new_options = dict(self._entry.options)
        new_options[self._desc.conf_key] = value
        self.hass.config_entries.async_update_entry(
            self._entry, options=new_options
        )
