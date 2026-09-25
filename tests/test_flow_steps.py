"""Upload-credential and indoor-room steps shared by the config and options flows."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.ws_core.config_flow import WSStationConfigFlow, WSStationOptionsFlowHandler
from custom_components.ws_core.const import (
    CONF_CWOP_CALLSIGN,
    CONF_CWOP_PASSCODE,
    CONF_ENABLE_CWOP,
    CONF_ENABLE_MQTT,
    CONF_ENABLE_WEATHERCLOUD,
    CONF_ENABLE_WINDY,
    CONF_INDOOR_ROOMS,
    CONF_MQTT_DISCOVERY_PREFIX,
    CONF_WC_API_KEY,
    CONF_WC_STATION_ID,
    CONF_WINDY_API_KEY,
    CONF_WINDY_INTERVAL_MIN,
    DEFAULT_MQTT_DISCOVERY_PREFIX,
)

pytestmark = pytest.mark.asyncio


def _config_flow(data: dict) -> WSStationConfigFlow:
    flow = WSStationConfigFlow()
    flow.hass = MagicMock()
    flow._data = dict(data)
    flow._show_step = lambda step_id, data_schema, **kw: {"step_id": step_id, "schema": data_schema}
    flow.async_show_form = MagicMock(side_effect=lambda **kw: {"step_id": kw["step_id"]})
    flow.async_show_menu = MagicMock(side_effect=lambda **kw: {"menu": kw["step_id"], "options": kw["menu_options"]})
    flow.async_step_alerts = AsyncMock(return_value={"step_id": "alerts"})
    return flow


def _options_flow(stored: dict, opt: dict) -> WSStationOptionsFlowHandler:
    flow = WSStationOptionsFlowHandler()
    flow.hass = MagicMock()
    flow._get = lambda key, default: stored.get(key, default)
    flow._opt = dict(opt)
    flow.async_show_form = MagicMock(side_effect=lambda **kw: {"step_id": kw["step_id"], "schema": kw["data_schema"]})
    flow.async_create_entry = MagicMock(side_effect=lambda **kw: {"type": "create_entry", "data": kw["data"]})
    return flow


def _default(schema, key):
    marker = next(m for m in schema.schema if str(m) == key)
    return marker.default()


async def test_setup_flow_visits_every_enabled_upload_step():
    # Weathercloud used to jump straight past OWM Stations, Windy and CWOP.
    flow = _config_flow({CONF_ENABLE_WEATHERCLOUD: True, CONF_ENABLE_WINDY: True, CONF_ENABLE_CWOP: True})
    assert (await flow._next_v2_step())["step_id"] == "weathercloud"
    result = await flow.async_step_weathercloud({CONF_WC_STATION_ID: " 42 ", CONF_WC_API_KEY: "key"})
    assert result["step_id"] == "windy"
    result = await flow.async_step_windy({CONF_WINDY_API_KEY: "wk"})
    assert result["step_id"] == "cwop"
    result = await flow.async_step_cwop({CONF_CWOP_CALLSIGN: " cw1234 ", CONF_CWOP_PASSCODE: ""})
    assert result["step_id"] == "alerts"

    assert flow._data[CONF_WC_STATION_ID] == "42"
    assert flow._data[CONF_CWOP_CALLSIGN] == "CW1234"
    assert flow._data[CONF_CWOP_PASSCODE] == "-1"


async def test_blank_credentials_disable_the_service():
    flow = _config_flow({CONF_ENABLE_WEATHERCLOUD: True})
    await flow.async_step_weathercloud({CONF_WC_STATION_ID: "", CONF_WC_API_KEY: "key"})
    assert flow._data[CONF_ENABLE_WEATHERCLOUD] is False
    assert CONF_WC_API_KEY not in flow._data


async def test_options_flow_prefills_and_normalizes():
    flow = _options_flow(
        stored={CONF_WINDY_API_KEY: "old-key", CONF_WINDY_INTERVAL_MIN: 10},
        opt={CONF_ENABLE_WINDY: True, CONF_ENABLE_MQTT: True},
    )
    result = await flow._next_v2_opt_step()
    assert result["step_id"] == "windy_opt"
    assert _default(result["schema"], CONF_WINDY_API_KEY) == "old-key"
    assert _default(result["schema"], CONF_WINDY_INTERVAL_MIN) == 10

    result = await flow.async_step_windy_opt({CONF_WINDY_API_KEY: " new-key ", CONF_WINDY_INTERVAL_MIN: 5.0})
    assert result["step_id"] == "mqtt_config_opt"
    result = await flow.async_step_mqtt_config_opt({CONF_MQTT_DISCOVERY_PREFIX: " "})
    assert result["type"] == "create_entry"
    assert result["data"][CONF_WINDY_API_KEY] == "new-key"
    assert result["data"][CONF_WINDY_INTERVAL_MIN] == 5
    assert result["data"][CONF_MQTT_DISCOVERY_PREFIX] == DEFAULT_MQTT_DISCOVERY_PREFIX


async def test_rooms_add_then_continue_to_uploads():
    flow = _config_flow({CONF_ENABLE_WINDY: True})
    menu = await flow.async_step_indoor_rooms()
    assert menu == {"menu": "indoor_rooms", "options": ["room_add", "room_done"]}

    await flow.async_step_room_add()
    menu = await flow.async_step_room_form({"name": " Kitchen ", "temp": "sensor.kitchen_temp"})
    assert menu["options"] == ["room_add", "room_edit", "room_remove", "room_done"]
    rooms = flow._data[CONF_INDOOR_ROOMS]
    assert [r["name"] for r in rooms] == ["Kitchen"]
    assert rooms[0]["temp"] == "sensor.kitchen_temp"

    assert (await flow.async_step_room_done())["step_id"] == "windy"


async def test_options_rooms_menu_uses_options_step_id():
    flow = _options_flow(stored={CONF_INDOOR_ROOMS: []}, opt={})
    flow.async_show_menu = MagicMock(side_effect=lambda **kw: {"menu": kw["step_id"]})
    assert (await flow.async_step_indoor_rooms_opt())["menu"] == "indoor_rooms_opt"
