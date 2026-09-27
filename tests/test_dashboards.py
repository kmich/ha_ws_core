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
