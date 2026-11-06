"""Execute the Enhanced dashboard's actual JavaScript with HA display states."""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="Node.js is needed to execute button-card templates")
SOURCE = Path(__file__).parents[1] / "dashboards/weather_dashboard.yaml"


def _walk(node):
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _walk(value)
    elif isinstance(node, list):
        for value in node:
            yield from _walk(value)


def _template(entity_id, field="content"):
    config = yaml.safe_load(SOURCE.read_text(encoding="utf-8"))
    return next(
        card["custom_fields"][field]
        for card in _walk(config)
        if card.get("entity") == entity_id and field in card.get("custom_fields", {})
    )


def _state(value, unit=None, **attrs):
    if unit:
        attrs["unit_of_measurement"] = unit
    return {"state": str(value), "attributes": attrs}


def _render(template, states, entity_id):
    result = subprocess.run(
        [
            NODE,
            "-e",
            """
const fs = require('node:fs');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const body = input.template.trim().slice(3, -3);
const render = new Function('states', 'entity', 'hass', 'window', body);
const hass = {states: input.states, config: {unit_system: {temperature: '°C', precipitation: 'mm'}}};
process.stdout.write(String(render(input.states, input.states[input.entity_id], hass, {})));
""",
        ],
        input=json.dumps({"template": template, "states": states, "entity_id": entity_id}),
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=True,
    )
    return result.stdout


def test_all_enhanced_dashboard_javascript_compiles():
    # Parse YAML first: folded/quoted scalars may span lines inside JS strings.
    config = yaml.safe_load(SOURCE.read_text(encoding="utf-8"))
    templates = [
        body
        for node in _walk(config)
        for value in node.values()
        if isinstance(value, str)
        for body in re.findall(r"\[\[\[(.*?)\]\]\]", value, re.S)
    ]
    assert templates
    result = subprocess.run(
        [
            NODE,
            "-e",
            "const fs = require('node:fs'); for (const body of JSON.parse(fs.readFileSync(0, 'utf8'))) new Function(body);",
        ],
        input=json.dumps(templates),
        text=True,
        encoding="utf-8",
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("temperature,unit", [(60.4, "°F"), (15.8, "°C"), (288.95, "K")])
def test_temperature_tile_uses_each_sensor_unit(temperature, unit):
    eid = "sensor.ws_temperature"
    states = {
        eid: _state(temperature, unit),
        "sensor.ws_feels_like": _state(0, "°C"),
        "sensor.ws_dew_point": _state(31.9, "°F"),
    }
    html = _render(_template(eid), states, eid)
    assert f"{temperature:.1f}{unit}" in html
    assert "Feels 0°C" in html
    assert "Dew 31.9°F" in html


def test_temperature_tile_missing_feels_like_uses_temperature_and_its_unit():
    eid = "sensor.ws_temperature"
    states = {eid: _state(60.4, "°F"), "sensor.ws_feels_like": _state("unavailable", "°C")}
    html = _render(_template(eid), states, eid)
    assert "Feels 60°F" in html
    assert "NaN" not in html


def test_summary_preserves_individual_units_and_zero():
    templates = re.findall(r"\[\[\[.*?\]\]\]", SOURCE.read_text(encoding="utf-8"), re.S)
    template = next(t for t in templates if "const location =" in t)
    states = {
        "sensor.ws_temperature": _state(60.4, "°F"),
        "sensor.ws_temperature_high_24h": _state(16, "°C"),
        "sensor.ws_temperature_low_24h": _state(28, "°F"),
        "sensor.ws_feels_like": _state(0, "°C"),
        "sensor.ws_wind_speed": _state(5, "mph"),
    }
    html = _render(template, states, "sensor.ws_zambretti_forecast")
    assert "Feels 0.0°C · H:16°C L:28°F" in html
    assert "5.0 mph" in html


@pytest.mark.parametrize("unit,expected", [("°F", "54°F / 36°F"), ("°C", "12°C / 2°C"), ("K", "285K / 275K")])
def test_forecast_converts_canonical_attributes_once(unit, expected):
    eid = "sensor.ws_forecast_tiles"
    states = {
        eid: _state(5, tiles=[{"tmax": 12, "tmin": 2, "precip_mm": 25.4}]),
        "sensor.ws_temperature": _state(60.4, unit),
        "sensor.ws_rain_today_mm": _state(1, "in"),
    }
    html = _render(_template(eid), states, eid)
    assert expected in html
    assert "1.00 in" in html


def test_forecast_zero_and_missing_values():
    eid = "sensor.ws_forecast_tiles"
    states = {
        eid: _state(5, tiles=[{"tmax": 0, "tmin": None}, {"tmax_c": -5, "tmin_c": 0}, {}]),
        "sensor.ws_temperature": _state("unavailable", "°F"),
    }
    html = _render(_template(eid), states, eid)
    assert "32°F / --" in html
    assert "23°F / 32°F" in html
    assert "-- / --" in html
    assert "NaN" not in html


@pytest.mark.parametrize("eid", ["sensor.iopool_lagonisi_temperature", "sensor.ws_sea_surface_temperature"])
def test_water_temperatures_keep_celsius_comfort_thresholds(eid):
    html = _render(_template(eid), {eid: _state(75.2, "°F")}, eid)
    assert "75.2" in html and "°F</span>" in html
    assert "Cold" not in html and "Warm" not in html and "Hot" not in html


@pytest.mark.parametrize(
    "eid,value,label", [("sensor.ws_heat_index", 100.4, "Extreme caution"), ("sensor.ws_wind_chill", 14, "Danger")]
)
def test_comfort_indices_classify_celsius_and_display_fahrenheit(eid, value, label):
    html = _render(_template(eid, "details"), {eid: _state(value, "°F")}, eid)
    assert f"{value:.1f}" in html and "°F</span>" in html
    assert label in html


def test_temperature_difference_does_not_add_fahrenheit_offset():
    eid = "sensor.ws_delta_t"
    html = _render(_template(eid, "details"), {eid: _state(7.2, "°F", spray_suitability="ideal")}, eid)
    assert "7.2" in html and "°F</span>" in html
    assert "Ideal: 3.6-14.4 °F" in html


def test_wind_tile_uses_states_without_relabeling_metric_attributes():
    eid = "sensor.ws_wind_beaufort"
    states = {
        eid: _state(2, speed_ms=2, gust_ms=3),
        "sensor.ws_wind_speed": _state(4.5, "mph"),
        "sensor.ws_wind_gust": _state(10.8, "km/h"),
    }
    html = _render(_template(eid), states, eid)
    assert "4.5 mph G10.8 km/h" in html


@pytest.mark.parametrize("value,unit,display", [(29.92, "inHg", "29.92"), (1013.25, "hPa", "1013")])
def test_pressure_preserves_display_unit_and_precision(value, unit, display):
    eid = "sensor.ws_sea_level_pressure"
    html = _render(_template(eid), {eid: _state(value, unit)}, eid)
    assert display in html and f">{unit}</span>" in html
    assert "hPa/3h" in html  # The explicit change_3h_hpa attribute stays in hPa.
