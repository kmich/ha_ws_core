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
        assert localize.summary("fr", "feels_like", v="20.0") == "ressenti 20.0°C"
        assert localize.alert("fr", "clear") == "Tout est normal"

    def test_english_default(self):
        assert localize.summary("en", "no_data") == "No data"
        assert localize.alert("en", "freeze", v="-1.0") == "Freeze risk: -1.0°C"

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
        from custom_components.ws_core.sensor import SENSORS

        keys = {s.key for s in SENSORS}
        assert KEY_FROST_RISK in keys
