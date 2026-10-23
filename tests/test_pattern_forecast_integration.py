"""Integration-layer tests for Pattern Forecast (wiring, labelling, storm source, flows)."""

from __future__ import annotations

import asyncio
import inspect
import json
import pathlib
import re
import time
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest

from custom_components.ws_core import const, pattern_runtime, pattern_sources
from custom_components.ws_core.const import (
    CONF_ENABLE_PATTERN_FORECAST,
    CONF_PATTERN_STORM_INTERNET_LIGHTNING,
    DEPRECATED_KEYS_FORECASTER,
    KEY_DEW_POINT_C,
    KEY_NORM_PRESSURE_HPA,
    KEY_NORM_RAIN_TOTAL_MM,
    KEY_NORM_TEMP_C,
    KEY_NORM_WIND_DIR_DEG,
    KEY_NORM_WIND_GUST_MS,
    KEY_NORM_WIND_SPEED_MS,
    KEY_PATTERN_FORECAST_SKILL,
    KEY_PATTERN_FORECAST_STATUS,
    KEY_PATTERN_STORM_3H,
    PATTERN_TARGET_KEYS,
    SRC_LIGHTNING_COUNT,
    SRC_LIGHTNING_DISTANCE,
)
from custom_components.ws_core.pattern_forecast import FACTOR_KEYS, TARGETS, Thresholds

COMPONENT = pathlib.Path(const.__file__).parent
LANGS = ("de", "en", "es", "fr", "it", "nl", "pl", "pt")


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def make_coord(options: dict | None = None, sources: dict | None = None, states: dict | None = None):
    """Real WSStationCoordinator.__init__ with a MagicMock hass (see TestEntryOptionsMerge)."""
    from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

    from custom_components.ws_core.coordinator import WSStationCoordinator

    hass = MagicMock()
    table = states if states is not None else {}

    def get(eid):
        return table.get(eid)

    hass.states.get = get
    hass.config.latitude = 38.0
    hass.config.longitude = 23.7
    data = {"entry_id": "abc", "sources": dict(sources or {}), **(options or {})}
    with patch.object(DataUpdateCoordinator, "__init__", lambda self, *a, **kw: None):
        coord = WSStationCoordinator(hass, data, {})
    return coord, table


def state(value, **attrs):
    return SimpleNamespace(state=str(value), attributes=attrs, last_updated=datetime.now(UTC))


class FakeRegistry:
    def __init__(self, *entries):
        self.entities = {e.entity_id: e for e in entries}


def reg_entry(entity_id, platform="blitzortung", unique_id="x", disabled_by=None):
    return SimpleNamespace(
        entity_id=entity_id,
        platform=platform,
        unique_id=unique_id,
        disabled_by=disabled_by,
        domain=entity_id.split(".")[0],
    )


BLITZ = FakeRegistry(
    reg_entry("sensor.blitzortung_lightning_counter", unique_id="abc-lightning_counter"),
    reg_entry("sensor.blitzortung_lightning_distance", unique_id="abc-lightning_distance"),
)


# ---------------------------------------------------------------------------
# constants and naming
# ---------------------------------------------------------------------------


class TestKeysAndNaming:
    def test_defaults_are_off(self):
        assert const.DEFAULT_ENABLE_PATTERN_FORECAST is False
        assert const.DEFAULT_PATTERN_STORM_INTERNET_LIGHTNING is False

    def test_no_new_key_intersects_the_forecaster_cleanup_list(self):
        new_keys = {
            v
            for name, v in vars(const).items()
            if isinstance(v, str) and (name.startswith(("KEY_PATTERN", "CONF_PATTERN")) or "PATTERN" in name)
        }
        new_keys |= {CONF_ENABLE_PATTERN_FORECAST, CONF_PATTERN_STORM_INTERNET_LIGHTNING}
        assert new_keys
        assert not new_keys & set(DEPRECATED_KEYS_FORECASTER)
        assert not [k for k in new_keys if "forecaster" in k]

    def test_unique_ids_and_translation_keys_avoid_the_cleanup_pattern(self):
        from custom_components.ws_core.entity_descriptions import SENSORS
        from custom_components.ws_core.switch import FEATURE_SWITCHES

        pattern_sensors = [s for s in SENSORS if s.key.startswith("pattern_")]
        assert len(pattern_sensors) == 9
        for s in pattern_sensors:
            assert "forecaster" not in s.key and "forecaster" not in (s.translation_key or "")
        sw = next(x for x in FEATURE_SWITCHES if x.conf_key == CONF_ENABLE_PATTERN_FORECAST)
        assert sw.default is False and "forecaster" not in sw.conf_key

    def test_no_forecaster_key_in_any_translation_file(self):
        for name in ("strings.json", *(f"translations/{lang}.json" for lang in LANGS)):
            text = (COMPONENT / name).read_text(encoding="utf-8")
            keys = set(re.findall(r'"([^"\n]+)":', text))
            assert not [k for k in keys if "forecaster" in k], name

    def test_no_em_dash_in_new_modules(self):
        for name in ("pattern_runtime.py", "pattern_sources.py", "pattern_forecast.py"):
            assert chr(0x2014) not in (COMPONENT / name).read_text(encoding="utf-8")


class TestLocalFirstContract:
    def test_pattern_modules_never_touch_network_or_network_fed_caches(self):
        for name in ("pattern_runtime.py", "pattern_sources.py", "pattern_forecast.py"):
            src = (COMPONENT / name).read_text(encoding="utf-8").lower()
            for banned in (
                "aiohttp",
                "clientsession",
                "_forecast_cache",
                "_nowcast_cache",
                "_neighbor_qc_cache",
                "_climate_normals",
                "open-meteo",
                "key_forecast",
                "key_nowcast",
            ):
                assert banned not in src, (name, banned)

    def test_runs_with_forecast_disabled_and_no_http_session(self):
        coord, states = make_coord({"forecast_enabled": False, CONF_ENABLE_PATTERN_FORECAST: True})
        assert coord.forecast_enabled is False
        assert coord._pattern is not None
        assert coord._pattern.storm_source is None
        with patch(
            "custom_components.ws_core.coordinator.async_get_clientsession", side_effect=AssertionError("network")
        ):
            rt = coord._pattern
            now = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)
            for i in range(35):
                rt.update(_data(), now + timedelta(minutes=i), sample=True)
        assert rt.engine.models


def _data(**kw):
    d = {
        KEY_NORM_TEMP_C: 12.0,
        KEY_DEW_POINT_C: 8.0,
        KEY_NORM_PRESSURE_HPA: 1010.0,
        const.KEY_SEA_LEVEL_PRESSURE_HPA: 1013.0,
        const.KEY_PRESSURE_TREND_HPAH: -0.2,
        KEY_NORM_WIND_SPEED_MS: 3.0,
        KEY_NORM_WIND_GUST_MS: 5.0,
        KEY_NORM_WIND_DIR_DEG: 270.0,
        KEY_NORM_RAIN_TOTAL_MM: 10.0,
        const.KEY_TEMP_HIGH_24H: 15.0,
        const.KEY_TEMP_LOW_24H: 8.0,
    }
    d.update(kw)
    return d


# ---------------------------------------------------------------------------
# sensors, switch, toggle gating, translations
# ---------------------------------------------------------------------------


class TestEntities:
    def test_nine_sensors_gated_by_the_one_toggle(self):
        from custom_components.ws_core.entity_descriptions import _FEATURE_TOGGLE_MAP, SENSORS

        keys = [s.key for s in SENSORS if s.key.startswith("pattern_")]
        assert sorted(keys) == sorted(
            [*PATTERN_TARGET_KEYS.values(), KEY_PATTERN_FORECAST_STATUS, KEY_PATTERN_FORECAST_SKILL]
        )
        assert {_FEATURE_TOGGLE_MAP[k] for k in keys} == {CONF_ENABLE_PATTERN_FORECAST}

    def test_probability_sensor_shape(self):
        from homeassistant.components.sensor import SensorStateClass

        from custom_components.ws_core.entity_descriptions import SENSORS

        desc = next(s for s in SENSORS if s.key == "pattern_rain_3h")
        assert desc.native_unit == "%" and desc.state_class == SensorStateClass.MEASUREMENT
        assert desc.suggested_display_precision == 0
        out = {"rain_3h": {"target": "rain", "maturity": "learning", "top_factors": []}}
        assert desc.attrs_fn({const.KEY_PATTERN_OUTPUTS: out})["maturity"] == "learning"
        assert desc.value_fn({"pattern_rain_3h": 42}) == 42
        assert desc.value_fn({"pattern_rain_3h": None}) is None  # unknown, not 0%

    def test_status_and_skill_sensors(self):
        from homeassistant.components.sensor import SensorDeviceClass
        from homeassistant.helpers.entity import EntityCategory

        from custom_components.ws_core.entity_descriptions import SENSORS

        status = next(s for s in SENSORS if s.key == KEY_PATTERN_FORECAST_STATUS)
        assert status.device_class == SensorDeviceClass.ENUM
        assert status.options == ["collecting", "waiting", "learning", "active"]
        skill = next(s for s in SENSORS if s.key == KEY_PATTERN_FORECAST_SKILL)
        assert skill.entity_category == EntityCategory.DIAGNOSTIC
        assert skill.entity_registry_enabled_default is False

    def test_entity_ids_follow_the_documented_names(self):
        from custom_components.ws_core.sensor import WSSensor

        for key, slug in (
            ("pattern_rain_1h", "pattern_rain_1h"),
            ("pattern_frost_12h", "pattern_frost_12h"),
            ("pattern_forecast_status", "pattern_forecast_status"),
            ("pattern_forecast_skill", "pattern_forecast_skill"),
        ):
            assert WSSensor._slug_for_key(key) == slug

    def test_feature_switch(self):
        from custom_components.ws_core.switch import FEATURE_SWITCHES

        sw = next(x for x in FEATURE_SWITCHES if x.conf_key == CONF_ENABLE_PATTERN_FORECAST)
        assert sw.name == "Feature: Pattern Forecast" and not sw.inverted

    def _setup(self, options: dict, sources: dict | None = None):
        from custom_components.ws_core import sensor

        coord, _ = make_coord(options, sources)
        entry = MagicMock()
        entry.entry_id = "entry_1"
        entry.data = {"prefix": "ws", **options, "sources": dict(sources or {})}
        entry.options = {}
        entry.runtime_data = coord
        added: list = []
        asyncio.run(sensor.async_setup_entry(MagicMock(), entry, added.extend))
        return {e._desc.key: e for e in added if hasattr(e, "_desc")}

    def test_nothing_is_created_while_the_toggle_is_off(self):
        ents = self._setup({})
        assert not [k for k in ents if k.startswith("pattern_")]

    def test_no_storm_entity_without_a_source(self):
        ents = self._setup({CONF_ENABLE_PATTERN_FORECAST: True})
        assert KEY_PATTERN_STORM_3H not in ents
        assert len([k for k in ents if k.startswith("pattern_")]) == 8

    def test_storm_entity_with_a_local_detector(self):
        ents = self._setup({CONF_ENABLE_PATTERN_FORECAST: True}, {SRC_LIGHTNING_COUNT: "sensor.wh57_count"})
        e = ents[KEY_PATTERN_STORM_3H]
        assert e._attr_translation_key == "pattern_storm_3h"
        assert e.entity_id == "sensor.ws_pattern_storm_3h"

    def test_internet_storm_entity_is_labelled_but_keeps_its_ids(self):
        opts = {CONF_ENABLE_PATTERN_FORECAST: True, CONF_PATTERN_STORM_INTERNET_LIGHTNING: True}
        e = self._setup(opts)[KEY_PATTERN_STORM_3H]
        assert e._attr_translation_key == "pattern_storm_3h_internet"
        assert e.entity_id == "sensor.ws_pattern_storm_3h"
        assert e._attr_unique_id == "entry_1_pattern_storm_3h"
        en = json.loads((COMPONENT / "translations/en.json").read_text(encoding="utf-8"))
        assert en["entity"]["sensor"]["pattern_storm_3h_internet"]["name"].endswith("(internet lightning)")

    def test_detector_wins_over_the_opt_in_for_the_entity_too(self):
        opts = {CONF_ENABLE_PATTERN_FORECAST: True, CONF_PATTERN_STORM_INTERNET_LIGHTNING: True}
        e = self._setup(opts, {SRC_LIGHTNING_COUNT: "sensor.wh57_count"})[KEY_PATTERN_STORM_3H]
        assert e._attr_translation_key == "pattern_storm_3h"


class TestTranslations:
    def _load(self, lang: str) -> dict:
        name = "strings.json" if lang == "strings" else f"translations/{lang}.json"
        return json.loads((COMPONENT / name).read_text(encoding="utf-8"))

    @pytest.mark.parametrize("lang", ["strings", *LANGS])
    def test_every_new_string_exists(self, lang):
        d = self._load(lang)
        sensors = d["entity"]["sensor"]
        for key in (
            *PATTERN_TARGET_KEYS.values(),
            "pattern_storm_3h_internet",
            KEY_PATTERN_FORECAST_STATUS,
            KEY_PATTERN_FORECAST_SKILL,
        ):
            assert sensors[key]["name"]
        for key in PATTERN_TARGET_KEYS.values():
            attrs = sensors[key]["state_attributes"]
            assert set(attrs["maturity"]["state"]) == {"collecting", "learning", "skilled", "degraded", "paused"}
            assert set(attrs["data_source"]["state"]) == {"local", "internet"}
        assert set(sensors[KEY_PATTERN_FORECAST_STATUS]["state"]) == {"collecting", "waiting", "learning", "active"}
        assert d["entity"]["switch"]["ws_enable_pattern_forecast"]["name"]
        for step, form in (("features", d["config"]["step"]), ("features_opt", d["options"]["step"])):
            assert form[step]["data"]["enable_pattern_forecast"]
            assert form[step]["data_description"]["enable_pattern_forecast"]
        for form, step in ((d["config"]["step"], "pattern_forecast"), (d["options"]["step"], "pattern_forecast_opt")):
            assert form[step]["title"] and form[step]["data"][CONF_PATTERN_STORM_INTERNET_LIGHTNING]
            assert form[step]["data_description"][CONF_PATTERN_STORM_INTERNET_LIGHTNING]

    @pytest.mark.parametrize("lang", ["strings", *LANGS])
    def test_factor_labels_cover_every_engine_factor(self, lang):
        d = self._load(lang)["selector"]
        assert set(d["pattern_factor"]["options"]) == set(FACTOR_KEYS)
        assert set(d["pattern_effect"]["options"]) == {"raises", "lowers"}

    @pytest.mark.parametrize("lang", [x for x in LANGS if x != "en"])
    def test_translations_are_real_not_english_copies(self, lang):
        en, tr = self._load("en"), self._load(lang)
        same = [
            k
            for k, v in en["selector"]["pattern_factor"]["options"].items()
            if tr["selector"]["pattern_factor"]["options"][k] == v
        ]
        assert len(same) <= 3, same  # a couple of cognates (e.g. "Night" -> "Nacht") are fine
        for path in (
            ("config", "step", "features", "data_description", "enable_pattern_forecast"),
            ("config", "step", "pattern_forecast", "data_description", CONF_PATTERN_STORM_INTERNET_LIGHTNING),
            ("entity", "sensor", "pattern_forecast_status", "name"),
            ("entity", "switch", "ws_enable_pattern_forecast", "name"),
        ):
            a, b = en, tr
            for p in path:
                a, b = a[p], b[p]
            assert a != b, path

    def test_strings_and_en_are_in_sync(self):
        assert self._load("strings") == self._load("en")

    def test_spec_field_description_is_used_verbatim(self):
        d = self._load("en")
        assert d["config"]["step"]["pattern_forecast"]["data_description"][CONF_PATTERN_STORM_INTERNET_LIGHTNING] == (
            "Use internet lightning data (Blitzortung) for the storm forecast. You don't have a lightning detector, "
            "so the storm forecast can only work with data downloaded from the Blitzortung community network. "
            "All other forecasts stay 100% local. Off by default."
        )

    def test_services_yaml_lists_the_new_reset_target(self):
        text = (COMPONENT / "services.yaml").read_text(encoding="utf-8")
        assert '"pattern_forecast"' in text


# ---------------------------------------------------------------------------
# storm data source
# ---------------------------------------------------------------------------


class TestStormSource:
    def test_hardware_always_wins(self):
        src = {SRC_LIGHTNING_COUNT: "sensor.x"}
        assert pattern_sources.storm_source(src, False) == "local"
        assert pattern_sources.storm_source(src, True) == "local"

    def test_internet_only_with_the_opt_in(self):
        assert pattern_sources.storm_source({}, False) is None
        assert pattern_sources.storm_source({SRC_LIGHTNING_COUNT: ""}, False) is None
        assert pattern_sources.storm_source({}, True) == "internet"

    def test_from_options_requires_the_feature(self):
        assert pattern_sources.storm_source_from_options({CONF_PATTERN_STORM_INTERNET_LIGHTNING: True}) is None
        on = {CONF_ENABLE_PATTERN_FORECAST: True, CONF_PATTERN_STORM_INTERNET_LIGHTNING: True}
        assert pattern_sources.storm_source_from_options(on) == "internet"

    def test_registry_check_requires_the_blitzortung_platform(self):
        impostor = FakeRegistry(reg_entry("sensor.blitzortung_lightning_counter", platform="template"))
        assert pattern_sources.find_blitzortung_entities(None, impostor) == {}
        found = pattern_sources.find_blitzortung_entities(None, BLITZ)
        assert found == {
            SRC_LIGHTNING_COUNT: "sensor.blitzortung_lightning_counter",
            SRC_LIGHTNING_DISTANCE: "sensor.blitzortung_lightning_distance",
        }

    def test_disabled_blitzortung_entities_are_ignored(self):
        reg = FakeRegistry(reg_entry("sensor.blitzortung_lightning_counter", disabled_by="user"))
        assert pattern_sources.find_blitzortung_entities(None, reg) == {}

    def test_config_flow_question_only_when_it_can_matter(self):
        on = {CONF_ENABLE_PATTERN_FORECAST: True, "sources": {}}
        assert pattern_sources.internet_choice_needed(None, on, BLITZ) is True
        assert pattern_sources.internet_choice_needed(None, on, FakeRegistry()) is False  # nothing to offer
        assert (
            pattern_sources.internet_choice_needed(None, {**on, "sources": {SRC_LIGHTNING_COUNT: "sensor.d"}}, BLITZ)
            is False
        )
        assert pattern_sources.internet_choice_needed(None, {"sources": {}}, BLITZ) is False  # feature off

    def test_fingerprint_changes_with_station_and_elevation_not_lightning(self):
        base = {"temperature": "sensor.t", "pressure": "sensor.p"}
        a = pattern_sources.source_fingerprint(base, 100)
        assert a == pattern_sources.source_fingerprint({**base, SRC_LIGHTNING_COUNT: "sensor.l"}, 100)
        assert a != pattern_sources.source_fingerprint({**base, "temperature": "sensor.t2"}, 100)
        assert a != pattern_sources.source_fingerprint(base, 250)

    def _rt(self, options: dict, sources: dict | None = None, states: dict | None = None):
        coord, table = make_coord({CONF_ENABLE_PATTERN_FORECAST: True, **options}, sources, states)
        return coord._pattern, table

    def test_internet_ticks_are_invalid_when_blitzortung_is_not_visible(self):
        rt, _ = self._rt({CONF_PATTERN_STORM_INTERNET_LIGHTNING: True})
        with patch.object(pattern_runtime, "find_blitzortung_entities", return_value={}):
            assert rt._strikes(1000.0) == (None, None)
        with patch.object(
            pattern_runtime,
            "find_blitzortung_entities",
            return_value={SRC_LIGHTNING_COUNT: "sensor.blitzortung_lightning_counter"},
        ):
            rt2, table = self._rt({CONF_PATTERN_STORM_INTERNET_LIGHTNING: True})
            assert rt2._strikes(1000.0) == (None, None)  # entity not in the state machine: not available
            table["sensor.blitzortung_lightning_counter"] = state("unavailable")
            assert rt2._strikes(1000.0) == (None, None)
            table["sensor.blitzortung_lightning_counter"] = state("12")
            assert rt2._strikes(1000.0)[0] == 12.0

    def test_blitzortung_is_never_consulted_when_a_detector_is_mapped(self):
        rt, table = self._rt(
            {CONF_PATTERN_STORM_INTERNET_LIGHTNING: True},
            {SRC_LIGHTNING_COUNT: "sensor.wh57_count"},
            {"sensor.wh57_count": state("5")},
        )
        assert rt.storm_source == "local"
        with patch.object(pattern_runtime, "find_blitzortung_entities", side_effect=AssertionError("must not scan")):
            assert rt._strikes(1000.0) == (5.0, None)
        assert rt.engine.data_source("storm_3h") == "local"
        assert rt.engine.internet_inputs() == []

    def test_blitzortung_is_never_consulted_without_the_opt_in(self):
        rt, _ = self._rt({})
        assert rt.storm_source is None
        with patch.object(pattern_runtime, "find_blitzortung_entities", side_effect=AssertionError("must not scan")):
            assert rt._strikes(1000.0) == (None, None)
        assert "storm_3h" not in rt.engine.models

    def test_internet_labelling_everywhere_it_shows(self):
        rt, _ = self._rt({CONF_PATTERN_STORM_INTERNET_LIGHTNING: True})
        data: dict = {}
        rt._rebuild_published()
        rt._publish(data)
        out = data[const.KEY_PATTERN_OUTPUTS]
        assert out["storm_3h"]["data_source"] == "internet"
        assert {out[t]["data_source"] for t in out if t != "storm_3h"} == {"local"}
        assert data[const.KEY_PATTERN_STATUS_ATTRS]["internet_inputs"] == ["storm_3h"]
        assert rt.diagnostics()["internet_lightning_in_use"] is True

    def test_local_storm_has_no_internet_inputs(self):
        rt, _ = self._rt({}, {SRC_LIGHTNING_COUNT: "sensor.d"}, {"sensor.d": state("0")})
        data: dict = {}
        rt._rebuild_published()
        rt._publish(data)
        assert data[const.KEY_PATTERN_STATUS_ATTRS]["internet_inputs"] == []
        assert data[const.KEY_PATTERN_OUTPUTS]["storm_3h"]["data_source"] == "local"
        assert rt.diagnostics()["internet_lightning_in_use"] is False

    def test_idle_unknown_detector_means_no_new_strikes_unavailable_means_invalid(self):
        rt, table = self._rt({}, {SRC_LIGHTNING_COUNT: "sensor.d"}, {"sensor.d": state("7")})
        assert rt._strikes(1.0)[0] == 7.0
        table["sensor.d"] = state("unknown")
        assert rt._strikes(2.0)[0] == 7.0
        table["sensor.d"] = state("unavailable")
        assert rt._strikes(3.0)[0] is None

    def test_no_storm_target_explains_why(self):
        rt, _ = self._rt({})
        data: dict = {}
        rt._rebuild_published()
        rt._publish(data)
        assert "not created" in data[const.KEY_PATTERN_STATUS_ATTRS]["storm_target"]
        assert const.KEY_PATTERN_STORM_3H not in data


# ---------------------------------------------------------------------------
# coordinator hooks
# ---------------------------------------------------------------------------


class TestCoordinatorHooks:
    def test_feature_is_off_by_default(self):
        coord, _ = make_coord()
        assert coord.pattern_enabled is False and coord._pattern is None

    def test_thresholds_reuse_the_existing_settings(self):
        coord, _ = make_coord(
            {
                CONF_ENABLE_PATTERN_FORECAST: True,
                "thresh_freeze_c": 2.0,
                "thresh_heat_day_c": 33.0,
                "thresh_wind_gust_ms": 12.0,
                "lightning_proximity_km": 25.0,
            }
        )
        assert coord._pattern.thresholds() == Thresholds(frost_c=2.0, heat_c=33.0, gust_ms=12.0, storm_km=25.0)

    def test_issue_only_on_the_quarter_hour_marks_of_sample_ticks(self):
        coord, _ = make_coord({CONF_ENABLE_PATTERN_FORECAST: True})
        rt = coord._pattern
        eng = rt.engine
        eng.issue = MagicMock(return_value={})  # type: ignore[method-assign]
        observe = MagicMock()
        eng.observe = observe  # type: ignore[method-assign]
        start = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)
        for i in range(61):
            rt.update(_data(), start + timedelta(minutes=i), sample=True)
        assert observe.call_count == 61
        assert eng.issue.call_count == 5  # 12:00, 12:15, 12:30, 12:45, 13:00
        hourly = [c.kwargs["hourly"] for c in eng.issue.call_args_list]
        assert hourly == [True, False, False, False, True]

    def test_source_change_recomputes_never_feed_or_issue(self):
        coord, _ = make_coord({CONF_ENABLE_PATTERN_FORECAST: True})
        rt = coord._pattern
        rt.engine.issue = MagicMock()  # type: ignore[method-assign]
        rt.engine.observe = MagicMock()  # type: ignore[method-assign]
        rt.update(_data(), datetime(2026, 3, 1, 12, 0, tzinfo=UTC), sample=False)
        rt.engine.issue.assert_not_called()
        rt.engine.observe.assert_not_called()
        from custom_components.ws_core.coordinator import WSStationCoordinator

        assert "sample=False" in inspect.getsource(WSStationCoordinator._handle_source_change)
        assert "sample=True" in inspect.getsource(WSStationCoordinator._handle_tick)

    def test_off_mark_start_waits_for_the_next_quarter(self):
        coord, _ = make_coord({CONF_ENABLE_PATTERN_FORECAST: True})
        rt = coord._pattern
        rt.engine.issue = MagicMock(return_value={})  # type: ignore[method-assign]
        start = datetime(2026, 3, 1, 12, 7, tzinfo=UTC)
        for i in range(10):
            rt.update(_data(), start + timedelta(minutes=i), sample=True)
        assert rt.engine.issue.call_count == 1  # only 12:15

    def test_flagged_inputs_pause_the_targets_that_use_them(self):
        coord, _ = make_coord({CONF_ENABLE_PATTERN_FORECAST: True})
        rt = coord._pattern
        seen: list = []
        rt.engine.observe = lambda ts, obs, tz=0.0: seen.append(obs)  # type: ignore[method-assign]
        data = _data()
        data["_drift_details"] = [{"sensor": "temperature"}, {"sensor": "rain_rate"}]
        data[const.KEY_SENSOR_STUCK] = ["humidity"]
        rt.update(data, datetime(2026, 3, 1, 12, 1, tzinfo=UTC), sample=True)
        obs = seen[0]
        assert obs.temp is None and obs.rain_total is None and obs.dpd is None
        assert obs.gust == 5.0 and obs.wind_speed == 3.0  # untouched inputs still flow

    def test_quality_flag_texts_map_to_input_groups(self):
        flagged = pattern_runtime.PatternRuntime._flagged_inputs(
            {
                const.KEY_SENSOR_QUALITY_FLAGS: [
                    "temperature 99.0°C outside physical range",
                    "wind gust below wind speed (check anemometer)",
                ],
                const.KEY_SENSOR_SPIKE: ["pressure: 900.0 is 5.0σ from mean 1010.0"],
            }
        )
        assert flagged == {"temp", "wind", "gust", "press"}

    def test_wind_components_follow_the_meteorological_convention(self):
        coord, _ = make_coord({CONF_ENABLE_PATTERN_FORECAST: True})
        rt = coord._pattern
        seen: list = []
        rt.engine.observe = lambda ts, obs, tz=0.0: seen.append(obs)  # type: ignore[method-assign]
        rt.update(
            _data(**{KEY_NORM_WIND_DIR_DEG: 270.0, KEY_NORM_WIND_SPEED_MS: 4.0}),
            datetime(2026, 3, 1, 12, 1, tzinfo=UTC),
            True,
        )
        assert seen[0].wind_u == pytest.approx(4.0)  # wind FROM the west blows toward the east
        assert seen[0].wind_v == pytest.approx(0.0, abs=1e-9)

    def test_clearness_and_night_fraction_inputs(self):
        coord, _ = make_coord(
            {CONF_ENABLE_PATTERN_FORECAST: True, "sources": {}},
            states={"sun.sun": state("above_horizon", elevation=45.0)},
        )
        rt = coord._pattern
        coord._get_solar_radiation = lambda: 450.0  # type: ignore[method-assign]
        captured: dict = {}
        rt.engine.issue = lambda ts, inst, tz=0.0, hourly=None, heuristics=None: captured.setdefault("inst", inst) or {}  # type: ignore[method-assign]
        rt.update(_data(), datetime(2026, 6, 21, 9, 0, tzinfo=UTC), sample=True)
        inst = captured["inst"]
        assert inst.solar_ok is True and 0.0 <= inst.cloud_deficit <= 1.0
        assert inst.last_day_clearness is not None
        assert 0.0 <= inst.night_frac_12h <= 1.0

    def test_heuristics_are_diagnostic_only_inputs_to_scoring(self):
        coord, _ = make_coord({CONF_ENABLE_PATTERN_FORECAST: True})
        rt = coord._pattern
        captured: dict = {}
        rt.engine.issue = lambda ts, inst, tz=0.0, hourly=None, heuristics=None: captured.update(h=heuristics) or {}  # type: ignore[method-assign]
        rt.update(
            _data(**{const.KEY_RAIN_PROBABILITY: 40, const.KEY_THUNDERSTORM_RISK: 10}),
            datetime(2026, 3, 1, 12, 0, tzinfo=UTC),
            True,
        )
        assert captured["h"]["rain_3h"] == pytest.approx(0.4)
        assert captured["h"]["storm_3h"] == pytest.approx(0.1)

    def test_a_failing_engine_never_breaks_the_package(self):
        coord, _ = make_coord({CONF_ENABLE_PATTERN_FORECAST: True})
        rt = coord._pattern
        rt.engine.observe = MagicMock(side_effect=RuntimeError("boom"))  # type: ignore[method-assign]
        data = _data()
        rt.update(data, datetime(2026, 3, 1, 12, 0, tzinfo=UTC), sample=True)  # must not raise
        rt.update(data, datetime(2026, 3, 1, 12, 1, tzinfo=UTC), sample=True)

    def test_published_data_keys_and_unknown_while_collecting(self):
        coord, _ = make_coord({CONF_ENABLE_PATTERN_FORECAST: True})
        rt = coord._pattern
        data = _data()
        for i in range(20):
            rt.update(data, datetime(2026, 3, 1, 12, 0, tzinfo=UTC) + timedelta(minutes=i), sample=True)
        for tid, key in PATTERN_TARGET_KEYS.items():
            if tid != "storm_3h":
                assert key in data and data[key] is None  # unknown, never 0%
        assert data[KEY_PATTERN_FORECAST_STATUS] == "waiting"  # recent/24 h inputs are not ready
        assert data[KEY_PATTERN_FORECAST_SKILL] == 0
        rain = data[const.KEY_PATTERN_OUTPUTS]["rain_3h"]
        assert rain["maturity"] == "collecting" and rain["progress_pct"] == 0
        assert rain["threshold"] == 0.2 and rain["threshold_unit"] == "mm"
        assert data[const.KEY_PATTERN_OUTPUTS]["frost_12h"]["threshold_unit"] == "°C"
        assert data[const.KEY_PATTERN_OUTPUTS]["gust_3h"]["threshold_unit"] == coord.wind_unit
        assert set(data[const.KEY_PATTERN_STATUS_ATTRS]["per_target"]) == {
            t.target_id for t in TARGETS if t.kind != "storm"
        }

    def test_threshold_attributes_follow_display_units(self):
        coord, _ = make_coord(
            {CONF_ENABLE_PATTERN_FORECAST: True, "wind_unit": "km/h", "rain_unit": "in", "temp_unit": "F"}
        )
        rt = coord._pattern
        assert rt._threshold_display("gust") == (61.2, "km/h")
        assert rt._threshold_display("rain") == (0.008, "in")
        assert rt._threshold_display("frost") == (32.0, "°F")

    @pytest.mark.parametrize(("minute", "expected"), [(0, "waiting"), (7, "collecting")])
    def test_full_compute_publishes_the_pattern_keys(self, minute, expected):
        sources = {
            "temperature": "sensor.t",
            "humidity": "sensor.h",
            "pressure": "sensor.p",
            "wind_speed": "sensor.ws",
            "wind_gust": "sensor.wg",
            "wind_direction": "sensor.wd",
            "rain_total": "sensor.r",
        }
        states = {
            "sensor.t": state(14, unit_of_measurement="°C"),
            "sensor.h": state(70, unit_of_measurement="%"),
            "sensor.p": state(1008, unit_of_measurement="hPa"),
            "sensor.ws": state(3, unit_of_measurement="m/s"),
            "sensor.wg": state(5, unit_of_measurement="m/s"),
            "sensor.wd": state(200),
            "sensor.r": state(10, unit_of_measurement="mm"),
            "sun.sun": state("above_horizon", elevation=30),
        }
        coord, _ = make_coord({CONF_ENABLE_PATTERN_FORECAST: True}, sources, states)
        # Before the first issue mark no forecast has been attempted; at an issue
        # mark missing recent/24 h history is explicitly reported as waiting.
        with patch.object(pattern_runtime.dt_util, "utcnow", return_value=datetime(2026, 3, 1, 12, minute, tzinfo=UTC)):
            for _ in range(3):
                data = coord._compute(sample=True)
        assert data[KEY_PATTERN_FORECAST_STATUS] == expected
        assert data["pattern_rain_3h"] is None
        # the same compute with the feature off carries no pattern keys at all
        off, _ = make_coord({}, sources, states)
        assert not [k for k in off._compute(sample=True) if k.startswith("pattern_")]

    def test_compute_time_budget(self):
        coord, _ = make_coord({CONF_ENABLE_PATTERN_FORECAST: True})
        rt = coord._pattern
        data = _data()
        start = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)
        t0 = time.perf_counter()
        for i in range(600):
            rt.update(dict(data), start + timedelta(minutes=i), sample=True)
        assert (time.perf_counter() - t0) / 600 < 0.01  # well under 10 ms per 60 s tick


class TestStoreWiring:
    class FakeStore:
        def __init__(self, data=None):
            self.data = data
            self.saved = None
            self.removed = False

        async def async_load(self):
            return self.data

        async def async_save(self, data):
            self.saved = data

        async def async_remove(self):
            self.removed = True

    def test_load_save_and_reset(self):
        async def go():
            coord, _ = make_coord({CONF_ENABLE_PATTERN_FORECAST: True})
            rt = coord._pattern
            store = self.FakeStore()
            await rt.async_load(store)
            assert rt.store is store
            rt.engine.models["rain_3h"].n_updates = 5
            await rt.async_save()
            assert store.saved["models"]["rain_3h"]["n_updates"] == 5
            await coord.async_reset_pattern_forecast()
            assert store.removed and rt.engine.models["rain_3h"].n_updates == 0

        asyncio.run(go())

    def test_store_name_is_separate_from_the_learning_store(self):
        coord, _ = make_coord({CONF_ENABLE_PATTERN_FORECAST: True})
        with patch("homeassistant.helpers.storage.Store") as store_cls:
            coord._pattern.make_store("abc")
        args = store_cls.call_args.args
        assert args[1] == const.PATTERN_STORE_VERSION and args[2] == "ws_core_abc_pattern_forecast"

    def test_threshold_change_between_restarts_resets_only_that_target(self):
        async def go():
            coord, _ = make_coord({CONF_ENABLE_PATTERN_FORECAST: True})
            rt = coord._pattern
            store = self.FakeStore()
            await rt.async_load(store)
            for m in rt.engine.models.values():
                m.n_updates = 9
            await rt.async_save()
            coord2, _ = make_coord({CONF_ENABLE_PATTERN_FORECAST: True, "thresh_freeze_c": 2.0})
            await coord2._pattern.async_load(self.FakeStore(json.loads(json.dumps(store.saved))))
            models = coord2._pattern.engine.models
            assert models["frost_12h"].n_updates == 0
            assert models["rain_3h"].n_updates == 9 and models["gust_3h"].n_updates == 9

        asyncio.run(go())

    def test_different_station_resets_everything(self):
        async def go():
            coord, _ = make_coord({CONF_ENABLE_PATTERN_FORECAST: True}, {"temperature": "sensor.a"})
            store = self.FakeStore()
            await coord._pattern.async_load(store)
            for m in coord._pattern.engine.models.values():
                m.n_updates = 4
            await coord._pattern.async_save()
            coord2, _ = make_coord({CONF_ENABLE_PATTERN_FORECAST: True}, {"temperature": "sensor.b"})
            await coord2._pattern.async_load(self.FakeStore(json.loads(json.dumps(store.saved))))
            assert all(m.n_updates == 0 for m in coord2._pattern.engine.models.values())

        asyncio.run(go())

    def test_corrupt_store_starts_fresh(self):
        async def go():
            coord, _ = make_coord({CONF_ENABLE_PATTERN_FORECAST: True})
            await coord._pattern.async_load(self.FakeStore({"schema_version": 1, "pool_id": "pool-v1", "models": 7}))
            assert coord._pattern.engine.overall_status() == "collecting"

        asyncio.run(go())


# ---------------------------------------------------------------------------
# services, diagnostics, flows
# ---------------------------------------------------------------------------


class TestServicesAndDiagnostics:
    def test_summary_lists_maturity_skill_and_named_weights(self):
        coord, _ = make_coord({CONF_ENABLE_PATTERN_FORECAST: True})
        s = coord._pattern.summary()
        assert set(s) == {t.target_id for t in TARGETS if t.kind != "storm"}
        assert "weights" in s["rain_3h"] and "dpd" in s["rain_3h"]["weights"]
        json.dumps(s)

    def test_diagnostics_section_has_no_location_data(self):
        from custom_components.ws_core.diagnostics import async_get_config_entry_diagnostics

        coord, _ = make_coord({CONF_ENABLE_PATTERN_FORECAST: True, "forecast_lat": 38.123, "forecast_lon": 23.456})
        coord.data = {}
        entry = MagicMock()
        entry.data = {"sources": {}}
        entry.options = {}
        entry.title = "t"
        entry.runtime_data = coord
        out = asyncio.run(async_get_config_entry_diagnostics(coord.hass, entry))
        section = out["pattern_forecast"]
        assert section["enabled"] is True
        text = json.dumps(section)
        assert "38.123" not in text and "23.456" not in text
        assert "standardizer" in section and "internet_lightning_in_use" in section

    def test_diagnostics_when_disabled(self):
        from custom_components.ws_core.diagnostics import async_get_config_entry_diagnostics

        coord, _ = make_coord()
        coord.data = {}
        entry = MagicMock()
        entry.data = {"sources": {}}
        entry.options = {}
        entry.title = "t"
        entry.runtime_data = coord
        out = asyncio.run(async_get_config_entry_diagnostics(coord.hass, entry))
        assert out["pattern_forecast"] == {"enabled": False}


class TestConfigFlow:
    def _flow(self, cls):
        flow = cls()
        flow.hass = MagicMock()
        flow.async_show_form = MagicMock(side_effect=lambda **kw: {"type": "form", **kw})
        flow.async_create_entry = MagicMock(side_effect=lambda **kw: {"type": "create_entry", **kw})
        return flow

    def test_setup_features_step_offers_the_toggle_default_off(self):
        from custom_components.ws_core.config_flow import WSStationConfigFlow

        flow = self._flow(WSStationConfigFlow)
        form = asyncio.run(flow.async_step_features())
        key = next(k for k in form["data_schema"].schema if k == CONF_ENABLE_PATTERN_FORECAST)
        assert key.default() is False

    def _submit_features(self, flow, **kw):
        base = {k: False for k in ("enable_sea_temp", "enable_wunderground", "enable_air_quality", "enable_pollen")}
        return asyncio.run(flow.async_step_features({**base, **kw}))

    def test_setup_asks_only_without_detector_and_with_blitzortung(self):
        from custom_components.ws_core.config_flow import WSStationConfigFlow

        flow = self._flow(WSStationConfigFlow)
        flow._data = {const.CONF_SOURCES: {}}
        flow.async_step_alerts = AsyncMock(return_value={"step": "alerts"})
        with patch.object(pattern_sources, "find_blitzortung_entities", return_value={SRC_LIGHTNING_COUNT: "sensor.b"}):
            out = self._submit_features(flow, **{CONF_ENABLE_PATTERN_FORECAST: True})
        assert out["step_id"] == "pattern_forecast"
        assert flow._data[CONF_ENABLE_PATTERN_FORECAST] is True

        # answering the question stores the opt-in and carries on with the chain
        out = asyncio.run(flow.async_step_pattern_forecast({CONF_PATTERN_STORM_INTERNET_LIGHTNING: True}))
        assert flow._data[CONF_PATTERN_STORM_INTERNET_LIGHTNING] is True
        assert out == {"step": "alerts"} or out.get("step_id") is not None

    def test_setup_skips_the_question_with_a_detector_or_without_blitzortung(self):
        from custom_components.ws_core.config_flow import WSStationConfigFlow

        for sources, blitz in (({SRC_LIGHTNING_COUNT: "sensor.d"}, {SRC_LIGHTNING_COUNT: "sensor.b"}), ({}, {})):
            flow = self._flow(WSStationConfigFlow)
            flow._data = {const.CONF_SOURCES: sources}
            flow.async_step_alerts = AsyncMock(return_value={"step": "alerts"})
            flow._next_v2_step = AsyncMock(return_value={"step": "alerts"})
            with patch.object(pattern_sources, "find_blitzortung_entities", return_value=blitz):
                out = self._submit_features(flow, **{CONF_ENABLE_PATTERN_FORECAST: True})
            assert out.get("step_id") != "pattern_forecast"
            assert CONF_PATTERN_STORM_INTERNET_LIGHTNING not in flow._data

    def test_setup_without_the_feature_never_scans_the_registry(self):
        from custom_components.ws_core.config_flow import WSStationConfigFlow

        flow = self._flow(WSStationConfigFlow)
        flow._data = {const.CONF_SOURCES: {}}
        flow.async_step_alerts = AsyncMock(return_value={"step": "alerts"})
        with patch.object(pattern_sources, "find_blitzortung_entities", side_effect=AssertionError("scan")):
            self._submit_features(flow)

    def test_options_flow_chains_the_same_step(self):
        from custom_components.ws_core.config_flow import WSStationOptionsFlowHandler

        flow = self._flow(WSStationOptionsFlowHandler)
        entry = MagicMock()
        entry.data = {const.CONF_SOURCES: {}}
        entry.options = {}
        flow._opt = {}
        flow.async_step_upload_services_opt = AsyncMock(return_value={"step": "uploads"})
        with (
            patch.object(WSStationOptionsFlowHandler, "config_entry", new_callable=PropertyMock, return_value=entry),
            patch.object(pattern_sources, "find_blitzortung_entities", return_value={SRC_LIGHTNING_COUNT: "sensor.b"}),
        ):
            out = asyncio.run(flow.async_step_features_opt({CONF_ENABLE_PATTERN_FORECAST: True}))
            assert out["step_id"] == "pattern_forecast_opt"
            out = asyncio.run(flow.async_step_pattern_forecast_opt({CONF_PATTERN_STORM_INTERNET_LIGHTNING: True}))
        assert flow._opt[CONF_PATTERN_STORM_INTERNET_LIGHTNING] is True
        assert out == {"step": "uploads"}

    def test_options_flow_default_off_and_no_question_without_blitzortung(self):
        from custom_components.ws_core.config_flow import WSStationOptionsFlowHandler

        flow = self._flow(WSStationOptionsFlowHandler)
        entry = MagicMock()
        entry.data = {const.CONF_SOURCES: {}}
        entry.options = {}
        flow._opt = {}
        flow.async_step_upload_services_opt = AsyncMock(return_value={"step": "uploads"})
        with (
            patch.object(WSStationOptionsFlowHandler, "config_entry", new_callable=PropertyMock, return_value=entry),
            patch.object(pattern_sources, "find_blitzortung_entities", return_value={}),
        ):
            form = asyncio.run(flow.async_step_features_opt())
            key = next(k for k in form["data_schema"].schema if k == CONF_ENABLE_PATTERN_FORECAST)
            assert key.default() is False
            out = asyncio.run(flow.async_step_features_opt({CONF_ENABLE_PATTERN_FORECAST: True}))
        assert out == {"step": "uploads"}


class TestAstronomy:
    def test_sun_elevation_athens(self):
        from custom_components.ws_core.algorithms import solar_elevation_deg

        winter = solar_elevation_deg(38.0, 23.7, datetime(2026, 12, 21, 10, 0, tzinfo=UTC))
        summer = solar_elevation_deg(38.0, 23.7, datetime(2026, 6, 21, 10, 0, tzinfo=UTC))
        night = solar_elevation_deg(38.0, 23.7, datetime(2026, 12, 21, 22, 0, tzinfo=UTC))
        assert winter == pytest.approx(28.5, abs=1.5)
        assert summer == pytest.approx(75.0, abs=1.5)
        assert night < -50

    def test_night_fraction_follows_the_season(self):
        from custom_components.ws_core.algorithms import night_fraction_ahead

        winter_evening = night_fraction_ahead(38.0, 23.7, datetime(2026, 12, 21, 15, 0, tzinfo=UTC))
        summer_morning = night_fraction_ahead(38.0, 23.7, datetime(2026, 6, 21, 4, 0, tzinfo=UTC))
        summer_evening = night_fraction_ahead(38.0, 23.7, datetime(2026, 6, 21, 18, 0, tzinfo=UTC))
        assert winter_evening == 1.0 and summer_morning == 0.0
        assert 0.4 < summer_evening < 0.9  # a short summer night, not a long winter one
        assert winter_evening > summer_evening
