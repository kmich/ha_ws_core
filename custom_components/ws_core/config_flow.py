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
    CONF_AQI_INTERVAL_MIN,
    CONF_CAL_HUMIDITY,
    CONF_CAL_PRESSURE_HPA,
    CONF_CAL_TEMP_C,
    CONF_CAL_WIND_MS,
    CONF_CLIMATE_REGION,
    CONF_CWOP_CALLSIGN,
    CONF_CWOP_INTERVAL_MIN,
    CONF_CWOP_PASSCODE,
    CONF_DEGREE_DAY_BASE_C,
    CONF_ELEVATION_M,
    CONF_ENABLE_ACTIVITY_SCORES,
    # v0.7.0
    CONF_ENABLE_AIR_QUALITY,
    CONF_ENABLE_CWOP,
    CONF_ENABLE_DEGREE_DAYS,
    CONF_ENABLE_DISPLAY_SENSORS,
    CONF_ENABLE_EXPORT,
    CONF_ENABLE_EXTENDED_SENSORS,
    CONF_ENABLE_FIRE_RISK,
    CONF_ENABLE_LAUNDRY,
    CONF_ENABLE_METAR,
    # v0.8.0
    CONF_ENABLE_MOON,
    CONF_ENABLE_POLLEN,
    CONF_ENABLE_RUNNING,
    CONF_ENABLE_SEA_TEMP,
    # v0.9.0
    CONF_ENABLE_SOLAR_FORECAST,
    CONF_ENABLE_STARGAZING,
    CONF_ENABLE_WUNDERGROUND,
    CONF_ENABLE_ZAMBRETTI,
    CONF_EXPORT_FORMAT,
    CONF_EXPORT_INTERVAL_MIN,
    CONF_EXPORT_PATH,
    CONF_FORECAST_ENABLED,
    CONF_FORECAST_INTERVAL_MIN,
    CONF_FORECAST_LAT,
    CONF_FORECAST_LON,
    CONF_HEMISPHERE,
    CONF_METAR_ICAO,
    CONF_METAR_INTERVAL_MIN,
    CONF_NAME,
    CONF_POLLEN_INTERVAL_MIN,
    CONF_PREFIX,
    CONF_PRESSURE_TREND_WINDOW_H,
    CONF_RAIN_FILTER_ALPHA,
    CONF_RAIN_PENALTY_HEAVY_MMPH,
    CONF_RAIN_PENALTY_LIGHT_MMPH,
    CONF_SEA_TEMP_LAT,
    CONF_SEA_TEMP_LON,
    CONF_SOLAR_INTERVAL_MIN,
    CONF_SOLAR_PANEL_AZIMUTH,
    CONF_SOLAR_PANEL_TILT,
    CONF_SOLAR_PEAK_KW,
    CONF_SOURCES,
    CONF_STALENESS_S,
    CONF_TEMP_UNIT,
    CONF_THRESH_FREEZE_C,
    CONF_THRESH_RAIN_RATE_MMPH,
    CONF_THRESH_WIND_GUST_MS,
    CONF_TOMORROW_IO_KEY,
    CONF_UNITS_MODE,
    CONF_WU_API_KEY,
    CONF_WU_INTERVAL_MIN,
    CONF_WU_STATION_ID,
    CONFIG_VERSION,
    DEFAULT_AQI_INTERVAL_MIN,
    DEFAULT_CAL_HUMIDITY,
    DEFAULT_CAL_PRESSURE_HPA,
    DEFAULT_CAL_TEMP_C,
    DEFAULT_CAL_WIND_MS,
    DEFAULT_CLIMATE_REGION,
    DEFAULT_CWOP_INTERVAL_MIN,
    DEFAULT_DEGREE_DAY_BASE_C,
    DEFAULT_ELEVATION_M,
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
    DEFAULT_EXPORT_FORMAT,
    DEFAULT_EXPORT_INTERVAL_MIN,
    DEFAULT_FORECAST_ENABLED,
    DEFAULT_FORECAST_INTERVAL_MIN,
    DEFAULT_HEMISPHERE,
    DEFAULT_METAR_INTERVAL_MIN,
    DEFAULT_NAME,
    DEFAULT_POLLEN_INTERVAL_MIN,
    DEFAULT_PREFIX,
    DEFAULT_PRESSURE_TREND_WINDOW_H,
    DEFAULT_RAIN_FILTER_ALPHA,
    DEFAULT_RAIN_PENALTY_HEAVY_MMPH,
    DEFAULT_RAIN_PENALTY_LIGHT_MMPH,
    DEFAULT_SOLAR_INTERVAL_MIN,
    DEFAULT_SOLAR_PANEL_AZIMUTH,
    DEFAULT_SOLAR_PANEL_TILT,
    DEFAULT_SOLAR_PEAK_KW,
    DEFAULT_STALENESS_S,
    DEFAULT_TEMP_UNIT,
    DEFAULT_THRESH_FREEZE_C,
    DEFAULT_THRESH_RAIN_RATE_MMPH,
    DEFAULT_THRESH_WIND_GUST_MS,
    DEFAULT_UNITS_MODE,
    DEFAULT_WU_INTERVAL_MIN,
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
    SRC_SOLAR_RADIATION,
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


async def _autodetect_metar_icao(lat: float, lon: float) -> str:
    """Find the nearest ICAO airport code via aviationweather.gov stations API."""
    try:
        import aiohttp

        url = (
            "https://aviationweather.gov/api/data/stationinfo"
            f"?bbox={lat - 2:.2f},{lon - 3:.2f},{lat + 2:.2f},{lon + 3:.2f}&format=json"
        )
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                if resp.status != 200:
                    return ""
                stations = await resp.json()
        if not isinstance(stations, list) or not stations:
            return ""

        # Find nearest by simple lat/lon distance
        def _dist(s: dict) -> float:
            return (float(s.get("lat", 0)) - lat) ** 2 + (float(s.get("lon", 0)) - lon) ** 2

        nearest = min(stations, key=_dist)
        return str(nearest.get("icaoId", nearest.get("stationIdentifier", ""))).upper()
    except Exception:
        return ""


async def _validate_tomorrow_io_key(api_key: str, lat: float, lon: float) -> tuple[bool, str]:
    """Validate a Tomorrow.io API key with a lightweight call. Returns (valid, error_key)."""
    try:
        import aiohttp

        url = f"https://data.tomorrow.io/v4/weather/realtime?location={lat},{lon}&fields=grassIndex&apikey={api_key}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    return True, ""
                if resp.status == 401 or resp.status == 403:
                    return False, "invalid_api_key"
                if resp.status == 429:
                    # Rate limited but key is valid
                    return True, ""
                return False, "cannot_connect"
    except Exception:
        return False, "cannot_connect"


async def _validate_wu_credentials(station_id: str, api_key: str) -> tuple[bool, str]:
    """Validate Weather Underground station ID + API key. Returns (valid, error_key)."""
    try:
        import aiohttp

        url = (
            f"https://api.weather.com/v2/pws/observations/current"
            f"?stationId={station_id}&format=json&units=m&apiKey={api_key}&numericPrecision=decimal"
        )
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    return True, ""
                if resp.status == 401 or resp.status == 403:
                    return False, "invalid_api_key"
                if resp.status == 404:
                    return False, "station_not_found"
                return False, "cannot_connect"
    except Exception:
        return False, "cannot_connect"


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


async def _auto_detect_metar_icao(hass) -> str:
    """Nearest METAR station to HA lat/lon via aviationweather.gov. Returns ICAO or empty string."""
    try:
        lat = float(hass.config.latitude)
        lon = float(hass.config.longitude)
    except (TypeError, ValueError):
        return ""
    url = (
        "https://aviationweather.gov/api/data/metar"
        f"?bbox={lon - 1.0:.2f},{lat - 1.0:.2f},{lon + 1.0:.2f},{lat + 1.0:.2f}"
        "&format=json&taf=false"
    )
    try:
        import aiohttp

        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                if resp.status != 200:
                    return ""
                data = await resp.json()
        if not data:
            return ""
        best_icao, best_dist = "", 999.0
        for st in data:
            slat, slon, icao = st.get("lat"), st.get("lon"), st.get("icaoId", "")
            if slat is None or not icao:
                continue
            dist = ((float(slat) - lat) ** 2 + (float(slon) - lon) ** 2) ** 0.5
            if dist < best_dist:
                best_dist, best_icao = dist, icao
        return best_icao
    except Exception:
        return ""


async def _validate_cwop(callsign: str) -> bool:
    """TCP ping to cwop.aprs.net:14580 to confirm reachability."""
    import asyncio

    try:
        _, writer = await asyncio.wait_for(asyncio.open_connection("cwop.aprs.net", 14580), timeout=5)
        writer.close()
        await asyncio.wait_for(writer.wait_closed(), timeout=3)
        return True
    except Exception:
        return False


async def _validate_wu(station_id: str, api_key: str) -> bool:
    """Test WU PWS credentials with a lightweight observations call."""
    if not (station_id and api_key):
        return False
    url = f"https://api.weather.com/v2/pws/observations/current?stationId={station_id}&format=json&units=m&apiKey={api_key}"
    try:
        import aiohttp

        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                return resp.status == 200
    except Exception:
        return False


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
        # v0.9.0: solar radiation (W/m²) for Penman-Monteith ET₀
        fields[vol.Optional(SRC_SOLAR_RADIATION)] = selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor")
        )
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
            return await self.async_step_features()

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
    # Step 7: Features (toggle advanced sensor groups)
    # ------------------------------------------------------------------
    async def async_step_features(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            self._data[CONF_ENABLE_ZAMBRETTI] = bool(user_input.get(CONF_ENABLE_ZAMBRETTI, True))
            self._data[CONF_ENABLE_DISPLAY_SENSORS] = bool(user_input.get(CONF_ENABLE_DISPLAY_SENSORS, True))
            self._data[CONF_ENABLE_LAUNDRY] = bool(user_input.get(CONF_ENABLE_LAUNDRY, False))
            self._data[CONF_ENABLE_STARGAZING] = bool(user_input.get(CONF_ENABLE_STARGAZING, False))
            self._data[CONF_ENABLE_FIRE_RISK] = bool(user_input.get(CONF_ENABLE_FIRE_RISK, False))
            self._data[CONF_ENABLE_RUNNING] = bool(user_input.get(CONF_ENABLE_RUNNING, False))
            self._data[CONF_ENABLE_SEA_TEMP] = bool(user_input.get(CONF_ENABLE_SEA_TEMP, False))
            self._data[CONF_ENABLE_DEGREE_DAYS] = bool(user_input.get(CONF_ENABLE_DEGREE_DAYS, False))
            self._data[CONF_ENABLE_METAR] = bool(user_input.get(CONF_ENABLE_METAR, False))
            self._data[CONF_ENABLE_CWOP] = bool(user_input.get(CONF_ENABLE_CWOP, False))
            self._data[CONF_ENABLE_WUNDERGROUND] = bool(user_input.get(CONF_ENABLE_WUNDERGROUND, False))
            self._data[CONF_ENABLE_EXPORT] = bool(user_input.get(CONF_ENABLE_EXPORT, False))
            # v0.7.0 – v0.9.0
            self._data[CONF_ENABLE_AIR_QUALITY] = bool(user_input.get(CONF_ENABLE_AIR_QUALITY, False))
            self._data[CONF_ENABLE_POLLEN] = bool(user_input.get(CONF_ENABLE_POLLEN, False))
            self._data[CONF_ENABLE_MOON] = bool(user_input.get(CONF_ENABLE_MOON, False))
            self._data[CONF_ENABLE_SOLAR_FORECAST] = bool(user_input.get(CONF_ENABLE_SOLAR_FORECAST, False))
            if self._data[CONF_ENABLE_SEA_TEMP]:
                return await self.async_step_sea_temp()
            if self._data[CONF_ENABLE_DEGREE_DAYS]:
                return await self.async_step_degree_days()
            if self._data[CONF_ENABLE_METAR]:
                return await self.async_step_metar()
            if self._data[CONF_ENABLE_CWOP]:
                return await self.async_step_cwop()
            if self._data[CONF_ENABLE_WUNDERGROUND]:
                return await self.async_step_wunderground()
            if self._data[CONF_ENABLE_EXPORT]:
                return await self.async_step_export()
            if self._data[CONF_ENABLE_AIR_QUALITY]:
                return await self.async_step_air_quality()
            if self._data[CONF_ENABLE_POLLEN]:
                return await self.async_step_pollen()
            if self._data[CONF_ENABLE_SOLAR_FORECAST]:
                return await self.async_step_solar_forecast()
            return await self.async_step_alerts()

        return self.async_show_form(
            step_id="features",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_ENABLE_ZAMBRETTI, default=DEFAULT_ENABLE_ZAMBRETTI): selector.BooleanSelector(),
                    vol.Optional(
                        CONF_ENABLE_DISPLAY_SENSORS, default=DEFAULT_ENABLE_DISPLAY_SENSORS
                    ): selector.BooleanSelector(),
                    vol.Optional(CONF_ENABLE_LAUNDRY, default=DEFAULT_ENABLE_LAUNDRY): selector.BooleanSelector(),
                    vol.Optional(CONF_ENABLE_STARGAZING, default=DEFAULT_ENABLE_STARGAZING): selector.BooleanSelector(),
                    vol.Optional(CONF_ENABLE_FIRE_RISK, default=DEFAULT_ENABLE_FIRE_RISK): selector.BooleanSelector(),
                    vol.Optional(CONF_ENABLE_RUNNING, default=DEFAULT_ENABLE_RUNNING): selector.BooleanSelector(),
                    vol.Optional(CONF_ENABLE_SEA_TEMP, default=DEFAULT_ENABLE_SEA_TEMP): selector.BooleanSelector(),
                    vol.Optional(
                        CONF_ENABLE_DEGREE_DAYS, default=DEFAULT_ENABLE_DEGREE_DAYS
                    ): selector.BooleanSelector(),
                    vol.Optional(CONF_ENABLE_METAR, default=DEFAULT_ENABLE_METAR): selector.BooleanSelector(),
                    vol.Optional(CONF_ENABLE_CWOP, default=DEFAULT_ENABLE_CWOP): selector.BooleanSelector(),
                    vol.Optional(
                        CONF_ENABLE_WUNDERGROUND, default=DEFAULT_ENABLE_WUNDERGROUND
                    ): selector.BooleanSelector(),
                    vol.Optional(CONF_ENABLE_EXPORT, default=DEFAULT_ENABLE_EXPORT): selector.BooleanSelector(),
                    # v0.7.0
                    vol.Optional(
                        CONF_ENABLE_AIR_QUALITY, default=DEFAULT_ENABLE_AIR_QUALITY
                    ): selector.BooleanSelector(),
                    vol.Optional(CONF_ENABLE_POLLEN, default=DEFAULT_ENABLE_POLLEN): selector.BooleanSelector(),
                    # v0.8.0
                    vol.Optional(CONF_ENABLE_MOON, default=DEFAULT_ENABLE_MOON): selector.BooleanSelector(),
                    # v0.9.0
                    vol.Optional(
                        CONF_ENABLE_SOLAR_FORECAST, default=DEFAULT_ENABLE_SOLAR_FORECAST
                    ): selector.BooleanSelector(),
                }
            ),
        )

    # ------------------------------------------------------------------
    # Step 7b: Sea temperature location (only shown if sea temp enabled)
    # ------------------------------------------------------------------
    async def async_step_sea_temp(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            self._data[CONF_SEA_TEMP_LAT] = user_input.get(CONF_SEA_TEMP_LAT)
            self._data[CONF_SEA_TEMP_LON] = user_input.get(CONF_SEA_TEMP_LON)
            if self._data.get(CONF_ENABLE_DEGREE_DAYS):
                return await self.async_step_degree_days()
            if self._data.get(CONF_ENABLE_METAR):
                return await self.async_step_metar()
            if self._data.get(CONF_ENABLE_CWOP):
                return await self.async_step_cwop()
            if self._data.get(CONF_ENABLE_WUNDERGROUND):
                return await self.async_step_wunderground()
            if self._data.get(CONF_ENABLE_EXPORT):
                return await self.async_step_export()
            if self._data.get(CONF_ENABLE_AIR_QUALITY):
                return await self.async_step_air_quality()
            if self._data.get(CONF_ENABLE_POLLEN):
                return await self.async_step_pollen()
            if self._data.get(CONF_ENABLE_SOLAR_FORECAST):
                return await self.async_step_solar_forecast()
            return await self.async_step_alerts()

        default_lat = getattr(self.hass.config, "latitude", 0.0) or 0.0
        default_lon = getattr(self.hass.config, "longitude", 0.0) or 0.0

        return self.async_show_form(
            step_id="sea_temp",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_SEA_TEMP_LAT, default=round(default_lat, 4)): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=-90, max=90, step=0.001, mode="box")
                    ),
                    vol.Optional(CONF_SEA_TEMP_LON, default=round(default_lon, 4)): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=-180, max=180, step=0.001, mode="box")
                    ),
                }
            ),
        )

    # ------------------------------------------------------------------
    # Step 7c: Degree days configuration  (v0.5.0)
    # ------------------------------------------------------------------
    async def async_step_degree_days(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            self._data[CONF_DEGREE_DAY_BASE_C] = float(
                user_input.get(CONF_DEGREE_DAY_BASE_C, DEFAULT_DEGREE_DAY_BASE_C)
            )
            if self._data.get(CONF_ENABLE_METAR):
                return await self.async_step_metar()
            if self._data.get(CONF_ENABLE_CWOP):
                return await self.async_step_cwop()
            if self._data.get(CONF_ENABLE_WUNDERGROUND):
                return await self.async_step_wunderground()
            if self._data.get(CONF_ENABLE_EXPORT):
                return await self.async_step_export()
            if self._data.get(CONF_ENABLE_AIR_QUALITY):
                return await self.async_step_air_quality()
            if self._data.get(CONF_ENABLE_POLLEN):
                return await self.async_step_pollen()
            if self._data.get(CONF_ENABLE_SOLAR_FORECAST):
                return await self.async_step_solar_forecast()
            return await self.async_step_alerts()

        return self.async_show_form(
            step_id="degree_days",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_DEGREE_DAY_BASE_C, default=DEFAULT_DEGREE_DAY_BASE_C): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=-10, max=30, step=0.5, mode="box", unit_of_measurement="°C")
                    ),
                }
            ),
            description_placeholders={
                "info": "Base temperature for heating/cooling degree day calculations. Standard: 18°C (64°F)."
            },
        )

    # ------------------------------------------------------------------
    # Step 7d: METAR station configuration  (v0.5.0)
    # ------------------------------------------------------------------
    async def async_step_metar(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            icao = str(user_input.get(CONF_METAR_ICAO, "")).upper().strip()
            if not icao:
                # Auto-detect nearest ICAO from forecast lat/lon
                lat = self._data.get(CONF_FORECAST_LAT)
                lon = self._data.get(CONF_FORECAST_LON)
                if lat is not None and lon is not None:
                    icao = await _autodetect_metar_icao(lat, lon) or ""
            if icao:
                self._data[CONF_METAR_ICAO] = icao
                self._data[CONF_METAR_INTERVAL_MIN] = int(
                    user_input.get(CONF_METAR_INTERVAL_MIN, DEFAULT_METAR_INTERVAL_MIN)
                )
            else:
                # Neither entered nor auto-detected — disable
                self._data[CONF_ENABLE_METAR] = False
                self._data[CONF_METAR_ICAO] = ""
            if self._data.get(CONF_ENABLE_CWOP):
                return await self.async_step_cwop()
            if self._data.get(CONF_ENABLE_WUNDERGROUND):
                return await self.async_step_wunderground()
            if self._data.get(CONF_ENABLE_EXPORT):
                return await self.async_step_export()
            if self._data.get(CONF_ENABLE_AIR_QUALITY):
                return await self.async_step_air_quality()
            if self._data.get(CONF_ENABLE_POLLEN):
                return await self.async_step_pollen()
            if self._data.get(CONF_ENABLE_SOLAR_FORECAST):
                return await self.async_step_solar_forecast()
            return await self.async_step_alerts()

        existing_icao = self._data.get(CONF_METAR_ICAO, "")
        lat = self._data.get(CONF_FORECAST_LAT)
        lat_hint = " (will auto-detect from lat/lon if blank)" if lat is not None else ""
        return self.async_show_form(
            step_id="metar",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_METAR_ICAO, default=existing_icao): selector.TextSelector(
                        selector.TextSelectorConfig(type="text")
                    ),
                    vol.Optional(CONF_METAR_INTERVAL_MIN, default=DEFAULT_METAR_INTERVAL_MIN): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=30, max=180, step=30, mode="box", unit_of_measurement="min")
                    ),
                }
            ),
            description_placeholders={
                "info": f"4-letter ICAO code e.g. LGAV for Athens.{lat_hint} Leave blank to auto-detect or disable."
            },
        )

    # ------------------------------------------------------------------
    # Step 7e: CWOP upload configuration  (v0.6.0)
    # ------------------------------------------------------------------
    async def async_step_cwop(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            callsign = str(user_input.get(CONF_CWOP_CALLSIGN, "")).upper().strip()
            if not callsign:
                # No callsign entered — silently disable CWOP and skip
                self._data[CONF_ENABLE_CWOP] = False
                self._data[CONF_CWOP_CALLSIGN] = ""
            else:
                self._data[CONF_CWOP_CALLSIGN] = callsign
                self._data[CONF_CWOP_PASSCODE] = str(user_input.get(CONF_CWOP_PASSCODE, "-1")).strip()
                self._data[CONF_CWOP_INTERVAL_MIN] = int(
                    user_input.get(CONF_CWOP_INTERVAL_MIN, DEFAULT_CWOP_INTERVAL_MIN)
                )
            if self._data.get(CONF_ENABLE_WUNDERGROUND):
                return await self.async_step_wunderground()
            if self._data.get(CONF_ENABLE_EXPORT):
                return await self.async_step_export()
            if self._data.get(CONF_ENABLE_AIR_QUALITY):
                return await self.async_step_air_quality()
            if self._data.get(CONF_ENABLE_POLLEN):
                return await self.async_step_pollen()
            if self._data.get(CONF_ENABLE_SOLAR_FORECAST):
                return await self.async_step_solar_forecast()
            return await self.async_step_alerts()

        existing_callsign = self._data.get(CONF_CWOP_CALLSIGN, "")
        return self.async_show_form(
            step_id="cwop",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_CWOP_CALLSIGN, default=existing_callsign): selector.TextSelector(
                        selector.TextSelectorConfig(type="text")
                    ),
                    vol.Optional(CONF_CWOP_PASSCODE, default="-1"): selector.TextSelector(
                        selector.TextSelectorConfig(type="text")
                    ),
                    vol.Optional(CONF_CWOP_INTERVAL_MIN, default=DEFAULT_CWOP_INTERVAL_MIN): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=5, max=60, step=5, mode="box", unit_of_measurement="min")
                    ),
                }
            ),
        )

    # ------------------------------------------------------------------
    # Step 7f: Weather Underground configuration  (v0.6.0)
    # ------------------------------------------------------------------
    async def async_step_wunderground(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        if user_input is not None:
            station_id = str(user_input.get(CONF_WU_STATION_ID, "")).strip()
            api_key = str(user_input.get(CONF_WU_API_KEY, "")).strip()
            if not station_id or not api_key:
                # Missing credentials — silently disable WU and skip
                self._data[CONF_ENABLE_WUNDERGROUND] = False
                self._data[CONF_WU_STATION_ID] = ""
                self._data[CONF_WU_API_KEY] = ""
            else:
                # Validate credentials
                valid, err = await _validate_wu_credentials(station_id, api_key)
                if not valid:
                    errors[CONF_WU_API_KEY] = err or "invalid_api_key"
                else:
                    self._data[CONF_WU_STATION_ID] = station_id
                    self._data[CONF_WU_API_KEY] = api_key
                    self._data[CONF_WU_INTERVAL_MIN] = int(
                        user_input.get(CONF_WU_INTERVAL_MIN, DEFAULT_WU_INTERVAL_MIN)
                    )
            if not errors:
                if self._data.get(CONF_ENABLE_EXPORT):
                    return await self.async_step_export()
                if self._data.get(CONF_ENABLE_AIR_QUALITY):
                    return await self.async_step_air_quality()
                if self._data.get(CONF_ENABLE_POLLEN):
                    return await self.async_step_pollen()
                if self._data.get(CONF_ENABLE_SOLAR_FORECAST):
                    return await self.async_step_solar_forecast()
                return await self.async_step_alerts()

        existing_station = self._data.get(CONF_WU_STATION_ID, "")
        return self.async_show_form(
            step_id="wunderground",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_WU_STATION_ID, default=existing_station): selector.TextSelector(
                        selector.TextSelectorConfig(type="text")
                    ),
                    vol.Optional(CONF_WU_API_KEY, default=""): selector.TextSelector(
                        selector.TextSelectorConfig(type="password")
                    ),
                    vol.Optional(CONF_WU_INTERVAL_MIN, default=DEFAULT_WU_INTERVAL_MIN): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=1, max=30, step=1, mode="box", unit_of_measurement="min")
                    ),
                }
            ),
            errors=errors,
            description_placeholders={
                "info": "Weather Underground PWS. Leave blank to skip. Credentials will be validated."
            },
        )

    # ------------------------------------------------------------------
    # Step 7g: CSV/JSON export configuration  (v0.6.0)
    # ------------------------------------------------------------------
    def _next_after_export(self):
        """Return the next step after export in the config flow."""
        if self._data.get(CONF_ENABLE_AIR_QUALITY):
            return self.async_step_air_quality()
        if self._data.get(CONF_ENABLE_POLLEN):
            return self.async_step_pollen()
        if self._data.get(CONF_ENABLE_SOLAR_FORECAST):
            return self.async_step_solar_forecast()
        return self.async_step_alerts()

    async def async_step_export(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            self._data[CONF_EXPORT_PATH] = str(user_input.get(CONF_EXPORT_PATH, "/config/ws_core_export")).strip()
            self._data[CONF_EXPORT_FORMAT] = str(user_input.get(CONF_EXPORT_FORMAT, DEFAULT_EXPORT_FORMAT))
            self._data[CONF_EXPORT_INTERVAL_MIN] = int(
                user_input.get(CONF_EXPORT_INTERVAL_MIN, DEFAULT_EXPORT_INTERVAL_MIN)
            )
            return await self._next_after_export()

        return self.async_show_form(
            step_id="export",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_EXPORT_PATH, default="/config/ws_core_export"): selector.TextSelector(
                        selector.TextSelectorConfig(type="text")
                    ),
                    vol.Optional(CONF_EXPORT_FORMAT, default=DEFAULT_EXPORT_FORMAT): selector.SelectSelector(
                        selector.SelectSelectorConfig(options=["csv", "json", "both"])
                    ),
                    vol.Optional(
                        CONF_EXPORT_INTERVAL_MIN, default=DEFAULT_EXPORT_INTERVAL_MIN
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=5, max=1440, step=5, mode="box", unit_of_measurement="min")
                    ),
                }
            ),
            description_placeholders={
                "info": "Directory path (on HA host) and interval for periodic observation exports."
            },
        )

    # ------------------------------------------------------------------
    # v0.7.0 — Air Quality (Open-Meteo, free, no API key)
    # ------------------------------------------------------------------
    async def async_step_air_quality(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            self._data[CONF_AQI_INTERVAL_MIN] = int(user_input.get(CONF_AQI_INTERVAL_MIN, DEFAULT_AQI_INTERVAL_MIN))
            if self._data.get(CONF_ENABLE_POLLEN):
                return await self.async_step_pollen()
            if self._data.get(CONF_ENABLE_SOLAR_FORECAST):
                return await self.async_step_solar_forecast()
            return await self.async_step_alerts()

        return self.async_show_form(
            step_id="air_quality",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_AQI_INTERVAL_MIN, default=DEFAULT_AQI_INTERVAL_MIN): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=15, max=360, step=15, mode="box", unit_of_measurement="min")
                    ),
                }
            ),
            description_placeholders={
                "info": "Air quality data (PM2.5, PM10, NO₂, ozone) from Open-Meteo. Free, no API key required. Uses forecast lat/lon."
            },
        )

    # ------------------------------------------------------------------
    # v0.7.0 — Pollen (Tomorrow.io, free API key required)
    # ------------------------------------------------------------------
    async def async_step_pollen(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        if user_input is not None:
            api_key = str(user_input.get(CONF_TOMORROW_IO_KEY, "")).strip()
            if not api_key:
                # No key — silently disable pollen and skip
                self._data[CONF_ENABLE_POLLEN] = False
                self._data[CONF_TOMORROW_IO_KEY] = ""
            else:
                # Validate key with a quick test call
                valid, err = await _validate_tomorrow_io_key(
                    api_key, self._data.get(CONF_FORECAST_LAT, 0), self._data.get(CONF_FORECAST_LON, 0)
                )
                if not valid:
                    errors[CONF_TOMORROW_IO_KEY] = err or "invalid_api_key"
                else:
                    self._data[CONF_TOMORROW_IO_KEY] = api_key
                    self._data[CONF_POLLEN_INTERVAL_MIN] = int(
                        user_input.get(CONF_POLLEN_INTERVAL_MIN, DEFAULT_POLLEN_INTERVAL_MIN)
                    )
            if not errors:
                if self._data.get(CONF_ENABLE_SOLAR_FORECAST):
                    return await self.async_step_solar_forecast()
                return await self.async_step_alerts()

        return self.async_show_form(
            step_id="pollen",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_TOMORROW_IO_KEY, default=""): selector.TextSelector(
                        selector.TextSelectorConfig(type="password")
                    ),
                    vol.Optional(
                        CONF_POLLEN_INTERVAL_MIN, default=DEFAULT_POLLEN_INTERVAL_MIN
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=60, max=1440, step=60, mode="box", unit_of_measurement="min")
                    ),
                }
            ),
            errors=errors,
            description_placeholders={
                "info": "Tomorrow.io free tier: up to 500 API calls/day. Leave blank to skip pollen sensors."
            },
        )

    # ------------------------------------------------------------------
    # v0.9.0 — Solar forecast (forecast.solar, free, no key)
    # ------------------------------------------------------------------
    async def async_step_solar_forecast(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            self._data[CONF_SOLAR_PEAK_KW] = float(user_input.get(CONF_SOLAR_PEAK_KW, DEFAULT_SOLAR_PEAK_KW))
            self._data[CONF_SOLAR_PANEL_AZIMUTH] = int(
                user_input.get(CONF_SOLAR_PANEL_AZIMUTH, DEFAULT_SOLAR_PANEL_AZIMUTH)
            )
            self._data[CONF_SOLAR_PANEL_TILT] = int(user_input.get(CONF_SOLAR_PANEL_TILT, DEFAULT_SOLAR_PANEL_TILT))
            self._data[CONF_SOLAR_INTERVAL_MIN] = int(
                user_input.get(CONF_SOLAR_INTERVAL_MIN, DEFAULT_SOLAR_INTERVAL_MIN)
            )
            return await self.async_step_alerts()

        return self.async_show_form(
            step_id="solar_forecast",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_SOLAR_PEAK_KW, default=DEFAULT_SOLAR_PEAK_KW): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0.1, max=100.0, step=0.1, mode="box", unit_of_measurement="kWp"
                        )
                    ),
                    vol.Optional(
                        CONF_SOLAR_PANEL_AZIMUTH, default=DEFAULT_SOLAR_PANEL_AZIMUTH
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=0, max=359, step=1, mode="box", unit_of_measurement="°")
                    ),
                    vol.Optional(CONF_SOLAR_PANEL_TILT, default=DEFAULT_SOLAR_PANEL_TILT): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=0, max=90, step=1, mode="box", unit_of_measurement="°")
                    ),
                    vol.Optional(CONF_SOLAR_INTERVAL_MIN, default=DEFAULT_SOLAR_INTERVAL_MIN): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=30, max=360, step=30, mode="box", unit_of_measurement="min")
                    ),
                }
            ),
            description_placeholders={
                "info": "Free solar PV generation forecast from forecast.solar. Uses forecast lat/lon. Azimuth: 0=N, 90=E, 180=S, 270=W."
            },
        )

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
    """Multi-step options flow — mirrors the config flow so every setting is accessible post-install."""

    def _get(self, key: str, default: Any) -> Any:
        return self.config_entry.options.get(key, self.config_entry.data.get(key, default))

    # ------------------------------------------------------------------
    # Step 1: Core — identity, location, units, forecast, calibration, alerts
    # ------------------------------------------------------------------
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
            try:
                elev = float(out.get(CONF_ELEVATION_M, 0))
                if not (VALID_ELEVATION_MIN_M <= elev <= VALID_ELEVATION_MAX_M):
                    return self.async_show_form(
                        step_id="init",
                        data_schema=self._build_core_schema(imperial, gust_u, rain_u, temp_u),
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
            # Merge into options — features step comes next
            self._opt: dict[str, Any] = out
            return await self.async_step_features_opt()

        return self.async_show_form(
            step_id="init",
            data_schema=self._build_core_schema(imperial, gust_u, rain_u, temp_u),
        )

    def _build_core_schema(self, imperial: bool, gust_u: str, rain_u: str, temp_u: str) -> vol.Schema:
        g = self._get
        default_lat = getattr(self.hass.config, "latitude", 0.0) or 0.0
        default_lon = getattr(self.hass.config, "longitude", 0.0) or 0.0
        cur_gust_ms = float(g(CONF_THRESH_WIND_GUST_MS, DEFAULT_THRESH_WIND_GUST_MS))
        cur_rain_mmph = float(g(CONF_THRESH_RAIN_RATE_MMPH, DEFAULT_THRESH_RAIN_RATE_MMPH))
        cur_freeze_c = float(g(CONF_THRESH_FREEZE_C, DEFAULT_THRESH_FREEZE_C))
        cur_light_mmph = float(g(CONF_RAIN_PENALTY_LIGHT_MMPH, DEFAULT_RAIN_PENALTY_LIGHT_MMPH))
        cur_heavy_mmph = float(g(CONF_RAIN_PENALTY_HEAVY_MMPH, DEFAULT_RAIN_PENALTY_HEAVY_MMPH))
        return vol.Schema(
            {
                vol.Optional(CONF_PREFIX, default=g(CONF_PREFIX, DEFAULT_PREFIX)): str,
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
                vol.Optional(CONF_UNITS_MODE, default=g(CONF_UNITS_MODE, DEFAULT_UNITS_MODE)): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=UNITS_MODE_OPTIONS, mode="dropdown")
                ),
                vol.Optional(CONF_TEMP_UNIT, default=g(CONF_TEMP_UNIT, DEFAULT_TEMP_UNIT)): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=TEMP_UNIT_OPTIONS, mode="list")
                ),
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
                    CONF_RAIN_PENALTY_LIGHT_MMPH, default=round(_convert_rain_to_display(cur_light_mmph, imperial), 2)
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=0, max=5, step=0.1, mode="box", unit_of_measurement=rain_u)
                ),
                vol.Optional(
                    CONF_RAIN_PENALTY_HEAVY_MMPH, default=round(_convert_rain_to_display(cur_heavy_mmph, imperial), 1)
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=0.1, max=50, step=0.5, mode="box", unit_of_measurement=rain_u)
                ),
                vol.Optional(CONF_CAL_TEMP_C, default=g(CONF_CAL_TEMP_C, DEFAULT_CAL_TEMP_C)): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=-10, max=10, step=0.1, mode="box", unit_of_measurement="°C")
                ),
                vol.Optional(
                    CONF_CAL_HUMIDITY, default=g(CONF_CAL_HUMIDITY, DEFAULT_CAL_HUMIDITY)
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=-20, max=20, step=0.5, mode="box", unit_of_measurement="%")
                ),
                vol.Optional(
                    CONF_CAL_PRESSURE_HPA, default=g(CONF_CAL_PRESSURE_HPA, DEFAULT_CAL_PRESSURE_HPA)
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=-10, max=10, step=0.1, mode="box", unit_of_measurement="hPa")
                ),
                vol.Optional(
                    CONF_CAL_WIND_MS, default=g(CONF_CAL_WIND_MS, DEFAULT_CAL_WIND_MS)
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=-5, max=5, step=0.1, mode="box", unit_of_measurement="m/s")
                ),
            }
        )

    # ------------------------------------------------------------------
    # Step 2: Features — all feature toggles
    # ------------------------------------------------------------------
    async def async_step_features_opt(self, user_input: dict[str, Any] | None = None):
        g = self._get
        if user_input is not None:
            self._opt.update(user_input)
            # Route through sub-steps for enabled features
            if user_input.get(CONF_ENABLE_SEA_TEMP):
                return await self.async_step_sea_temp_opt()
            if user_input.get(CONF_ENABLE_DEGREE_DAYS):
                return await self.async_step_degree_days_opt()
            if user_input.get(CONF_ENABLE_METAR):
                return await self.async_step_metar_opt()
            if user_input.get(CONF_ENABLE_CWOP):
                return await self.async_step_cwop_opt()
            if user_input.get(CONF_ENABLE_WUNDERGROUND):
                return await self.async_step_wunderground_opt()
            if user_input.get(CONF_ENABLE_EXPORT):
                return await self.async_step_export_opt()
            if user_input.get(CONF_ENABLE_AIR_QUALITY):
                return await self.async_step_air_quality_opt()
            if user_input.get(CONF_ENABLE_POLLEN):
                return await self.async_step_pollen_opt()
            if user_input.get(CONF_ENABLE_SOLAR_FORECAST):
                return await self.async_step_solar_forecast_opt()
            return self.async_create_entry(title="", data=self._opt)

        return self.async_show_form(
            step_id="features_opt",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_ENABLE_ZAMBRETTI,
                        default=g(CONF_ENABLE_ZAMBRETTI, g(CONF_ENABLE_EXTENDED_SENSORS, DEFAULT_ENABLE_ZAMBRETTI)),
                    ): selector.BooleanSelector(),
                    vol.Optional(
                        CONF_ENABLE_DISPLAY_SENSORS,
                        default=g(
                            CONF_ENABLE_DISPLAY_SENSORS, g(CONF_ENABLE_EXTENDED_SENSORS, DEFAULT_ENABLE_DISPLAY_SENSORS)
                        ),
                    ): selector.BooleanSelector(),
                    vol.Optional(
                        CONF_ENABLE_LAUNDRY,
                        default=g(CONF_ENABLE_LAUNDRY, g(CONF_ENABLE_ACTIVITY_SCORES, DEFAULT_ENABLE_LAUNDRY)),
                    ): selector.BooleanSelector(),
                    vol.Optional(
                        CONF_ENABLE_STARGAZING,
                        default=g(CONF_ENABLE_STARGAZING, g(CONF_ENABLE_ACTIVITY_SCORES, DEFAULT_ENABLE_STARGAZING)),
                    ): selector.BooleanSelector(),
                    vol.Optional(
                        CONF_ENABLE_FIRE_RISK,
                        default=g(CONF_ENABLE_FIRE_RISK, g(CONF_ENABLE_ACTIVITY_SCORES, DEFAULT_ENABLE_FIRE_RISK)),
                    ): selector.BooleanSelector(),
                    vol.Optional(
                        CONF_ENABLE_RUNNING,
                        default=g(CONF_ENABLE_RUNNING, g(CONF_ENABLE_ACTIVITY_SCORES, DEFAULT_ENABLE_RUNNING)),
                    ): selector.BooleanSelector(),
                    vol.Optional(
                        CONF_ENABLE_SEA_TEMP, default=g(CONF_ENABLE_SEA_TEMP, DEFAULT_ENABLE_SEA_TEMP)
                    ): selector.BooleanSelector(),
                    vol.Optional(
                        CONF_ENABLE_DEGREE_DAYS, default=g(CONF_ENABLE_DEGREE_DAYS, DEFAULT_ENABLE_DEGREE_DAYS)
                    ): selector.BooleanSelector(),
                    vol.Optional(
                        CONF_ENABLE_METAR, default=g(CONF_ENABLE_METAR, DEFAULT_ENABLE_METAR)
                    ): selector.BooleanSelector(),
                    vol.Optional(
                        CONF_ENABLE_CWOP, default=g(CONF_ENABLE_CWOP, DEFAULT_ENABLE_CWOP)
                    ): selector.BooleanSelector(),
                    vol.Optional(
                        CONF_ENABLE_WUNDERGROUND, default=g(CONF_ENABLE_WUNDERGROUND, DEFAULT_ENABLE_WUNDERGROUND)
                    ): selector.BooleanSelector(),
                    vol.Optional(
                        CONF_ENABLE_EXPORT, default=g(CONF_ENABLE_EXPORT, DEFAULT_ENABLE_EXPORT)
                    ): selector.BooleanSelector(),
                    vol.Optional(
                        CONF_ENABLE_AIR_QUALITY, default=g(CONF_ENABLE_AIR_QUALITY, DEFAULT_ENABLE_AIR_QUALITY)
                    ): selector.BooleanSelector(),
                    vol.Optional(
                        CONF_ENABLE_POLLEN, default=g(CONF_ENABLE_POLLEN, DEFAULT_ENABLE_POLLEN)
                    ): selector.BooleanSelector(),
                    vol.Optional(
                        CONF_ENABLE_MOON, default=g(CONF_ENABLE_MOON, DEFAULT_ENABLE_MOON)
                    ): selector.BooleanSelector(),
                    vol.Optional(
                        CONF_ENABLE_SOLAR_FORECAST,
                        default=g(CONF_ENABLE_SOLAR_FORECAST, DEFAULT_ENABLE_SOLAR_FORECAST),
                    ): selector.BooleanSelector(),
                }
            ),
        )

    # ------------------------------------------------------------------
    # Sub-steps for each configurable feature
    # ------------------------------------------------------------------
    def _opt_next_after(self, after: str):
        """Route to the next enabled feature sub-step or finish."""
        order = [
            (CONF_ENABLE_SEA_TEMP, "sea_temp_opt"),
            (CONF_ENABLE_DEGREE_DAYS, "degree_days_opt"),
            (CONF_ENABLE_METAR, "metar_opt"),
            (CONF_ENABLE_CWOP, "cwop_opt"),
            (CONF_ENABLE_WUNDERGROUND, "wunderground_opt"),
            (CONF_ENABLE_EXPORT, "export_opt"),
            (CONF_ENABLE_AIR_QUALITY, "air_quality_opt"),
            (CONF_ENABLE_POLLEN, "pollen_opt"),
            (CONF_ENABLE_SOLAR_FORECAST, "solar_forecast_opt"),
        ]
        past = False
        for conf_key, step_name in order:
            if step_name == after:
                past = True
                continue
            if past and self._opt.get(conf_key):
                return getattr(self, f"async_step_{step_name}")()
        return None  # signals: go to finish

    async def _finish_or_next(self, after: str):
        nxt = self._opt_next_after(after)
        if nxt is not None:
            return await nxt
        return self.async_create_entry(title="", data=self._opt)

    async def async_step_sea_temp_opt(self, user_input: dict[str, Any] | None = None):
        g = self._get
        default_lat = getattr(self.hass.config, "latitude", 0.0) or 0.0
        default_lon = getattr(self.hass.config, "longitude", 0.0) or 0.0
        if user_input is not None:
            self._opt.update(user_input)
            return await self._finish_or_next("sea_temp_opt")
        return self.async_show_form(
            step_id="sea_temp_opt",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_SEA_TEMP_LAT, default=g(CONF_SEA_TEMP_LAT, round(default_lat, 4))
                    ): selector.NumberSelector(selector.NumberSelectorConfig(min=-90, max=90, step=0.001, mode="box")),
                    vol.Optional(
                        CONF_SEA_TEMP_LON, default=g(CONF_SEA_TEMP_LON, round(default_lon, 4))
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=-180, max=180, step=0.001, mode="box")
                    ),
                }
            ),
        )

    async def async_step_degree_days_opt(self, user_input: dict[str, Any] | None = None):
        g = self._get
        if user_input is not None:
            self._opt.update(user_input)
            return await self._finish_or_next("degree_days_opt")
        return self.async_show_form(
            step_id="degree_days_opt",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_DEGREE_DAY_BASE_C, default=g(CONF_DEGREE_DAY_BASE_C, DEFAULT_DEGREE_DAY_BASE_C)
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=0, max=25, step=0.5, mode="box", unit_of_measurement="°C")
                    ),
                }
            ),
        )

    async def async_step_metar_opt(self, user_input: dict[str, Any] | None = None):
        g = self._get
        errors: dict[str, str] = {}
        if user_input is not None:
            icao = str(user_input.get(CONF_METAR_ICAO, "")).upper().strip()
            if not icao:
                lat = self._opt.get(CONF_FORECAST_LAT) or g(CONF_FORECAST_LAT, None)
                lon = self._opt.get(CONF_FORECAST_LON) or g(CONF_FORECAST_LON, None)
                if lat is not None and lon is not None:
                    icao = await _autodetect_metar_icao(lat, lon) or ""
            self._opt[CONF_METAR_ICAO] = icao
            self._opt[CONF_METAR_INTERVAL_MIN] = int(
                user_input.get(CONF_METAR_INTERVAL_MIN, DEFAULT_METAR_INTERVAL_MIN)
            )
            if not errors:
                return await self._finish_or_next("metar_opt")
        return self.async_show_form(
            step_id="metar_opt",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_METAR_ICAO, default=g(CONF_METAR_ICAO, "")): selector.TextSelector(
                        selector.TextSelectorConfig(type="text")
                    ),
                    vol.Optional(
                        CONF_METAR_INTERVAL_MIN, default=g(CONF_METAR_INTERVAL_MIN, DEFAULT_METAR_INTERVAL_MIN)
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=30, max=180, step=30, mode="box", unit_of_measurement="min")
                    ),
                }
            ),
            errors=errors,
            description_placeholders={"info": "Leave ICAO blank to auto-detect nearest airport."},
        )

    async def async_step_cwop_opt(self, user_input: dict[str, Any] | None = None):
        g = self._get
        if user_input is not None:
            self._opt[CONF_CWOP_CALLSIGN] = str(user_input.get(CONF_CWOP_CALLSIGN, "")).upper().strip()
            self._opt[CONF_CWOP_PASSCODE] = str(user_input.get(CONF_CWOP_PASSCODE, "-1")).strip()
            self._opt[CONF_CWOP_INTERVAL_MIN] = int(user_input.get(CONF_CWOP_INTERVAL_MIN, DEFAULT_CWOP_INTERVAL_MIN))
            return await self._finish_or_next("cwop_opt")
        return self.async_show_form(
            step_id="cwop_opt",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_CWOP_CALLSIGN, default=g(CONF_CWOP_CALLSIGN, "")): selector.TextSelector(
                        selector.TextSelectorConfig(type="text")
                    ),
                    vol.Optional(CONF_CWOP_PASSCODE, default=g(CONF_CWOP_PASSCODE, "-1")): selector.TextSelector(
                        selector.TextSelectorConfig(type="text")
                    ),
                    vol.Optional(
                        CONF_CWOP_INTERVAL_MIN, default=g(CONF_CWOP_INTERVAL_MIN, DEFAULT_CWOP_INTERVAL_MIN)
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=5, max=60, step=5, mode="box", unit_of_measurement="min")
                    ),
                }
            ),
        )

    async def async_step_wunderground_opt(self, user_input: dict[str, Any] | None = None):
        g = self._get
        errors: dict[str, str] = {}
        if user_input is not None:
            station_id = str(user_input.get(CONF_WU_STATION_ID, "")).strip()
            api_key = str(user_input.get(CONF_WU_API_KEY, "")).strip()
            if not api_key:
                api_key = g(CONF_WU_API_KEY, "")  # keep existing key if not re-entered
            if station_id and api_key:
                valid, err = await _validate_wu_credentials(station_id, api_key)
                if not valid:
                    errors[CONF_WU_API_KEY] = err or "invalid_api_key"
                else:
                    self._opt[CONF_WU_STATION_ID] = station_id
                    self._opt[CONF_WU_API_KEY] = api_key
                    self._opt[CONF_WU_INTERVAL_MIN] = int(user_input.get(CONF_WU_INTERVAL_MIN, DEFAULT_WU_INTERVAL_MIN))
            else:
                self._opt[CONF_WU_STATION_ID] = station_id
                self._opt[CONF_WU_API_KEY] = api_key
                self._opt[CONF_WU_INTERVAL_MIN] = int(user_input.get(CONF_WU_INTERVAL_MIN, DEFAULT_WU_INTERVAL_MIN))
            if not errors:
                return await self._finish_or_next("wunderground_opt")
        return self.async_show_form(
            step_id="wunderground_opt",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_WU_STATION_ID, default=g(CONF_WU_STATION_ID, "")): selector.TextSelector(
                        selector.TextSelectorConfig(type="text")
                    ),
                    vol.Optional(CONF_WU_API_KEY, default=""): selector.TextSelector(
                        selector.TextSelectorConfig(type="password")
                    ),
                    vol.Optional(
                        CONF_WU_INTERVAL_MIN, default=g(CONF_WU_INTERVAL_MIN, DEFAULT_WU_INTERVAL_MIN)
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=1, max=30, step=1, mode="box", unit_of_measurement="min")
                    ),
                }
            ),
            errors=errors,
            description_placeholders={"info": "Leave API key blank to keep existing key. Will validate."},
        )

    async def async_step_export_opt(self, user_input: dict[str, Any] | None = None):
        g = self._get
        if user_input is not None:
            self._opt[CONF_EXPORT_PATH] = str(user_input.get(CONF_EXPORT_PATH, "/config/ws_core_export")).strip()
            self._opt[CONF_EXPORT_FORMAT] = str(user_input.get(CONF_EXPORT_FORMAT, DEFAULT_EXPORT_FORMAT))
            self._opt[CONF_EXPORT_INTERVAL_MIN] = int(
                user_input.get(CONF_EXPORT_INTERVAL_MIN, DEFAULT_EXPORT_INTERVAL_MIN)
            )
            return await self._finish_or_next("export_opt")
        return self.async_show_form(
            step_id="export_opt",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_EXPORT_PATH, default=g(CONF_EXPORT_PATH, "/config/ws_core_export")
                    ): selector.TextSelector(selector.TextSelectorConfig(type="text")),
                    vol.Optional(
                        CONF_EXPORT_FORMAT, default=g(CONF_EXPORT_FORMAT, DEFAULT_EXPORT_FORMAT)
                    ): selector.SelectSelector(selector.SelectSelectorConfig(options=["csv", "json", "both"])),
                    vol.Optional(
                        CONF_EXPORT_INTERVAL_MIN, default=g(CONF_EXPORT_INTERVAL_MIN, DEFAULT_EXPORT_INTERVAL_MIN)
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=5, max=1440, step=5, mode="box", unit_of_measurement="min")
                    ),
                }
            ),
        )

    async def async_step_air_quality_opt(self, user_input: dict[str, Any] | None = None):
        g = self._get
        if user_input is not None:
            self._opt[CONF_AQI_INTERVAL_MIN] = int(user_input.get(CONF_AQI_INTERVAL_MIN, DEFAULT_AQI_INTERVAL_MIN))
            return await self._finish_or_next("air_quality_opt")
        return self.async_show_form(
            step_id="air_quality_opt",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_AQI_INTERVAL_MIN, default=g(CONF_AQI_INTERVAL_MIN, DEFAULT_AQI_INTERVAL_MIN)
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=15, max=360, step=15, mode="box", unit_of_measurement="min")
                    ),
                }
            ),
            description_placeholders={"info": "Open-Meteo Air Quality API. Free, no key required."},
        )

    async def async_step_pollen_opt(self, user_input: dict[str, Any] | None = None):
        g = self._get
        errors: dict[str, str] = {}
        if user_input is not None:
            api_key = str(user_input.get(CONF_TOMORROW_IO_KEY, "")).strip()
            if not api_key:
                api_key = g(CONF_TOMORROW_IO_KEY, "")  # keep existing
            if api_key:
                lat = self._opt.get(CONF_FORECAST_LAT) or g(CONF_FORECAST_LAT, 0)
                lon = self._opt.get(CONF_FORECAST_LON) or g(CONF_FORECAST_LON, 0)
                valid, err = await _validate_tomorrow_io_key(api_key, lat, lon)
                if not valid:
                    errors[CONF_TOMORROW_IO_KEY] = err or "invalid_api_key"
                else:
                    self._opt[CONF_TOMORROW_IO_KEY] = api_key
                    self._opt[CONF_POLLEN_INTERVAL_MIN] = int(
                        user_input.get(CONF_POLLEN_INTERVAL_MIN, DEFAULT_POLLEN_INTERVAL_MIN)
                    )
            if not errors:
                return await self._finish_or_next("pollen_opt")
        return self.async_show_form(
            step_id="pollen_opt",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_TOMORROW_IO_KEY, default=""): selector.TextSelector(
                        selector.TextSelectorConfig(type="password")
                    ),
                    vol.Optional(
                        CONF_POLLEN_INTERVAL_MIN, default=g(CONF_POLLEN_INTERVAL_MIN, DEFAULT_POLLEN_INTERVAL_MIN)
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=60, max=1440, step=60, mode="box", unit_of_measurement="min")
                    ),
                }
            ),
            errors=errors,
            description_placeholders={"info": "Leave API key blank to keep existing key."},
        )

    async def async_step_solar_forecast_opt(self, user_input: dict[str, Any] | None = None):
        g = self._get
        if user_input is not None:
            self._opt[CONF_SOLAR_PEAK_KW] = float(user_input.get(CONF_SOLAR_PEAK_KW, DEFAULT_SOLAR_PEAK_KW))
            self._opt[CONF_SOLAR_PANEL_AZIMUTH] = int(
                user_input.get(CONF_SOLAR_PANEL_AZIMUTH, DEFAULT_SOLAR_PANEL_AZIMUTH)
            )
            self._opt[CONF_SOLAR_PANEL_TILT] = int(user_input.get(CONF_SOLAR_PANEL_TILT, DEFAULT_SOLAR_PANEL_TILT))
            self._opt[CONF_SOLAR_INTERVAL_MIN] = int(
                user_input.get(CONF_SOLAR_INTERVAL_MIN, DEFAULT_SOLAR_INTERVAL_MIN)
            )
            return await self._finish_or_next("solar_forecast_opt")
        return self.async_show_form(
            step_id="solar_forecast_opt",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_SOLAR_PEAK_KW, default=g(CONF_SOLAR_PEAK_KW, DEFAULT_SOLAR_PEAK_KW)
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0.1, max=100.0, step=0.1, mode="box", unit_of_measurement="kWp"
                        )
                    ),
                    vol.Optional(
                        CONF_SOLAR_PANEL_AZIMUTH, default=g(CONF_SOLAR_PANEL_AZIMUTH, DEFAULT_SOLAR_PANEL_AZIMUTH)
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=0, max=359, step=1, mode="box", unit_of_measurement="°")
                    ),
                    vol.Optional(
                        CONF_SOLAR_PANEL_TILT, default=g(CONF_SOLAR_PANEL_TILT, DEFAULT_SOLAR_PANEL_TILT)
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=0, max=90, step=1, mode="box", unit_of_measurement="°")
                    ),
                    vol.Optional(
                        CONF_SOLAR_INTERVAL_MIN, default=g(CONF_SOLAR_INTERVAL_MIN, DEFAULT_SOLAR_INTERVAL_MIN)
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=30, max=360, step=30, mode="box", unit_of_measurement="min")
                    ),
                }
            ),
            description_placeholders={"info": "Azimuth: 0=N, 90=E, 180=S, 270=W. Tilt: degrees from horizontal."},
        )
