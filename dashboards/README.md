# Weather Station Core — Dashboards

Ready-to-use Lovelace dashboards for Weather Station Core. All entity IDs assume
the default `ws` prefix — if you used a different prefix, replace `ws` throughout.

## Available dashboards

| File | Description | Required custom cards |
|---|---|---|
| `weather_dashboard_vanilla.yaml` | Five views (Weather / Radar / Station / Activities / Windows) using only native Home Assistant cards. | none |
| `weather_dashboard.yaml` | Rich animated two-page dashboard (Weather + Advanced), including the opt-in Pattern Forecast section. | `button-card`, `mini-graph-card`, `stack-in-card`, `config-template-card`, `windrose-card`, `card-mod`, `kiosk-mode` |
| `ws_core_dashboard.yaml` | **v3.0** full 7-view dashboard: Now / Charts / Advanced / Records / Diagnostics / Indoor / Windows. Covers core, comfort, fire, agro, solar, upload status, data quality, events and Weather Windows. | `mushroom`, `mini-graph-card` |
| `ws_core_dashboard_mobile.yaml` | **v2.0** single-column, touch-optimised layout for phones (HA Sections). | `mushroom`, `mini-graph-card` |
| `ws_core_bubble_dashboard.yaml` | **v2.13.4** mobile-first dashboard in one centred column: alert banner, summary buttons, the adaptive rain chance and what the integration is learning, six pop-ups (Temperature / Rain / Wind / Forecast with Pattern Forecast / Garden & Air / Station) and a bottom bar. | Bubble Card **v3.2.0+** |
| `ws_core_gauge_presets.yaml` | **v2.0** drop-in gauge cards with sensible severity bands for 13 common sensors. Not a dashboard: copy individual cards into any view. | none (built-in `gauge` card) |

## Installation

**Paste a whole dashboard:**

1. Settings → Dashboards → **Add Dashboard** → *New dashboard from scratch* (give it a name).
2. Open it → top-right ⋮ → **Edit Dashboard** → ⋮ → **Raw configuration editor**.
3. Paste the contents of the chosen `.yaml` file and **Save**.

**Use just a few cards (e.g. the gauges):**

1. Edit any dashboard → **Add Card** → *Manual*.
2. Paste a single card block from `ws_core_gauge_presets.yaml`.

## Notes

- Cards referencing optional sensors (comfort indices, fire risk, lightning,
  indoor, degree days, uploads) only show data when that feature group is
  enabled. Use **Configure → Features & Diagnostics** for optional features,
  **Indoor Rooms** for room sensors, and **Decision Engine & Weather Windows**
  for activity profiles. Cards for missing entities can be removed.
- Install custom cards from **Settings → Marketplace** on Home Assistant 2026.11
  and newer. On earlier versions, use HACS. Home Assistant shows "Custom element
  doesn't exist" if a required card is missing.
- To change the prefix, do a find-and-replace of `ws_` → `yourprefix_` and
  `weather.ws` → `weather.yourprefix` in the pasted YAML.
