"""Switch entities for Weather Station Core.

Includes:
  - WSToggleSwitch: restore-state switches (e.g. dashboard animations)
  - WSFeatureSwitch: config-backed feature toggles that write to
    entry.options and trigger a coordinator reload when toggled
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    CONF_ENABLE_AIR_QUALITY,
    CONF_ENABLE_CWOP,
    CONF_ENABLE_DEGREE_DAYS,
    CONF_ENABLE_DISPLAY_SENSORS,
    CONF_ENABLE_EXPORT,
    CONF_ENABLE_FIRE_RISK,
    CONF_ENABLE_LAUNDRY,
    CONF_ENABLE_METAR,
    CONF_ENABLE_MOON,
    CONF_ENABLE_POLLEN,
    CONF_ENABLE_RUNNING,
    CONF_ENABLE_SEA_TEMP,
    CONF_ENABLE_SOLAR_FORECAST,
    CONF_ENABLE_STARGAZING,
    CONF_ENABLE_WUNDERGROUND,
    CONF_ENABLE_ZAMBRETTI,
    CONF_PREFIX,
    DEFAULT_ENABLE_AIR_QUALITY,
    DEFAULT_ENABLE_CWOP,
    DEFAULT_ENABLE_DEGREE_DAYS,
    DEFAULT_ENABLE_DISPLAY_SENSORS,
    DEFAULT_ENABLE_EXPORT,
    DEFAULT_ENABLE_FIRE_RISK,
    DEFAULT_ENABLE_LAUNDRY,
    DEFAULT_ENABLE_METAR,
    DEFAULT_ENABLE_MOON,
    DEFAULT_ENABLE_POLLEN,
    DEFAULT_ENABLE_RUNNING,
    DEFAULT_ENABLE_SEA_TEMP,
    DEFAULT_ENABLE_SOLAR_FORECAST,
    DEFAULT_ENABLE_STARGAZING,
    DEFAULT_ENABLE_WUNDERGROUND,
    DEFAULT_ENABLE_ZAMBRETTI,
    DEFAULT_PREFIX,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Feature toggle descriptors
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WSFeatureDesc:
    """Descriptor for a config-backed feature toggle switch."""

    conf_key: str
    default: bool
    name: str
    icon: str


FEATURE_SWITCHES: tuple[WSFeatureDesc, ...] = (
    WSFeatureDesc(
        conf_key=CONF_ENABLE_ZAMBRETTI,
        default=DEFAULT_ENABLE_ZAMBRETTI,
        name="Zambretti Forecast",
        icon="mdi:chart-timeline-variant-shimmer",
    ),
    WSFeatureDesc(
        conf_key=CONF_ENABLE_DISPLAY_SENSORS,
        default=DEFAULT_ENABLE_DISPLAY_SENSORS,
        name="Display Sensors",
        icon="mdi:monitor-dashboard",
    ),
    WSFeatureDesc(
        conf_key=CONF_ENABLE_LAUNDRY,
        default=DEFAULT_ENABLE_LAUNDRY,
        name="Laundry Drying Score",
        icon="mdi:hanger",
    ),
    WSFeatureDesc(
        conf_key=CONF_ENABLE_STARGAZING,
        default=DEFAULT_ENABLE_STARGAZING,
        name="Stargazing Quality",
        icon="mdi:telescope",
    ),
    WSFeatureDesc(
        conf_key=CONF_ENABLE_FIRE_RISK,
        default=DEFAULT_ENABLE_FIRE_RISK,
        name="Fire Risk Score",
        icon="mdi:fire-alert",
    ),
    WSFeatureDesc(
        conf_key=CONF_ENABLE_RUNNING,
        default=DEFAULT_ENABLE_RUNNING,
        name="Running Conditions Score",
        icon="mdi:run-fast",
    ),
    WSFeatureDesc(
        conf_key=CONF_ENABLE_SEA_TEMP,
        default=DEFAULT_ENABLE_SEA_TEMP,
        name="Sea Surface Temperature",
        icon="mdi:waves",
    ),
    WSFeatureDesc(
        conf_key=CONF_ENABLE_DEGREE_DAYS,
        default=DEFAULT_ENABLE_DEGREE_DAYS,
        name="Degree Days",
        icon="mdi:thermometer-lines",
    ),
    WSFeatureDesc(
        conf_key=CONF_ENABLE_METAR,
        default=DEFAULT_ENABLE_METAR,
        name="METAR Cross-Validation",
        icon="mdi:airplane",
    ),
    WSFeatureDesc(
        conf_key=CONF_ENABLE_CWOP,
        default=DEFAULT_ENABLE_CWOP,
        name="CWOP Upload",
        icon="mdi:upload-network",
    ),
    WSFeatureDesc(
        conf_key=CONF_ENABLE_WUNDERGROUND,
        default=DEFAULT_ENABLE_WUNDERGROUND,
        name="Weather Underground Upload",
        icon="mdi:cloud-upload",
    ),
    WSFeatureDesc(
        conf_key=CONF_ENABLE_EXPORT,
        default=DEFAULT_ENABLE_EXPORT,
        name="CSV/JSON Data Export",
        icon="mdi:file-export",
    ),
    WSFeatureDesc(
        conf_key=CONF_ENABLE_AIR_QUALITY,
        default=DEFAULT_ENABLE_AIR_QUALITY,
        name="Air Quality Index",
        icon="mdi:air-filter",
    ),
    WSFeatureDesc(
        conf_key=CONF_ENABLE_POLLEN,
        default=DEFAULT_ENABLE_POLLEN,
        name="Pollen Levels",
        icon="mdi:flower-pollen",
    ),
    WSFeatureDesc(
        conf_key=CONF_ENABLE_MOON,
        default=DEFAULT_ENABLE_MOON,
        name="Moon Phase & Illumination",
        icon="mdi:moon-waning-crescent",
    ),
    WSFeatureDesc(
        conf_key=CONF_ENABLE_SOLAR_FORECAST,
        default=DEFAULT_ENABLE_SOLAR_FORECAST,
        name="Solar PV Forecast",
        icon="mdi:solar-power",
    ),
)


# ---------------------------------------------------------------------------
# Platform setup
# ---------------------------------------------------------------------------


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switch entities."""
    prefix = (entry.options.get(CONF_PREFIX) or entry.data.get(CONF_PREFIX) or DEFAULT_PREFIX).strip().lower()

    entities: list[SwitchEntity] = [
        # Existing dashboard toggle (restore-state)
        WSToggleSwitch(
            entry,
            prefix,
            key="enable_animations",
            name="WS Enable Animations",
            icon="mdi:animation-play",
            default=True,
        ),
    ]

    # Config-backed feature toggles
    for desc in FEATURE_SWITCHES:
        entities.append(WSFeatureSwitch(entry, prefix, desc))

    async_add_entities(entities)


# ---------------------------------------------------------------------------
# Restore-state toggle (unchanged from v1.0.0)
# ---------------------------------------------------------------------------


class WSToggleSwitch(RestoreEntity, SwitchEntity):
    """A toggle switch owned by the integration."""

    def __init__(
        self,
        entry: ConfigEntry,
        prefix: str,
        *,
        key: str,
        name: str,
        icon: str,
        default: bool = True,
    ) -> None:
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_suggested_object_id = f"{prefix}_{key}"
        self._attr_name = name
        self._attr_icon = icon
        self._attr_is_on = default

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, self._entry.entry_id)}}

    async def async_added_to_hass(self) -> None:
        """Restore last state."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state:
            self._attr_is_on = last_state.state == "on"

    async def async_turn_on(self, **kwargs) -> None:
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        self._attr_is_on = False
        self.async_write_ha_state()


# ---------------------------------------------------------------------------
# Config-backed feature toggle
# ---------------------------------------------------------------------------


class WSFeatureSwitch(SwitchEntity):
    """A switch that reflects and modifies a boolean config entry option.

    Toggling writes to entry.options which fires the update listener
    and triggers a coordinator reload.
    """

    _attr_entity_category = EntityCategory.CONFIG
    _attr_has_entity_name = False

    def __init__(
        self,
        entry: ConfigEntry,
        prefix: str,
        desc: WSFeatureDesc,
    ) -> None:
        self._entry = entry
        self._desc = desc
        # Use the conf_key as the object-id suffix (e.g. enable_air_quality)
        self._attr_unique_id = f"{entry.entry_id}_{desc.conf_key}"
        self._attr_suggested_object_id = f"{prefix}_{desc.conf_key}"
        self._attr_name = desc.name
        self._attr_icon = desc.icon

    @property
    def device_info(self) -> dict[str, Any]:
        return {"identifiers": {(DOMAIN, self._entry.entry_id)}}

    @property
    def is_on(self) -> bool:
        """Read current state from the config entry."""
        return bool(
            self._entry.options.get(
                self._desc.conf_key,
                self._entry.data.get(self._desc.conf_key, self._desc.default),
            )
        )

    async def async_turn_on(self, **kwargs) -> None:
        """Enable the feature."""
        await self._write(True)

    async def async_turn_off(self, **kwargs) -> None:
        """Disable the feature."""
        await self._write(False)

    async def _write(self, value: bool) -> None:
        """Persist value to entry.options (triggers reload via update listener)."""
        new_options = dict(self._entry.options)
        new_options[self._desc.conf_key] = value
        self.hass.config_entries.async_update_entry(self._entry, options=new_options)
