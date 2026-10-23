"""Docs, blueprints and release metadata for Pattern Forecast."""

from __future__ import annotations

import json
import pathlib
import re

import jinja2
import pytest
import yaml

ROOT = pathlib.Path(__file__).parent.parent
DOCS = ROOT / "docs"
NEW_ANCHORS = {
    "sensors.md": "pattern-forecast",
    "science.md": "pattern-forecast",
    "troubleshooting.md": "pattern-forecast",
}
EDITED = ["index.md", "quickstart.md", "use_cases.md", "blueprints.md", "dashboards.md", "forecast_providers.md"]


def _anchors(path: pathlib.Path) -> set[str]:
    out = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^#{1,6}\s+(.*)$", line)
        if not m:
            continue
        explicit = re.search(r"\{#([\w-]+)\}", m.group(1))
        if explicit:
            out.add(explicit.group(1))
        else:
            t = re.sub(r"[^\w\s-]", "", m.group(1).strip().lower())
            out.add(re.sub(r"\s+", "-", t).strip("-"))
    return out


def test_nav_lists_the_guide():
    cfg = yaml.safe_load((ROOT / "mkdocs.yml").read_text(encoding="utf-8"))
    guides = next(item["Guides"] for item in cfg["nav"] if "Guides" in item)
    assert {"Pattern Forecast": "guides/pattern_forecast.md"} in guides
    assert (DOCS / "guides/pattern_forecast.md").exists()


@pytest.mark.parametrize(("page", "anchor"), NEW_ANCHORS.items())
def test_launch_urls_have_their_anchors(page, anchor):
    assert anchor in _anchors(DOCS / page)


def test_relative_links_and_anchors_resolve():
    """mkdocs build --strict runs in CI; this catches broken links without needing mkdocs."""
    pages = ["guides/pattern_forecast.md", *NEW_ANCHORS, *EDITED]
    for page in pages:
        path = DOCS / page
        for m in re.finditer(r"\]\(([^)\s]+)\)", path.read_text(encoding="utf-8")):
            link = m.group(1)
            if re.match(r"^(https?:|mailto:)", link):
                continue
            target, _, frag = link.partition("#")
            tgt = (path.parent / target).resolve() if target else path.resolve()
            assert tgt.exists(), (page, link)
            if frag and tgt.suffix == ".md":
                assert frag in _anchors(tgt), (page, link)


def test_no_em_dash_in_new_text():
    em = chr(0x2014)
    assert em not in (DOCS / "guides/pattern_forecast.md").read_text(encoding="utf-8")
    for name in ("pattern_forecast.py", "pattern_runtime.py", "pattern_sources.py"):
        assert em not in (ROOT / "custom_components/ws_core" / name).read_text(encoding="utf-8")
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    section = changelog.split("## [2.11.0]", 1)[1].split("\n## [", 1)[0]
    assert em not in section


def test_guide_has_the_comparison_table_and_uses_the_ws90():
    guide = (DOCS / "guides/pattern_forecast.md").read_text(encoding="utf-8")
    for needle in ("rain_probability", "rain_probability_combined", "Nowcast", "Pattern Forecast", "Shelly WS90"):
        assert needle in guide
    assert "maturity" in guide and "skilled" in guide


def test_guide_claims_no_accuracy_numbers():
    guide = (DOCS / "guides/pattern_forecast.md").read_text(encoding="utf-8").lower()
    assert not re.search(r"\b\d+\s*%\s*(accurate|accuracy|correct)", guide)
    assert "accuracy figures" in guide


def test_dashboard_card_template_renders():
    guide = (DOCS / "guides/pattern_forecast.md").read_text(encoding="utf-8")
    card = yaml.safe_load(re.search(r"```yaml\n(type: markdown\n.*?)```", guide, re.S).group(1))
    env = jinja2.Environment()
    env.globals.update(
        states=lambda e: "42.4" if e.endswith("rain_1h") else "unknown",
        is_number=lambda v: v.replace(".", "", 1).isdigit(),
        state_attr=lambda e, a: "learning" if e.endswith("rain_1h") else None,
    )
    out = env.from_string(card["content"]).render()
    assert "| Rain, next 1 h | 42 % | learning |" in out
    assert "| Frost, next 12 h | - | n/a |" in out


def test_readme_entry_is_honest():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    entry = next(line for line in readme.splitlines() if "Pattern Forecast (opt-in)" in line)
    for needle in ("probabilities", "needs time to learn", "100% local", "optional, labelled", "kmich.github.io"):
        assert needle in entry
    assert "Pattern Forecast storm data" in readme  # privacy table row


class _Loader(yaml.SafeLoader):
    pass


_Loader.add_constructor("!input", lambda loader, node: f"<input:{loader.construct_scalar(node)}>")


def _load_blueprint(name: str) -> dict:
    return yaml.load((ROOT / f"blueprints/automation/ws_core/{name}.yaml").read_text(encoding="utf-8"), Loader=_Loader)


@pytest.mark.parametrize("name", ["frost_alert", "freeze_alert"])
def test_blueprint_early_warning_input(name):
    bp = _load_blueprint(name)
    inputs = bp["blueprint"]["input"]
    assert inputs["pattern_frost_sensor"]["default"] == ""  # empty = unchanged behaviour
    assert inputs["pattern_frost_threshold"]["default"] == 50
    assert [t["platform"] for t in bp["trigger"]] == ["numeric_state", "template"]
    assert set(bp["trigger_variables"]) == {"pattern_sensor", "pattern_threshold"}

    tpl = bp["trigger"][1]["value_template"]
    env = jinja2.Environment()
    env.filters["is_number"] = lambda v: str(v).replace(".", "", 1).isdigit()

    def fires(sensor, state, maturity, threshold=50):
        out = env.from_string(tpl).render(
            pattern_sensor=sensor,
            pattern_threshold=threshold,
            states=lambda e: state,
            state_attr=lambda e, a: maturity,
        )
        return out.strip() == "True"

    assert not fires("", None, None)  # input left empty: never fires
    assert fires("sensor.ws_pattern_frost_12h", "70", "skilled")
    assert not fires("sensor.ws_pattern_frost_12h", "70", "learning")  # only while skilled
    assert not fires("sensor.ws_pattern_frost_12h", "70", "collecting")
    assert not fires("sensor.ws_pattern_frost_12h", "30", "skilled")
    assert not fires("sensor.ws_pattern_frost_12h", "unknown", "skilled")


def test_original_temperature_trigger_is_untouched():
    first = _load_blueprint("frost_alert")["trigger"][0]
    assert first["platform"] == "numeric_state" and first["below"] == "<input:freeze_threshold>"
    first = _load_blueprint("freeze_alert")["trigger"][0]
    assert first["platform"] == "numeric_state" and first["below"] == "<input:threshold>"


def test_versions_are_consistent_at_2_11_0():
    manifest = json.loads((ROOT / "custom_components/ws_core/manifest.json").read_text(encoding="utf-8"))
    assert manifest["version"] == "2.11.0"
    assert manifest["requirements"] == []
    assert 'version = "2.11.0"' in (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert '_INTEGRATION_VERSION = "2.11.0"' in (ROOT / "custom_components/ws_core/const.py").read_text(
        encoding="utf-8"
    )
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "## [2.11.0]" in changelog and "## [Unreleased]" not in changelog
    section = changelog.split("## [2.11.0]", 1)[1].split("\n## [", 1)[0]
    assert "Pattern Forecast" in section and "neighbor qc" in section.lower()
