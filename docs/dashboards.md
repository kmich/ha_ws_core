# Dashboards

Weather Station Core ships five ready-made Lovelace dashboards and one set of drop-in
gauge cards in the `dashboards/` directory. All are copy-paste YAML: no setup beyond
pasting into the raw configuration editor.

| File | What it is | Custom cards needed |
|---|---|---|
| [`weather_dashboard_vanilla.yaml`](#vanilla-dashboard-weather_dashboard_vanillayaml) | Native-cards dashboard that works immediately | none |
| [`weather_dashboard.yaml`](#enhanced-dashboard-weather_dashboardyaml) | Rich, animated two-page dashboard (Weather + Advanced) | `button-card` and six others |
| [`ws_core_dashboard.yaml`](#v20-full-dashboard-ws_core_dashboardyaml) | Six-view dashboard covering every sensor group | `mushroom`, `mini-graph-card` |
| [`ws_core_dashboard_mobile.yaml`](#v20-mobile-dashboard-ws_core_dashboard_mobileyaml) | Single-column phone layout | `mushroom`, `mini-graph-card` |
| [`ws_core_bubble_dashboard.yaml`](#bubble-card-dashboard-ws_core_bubble_dashboardyaml) | Mobile-first dashboard with pop-ups and a bottom bar | Bubble Card v3.2.0+ |
| [`ws_core_gauge_presets.yaml`](#gauge-presets-ws_core_gauge_presetsyaml) | Not a dashboard: gauge cards to paste into your own | none |

---

## Installing a dashboard

1. Open Home Assistant and go to your Lovelace dashboard
2. Click the three-dot menu in the top right and choose **Edit dashboard**
3. Click the three-dot menu again and choose **Raw configuration editor**
4. Replace or merge the YAML content with the dashboard file
5. Save

Alternatively, create a new dashboard: **Settings → Dashboards → Add Dashboard**,
then paste the YAML into the raw editor.

---

## Vanilla Dashboard (`weather_dashboard_vanilla.yaml`)

**No HACS frontend dependencies.** Uses only native Home Assistant cards.
Works immediately after installation.

Best for users who want a functional weather dashboard without installing any
additional HACS frontend integrations.

**Cards used:** `entities`, `gauge`, `history-graph`, `logbook`, `weather-forecast`, `statistic`.

Includes a **Recent Weather Events** logbook card (Station page) showing the last
72h of rain start/stop, frost/thaw, and lightning-strike events from the built-in
event entities.

---

## Enhanced Dashboard (`weather_dashboard.yaml`)

Rich visual layout with colored tiles, animations, and custom card types.

**HACS frontend dependencies required:**

| Integration | HACS type |
|---|---|
| `custom:button-card` | Frontend |
| `custom:mini-graph-card` | Frontend |
| `custom:stack-in-card` | Frontend |
| `custom:config-template-card` | Frontend |
| `custom:windrose-card` | Frontend |
| `card-mod` | Frontend |
| `kiosk-mode` | Frontend |

Install all dependencies from HACS before pasting the dashboard YAML.

**Features:**
- Color-coded temperature, UV, and AQI tiles
- Mini graph cards for 24h temperature and rain trends
- Wind rose card showing direction history
- Station health and data quality badges
- AQI and pollen level display

---

## v2.0 Full Dashboard (`ws_core_dashboard.yaml`)

Six-view dashboard covering the full range of v2.0 sensors.

**Views:**
1. **Now** — current conditions tile grid with weather conditions, temperature,
   rain, wind, nowcast, and alerts
2. **Charts** — 24h and 7-day trend graphs
3. **Advanced** — UTCI, fire risk, ET₀, VPD, pressure trend, forecast agreement
4. **Records** — rain accumulators (today/week/month/year), temperature records,
   streak counters
5. **Diagnostics** — data quality score, sensor drift flags, upload status sensors,
   and a **Recent Weather Events** logbook (rain start/stop, frost/thaw, lightning)
6. **Indoor** — indoor comfort score, temperature and humidity deltas, plus per-room sensors (temp delta, humidity, CO₂ and comfort) for each named room

**HACS frontend dependencies required:** `mushroom`, `mini-graph-card`.

---

## v2.0 Mobile Dashboard (`ws_core_dashboard_mobile.yaml`)

Single-column, touch-optimised layout designed for phones using HA Sections view.
All the same data as the full dashboard but stacked vertically for portrait screens,
including the **Recent Weather Events** logbook card.

**HACS frontend dependencies required:** `mushroom`, `mini-graph-card`.

---

## Bubble Card Dashboard (`ws_core_bubble_dashboard.yaml`)

Mobile-first dashboard built on [Bubble Card](https://github.com/Clooos/Bubble-Card).
One page of summary buttons (temperature, rain, wind, outlook, garden) plus the
provider forecast. Tap a button, or use the bottom bar, to open its pop-up:

| Pop-up | Shows |
|---|---|
| Temperature | 24 h high/low and graph, feels like, dew and frost point, UTCI and WBGT (comfort indices) |
| Rain | Totals, days since rain, nowcast countdown, Pattern Forecast rain chances |
| Wind | Gust, strongest gust in 24 h, Beaufort, direction, 24 h graph |
| Forecast | Pressure trend and sea-level pressure, Pattern Forecast frost / heat / gust with a maturity-and-why table, thunderstorm and fog risk, hourly forecast |
| Garden & Air | ET₀, water deficit, VPD, UV, solar forecast, air quality, pollen, fire risk |
| Station | Data quality, sensor package, battery, stuck sensors, alerts |

Cards for opt-in features only appear when that feature's switch is on, so nothing
shows *unavailable* for features you haven't enabled.

**HACS frontend dependencies required:** Bubble Card **v3.2.0 or later**. The pop-ups use
the standalone format introduced in v3.2.0. Everything else is a built-in card.

---

## Gauge Presets (`ws_core_gauge_presets.yaml`)

Drop-in gauge card snippets with pre-set severity bands for 13 common sensors:
temperature, humidity, pressure, wind speed, wind gust, UV index, rain rate,
rain probability, data quality score, AQI, fire risk score, WBGT, and
(opt-in, v2.7) snow rate.

Uses only the built-in `gauge` card — no HACS dependencies.

Paste individual card definitions into any existing dashboard.

---

## Pattern Forecast card

The Weather dashboard (`weather_dashboard.yaml`) has a Pattern Forecast section at the
end of its Advanced page. It appears once `switch.ws_enable_pattern_forecast` is on and
shows every forecast's chance, maturity and top factors. For any other dashboard, the
[Pattern Forecast guide](guides/pattern_forecast.md#a-dashboard-card) has a native
Markdown card that lists every forecast with its maturity; paste it in.

---

## Keeping dashboards up to date

Dashboards are not auto-updated by HACS. When a new version of ws_core adds entities
referenced in a dashboard update, re-paste the updated YAML from the `dashboards/`
directory.

The CHANGELOG notes dashboard changes per version.

## Streamlined dashboard preview

[ws_core_dashboard_preview.yaml](../dashboards/ws_core_dashboard_preview.yaml) is a
review-only, built-in-card proposal with compact current conditions,
calendar-labeled rain periods, and separate station, package, and prediction
readiness. It does not replace the shipped dashboards. Coverage limitations
and static consumer findings are in [the entity usage and history coverage
ledger](usage_ledger.md) and [per-entity CSV](entity_usage_ledger.csv).
