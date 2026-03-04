"""Weather Station Core integration."""

from __future__ import annotations

import json
import logging
import pathlib
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

    coordinator = WSStationCoordinator(hass, {**entry.data, "entry_id": entry.entry_id}, entry.options)
    coordinator._entry = entry  # stored for learning service callbacks
    # Register before async_start so that async_forward_entry_setups can
    # find it; clean up on failure so no ghost entry remains.
    hass.data[DOMAIN][entry.entry_id] = coordinator

    try:
        await coordinator.async_start()
    except Exception:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        raise

    # Create a device for the station
    dev_reg = dr.async_get(hass)
    _manifest = json.loads((pathlib.Path(__file__).parent / "manifest.json").read_text(encoding="utf-8"))
    dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.title,
        manufacturer="Weather Station Core",
        model="Derived Weather Package",
        sw_version=_manifest.get("version", "unknown"),
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
            # Reset the Kalman filter so stale estimates don't bleed into the new baseline.
            # Preserve measurement_noise so user tuning via rain_filter_alpha is retained.
            coord.runtime.kalman = type(coord.runtime.kalman)(measurement_noise=coord.runtime.kalman.measurement_noise)
            await coord.async_refresh()

    # Register services once per integration domain (idempotent)
    if not hass.services.has_service(DOMAIN, SERVICE_RESET_RAIN):
        hass.services.async_register(DOMAIN, SERVICE_RESET_RAIN, _reset_rain, schema=SERVICE_RESET_RAIN_SCHEMA)

    # ── v1.2.0 learning services ───────────────────────────────────────────
    SERVICE_APPLY_CAL = "apply_learned_calibration"
    SERVICE_RESET_LEARNING = "reset_learning_state"
    SERVICE_EXPORT_LEARNING = "export_learning_state"

    SERVICE_APPLY_CAL_SCHEMA = vol.Schema({vol.Optional(ATTR_ENTRY_ID): cv.string})
    SERVICE_RESET_LEARNING_SCHEMA = vol.Schema(
        {
            vol.Optional(ATTR_ENTRY_ID): cv.string,
            vol.Optional("target", default="all"): vol.In(["all", "temp", "pressure", "solar", "forecast", "streaks"]),
        }
    )
    SERVICE_EXPORT_LEARNING_SCHEMA = vol.Schema({vol.Optional(ATTR_ENTRY_ID): cv.string})

    def _get_targets(call: ServiceCall) -> list:
        entry_id = call.data.get(ATTR_ENTRY_ID)
        if entry_id:
            coord = hass.data[DOMAIN].get(entry_id)
            return [coord] if coord else []
        return list(hass.data[DOMAIN].values())

    async def _apply_cal(call: ServiceCall) -> None:
        from .learning_state import MIN_SAMPLES_MEDIUM

        for coord in _get_targets(call):
            ls = coord._learning_state
            opts = dict(coord._entry.options if hasattr(coord, "_entry") else {})
            changed = False
            if ls.temp_bias_ema is not None and ls.temp_bias_n >= MIN_SAMPLES_MEDIUM:
                suggestion = round(-ls.temp_bias_ema, 1)
                current = float(opts.get("cal_temp_c", 0.0))
                opts["cal_temp_c"] = round(current + suggestion, 1)
                _LOGGER.info("ws_core: applying learned temp cal: %+.1f°C (was %.1f)", suggestion, current)
                changed = True
            if ls.pressure_bias_ema is not None and ls.pressure_bias_n >= MIN_SAMPLES_MEDIUM:
                suggestion = round(-ls.pressure_bias_ema, 1)
                current = float(opts.get("cal_pressure_hpa", 0.0))
                opts["cal_pressure_hpa"] = round(current + suggestion, 1)
                _LOGGER.info("ws_core: applying learned pressure cal: %+.1f hPa (was %.1f)", suggestion, current)
                changed = True
            if changed and hasattr(coord, "_entry"):
                hass.config_entries.async_update_entry(coord._entry, options=opts)

    async def _reset_learning(call: ServiceCall) -> None:
        from .learning_state import async_save_learning

        target = call.data.get("target", "all")
        for coord in _get_targets(call):
            ls = coord._learning_state
            if target in ("all", "temp"):
                ls.temp_bias_ema = None
                ls.temp_bias_n = 0
            if target in ("all", "pressure"):
                ls.pressure_bias_ema = None
                ls.pressure_bias_n = 0
            if target in ("all", "solar"):
                ls.solar_lux_factor = 126.0
                ls.solar_factor_n = 0
            if target in ("all", "forecast"):
                ls.forecast_outcomes = []
                ls.blend_local = 0.5
                ls.blend_openmeteo = 0.5
            if target in ("all", "streaks"):
                ls.dry_streak_days = 0
                ls.heat_streak_days = 0
                ls.frost_streak_days = 0
                ls.gdd_season_total = 0.0
            if coord._learning_store is not None:
                await async_save_learning(coord._learning_store, ls)
            _LOGGER.info("ws_core: learning state reset (target=%s)", target)

    async def _export_learning(call: ServiceCall) -> None:
        for coord in _get_targets(call):
            payload = coord._learning_state.to_dict()
            _LOGGER.info("ws_core learning state export: %s", payload)
            # Service response is only visible via HA service call UI / REST API
            return {"learning_state": payload}

    if not hass.services.has_service(DOMAIN, SERVICE_APPLY_CAL):
        hass.services.async_register(DOMAIN, SERVICE_APPLY_CAL, _apply_cal, schema=SERVICE_APPLY_CAL_SCHEMA)
    if not hass.services.has_service(DOMAIN, SERVICE_RESET_LEARNING):
        hass.services.async_register(
            DOMAIN, SERVICE_RESET_LEARNING, _reset_learning, schema=SERVICE_RESET_LEARNING_SCHEMA
        )
    if not hass.services.has_service(DOMAIN, SERVICE_EXPORT_LEARNING):
        hass.services.async_register(
            DOMAIN, SERVICE_EXPORT_LEARNING, _export_learning, schema=SERVICE_EXPORT_LEARNING_SCHEMA
        )

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
