"""Unit tests for the ws_core weather platform."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.ws_core.const import (
    CONF_PREFIX,
    DOMAIN,
    KEY_CURRENT_CONDITION,
    KEY_DEW_POINT_C,
    KEY_FEELS_LIKE_C,
    KEY_FORECAST,
    KEY_NORM_HUMIDITY,
    KEY_NORM_TEMP_C,
    KEY_NORM_WIND_DIR_DEG,
    KEY_NORM_WIND_GUST_MS,
    KEY_NORM_WIND_SPEED_MS,
    KEY_PACKAGE_OK,
    KEY_SEA_LEVEL_PRESSURE_HPA,
    KEY_UV,
)
from custom_components.ws_core.weather import (
    WSStationWeather,
    _nowcast_blend,
    _weathercode_to_condition,
    async_setup_entry,
)


def test_nowcast_blend():
    assert _nowcast_blend(None, 20.0, 0.7) == 20.0
    assert _nowcast_blend(15.0, None, 0.7) == 15.0
    # 20 * 0.7 + 10 * 0.3 = 14 + 3 = 17.0
    assert _nowcast_blend(20.0, 10.0, 0.7) == 17.0


def test_weathercode_to_condition():
    assert _weathercode_to_condition(None) is None
    assert _weathercode_to_condition(0) == "sunny"
    assert _weathercode_to_condition(1) == "partlycloudy"
    assert _weathercode_to_condition(2) == "partlycloudy"
    assert _weathercode_to_condition(3) == "cloudy"
    assert _weathercode_to_condition(45) == "fog"
    assert _weathercode_to_condition(61) == "rainy"
    assert _weathercode_to_condition(71) == "snowy"
    assert _weathercode_to_condition(80) == "pouring"
    assert _weathercode_to_condition(85) == "snowy-rainy"
    assert _weathercode_to_condition(95) == "lightning-rainy"
    assert _weathercode_to_condition(999) is None


@pytest.fixture
def mock_coordinator():
    coord = MagicMock()
    coord.data = {
        KEY_PACKAGE_OK: True,
        KEY_NORM_TEMP_C: 22.5,
        KEY_NORM_HUMIDITY: 65.0,
        KEY_SEA_LEVEL_PRESSURE_HPA: 1015.2,
        KEY_NORM_WIND_SPEED_MS: 4.2,
        KEY_NORM_WIND_DIR_DEG: 180.0,
        KEY_NORM_WIND_GUST_MS: 7.5,
        KEY_DEW_POINT_C: 15.6,
        KEY_FEELS_LIKE_C: 23.0,
        KEY_UV: 5.0,
        KEY_CURRENT_CONDITION: "sunny",
        KEY_FORECAST: {
            "provider": "open-meteo",
            "daily": [
                {
                    "date": "2026-06-01",
                    "tmax_c": 25.0,
                    "tmin_c": 14.0,
                    "precip_mm": 0.0,
                    "precip_prob": 10,
                    "wind_kmh": 14.4,
                    "gust_kmh": 28.8,
                    "weathercode": 0,
                }
            ],
            "hourly": [
                {
                    "datetime": "2026-06-01T12:00",
                    "temp_c": 22.0,
                    "apparent_temp_c": 22.5,
                    "dewpoint_c": 15.0,
                    "humidity": 65.0,
                    "precip_prob": 5,
                    "precip_mm": 0.0,
                    "wind_kmh": 14.4,
                    "gust_kmh": 28.8,
                    "cloud_cover": 10,
                    "weathercode": 0,
                }
            ],
        },
    }
    return coord


@pytest.fixture
def mock_config_entry(mock_coordinator):
    entry = MagicMock()
    entry.entry_id = "test_entry_weather"
    entry.data = {CONF_PREFIX: "ws"}
    entry.options = {}
    entry.runtime_data = mock_coordinator
    return entry


async def test_async_setup_entry_creates_weather_entity(mock_config_entry, mock_coordinator):
    hass = MagicMock()
    added_entities = []

    def mock_add_entities(entities):
        added_entities.extend(entities)

    await async_setup_entry(hass, mock_config_entry, mock_add_entities)

    assert len(added_entities) == 1
    entity = added_entities[0]
    assert isinstance(entity, WSStationWeather)
    assert entity.entity_id == "weather.ws"
    assert entity.unique_id == "test_entry_weather_weather"


def test_weather_entity_properties(mock_config_entry, mock_coordinator):
    entity = WSStationWeather(mock_coordinator, mock_config_entry, "ws")

    assert entity.available is True
    assert entity.native_temperature == 22.5
    assert entity.humidity == 65.0
    assert entity.native_pressure == 1015.2
    assert entity.native_wind_speed == 4.2
    assert entity.wind_bearing == 180.0
    assert entity.native_wind_gust_speed == 7.5
    assert entity.native_dew_point == 15.6
    assert entity.native_apparent_temperature == 23.0
    assert entity.uv_index == 5.0
    assert entity.condition == "sunny"
    assert "Open-Meteo" in entity.attribution
    assert entity.device_info == {"identifiers": {(DOMAIN, "test_entry_weather")}}


def test_weather_condition_fallback(mock_config_entry, mock_coordinator):
    # Remove local condition
    mock_coordinator.data[KEY_CURRENT_CONDITION] = None
    entity = WSStationWeather(mock_coordinator, mock_config_entry, "ws")

    # Should fall back to hourly or daily weathercode
    assert entity.condition == "sunny"


async def test_weather_forecast_daily_and_hourly(mock_config_entry, mock_coordinator):
    entity = WSStationWeather(mock_coordinator, mock_config_entry, "ws")

    daily = await entity.async_forecast_daily()
    assert daily is not None
    assert len(daily) == 1
    assert daily[0]["temperature"] == 25.0
    assert daily[0]["templow"] == 14.0
    assert daily[0]["wind_speed"] == pytest.approx(4.0)  # 14.4 km/h -> 4.0 m/s
    assert daily[0]["native_wind_gust_speed"] == pytest.approx(8.0)  # 28.8 km/h -> 8.0 m/s
    assert daily[0]["condition"] == "sunny"

    hourly = await entity.async_forecast_hourly()
    assert hourly is not None
    assert len(hourly) == 1
    assert hourly[0]["temperature"] is not None
    assert hourly[0]["wind_speed"] is not None


def _sync_weather_units(entity, options, explicit):
    from types import SimpleNamespace
    from unittest.mock import patch

    entity.coordinator.explicit_units = MagicMock(return_value=explicit)
    entity.hass = MagicMock()
    entity.registry_entry = SimpleNamespace(options=options)
    reg = MagicMock()
    with (
        patch("homeassistant.helpers.entity_registry.async_get", return_value=reg),
        patch.object(WSStationWeather, "async_registry_entry_updated"),
    ):
        entity._async_sync_registry_units()
    return {c.args[1]: c.args[2] for c in reg.async_update_entity_options.call_args_list}


def test_weather_units_follow_ws_core_choice(mock_config_entry, mock_coordinator):
    """Imperial chosen in ws_core shows the weather entity in °F, not the HA default."""
    entity = WSStationWeather(mock_coordinator, mock_config_entry, "ws")
    writes = _sync_weather_units(entity, {}, {"temperature": "°F", "wind": "mph"})
    assert writes["weather"] == {"temperature_unit": "°F", "wind_speed_unit": "mph"}
    assert writes[DOMAIN] == {"weather_units": {"temperature_unit": "°F", "wind_speed_unit": "mph"}}


def test_weather_units_keep_user_choice_and_drop_ours(mock_config_entry, mock_coordinator):
    entity = WSStationWeather(mock_coordinator, mock_config_entry, "ws")
    options = {
        # temperature set by the user in HA, wind written earlier by ws_core
        "weather": {"temperature_unit": "°C", "wind_speed_unit": "mph"},
        DOMAIN: {"weather_units": {"wind_speed_unit": "mph"}},
    }
    # Back to full auto: ws_core removes only its own value.
    writes = _sync_weather_units(entity, options, {})
    assert writes["weather"] == {"temperature_unit": "°C"}
    assert writes[DOMAIN] == {"weather_units": {}}

    # Imperial again: the user's °C stays.
    writes = _sync_weather_units(entity, options, {"temperature": "°F", "wind": "km/h"})
    assert writes["weather"] == {"temperature_unit": "°C", "wind_speed_unit": "km/h"}
    assert writes[DOMAIN] == {"weather_units": {"wind_speed_unit": "km/h"}}


def test_weather_units_no_write_when_unchanged(mock_config_entry, mock_coordinator):
    entity = WSStationWeather(mock_coordinator, mock_config_entry, "ws")
    assert _sync_weather_units(entity, {}, {}) == {}
    options = {"weather": {"pressure_unit": "inHg"}, DOMAIN: {"weather_units": {"pressure_unit": "inHg"}}}
    assert _sync_weather_units(entity, options, {"pressure": "inHg"}) == {}
