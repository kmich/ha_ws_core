"""Diagnostics support for WS Station."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_SOURCES, DOMAIN


def _redact_coords(d: dict[str, Any]) -> dict[str, Any]:
    out = dict(d)
    out.pop("forecast_lat", None)
    out.pop("forecast_lon", None)
    return out


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, Any]:
    coord = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    data = coord.data if coord else None

    return {
        "title": entry.title,
        "entry_data": _redact_coords(dict(entry.data)),
        "entry_options": _redact_coords(dict(entry.options)),
        "sources": dict(entry.data.get(CONF_SOURCES, {})),
        "last_computed": data,
    }
