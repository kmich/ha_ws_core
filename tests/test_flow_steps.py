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


class TestFreezeThresholdRoundTrip:
    """Submitting Core options unchanged must preserve CONF_THRESH_FREEZE_C across unit mixes."""

    @pytest.mark.parametrize(
        ("imperial_ha", "units_mode", "temp_unit", "initial_freeze_c"),
        [
            (False, "auto", "auto", -2.0),
            (True, "auto", "auto", -2.0),
            (True, "auto", "C", -2.0),  # Imperial HA system with Celsius override
            (False, "auto", "F", -2.0),  # Metric HA system with Fahrenheit override
            (False, "imperial", "C", -2.0),  # Imperial mode override with Celsius temp override
        ],
    )
    async def test_core_options_unchanged_preserves_freeze_threshold(
        self,
        imperial_ha: bool,
        units_mode: str,
        temp_unit: str,
        initial_freeze_c: float,
    ):
        import voluptuous as vol
        from homeassistant.util.unit_system import METRIC_SYSTEM, US_CUSTOMARY_SYSTEM

        from custom_components.ws_core.const import (
            CONF_TEMP_UNIT,
            CONF_THRESH_FREEZE_C,
            CONF_UNITS_MODE,
        )

        flow = _options_flow(
            {
                CONF_UNITS_MODE: units_mode,
                CONF_TEMP_UNIT: temp_unit,
                CONF_THRESH_FREEZE_C: initial_freeze_c,
            },
            {},
        )
        flow.hass.config.units = US_CUSTOMARY_SYSTEM if imperial_ha else METRIC_SYSTEM
        flow.hass.config.latitude = 40.0
        flow.hass.config.longitude = -74.0
        flow.async_step_required_sources_opt = AsyncMock(return_value={"step_id": "required_sources_opt"})
        show_res = await flow.async_step_thresholds(user_input=None)
        schema = show_res["schema"]

        unchanged_input = {}
        for key in schema.schema:
            name = getattr(key, "schema", key)
            if isinstance(key, vol.Optional) and key.default is not vol.UNDEFINED:
                unchanged_input[name] = key.default() if callable(key.default) else key.default

        # Submit the exact schema defaults unchanged
        await flow.async_step_thresholds(user_input=unchanged_input)
        assert abs(flow._opt[CONF_THRESH_FREEZE_C] - initial_freeze_c) < 0.15


class TestSoilMoistureUnitFlow:
    """CONF_SOIL_MOISTURE_UNIT option appears next to soil_moisture in optional_sources steps."""

    async def test_optional_sources_exposes_and_stores_soil_moisture_unit(self):
        from custom_components.ws_core.const import (
            CONF_SOIL_MOISTURE_UNIT,
            CONF_SOURCES,
            SRC_SOIL_MOISTURE,
        )

        flow = _config_flow({})
        flow._validate_numeric_sensor = MagicMock(return_value=None)
        flow.async_step_location = AsyncMock(return_value={"step_id": "location"})

        res = await flow.async_step_optional_sources(user_input=None)
        keys = [str(getattr(k, "schema", k)) for k in res["schema"].schema]
        assert CONF_SOIL_MOISTURE_UNIT in keys
        assert keys.index(CONF_SOIL_MOISTURE_UNIT) == keys.index(SRC_SOIL_MOISTURE) + 1

        await flow.async_step_optional_sources(
            user_input={SRC_SOIL_MOISTURE: "sensor.soil", CONF_SOIL_MOISTURE_UNIT: "percent"}
        )
        assert flow._data[CONF_SOURCES][SRC_SOIL_MOISTURE] == "sensor.soil"
        assert CONF_SOIL_MOISTURE_UNIT not in flow._data[CONF_SOURCES]
        assert flow._data[CONF_SOIL_MOISTURE_UNIT] == "percent"

    async def test_optional_sources_opt_exposes_and_stores_soil_moisture_unit(self):
        from unittest.mock import patch

        from custom_components.ws_core.const import (
            CONF_SOIL_MOISTURE_UNIT,
            CONF_SOURCES,
            SRC_SOIL_MOISTURE,
        )

        flow = _options_flow({CONF_SOIL_MOISTURE_UNIT: "fraction"}, {})
        flow._current_sources_for_options = MagicMock(return_value={SRC_SOIL_MOISTURE: "sensor.soil"})
        flow.async_step_features_opt = AsyncMock(return_value={"step_id": "features_opt"})

        res = await flow.async_step_optional_sources_opt(user_input=None)
        keys = [str(getattr(k, "schema", k)) for k in res["schema"].schema]
        assert CONF_SOIL_MOISTURE_UNIT in keys
        assert keys.index(CONF_SOIL_MOISTURE_UNIT) == keys.index(SRC_SOIL_MOISTURE) + 1
        assert _default(res["schema"], CONF_SOIL_MOISTURE_UNIT) == "fraction"

        with patch("custom_components.ws_core.config_flow._validate_numeric_sensor", return_value=None):
            await flow.async_step_optional_sources_opt(
                user_input={SRC_SOIL_MOISTURE: "sensor.soil", CONF_SOIL_MOISTURE_UNIT: "percent"}
            )
        assert flow._opt[CONF_SOURCES][SRC_SOIL_MOISTURE] == "sensor.soil"
        assert CONF_SOIL_MOISTURE_UNIT not in flow._opt[CONF_SOURCES]
        assert flow._opt[CONF_SOIL_MOISTURE_UNIT] == "percent"


class TestOptionsMenuNavigation:
    """v3.0.0 Scope D: Menu-driven options flow navigation."""

    async def test_options_init_displays_main_menu(self):
        flow = _options_flow(stored={}, opt={})
        flow.async_show_menu = MagicMock(
            side_effect=lambda **kw: {"menu": kw["step_id"], "options": kw["menu_options"]}
        )
        res = await flow.async_step_init(None)
        assert res["menu"] == "init"
        assert res["options"] == [
            "sources",
            "forecast",
            "decision_profiles",
            "rooms",
            "thresholds",
            "uploads",
            "diagnostics",
        ]

    async def test_options_forecast_step_saves_and_exposes_schema(self):
        from custom_components.ws_core.const import (
            CONF_FORECAST_ENABLED,
            CONF_FORECAST_ENTITY,
            CONF_FORECAST_INTERVAL_MIN,
            CONF_FORECAST_PROVIDER,
            FORECAST_PROVIDER_HA_ENTITY,
        )

        flow = _options_flow(
            stored={CONF_FORECAST_PROVIDER: "open_meteo", CONF_FORECAST_ENTITY: "weather.old"},
            opt={CONF_FORECAST_ENTITY: "weather.old"},
        )
        flow.async_show_form = MagicMock(
            side_effect=lambda **kw: {
                "step_id": kw["step_id"],
                "schema": kw["data_schema"],
                "errors": kw.get("errors", {}),
            }
        )
        res = await flow.async_step_forecast(None)
        assert res["step_id"] == "forecast"

        # Selecting ha_weather_entity without forecast_entity returns required error
        err_res = await flow.async_step_forecast(
            {CONF_FORECAST_ENABLED: True, CONF_FORECAST_PROVIDER: FORECAST_PROVIDER_HA_ENTITY}
        )
        assert err_res["errors"] == {CONF_FORECAST_ENTITY: "required"}

        # Clearing forecast_entity explicitly resets _opt[CONF_FORECAST_ENTITY] to ""
        save_res = await flow.async_step_forecast({CONF_FORECAST_ENABLED: False, CONF_FORECAST_INTERVAL_MIN: 60})
        assert save_res["type"] == "create_entry"
        assert save_res["data"][CONF_FORECAST_ENABLED] is False
        assert save_res["data"][CONF_FORECAST_INTERVAL_MIN] == 60
        assert save_res["data"][CONF_FORECAST_ENTITY] == ""

    async def test_options_decision_profiles_step(self):
        from custom_components.ws_core.const import (
            CONF_ENABLE_WEATHER_WINDOWS,
            CONF_WEATHER_WINDOW_PROFILES,
            PROFILE_OUTDOOR_DRYING,
        )

        flow = _options_flow(stored={}, opt={})
        res = await flow.async_step_decision_profiles(None)
        assert res["step_id"] == "decision_profiles"

        save_res = await flow.async_step_decision_profiles(
            {
                CONF_ENABLE_WEATHER_WINDOWS: True,
                CONF_WEATHER_WINDOW_PROFILES: [PROFILE_OUTDOOR_DRYING],
            }
        )
        assert save_res["type"] == "create_entry"
        assert save_res["data"][CONF_ENABLE_WEATHER_WINDOWS] is True
        assert save_res["data"][CONF_WEATHER_WINDOW_PROFILES] == [PROFILE_OUTDOOR_DRYING]

    async def test_options_thresholds_step_validates_and_saves(self):
        from custom_components.ws_core.const import CONF_PREFIX

        flow = _options_flow(stored={}, opt={})
        res = await flow.async_step_thresholds(None)
        assert res["step_id"] == "thresholds"

        save_res = await flow.async_step_thresholds({CONF_PREFIX: "my_station"})
        assert save_res["type"] == "create_entry"
        assert save_res["data"][CONF_PREFIX] == "my_station"

    async def test_options_rooms_menu_routes_and_done_creates_entry(self):
        flow = _options_flow(stored={CONF_INDOOR_ROOMS: []}, opt={})
        flow.async_show_menu = MagicMock(
            side_effect=lambda **kw: {"menu": kw["step_id"], "options": kw["menu_options"]}
        )
        menu = await flow.async_step_rooms(None)
        assert menu["menu"] == "indoor_rooms_opt"
        assert flow._in_menu_rooms is True

        done_res = await flow.async_step_room_done()
        assert done_res["type"] == "create_entry"

    async def test_options_sources_menu_routes_and_done_creates_entry(self):
        from unittest.mock import patch

        from custom_components.ws_core.const import CONF_SOURCES, REQUIRED_SOURCES

        sources = {k: f"sensor.{k}" for k in REQUIRED_SOURCES}
        flow = _options_flow(stored={CONF_SOURCES: sources}, opt={})

        req_res = await flow.async_step_sources(None)
        assert req_res["step_id"] == "required_sources_opt"

        with patch("custom_components.ws_core.config_flow._validate_numeric_sensor", return_value=None):
            opt_res = await flow.async_step_required_sources_opt(sources)
            assert opt_res["step_id"] == "optional_sources_opt"

            save_res = await flow.async_step_optional_sources_opt({})
            assert save_res["type"] == "create_entry"
