# Contributing to Weather Station Core

Thanks for your interest in improving `ws_core`. Contributions of code, translations,
documentation, hardware-mapping notes, and forecast providers are all welcome.

Please open an issue to discuss anything non-trivial before starting, so we can agree on
the approach.

## Quick start

```bash
pip install -r requirements_dev.txt
python -m pytest          # run the test suite
ruff check custom_components/
ruff format --check custom_components/
python scripts/validate_dashboard_entities.py
```

All of the above run in CI (`.github/workflows/validate.yml`); please make sure they pass
locally before opening a pull request.

## Where things live

- Meteorological math: `custom_components/ws_core/algorithms.py` (pure functions, unit-tested).
- Data pipeline: `custom_components/ws_core/coordinator.py`.
- Config / options flow: `custom_components/ws_core/config_flow.py`.
- Dashboards, blueprints, and docs: `dashboards/`, `blueprints/`, `docs/`.

## Guidelines

- Do not change a formula without a test and a `CHANGELOG.md` entry documenting the
  before/after behaviour.
- Preserve `unique_id`s and default entity ids; deprecate rather than delete.
- Never hardcode a location, latitude, hemisphere, unit system, or device name.

The full contribution guide, including the translation and forecast-provider workflows,
lives in [docs/contributing.md](docs/contributing.md).

## Reporting bugs

Use the GitHub issue templates and attach your diagnostics export (credentials and
coordinates are redacted automatically). See [SECURITY.md](SECURITY.md) for security
issues.
