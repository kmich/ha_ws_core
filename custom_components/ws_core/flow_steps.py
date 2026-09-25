"""Steps shared by the config flow and the options flow.

Both flows walk the same upload-credential and indoor-room steps; only where
values are stored, what pre-fills the forms and what follows the last step
differ. Hosts provide those through the small ``_flow_*`` hook methods.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

import voluptuous as vol
from homeassistant.helpers import selector

from .const import (
    CONF_AWEKAS_INTERVAL_MIN,
    CONF_AWEKAS_PASSWORD,
    CONF_AWEKAS_USERNAME,
    CONF_CWOP_CALLSIGN,
    CONF_CWOP_INTERVAL_MIN,
    CONF_CWOP_PASSCODE,
    CONF_CWOP_PORT,
    CONF_CWOP_SERVER,
    CONF_ENABLE_AWEKAS,
    CONF_ENABLE_CWOP,
    CONF_ENABLE_MQTT,
    CONF_ENABLE_OWM_STATIONS,
    CONF_ENABLE_PWSWEATHER,
    CONF_ENABLE_WEATHERCLOUD,
    CONF_ENABLE_WINDY,
    CONF_ENABLE_WOW,
    CONF_INDOOR_ROOMS,
    CONF_MQTT_DISCOVERY_PREFIX,
    CONF_MQTT_INTERVAL_MIN,
    CONF_MQTT_STATE_PREFIX,
    CONF_OWM_STATIONS_API_KEY,
    CONF_OWM_STATIONS_INTERVAL_MIN,
    CONF_OWM_STATIONS_STATION_ID,
    CONF_PWS_API_KEY,
    CONF_PWS_INTERVAL_MIN,
    CONF_PWS_STATION_ID,
    CONF_WC_API_KEY,
    CONF_WC_INTERVAL_MIN,
    CONF_WC_STATION_ID,
    CONF_WINDY_API_KEY,
    CONF_WINDY_INTERVAL_MIN,
    CONF_WINDY_STATION_ID,
    CONF_WOW_AUTH_KEY,
    CONF_WOW_INTERVAL_MIN,
    CONF_WOW_SITE_ID,
    DEFAULT_AWEKAS_INTERVAL_MIN,
    DEFAULT_CWOP_INTERVAL_MIN,
    DEFAULT_CWOP_PORT,
    DEFAULT_CWOP_SERVER,
    DEFAULT_MQTT_DISCOVERY_PREFIX,
    DEFAULT_MQTT_INTERVAL_MIN,
    DEFAULT_MQTT_STATE_PREFIX,
    DEFAULT_OWM_STATIONS_INTERVAL_MIN,
    DEFAULT_PWS_INTERVAL_MIN,
    DEFAULT_WC_INTERVAL_MIN,
    DEFAULT_WINDY_INTERVAL_MIN,
    DEFAULT_WOW_INTERVAL_MIN,
    normalize_indoor_rooms,
)


@dataclass(frozen=True)
class _Field:
    key: str
    default: Any
    kind: str  # "text", "password", "minutes" or "port"
    min_value: int = 1
    required: bool = False  # blank disables the service
    upper: bool = False
    blank_default: bool = False  # blank falls back to ``default``


@dataclass(frozen=True)
class _UploadService:
    step: str  # step id in the config flow; the options flow appends "_opt"
    enable_key: str
    fields: tuple[_Field, ...]
    info: str


UPLOAD_SERVICES: tuple[_UploadService, ...] = (
    _UploadService(
        "weathercloud",
        CONF_ENABLE_WEATHERCLOUD,
        (
            _Field(CONF_WC_STATION_ID, "", "text", required=True),
            _Field(CONF_WC_API_KEY, "", "password", required=True),
            _Field(CONF_WC_INTERVAL_MIN, DEFAULT_WC_INTERVAL_MIN, "minutes"),
        ),
        "Weathercloud station ID and key from weathercloud.net/dashboard. Leave blank to skip.",
    ),
    _UploadService(
        "pwsweather",
        CONF_ENABLE_PWSWEATHER,
        (
            _Field(CONF_PWS_STATION_ID, "", "text", required=True),
            _Field(CONF_PWS_API_KEY, "", "password", required=True),
            _Field(CONF_PWS_INTERVAL_MIN, DEFAULT_PWS_INTERVAL_MIN, "minutes"),
        ),
        "PWSWeather station ID and API key from pwsweather.com. Leave blank to skip.",
    ),
    _UploadService(
        "wow",
        CONF_ENABLE_WOW,
        (
            _Field(CONF_WOW_SITE_ID, "", "text", required=True),
            _Field(CONF_WOW_AUTH_KEY, "", "password", required=True),
            _Field(CONF_WOW_INTERVAL_MIN, DEFAULT_WOW_INTERVAL_MIN, "minutes"),
        ),
        "WOW site ID and authentication key from wow.metoffice.gov.uk. Leave blank to skip.",
    ),
    _UploadService(
        "awekas",
        CONF_ENABLE_AWEKAS,
        (
            _Field(CONF_AWEKAS_USERNAME, "", "text", required=True),
            _Field(CONF_AWEKAS_PASSWORD, "", "password", required=True),
            _Field(CONF_AWEKAS_INTERVAL_MIN, DEFAULT_AWEKAS_INTERVAL_MIN, "minutes"),
        ),
        "AWEKAS username and password from awekas.at. Leave blank to skip.",
    ),
    _UploadService(
        "owm_stations",
        CONF_ENABLE_OWM_STATIONS,
        (
            _Field(CONF_OWM_STATIONS_API_KEY, "", "password", required=True),
            _Field(CONF_OWM_STATIONS_STATION_ID, "", "text", required=True),
            _Field(CONF_OWM_STATIONS_INTERVAL_MIN, DEFAULT_OWM_STATIONS_INTERVAL_MIN, "minutes"),
        ),
        "OpenWeatherMap Stations API. Create a station via the OWM API to get a "
        "station_id, and use your OWM API key. Leave blank to skip.",
    ),
    _UploadService(
        "windy",
        CONF_ENABLE_WINDY,
        (
            _Field(CONF_WINDY_API_KEY, "", "password", required=True),
            _Field(CONF_WINDY_STATION_ID, "", "text"),
            _Field(CONF_WINDY_INTERVAL_MIN, DEFAULT_WINDY_INTERVAL_MIN, "minutes"),
        ),
        "Windy.com Stations API key from stations.windy.com. Station ID is optional "
        "(defaults to 0 for single-station accounts). Leave the key blank to skip.",
    ),
    _UploadService(
        "cwop",
        CONF_ENABLE_CWOP,
        (
            _Field(CONF_CWOP_CALLSIGN, "", "text", required=True, upper=True),
            _Field(CONF_CWOP_PASSCODE, "-1", "text", blank_default=True),
            _Field(CONF_CWOP_SERVER, DEFAULT_CWOP_SERVER, "text", blank_default=True),
            _Field(CONF_CWOP_PORT, DEFAULT_CWOP_PORT, "port"),
            _Field(CONF_CWOP_INTERVAL_MIN, DEFAULT_CWOP_INTERVAL_MIN, "minutes", min_value=5),
        ),
        "CWOP (Citizen Weather Observer Program) via APRS. Enter your CWOP/APRS "
        "callsign (e.g. CW1234 or a licensed ham callsign). Passcode is -1 for "
        "CWOP-issued IDs, or your APRS-IS passcode for ham callsigns. Leave the "
        "callsign blank to skip. Forecast lat/lon must be set.",
    ),
    _UploadService(
        "mqtt_config",
        CONF_ENABLE_MQTT,
        (
            _Field(CONF_MQTT_DISCOVERY_PREFIX, DEFAULT_MQTT_DISCOVERY_PREFIX, "text", blank_default=True),
            _Field(CONF_MQTT_STATE_PREFIX, DEFAULT_MQTT_STATE_PREFIX, "text", blank_default=True),
            _Field(CONF_MQTT_INTERVAL_MIN, DEFAULT_MQTT_INTERVAL_MIN, "minutes"),
        ),
        "Sensors will be published as MQTT Discovery payloads under "
        f"{DEFAULT_MQTT_DISCOVERY_PREFIX}/sensor/... and state updates under "
        f"{DEFAULT_MQTT_STATE_PREFIX}/{{prefix}}/{{sensor}}/state. "
        "Requires the HA MQTT integration to be configured.",
    ),
)
_SERVICES_BY_STEP = {svc.step: svc for svc in UPLOAD_SERVICES}


def _field_selector(field: _Field) -> Any:
    if field.kind == "password":
        return selector.TextSelector(selector.TextSelectorConfig(type="password"))
    if field.kind == "minutes":
        return selector.NumberSelector(
            selector.NumberSelectorConfig(min=field.min_value, max=60, step=1, mode="box", unit_of_measurement="min")
        )
    if field.kind == "port":
        return selector.NumberSelector(selector.NumberSelectorConfig(min=1, max=65535, step=1, mode="box"))
    return selector.TextSelector(selector.TextSelectorConfig(type="text"))


def _normalize(field: _Field, value: Any) -> Any:
    if field.kind in ("minutes", "port"):
        return int(value if value not in (None, "") else field.default)
    text = str(value or "").strip()
    if field.upper:
        text = text.upper()
    if not text and field.blank_default:
        return field.default
    return text


class SharedFlowSteps:
    """Upload-credential and indoor-room steps for both flows.

    Hosts implement:
      _flow_store()            dict that receives submitted values
      _flow_default(key, d)    current value used to pre-fill a form
      _flow_back(user_input)   awaitable navigation result, or None
      _flow_show(step_id, schema, placeholders)
      _uploads_done()          awaitable result after the last upload step
      _rooms_done()            awaitable result when leaving the room menu
    and the class attributes ``_step_suffix`` and ``_rooms_hub_step``.
    """

    _step_suffix = ""
    _rooms_hub_step = "indoor_rooms"

    # -- upload services ------------------------------------------------

    async def _next_upload_step(self, after: str | None = None):
        """Show the next enabled upload step after ``after`` (or the first one)."""
        store = self._flow_store()
        steps = [svc.step for svc in UPLOAD_SERVICES]
        start = steps.index(after) + 1 if after else 0
        for svc in UPLOAD_SERVICES[start:]:
            if store.get(svc.enable_key):
                return await getattr(self, f"async_step_{svc.step}{self._step_suffix}")()
        return await self._uploads_done()

    async def _upload_step(self, step: str, user_input: dict[str, Any] | None):
        svc = _SERVICES_BY_STEP[step]
        if user_input is not None:
            back = await self._flow_back(user_input)
            if back:
                return back
            values = {f.key: _normalize(f, user_input.get(f.key)) for f in svc.fields}
            store = self._flow_store()
            if any(f.required and not values[f.key] for f in svc.fields):
                store[svc.enable_key] = False
            else:
                store.update(values)
            return await self._next_upload_step(after=step)

        schema = {
            vol.Optional(f.key, default=self._flow_default(f.key, f.default)): _field_selector(f) for f in svc.fields
        }
        return self._flow_show(f"{step}{self._step_suffix}", vol.Schema(schema), {"info": svc.info})

    async def async_step_weathercloud(self, user_input: dict[str, Any] | None = None):
        return await self._upload_step("weathercloud", user_input)

    async def async_step_pwsweather(self, user_input: dict[str, Any] | None = None):
        return await self._upload_step("pwsweather", user_input)

    async def async_step_wow(self, user_input: dict[str, Any] | None = None):
        return await self._upload_step("wow", user_input)

    async def async_step_awekas(self, user_input: dict[str, Any] | None = None):
        return await self._upload_step("awekas", user_input)

    async def async_step_owm_stations(self, user_input: dict[str, Any] | None = None):
        return await self._upload_step("owm_stations", user_input)

    async def async_step_windy(self, user_input: dict[str, Any] | None = None):
        return await self._upload_step("windy", user_input)

    async def async_step_cwop(self, user_input: dict[str, Any] | None = None):
        return await self._upload_step("cwop", user_input)

    async def async_step_mqtt_config(self, user_input: dict[str, Any] | None = None):
        return await self._upload_step("mqtt_config", user_input)

    # -- indoor rooms ---------------------------------------------------

    def _rooms_working_copy(self) -> list[dict]:
        """Return (initializing if needed) the in-progress room list."""
        store = self._flow_store()
        if CONF_INDOOR_ROOMS not in store:
            store[CONF_INDOOR_ROOMS] = normalize_indoor_rooms(self._flow_default(CONF_INDOOR_ROOMS, []))
        return store[CONF_INDOOR_ROOMS]

    @staticmethod
    def _room_form_schema(src: dict | None) -> vol.Schema:
        src = src or {}
        sensor_sel = selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor"))
        schema: dict[Any, Any] = {
            vol.Required("name", default=src.get("name", "")): selector.TextSelector(),
        }
        for field in ("temp", "humidity", "co2"):
            cur = src.get(field)
            # suggested_value (not default) keeps the field clearable when
            # editing a room to remove a previously-assigned sensor -- see
            # issue #135.
            key = vol.Optional(field, description={"suggested_value": cur}) if cur else vol.Optional(field)
            schema[key] = sensor_sel
        return vol.Schema(schema)

    async def _rooms_menu(self):
        menu_options = ["room_add"]
        if self._rooms_working_copy():
            menu_options += ["room_edit", "room_remove"]
        menu_options.append("room_done")
        return self.async_show_menu(step_id=self._rooms_hub_step, menu_options=menu_options)

    async def async_step_room_done(self, user_input: dict[str, Any] | None = None):
        return await self._rooms_done()

    async def async_step_room_add(self, user_input: dict[str, Any] | None = None):
        self._edit_rid: str | None = None
        return await self.async_step_room_form()

    async def async_step_room_edit(self, user_input: dict[str, Any] | None = None):
        rooms = self._rooms_working_copy()
        if user_input is not None:
            self._edit_rid = user_input["room"]
            return await self.async_step_room_form()
        options = [{"value": r["id"], "label": r["name"]} for r in rooms]
        return self.async_show_form(
            step_id="room_edit",
            data_schema=vol.Schema(
                {
                    vol.Required("room"): selector.SelectSelector(
                        selector.SelectSelectorConfig(options=options, mode=selector.SelectSelectorMode.DROPDOWN)
                    )
                }
            ),
            last_step=False,
        )

    async def async_step_room_form(self, user_input: dict[str, Any] | None = None):
        rooms = self._rooms_working_copy()
        editing = next((r for r in rooms if r["id"] == self._edit_rid), None) if self._edit_rid else None
        if user_input is not None:
            name = (user_input.get("name") or "").strip()
            if not name:
                return self.async_show_form(
                    step_id="room_form",
                    data_schema=self._room_form_schema({**(editing or {}), **user_input}),
                    errors={"name": "room_name_required"},
                    last_step=False,
                )
            room = {
                "id": editing["id"] if editing else uuid.uuid4().hex[:8],
                "name": name,
                "temp": user_input.get("temp") or None,
                "humidity": user_input.get("humidity") or None,
                "co2": user_input.get("co2") or None,
            }
            store = self._flow_store()
            if editing:
                store[CONF_INDOOR_ROOMS] = [room if r["id"] == editing["id"] else r for r in rooms]
            else:
                store[CONF_INDOOR_ROOMS] = [*rooms, room]
            return await self._rooms_menu()
        return self.async_show_form(
            step_id="room_form",
            data_schema=self._room_form_schema(editing),
            last_step=False,
        )

    async def async_step_room_remove(self, user_input: dict[str, Any] | None = None):
        rooms = self._rooms_working_copy()
        if user_input is not None:
            to_remove = set(user_input.get("rooms") or [])
            self._flow_store()[CONF_INDOOR_ROOMS] = [r for r in rooms if r["id"] not in to_remove]
            return await self._rooms_menu()
        options = [{"value": r["id"], "label": r["name"]} for r in rooms]
        return self.async_show_form(
            step_id="room_remove",
            data_schema=vol.Schema(
                {
                    vol.Optional("rooms", default=[]): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=options, multiple=True, mode=selector.SelectSelectorMode.LIST
                        )
                    )
                }
            ),
            last_step=False,
        )
