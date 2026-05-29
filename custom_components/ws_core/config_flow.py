"""Config flow for Weather Station Core."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
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
    CONF_ELEVATION_M,
    CONF_ENABLE_ADVANCED_SENSORS,
    CONF_ENABLE_AIR_QUALITY,
    CONF_ENABLE_COMFORT_INDICES,
    CONF_ENABLE_DIAGNOSTICS,
    CONF_ENABLE_DISPLAY_SENSORS,
    CONF_ENABLE_FIRE_RISK,
    CONF_ENABLE_FOG,
    CONF_ENABLE_FWI_COMPONENTS,
    CONF_ENABLE_MOON,
    CONF_ENABLE_NOWCAST,
    CONF_ENABLE_POLLEN,
    CONF_ENABLE_SEA_TEMP,
    CONF_ENABLE_SOLAR_FORECAST,
    CONF_ENABLE_THUNDERSTORM,
    CONF_ENABLE_VIGICRUES,
    CONF_ENABLE_VIGILANCE_METEO,
    CONF_ENABLE_WUNDERGROUND,
    CONF_ENABLE_ZAMBRETTI,
    CONF_FORECAST_API_KEY,
    CONF_FORECAST_ENABLED,
    CONF_FORECAST_INTERVAL_MIN,
    CONF_FORECAST_LAT,
    CONF_FORECAST_LON,
    CONF_FORECAST_PROVIDER,
    CONF_HEMISPHERE,
    CONF_NAME,
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
    CONF_UNITS_MODE,
    CONF_VIGICRUES_STATION_CODE,
    CONF_VIGICRUES_STATIONS,
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
    DEFAULT_ELEVATION_M,
    DEFAULT_ENABLE_ADVANCED_SENSORS,
    DEFAULT_ENABLE_AIR_QUALITY,
    DEFAULT_ENABLE_COMFORT_INDICES,
    DEFAULT_ENABLE_DIAGNOSTICS,
    DEFAULT_ENABLE_DISPLAY_SENSORS,
    DEFAULT_ENABLE_FIRE_RISK,
    DEFAULT_ENABLE_FOG,
    DEFAULT_ENABLE_FWI_COMPONENTS,
    DEFAULT_ENABLE_MOON,
    DEFAULT_ENABLE_NOWCAST,
    DEFAULT_ENABLE_POLLEN,
    DEFAULT_ENABLE_SEA_TEMP,
    DEFAULT_ENABLE_SOLAR_FORECAST,
    DEFAULT_ENABLE_THUNDERSTORM,
    DEFAULT_ENABLE_VIGICRUES,
    DEFAULT_ENABLE_VIGILANCE_METEO,
    DEFAULT_ENABLE_WUNDERGROUND,
    DEFAULT_FORECAST_ENABLED,
    DEFAULT_FORECAST_INTERVAL_MIN,
    DEFAULT_FORECAST_PROVIDER,
    DEFAULT_HEMISPHERE,
    DEFAULT_NAME,
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
    FORECAST_PROVIDER_MET_NO,
    FORECAST_PROVIDER_METEO_FRANCE,
    FORECAST_PROVIDER_NWS,
    FORECAST_PROVIDER_OPEN_METEO,
    FORECAST_PROVIDER_OWM,
    FORECAST_PROVIDER_PIRATE,
    HEMISPHERE_OPTIONS,
    OPTIONAL_SOURCES,
    PROVIDERS_REQUIRING_API_KEY,
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


_VIGICRUES_AUTO_OPTION = {
    "value": "",
    "label": "auto_nearest",  # Modifié pour servir de fallback ou géré par la traduction du sélecteur
    "_name": "",
    "_river": "",
}


async def _fetch_vigicrues_station_options(lat: float, lon: float) -> list[dict]:
    """Return a list of nearby Vigicrues stations as SelectSelector option dicts."""
    options = [_VIGICRUES_AUTO_OPTION]
    try:
        url = (
            "https://hubeau.eaufrance.fr/api/v2/hydrometrie/referentiel/stations"
            f"?format=json&longitude={lon:.4f}&latitude={lat:.4f}&distance=50"
            "&en_service=true&size=20"
            "&fields=code_station,libelle_station,libelle_cours_eau"
        )
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    return options
                data = await resp.json()
    except (aiohttp.ClientError, TimeoutError, ValueError):
        return options

    for st in data.get("data", []):
        code = st.get("code_station", "").strip()
        name = (st.get("libelle_station") or code).strip()
        river = (st.get("libelle_cours_eau") or "").strip()
        if not code:
            continue
        label = f"{name} ({river})" if river else name
        options.append({"value": code, "label": label, "_name": name, "_river": river})

    return options


def _guess_defaults(hass: HomeAssistant) -> dict[str, str]:
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
        SRC_BATTERY: ["ws_01_battery", "ws90_battery", "wh90_battery"],
    }

    for k, subs in mapping.items():
        eid = pick(subs)
        if eid:
            guess[k] = eid
    return guess


def _auto_detect_elevation(hass: HomeAssistant) -> float:
    try:
        elev = float(hass.config.elevation)
        if VALID_ELEVATION_MIN_M <= elev <= VALID_ELEVATION_MAX_M:
            return round(elev, 1)
    except (TypeError, ValueError):
        pass

    for state in hass.states.async_all():
        attrs = state.attributes
        for attr_key in ("elevation", "altitude", "elevation_m", "alt_m"):
            raw = attrs.get(attr_key)
            if raw is not None:
                try:
                    elev = float(raw)
                    if VALID_ELEVATION_MIN_M <= elev <= VALID_ELEVATION_MAX_M:
                        return round(elev, 1)
                except (TypeError, ValueError):
                    continue

    return DEFAULT_ELEVATION_M


def _guess_hemisphere(hass: HomeAssistant) -> str:
    try:
        lat = float(hass.config.latitude)
        return "Southern" if lat < 0 else "Northern"
    except (TypeError, ValueError):
        return DEFAULT_HEMISPHERE


def _guess_climate_region(hass: HomeAssistant) -> str:
    try:
        lat = float(hass.config.latitude)
        lon = float(hass.config.longitude)
    except (TypeError, ValueError):
        return DEFAULT_CLIMATE_REGION

    if lat < 0:
        return "Australia"
    if lat > 55 and 5 <= lon <= 32:
        return "Scandinavia"
    if 30 <= lat <= 47 and -5 <= lon <= 40:
        return "Mediterranean"
    if -170 <= lon <= -50:
        return "North America East" if lon > -100 else "North America West"
    if lon > 15:
        return "Continental Europe"
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


_DEVICE_CLASS_FOR_SOURCE: dict[str, str] = {
    SRC_TEMP: "temperature",
    SRC_HUM: "humidity",
    SRC_PRESS: "atmospheric_pressure",
    SRC_RAIN_TOTAL: "precipitation",
    SRC_LUX: "illuminance",
    SRC_DEW_POINT: "temperature",
    SRC_BATTERY: "battery",
    SRC_SOLAR_RADIATION: "irradiance",
}

_EXTRA_DEVICE_CLASSES_FOR_SOURCE: dict[str, set[str]] = {
    SRC_BATTERY: {"voltage"},
}

_EXPECTED_UNITS_FOR_SOURCE: dict[str, str] = {
    SRC_TEMP: "°C / °F",
    SRC_HUM: "%",
    SRC_PRESS: "hPa / mbar / inHg",
    SRC_WIND: "m/s, km/h, mph or kn",
    SRC_GUST: "m/s, km/h, mph or kn",
    SRC_WIND_DIR: "° (0–360)",
    SRC_RAIN_TOTAL: "mm / in",
    SRC_LUX: "lx",
    SRC_UV: "UV index",
    SRC_DEW_POINT: "°C / °F",
    SRC_BATTERY: "% or V",
    SRC_SOLAR_RADIATION: "W/m²",
}


def _build_entity_selector(source_key: str) -> selector.EntitySelector:
    dc = _DEVICE_CLASS_FOR_SOURCE.get(source_key)
    if dc:
        return selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor", device_class=dc))
    return selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor"))


# ---------------------------------------------------------------------------
# Config Flow
# ---------------------------------------------------------------------------


class WSStationConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = CONFIG_VERSION

    @classmethod
    def async_get_options_flow(cls, config_entry: config_entries.ConfigEntry):
        return WSStationOptionsFlowHandler()

    def __init__(self):
        self._data: dict[str, Any] = {}
        self._step_history: list[str] = []

    def _show_step(
        self,
        step_id: str,
        data_schema: vol.Schema,
        errors: dict | None = None,
        last_step: bool = False,
        description_placeholders: dict | None = None,
    ):
        if not self._step_history or self._step_history[-1] != step_id:
            self._step_history.append(step_id)
        if step_id != "user" and len(self._step_history) > 1:
            try:
                extended = {**data_schema.schema, vol.Optional("_go_back", default=False): bool}
                data_schema = vol.Schema(extended)
            except Exception:
                pass
        return self.async_show_form(
            step_id=step_id,
            data_schema=data_schema,
            errors=errors or {},
            last_step=last_step,
            description_placeholders=description_placeholders,
        )

    async def _handle_back(self, user_input: dict[str, Any]) -> dict | None:
        if not user_input.pop("_go_back", False):
            return None
        if len(self._step_history) >= 2:
            self._step_history.pop()
            prev = self._step_history.pop()
            handler = getattr(self, f"async_step_{prev}", None)
            if handler:
                return await handler()
        return None

    def _validate_source_sensor(self, eid: str, source_key: str) -> str | None:
        st = self.hass.states.get(eid)
        if st is None or st.state in ("unknown", "unavailable"):
            return "entity_not_found"
        try:
            float(st.state)
        except (ValueError, TypeError):
            return "not_numeric"
        expected_dc = _DEVICE_CLASS_FOR_SOURCE.get(source_key)
        if expected_dc:
            actual_dc = st.attributes.get("device_class", "")
            extras = _EXTRA_DEVICE_CLASSES_FOR_SOURCE.get(source_key, set())
            if actual_dc and actual_dc != expected_dc and actual_dc not in extras:
                return "wrong_sensor_type"
        return None

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            self._data[CONF_NAME] = str(user_input.get(CONF_NAME) or DEFAULT_NAME)
            self._data[CONF_PREFIX] = _sanitize_prefix(str(user_input.get(CONF_PREFIX) or DEFAULT_PREFIX))
            return await self.async_step_required_sources()

        return self._show_step(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
                    vol.Required(CONF_PREFIX, default=DEFAULT_PREFIX): str,
                }
            ),
            last_step=False,
        )

    async def async_step_required_sources(self, user_input: dict[str, Any] | None = None):
        defaults = _guess_defaults(self.hass)
        errors: dict[str, str] = {}

        if user_input is not None:
            back = await self._handle_back(user_input)
            if back:
                return back
            for k in REQUIRED_SOURCES:
                eid = user_input.get(k)
                if not eid:
                    errors[k] = "required"
                else:
                    err = self._validate_source_sensor(eid, k)
                    if err:
                        errors[k] = err
            if not errors:
                sources = {k: user_input[k] for k in REQUIRED_SOURCES}
                self._data[CONF_SOURCES] = sources
                return await self.async_step_optional_sources()

        fields = {vol.Required(k, default=defaults.get(k)): _build_entity_selector(k) for k in REQUIRED_SOURCES}
        return self._show_step(
            step_id="required_sources",
            data_schema=vol.Schema(fields),
            errors=errors,
            last_step=False,
        )

    async def async_step_optional_sources(self, user_input: dict[str, Any] | None = None):
        defaults = _guess_defaults(self.hass)
        errors: dict[str, str] = {}

        if user_input is not None:
            back = await self._handle_back(user_input)
            if back:
                return back
            sources = dict(self._data.get(CONF_SOURCES, {}))
            for k in OPTIONAL_SOURCES:
                eid = user_input.get(k)
                if not eid:
                    continue
                err = self._validate_source_sensor(eid, k)
                if err:
                    errors[k] = err
                else:
                    sources[k] = eid
            if not errors:
                self._data[CONF_SOURCES] = sources
                return await self.async_step_location()

        fields = {
            (vol.Optional(k, default=defaults[k]) if k in defaults else vol.Optional(k)): _build_entity_selector(k)
            for k in OPTIONAL_SOURCES
        }
        return self._show_step(
            step_id="optional_sources",
            data_schema=vol.Schema(fields),
            errors=errors,
            last_step=False,
        )

    async def async_step_location(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}

        auto_elev = _auto_detect_elevation(self.hass)
        auto_hemi = _guess_hemisphere(self.hass)
        auto_region = _guess_climate_region(self.hass)

        if user_input is not None:
            back = await self._handle_back(user_input)
            if back:
                return back
            elev = float(user_input.get(CONF_ELEVATION_M, auto_elev))
            if not (VALID_ELEVATION_MIN_M <= elev <= VALID_ELEVATION_MAX_M):
                errors[CONF_ELEVATION_M] = "elevation_out_of_range"

            if not errors:
                self._data[CONF_HEMISPHERE] = user_input[CONF_HEMISPHERE]
                self._data[CONF_CLIMATE_REGION] = user_input[CONF_CLIMATE_REGION]
                self._data[CONF_ELEVATION_M] = elev
                return await self.async_step_display()

        return self._show_step(
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
            last_step=False,
        )

    async def async_step_display(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            back = await self._handle_back(user_input)
            if back:
                return back
            self._data[CONF_UNITS_MODE] = user_input[CONF_UNITS_MODE]
            self._data[CONF_TEMP_UNIT] = user_input[CONF_TEMP_UNIT]
            return await self.async_step_forecast()

        try:
            is_metric = self.hass.config.units.temperature_unit == "°C"
            default_units = "metric" if is_metric else "imperial"
            default_temp = "C" if is_metric else "F"
        except Exception:
            default_units = DEFAULT_UNITS_MODE
            default_temp = DEFAULT_TEMP_UNIT

        return self._show_step(
            step_id="display",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_UNITS_MODE, default=default_units): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                {"value": "auto", "label": "auto"},
                                {"value": "metric", "label": "metric"},
                                {"value": "imperial", "label": "imperial"},
                            ],
                            mode="list",
                            translation_key="units_mode",
                        )
                    ),
                    vol.Required(CONF_TEMP_UNIT, default=default_temp): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                {"value": "auto", "label": "auto"},
                                {"value": "C", "label": "celsius"},
                                {"value": "F", "label": "fahrenheit"},
                            ],
                            mode="list",
                            translation_key="temp_unit",
                        )
                    ),
                }
            ),
            last_step=False,
        )

    async def async_step_forecast(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            back = await self._handle_back(user_input)
            if back:
                return back
            self._data.update(user_input)
            if user_input.get(CONF_FORECAST_PROVIDER) in PROVIDERS_REQUIRING_API_KEY:
                return await self.async_step_forecast_api_key()
            return await self.async_step_features()

        default_lat = getattr(self.hass.config, "latitude", 0.0) or 0.0
        default_lon = getattr(self.hass.config, "longitude", 0.0) or 0.0

        return self._show_step(
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
                    vol.Optional(CONF_FORECAST_PROVIDER, default=DEFAULT_FORECAST_PROVIDER): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                {"value": FORECAST_PROVIDER_OPEN_METEO, "label": "open_meteo"},
                                {"value": FORECAST_PROVIDER_MET_NO, "label": "met_no"},
                                {"value": FORECAST_PROVIDER_NWS, "label": "nws"},
                                {"value": FORECAST_PROVIDER_OWM, "label": "owm"},
                                {"value": FORECAST_PROVIDER_PIRATE, "label": "pirate"},
                                {"value": FORECAST_PROVIDER_METEO_FRANCE, "label": "meteo_france"},
                            ],
                            mode=selector.SelectSelectorMode.LIST,
                            translation_key="forecast_provider",
                        )
                    ),
                }
            ),
            last_step=False,
        )

    async def async_step_forecast_api_key(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            back = await self._handle_back(user_input)
            if back:
                return back
            self._data.update(user_input)
            return await self.async_step_features()

        provider = self._data.get(CONF_FORECAST_PROVIDER, "")
        provider_labels = {
            FORECAST_PROVIDER_OWM: "OpenWeatherMap",
            FORECAST_PROVIDER_PIRATE: "Pirate Weather",
            FORECAST_PROVIDER_METEO_FRANCE: "Météo France",
        }
        provider_name = provider_labels.get(provider, provider)

        return self._show_step(
            step_id="forecast_api_key",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_FORECAST_API_KEY,
                        default=self._data.get(CONF_FORECAST_API_KEY, ""),
                    ): selector.TextSelector(selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)),
                    vol.Optional("_go_back", default=False): selector.BooleanSelector(),
                }
            ),
            description_placeholders={"provider_name": provider_name},
            last_step=False,
        )

    async def async_step_features(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            back = await self._handle_back(user_input)
            if back:
                return back
            self._data[CONF_ENABLE_ZAMBRETTI] = True
            self._data[CONF_ENABLE_DISPLAY_SENSORS] = bool(user_input.get(CONF_ENABLE_DISPLAY_SENSORS, True))
