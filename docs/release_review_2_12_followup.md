# 2.13.0 release review and migration notes

This document describes the 2.13.0 changes built on 2.12.0. Publishing the
release does not install it on a Home Assistant instance or change live state.

## Correctness and entity contract

| Handoff item | Disposition | Review note |
|---|---|---|
| A: health and quality | Fixed | Required mappings, unavailable or stale readings, and diagnostic flags now affect public health and quality outputs. Drift deductions count diagnostic details. Configuration, source, and model readiness are exposed separately. |
| B: solar and daily ET₀ | Fixed for live sampled days | Solar accumulation no longer depends on Hargreaves extrema. Daily Penman–Monteith uses one completed local day of radiation and same-day weather observations, with coverage and reason metadata. Zero and missing radiation differ; old totals without coverage evidence cannot authorize a daily result. |
| C: forecast factors | Fixed | Physical labels use raw conditions and explicit windows/thresholds while contribution strength remains model-based. Translations and dashboard wording were updated. |
| D: warm-start recovery | Fixed for tested restart and recorder paths | Pressure hydration runs independently of annual replay; recorder failures have bounded retries. A recovered public prediction is issued on the next eligible sample or quarter-hour mark without duplicate pending predictions. |
| E: feature prerequisites | Fixed for affected families | Remote PV forecast, local ET₀, solar readings, irrigation, and FWI components have coherent selection rules. A temporary source outage leaves its configured entity registered. |
| F: registration defaults | Fixed | Description defaults now reach the Home Assistant entity boundary. Primary FWI is enabled for a new Fire Risk registration; 34 specialist descriptions remain disabled by default. Existing registry choices and names are not rewritten. |
| G: historical coverage | Partially delivered; backfill deferred | The review ledger distinguishes installation-limited coordinator metrics from Pattern recorder replay. Broad coverage metadata and recorder backfill need verified reset, retention, unit, and overlap semantics before implementation. |

## Migration behavior

- Unique IDs and existing entity IDs are unchanged. Home Assistant's registry
  keeps user renames and enabled/disabled choices, including the seventeen
  entities explicitly enabled during the audit. New defaults affect only newly
  registered entities.
- Existing solar energy totals remain in storage for display. Legacy records
  lack the period and coverage evidence required for daily Penman–Monteith;
  that output remains unknown until a newly observed, sufficiently covered day
  completes. The new solar metadata is versioned and validated on restore.
- FWI Components selection now runs the FWI calculation even when the primary
  Fire Risk display switch is off. Composite FWI and DSR entities still follow
  the primary switch. The new FWI default does not override existing registry
  settings.
- Local daily ET₀ is selected by a mapped radiation sensor, or a mapped lux
  sensor with the explicit illuminance fallback. The Solar PV Forecast switch
  controls remote generation predictions only.
- The streamlined dashboard is a preview. Existing shipped dashboards and
  users' saved dashboards are unchanged. No entity is proposed for disablement.

## Verification and remaining release gates

- Local verification on the integrated branch: 1,045 tests passed with the
  Home Assistant and asyncio fixture plugins enabled; Ruff lint and format
  checks passed; all shipped dashboard entity references validated.
- Draft PR CI passed the full 1,045-test suite, lint, HACS validation,
  hassfest, dashboard validation, version consistency, and bytecode check.
  A separate job passed 210 entity-contract tests on the declared minimum
  Home Assistant 2024.6.0. That minimum-version job is a focused compatibility
  check, not a full lifecycle or live installation test.
- Inspect the dashboard preview with a fresh registry and verify a supported
  Home Assistant version before making it the default view.
- After an approved deployment, perform a live smoke check of source health,
  completed-day ET₀ coverage, forecast recovery, entity registry choices, and
  the seventeen explicitly enabled entities. No live state was changed here.
- Confirm Pattern store-load timing at quarter-hour restart offsets in a live
  Home Assistant instance. The isolated tests cover public recovery and bounded
  retries, but not every runtime scheduling offset.
- Historical replay event counts still need independent comparison with source
  hourly min/max over a bounded period. User-specific dashboards, automations,
  Node-RED, and external clients remain outside the repository usage scan.

The [entity contract](entity_contracts.md), [usage and coverage ledger](usage_ledger.md),
and [dashboard preview](https://github.com/kmich/ha_ws_core/blob/main/dashboards/ws_core_dashboard_preview.yaml) provide
the review evidence and the proposed everyday presentation.
