"""Tests for dashboard YAML files: entity references, card types, and syntax.

Prevents regressions such as non-existent Mushroom cards (issue #159:
mushroom-sensor-card, mushroom-weather-info-card) or broken entity references.
"""

from __future__ import annotations

import os
import pathlib
import sys

import jinja2
import pytest
import yaml

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from scripts.validate_dashboard_entities import (
    ALL_KNOWN_CARD_TYPES,
    _dashboard_card_refs,
    validate,
)

ROOT = pathlib.Path(__file__).parent.parent
DASHBOARDS_DIR = ROOT / "dashboards"


def test_validate_script_passes():
    """Verify that the dashboard validator passes across all dashboard files."""
    assert validate(prefix="ws") is True


def test_dashboard_yaml_syntax():
    """Verify that every dashboard YAML file is valid YAML."""
    yaml_files = list(DASHBOARDS_DIR.glob("*.yaml"))
    assert yaml_files, "No dashboard YAML files found"
    for yf in yaml_files:
        content = yf.read_text(encoding="utf-8")
        parsed = yaml.safe_load(content)
        assert isinstance(parsed, dict), f"{yf.name} should parse into a YAML dict"


def test_all_card_types_recognized():
    """Verify that all card types in dashboards are recognized (no hallucinated cards)."""
    yaml_files = list(DASHBOARDS_DIR.glob("*.yaml"))
    for yf in yaml_files:
        card_refs = _dashboard_card_refs(yf)
        unrecognized = {ctype: lines for ctype, lines in card_refs.items() if ctype not in ALL_KNOWN_CARD_TYPES}
        assert not unrecognized, f"Unrecognized card types in {yf.name}: {unrecognized}"


def test_no_invalid_mushroom_cards():
    """Explicitly verify that issue #159 hallucinated mushroom cards are absent."""
    yaml_files = list(DASHBOARDS_DIR.glob("*.yaml"))
    forbidden = ["mushroom-sensor-card", "mushroom-weather-info-card", "mushroom-weather-card"]
    for yf in yaml_files:
        text = yf.read_text(encoding="utf-8")
        for card in forbidden:
            assert card not in text, f"Found forbidden '{card}' in {yf.name}"


@pytest.mark.parametrize("filename", ["weather_dashboard.yaml", "ws_core_bubble_dashboard.yaml"])
@pytest.mark.parametrize("scenario", ["paused", "collecting", "learning", "old_version"])
def test_pattern_table_explains_unknowns_without_hiding_factors(filename, scenario):
    config = yaml.safe_load((DASHBOARDS_DIR / filename).read_text(encoding="utf-8"))

    def markdowns(node):
        if isinstance(node, dict):
            if node.get("title") == "Maturity and why":
                yield node["content"]
            for value in node.values():
                yield from markdowns(value)
        elif isinstance(node, list):
            for value in node:
                yield from markdowns(value)

    attrs = {"maturity": scenario, "progress_pct": 20}
    if scenario == "paused":
        attrs.update(reason="waiting_for:wind_u", explanation="Waiting for recent wind history.")
    elif scenario == "learning":
        attrs["top_factors"] = [{"factor": "pressure_falling", "effect": "raises"}]
    elif scenario == "old_version":
        attrs.update(maturity="paused", reason="waiting_for:wind_u")
    env = jinja2.Environment()
    env.globals.update(states=lambda e: "unknown", state_attr=lambda e, a: attrs.get(a))
    rendered = "\n".join(env.from_string(template).render() for template in markdowns(config))
    assert rendered
    expected = {
        "paused": "Waiting for recent wind history.",
        "collecting": "Collecting: 20%",
        "learning": "pressure falling (raises)",
        "old_version": "waiting_for:wind_u",
    }
    assert expected[scenario] in rendered


# ---------------------------------------------------------------------------
# Bubble Card dashboard (ws_core_bubble_dashboard.yaml)
# ---------------------------------------------------------------------------

BUBBLE_DASHBOARD = DASHBOARDS_DIR / "ws_core_bubble_dashboard.yaml"


def _bubble_cards(node, out=None):
    """Every custom:bubble-card in a parsed dashboard, at any depth."""
    out = [] if out is None else out
    if isinstance(node, list):
        for item in node:
            _bubble_cards(item, out)
    elif isinstance(node, dict):
        if node.get("type") == "custom:bubble-card":
            out.append(node)
        for value in node.values():
            _bubble_cards(value, out)
    return out


def _bubble_links(node, out=None):
    """Every '#hash' a button or the bottom bar navigates to."""
    out = [] if out is None else out
    if isinstance(node, list):
        for item in node:
            _bubble_links(item, out)
    elif isinstance(node, dict):
        for key, value in node.items():
            if key == "navigation_path" or key.endswith("_link"):
                out.append(value)
            _bubble_links(value, out)
    return out


def _top_level_cards(view):
    """A view's own cards: `cards` for masonry views, each section's cards for sections views."""
    if view.get("type") == "sections":
        return [card for section in view.get("sections", []) for card in section.get("cards", [])]
    return view.get("cards", [])


def test_bubble_popups_use_standalone_format():
    """Bubble Card v3.2+ pop-ups hold their content in `cards`, not a vertical-stack wrapper."""
    config = yaml.safe_load(BUBBLE_DASHBOARD.read_text(encoding="utf-8"))
    popups = [c for c in _bubble_cards(config) if c.get("card_type") == "pop-up"]
    assert popups, "Bubble dashboard should define pop-ups"
    for popup in popups:
        assert popup.get("cards"), f"Pop-up {popup.get('hash')} has no cards"
    for view in config["views"]:
        for card in _top_level_cards(view):
            if card.get("type") == "vertical-stack":
                first = (card.get("cards") or [{}])[0]
                assert first.get("card_type") != "pop-up", "Pop-up uses the old vertical-stack wrapper"


def test_bubble_popup_hashes_unique_and_every_link_resolves():
    config = yaml.safe_load(BUBBLE_DASHBOARD.read_text(encoding="utf-8"))
    hashes = [c["hash"] for c in _bubble_cards(config) if c.get("card_type") == "pop-up"]
    assert len(hashes) == len(set(hashes)), f"Duplicate pop-up hashes: {hashes}"
    links = _bubble_links(config)
    assert links, "Bubble dashboard should link to its pop-ups"
    for link in links:
        assert link in hashes, f"Link {link!r} opens no pop-up"


def test_bubble_bottom_bar_is_last_card_in_view():
    """Bubble Card requires the horizontal-buttons-stack to be the view's last card, outside any stack."""
    config = yaml.safe_load(BUBBLE_DASHBOARD.read_text(encoding="utf-8"))
    for view in config["views"]:
        cards = _top_level_cards(view)
        assert cards, f"View {view.get('path')} has no cards"
        stacks = [c for c in _bubble_cards(cards) if c.get("card_type") == "horizontal-buttons-stack"]
        if not stacks:
            continue
        assert len(stacks) == 1, "One bottom bar per view"
        assert cards[-1] is stacks[0], "The bottom bar must be the last top-level card in the view"


def test_validator_knows_parenthesized_switch_constants():
    """CONF_ENABLE_DIAGNOSTICS is wrapped in parentheses in const.py; its switch must still be known."""
    from scripts.validate_dashboard_entities import build_known_entities

    assert "switch.ws_enable_diagnostics" in build_known_entities("ws")


def _gate_violations(node, gates, toggles, out):
    """Entity refs to toggle-gated sensors that no enclosing conditional guards."""
    if isinstance(node, list):
        for item in node:
            _gate_violations(item, gates, toggles, out)
    elif isinstance(node, dict):
        if node.get("type") == "conditional":
            guards = gates | {c.get("entity") for c in node.get("conditions", [])}
            _gate_violations(node.get("card"), guards, toggles, out)
            return
        entity = node.get("entity")
        if isinstance(entity, str) and entity in toggles:
            switch = f"switch.ws_{toggles[entity]}"
            if switch not in gates and entity not in gates:
                out.append(f"{entity} needs a conditional on {switch}")
        for value in node.values():
            _gate_violations(value, gates, toggles, out)
    return out


def test_bubble_gated_sensors_sit_behind_their_switch():
    """A sensor that only exists with a feature switch on must not show 'Entity not found' when it's off."""
    from custom_components.ws_core import const
    from custom_components.ws_core.entity_descriptions import _FEATURE_TOGGLE_MAP, SENSORS
    from custom_components.ws_core.sensor import WSSensor

    # Features that are on by default (display sensors) may be shown unguarded.
    default_on = {
        getattr(const, name)
        for name in dir(const)
        if name.startswith("CONF_ENABLE_") and getattr(const, f"DEFAULT_{name[5:]}", False) is True
    }
    toggles = {
        f"sensor.ws_{WSSensor._slug_for_key(d.key)}": _FEATURE_TOGGLE_MAP[d.key]
        for d in SENSORS
        if d.key in _FEATURE_TOGGLE_MAP and _FEATURE_TOGGLE_MAP[d.key] not in default_on
    }
    config = yaml.safe_load(BUBBLE_DASHBOARD.read_text(encoding="utf-8"))
    assert _gate_violations(config, set(), toggles, []) == []


def test_bubble_main_page_is_one_column():
    """A one-column sections view keeps the short main page from spreading thin on a desktop."""
    config = yaml.safe_load(BUBBLE_DASHBOARD.read_text(encoding="utf-8"))
    view = config["views"][0]
    assert view.get("type") == "sections"
    assert view.get("max_columns") == 1
    bar = _top_level_cards(view)[-1]
    assert bar.get("width_desktop"), "Six bottom-bar buttons don't fit Bubble Card's 540px desktop default"
