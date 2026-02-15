"""Weather Station Core integration."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN, PLATFORMS
from .coordinator import WSStationCoordinator

_LOGGER = logging.getLogger(__name__)

SERVICE_RESET_RAIN = "reset_rain_baseline"
ATTR_ENTRY_ID = "entry_id"

SERVICE_RESET_RAIN_SCHEMA = vol.Schema({vol.Optional(ATTR_ENTRY_ID): cv.string})


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = WSStationCoordinator(hass, entry.data, entry.options)
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await coordinator.async_start()

    # Create a device for the station
    dev_reg = dr.async_get(hass)
    dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.title,
        manufacturer="WS Station",
        model="Derived Weather Package",
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def _reset_rain(call: ServiceCall) -> None:
        entry_id = call.data.get(ATTR_ENTRY_ID)
        targets = []
        if entry_id:
            coord = hass.data[DOMAIN].get(entry_id)
            if coord:
                targets = [coord]
        else:
            targets = list(hass.data[DOMAIN].values())

        for coord in targets:
            coord.runtime.last_rain_total_mm = None
            coord.runtime.last_rain_ts = None
            coord.runtime.last_rain_rate_filt = 0.0
            await coord.async_refresh()

    # Register services once per integration domain (idempotent)
    if not hass.services.has_service(DOMAIN, SERVICE_RESET_RAIN):
        hass.services.async_register(DOMAIN, SERVICE_RESET_RAIN, _reset_rain, schema=SERVICE_RESET_RAIN_SCHEMA)

    return True


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    coordinator: WSStationCoordinator | None = hass.data[DOMAIN].pop(entry.entry_id, None)
    if coordinator is not None:
        await coordinator.async_stop()
    return unload_ok
