# Dashboards

Weather Station Core ships with three bundled Lovelace dashboards in the `dashboards/`
directory. All are copy-paste YAML — no additional setup beyond pasting into the
raw configuration editor.

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

**Cards used:** `entities`, `gauge`, `history-graph`, `weather-forecast`, `statistic`.

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
5. **Diagnostics** — data quality score, sensor drift flags, upload status sensors
6. **Indoor** — indoor comfort score, temperature and humidity deltas, plus per-room sensors (temp delta, humidity, CO₂ and comfort) for each named room

**HACS frontend dependencies required:** `mushroom`, `mini-graph-card`.

---

## v2.0 Mobile Dashboard (`ws_core_dashboard_mobile.yaml`)

Single-column, touch-optimised layout designed for phones using HA Sections view.
All the same data as the full dashboard but stacked vertically for portrait screens.

**HACS frontend dependencies required:** `mushroom`, `mini-graph-card`.

---

## Gauge Presets (`ws_core_gauge_presets.yaml`)

Drop-in gauge card snippets with pre-set severity bands for 12 common sensors:
temperature, humidity, UV index, AQI, wind speed, rain rate, fire risk score,
UTCI, VPD, fog probability, thunderstorm risk, and lightning clearance.

Uses only the built-in `gauge` card — no HACS dependencies.

Paste individual card definitions into any existing dashboard.

---

## Keeping dashboards up to date

Dashboards are not auto-updated by HACS. When a new version of ws_core adds entities
referenced in a dashboard update, re-paste the updated YAML from the `dashboards/`
directory.

The CHANGELOG notes dashboard changes per version.
