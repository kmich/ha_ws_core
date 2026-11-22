# Contributing

Contributions are welcome. Please open an issue first to discuss what you'd like to
change, unless it is a straightforward bug fix.

---

## Translations

Eight languages ship with the integration: English, French, German, Dutch, Spanish,
Italian, Portuguese, Polish. Translations cover all 170+ entity names, config flow
strings, state labels, and attribute keys.

To add a new language:
1. Copy `custom_components/ws_core/translations/en.json` to a new file named with
   the [BCP-47 language tag](https://www.iana.org/assignments/language-subtag-registry)
   (e.g. `zh.json` for Simplified Chinese, `sv.json` for Swedish)
2. Translate all values. Keys must not change.
3. Open a PR

**Languages most needed:** Chinese (Simplified), Japanese, Korean, Czech, Swedish,
Norwegian, Finnish, Danish, Turkish.

---

## Bug reports

Use the GitHub issue template. Include:
- Your HA version and ws_core version
- Diagnostics export (Settings → Devices & Services → Weather Station Core → ⋮ →
  Download Diagnostics)
- Relevant log entries with debug logging enabled

---

## Weather station compatibility

If your station brand needs special entity handling (non-standard device class,
unusual unit, etc.), open an issue with your entity IDs and the output of
Developer Tools → States filtered to your station entities.

---

## New forecast providers

The forecast provider system is pluggable. To add a new provider:

1. Create `custom_components/ws_core/providers/your_provider.py`
   - Subclass `ForecastProvider` from `base.py`
   - Implement `async_fetch(session, lat, lon, api_key=None)` using the daily and
     hourly row formats documented in `base.py`. Keep missing values as `None`.
2. Import and register it in `providers/__init__.py`, and describe its forecast
   fields in `providers/capabilities.py`.
3. Add display names to `strings.json` and all `translations/*.json` under
   `forecast_provider` selector options

Open a PR. Include a note on whether the provider requires an API key and any
rate-limiting constraints.

---

## Development setup

```bash
git clone https://github.com/kmich/ha_ws_core
cd ha_ws_core
pip install -r requirements_dev.txt
```

Run tests:
```bash
pytest tests/ -v --tb=short
```

Run linting:
```bash
ruff check custom_components/ tests/ scripts/
ruff format --check custom_components/ tests/ scripts/
```

CI (`.github/workflows/validate.yml`) validates pull requests with the test suite,
Home Assistant compatibility checks, hassfest, HACS validation, Ruff, version
and bytecode checks, dashboard entity validation, and a strict MkDocs build.

---

## Code conventions

- Follow the existing code style (ruff enforces it)
- Declare new derived sensors in `entity_descriptions.py`. Entity ID overrides
  live in `sensor.py`. Regenerate the entity map with `python scripts/generate_entity_map.py`.
- New algorithm code goes in `algorithms.py`
- New coordinator keys go in `const.py` as `KEY_*` constants
- New feature toggles need: `const.py` `CONF_*` + `DEFAULT_*`, `switch.py` entry,
  `strings.json` translation, `en.json` translation, coordinator guard
- All PRs need: passing CI, no new lint warnings, and a CHANGELOG entry under
  `## Unreleased` (or the correct version section)

---

## License

MIT. Contributions are accepted under the same license.
