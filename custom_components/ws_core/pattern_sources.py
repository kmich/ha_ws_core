"""Storm data-source selection for Pattern Forecast.

The one rule that keeps Pattern Forecast local: a mapped hardware lightning
detector always wins; Blitzortung (internet lightning) is used only when no
detector is mapped AND the user explicitly opted in, and only for the storm
target. Everything here is a pure decision over the source mapping, the opt-in
flag and the entity registry; nothing is fetched.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from .const import (
    CONF_ENABLE_PATTERN_FORECAST,
    CONF_PATTERN_STORM_INTERNET_LIGHTNING,
    CONF_SOURCES,
    DEFAULT_ENABLE_PATTERN_FORECAST,
    DEFAULT_PATTERN_STORM_INTERNET_LIGHTNING,
    PATTERN_SOURCE_INTERNET,
    PATTERN_SOURCE_LOCAL,
    SRC_LIGHTNING_COUNT,
    SRC_LIGHTNING_DISTANCE,
)

_LOGGER = logging.getLogger(__name__)

BLITZORTUNG_PLATFORM = "blitzortung"


def hardware_detector_mapped(sources: dict[str, str] | None) -> bool:
    """True when the user mapped a lightning strike counter (a local detector)."""
    return bool((sources or {}).get(SRC_LIGHTNING_COUNT))


def find_blitzortung_entities(hass: Any, registry: Any = None) -> dict[str, str]:
    """Entity ids of the Blitzortung integration's strike counter and distance.

    Strict registry check: the entity must belong to the ``blitzortung``
    platform (an entity id that merely starts with ``sensor.blitzortung_`` is
    not enough) and must not be disabled. Returns ``{}`` when it is not set up.
    """
    if registry is None:
        from homeassistant.helpers import entity_registry as er

        registry = er.async_get(hass)
    found: dict[str, str] = {}
    for entry in registry.entities.values():
        if entry.platform != BLITZORTUNG_PLATFORM or entry.domain != "sensor":
            continue
        if getattr(entry, "disabled_by", None) is not None:
            continue
        eid = entry.entity_id
        uid = str(entry.unique_id or "").lower()
        if SRC_LIGHTNING_COUNT not in found and (
            "counter" in uid or "count" in uid or "counter" in eid or "count" in eid
        ):
            found[SRC_LIGHTNING_COUNT] = eid
        if SRC_LIGHTNING_DISTANCE not in found and ("distance" in uid or "distance" in eid):
            found[SRC_LIGHTNING_DISTANCE] = eid
    return found


def storm_source(sources: dict[str, str] | None, internet_opt_in: bool) -> str | None:
    """``local``, ``internet`` or ``None`` (no storm target).

    Hardware always wins, even with the opt-in on. The opt-in alone selects
    ``internet``; whether Blitzortung is actually present is checked when the
    data is read (and shown in the status sensor), so a slow integration start
    never silently drops the storm sensor.
    """
    if hardware_detector_mapped(sources):
        return PATTERN_SOURCE_LOCAL
    if internet_opt_in:
        return PATTERN_SOURCE_INTERNET
    return None


def storm_source_from_options(opts: dict[str, Any]) -> str | None:
    """The same decision from merged config-entry data + options."""
    if not opts.get(CONF_ENABLE_PATTERN_FORECAST, DEFAULT_ENABLE_PATTERN_FORECAST):
        return None
    return storm_source(
        opts.get(CONF_SOURCES) or {},
        bool(opts.get(CONF_PATTERN_STORM_INTERNET_LIGHTNING, DEFAULT_PATTERN_STORM_INTERNET_LIGHTNING)),
    )


def internet_choice_needed(hass: Any, opts: dict[str, Any], registry: Any = None) -> bool:
    """Whether the config flow should ask about internet lightning.

    Only when Pattern Forecast is on, no hardware detector is mapped, and
    Blitzortung entities exist. With a detector, or with nothing to offer,
    no question is asked.
    """
    if not opts.get(CONF_ENABLE_PATTERN_FORECAST, DEFAULT_ENABLE_PATTERN_FORECAST):
        return False
    if hardware_detector_mapped(opts.get(CONF_SOURCES)):
        return False
    return bool(find_blitzortung_entities(hass, registry))


def source_fingerprint(sources: dict[str, str] | None, elevation_m: float) -> str:
    """Hash of the mapped source entity ids plus elevation.

    A different station mapped, or an edited elevation, changes the physics the
    models learned (the standardizer would be wrong), so everything resets.
    The lightning mapping is left out: it is covered by the storm label id.
    """
    parts = [f"{k}={v}" for k, v in sorted((sources or {}).items()) if v and not k.startswith("lightning")]
    parts.append(f"elev={round(float(elevation_m))}")
    return hashlib.sha1("|".join(parts).encode()).hexdigest()[:16]
