#!/usr/bin/env python3
"""Validate that every entity referenced in dashboards/*.yaml is a known entity.

Derives the authoritative entity list from:
  - sensor.py  (_slug_for_key overrides dict)
  - switch.py  (CONF_ENABLE_* constants)
  - binary_sensor.py (suggested_object_id slugs)
  - weather.py (suggested_object_id slug)
  - A small set of well-known external entities

Usage:
    python scripts/validate_dashboard_entities.py          # exits 1 on error
    python scripts/validate_dashboard_entities.py --list   # print entity list and exit
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).parent.parent


# ---------------------------------------------------------------------------
# Source-derived entity sets
# ---------------------------------------------------------------------------

def _sensor_entity_ids(prefix: str = "ws") -> set[str]:
    sensor_py = (ROOT / "custom_components/ws_core/sensor.py").read_text()
    start = sensor_py.find("overrides = {")
    end = sensor_py.find("return overrides[key]", start)
    if start == -1 or end == -1:
        sys.exit("ERROR: Could not find overrides dict in sensor.py")
    block = sensor_py[start:end]
    pairs = re.findall(r'(KEY_\w+):\s*"([^"]+)"', block)
    if not pairs:
        sys.exit("ERROR: No KEY_*/slug pairs found in sensor.py overrides dict")
    return {f"sensor.{prefix}_{slug}" for _, slug in pairs}


def _switch_entity_ids(prefix: str = "ws") -> set[str]:
    switch_py = (ROOT / "custom_components/ws_core/switch.py").read_text()
    const_py = (ROOT / "custom_components/ws_core/const.py").read_text()
    conf_keys = set(re.findall(r'CONF_ENABLE_\w+', switch_py))
    ids: set[str] = set()
    for const_name in conf_keys:
        m = re.search(rf'^{const_name}\s*=\s*"([^"]+)"', const_py, re.MULTILINE)
        if m:
            ids.add(f"switch.{prefix}_{m.group(1)}")
    ids.add(f"switch.{prefix}_enable_animations")
    return ids


def _binary_sensor_entity_ids(prefix: str = "ws") -> set[str]:
    """Read suggested_object_id slugs from binary_sensor.py."""
    bs_py = (ROOT / "custom_components/ws_core/binary_sensor.py").read_text()
    # Pattern: f"{prefix}_package_ok" etc.
    slugs = re.findall(r'f"\{prefix\}_([^"]+)"', bs_py)
    return {f"binary_sensor.{prefix}_{slug}" for slug in slugs}


def _weather_entity_ids(prefix: str = "ws") -> set[str]:
    """Weather platform uses suggested_object_id = prefix → weather.{prefix}."""
    return {f"weather.{prefix}"}


KNOWN_EXTERNAL: set[str] = {
    "sun.sun",
    "select.ws_graph_range",
    "input_text.weather_background_path",
    "input_text.weather_station_location",
    "input_text.weather_lightning_sensor",
}


def build_known_entities(prefix: str = "ws") -> set[str]:
    return (
        _sensor_entity_ids(prefix)
        | _switch_entity_ids(prefix)
        | _binary_sensor_entity_ids(prefix)
        | _weather_entity_ids(prefix)
        | KNOWN_EXTERNAL
    )


# ---------------------------------------------------------------------------
# Dashboard reference extraction
# ---------------------------------------------------------------------------

_ENTITY_RE = re.compile(
    r"""(?:entity:\s*|states\s*\[['"])"""
    r"""((?:sensor|switch|select|sun|input_text|binary_sensor|weather)\.[\w]+)"""
)


def _dashboard_entity_refs(yaml_path: pathlib.Path) -> dict[str, list[int]]:
    refs: dict[str, list[int]] = {}
    for lineno, line in enumerate(yaml_path.read_text().splitlines(), 1):
        for m in _ENTITY_RE.finditer(line):
            eid = m.group(1)
            refs.setdefault(eid, []).append(lineno)
    return refs


# ---------------------------------------------------------------------------
# Validation / list
# ---------------------------------------------------------------------------

def validate(prefix: str = "ws", verbose: bool = False) -> bool:
    known = build_known_entities(prefix)
    dashboards = sorted((ROOT / "dashboards").glob("*.yaml"))
    if not dashboards:
        print("WARNING: No dashboard YAML files found under dashboards/")
        return True

    all_ok = True
    for dash_path in dashboards:
        refs = _dashboard_entity_refs(dash_path)
        broken = {eid: lines for eid, lines in refs.items() if eid not in known}
        if broken:
            all_ok = False
            print(f"\n❌ {dash_path.name}: {len(broken)} broken entity ref(s)")
            for eid, lines in sorted(broken.items()):
                line_str = ", ".join(str(l) for l in lines[:5])
                if len(lines) > 5:
                    line_str += f" (+{len(lines)-5} more)"
                print(f"   BROKEN  {eid}  (lines: {line_str})")
        else:
            print(f"✓ {dash_path.name}: all {len(refs)} entity refs valid")
            if verbose:
                for eid in sorted(refs):
                    print(f"   {eid}")

    return all_ok


def list_entities(prefix: str = "ws") -> None:
    known = build_known_entities(prefix)
    for domain in ("sensor", "switch", "binary_sensor", "weather", "select", "sun", "input_text"):
        subset = sorted(e for e in known if e.startswith(f"{domain}."))
        if subset:
            print(f"\n# {domain} ({len(subset)})")
            for e in subset:
                print(f"  {e}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--prefix", default="ws", help="Entity prefix (default: ws)")
    parser.add_argument("--list", action="store_true", help="Print all known entity IDs and exit")
    parser.add_argument("--verbose", "-v", action="store_true", help="Print all refs, not just broken ones")
    args = parser.parse_args()

    if args.list:
        list_entities(args.prefix)
        sys.exit(0)

    ok = validate(prefix=args.prefix, verbose=args.verbose)
    if not ok:
        print("\nFAILED: Fix broken entity references before merging.")
        sys.exit(1)
    print("\nAll dashboards pass entity validation.")


if __name__ == "__main__":
    main()
