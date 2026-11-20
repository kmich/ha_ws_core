"""Empty sensors explain themselves: feels-like fallback, station support and Data Status."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from custom_components.ws_core import const as c
from custom_components.ws_core.entity_descriptions import SENSORS, sensor_selected, station_supports
from custom_components.ws_core.sensor import WSDataStatusSensor, WSSensor, WSSensorDescription
from tests.test_coordinator import _make_coordinator

ENTRY_ID = "status_entry"


def _desc(key):
    return next(d for d in SENSORS if d.key == key)


def _sensor(key, data):
    coordinator = MagicMock()
    coordinator.data = data
    return WSSensor(coordinator, MagicMock(entry_id=ENTRY_ID), _desc(key), "ws")


# --- Feels-like sensors show the air temperature outside their range -----------------


def test_coordinator_marks_out_of_range_feels_like_formulas():
    coord = _make_coordinator()
    data: dict = {}
    coord._compute_derived_temperature(data, datetime.now(UTC), 18.9, 60.0, 1.0)
    assert data[c.KEY_HEAT_INDEX] is None
    assert data[c.KEY_WIND_CHILL] is None
    assert data[c.KEY_THW_INDEX] is None
    # Data keys stay None (MQTT/exports); the marker lists them
    assert {c.KEY_HEAT_INDEX, c.KEY_WIND_CHILL, c.KEY_THW_INDEX} <= set(data[c.KEY_FEELS_LIKE_AIR_TEMP])
    # No solar sensor: THSW was not computed at all, so it is not marked
    assert c.KEY_THSW_INDEX not in data[c.KEY_FEELS_LIKE_AIR_TEMP]


def test_coordinator_does_not_mark_formulas_in_range():
    coord = _make_coordinator()
    data: dict = {}
    coord._compute_derived_temperature(data, datetime.now(UTC), 32.0, 60.0, 1.0)
    assert data[c.KEY_HEAT_INDEX] is not None
    assert c.KEY_HEAT_INDEX not in data[c.KEY_FEELS_LIKE_AIR_TEMP]


def test_out_of_range_sensor_shows_air_temperature_and_says_so():
    data = {c.KEY_NORM_TEMP_C: 18.9, c.KEY_HEAT_INDEX: None, c.KEY_FEELS_LIKE_AIR_TEMP: [c.KEY_HEAT_INDEX]}
    sensor = _sensor(c.KEY_HEAT_INDEX, data)
    assert sensor.native_value == 18.9
    attrs = sensor.extra_state_attributes
    assert attrs["formula_applies"] is False
    assert "air temperature" in attrs["explanation"]
    assert "reason" not in attrs


def test_in_range_sensor_shows_the_index():
    data = {c.KEY_NORM_TEMP_C: 32.0, c.KEY_HEAT_INDEX: 36.4, c.KEY_FEELS_LIKE_AIR_TEMP: []}
    sensor = _sensor(c.KEY_HEAT_INDEX, data)
    assert sensor.native_value == 36.4
    assert sensor.extra_state_attributes["formula_applies"] is True


def test_missing_inputs_still_report_unknown_with_a_reason():
    sensor = _sensor(c.KEY_WIND_CHILL, {})
    assert sensor.native_value is None
    assert "reason" in sensor.extra_state_attributes


# --- Sensors this station can never fill are not created ------------------------------


def test_thsw_needs_a_solar_sensor_and_the_comfort_toggle():
    comfort = {c.CONF_ENABLE_COMFORT_INDICES: True}
    solar = {c.SRC_SOLAR_RADIATION: "sensor.solar"}
    lux = {c.SRC_LUX: "sensor.lux"}
    assert not station_supports(c.KEY_THSW_INDEX, comfort, lux)
    assert not sensor_selected(c.KEY_THSW_INDEX, comfort, lux)
    assert sensor_selected(c.KEY_THSW_INDEX, comfort, solar)
    assert not sensor_selected(c.KEY_THSW_INDEX, {}, solar)
    # Other comfort sensors do not depend on the hardware
    assert sensor_selected(c.KEY_HEAT_INDEX, comfort, lux)


def test_feature_toggles_never_count_as_unsupported():
    for desc in SENSORS:
        if desc.key not in (
            c.KEY_THSW_INDEX,
            c.KEY_CLEARNESS_INDEX,
            c.KEY_CLOUD_COVER_PCT,
            c.KEY_ET0_PM_DAILY_MM,
            c.KEY_SOLAR_ENERGY_TODAY_WHM2,
            c.KEY_PEAK_SUN_HOURS,
            c.KEY_NET_RADIATION,
        ):
            assert station_supports(desc.key, {}, {}), desc.key


# --- Data Status ------------------------------------------------------------------------


class _Registry:
    def __init__(self, entries):
        self._by_uid = {(domain, uid): eid for domain, uid, eid in entries}
        self._entries = {eid: SimpleNamespace(disabled_by=None) for _, _, eid in entries}

    def async_get_entity_id(self, domain, platform, unique_id):
        return self._by_uid.get((domain, unique_id))

    def async_get(self, entity_id):
        return self._entries.get(entity_id)


def _status(data, watched, *, registered, states=None, options=None, sources=None, coordinator_extra=None):
    coordinator = MagicMock()
    coordinator.data = data
    coordinator.sources = sources or {c.SRC_LUX: "sensor.lux"}
    coordinator.nowcast_enabled = True
    coordinator._nowcast_cache = {"x": 1}
    coordinator.lightning_enabled = True
    coordinator._blitzortung_sources = {
        c.SRC_LIGHTNING_DISTANCE: "sensor.blitzortung_distance",
        c.SRC_LIGHTNING_AZIMUTH: "sensor.blitzortung_azimuth",
    }
    for key, value in (coordinator_extra or {}).items():
        setattr(coordinator, key, value)
    entry = MagicMock(entry_id=ENTRY_ID, data={}, options=options or {c.CONF_ENABLE_COMFORT_INDICES: True})
    sensor = WSDataStatusSensor(coordinator, entry, "ws", watched)
    states = states or {}
    sensor.hass = MagicMock()
    sensor.hass.states.get = lambda eid: SimpleNamespace(state=states[eid]) if eid in states else None
    registry = _Registry(registered)
    with patch("custom_components.ws_core.sensor.er.async_get", return_value=registry):
        return sensor.native_value, sensor.extra_state_attributes


def _pattern_desc(key):
    return WSSensorDescription(
        key=key,
        attrs_fn=lambda d: {"reason": "collecting_training_data", "explanation": "Collecting: 1/5 events."},
    )


def test_live_station_replay_is_ok_with_nine_waiting():
    """The 13 'unknown' sensors seen on the WS90 on 2026-11-20 at 18.9 °C."""
    keys = [
        c.KEY_HEAT_INDEX,
        c.KEY_WIND_CHILL,
        c.KEY_THW_INDEX,
        c.KEY_MINUTES_UNTIL_RAIN,
        c.KEY_MINUTES_UNTIL_DRY,
        c.KEY_LIGHTNING_DISTANCE_KM,
        c.KEY_LIGHTNING_AZIMUTH,
        c.KEY_LIGHTNING_PROXIMITY,
        c.KEY_LIGHTNING_CLEARANCE_MIN,
    ]
    watched = [_desc(k) for k in keys] + [_pattern_desc("pattern_frost_12h"), _pattern_desc("pattern_gust_3h")]
    registered = [("sensor", f"{ENTRY_ID}_{d.key}", f"sensor.ws_{d.key}") for d in watched]
    registered += [
        ("event", f"{ENTRY_ID}_frost_event", "event.ws_frost_event"),
        ("event", f"{ENTRY_ID}_rain_event", "event.ws_rain_event"),
    ]
    data = {
        c.KEY_NORM_TEMP_C: 18.9,
        c.KEY_NORM_HUMIDITY: 60.0,
        c.KEY_NORM_WIND_SPEED_MS: 1.0,
        c.KEY_FEELS_LIKE_AIR_TEMP: [c.KEY_HEAT_INDEX, c.KEY_WIND_CHILL, c.KEY_THW_INDEX],
        c.KEY_NOWCAST_INTENSITY: 0.0,
        c.KEY_SOURCE_PROBLEMS: [],
    }
    states = {f"sensor.ws_{d.key}": "unknown" for d in watched}
    states.update({"event.ws_frost_event": "unknown", "event.ws_rain_event": "2026-11-19T10:00:00+00:00"})

    state, attrs = _status(data, watched, registered=registered, states=states)

    assert state == "ok"
    assert attrs["needs_attention"] == []
    assert len(attrs["waiting"]) == 9, attrs["waiting"]
    assert "event.ws_frost_event" in attrs["waiting"]
    assert "event.ws_rain_event" not in attrs["waiting"]
    for feels_like in ("heat_index_c", "wind_chill_c", "thw_index_c"):
        assert f"sensor.ws_{feels_like}" not in attrs["waiting"]
    # The WS90 has lux but no W/m² sensor: the solar families are named, with the fallback hint
    notes = attrs["not_on_this_station"]
    assert "Clearness index and cloud cover" in notes
    assert "THSW index" in notes
    solar = next(v for k, v in notes.items() if k.startswith("Solar energy"))
    assert "illuminance fallback" in solar
    assert "Lightning" not in notes  # Blitzortung is present
    assert attrs["summary"].startswith("Everything is working.")


def test_pattern_target_before_its_first_run_says_so():
    """Right after a restart a learning target has details but no forecast yet."""
    desc = WSSensorDescription(key="pattern_rain_3h", attrs_fn=lambda d: {"maturity": "learning", "events_live": 12})
    watched = [desc]
    registered = [("sensor", f"{ENTRY_ID}_pattern_rain_3h", "sensor.ws_pattern_rain_3h")]
    states = {"sensor.ws_pattern_rain_3h": "unknown"}
    state, attrs = _status({c.KEY_SOURCE_PROBLEMS: []}, watched, registered=registered, states=states)
    assert state == "ok"
    assert "has not run since Home Assistant started" in attrs["waiting"]["sensor.ws_pattern_rain_3h"]

    coordinator = MagicMock()
    coordinator.data = {}
    sensor = WSSensor(coordinator, MagicMock(entry_id=ENTRY_ID), desc, "ws")
    own = sensor.extra_state_attributes
    assert own["reason"] == "waiting_for_first_run"
    assert own["events_live"] == 12


def test_lasting_source_problem_turns_status_to_attention():
    data = {c.KEY_SOURCE_PROBLEMS: ["No recent update from: wind_speed"]}
    state, attrs = _status(data, [], registered=[])
    assert state == "attention"
    assert attrs["needs_attention"] == ["No recent update from: wind_speed"]
    assert "wind_speed" in attrs["summary"]


def test_restored_values_and_disabled_entities_are_not_listed():
    watched = [_desc(c.KEY_MINUTES_UNTIL_RAIN), _desc(c.KEY_MINUTES_UNTIL_DRY)]
    registered = [
        ("sensor", f"{ENTRY_ID}_{c.KEY_MINUTES_UNTIL_RAIN}", "sensor.ws_minutes_until_rain"),
    ]  # minutes_until_dry is not registered (disabled or never created)
    states = {"sensor.ws_minutes_until_rain": "12"}  # still showing a restored value
    state, attrs = _status({c.KEY_SOURCE_PROBLEMS: []}, watched, registered=registered, states=states)
    assert state == "ok"
    assert attrs["waiting"] == {}


def test_lightning_without_any_source_is_one_station_note():
    watched = [_desc(c.KEY_LIGHTNING_DISTANCE_KM), _desc(c.KEY_LIGHTNING_AZIMUTH)]
    registered = [("sensor", f"{ENTRY_ID}_{d.key}", f"sensor.ws_{d.key}") for d in watched]
    states = {f"sensor.ws_{d.key}": "unknown" for d in watched}
    state, attrs = _status(
        {c.KEY_SOURCE_PROBLEMS: []},
        watched,
        registered=registered,
        states=states,
        coordinator_extra={"_blitzortung_sources": {}},
    )
    assert state == "ok"
    assert "Lightning" in attrs["not_on_this_station"]
    assert not any(k.startswith("sensor.ws_lightning") for k in attrs["not_on_this_station"])
    assert attrs["waiting"] == {}


def test_source_problems_need_the_grace_period():
    coord = _make_coordinator()
    coord._source_problem_since = None
    start = datetime.now(UTC)
    data: dict = {}
    coord._compute_health(data, start, missing=["temperature"], missing_entities=[])
    assert data[c.KEY_SOURCE_PROBLEMS] == []  # just started: no alarm yet
    later = start + timedelta(seconds=c.MISSING_SOURCE_GRACE_S + 1)
    coord._compute_health(data, later, missing=["temperature"], missing_entities=[])
    assert data[c.KEY_SOURCE_PROBLEMS] == ["Required source not mapped: temperature"]
    coord._compute_health(data, later, missing=[], missing_entities=[])
    assert data[c.KEY_SOURCE_PROBLEMS] == []
