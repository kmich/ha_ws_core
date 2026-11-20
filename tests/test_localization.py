"""Tests for v2.5.0 localization and selector slugging (issue #104 / #105)."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from custom_components.ws_core import localize
from custom_components.ws_core.const import (
    CLIMATE_REGION_OPTIONS,
    DEFAULT_CLIMATE_REGION,
    DEFAULT_HEMISPHERE,
    HEMISPHERE_OPTIONS,
    KEY_FROST_RISK,
)


class TestLocalize:
    def test_french_summary_and_alert(self):
        assert localize.summary("fr", "feels_like", v="20.0°C") == "ressenti 20.0°C"
        assert localize.alert("fr", "clear") == "Tout est normal"

    def test_english_default(self):
        assert localize.summary("en", "no_data") == "No data"
        assert localize.alert("en", "freeze", v="-1.0°C") == "Freeze risk: -1.0°C"

    def test_unknown_language_falls_back_to_english(self):
        # German is not provided -> English fallback, no KeyError.
        assert localize.summary("de", "humidity", v="50") == "RH 50%"
        assert localize.alert(None, "clear") == "All clear"

    def test_region_variant_falls_back(self):
        # "fr-CA" should resolve to the "fr" table.
        assert localize.alert("fr-CA", "clear") == "Tout est normal"


class TestSelectorSlugging:
    def test_option_values_are_slugs(self):
        for v in HEMISPHERE_OPTIONS + CLIMATE_REGION_OPTIONS:
            assert v == v.lower()
            assert " " not in v
        assert DEFAULT_HEMISPHERE == "northern"
        assert DEFAULT_CLIMATE_REGION == "atlantic_europe"


class TestFrostRiskSensor:
    def test_frost_risk_has_sensor_description(self):
        # Parse the source rather than importing sensor.py, which pulls in
        # HA-version-sensitive device classes unrelated to this test.
        pkg_dir = os.path.join(os.path.dirname(__file__), "..", "custom_components", "ws_core")
        text = ""
        for fname in ("entity_descriptions.py", "sensor.py"):
            fpath = os.path.join(pkg_dir, fname)
            if os.path.exists(fpath):
                with open(fpath, encoding="utf-8") as f:
                    text += f.read()
        assert "key=KEY_FROST_RISK" in text
        assert 'translation_key="frost_risk"' in text
        assert KEY_FROST_RISK == "frost_risk"


class TestPR6LocalizationCompleteness:
    """PR 6 item 25 & PR 4 item 17 translation completeness across strings and all 8 languages."""

    @staticmethod
    def _load(name: str) -> dict:
        import json
        from pathlib import Path

        base = Path(__file__).resolve().parent.parent / "custom_components" / "ws_core"
        p = base / ("strings.json" if name == "strings" else f"translations/{name}.json")
        return json.loads(p.read_text(encoding="utf-8"))

    def test_optional_sources_and_soil_keys_present_in_all_languages(self):
        from custom_components.ws_core.const import CONF_SOIL_MOISTURE_UNIT, SRC_LIGHTNING_AZIMUTH

        en = self._load("en")
        assert self._load("strings") == en

        for lang in ("strings", "en", "de", "es", "fr", "it", "nl", "pl", "pt"):
            d = self._load(lang)
            cfg_data = d["config"]["step"]["optional_sources"]["data"]
            opt_data = d["options"]["step"]["optional_sources_opt"]["data"]
            assert cfg_data[SRC_LIGHTNING_AZIMUTH]
            assert opt_data[SRC_LIGHTNING_AZIMUTH]
            assert cfg_data[CONF_SOIL_MOISTURE_UNIT]
            assert opt_data[CONF_SOIL_MOISTURE_UNIT]
            opts = d["selector"]["soil_moisture_unit"]["options"]
            assert set(opts) == {"auto", "percent", "fraction"}
            assert all(opts.values())
            issue = d["issues"]["ambiguous_soil_moisture_unit"]
            assert issue["title"] and issue["description"]

        for lang in ("de", "es", "fr", "it", "nl", "pl", "pt"):
            tr = self._load(lang)
            assert (
                tr["issues"]["ambiguous_soil_moisture_unit"]["title"]
                != en["issues"]["ambiguous_soil_moisture_unit"]["title"]
            )
            assert (
                tr["config"]["step"]["optional_sources"]["data"][CONF_SOIL_MOISTURE_UNIT]
                != en["config"]["step"]["optional_sources"]["data"][CONF_SOIL_MOISTURE_UNIT]
            )

    def test_v3_options_menu_and_weather_window_sensors_present_in_all_languages(self):
        en = self._load("en")
        assert self._load("strings") == en

        expected_menu = {"sources", "forecast", "decision_profiles", "rooms", "thresholds", "uploads", "diagnostics"}
        expected_steps = {"init", "sources", "forecast", "decision_profiles", "thresholds"}
        expected_window_sensors = {
            f"window_{pid}_{suffix}"
            for pid in ("outdoor_drying", "garden_work", "custom")
            for suffix in ("status", "next_start", "next_end")
        }

        for lang in ("strings", "en", "de", "es", "fr", "it", "nl", "pl", "pt"):
            d = self._load(lang)
            opt_steps = d["options"]["step"]
            assert expected_steps <= set(opt_steps), (lang, expected_steps - set(opt_steps))
            assert set(opt_steps["init"]["menu_options"]) == expected_menu, lang
            assert opt_steps["decision_profiles"]["data"]["enable_weather_windows"]
            assert opt_steps["decision_profiles"]["data"]["weather_window_profiles"]
            for custom_key in (
                "custom_window_name",
                "custom_min_duration_h",
                "custom_max_rain_prob_pct",
                "custom_max_rain_mm",
                "custom_min_temp_c",
                "custom_max_temp_c",
                "custom_min_humidity_pct",
                "custom_max_humidity_pct",
                "custom_min_wind_kmh",
                "custom_max_wind_kmh",
                "custom_max_wind_gust_kmh",
                "custom_max_cloud_cover_pct",
                "custom_require_daylight",
            ):
                assert opt_steps["decision_profiles"]["data"][custom_key], (lang, custom_key)
                if custom_key in (
                    "custom_max_rain_mm",
                    "custom_min_temp_c",
                    "custom_max_temp_c",
                    "custom_min_wind_kmh",
                    "custom_max_wind_kmh",
                    "custom_max_wind_gust_kmh",
                ):
                    label = opt_steps["decision_profiles"]["data"][custom_key]
                    assert "(°C)" not in label and "(km/h)" not in label and "(mm/h)" not in label, (lang, custom_key)
            assert "{provider_warning}" in opt_steps["decision_profiles"]["description"], lang
            prof_opts = d["selector"]["weather_window_profiles"]["options"]
            assert set(prof_opts) == {"outdoor_drying", "garden_work", "custom"}, lang
            assert all(prof_opts.values()), lang
            assert d["options"]["error"]["invalid_duration"]
            assert d["options"]["error"]["min_exceeds_max"]

            sensors = d["entity"]["sensor"]
            assert expected_window_sensors <= set(sensors), (lang, expected_window_sensors - set(sensors))
            for pid in ("outdoor_drying", "garden_work", "custom"):
                st = sensors[f"window_{pid}_status"]
                assert set(st["state"]) == {"suitable_now", "window_upcoming", "unsuitable", "unknown"}
                assert all(st["state"].values())

        for lang in ("de", "es", "fr", "it", "nl", "pl", "pt"):
            tr = self._load(lang)
            assert tr["options"]["step"]["init"]["title"] != en["options"]["step"]["init"]["title"], lang
            assert (
                tr["selector"]["weather_window_profiles"]["options"]["outdoor_drying"]
                != en["selector"]["weather_window_profiles"]["options"]["outdoor_drying"]
            ), lang
            assert (
                tr["entity"]["sensor"]["window_outdoor_drying_status"]["name"]
                != en["entity"]["sensor"]["window_outdoor_drying_status"]["name"]
            ), lang


def test_every_translation_has_exactly_the_english_keys_and_placeholders():
    """No missing, stale or mismatched strings in any language (issues #91, #94 class)."""
    import json
    import re
    from pathlib import Path

    base = Path(__file__).resolve().parent.parent / "custom_components" / "ws_core"
    placeholder = re.compile(r"\{([a-zA-Z0-9_]+)\}")

    def flatten(node, path=()):
        if isinstance(node, dict):
            for key, value in node.items():
                yield from flatten(value, (*path, key))
        else:
            yield path, node

    english = dict(flatten(json.loads((base / "strings.json").read_text(encoding="utf-8"))))
    for file in sorted((base / "translations").glob("*.json")):
        other = dict(flatten(json.loads(file.read_text(encoding="utf-8"))))
        assert set(other) == set(english), (file.name, sorted(set(other) ^ set(english))[:5])
        for key, text in english.items():
            assert set(placeholder.findall(str(text))) == set(placeholder.findall(str(other[key]))), (file.name, key)
