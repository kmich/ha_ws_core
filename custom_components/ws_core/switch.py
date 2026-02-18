"""Switch entities for Weather Station Core."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import CONF_PREFIX, DEFAULT_PREFIX, DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switch entities."""
    prefix = (entry.options.get(CONF_PREFIX) or entry.data.get(CONF_PREFIX) or DEFAULT_PREFIX).strip().lower()
    async_add_entities(
        [
            WSToggleSwitch(
                entry,
                prefix,
                key="enable_animations",
                name="WS Enable Animations",
                icon="mdi:animation-play",
                default=True,
            ),
        ]
    )


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
