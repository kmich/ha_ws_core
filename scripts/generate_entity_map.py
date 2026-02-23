#!/usr/bin/env python3
"""Generate docs/entity_map.html — a visual entity map for WS Core.

Derives everything from source code (sensor.py, switch.py, manifest.json).
Injects: version, generation timestamp, sensor count.
Never hand-maintained.

Usage:
    python scripts/generate_entity_map.py
    python scripts/generate_entity_map.py --output path/to/output.html
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).parent.parent


# ---------------------------------------------------------------------------
# Source extraction
# ---------------------------------------------------------------------------

def _manifest() -> dict:
    return json.loads((ROOT / "custom_components/ws_core/manifest.json").read_text())


def _sensor_descriptions() -> list[dict]:
    sensor_py = (ROOT / "custom_components/ws_core/sensor.py").read_text()

    # Slug overrides: KEY_* -> "slug"
    start = sensor_py.find("overrides = {")
    end = sensor_py.find("return overrides[key]", start)
    if start == -1 or end == -1:
        sys.exit("ERROR: Could not find overrides dict in sensor.py")
    block = sensor_py[start:end]
    slug_map: dict[str, str] = dict(re.findall(r'(KEY_\w+):\s*"([^"]+)"', block))

    # _FEATURE_TOGGLE_MAP
    tm_start = sensor_py.find("_FEATURE_TOGGLE_MAP")
    tm_end = sensor_py.find("\n}", tm_start) + 2
    tm_block = sensor_py[tm_start:tm_end]
    toggle_map: dict[str, str] = dict(re.findall(r'(KEY_\w+):\s*(CONF_\w+)', tm_block))

    # _DISABLED_BY_DEFAULT
    db_start = sensor_py.find("_DISABLED_BY_DEFAULT")
    db_end = sensor_py.find("\n    }", db_start) + 6
    db_block = sensor_py[db_start:db_end]
    disabled: set[str] = set(re.findall(r'KEY_\w+', db_block))

    # Parse WSSensorDescription entries
    sensors_start = sensor_py.find("SENSORS: list[WSSensorDescription] = [")
    sensors_end = sensor_py.find("\n# Sensor-to-feature-toggle mapping", sensors_start)
    sensors_block = sensor_py[sensors_start:sensors_end]

    descs = []
    for m in re.finditer(r'WSSensorDescription\((.+?)\n    \)', sensors_block, re.DOTALL):
        body = m.group(1)
        key_m = re.search(r'key=(KEY_\w+)', body)
        if not key_m:
            continue
        key = key_m.group(1)
        slug = slug_map.get(key)
        if not slug:
            continue

        name_m = re.search(r'name="([^"]+)"', body)
        unit_m = re.search(r'native_unit="([^"]+)"', body)
        cat_m = re.search(r'EntityCategory\.(\w+)', body)
        has_attrs = "attrs_fn" in body

        descs.append({
            "key": key,
            "slug": slug,
            "entity_id": f"sensor.ws_{slug}",
            "name": name_m.group(1) if name_m else key,
            "unit": unit_m.group(1) if unit_m else None,
            "category": cat_m.group(1) if cat_m else None,
            "has_attrs": has_attrs,
            "toggle": toggle_map.get(key),
            "disabled_default": key in disabled,
        })

    return descs


def _switch_entities() -> list[dict]:
    switch_py = (ROOT / "custom_components/ws_core/switch.py").read_text()
    const_py = (ROOT / "custom_components/ws_core/const.py").read_text()
    conf_keys = set(re.findall(r'CONF_ENABLE_\w+', switch_py))
    switches = []
    for const_name in sorted(conf_keys):
        m = re.search(rf'^{const_name}\s*=\s*"([^"]+)"', const_py, re.MULTILINE)
        if m:
            switches.append({"entity_id": f"switch.ws_{m.group(1)}", "const": const_name})
    switches.append({"entity_id": "switch.ws_enable_animations", "const": "static"})
    return sorted(switches, key=lambda x: x["entity_id"])


# ---------------------------------------------------------------------------
# Section assignment
# ---------------------------------------------------------------------------

_SECTION_MAP: dict[str, str] = {
    "KEY_NORM_TEMP_C": "Core Measurements", "KEY_DEW_POINT_C": "Core Measurements",
    "KEY_NORM_HUMIDITY": "Core Measurements", "KEY_NORM_PRESSURE_HPA": "Core Measurements",
    "KEY_SEA_LEVEL_PRESSURE_HPA": "Core Measurements", "KEY_NORM_WIND_SPEED_MS": "Core Measurements",
    "KEY_NORM_WIND_GUST_MS": "Core Measurements", "KEY_NORM_WIND_DIR_DEG": "Core Measurements",
    "KEY_NORM_RAIN_TOTAL_MM": "Core Measurements", "KEY_RAIN_RATE_RAW": "Core Measurements",
    "KEY_RAIN_RATE_FILT": "Core Measurements", "KEY_LUX": "Core Measurements",
    "KEY_UV": "Core Measurements", "KEY_BATTERY_PCT": "Core Measurements",
    "KEY_DATA_QUALITY": "Diagnostics", "KEY_PACKAGE_STATUS": "Diagnostics",
    "KEY_SENSOR_QUALITY_FLAGS": "Diagnostics", "KEY_ALERT_STATE": "Diagnostics",
    "KEY_ALERT_MESSAGE": "Diagnostics", "KEY_FORECAST": "Diagnostics",
    "KEY_PRESSURE_TREND_HPAH": "Diagnostics", "KEY_PRESSURE_CHANGE_WINDOW_HPA": "Diagnostics",
    "KEY_WIND_DIR_SMOOTH_DEG": "Diagnostics", "KEY_ZAMBRETTI_NUMBER": "Diagnostics",
    "KEY_FEELS_LIKE_C": "Advanced Meteorological", "KEY_WET_BULB_C": "Advanced Meteorological",
    "KEY_FROST_POINT_C": "Advanced Meteorological", "KEY_ZAMBRETTI_FORECAST": "Advanced Meteorological",
    "KEY_WIND_BEAUFORT": "Advanced Meteorological", "KEY_WIND_QUADRANT": "Advanced Meteorological",
    "KEY_CURRENT_CONDITION": "Advanced Meteorological", "KEY_RAIN_PROBABILITY": "Advanced Meteorological",
    "KEY_RAIN_PROBABILITY_COMBINED": "Advanced Meteorological", "KEY_RAIN_DISPLAY": "Advanced Meteorological",
    "KEY_RAIN_ACCUM_1H": "Advanced Meteorological", "KEY_RAIN_ACCUM_24H": "Advanced Meteorological",
    "KEY_TIME_SINCE_RAIN": "Advanced Meteorological", "KEY_PRESSURE_TREND_DISPLAY": "Advanced Meteorological",
    "KEY_HEALTH_DISPLAY": "Advanced Meteorological", "KEY_FORECAST_TILES": "Advanced Meteorological",
    "KEY_TEMP_HIGH_24H": "24h Statistics", "KEY_TEMP_LOW_24H": "24h Statistics",
    "KEY_TEMP_AVG_24H": "24h Statistics", "KEY_WIND_GUST_MAX_24H": "24h Statistics",
    "KEY_HUMIDITY_LEVEL_DISPLAY": "Display Sensors", "KEY_UV_LEVEL_DISPLAY": "Display Sensors",
    "KEY_TEMP_DISPLAY": "Display Sensors",
    "KEY_LAUNDRY_SCORE": "Activity Scores", "KEY_STARGAZE_SCORE": "Activity Scores",
    "KEY_FIRE_RISK_SCORE": "Activity Scores", "KEY_RUNNING_SCORE": "Activity Scores",
    "KEY_SEA_SURFACE_TEMP": "Sea Temperature",
    "KEY_HDD_TODAY": "Degree Days & ET₀", "KEY_CDD_TODAY": "Degree Days & ET₀",
    "KEY_HDD_RATE": "Degree Days & ET₀", "KEY_CDD_RATE": "Degree Days & ET₀",
    "KEY_ET0_DAILY_MM": "Degree Days & ET₀", "KEY_ET0_HOURLY_MM": "Degree Days & ET₀",
    "KEY_ET0_PM_DAILY_MM": "Degree Days & ET₀",
    "KEY_METAR_VALIDATION": "METAR", "KEY_METAR_TEMP_C": "METAR",
    "KEY_METAR_PRESSURE_HPA": "METAR", "KEY_METAR_DELTA_TEMP": "METAR",
    "KEY_METAR_DELTA_PRESSURE": "METAR",
    "KEY_CWOP_STATUS": "Upload / Export", "KEY_WU_STATUS": "Upload / Export",
    "KEY_LAST_EXPORT_TIME": "Upload / Export",
    "KEY_AQI": "Air Quality", "KEY_AQI_LEVEL": "Air Quality",
    "KEY_PM2_5": "Air Quality", "KEY_PM10": "Air Quality",
    "KEY_NO2": "Air Quality", "KEY_OZONE": "Air Quality",
    "KEY_POLLEN_OVERALL": "Pollen", "KEY_POLLEN_GRASS": "Pollen",
    "KEY_POLLEN_TREE": "Pollen", "KEY_POLLEN_WEED": "Pollen",
    "KEY_MOON_DISPLAY": "Moon", "KEY_MOON_PHASE": "Moon", "KEY_MOON_ILLUMINATION_PCT": "Moon",
    "KEY_SOLAR_FORECAST_TODAY_KWH": "Solar Forecast",
    "KEY_SOLAR_FORECAST_TOMORROW_KWH": "Solar Forecast",
}

_SECTIONS = [
    ("Core Measurements", "🌡️"),
    ("Diagnostics", "🔧"),
    ("Advanced Meteorological", "⚡"),
    ("24h Statistics", "📊"),
    ("Display Sensors", "🖥️"),
    ("Activity Scores", "🏃"),
    ("Sea Temperature", "🌊"),
    ("Degree Days & ET₀", "🌱"),
    ("METAR", "✈️"),
    ("Upload / Export", "📡"),
    ("Air Quality", "💨"),
    ("Pollen", "🌸"),
    ("Moon", "🌙"),
    ("Solar Forecast", "☀️"),
]


# ---------------------------------------------------------------------------
# HTML generation
# ---------------------------------------------------------------------------

def _badge(desc: dict) -> str:
    parts = []
    if desc.get("toggle"):
        label = desc["toggle"].replace("CONF_ENABLE_", "").lower().replace("_", "-")
        parts.append(f'<span class="badge cond" title="Requires {desc["toggle"]} = on">gated:{label}</span>')
    elif desc.get("category") == "DIAGNOSTIC":
        parts.append('<span class="badge diag">diagnostic</span>')
    else:
        parts.append('<span class="badge ok">always-on</span>')
    if desc["has_attrs"]:
        parts.append('<span class="badge attrs">attrs</span>')
    if desc["disabled_default"]:
        parts.append('<span class="badge off">off-default</span>')
    return " ".join(parts)


def generate_html(sensors: list[dict], switches: list[dict], manifest: dict) -> str:
    version = manifest.get("version", "unknown")
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    sections_html = ""
    ungrouped = []
    for sec_name, icon in _SECTIONS:
        rows = [d for d in sensors if _SECTION_MAP.get(d["key"]) == sec_name]
        if not rows:
            continue
        rows_html = ""
        for d in rows:
            unit = f" <small style='color:#64748b'>· {d['unit']}</small>" if d["unit"] else ""
            rows_html += f"""
        <tr>
          <td><code>sensor.ws_{d['slug']}</code></td>
          <td>{d['name']}{unit}</td>
          <td>{_badge(d)}</td>
        </tr>"""
        sections_html += f"""
  <section>
    <h2><span class="sec-icon">{icon}</span> {sec_name} <span class="count">({len(rows)})</span></h2>
    <table>
      <thead><tr><th>Entity ID</th><th>Name</th><th>Flags</th></tr></thead>
      <tbody>{rows_html}</tbody>
    </table>
  </section>"""

    # Any sensors not in section map
    mapped_keys = set(_SECTION_MAP.keys())
    ungrouped = [d for d in sensors if d["key"] not in mapped_keys]
    if ungrouped:
        rows_html = ""
        for d in ungrouped:
            rows_html += f"""
        <tr><td><code>sensor.ws_{d['slug']}</code></td><td>{d['name']}</td><td>{_badge(d)}</td></tr>"""
        sections_html += f"""
  <section>
    <h2>❓ Uncategorised <span class="count">({len(ungrouped)})</span></h2>
    <table><thead><tr><th>Entity ID</th><th>Name</th><th>Flags</th></tr></thead>
    <tbody>{rows_html}</tbody></table>
  </section>"""

    sw_rows = ""
    for sw in switches:
        sw_rows += f"""
        <tr><td><code>{sw['entity_id']}</code></td><td>Feature toggle</td><td><span class="badge ok">always-on</span></td></tr>"""
    sections_html += f"""
  <section>
    <h2><span class="sec-icon">🔀</span> Feature Switches <span class="count">({len(switches)})</span></h2>
    <table>
      <thead><tr><th>Entity ID</th><th>Type</th><th>Flags</th></tr></thead>
      <tbody>{sw_rows}</tbody>
    </table>
  </section>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>WS Core {version} — Entity Map</title>
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#0f1117;color:#e2e8f0;font-family:system-ui,sans-serif;padding:24px 20px;max-width:1050px;margin:0 auto}}
header{{border-bottom:1px solid #2d3748;padding-bottom:18px;margin-bottom:24px}}
h1{{font-size:21px;font-weight:700;color:#f8fafc}}
.meta{{display:flex;gap:18px;flex-wrap:wrap;font-size:12px;color:#64748b;margin-top:8px}}
.legend{{display:flex;gap:10px;flex-wrap:wrap;font-size:11px;margin-bottom:20px}}
section{{margin-bottom:24px}}
h2{{font-size:14px;font-weight:600;color:#94a3b8;background:#1e2533;padding:6px 12px;border-radius:8px;border-left:3px solid #3b82f6;margin-bottom:6px}}
.sec-icon{{margin-right:4px}}
.count{{font-size:11px;font-weight:400;color:#64748b}}
table{{width:100%;border-collapse:collapse;font-size:12px}}
th{{text-align:left;padding:5px 10px;color:#4b5563;font-weight:600;border-bottom:1px solid #1e2533}}
td{{padding:4px 10px;border-bottom:1px solid #1a1f2e;vertical-align:middle}}
tr:hover td{{background:rgba(255,255,255,.025)}}
code{{font-family:'Courier New',monospace;color:#93c5fd;font-size:11px}}
small{{font-size:10px}}
.badge{{display:inline-block;font-size:10px;padding:1px 5px;border-radius:3px;font-weight:600;margin-right:2px;white-space:nowrap}}
.badge.ok{{background:rgba(16,185,129,.15);color:#34d399;border:1px solid rgba(16,185,129,.3)}}
.badge.diag{{background:rgba(99,102,241,.15);color:#a5b4fc;border:1px solid rgba(99,102,241,.3)}}
.badge.cond{{background:rgba(20,184,166,.15);color:#5eead4;border:1px solid rgba(20,184,166,.3)}}
.badge.attrs{{background:rgba(251,191,36,.12);color:#fbbf24;border:1px solid rgba(251,191,36,.3)}}
.badge.off{{background:rgba(100,116,139,.12);color:#94a3b8;border:1px solid rgba(100,116,139,.3)}}
</style>
</head>
<body>
<header>
  <h1>⛅ Weather Station Core — Entity Map</h1>
  <div class="meta">
    <span>🔖 v{version}</span>
    <span>📦 {len(sensors)} sensor entities + {len(switches)} switches</span>
    <span>🕐 Generated {generated}</span>
  </div>
</header>
<div class="legend">
  <span class="badge ok">always-on</span> Always registered
  <span class="badge diag">diagnostic</span> EntityCategory.DIAGNOSTIC
  <span class="badge cond">gated:*</span> Requires feature switch ON
  <span class="badge attrs">attrs</span> Exposes extra_state_attributes
  <span class="badge off">off-default</span> Disabled by default in entity registry
</div>
{sections_html}
</body>
</html>"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output", default="docs/entity_map.html")
    args = parser.parse_args()

    sensors = _sensor_descriptions()
    switches = _switch_entities()
    manifest = _manifest()

    html = generate_html(sensors, switches, manifest)
    out = ROOT / args.output
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    v = manifest["version"]
    print(f"Generated {out}  ({len(sensors)} sensors, {len(switches)} switches, v{v})")


if __name__ == "__main__":
    main()
