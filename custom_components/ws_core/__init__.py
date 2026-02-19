"""Weather Station Core integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr

from .const import (
    CONF_CLIMATE_REGION,
    CONF_HEMISPHERE,
    CONFIG_VERSION,
    DEFAULT_CLIMATE_REGION,
    DEFAULT_HEMISPHERE,
    DOMAIN,
    PLATFORMS,
)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
_LOGGER = logging.getLogger(__name__)

if TYPE_CHECKING:
    from .coordinator import WSStationCoordinator

SERVICE_RESET_RAIN = "reset_rain_baseline"
ATTR_ENTRY_ID = "entry_id"

SERVICE_RESET_RAIN_SCHEMA = vol.Schema({vol.Optional(ATTR_ENTRY_ID): cv.string})


async def async_migrate_entry(hass: HomeAssistant, entry) -> bool:
    """Handle config entry schema version migrations.

    v1 -> v2: Added hemisphere and climate_region fields.
    """
    _LOGGER.info("Migrating WS Station config entry from version %s", entry.version)

    if entry.version == 1:
        new_data = dict(entry.data)
        if CONF_HEMISPHERE not in new_data:
            try:
                lat = float(hass.config.latitude)
                new_data[CONF_HEMISPHERE] = "Southern" if lat < 0 else "Northern"
            except (TypeError, ValueError):
                new_data[CONF_HEMISPHERE] = DEFAULT_HEMISPHERE
        if CONF_CLIMATE_REGION not in new_data:
            new_data[CONF_CLIMATE_REGION] = DEFAULT_CLIMATE_REGION
        hass.config_entries.async_update_entry(entry, data=new_data, version=CONFIG_VERSION)
        _LOGGER.info(
            "Migration to v2 complete: hemisphere=%s, climate_region=%s",
            new_data[CONF_HEMISPHERE],
            new_data[CONF_CLIMATE_REGION],
        )
        return True

    _LOGGER.error("Unknown config entry version %s -- cannot migrate", entry.version)
    return False


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    from .coordinator import WSStationCoordinator

    coordinator = WSStationCoordinator(hass, entry.data, entry.options)
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await coordinator.async_start()

    # Create a device for the station
    dev_reg = dr.async_get(hass)
    dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.title,
        manufacturer="Weather Station Core",
        model="Derived Weather Package",
        sw_version="1.0.3",
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Reload the entry whenever the user saves new options
    entry.async_on_unload(entry.add_update_listener(async_update_options))

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
