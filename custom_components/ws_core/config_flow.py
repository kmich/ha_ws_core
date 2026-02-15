"""Config flow for Weather Station Core."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.helpers import selector

from .const import (
    CONF_ELEVATION_M,
    CONF_ENABLE_ACTIVITY_SCORES,
    CONF_FORECAST_ENABLED,
    CONF_FORECAST_INTERVAL_MIN,
    CONF_FORECAST_LAT,
    CONF_FORECAST_LON,
    CONF_NAME,
    CONF_PREFIX,
    CONF_PRESSURE_TREND_WINDOW_H,
    CONF_RAIN_FILTER_ALPHA,
    CONF_RAIN_PENALTY_HEAVY_MMPH,
    CONF_RAIN_PENALTY_LIGHT_MMPH,
    CONF_SOURCES,
    CONF_STALENESS_S,
    CONF_THRESH_FREEZE_C,
    CONF_THRESH_RAIN_RATE_MMPH,
    CONF_THRESH_WIND_GUST_MS,
    CONF_UNITS_MODE,
    DEFAULT_ELEVATION_M,
    DEFAULT_FORECAST_ENABLED,
    DEFAULT_FORECAST_INTERVAL_MIN,
    DEFAULT_NAME,
    DEFAULT_PREFIX,
    DEFAULT_PRESSURE_TREND_WINDOW_H,
    DEFAULT_RAIN_FILTER_ALPHA,
    DEFAULT_RAIN_PENALTY_HEAVY_MMPH,
    DEFAULT_RAIN_PENALTY_LIGHT_MMPH,
    DEFAULT_STALENESS_S,
    DEFAULT_THRESH_FREEZE_C,
    DEFAULT_THRESH_RAIN_RATE_MMPH,
    DEFAULT_THRESH_WIND_GUST_MS,
    DEFAULT_UNITS_MODE,
    DOMAIN,
    OPTIONAL_SOURCES,
    REQUIRED_SOURCES,
    SRC_BATTERY,
    SRC_DEW_POINT,
    SRC_GUST,
    SRC_HUM,
    SRC_LUX,
    SRC_PRESS,
    SRC_RAIN_TOTAL,
    SRC_TEMP,
    SRC_UV,
    SRC_WIND,
    SRC_WIND_DIR,
)


def _guess_defaults(hass: HomeAssistant) -> dict[str, str]:
    """Best-effort auto-guess for Ecowitt/BTHome naming."""
    guess: dict[str, str] = {}
    candidates = [s.entity_id for s in hass.states.async_all()]

    def pick(sub: str) -> str | None:
        for eid in candidates:
            if eid.endswith(sub):
                return eid
        for eid in candidates:
            if sub in eid:
                return eid
        return None

    mapping = {
        SRC_TEMP: ["ws_01_temperature", "ws90_temperature", "temperature"],
        SRC_HUM: ["ws_01_humidity", "ws90_humidity", "humidity"],
        SRC_PRESS: ["ws_01_pressure", "ws90_pressure", "pressure"],
        SRC_WIND: ["ws_01_speed_1", "wind_speed", "speed_1"],
        SRC_GUST: ["ws_01_speed_2", "wind_gust", "speed_2", "gust"],
        SRC_WIND_DIR: ["ws_01_direction", "wind_direction", "direction"],
        SRC_RAIN_TOTAL: ["ws_01_precipitation", "rain_total", "precipitation", "rainfall"],
        SRC_LUX: ["ws_01_illuminance", "illuminance", "lux"],
        SRC_UV: ["ws_01_uv_index", "uv_index", "uv"],
        SRC_DEW_POINT: ["ws_01_dew_point", "dew_point"],
        SRC_BATTERY: ["ws_01_battery", "battery"],
    }

    for k, subs in mapping.items():
        for sub in subs:
            eid = pick(sub)
            if eid:
                guess[k] = eid
                break

    return guess


def _is_imperial(units_mode: str, hass: HomeAssistant) -> bool:
    m = (units_mode or "auto").lower()
    if m == "imperial":
        return True
    if m == "metric":
        return False
    # auto -> follow HA unit system
    try:
        return not bool(hass.config.units.is_metric)
    except Exception:
        return False


def _sanitize_prefix(prefix: str) -> str:
    p = (prefix or "").strip().lower()
    # allow [a-z0-9_] only
    p = "".join(ch if (ch.isalnum() or ch == "_") else "_" for ch in p)
    p = p.strip("_")
    return p or DEFAULT_PREFIX


def _convert_gust_to_display(gust_ms: float, imperial: bool) -> float:
    return gust_ms / 0.44704 if imperial else gust_ms


def _convert_gust_to_ms(val: float, imperial: bool) -> float:
    return val * 0.44704 if imperial else val


def _convert_rain_to_display(mmph: float, imperial: bool) -> float:
    return mmph / 25.4 if imperial else mmph


def _convert_rain_to_mmph(val: float, imperial: bool) -> float:
    return val * 25.4 if imperial else val


def _convert_temp_to_display(c: float, imperial: bool) -> float:
    return (c * 9.0 / 5.0) + 32.0 if imperial else c


def _convert_temp_to_c(val: float, imperial: bool) -> float:
    return (val - 32.0) * 5.0 / 9.0 if imperial else val


class WSStationConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def async_get_options_flow(self, config_entry: config_entries.ConfigEntry):
        return WSStationOptionsFlowHandler(config_entry)

    def __init__(self):
        self._data: dict[str, Any] = {}

    def _validate_numeric_sensor(self, eid: str) -> bool:
        st = self.hass.states.get(eid)
        if st is None:
            return False
        if st.state in ("unknown", "unavailable", None):
            return False
        try:
            float(st.state)
            return True
        except Exception:
            return False

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            self._data[CONF_NAME] = str(user_input.get(CONF_NAME) or DEFAULT_NAME)
            self._data[CONF_PREFIX] = _sanitize_prefix(str(user_input.get(CONF_PREFIX) or DEFAULT_PREFIX))
            return await self.async_step_required_sources()

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
                vol.Required(CONF_PREFIX, default=DEFAULT_PREFIX): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema)

    async def async_step_required_sources(self, user_input: dict[str, Any] | None = None):
        defaults = _guess_defaults(self.hass)
        errors: dict[str, str] = {}

        if user_input is not None:
            # validate required mappings
            for k in REQUIRED_SOURCES:
                eid = user_input.get(k)
                if not eid:
                    errors[k] = "required"
                    continue
                if self.hass.states.get(eid) is None:
                    errors[k] = "entity_not_found"
                    continue
                if not self._validate_numeric_sensor(eid):
                    errors[k] = "not_numeric"
            if not errors:
                sources = dict(self._data.get(CONF_SOURCES, {}))
                for k in REQUIRED_SOURCES:
                    sources[k] = user_input[k]
                self._data[CONF_SOURCES] = sources
                return await self.async_step_optional_sources()

        fields: dict[Any, Any] = {}
        for k in REQUIRED_SOURCES:
            fields[vol.Required(k, default=defaults.get(k))] = selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            )

        return self.async_show_form(step_id="required_sources", data_schema=vol.Schema(fields), errors=errors)

    async def async_step_optional_sources(self, user_input: dict[str, Any] | None = None):
        defaults = _guess_defaults(self.hass)
        errors: dict[str, str] = {}

        if user_input is not None:
            sources = dict(self._data.get(CONF_SOURCES, {}))
            for k in OPTIONAL_SOURCES:
                eid = user_input.get(k)
                if not eid:
                    continue
                if self.hass.states.get(eid) is None:
                    errors[k] = "entity_not_found"
                elif not self._validate_numeric_sensor(eid):
                    errors[k] = "not_numeric"
                else:
                    sources[k] = eid

            if not errors:
                self._data[CONF_SOURCES] = sources
                return await self.async_step_settings()

        fields: dict[Any, Any] = {}
        for k in OPTIONAL_SOURCES:
            fields[vol.Optional(k, default=defaults.get(k))] = selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            )

        return self.async_show_form(step_id="optional_sources", data_schema=vol.Schema(fields), errors=errors)

    async def async_step_settings(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_alerts()

        schema = vol.Schema(
            {
                vol.Optional(CONF_UNITS_MODE, default=DEFAULT_UNITS_MODE): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=["auto", "metric", "imperial"],
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Optional(CONF_ELEVATION_M, default=DEFAULT_ELEVATION_M): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=-500, max=5000, step=1, mode=selector.NumberSelectorMode.BOX, unit_of_measurement="m")
                ),
                vol.Optional(CONF_STALENESS_S, default=DEFAULT_STALENESS_S): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=60, max=86400, step=60, mode=selector.NumberSelectorMode.BOX, unit_of_measurement="s")
                ),
                vol.Optional(CONF_FORECAST_ENABLED, default=DEFAULT_FORECAST_ENABLED): selector.BooleanSelector(),
                vol.Optional(CONF_FORECAST_INTERVAL_MIN, default=DEFAULT_FORECAST_INTERVAL_MIN): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=10, max=180, step=5, mode=selector.NumberSelectorMode.BOX, unit_of_measurement="min")
                ),
                vol.Optional(CONF_FORECAST_LAT, default=self.hass.config.latitude or 0.0): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=-90, max=90, step=0.0001, mode=selector.NumberSelectorMode.BOX)
                ),
                vol.Optional(CONF_FORECAST_LON, default=self.hass.config.longitude or 0.0): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=-180, max=180, step=0.0001, mode=selector.NumberSelectorMode.BOX)
                ),
            }
        )
        return self.async_show_form(step_id="settings", data_schema=schema)

    async def async_step_alerts(self, user_input: dict[str, Any] | None = None):
        units_mode = str(self._data.get(CONF_UNITS_MODE, DEFAULT_UNITS_MODE))
        imperial = _is_imperial(units_mode, self.hass)

        gust_u = "mph" if imperial else "m/s"
        rain_u = "in/h" if imperial else "mm/h"
        temp_u = "°F" if imperial else "°C"

        if user_input is not None:
            # Convert display units to canonical metric storage
            self._data[CONF_THRESH_WIND_GUST_MS] = float(_convert_gust_to_ms(float(user_input.get(CONF_THRESH_WIND_GUST_MS, DEFAULT_THRESH_WIND_GUST_MS)), imperial))
            self._data[CONF_THRESH_RAIN_RATE_MMPH] = float(_convert_rain_to_mmph(float(user_input.get(CONF_THRESH_RAIN_RATE_MMPH, DEFAULT_THRESH_RAIN_RATE_MMPH)), imperial))
            self._data[CONF_THRESH_FREEZE_C] = float(_convert_temp_to_c(float(user_input.get(CONF_THRESH_FREEZE_C, DEFAULT_THRESH_FREEZE_C)), imperial))

            self._data[CONF_RAIN_FILTER_ALPHA] = float(user_input.get(CONF_RAIN_FILTER_ALPHA, DEFAULT_RAIN_FILTER_ALPHA))
            self._data[CONF_PRESSURE_TREND_WINDOW_H] = int(user_input.get(CONF_PRESSURE_TREND_WINDOW_H, DEFAULT_PRESSURE_TREND_WINDOW_H))
            self._data[CONF_ENABLE_ACTIVITY_SCORES] = bool(user_input.get(CONF_ENABLE_ACTIVITY_SCORES, False))

            self._data[CONF_RAIN_PENALTY_LIGHT_MMPH] = float(_convert_rain_to_mmph(float(user_input.get(CONF_RAIN_PENALTY_LIGHT_MMPH, DEFAULT_RAIN_PENALTY_LIGHT_MMPH)), imperial))
            self._data[CONF_RAIN_PENALTY_HEAVY_MMPH] = float(_convert_rain_to_mmph(float(user_input.get(CONF_RAIN_PENALTY_HEAVY_MMPH, DEFAULT_RAIN_PENALTY_HEAVY_MMPH)), imperial))

            title = self._data.get(CONF_NAME, DEFAULT_NAME)
            return self.async_create_entry(title=title, data=self._data)

        schema = vol.Schema(
            {
                vol.Optional(CONF_THRESH_WIND_GUST_MS, default=round(_convert_gust_to_display(DEFAULT_THRESH_WIND_GUST_MS, imperial), 1)): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=0, max=60, step=0.1, mode=selector.NumberSelectorMode.BOX, unit_of_measurement=gust_u)
                ),
                vol.Optional(CONF_THRESH_RAIN_RATE_MMPH, default=round(_convert_rain_to_display(DEFAULT_THRESH_RAIN_RATE_MMPH, imperial), 2)): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=0, max=200, step=0.1, mode=selector.NumberSelectorMode.BOX, unit_of_measurement=rain_u)
                ),
                vol.Optional(CONF_THRESH_FREEZE_C, default=round(_convert_temp_to_display(DEFAULT_THRESH_FREEZE_C, imperial), 1)): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=-50, max=50, step=0.1, mode=selector.NumberSelectorMode.BOX, unit_of_measurement=temp_u)
                ),
                vol.Optional(CONF_RAIN_FILTER_ALPHA, default=DEFAULT_RAIN_FILTER_ALPHA): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=0.05, max=1.0, step=0.05, mode=selector.NumberSelectorMode.BOX)
                ),
                vol.Optional(CONF_PRESSURE_TREND_WINDOW_H, default=DEFAULT_PRESSURE_TREND_WINDOW_H): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=1, max=12, step=1, mode=selector.NumberSelectorMode.BOX, unit_of_measurement="h")
                ),
                vol.Optional(CONF_ENABLE_ACTIVITY_SCORES, default=False): selector.BooleanSelector(),
                vol.Optional(CONF_RAIN_PENALTY_LIGHT_MMPH, default=round(_convert_rain_to_display(DEFAULT_RAIN_PENALTY_LIGHT_MMPH, imperial), 2)): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=0, max=10, step=0.1, mode=selector.NumberSelectorMode.BOX, unit_of_measurement=rain_u)
                ),
                vol.Optional(CONF_RAIN_PENALTY_HEAVY_MMPH, default=round(_convert_rain_to_display(DEFAULT_RAIN_PENALTY_HEAVY_MMPH, imperial), 2)): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=0.1, max=50, step=0.1, mode=selector.NumberSelectorMode.BOX, unit_of_measurement=rain_u)
                ),
            }
        )
        return self.async_show_form(step_id="alerts", data_schema=schema)


class WSStationOptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry: config_entries.ConfigEntry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        units_mode = str(self.config_entry.options.get(CONF_UNITS_MODE, self.config_entry.data.get(CONF_UNITS_MODE, DEFAULT_UNITS_MODE)))
        imperial = _is_imperial(units_mode, self.hass)

        gust_u = "mph" if imperial else "m/s"
        rain_u = "in/h" if imperial else "mm/h"
        temp_u = "°F" if imperial else "°C"

        if user_input is not None:
            out = dict(user_input)

            # Prefix sanitize
            if CONF_PREFIX in out:
                out[CONF_PREFIX] = _sanitize_prefix(str(out[CONF_PREFIX]))

            # Convert thresholds to canonical metric for coordinator
            out[CONF_THRESH_WIND_GUST_MS] = float(_convert_gust_to_ms(float(out.get(CONF_THRESH_WIND_GUST_MS, DEFAULT_THRESH_WIND_GUST_MS)), imperial))
            out[CONF_THRESH_RAIN_RATE_MMPH] = float(_convert_rain_to_mmph(float(out.get(CONF_THRESH_RAIN_RATE_MMPH, DEFAULT_THRESH_RAIN_RATE_MMPH)), imperial))
            out[CONF_THRESH_FREEZE_C] = float(_convert_temp_to_c(float(out.get(CONF_THRESH_FREEZE_C, DEFAULT_THRESH_FREEZE_C)), imperial))

            out[CONF_RAIN_PENALTY_LIGHT_MMPH] = float(_convert_rain_to_mmph(float(out.get(CONF_RAIN_PENALTY_LIGHT_MMPH, DEFAULT_RAIN_PENALTY_LIGHT_MMPH)), imperial))
            out[CONF_RAIN_PENALTY_HEAVY_MMPH] = float(_convert_rain_to_mmph(float(out.get(CONF_RAIN_PENALTY_HEAVY_MMPH, DEFAULT_RAIN_PENALTY_HEAVY_MMPH)), imperial))

            return self.async_create_entry(title="", data=out)

        # Read current metric options and convert for display
        cur_gust_ms = float(self.config_entry.options.get(CONF_THRESH_WIND_GUST_MS, self.config_entry.data.get(CONF_THRESH_WIND_GUST_MS, DEFAULT_THRESH_WIND_GUST_MS)))
        cur_rain_mmph = float(self.config_entry.options.get(CONF_THRESH_RAIN_RATE_MMPH, self.config_entry.data.get(CONF_THRESH_RAIN_RATE_MMPH, DEFAULT_THRESH_RAIN_RATE_MMPH)))
        cur_freeze_c = float(self.config_entry.options.get(CONF_THRESH_FREEZE_C, self.config_entry.data.get(CONF_THRESH_FREEZE_C, DEFAULT_THRESH_FREEZE_C)))
        cur_alpha = float(self.config_entry.options.get(CONF_RAIN_FILTER_ALPHA, self.config_entry.data.get(CONF_RAIN_FILTER_ALPHA, DEFAULT_RAIN_FILTER_ALPHA)))
        cur_window_h = int(self.config_entry.options.get(CONF_PRESSURE_TREND_WINDOW_H, self.config_entry.data.get(CONF_PRESSURE_TREND_WINDOW_H, DEFAULT_PRESSURE_TREND_WINDOW_H)))
        cur_enable_scores = bool(self.config_entry.options.get(CONF_ENABLE_ACTIVITY_SCORES, self.config_entry.data.get(CONF_ENABLE_ACTIVITY_SCORES, False)))
        cur_light = float(self.config_entry.options.get(CONF_RAIN_PENALTY_LIGHT_MMPH, self.config_entry.data.get(CONF_RAIN_PENALTY_LIGHT_MMPH, DEFAULT_RAIN_PENALTY_LIGHT_MMPH)))
        cur_heavy = float(self.config_entry.options.get(CONF_RAIN_PENALTY_HEAVY_MMPH, self.config_entry.data.get(CONF_RAIN_PENALTY_HEAVY_MMPH, DEFAULT_RAIN_PENALTY_HEAVY_MMPH)))

        schema = vol.Schema(
            {
                vol.Optional(CONF_PREFIX, default=self.config_entry.options.get(CONF_PREFIX, self.config_entry.data.get(CONF_PREFIX, DEFAULT_PREFIX))): str,
                vol.Optional(CONF_UNITS_MODE, default=units_mode): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=["auto", "metric", "imperial"], mode=selector.SelectSelectorMode.DROPDOWN)
                ),
                vol.Optional(CONF_ELEVATION_M, default=self.config_entry.options.get(CONF_ELEVATION_M, self.config_entry.data.get(CONF_ELEVATION_M, DEFAULT_ELEVATION_M))): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=-500, max=5000, step=1, mode=selector.NumberSelectorMode.BOX, unit_of_measurement="m")
                ),
                vol.Optional(CONF_STALENESS_S, default=self.config_entry.options.get(CONF_STALENESS_S, self.config_entry.data.get(CONF_STALENESS_S, DEFAULT_STALENESS_S))): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=60, max=86400, step=60, mode=selector.NumberSelectorMode.BOX, unit_of_measurement="s")
                ),
                vol.Optional(CONF_FORECAST_ENABLED, default=self.config_entry.options.get(CONF_FORECAST_ENABLED, self.config_entry.data.get(CONF_FORECAST_ENABLED, DEFAULT_FORECAST_ENABLED))): selector.BooleanSelector(),
                vol.Optional(CONF_FORECAST_INTERVAL_MIN, default=self.config_entry.options.get(CONF_FORECAST_INTERVAL_MIN, self.config_entry.data.get(CONF_FORECAST_INTERVAL_MIN, DEFAULT_FORECAST_INTERVAL_MIN))): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=10, max=180, step=5, mode=selector.NumberSelectorMode.BOX, unit_of_measurement="min")
                ),
                vol.Optional(CONF_FORECAST_LAT, default=self.config_entry.options.get(CONF_FORECAST_LAT, self.config_entry.data.get(CONF_FORECAST_LAT, self.hass.config.latitude or 0.0))): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=-90, max=90, step=0.0001, mode=selector.NumberSelectorMode.BOX)
                ),
                vol.Optional(CONF_FORECAST_LON, default=self.config_entry.options.get(CONF_FORECAST_LON, self.config_entry.data.get(CONF_FORECAST_LON, self.hass.config.longitude or 0.0))): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=-180, max=180, step=0.0001, mode=selector.NumberSelectorMode.BOX)
                ),
                # Alerts & heuristics
                vol.Optional(CONF_THRESH_WIND_GUST_MS, default=round(_convert_gust_to_display(cur_gust_ms, imperial), 1)): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=0, max=60, step=0.1, mode=selector.NumberSelectorMode.BOX, unit_of_measurement=gust_u)
                ),
                vol.Optional(CONF_THRESH_RAIN_RATE_MMPH, default=round(_convert_rain_to_display(cur_rain_mmph, imperial), 2)): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=0, max=200, step=0.1, mode=selector.NumberSelectorMode.BOX, unit_of_measurement=rain_u)
                ),
                vol.Optional(CONF_THRESH_FREEZE_C, default=round(_convert_temp_to_display(cur_freeze_c, imperial), 1)): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=-50, max=50, step=0.1, mode=selector.NumberSelectorMode.BOX, unit_of_measurement=temp_u)
                ),
                vol.Optional(CONF_RAIN_FILTER_ALPHA, default=cur_alpha): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=0.05, max=1.0, step=0.05, mode=selector.NumberSelectorMode.BOX)
                ),
                vol.Optional(CONF_PRESSURE_TREND_WINDOW_H, default=cur_window_h): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=1, max=12, step=1, mode=selector.NumberSelectorMode.BOX, unit_of_measurement="h")
                ),
                vol.Optional(CONF_ENABLE_ACTIVITY_SCORES, default=cur_enable_scores): selector.BooleanSelector(),
                vol.Optional(CONF_RAIN_PENALTY_LIGHT_MMPH, default=round(_convert_rain_to_display(cur_light, imperial), 2)): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=0, max=10, step=0.1, mode=selector.NumberSelectorMode.BOX, unit_of_measurement=rain_u)
                ),
                vol.Optional(CONF_RAIN_PENALTY_HEAVY_MMPH, default=round(_convert_rain_to_display(cur_heavy, imperial), 2)): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=0.1, max=50, step=0.1, mode=selector.NumberSelectorMode.BOX, unit_of_measurement=rain_u)
                ),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)