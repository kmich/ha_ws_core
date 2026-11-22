"""Regression tests for v3.0.0 issue fixes (#209, #210, #212, #213, #214)."""

from __future__ import annotations

import json
import pathlib
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.util.unit_system import METRIC_SYSTEM, US_CUSTOMARY_SYSTEM

from custom_components.ws_core import const as c
from custom_components.ws_core.algorithms import (
    BEAUFORT_KEYS,
    beaufort_key,
    calculate_apparent_temperature,
    calculate_european_aqi,
    european_aqi_color,
    european_aqi_level,
    is_european_location,
    resolve_aqi_scale,
)
from custom_components.ws_core.config_flow import _guess_climate_region
from custom_components.ws_core.entity_descriptions import SENSORS
from custom_components.ws_core.providers import HaWeatherEntityProvider
from custom_components.ws_core.sensor import WSDataStatusSensor, WSSensor, async_setup_entry
from custom_components.ws_core.sensor_status import unknown_status
from custom_components.ws_core.weather import WSStationWeather, _weathercode_to_condition
from tests.test_coordinator import _make_coordinator
from tests.test_health_solar_regression import _full_coord
from tests.test_providers import _ha_entity_hass

# ---------------------------------------------------------------------------
# Issue #209 — Alert debounce, hysteresis deadbands, stable alert_message
# ---------------------------------------------------------------------------


class TestAlertDebounceAndStability:
    def test_clear_debounce_holds_alert_for_three_ticks_after_clearing(self):
        coord = _make_coordinator()
        coord.hass.config.language = "en"
        now = datetime(2026, 11, 22, 8, 0, tzinfo=UTC)

        # Two ticks at -0.5 °C fire freeze advisory
        for i in range(2):
            data = {c.KEY_NORM_TEMP_C: -0.5}
            coord._compute_health(data, now + timedelta(minutes=i), [], [], sample=True)
        assert data[c.KEY_ALERT_STATE] == "advisory"
        assert data[c.KEY_ALERT_MESSAGE] == "Freeze risk"

        # Temperature jumps well above +0.5 °C deadband: must stay active for 2 off-ticks
        for i in (2, 3):
            data = {c.KEY_NORM_TEMP_C: 2.0}
            coord._compute_health(data, now + timedelta(minutes=i), [], [], sample=True)
            assert data[c.KEY_ALERT_STATE] == "advisory"
            assert data[c.KEY_ALERT_MESSAGE] == "Freeze risk"
            assert len(data["_active_alerts"]) == 1
            assert "2.0" in data["_alert_detail_message"]

        # Third clear tick turns the alert off
        data = {c.KEY_NORM_TEMP_C: 2.0}
        coord._compute_health(data, now + timedelta(minutes=4), [], [], sample=True)
        assert data[c.KEY_ALERT_STATE] == "clear"
        assert data[c.KEY_ALERT_MESSAGE] == "All clear"
        assert data["_active_alerts"] == []

    def test_freeze_hysteresis_deadband_holds_between_zero_and_half_degree(self):
        coord = _make_coordinator()
        coord.hass.config.language = "en"
        now = datetime(2026, 11, 22, 8, 0, tzinfo=UTC)

        for i in range(2):
            data = {c.KEY_NORM_TEMP_C: -0.2}
            coord._compute_health(data, now + timedelta(minutes=i), [], [], sample=True)
        assert data[c.KEY_ALERT_STATE] == "advisory"

        # Hovering at +0.3 °C (<= 0.0 + 0.5) keeps the freeze alert active indefinitely
        for i in range(2, 12):
            data = {c.KEY_NORM_TEMP_C: 0.3}
            coord._compute_health(data, now + timedelta(minutes=i), [], [], sample=True)
            assert data[c.KEY_ALERT_STATE] == "advisory"

        # Above +0.5 °C clears after ALERT_DEBOUNCE_OFF_TICKS = 3
        for i in range(12, 15):
            data = {c.KEY_NORM_TEMP_C: 0.6}
            coord._compute_health(data, now + timedelta(minutes=i), [], [], sample=True)
        assert data[c.KEY_ALERT_STATE] == "clear"

    def test_wind_and_rain_hysteresis_and_low_threshold_clear(self):
        coord = _make_coordinator()
        coord.hass.config.language = "en"
        now = datetime(2026, 11, 22, 9, 0, tzinfo=UTC)

        # Default wind threshold 17.0 m/s -> deadband clears below 15.5 m/s
        for i in range(2):
            data = {c.KEY_NORM_WIND_GUST_MS: 18.0, c.KEY_RAIN_RATE_FILT: 11.0}
            coord._compute_health(data, now + timedelta(minutes=i), [], [], sample=True)
        assert data[c.KEY_ALERT_STATE] == "warning"
        assert data[c.KEY_ALERT_MESSAGE] == "Extreme wind | Heavy rain"

        # 16.0 m/s wind and 9.5 mm/h rain remain inside hysteresis deadbands
        for i in range(2, 8):
            data = {c.KEY_NORM_WIND_GUST_MS: 16.0, c.KEY_RAIN_RATE_FILT: 9.5}
            coord._compute_health(data, now + timedelta(minutes=i), [], [], sample=True)
        assert data[c.KEY_ALERT_MESSAGE] == "Extreme wind | Heavy rain"

        # Low custom threshold (1.0 m/s) clears cleanly at 0.0 m/s (max(0.1, thr - 1.5))
        coord2 = _make_coordinator()
        coord2.entry_options = {c.CONF_THRESH_WIND_GUST_MS: 1.0}
        for i in range(2):
            coord2._compute_health({c.KEY_NORM_WIND_GUST_MS: 1.5}, now + timedelta(minutes=i), [], [], sample=True)
        for i in range(2, 5):
            d2 = {c.KEY_NORM_WIND_GUST_MS: 0.0}
            coord2._compute_health(d2, now + timedelta(minutes=i), [], [], sample=True)
        assert d2[c.KEY_ALERT_STATE] == "clear"

    def test_alert_message_state_stable_while_temperature_fluctuates(self):
        coord = _make_coordinator()
        coord.hass.config.language = "de"
        now = datetime(2026, 11, 22, 8, 0, tzinfo=UTC)

        states_seen = set()
        details_seen = []
        for idx, tc in enumerate((-0.1, -0.4, -0.8, -0.2, 0.1)):
            data = {c.KEY_NORM_TEMP_C: tc}
            coord._compute_health(data, now + timedelta(minutes=idx), [], [], sample=True)
            if idx >= 1:
                states_seen.add(data[c.KEY_ALERT_MESSAGE])
                details_seen.append(data["_alert_detail_message"])

        assert states_seen == {"Frostgefahr"}
        assert len(set(details_seen)) == 4

        # Verify WSSensor exposes detail_message and active_alerts on alert_message & alert_state
        coord.data = data
        msg_desc = next(d for d in SENSORS if d.key == c.KEY_ALERT_MESSAGE)
        state_desc = next(d for d in SENSORS if d.key == c.KEY_ALERT_STATE)
        msg_ent = WSSensor(coord, MagicMock(entry_id="e"), msg_desc, "ws")
        state_ent = WSSensor(coord, MagicMock(entry_id="e"), state_desc, "ws")
        assert msg_ent.extra_state_attributes["detail_message"] == data["_alert_detail_message"]
        assert len(msg_ent.extra_state_attributes["active_alerts"]) == 1
        assert state_ent.extra_state_attributes["detail_message"] == data["_alert_detail_message"]

    def test_sample_false_does_not_drop_active_alert(self):
        coord = _make_coordinator()
        coord.hass.config.language = "en"
        now = datetime(2026, 11, 22, 8, 0, tzinfo=UTC)
        for i in range(2):
            coord._compute_health({c.KEY_NORM_TEMP_C: -1.0}, now + timedelta(minutes=i), [], [], sample=True)
        inter = {c.KEY_NORM_TEMP_C: 3.0}
        coord._compute_health(inter, now + timedelta(minutes=2), [], [], sample=False)
        assert inter[c.KEY_ALERT_STATE] == "advisory"
        assert inter[c.KEY_ALERT_MESSAGE] == "Freeze risk"


class TestFrostRisk:
    """Follow-up on #209 / #211: frost risk threshold, forecast low, hysteresis, debounce."""

    NOW = datetime(2026, 11, 22, 18, 0, tzinfo=UTC)

    def _run(self, coord, tc, forecast=None, sample=True):
        data = {c.KEY_FORECAST: forecast} if forecast is not None else {}
        coord._compute_frost_risk(data, tc, sample=sample, now=self.NOW)
        return data

    def test_reads_tmin_c_and_prefers_next_12h_hourly_min(self):
        coord = _make_coordinator()
        coord.entry_options = {}
        # Daily low under the normalized key tmin_c (the old code read "templow")
        data = self._run(coord, 8.0, {"daily": [{"tmax_c": 12.0, "tmin_c": -1.0}], "hourly": []})
        assert data[c.KEY_FROST_RISK] == "high"
        assert data["_frost_risk_forecast_min_c"] == -1.0
        assert data["_frost_risk_min_temp_c"] == -1.0

        # Hourly window (next 12 h) wins over a daily low that already happened this morning
        coord2 = _make_coordinator()
        coord2.entry_options = {}
        hourly = [
            {"utc_datetime": (self.NOW + timedelta(hours=h)).isoformat(), "temp_c": 6.0 - 0.1 * h} for h in range(24)
        ]
        hourly[20]["temp_c"] = -5.0  # outside the 12 h window
        fc = {"daily": [{"tmax_c": 12.0, "tmin_c": -1.0}], "hourly": hourly}
        data2 = self._run(coord2, 8.0, fc)
        assert data2["_frost_risk_forecast_min_c"] == pytest.approx(4.9)
        assert data2[c.KEY_FROST_RISK] == "no_risk"  # not "high" from this morning's -1 °C

        # Daily high is never used as a "low"
        coord3 = _make_coordinator()
        coord3.entry_options = {}
        data3 = self._run(coord3, 8.0, {"daily": [{"tmax_c": 1.0, "tmin_c": None}]})
        assert data3["_frost_risk_forecast_min_c"] is None
        assert data3[c.KEY_FROST_RISK] == "no_risk"

    @pytest.mark.parametrize(
        ("tc", "expected"),
        [(1.0, "high"), (2.9, "probable"), (3.0, "probable"), (5.0, "unlikely"), (5.1, "no_risk")],
    )
    def test_tiers_follow_freeze_threshold(self, tc, expected):
        coord = _make_coordinator()
        coord.entry_options = {c.CONF_THRESH_FREEZE_C: 1.0}
        data = self._run(coord, tc)
        assert data[c.KEY_FROST_RISK] == expected
        assert data["_frost_risk_threshold_c"] == 1.0

    def test_hysteresis_and_debounce(self):
        coord = _make_coordinator()
        coord.entry_options = {}
        assert self._run(coord, 1.8)[c.KEY_FROST_RISK] == "probable"  # first reading seeds

        # Inside the +0.5 °C deadband: holds probable indefinitely
        for _ in range(6):
            assert self._run(coord, 2.3)[c.KEY_FROST_RISK] == "probable"

        # Above the deadband: 3 ticks to step down; burst updates do not count
        assert self._run(coord, 2.6)[c.KEY_FROST_RISK] == "probable"
        assert self._run(coord, 2.6, sample=False)[c.KEY_FROST_RISK] == "probable"
        assert self._run(coord, 2.6)[c.KEY_FROST_RISK] == "probable"
        assert self._run(coord, 2.6)[c.KEY_FROST_RISK] == "unlikely"

        # Escalation needs 2 ticks
        assert self._run(coord, 1.9)[c.KEY_FROST_RISK] == "unlikely"
        assert self._run(coord, 1.9, sample=False)[c.KEY_FROST_RISK] == "unlikely"
        assert self._run(coord, 1.9)[c.KEY_FROST_RISK] == "probable"

        # A single dip does not escalate; returning resets the pending counter
        assert self._run(coord, -0.5)[c.KEY_FROST_RISK] == "probable"
        assert self._run(coord, 1.5)[c.KEY_FROST_RISK] == "probable"
        assert self._run(coord, -0.5)[c.KEY_FROST_RISK] == "probable"

    def test_sensor_is_enum_with_attributes(self):
        desc = next(d for d in SENSORS if d.key == c.KEY_FROST_RISK)
        assert desc.device_class == SensorDeviceClass.ENUM
        assert desc.options == ["no_risk", "unlikely", "probable", "high"]
        coord = _make_coordinator()
        coord.entry_options = {}
        data = self._run(coord, 1.0, {"daily": [{"tmin_c": -2.0}]})
        data[c.KEY_FROST_POINT_C] = -3.4
        coord.data = data
        ent = WSSensor(coord, MagicMock(entry_id="e"), desc, "ws")
        attrs = ent.extra_state_attributes
        assert attrs["min_temp_c"] == -2.0
        assert attrs["forecast_min_c"] == -2.0
        assert attrs["threshold_c"] == 0.0
        assert attrs["frost_point_c"] == -3.4

    def test_missing_sample_resets_pending_frost_risk_change(self):
        coord = _make_coordinator()
        assert self._run(coord, 4.1)[c.KEY_FROST_RISK] == "no_risk"
        assert self._run(coord, 1.9)[c.KEY_FROST_RISK] == "no_risk"
        assert c.KEY_FROST_RISK not in self._run(coord, None)
        assert self._run(coord, -0.1)[c.KEY_FROST_RISK] == "no_risk"
        assert self._run(coord, -0.1)[c.KEY_FROST_RISK] == "high"

    def test_frost_risk_only_moves_to_a_tier_supported_across_the_run(self):
        coord = _make_coordinator()
        assert self._run(coord, 4.1)[c.KEY_FROST_RISK] == "no_risk"
        assert self._run(coord, 1.9)[c.KEY_FROST_RISK] == "no_risk"
        assert self._run(coord, -0.1)[c.KEY_FROST_RISK] == "probable"
        assert self._run(coord, -0.1)[c.KEY_FROST_RISK] == "probable"
        assert self._run(coord, -0.1)[c.KEY_FROST_RISK] == "high"
        assert self._run(coord, 1.0)[c.KEY_FROST_RISK] == "high"
        assert self._run(coord, 5.0)[c.KEY_FROST_RISK] == "high"
        assert self._run(coord, 5.0)[c.KEY_FROST_RISK] == "probable"


# ---------------------------------------------------------------------------
# Issue #210 — Localization, Beaufort enum sensor, translation sweep
# ---------------------------------------------------------------------------


class TestBeaufortAndTranslations:
    def test_beaufort_key_and_localized_description(self):
        assert beaufort_key(-1) == "calm"
        assert beaufort_key(4) == "moderate_breeze"
        assert beaufort_key(99) == "hurricane"

        coord = _make_coordinator()
        coord.hass.config.language = "de"
        data: dict = {}
        coord._compute_derived_wind(data, datetime.now(UTC), wind_ms=6.0, gust_ms=8.0, wind_dir=180.0, sample=True)
        assert data[c.KEY_WIND_BEAUFORT] == 4
        assert data[c.KEY_WIND_BEAUFORT_DESC] == "Mäßige Brise"
        assert data[c.KEY_WIND_BEAUFORT_KEY] == "moderate_breeze"

    def test_beaufort_description_enum_sensor_created(self):
        coord = MagicMock()
        coord.sources = {}
        coord._pattern = None
        entry = MagicMock(entry_id="bft_test", data={c.CONF_SOURCES: {}}, options={})
        added = []
        setup = async_setup_entry(MagicMock(), entry, added.extend)
        with pytest.raises(StopIteration):
            setup.send(None)
        bft_desc_ent = next(e for e in added if isinstance(e, WSSensor) and e._desc.key == c.KEY_WIND_BEAUFORT_KEY)
        assert bft_desc_ent.entity_id == "sensor.ws_wind_beaufort_description"
        assert bft_desc_ent.device_class == SensorDeviceClass.ENUM
        assert bft_desc_ent.options == list(BEAUFORT_KEYS)

    def test_new_keys_and_entity_names_translated_in_all_languages(self):
        base = pathlib.Path("custom_components/ws_core/translations")
        en = json.loads((base / "en.json").read_text(encoding="utf-8"))
        allowed_identical = {
            "sensor.humidex",
            "sensor.delta_t",
            "sensor.pm10",
            "sensor.wbgt",
            "sensor.utci",
            "sensor.indoor_room_co2",
            "sensor.ozone",  # French
            "sensor.indoor_room_comfort",  # IT / NL loanword
        }
        for lang in ("fr", "de", "es", "it", "nl", "pl", "pt"):
            tr = json.loads((base / f"{lang}.json").read_text(encoding="utf-8"))
            bft = tr["entity"]["sensor"]["wind_beaufort_description"]
            assert set(bft["state"]) == set(BEAUFORT_KEYS)
            assert all(bft["state"].values())
            assert set(tr["selector"]["aqi_scale"]["options"]) == {"auto", "european", "us"}
            assert tr["entity"]["sensor"]["aqi"]["state_attributes"]["scale"]["state"]
            assert tr["entity"]["sensor"]["forecast_agreement"]["state_attributes"]["comparison_window"]["state"]

            for dom, items in en["entity"].items():
                for ek, ev in items.items():
                    if isinstance(ev, dict) and "name" in ev and f"{dom}.{ek}" not in allowed_identical:
                        assert tr["entity"][dom][ek]["name"] != ev["name"], (lang, dom, ek)


# ---------------------------------------------------------------------------
# Issues #212 & #213 — ha_weather_entity provider, weather.py, sensor_status
# ---------------------------------------------------------------------------


class TestHaWeatherEntityFixes:
    def test_wmo_68_69_map_to_snowy_rainy(self):
        assert _weathercode_to_condition(68) == "snowy-rainy"
        assert _weathercode_to_condition(69) == "snowy-rainy"

    @pytest.mark.asyncio
    async def test_preserves_conditions_full_horizon_extra_fields_and_attribution(self):
        now = datetime(2026, 11, 22, 12, 0, tzinfo=UTC)
        daily_rows = [
            {
                "datetime": (now + timedelta(days=i)).isoformat(),
                "temperature": 5.0 + i,
                "templow": -1.0,
                "precipitation": 5.1,
                "wind_speed": 18.0,
                "wind_gust_speed": 30.0,
                "condition": cond,
                "cloud_coverage": 80,
                "humidity": 88,
                "pressure": 29.92,  # inHg -> ~1013.21 hPa
                "visibility": 10.0,  # mi -> ~16.09 km
                "uv_index": 2.0,
                "wind_bearing": 240,
            }
            for i, cond in enumerate(
                [
                    "snowy-rainy",
                    "pouring",
                    "exceptional",
                    "lightning",
                    "hail",
                    "windy",
                    "cloudy",
                    "sunny",
                    "rainy",
                ]
            )
        ]
        hourly_rows = [
            {
                "datetime": (now + timedelta(hours=i)).isoformat(),
                "temperature": 6.0,
                "humidity": 80,
                "wind_speed": 14.4,  # 4 m/s
                "condition": "snowy-rainy" if i == 0 else "pouring",
                "pressure": 29.92,
                "visibility": 5.0,
                "uv_index": 1.0,
                "wind_bearing": 180,
            }
            for i in range(216)
        ]
        hass = _ha_entity_hass(
            {
                "temperature_unit": "°C",
                "wind_speed_unit": "km/h",
                "precipitation_unit": "mm",
                "pressure_unit": "inHg",
                "visibility_unit": "mi",
                "attribution": "Data provided by DWD",
                "friendly_name": "DWD Munich",
            },
            daily_rows,
            hourly_rows,
        )
        with patch("custom_components.ws_core.providers.ha_weather_entity.dt_util.utcnow", return_value=now):
            fc = await HaWeatherEntityProvider(hass).async_fetch(MagicMock(), 48.1, 11.6, api_key="weather.dwd")

        assert len(fc["daily"]) == 9
        assert len(fc["hourly"]) == 216
        assert fc["source_attribution"] == "Data provided by DWD"
        assert fc["daily"][0]["condition"] == "snowy-rainy"
        assert fc["daily"][0]["pressure_hpa"] == pytest.approx(1013.21, abs=0.1)
        assert fc["daily"][0]["visibility_km"] == pytest.approx(16.09, abs=0.1)
        # Missing apparent_temperature is derived from T/RH/wind
        expected_at = calculate_apparent_temperature(6.0, 80.0, 4.0)
        assert fc["hourly"][10]["apparent_temp_c"] == pytest.approx(expected_at, abs=0.05)

        coord = MagicMock()
        coord.data = {c.KEY_CURRENT_CONDITION: "cloudy", c.KEY_FORECAST: fc}
        entry = MagicMock(entry_id="e", data={c.CONF_PREFIX: "ws"}, options={})
        w = WSStationWeather(coord, entry, "ws")
        w.hass = MagicMock()
        w.hass.config.units = US_CUSTOMARY_SYSTEM
        assert w.attribution.endswith("Data provided by DWD")

        daily_out = await w.async_forecast_daily()
        assert len(daily_out) == 9
        assert [d["condition"] for d in daily_out[:6]] == [
            "snowy-rainy",
            "pouring",
            "exceptional",
            "lightning",
            "hail",
            "windy",
        ]
        assert daily_out[0]["cloud_coverage"] == 80
        assert daily_out[0]["humidity"] == 88
        assert daily_out[0]["native_pressure"] == pytest.approx(1013.21, abs=0.1)
        assert w._convert_forecast(daily_out)[0]["visibility"] == 10.0
        assert daily_out[0]["uv_index"] == 2.0
        assert daily_out[0]["wind_bearing"] == 240
        assert daily_out[0][ATTR_ATTRIBUTION] == w.attribution

        with patch("custom_components.ws_core.weather.dt_util.now", return_value=now):
            hourly_out = await w.async_forecast_hourly()
        assert len(hourly_out) == 216
        assert hourly_out[10]["native_apparent_temperature"] == pytest.approx(expected_at, abs=0.05)
        assert hourly_out[10]["condition"] == "pouring"
        assert w._convert_forecast(hourly_out)[10]["visibility"] == 5.0

        w.hass.config.units = METRIC_SYSTEM
        assert w._convert_forecast(await w.async_forecast_daily())[0]["visibility"] == 16.09
        with patch("custom_components.ws_core.weather.dt_util.now", return_value=now):
            assert w._convert_forecast(await w.async_forecast_hourly())[10]["visibility"] == 8.05

        # weather.py also derives missing apparent_temperature when a forecast row omits it
        coord.data = {
            c.KEY_CURRENT_CONDITION: "cloudy",
            c.KEY_FORECAST: {
                "provider": "open_meteo",
                "hourly": [
                    {
                        "utc_datetime": (now + timedelta(hours=4)).isoformat(),
                        "temp_c": 6.0,
                        "humidity": 80,
                        "wind_kmh": 14.4,
                        "apparent_temp_c": None,
                    }
                ],
                "daily": [],
            },
        }
        with patch("custom_components.ws_core.weather.dt_util.now", return_value=now):
            derived_hourly = await w.async_forecast_hourly()
        assert derived_hourly[0]["native_apparent_temperature"] == pytest.approx(expected_at, abs=0.05)

    def test_forecast_agreement_missing_precip_prob_reason_and_data_status(self):
        co = SimpleNamespace(sources={}, forecast_enabled=True)
        info = unknown_status(
            c.KEY_FORECAST_AGREEMENT,
            co,
            {c.KEY_ZAMBRETTI_NUMBER: 10, "_forecast_agreement_reason": "provider_missing_precip_prob"},
        )
        assert info["reason"] == "provider_missing_precip_prob"
        assert "precipitation probability" in info["explanation"]

        # WSDataStatusSensor classifies provider_missing_precip_prob under not_on_this_station
        coord = MagicMock()
        coord.sources = {}
        coord.forecast_enabled = True
        coord.data = {
            c.KEY_SOURCE_PROBLEMS: [],
            c.KEY_ZAMBRETTI_NUMBER: 10,
            "_forecast_agreement_reason": "provider_missing_precip_prob",
        }
        entry = MagicMock(entry_id="ds_test", data={c.CONF_SOURCES: {}}, options={})
        desc = next(d for d in SENSORS if d.key == c.KEY_FORECAST_AGREEMENT)
        ds = WSDataStatusSensor(coord, entry, "ws", [desc])
        ds.hass = SimpleNamespace(states=SimpleNamespace(get=lambda eid: None))
        reg = SimpleNamespace(
            async_get_entity_id=lambda dom, plat, uid: "sensor.ws_forecast_agreement" if dom == "sensor" else None,
            async_get=lambda eid: SimpleNamespace(disabled_by=None),
        )
        with patch("custom_components.ws_core.sensor.er.async_get", return_value=reg):
            attrs = ds.extra_state_attributes
        assert "sensor.ws_forecast_agreement" in attrs["not_on_this_station"]


# ---------------------------------------------------------------------------
# Issue #214 — Forecast agreement 12h hourly basis, Central Europe, EAQI/US AQI
# ---------------------------------------------------------------------------


class TestIssue214ZambrettiAndAqi:
    def test_forecast_agreement_prefers_next_12h_hourly_max_over_daily(self):
        coord = _make_coordinator()
        coord.forecast_enabled = True
        now = datetime(2026, 11, 22, 18, 0, tzinfo=UTC)
        coord.runtime.last_forecast_fetch = now - timedelta(minutes=10)
        # Morning rain made today's daily precip_prob=90%, but next 12h are dry (10%)
        coord._forecast_cache = {
            "provider": "open_meteo",
            "daily": [{"date": "2026-11-22", "tmax_c": 10.0, "tmin_c": 3.0, "precip_prob": 90}],
            "hourly": [
                {"utc_datetime": (now + timedelta(hours=h)).isoformat(), "precip_prob": 10} for h in range(1, 12)
            ],
        }
        data = {c.KEY_ZAMBRETTI_NUMBER: 2}  # Z=2 -> 10% rain
        coord._compute_forecast_agreement(data, now=now)
        assert data[c.KEY_FORECAST_AGREEMENT] == "aligned"
        assert data["_forecast_agreement_basis"] == "hourly_12h"
        assert data["_forecast_agreement_api_precip_prob"] == 10

        # Without hourly probs, falls back to daily
        coord._forecast_cache["hourly"] = []
        data_daily = {c.KEY_ZAMBRETTI_NUMBER: 2}
        coord._compute_forecast_agreement(data_daily, now=now)
        assert data_daily[c.KEY_FORECAST_AGREEMENT] == "conflict"
        assert data_daily["_forecast_agreement_basis"] == "daily"

        # Without any precip_prob, leaves state absent and sets diagnostic reason
        coord._forecast_cache["daily"][0]["precip_prob"] = None
        data_missing = {c.KEY_ZAMBRETTI_NUMBER: 2}
        coord._compute_forecast_agreement(data_missing, now=now)
        assert c.KEY_FORECAST_AGREEMENT not in data_missing
        assert data_missing["_forecast_agreement_reason"] == "provider_missing_precip_prob"

    @pytest.mark.parametrize(
        ("lat", "lon", "expected"),
        [
            (48.14, 11.58, "continental_europe"),  # Munich
            (52.52, 13.40, "continental_europe"),  # Berlin
            (48.21, 16.37, "continental_europe"),  # Vienna
            (51.51, -0.13, "atlantic_europe"),  # London
            (48.86, 2.35, "atlantic_europe"),  # Paris
            (52.37, 4.90, "atlantic_europe"),  # Amsterdam
        ],
    )
    def test_guess_climate_region_central_europe(self, lat, lon, expected):
        hass = SimpleNamespace(config=SimpleNamespace(latitude=lat, longitude=lon))
        assert _guess_climate_region(hass) == expected

    def test_european_aqi_calculation_and_scale_auto_detection(self):
        assert is_european_location(48.14, 11.58) is True  # Munich
        assert is_european_location(40.71, -74.01) is False  # New York
        assert resolve_aqi_scale("auto", 48.14, 11.58) == "european"
        assert resolve_aqi_scale("auto", 40.71, -74.01) == "us"
        assert resolve_aqi_scale("us", 48.14, 11.58) == "us"
        assert resolve_aqi_scale("european", 40.71, -74.01) == "european"

        # Low pollutants -> Good (<= 20)
        val_good = calculate_european_aqi(pm2_5=5.0, pm10=10.0, no2=10.0, ozone=40.0)
        assert val_good is not None and val_good <= 20
        assert european_aqi_level(val_good) == "good"
        assert european_aqi_color(val_good) == "#50F0E6"

        # Elevated NO2/O3 drives EAQI even if PM is low
        val_no2 = calculate_european_aqi(pm2_5=4.0, pm10=8.0, no2=100.0, ozone=40.0)
        assert val_no2 == 80
        assert european_aqi_level(val_no2) == "poor"

    @pytest.mark.parametrize(
        ("pollutants", "index"),
        [
            ({"pm2_5": 9.0}, 28),
            ({"pm10": 120.0}, 60),
            ({"ozone": 61.0}, 21),
            ({"ozone": 160.0}, 80),
            ({"so2": 275.0}, 100),
            ({"so2": 360.0}, 120),
            ({"pm2_5": float("nan"), "so2": -1.0}, None),
        ],
    )
    def test_european_aqi_revised_thresholds(self, pollutants, index):
        assert calculate_european_aqi(**({"pm2_5": None, "pm10": None} | pollutants)) == index

    @pytest.mark.asyncio
    async def test_coordinator_fetch_aqi_auto_european_and_fallback(self):
        coord = _full_coord()
        coord.async_request_refresh = AsyncMock()
        coord.aqi_enabled = True
        coord.pollen_enabled = False
        coord.aqi_scale = "auto"
        coord.forecast_lat = 48.14
        coord.forecast_lon = 11.58

        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(
            return_value={
                "current": {
                    "pm2_5": 6.0,
                    "pm10": 12.0,
                    "nitrogen_dioxide": 30.0,
                    "ozone": 60.0,
                    "carbon_monoxide": 200.0,
                    "european_aqi": 24,
                    "us_aqi": 33,
                }
            }
        )
        cm = AsyncMock()
        cm.__aenter__.return_value = mock_resp
        cm.__aexit__.return_value = None
        session = MagicMock()
        session.get.return_value = cm

        with patch("custom_components.ws_core.coordinator.async_get_clientsession", return_value=session):
            await coord._async_fetch_aqi()

        assert coord._aqi_cache["aqi"] == 24
        assert coord._aqi_cache["aqi_scale"] == "european"
        assert coord._aqi_cache["aqi_level"] == "fair"
        assert coord._aqi_cache["aqi_color"] == "#50CCAA"
        assert coord._aqi_cache["aqi_source"] == "open_meteo"
        assert "sulphur_dioxide" in session.get.call_args.args[0]

        # Without Open-Meteo's european_aqi field, falls back to local EAQI calculation
        mock_resp.json = AsyncMock(
            return_value={"current": {"pm2_5": 6.0, "sulphur_dioxide": 232.5, "european_aqi": float("inf")}}
        )
        with patch("custom_components.ws_core.coordinator.async_get_clientsession", return_value=session):
            await coord._async_fetch_aqi()
        assert coord._aqi_cache["aqi_scale"] == "european"
        assert coord._aqi_cache["aqi"] == 90
        assert coord._aqi_cache["aqi_level"] == "very_poor"
        assert coord._aqi_cache["aqi_color"] == "#960032"
        assert coord._aqi_cache["aqi_source"] == "local_estimate"
        assert coord._aqi_cache["missing_pollutants"] == ["pm10", "no2", "ozone"]
        coord.data = coord._compute(sample=False)
        desc = next(d for d in SENSORS if d.key == c.KEY_AQI)
        attrs = WSSensor(coord, MagicMock(entry_id="e"), desc, "ws").extra_state_attributes
        assert attrs["scale"] == "european"
        assert attrs["source"] == "local_estimate"
        assert attrs["missing_pollutants"] == ["pm10", "no2", "ozone"]
        assert attrs["so2_ug_m3"] == 232.5
        assert attrs["color"] == "#960032"

        # Explicit US override outside or inside Europe uses US EPA scale
        coord.aqi_scale = "us"
        mock_resp.json = AsyncMock(return_value={"current": {"pm2_5": 9.0, "pm10": 15.0, "us_aqi": 50}})
        with patch("custom_components.ws_core.coordinator.async_get_clientsession", return_value=session):
            await coord._async_fetch_aqi()
        assert coord._aqi_cache["aqi"] == 50
        assert coord._aqi_cache["aqi_scale"] == "us"
        assert coord._aqi_cache["aqi_level"] == "good"
