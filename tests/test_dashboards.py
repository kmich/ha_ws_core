"""Tests for dashboard YAML files: entity references, card types, and syntax.

Prevents regressions such as non-existent Mushroom cards (issue #159:
mushroom-sensor-card, mushroom-weather-info-card) or broken entity references.
"""

from __future__ import annotations

import os
import pathlib
import sys

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


def test_bubble_popups_use_standalone_format():
    """Bubble Card v3.2+ pop-ups hold their content in `cards`, not a vertical-stack wrapper."""
    config = yaml.safe_load(BUBBLE_DASHBOARD.read_text(encoding="utf-8"))
    popups = [c for c in _bubble_cards(config) if c.get("card_type") == "pop-up"]
    assert popups, "Bubble dashboard should define pop-ups"
    for popup in popups:
        assert popup.get("cards"), f"Pop-up {popup.get('hash')} has no cards"
    for view in config["views"]:
        for card in view.get("cards", []):
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
        cards = view.get("cards", [])
        stacks = [c for c in _bubble_cards(cards) if c.get("card_type") == "horizontal-buttons-stack"]
        if not stacks:
            continue
        assert len(stacks) == 1, "One bottom bar per view"
        assert cards[-1] is stacks[0], "The bottom bar must be the last top-level card in the view"
