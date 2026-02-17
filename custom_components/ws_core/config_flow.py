"""Config flow for Weather Station Core.

Setup wizard walks the user through:
  Step 1 (user)            – Station name & entity prefix
  Step 2 (required_sources)– Map the 7 required sensors
  Step 3 (optional_sources)– Map optional sensors (lux, UV, dew point, battery)
  Step 4 (location)        – Hemisphere, climate region, elevation (auto-detected)
  Step 5 (display)         – Units / temperature display preference
  Step 6 (forecast)        – Open-Meteo forecast options
  Step 7 (alerts)          – Alert thresholds & advanced options

The Options flow (Configure button) exposes all settings for post-install changes.
"""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.helpers import selector

from .const import (
    CLIMATE_REGION_OPTIONS,
    CONF_CLIMATE_REGION,
    CONF_ELEVATION_M,
    CONF_ENABLE_ACTIVITY_SCORES,
    CONF_FORECAST_ENABLED,
    CONF_FORECAST_INTERVAL_MIN,
    CONF_FORECAST_LAT,
    CONF_FORECAST_LON,
    CONF_HEMISPHERE,
    CONF_NAME,
    CONF_PREFIX,
    CONF_PRESSURE_TREND_WINDOW_H,
    CONF_RAIN_FILTER_ALPHA,
    CONF_RAIN_PENALTY_HEAVY_MMPH,
    CONF_RAIN_PENALTY_LIGHT_MMPH,
    CONF_SOURCES,
    CONF_STALENESS_S,
    CONF_TEMP_UNIT,
    CONF_THRESH_FREEZE_C,
    CONF_THRESH_RAIN_RATE_MMPH,
    CONF_THRESH_WIND_GUST_MS,
    CONF_UNITS_MODE,
    CONFIG_VERSION,
    DEFAULT_CLIMATE_REGION,
    DEFAULT_ELEVATION_M,
    DEFAULT_ENABLE_ACTIVITY_SCORES,
    DEFAULT_FORECAST_ENABLED,
    DEFAULT_FORECAST_INTERVAL_MIN,
    DEFAULT_HEMISPHERE,
    DEFAULT_NAME,
    DEFAULT_PREFIX,
    DEFAULT_PRESSURE_TREND_WINDOW_H,
    DEFAULT_RAIN_FILTER_ALPHA,
    DEFAULT_RAIN_PENALTY_HEAVY_MMPH,
    DEFAULT_RAIN_PENALTY_LIGHT_MMPH,
    DEFAULT_STALENESS_S,
    DEFAULT_TEMP_UNIT,
    DEFAULT_THRESH_FREEZE_C,
    DEFAULT_THRESH_RAIN_RATE_MMPH,
    DEFAULT_THRESH_WIND_GUST_MS,
    DEFAULT_UNITS_MODE,
    DOMAIN,
    HEMISPHERE_OPTIONS,
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
    TEMP_UNIT_OPTIONS,
    UNITS_MODE_OPTIONS,
    VALID_ELEVATION_MAX_M,
    VALID_ELEVATION_MIN_M,
    VALID_TEMP_MAX_C,
    VALID_TEMP_MIN_C,
    VALID_WIND_GUST_MAX_MS,
)

_LOGGER = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sanitize_prefix(prefix: str) -> str:
    p = (prefix or "").strip().lower()
    p = "".join(ch if (ch.isalnum() or ch == "_") else "_" for ch in p)
    p = p.strip("_")
    return p or DEFAULT_PREFIX


def _guess_defaults(hass: HomeAssistant) -> dict[str, str]:
    """Best-effort auto-detection of sensor entity IDs by name pattern."""
    guess: dict[str, str] = {}
    candidates = [s.entity_id for s in hass.states.async_all()]

    def pick(subs: list[str]) -> str | None:
        for sub in subs:
            for eid in candidates:
                if eid.endswith(sub):
                    return eid
        for sub in subs:
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
        eid = pick(subs)
        if eid:
            guess[k] = eid
    return guess


def _auto_detect_elevation(hass: HomeAssistant) -> float:
    """Try to read elevation from multiple sources in priority order.

    Priority:
      1. HA system configuration (hass.config.elevation)
      2. Weather station entity attribute 'elevation' or 'altitude'
      3. Fall back to 0.0
    """
    # 1. HA system config
    try:
        elev = float(hass.config.elevation)
        if VALID_ELEVATION_MIN_M <= elev <= VALID_ELEVATION_MAX_M:
            _LOGGER.debug("Elevation auto-detected from HA config: %.1f m", elev)
            return round(elev, 1)
    except (TypeError, ValueError):
        pass

    # 2. Scan entity states for elevation/altitude attributes
    for state in hass.states.async_all():
        attrs = state.attributes
        for attr_key in ("elevation", "altitude", "elevation_m", "alt_m"):
            raw = attrs.get(attr_key)
            if raw is not None:
                try:
                    elev = float(raw)
                    if VALID_ELEVATION_MIN_M <= elev <= VALID_ELEVATION_MAX_M:
                        _LOGGER.debug(
                            "Elevation auto-detected from entity %s attr '%s': %.1f m",
                            state.entity_id,
                            attr_key,
                            elev,
                        )
                        return round(elev, 1)
                except (TypeError, ValueError):
                    continue

    return DEFAULT_ELEVATION_M


def _guess_hemisphere(hass: HomeAssistant) -> str:
    """Infer hemisphere from HA system latitude."""
    try:
        lat = float(hass.config.latitude)
        return "Southern" if lat < 0 else "Northern"
    except (TypeError, ValueError):
        return DEFAULT_HEMISPHERE


def _guess_climate_region(hass: HomeAssistant) -> str:
    """Best-effort climate region guess from HA lat/lon."""
    try:
        lat = float(hass.config.latitude)
        lon = float(hass.config.longitude)
    except (TypeError, ValueError):
        return DEFAULT_CLIMATE_REGION

    # Southern hemisphere → Australia (only option currently)
    if lat < 0:
        return "Australia"
    # Scandinavia
    if lat > 55 and 5 <= lon <= 32:
        return "Scandinavia"
    # Mediterranean
    if 30 <= lat <= 47 and -5 <= lon <= 40:
        return "Mediterranean"
    # North America
    if -170 <= lon <= -50:
        return "North America East" if lon > -100 else "North America West"
    # Continental Europe (east of 15°E)
    if lon > 15:
        return "Continental Europe"
    # Default Atlantic Europe
    return "Atlantic Europe"


def _is_imperial(units_mode: str, hass: HomeAssistant) -> bool:
    m = (units_mode or "auto").lower()
    if m == "imperial":
        return True
    if m == "metric":
        return False
    try:
        return hass.config.units.temperature_unit != "°C"
    except Exception:
        return False


def _convert_gust_to_display(ms: float, imperial: bool) -> float:
    return ms / 0.44704 if imperial else ms


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


# ---------------------------------------------------------------------------
# Config Flow
# ---------------------------------------------------------------------------


class WSStationConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = CONFIG_VERSION

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        return WSStationOptionsFlowHandler()

    def __init__(self):
        self._data: dict[str, Any] = {}

    def _validate_numeric_sensor(self, eid: str) -> bool:
        st = self.hass.states.get(eid)
        if st is None or st.state in ("unknown", "unavailable"):
            return False
        try:
            float(st.state)
            return True
        except (ValueError, TypeError):
            return False

    # ------------------------------------------------------------------
    # Step 1: Name & prefix
    # ------------------------------------------------------------------
    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            self._data[CONF_NAME] = str(user_input.get(CONF_NAME) or DEFAULT_NAME)
            self._data[CONF_PREFIX] = _sanitize_prefix(str(user_input.get(CONF_PREFIX) or DEFAULT_PREFIX))
            return await self.async_step_required_sources()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
                    vol.Required(CONF_PREFIX, default=DEFAULT_PREFIX): str,
                }
            ),
        )

    # ------------------------------------------------------------------
    # Step 2: Required sensor mapping
    # ------------------------------------------------------------------
    async def async_step_required_sources(self, user_input: dict[str, Any] | None = None):
        defaults = _guess_defaults(self.hass)
        errors: dict[str, str] = {}

        if user_input is not None:
            for k in REQUIRED_SOURCES:
                eid = user_input.get(k)
                if not eid:
                    errors[k] = "required"
                elif self.hass.states.get(eid) is None:
                    errors[k] = "entity_not_found"
                elif not self._validate_numeric_sensor(eid):
                    errors[k] = "not_numeric"
            if not errors:
                sources = {k: user_input[k] for k in REQUIRED_SOURCES}
                self._data[CONF_SOURCES] = sources
                return await self.async_step_optional_sources()

        fields = {
            vol.Required(k, default=defaults.get(k)): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            )
            for k in REQUIRED_SOURCES
        }
        return self.async_show_form(step_id="required_sources", data_schema=vol.Schema(fields), errors=errors)

    # ------------------------------------------------------------------
    # Step 3: Optional sensor mapping
    # ------------------------------------------------------------------
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
                return await self.async_step_location()

        fields = {
            vol.Optional(k, default=defaults.get(k)): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            )
            for k in OPTIONAL_SOURCES
        }
        return self.async_show_form(step_id="optional_sources", data_schema=vol.Schema(fields), errors=errors)

    # ------------------------------------------------------------------
    # Step 4: Location — hemisphere, climate region, elevation
    # ------------------------------------------------------------------
    async def async_step_location(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}

        auto_elev = _auto_detect_elevation(self.hass)
        auto_hemi = _guess_hemisphere(self.hass)
        auto_region = _guess_climate_region(self.hass)

        if user_input is not None:
            elev = float(user_input.get(CONF_ELEVATION_M, auto_elev))
            if not (VALID_ELEVATION_MIN_M <= elev <= VALID_ELEVATION_MAX_M):
                errors[CONF_ELEVATION_M] = "elevation_out_of_range"

            if not errors:
                self._data[CONF_HEMISPHERE] = user_input[CONF_HEMISPHERE]
                self._data[CONF_CLIMATE_REGION] = user_input[CONF_CLIMATE_REGION]
                self._data[CONF_ELEVATION_M] = elev
                return await self.async_step_display()

        return self.async_show_form(
            step_id="location",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HEMISPHERE, default=auto_hemi): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=HEMISPHERE_OPTIONS,
                            mode="list",
                            translation_key="hemisphere",
                        )
                    ),
                    vol.Required(CONF_CLIMATE_REGION, default=auto_region): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=CLIMATE_REGION_OPTIONS,
                            mode="dropdown",
                            translation_key="climate_region",
                        )
                    ),
                    vol.Optional(CONF_ELEVATION_M, default=auto_elev): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=VALID_ELEVATION_MIN_M,
                            max=VALID_ELEVATION_MAX_M,
                            step=1,
                            mode="box",
                            unit_of_measurement="m",
                        )
                    ),
                }
            ),
            errors=errors,
        )

    # ------------------------------------------------------------------
    # Step 5: Display units
    # ------------------------------------------------------------------
    async def async_step_display(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            self._data[CONF_UNITS_MODE] = user_input[CONF_UNITS_MODE]
            self._data[CONF_TEMP_UNIT] = user_input[CONF_TEMP_UNIT]
            return await self.async_step_forecast()

        # Guess sensible defaults from HA unit system
        try:
            is_metric = self.hass.config.units.temperature_unit == "°C"
            default_units = "metric" if is_metric else "imperial"
            default_temp = "C" if is_metric else "F"
        except Exception:
            default_units = DEFAULT_UNITS_MODE
            default_temp = DEFAULT_TEMP_UNIT

        return self.async_show_form(
            step_id="display",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_UNITS_MODE, default=default_units): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                {"value": "auto", "label": "Auto (follow Home Assistant)"},
                                {"value": "metric", "label": "Metric (km/h, mm, hPa)"},
                                {"value": "imperial", "label": "Imperial (mph, in, inHg)"},
                            ],
                            mode="list",
                        )
                    ),
                    vol.Required(CONF_TEMP_UNIT, default=default_temp): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                {"value": "auto", "label": "Auto (follow Home Assistant)"},
                                {"value": "C", "label": "Celsius (°C)"},
                                {"value": "F", "label": "Fahrenheit (°F)"},
                            ],
                            mode="list",
                        )
                    ),
                }
            ),
        )

    # ------------------------------------------------------------------
    # Step 6: Forecast
    # ------------------------------------------------------------------
    async def async_step_forecast(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_alerts()

        default_lat = getattr(self.hass.config, "latitude", 0.0) or 0.0
        default_lon = getattr(self.hass.config, "longitude", 0.0) or 0.0

        return self.async_show_form(
            step_id="forecast",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_FORECAST_ENABLED, default=DEFAULT_FORECAST_ENABLED): selector.BooleanSelector(),
                    vol.Optional(
                        CONF_FORECAST_INTERVAL_MIN, default=DEFAULT_FORECAST_INTERVAL_MIN
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=10, max=180, step=5, mode="box", unit_of_measurement="min")
                    ),
                    vol.Optional(CONF_FORECAST_LAT, default=round(default_lat, 4)): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=-90, max=90, step=0.001, mode="box")
                    ),
                    vol.Optional(CONF_FORECAST_LON, default=round(default_lon, 4)): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=-180, max=180, step=0.001, mode="box")
                    ),
                }
            ),
        )

    # ------------------------------------------------------------------
    # Step 7: Alerts & advanced options
    # ------------------------------------------------------------------
    async def async_step_alerts(self, user_input: dict[str, Any] | None = None):
        units_mode = str(self._data.get(CONF_UNITS_MODE, DEFAULT_UNITS_MODE))
        imperial = _is_imperial(units_mode, self.hass)
        gust_u = "mph" if imperial else "m/s"
        rain_u = "in/h" if imperial else "mm/h"
        temp_u = "°F" if imperial else "°C"

        if user_input is not None:
            errors = self._validate_alert_inputs(user_input, imperial)
            if not errors:
                self._data[CONF_THRESH_WIND_GUST_MS] = _convert_gust_to_ms(
                    float(user_input[CONF_THRESH_WIND_GUST_MS]), imperial
                )
                self._data[CONF_THRESH_RAIN_RATE_MMPH] = _convert_rain_to_mmph(
                    float(user_input[CONF_THRESH_RAIN_RATE_MMPH]), imperial
                )
                self._data[CONF_THRESH_FREEZE_C] = _convert_temp_to_c(float(user_input[CONF_THRESH_FREEZE_C]), imperial)
                self._data[CONF_RAIN_FILTER_ALPHA] = float(user_input[CONF_RAIN_FILTER_ALPHA])
                self._data[CONF_PRESSURE_TREND_WINDOW_H] = int(user_input[CONF_PRESSURE_TREND_WINDOW_H])
                self._data[CONF_ENABLE_ACTIVITY_SCORES] = bool(user_input[CONF_ENABLE_ACTIVITY_SCORES])
                self._data[CONF_STALENESS_S] = int(user_input[CONF_STALENESS_S])
                self._data[CONF_RAIN_PENALTY_LIGHT_MMPH] = _convert_rain_to_mmph(
                    float(user_input[CONF_RAIN_PENALTY_LIGHT_MMPH]), imperial
                )
                self._data[CONF_RAIN_PENALTY_HEAVY_MMPH] = _convert_rain_to_mmph(
                    float(user_input[CONF_RAIN_PENALTY_HEAVY_MMPH]), imperial
                )

                title = self._data.get(CONF_NAME, DEFAULT_NAME)
                return self.async_create_entry(title=title, data=self._data)

        gust_max = round(_convert_gust_to_display(VALID_WIND_GUST_MAX_MS, imperial), 1)

        return self.async_show_form(
            step_id="alerts",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_THRESH_WIND_GUST_MS,
                        default=round(_convert_gust_to_display(DEFAULT_THRESH_WIND_GUST_MS, imperial), 1),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0, max=gust_max, step=0.1, mode="box", unit_of_measurement=gust_u
                        )
                    ),
                    vol.Optional(
                        CONF_THRESH_RAIN_RATE_MMPH,
                        default=round(_convert_rain_to_display(DEFAULT_THRESH_RAIN_RATE_MMPH, imperial), 2),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=0, max=200, step=0.5, mode="box", unit_of_measurement=rain_u)
                    ),
                    vol.Optional(
                        CONF_THRESH_FREEZE_C,
                        default=round(_convert_temp_to_display(DEFAULT_THRESH_FREEZE_C, imperial), 1),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=-30, max=10, step=0.5, mode="box", unit_of_measurement=temp_u)
                    ),
                    vol.Optional(CONF_STALENESS_S, default=DEFAULT_STALENESS_S): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=60, max=3600, step=60, mode="box", unit_of_measurement="s")
                    ),
                    vol.Optional(CONF_RAIN_FILTER_ALPHA, default=DEFAULT_RAIN_FILTER_ALPHA): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=0.05, max=1.0, step=0.05, mode="slider")
                    ),
                    vol.Optional(
                        CONF_PRESSURE_TREND_WINDOW_H, default=DEFAULT_PRESSURE_TREND_WINDOW_H
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=1, max=12, step=1, mode="box", unit_of_measurement="h")
                    ),
                    vol.Optional(CONF_ENABLE_ACTIVITY_SCORES, default=False): selector.BooleanSelector(),
                    vol.Optional(
                        CONF_RAIN_PENALTY_LIGHT_MMPH,
                        default=round(_convert_rain_to_display(DEFAULT_RAIN_PENALTY_LIGHT_MMPH, imperial), 2),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=0, max=5, step=0.1, mode="box", unit_of_measurement=rain_u)
                    ),
                    vol.Optional(
                        CONF_RAIN_PENALTY_HEAVY_MMPH,
                        default=round(_convert_rain_to_display(DEFAULT_RAIN_PENALTY_HEAVY_MMPH, imperial), 1),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=0.1, max=50, step=0.5, mode="box", unit_of_measurement=rain_u)
                    ),
                }
            ),
        )

    @staticmethod
    def _validate_alert_inputs(user_input: dict, imperial: bool) -> dict[str, str]:
        errors: dict[str, str] = {}
        gust_ms = _convert_gust_to_ms(float(user_input.get(CONF_THRESH_WIND_GUST_MS, 0)), imperial)
        if gust_ms > VALID_WIND_GUST_MAX_MS:
            errors[CONF_THRESH_WIND_GUST_MS] = "wind_gust_too_high"
        freeze_c = _convert_temp_to_c(float(user_input.get(CONF_THRESH_FREEZE_C, 0)), imperial)
        if not (VALID_TEMP_MIN_C <= freeze_c <= VALID_TEMP_MAX_C):
            errors[CONF_THRESH_FREEZE_C] = "temp_out_of_range"
        return errors


# ---------------------------------------------------------------------------
# Options Flow (Configure button post-install)
# ---------------------------------------------------------------------------


class WSStationOptionsFlowHandler(config_entries.OptionsFlow):
    """Options flow handler. self.config_entry is provided by parent class."""

    def _get(self, key: str, default: Any) -> Any:
        return self.config_entry.options.get(key, self.config_entry.data.get(key, default))

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        units_mode = str(self._get(CONF_UNITS_MODE, DEFAULT_UNITS_MODE))
        imperial = _is_imperial(units_mode, self.hass)
        gust_u = "mph" if imperial else "m/s"
        rain_u = "in/h" if imperial else "mm/h"
        temp_u = "°F" if imperial else "°C"

        if user_input is not None:
            out = dict(user_input)
            if CONF_PREFIX in out:
                out[CONF_PREFIX] = _sanitize_prefix(str(out[CONF_PREFIX]))

            # Elevation validation
            try:
                elev = float(out.get(CONF_ELEVATION_M, 0))
                if not (VALID_ELEVATION_MIN_M <= elev <= VALID_ELEVATION_MAX_M):
                    return self.async_show_form(
                        step_id="init",
                        data_schema=self._build_options_schema(imperial, gust_u, rain_u, temp_u),
                        errors={CONF_ELEVATION_M: "elevation_out_of_range"},
                    )
            except (TypeError, ValueError):
                pass

            # Convert thresholds to canonical metric
            out[CONF_THRESH_WIND_GUST_MS] = _convert_gust_to_ms(
                float(out.get(CONF_THRESH_WIND_GUST_MS, DEFAULT_THRESH_WIND_GUST_MS)), imperial
            )
            out[CONF_THRESH_RAIN_RATE_MMPH] = _convert_rain_to_mmph(
                float(out.get(CONF_THRESH_RAIN_RATE_MMPH, DEFAULT_THRESH_RAIN_RATE_MMPH)), imperial
            )
            out[CONF_THRESH_FREEZE_C] = _convert_temp_to_c(
                float(out.get(CONF_THRESH_FREEZE_C, DEFAULT_THRESH_FREEZE_C)), imperial
            )
            out[CONF_RAIN_PENALTY_LIGHT_MMPH] = _convert_rain_to_mmph(
                float(out.get(CONF_RAIN_PENALTY_LIGHT_MMPH, DEFAULT_RAIN_PENALTY_LIGHT_MMPH)), imperial
            )
            out[CONF_RAIN_PENALTY_HEAVY_MMPH] = _convert_rain_to_mmph(
                float(out.get(CONF_RAIN_PENALTY_HEAVY_MMPH, DEFAULT_RAIN_PENALTY_HEAVY_MMPH)), imperial
            )
            return self.async_create_entry(title="", data=out)

        return self.async_show_form(
            step_id="init",
            data_schema=self._build_options_schema(imperial, gust_u, rain_u, temp_u),
        )

    def _build_options_schema(self, imperial: bool, gust_u: str, rain_u: str, temp_u: str) -> vol.Schema:
        g = self._get
        cur_gust_ms = float(g(CONF_THRESH_WIND_GUST_MS, DEFAULT_THRESH_WIND_GUST_MS))
        cur_rain_mmph = float(g(CONF_THRESH_RAIN_RATE_MMPH, DEFAULT_THRESH_RAIN_RATE_MMPH))
        cur_freeze_c = float(g(CONF_THRESH_FREEZE_C, DEFAULT_THRESH_FREEZE_C))
        cur_light_mmph = float(g(CONF_RAIN_PENALTY_LIGHT_MMPH, DEFAULT_RAIN_PENALTY_LIGHT_MMPH))
        cur_heavy_mmph = float(g(CONF_RAIN_PENALTY_HEAVY_MMPH, DEFAULT_RAIN_PENALTY_HEAVY_MMPH))

        default_lat = getattr(self.hass.config, "latitude", 0.0) or 0.0
        default_lon = getattr(self.hass.config, "longitude", 0.0) or 0.0

        return vol.Schema(
            {
                vol.Optional(CONF_PREFIX, default=g(CONF_PREFIX, DEFAULT_PREFIX)): str,
                # Location & Zambretti
                vol.Optional(CONF_HEMISPHERE, default=g(CONF_HEMISPHERE, DEFAULT_HEMISPHERE)): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=HEMISPHERE_OPTIONS, mode="list")
                ),
                vol.Optional(
                    CONF_CLIMATE_REGION, default=g(CONF_CLIMATE_REGION, DEFAULT_CLIMATE_REGION)
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=CLIMATE_REGION_OPTIONS, mode="dropdown")
                ),
                vol.Optional(
                    CONF_ELEVATION_M, default=g(CONF_ELEVATION_M, DEFAULT_ELEVATION_M)
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=VALID_ELEVATION_MIN_M,
                        max=VALID_ELEVATION_MAX_M,
                        step=1,
                        mode="box",
                        unit_of_measurement="m",
                    )
                ),
                # Units
                vol.Optional(CONF_UNITS_MODE, default=g(CONF_UNITS_MODE, DEFAULT_UNITS_MODE)): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=UNITS_MODE_OPTIONS, mode="dropdown")
                ),
                vol.Optional(CONF_TEMP_UNIT, default=g(CONF_TEMP_UNIT, DEFAULT_TEMP_UNIT)): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=TEMP_UNIT_OPTIONS, mode="list")
                ),
                # Forecast
                vol.Optional(
                    CONF_FORECAST_ENABLED, default=g(CONF_FORECAST_ENABLED, DEFAULT_FORECAST_ENABLED)
                ): selector.BooleanSelector(),
                vol.Optional(
                    CONF_FORECAST_INTERVAL_MIN, default=g(CONF_FORECAST_INTERVAL_MIN, DEFAULT_FORECAST_INTERVAL_MIN)
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=10, max=180, step=5, mode="box", unit_of_measurement="min")
                ),
                vol.Optional(
                    CONF_FORECAST_LAT, default=g(CONF_FORECAST_LAT, round(default_lat, 4))
                ): selector.NumberSelector(selector.NumberSelectorConfig(min=-90, max=90, step=0.001, mode="box")),
                vol.Optional(
                    CONF_FORECAST_LON, default=g(CONF_FORECAST_LON, round(default_lon, 4))
                ): selector.NumberSelector(selector.NumberSelectorConfig(min=-180, max=180, step=0.001, mode="box")),
                # Alerts
                vol.Optional(
                    CONF_THRESH_WIND_GUST_MS, default=round(_convert_gust_to_display(cur_gust_ms, imperial), 1)
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=0, max=120, step=0.1, mode="box", unit_of_measurement=gust_u)
                ),
                vol.Optional(
                    CONF_THRESH_RAIN_RATE_MMPH, default=round(_convert_rain_to_display(cur_rain_mmph, imperial), 2)
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=0, max=200, step=0.5, mode="box", unit_of_measurement=rain_u)
                ),
                vol.Optional(
                    CONF_THRESH_FREEZE_C, default=round(_convert_temp_to_display(cur_freeze_c, imperial), 1)
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=-30, max=10, step=0.5, mode="box", unit_of_measurement=temp_u)
                ),
                # Advanced
                vol.Optional(
                    CONF_STALENESS_S, default=g(CONF_STALENESS_S, DEFAULT_STALENESS_S)
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=60, max=3600, step=60, mode="box", unit_of_measurement="s")
                ),
                vol.Optional(
                    CONF_RAIN_FILTER_ALPHA, default=g(CONF_RAIN_FILTER_ALPHA, DEFAULT_RAIN_FILTER_ALPHA)
                ): selector.NumberSelector(selector.NumberSelectorConfig(min=0.05, max=1.0, step=0.05, mode="slider")),
                vol.Optional(
                    CONF_PRESSURE_TREND_WINDOW_H,
                    default=g(CONF_PRESSURE_TREND_WINDOW_H, DEFAULT_PRESSURE_TREND_WINDOW_H),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=1, max=12, step=1, mode="box", unit_of_measurement="h")
                ),
                vol.Optional(
                    CONF_ENABLE_ACTIVITY_SCORES, default=g(CONF_ENABLE_ACTIVITY_SCORES, DEFAULT_ENABLE_ACTIVITY_SCORES)
                ): selector.BooleanSelector(),
                vol.Optional(
                    CONF_RAIN_PENALTY_LIGHT_MMPH, default=round(_convert_rain_to_display(cur_light_mmph, imperial), 2)
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=0, max=5, step=0.1, mode="box", unit_of_measurement=rain_u)
                ),
                vol.Optional(
                    CONF_RAIN_PENALTY_HEAVY_MMPH, default=round(_convert_rain_to_display(cur_heavy_mmph, imperial), 1)
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=0.1, max=50, step=0.5, mode="box", unit_of_measurement=rain_u)
                ),
            }
        )
