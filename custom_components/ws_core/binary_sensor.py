"""Binary sensors for Weather Station Core."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_PREFIX, DEFAULT_PREFIX, DOMAIN, KEY_PACKAGE_OK


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    prefix = (entry.options.get(CONF_PREFIX) or entry.data.get(CONF_PREFIX) or DEFAULT_PREFIX).strip().lower()
    async_add_entities([WSPackageOK(coordinator, entry, prefix)])


class WSPackageOK(CoordinatorEntity, BinarySensorEntity):
    """True when required sources exist and are mapped."""

    def __init__(self, coordinator, entry: ConfigEntry, prefix: str):
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_package_ok"
        self._attr_suggested_object_id = f"{prefix}_package_ok"
        self._attr_name = "WS Package OK"
        self._attr_icon = "mdi:check-decagram"

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, self._entry.entry_id)}}

    @property
    def is_on(self) -> bool | None:
        d = self.coordinator.data or {}
        v = d.get(KEY_PACKAGE_OK)
        if v is None:
            return None
        return bool(v)
