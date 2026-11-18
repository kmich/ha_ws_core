"""Unit tests for the ws_core weather platform."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from homeassistant.util import dt as dt_util

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
                    "datetime": (dt_util.now() + timedelta(hours=1)).strftime("%Y-%m-%dT%H:00"),
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


def test_pre_storm_weather_condition_is_cloudy_not_lightning_rainy(mock_config_entry, mock_coordinator):
    """Issue #203: pre-storm (approaching storm, dry) must report cloudy, not lightning-rainy."""
    mock_coordinator.data[KEY_CURRENT_CONDITION] = "pre-storm"
    entity = WSStationWeather(mock_coordinator, mock_config_entry, "ws")
    assert entity.condition == "cloudy"


def test_all_local_conditions_mapped_to_valid_ha_weather_conditions():
    """All 31 conditions defined by ws_core must map to valid HA weather conditions."""
    import homeassistant.components.weather as w

    from custom_components.ws_core.algorithms import CONDITION_DESCRIPTIONS

    valid_ha_conditions = {
        getattr(w, k) for k in dir(w) if k.startswith("ATTR_CONDITION_") and k != "ATTR_CONDITION_CLASS"
    }

    local_map = WSStationWeather._LOCAL_CONDITION_MAP

    for cond in CONDITION_DESCRIPTIONS:
        assert cond in local_map, f"Condition '{cond}' is missing from _LOCAL_CONDITION_MAP"
        ha_cond = local_map[cond]
        assert ha_cond in valid_ha_conditions, f"Mapped condition '{ha_cond}' is not a valid HA weather condition"

    # Crucial safety assertions against false lightning/rain warnings
    assert local_map["pre-storm"] == "cloudy"
    assert local_map["severe-storm"] == "exceptional"
    assert local_map["hurricane"] == "exceptional"
    assert local_map["thunderstorm"] == "lightning-rainy"


async def test_weather_forecast_daily_and_hourly(mock_config_entry, mock_coordinator):
    entity = WSStationWeather(mock_coordinator, mock_config_entry, "ws")

    daily = await entity.async_forecast_daily()
    assert daily is not None
    assert len(daily) == 1
    assert daily[0]["native_temperature"] == 25.0
    assert daily[0]["native_templow"] == 14.0
    assert daily[0]["native_wind_speed"] == pytest.approx(4.0)  # 14.4 km/h -> 4.0 m/s
    assert daily[0]["native_wind_gust_speed"] == pytest.approx(8.0)  # 28.8 km/h -> 8.0 m/s
    assert daily[0]["condition"] == "sunny"

    hourly = await entity.async_forecast_hourly()
    assert hourly is not None
    assert len(hourly) == 1
    assert hourly[0]["native_temperature"] is not None
    assert hourly[0]["native_wind_speed"] is not None


async def test_nowcast_blending_uses_lead_time_not_row_count(mock_config_entry, mock_coordinator):
    now_hr = dt_util.now().replace(minute=0, second=0, microsecond=0)
    mock_coordinator.data[KEY_NORM_TEMP_C] = 30.0
    mock_coordinator.data[KEY_FORECAST] = {
        "provider": "open_meteo",
        "daily": [],
        "hourly": [
            # Tomorrow noon (~24h ahead): MUST NOT receive local 30°C blending
            {"datetime": (now_hr + timedelta(hours=24)).strftime("%Y-%m-%dT%H:00"), "temp_c": 0.0, "wind_kmh": 0.0}
        ],
    }
    entity = WSStationWeather(mock_coordinator, mock_config_entry, "ws")
    out = await entity.async_forecast_hourly()
    assert len(out) == 1
    assert out[0]["native_temperature"] == 0.0

    # Sparse hours: +1h blends with weight 0.4, +5h stays raw provider value
    mock_coordinator.data[KEY_FORECAST]["hourly"] = [
        {"datetime": (now_hr + timedelta(hours=1)).strftime("%Y-%m-%dT%H:00"), "temp_c": 10.0, "wind_kmh": 0.0},
        {"datetime": (now_hr + timedelta(hours=5)).strftime("%Y-%m-%dT%H:00"), "temp_c": 10.0, "wind_kmh": 0.0},
    ]
    out_sparse = await entity.async_forecast_hourly()
    assert out_sparse[0]["native_temperature"] == pytest.approx(18.0)  # 30*0.4 + 10*0.6
    assert out_sparse[1]["native_temperature"] == 10.0


async def test_weather_forecast_converts_in_imperial_and_metric(mock_config_entry, mock_coordinator):
    from homeassistant.util.unit_system import METRIC_SYSTEM, US_CUSTOMARY_SYSTEM

    now_hr = dt_util.now().replace(minute=0, second=0, microsecond=0)
    mock_coordinator.data[KEY_FORECAST] = {
        "provider": "open_meteo",
        "daily": [
            {
                "date": now_hr.strftime("%Y-%m-%d"),
                "tmax_c": 20.0,
                "tmin_c": 10.0,
                "precip_mm": 25.4,
                "wind_kmh": 36.0,  # 10 m/s
                "gust_kmh": 54.0,  # 15 m/s
                "weathercode": 0,
                "precip_prob": 20,
            }
        ],
        "hourly": [
            {
                "datetime": (now_hr + timedelta(hours=4)).strftime("%Y-%m-%dT%H:00"),
                "temp_c": 20.0,
                "apparent_temp_c": 21.0,
                "dewpoint_c": 10.0,
                "precip_mm": 2.54,
                "wind_kmh": 36.0,
                "gust_kmh": 54.0,
                "weathercode": 0,
            }
        ],
    }
    entity = WSStationWeather(mock_coordinator, mock_config_entry, "ws")
    entity.hass = MagicMock()
    entity.hass.config.units = US_CUSTOMARY_SYSTEM

    imp_daily = entity._convert_forecast(await entity.async_forecast_daily())
    assert imp_daily[0]["temperature"] == pytest.approx(68.0)
    assert imp_daily[0]["templow"] == pytest.approx(50.0)
    assert imp_daily[0]["precipitation"] == pytest.approx(1.0)
    assert imp_daily[0]["wind_speed"] == pytest.approx(22.37, abs=0.1)
    assert imp_daily[0]["wind_gust_speed"] == pytest.approx(33.55, abs=0.1)

    imp_hourly = entity._convert_forecast(await entity.async_forecast_hourly())
    assert imp_hourly[0]["apparent_temperature"] == pytest.approx(70.0, abs=0.5)
    assert imp_hourly[0]["dew_point"] == pytest.approx(50.0)

    entity.hass.config.units = METRIC_SYSTEM
    met_daily = entity._convert_forecast(await entity.async_forecast_daily())
    assert met_daily[0]["temperature"] == pytest.approx(20.0)
    assert met_daily[0]["wind_speed"] == pytest.approx(36.0, abs=0.1)


@pytest.mark.parametrize(
    ("provider_id", "expected_credit"),
    [
        ("open_meteo", "Open-Meteo"),
        ("met_no", "MET Norway"),
        ("nws_noaa", "NOAA"),
        ("openweathermap", "OpenWeatherMap"),
        ("pirate_weather", "Pirate Weather"),
        ("meteo_france", "Météo-France"),
        ("ha_weather_entity", "Home Assistant"),
    ],
)
def test_provider_attribution_covers_all_providers(mock_config_entry, mock_coordinator, provider_id, expected_credit):
    mock_coordinator.data[KEY_FORECAST] = {"provider": provider_id}
    entity = WSStationWeather(mock_coordinator, mock_config_entry, "ws")
    assert expected_credit in entity.attribution


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


async def test_hourly_forecast_repeated_dst_hour_blend_lead_times(mock_config_entry, mock_coordinator):
    from zoneinfo import ZoneInfo

    berlin = ZoneInfo("Europe/Berlin")
    old_tz = dt_util.get_default_time_zone()
    dt_util.set_default_time_zone(berlin)
    try:
        t0_utc = datetime(2026, 10, 25, 0, 0, tzinfo=UTC)  # 02:00+02:00 (first 02:00 CEST hour)
        t1_utc = datetime(2026, 10, 25, 1, 0, tzinfo=UTC)  # 02:00+01:00 (second 02:00 CET hour)
        t2_utc = datetime(2026, 10, 25, 2, 0, tzinfo=UTC)  # 03:00+01:00
        mock_coordinator.data[KEY_NORM_TEMP_C] = 20.0
        mock_coordinator.data[KEY_FORECAST] = {
            "provider": "met_no",
            "daily": [],
            "hourly": [
                {"datetime": "2026-10-25T02:00", "utc_datetime": t0_utc.isoformat(), "temp_c": 10.0, "wind_kmh": 0.0},
                {"datetime": "2026-10-25T02:00", "utc_datetime": t1_utc.isoformat(), "temp_c": 10.0, "wind_kmh": 0.0},
                {"datetime": "2026-10-25T03:00", "utc_datetime": t2_utc.isoformat(), "temp_c": 10.0, "wind_kmh": 0.0},
            ],
        }
        entity = WSStationWeather(mock_coordinator, mock_config_entry, "ws")

        with patch.object(dt_util, "now", return_value=t0_utc.astimezone(berlin)):
            out0 = await entity.async_forecast_hourly()
        assert [o["datetime"] for o in out0] == [
            "2026-10-25T02:00:00+02:00",
            "2026-10-25T02:00:00+01:00",
            "2026-10-25T03:00:00+01:00",
        ]
        # Lead hours in UTC: 0 (0.7*20+0.3*10=17.0), 1 (0.4*20+0.6*10=14.0), 2 (0.2*20+0.8*10=12.0)
        assert [o["native_temperature"] for o in out0] == pytest.approx([17.0, 14.0, 12.0])

        # During the second 02:00 hour (01:00Z = 02:00+01:00), 00:00Z (+02:00) is past and discarded
        with patch.object(dt_util, "now", return_value=t1_utc.astimezone(berlin)):
            out1 = await entity.async_forecast_hourly()
        assert [o["datetime"] for o in out1] == [
            "2026-10-25T02:00:00+01:00",
            "2026-10-25T03:00:00+01:00",
        ]
        assert [o["native_temperature"] for o in out1] == pytest.approx([17.0, 14.0])
    finally:
        dt_util.set_default_time_zone(old_tz)
