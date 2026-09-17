"""Regression tests for issue #135.

Optional entity-picker fields in the config/options flow must stay
clearable. Home Assistant's frontend forms treat a ``vol.Optional(...,
default=X)`` field as "sticky": once auto-detection pre-fills a guessed
sensor, the user cannot clear the picker back to empty, which blocks saving
whenever the guess is wrong, unavailable, or the wrong type. The fix is to
pre-fill via ``description={"suggested_value": X}`` instead, which shows the
same pre-filled suggestion but leaves the field genuinely clearable.
"""

from __future__ import annotations

import os
import sys

import voluptuous as vol

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _schema_marker(schema: vol.Schema, key_name: str):
    """Return the vol.Optional/vol.Required marker object for a field name."""
    return next(k for k in schema.schema if str(k) == key_name)


class TestRoomFormSchemaClearable:
    """WSStationConfigFlow._room_form_schema (initial setup + options flow)."""

    def test_prefilled_optional_field_has_no_sticky_default(self):
        from custom_components.ws_core.config_flow import WSStationConfigFlow

        flow = WSStationConfigFlow()
        schema = flow._room_form_schema({"name": "Bedroom", "temp": "sensor.bedroom_temp"})

        marker = _schema_marker(schema, "temp")
        # vol.UNDEFINED (rendered as Ellipsis) means "no default" -- the
        # field is not locked to the pre-filled value and can be cleared.
        assert marker.default is vol.UNDEFINED
        assert marker.description == {"suggested_value": "sensor.bedroom_temp"}

    def test_field_with_no_current_value_has_no_default_or_suggestion(self):
        from custom_components.ws_core.config_flow import WSStationConfigFlow

        flow = WSStationConfigFlow()
        schema = flow._room_form_schema({"name": "Office"})

        marker = _schema_marker(schema, "humidity")
        assert marker.default is vol.UNDEFINED

    def test_options_flow_room_form_schema_matches(self):
        from custom_components.ws_core.config_flow import WSStationOptionsFlowHandler

        handler = WSStationOptionsFlowHandler()
        schema = handler._room_form_schema({"name": "Kitchen", "co2": "sensor.kitchen_co2"})

        marker = _schema_marker(schema, "co2")
        assert marker.default is vol.UNDEFINED
        assert marker.description == {"suggested_value": "sensor.kitchen_co2"}


class TestOptionalSourcesSchemaClearable:
    """The optional_sources / optional_sources_opt sensor-mapping steps."""

    def test_guessed_optional_source_is_suggested_not_defaulted(self):
        from custom_components.ws_core.config_flow import OPTIONAL_SOURCES

        guessed_key = next(iter(OPTIONAL_SOURCES))
        defaults = {guessed_key: "sensor.guessed_humidity"}

        # Mirrors the field-construction expression used in
        # async_step_optional_sources / async_step_optional_sources_opt.
        fields = {
            (
                vol.Optional(k, description={"suggested_value": defaults[k]}) if k in defaults else vol.Optional(k)
            ): object()
            for k in OPTIONAL_SOURCES
        }
        schema = vol.Schema(fields)

        marker = _schema_marker(schema, guessed_key)
        assert marker.default is vol.UNDEFINED
        assert marker.description == {"suggested_value": "sensor.guessed_humidity"}


class TestMergeSubmittedSources:
    """Regression tests for issue #149.

    When one field on the required/optional source-mapping step fails
    validation, the whole form is re-shown. Without merging the just-submitted
    values back into the pre-fill defaults, every *other* field silently
    reverts to its old guessed/stored value, and a field the user just
    cleared reappears pre-filled with its old value.
    """

    def test_valid_submitted_value_overrides_stale_default(self):
        from custom_components.ws_core.config_flow import _merge_submitted_sources

        defaults = {"humidity": "sensor.old_humidity", "dew_point": "sensor.old_dewpoint"}
        # User corrected "dew_point" but a different field ("humidity") is
        # what actually failed validation this submission.
        user_input = {"humidity": "sensor.bad_humidity", "dew_point": "sensor.new_dewpoint"}

        merged = _merge_submitted_sources(defaults, user_input, ["humidity", "dew_point"])

        assert merged["dew_point"] == "sensor.new_dewpoint"
        assert merged["humidity"] == "sensor.bad_humidity"

    def test_cleared_field_none_does_not_revert_to_stale_default(self):
        from custom_components.ws_core.config_flow import _merge_submitted_sources

        defaults = {"humidity": "sensor.old_humidity", "dew_point": "sensor.old_dewpoint"}
        # User cleared "dew_point" via the picker's X button (submitted as
        # empty/None) while "humidity" failed validation.
        user_input = {"humidity": "sensor.bad_humidity", "dew_point": None}

        merged = _merge_submitted_sources(defaults, user_input, ["humidity", "dew_point"])

        assert "dew_point" not in merged

    def test_cleared_field_empty_string_does_not_revert_to_stale_default(self):
        from custom_components.ws_core.config_flow import _merge_submitted_sources

        defaults = {"humidity": "sensor.old_humidity", "dew_point": "sensor.old_dewpoint"}
        user_input = {"humidity": "sensor.bad_humidity", "dew_point": ""}

        merged = _merge_submitted_sources(defaults, user_input, ["humidity", "dew_point"])

        assert "dew_point" not in merged

    def test_field_absent_from_submission_is_cleared(self):
        from custom_components.ws_core.config_flow import _merge_submitted_sources

        defaults = {"humidity": "sensor.old_humidity", "dew_point": "sensor.old_dewpoint"}
        # In Home Assistant frontend, clearing an entity picker sets its value
        # to undefined, which JSON.stringify strips entirely from the submission.
        # Merging must treat an omitted rendered field as cleared, not keep stale defaults.
        user_input = {"humidity": "sensor.bad_humidity"}  # dew_point cleared by user

        merged = _merge_submitted_sources(defaults, user_input, ["humidity", "dew_point"])

        assert "dew_point" not in merged
        assert merged["humidity"] == "sensor.bad_humidity"


class TestValidateNumericSensor:
    """Tests for _validate_numeric_sensor behavior (issues #88, #149)."""

    def test_numeric_sensor_accepted(self):
        from unittest.mock import MagicMock

        from custom_components.ws_core.config_flow import _validate_numeric_sensor

        hass = MagicMock()
        state = MagicMock()
        state.state = "14.2"
        hass.states.get.return_value = state

        assert _validate_numeric_sensor(hass, "sensor.gw3000a_dewpoint") is None

    def test_unavailable_or_unknown_sensor_accepted(self):
        from unittest.mock import MagicMock

        from custom_components.ws_core.config_flow import _validate_numeric_sensor

        hass = MagicMock()
        for s in ("unavailable", "unknown"):
            state = MagicMock()
            state.state = s
            hass.states.get.return_value = state
            assert _validate_numeric_sensor(hass, "sensor.gw3000a_dewpoint") is None

    def test_entity_not_in_states_but_in_registry_accepted(self):
        from unittest.mock import MagicMock, patch

        from custom_components.ws_core.config_flow import _validate_numeric_sensor

        hass = MagicMock()
        hass.states.get.return_value = None

        mock_reg = MagicMock()
        mock_reg.async_get.return_value = MagicMock()  # entity exists in registry

        with patch("homeassistant.helpers.entity_registry.async_get", return_value=mock_reg):
            assert _validate_numeric_sensor(hass, "sensor.gw3000a_dewpoint") is None

    def test_missing_sensor_rejected(self):
        from unittest.mock import MagicMock, patch

        from custom_components.ws_core.config_flow import _validate_numeric_sensor

        hass = MagicMock()
        hass.states.get.return_value = None

        mock_reg = MagicMock()
        mock_reg.async_get.return_value = None  # not in registry either

        with patch("homeassistant.helpers.entity_registry.async_get", return_value=mock_reg):
            assert _validate_numeric_sensor(hass, "sensor.does_not_exist") == "entity_not_found"

    def test_non_numeric_sensor_rejected(self):
        from unittest.mock import MagicMock

        from custom_components.ws_core.config_flow import _validate_numeric_sensor

        hass = MagicMock()
        state = MagicMock()
        state.state = "sunny"
        hass.states.get.return_value = state

        assert _validate_numeric_sensor(hass, "sensor.weather_summary") == "not_numeric"

    def test_whitespace_padded_entity_id_handled(self):
        from unittest.mock import MagicMock

        from custom_components.ws_core.config_flow import _validate_numeric_sensor

        hass = MagicMock()
        state = MagicMock()
        state.state = "18.5"
        hass.states.get.side_effect = lambda eid: state if eid == "sensor.temp" else None

        assert _validate_numeric_sensor(hass, "  sensor.temp  ") is None


class TestGuessDefaults:
    """Tests for _guess_defaults auto-detection (issues #135, #149)."""

    def test_ignores_non_sensor_domains(self):
        from unittest.mock import MagicMock

        from custom_components.ws_core.config_flow import _guess_defaults

        hass = MagicMock()
        hass.data = {}
        s_binary = MagicMock()
        s_binary.entity_id = "binary_sensor.gw3000a_wh65_battery"
        s_switch = MagicMock()
        s_switch.entity_id = "switch.station_power"
        s_temp = MagicMock()
        s_temp.entity_id = "sensor.gw3000a_outdoor_temperature"

        hass.states.async_all.return_value = [s_binary, s_switch, s_temp]

        guessed = _guess_defaults(hass)
        assert "battery" not in guessed
        assert guessed.get("temperature") == "sensor.gw3000a_outdoor_temperature"

    def test_excludes_ws_core_derived_sensors(self):
        from unittest.mock import MagicMock

        from custom_components.ws_core.config_flow import _guess_defaults

        hass = MagicMock()
        hass.data = {}
        s_ws = MagicMock()
        s_ws.entity_id = "sensor.ws_dew_point"
        hass.states.async_all.return_value = [s_ws]

        guessed = _guess_defaults(hass)
        assert "dew_point" not in guessed

    def test_matches_valid_sensor_battery(self):
        from unittest.mock import MagicMock

        from custom_components.ws_core.config_flow import _guess_defaults

        hass = MagicMock()
        hass.data = {}
        s_bat = MagicMock()
        s_bat.entity_id = "sensor.gw3000a_station_battery"
        hass.states.async_all.return_value = [s_bat]

        guessed = _guess_defaults(hass)
        assert guessed.get("battery") == "sensor.gw3000a_station_battery"


class TestCurrentSourcesForOptions:
    """Tests for _current_sources_for_options in options flow (issues #135, #149)."""

    def test_cleared_optional_source_not_resurrected_from_data(self):
        from unittest.mock import MagicMock

        from custom_components.ws_core.config_flow import WSStationOptionsFlowHandler
        from custom_components.ws_core.const import CONF_SOURCES

        entry = MagicMock()
        entry.data = {
            CONF_SOURCES: {
                "temperature": "sensor.t",
                "battery": "sensor.old_bat",
            }
        }
        # User saved options without battery (cleared)
        entry.options = {
            CONF_SOURCES: {
                "temperature": "sensor.t",
            }
        }

        hass = MagicMock()
        hass.data = {}
        hass.states.async_all.return_value = []

        flow = type(
            "_TestFlow",
            (WSStationOptionsFlowHandler,),
            {"config_entry": property(lambda self: entry)},
        )()
        flow.hass = hass

        defaults = flow._current_sources_for_options()
        assert "battery" not in defaults
        assert defaults["temperature"] == "sensor.t"

    def test_unconfigured_optional_source_not_auto_guessed(self):
        from unittest.mock import MagicMock

        from custom_components.ws_core.config_flow import WSStationOptionsFlowHandler
        from custom_components.ws_core.const import CONF_SOURCES

        entry = MagicMock()
        entry.data = {CONF_SOURCES: {"temperature": "sensor.t"}}
        entry.options = {}

        # HA has an available battery sensor that matches patterns
        s_bat = MagicMock()
        s_bat.entity_id = "sensor.gw3000a_station_battery"

        hass = MagicMock()
        hass.data = {}
        hass.states.async_all.return_value = [s_bat]

        flow = type(
            "_TestFlow",
            (WSStationOptionsFlowHandler,),
            {"config_entry": property(lambda self: entry)},
        )()
        flow.hass = hass

        defaults = flow._current_sources_for_options()
        # In Options flow, unconfigured optional sources must NOT be guessed
        assert "battery" not in defaults
        assert defaults["temperature"] == "sensor.t"

    def test_configured_optional_source_preserved(self):
        from unittest.mock import MagicMock

        from custom_components.ws_core.config_flow import WSStationOptionsFlowHandler
        from custom_components.ws_core.const import CONF_SOURCES

        entry = MagicMock()
        entry.data = {
            CONF_SOURCES: {
                "temperature": "sensor.t",
                "dew_point": "sensor.dp",
            }
        }
        entry.options = {}

        hass = MagicMock()
        hass.data = {}
        hass.states.async_all.return_value = []

        flow = type(
            "_TestFlow",
            (WSStationOptionsFlowHandler,),
            {"config_entry": property(lambda self: entry)},
        )()
        flow.hass = hass

        defaults = flow._current_sources_for_options()
        assert defaults["dew_point"] == "sensor.dp"

    def test_missing_required_source_falls_back_to_guess(self):
        from unittest.mock import MagicMock

        from custom_components.ws_core.config_flow import WSStationOptionsFlowHandler
        from custom_components.ws_core.const import CONF_SOURCES

        entry = MagicMock()
        entry.data = {CONF_SOURCES: {"temperature": "sensor.t"}}
        entry.options = {}

        s_hum = MagicMock()
        s_hum.entity_id = "sensor.gw3000a_outdoor_humidity"

        hass = MagicMock()
        hass.data = {}
        hass.states.async_all.return_value = [s_hum]

        flow = type(
            "_TestFlow",
            (WSStationOptionsFlowHandler,),
            {"config_entry": property(lambda self: entry)},
        )()
        flow.hass = hass

        defaults = flow._current_sources_for_options()
        # Required sources (humidity) fall back to guess if missing
        assert defaults["humidity"] == "sensor.gw3000a_outdoor_humidity"
