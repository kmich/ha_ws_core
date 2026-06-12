# Contributing

Contributions are welcome. Please open an issue first to discuss what you'd like to
change, unless it is a straightforward bug fix.

---

## Translations

Eight languages ship with the integration: English, French, German, Dutch, Spanish,
Italian, Portuguese, Polish. Translations cover all 150+ entity names, config flow
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
   - Implement `async_fetch(session, lat, lon, api_key=None)` returning the
     normalised 7-day daily + 24h hourly format documented in `base.py`
2. Add one line to `providers/__init__.py`: `"your_id": YourProvider`
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
ruff check custom_components/
ruff format --check custom_components/
```

CI runs automatically on PRs to `main`. All six jobs must pass: hassfest, HACS
validation, lint, tests, no-bytecode, and version consistency.

---

## Code conventions

- Follow the existing code style (ruff enforces it)
- New sensors go in `sensor.py` with a `WSSensorDescription` entry
- New algorithm code goes in `algorithms.py`
- New coordinator keys go in `const.py` as `KEY_*` constants
- New feature toggles need: `const.py` `CONF_*` + `DEFAULT_*`, `switch.py` entry,
  `strings.json` translation, `en.json` translation, coordinator guard
- All PRs need: passing CI, no new lint warnings, and a CHANGELOG entry under
  `## Unreleased` (or the correct version section)

---

## License

MIT. Contributions are accepted under the same license.
