# Weather Station Core adoption, documentation, marketing, and distribution audit

**Audit date:** 2026-07-11  
**Repository:** <https://github.com/kmich/ha_ws_core>  
**Evidence convention:** **Fact** = observed in the repository, GitHub API, or a cited primary source; **Inference** = conclusion from those facts; **Recommendation** = proposed action; **Validate** = data is unavailable and must be collected.

This is an adoption audit, not a general code review. GitHub counts are a point-in-time snapshot, not installation counts.

## A. Executive Assessment

**Current adoption position.** **Fact:** the public repository has 19 stars, 5 forks, no open issues, 63 pull-request records, 59 issue records, 20 relevant topics, Discussions enabled, an 85% GitHub community-profile score, and releases through v2.6.2. It was created only in February 2026. **Inference:** adoption is early, but the project is neither dormant nor under-documented. The premise that it mainly needs “more features” is false.

**Strongest advantages.** It accepts ordinary Home Assistant entities rather than one hardware family; core calculations are local; optional network activity is disclosed; it combines rain nowcasting, ET0, heat stress, fire weather, frost, lightning, pressure forecasting, upload networks, dashboards, blueprints, diagnostics, and eight translations. The unusual advantage is not “170+ sensors”; it is turning an already-owned station into actionable local automations.

**Primary blockers.** (1) custom-repository installation prevents ambient HACS discovery; (2) “WS Core” is opaque outside existing context; (3) the first-run claim conflicts with seven required mappings and 56 config/options steps in the implementation; (4) 170+ entities creates perceived and actual overload; (5) screenshots prove breadth but not a simple before/after outcome; (6) there is almost no independent proof—showcase installations, quotations, forum threads, or compatibility reports; (7) releases are too frequent and inconsistently explained; (8) the strongest use cases compete for the same first screen.

**Strategic conclusion.** Stop selling a sensor catalog. Sell one repeatable transformation: **“Turn the weather station already in Home Assistant into local rain, safety, garden, and comfort automations.”** Use “rain starts soon” as the acquisition hook and local weather intelligence as the category.

**Top five actions.** Keep the existing HACS default submission healthy while it waits for review; replace the “60-second” claim with a measured five-minute path; publish a 45-second real-install demo; create selectable Starter/Garden/Safety/Full entity profiles; launch one evidence-led Community post with a compatibility-report call to action.

**Growth potential.** A credible 30-day target is doubling qualified repository visits and reaching 30–40 stars, 5–10 documented installations/compatibility reports, and a measurable HACS-default submission state. A credible 90-day target is 60–100 stars, 15–30 compatibility reports, 3–5 non-code contributors, and a stable support baseline. These are planning ranges, not forecasts or promises.

## B. Current-State Scorecard

| Area | Score | Evidence | To reach 9–10 |
|---|---:|---|---|
| Product clarity | 7 | README leads with rain countdown and explains inputs | One category name, one primary audience, measured setup claim |
| Differentiation | 8 | Local derived intelligence, nowcast correction, ET0, three fire systems | Publish methodology comparisons and real outcomes |
| README | 8 | Hero, CTA, compatibility, screenshots, automations, privacy, FAQ | Remove hype/“nerd” framing; add limits, status, support, five-minute result |
| Documentation | 8 | MkDocs tree, science, quickstart, hardware guide, use cases | FAQ search coverage, glossary, upgrade policy, per-profile reference |
| Onboarding | 5 | UI flow and auto-discovery exist | Presets, fewer required choices, post-setup actions, measured walkthrough |
| Installation | 5 | HACS My-link and manual route | HACS default listing; explicit restart/reload and rollback validation |
| User experience | 6 | Entity selectors, options, diagnostics, translations | Progressive disclosure, profile-based entity enablement, Repairs |
| Visual communication | 7 | Four real screenshots | Setup GIF, annotated outcome screenshot, architecture diagram |
| Trust | 7 | Tests, CI, SECURITY, local/privacy table, scientific docs | Support/version policy, limitations, public compatibility matrix, testimonials |
| GitHub optimization | 8 | Description, homepage, 20 topics, templates, workflows | Custom social preview, Code of Conduct, pinned Discussions, cleaner releases |
| HACS discoverability | 5 | Valid custom-repository path and passing default-repository submission #7759 in the review queue | Default inclusion and HACS search discovery |
| Search discoverability | 7 | Strong topics and MkDocs titles | Indexing check, query-led guides, backlinks/community posts |
| Marketing | 4 | Launch kit exists | Execute it; recurring proof-led release/community cadence |
| Community | 3 | Discussions enabled | Categories, welcome/showcase thread, response SLA, compatibility program |
| Contribution path | 6 | CONTRIBUTING and docs guide | Non-code path, good-first issues, translation/gallery workflow |
| Release communication | 5 | Frequent GitHub releases and large changelog | Outcome-led notes, consolidated cadence, screenshots, migrations |
| Retention | 5 | Dashboards/blueprints create actionability | Profiles, disabled-by-default advanced entities, health summary |
| Measurement | 2 | Public GitHub signals only | Baseline dashboard, tagged links, support taxonomy, monthly scorecard |

## C. Audience and Positioning

### Segment ranking

Scores are relative (5 = strongest).

| Segment | Audience | Install | Recommend | Strategic | Reach | Problem / proof / abandonment / channel |
|---|---:|---:|---:|---:|---:|---|
| PWS owners already in HA (Ecowitt, Tempest, Davis, Netatmo) | 5 | 5 | 5 | 5 | 5 | Want more value from hardware; need exact mapping screenshot and compatibility report; abandon at entity mapping; Ecowitt/PWS forums + HA Community |
| Garden and irrigation users | 4 | 5 | 4 | 5 | 4 | Need rain skip/ET0; need water-saving explanation and sample dashboard; abandon at ET terminology; Smart Irrigation and gardening communities |
| Weather-safety automation users | 4 | 4 | 5 | 5 | 4 | Want wind/frost/heat/lightning actions; need limits and false-alert controls; abandon if warnings appear “official”; blueprints and HA Community |
| Local-first HA users | 4 | 4 | 4 | 4 | 4 | Avoid subscriptions/cloud; need precise network disclosure; abandon on optional-provider confusion; Reddit and privacy/local-first groups |
| Dashboard builders | 5 | 3 | 5 | 3 | 5 | Want visual weather data; need copyable vanilla and enhanced examples; abandon on card dependencies; GitHub/HACS/Reddit |
| Solar/energy users | 4 | 3 | 3 | 3 | 4 | Want PV expectation; need calibration example; abandon if it duplicates Forecast.Solar; energy forums |
| MQTT/data publishers | 2 | 3 | 3 | 2 | 3 | Want redistribution/upload; need protocol/security docs; abandon on credential complexity; technical docs |
| Integration/blueprint authors | 2 | 2 | 4 | 4 | 3 | Need stable entity contracts; need developer reference; abandon on churn; GitHub |

**Primary persona:** an intermediate Home Assistant user whose PWS already exposes temperature, humidity, pressure, wind, and rain entities and who wants useful automations without maintaining templates.

**Secondary:** irrigation/garden users, safety automation users, and local-first enthusiasts. Dashboard builders are acquisition amplifiers, not the product’s primary buyer. Upload-network and advanced-model users should not dominate the opening message.

**Product definition:** For Home Assistant users with a local weather station, Weather Station Core is a local weather-intelligence integration that turns raw station entities into actionable rain, safety, garden, and comfort signals, unlike isolated templates or cloud forecasts, because it combines on-site observations, documented meteorological calculations, and ready-to-import automations.

**Messaging hierarchy:** outcome → compatibility → local/privacy → five-minute proof → four feature packs → science/reference.

**Recommended tagline:** **Your weather station, ready to automate.** Alternatives: **Local weather data. Actionable home intelligence.** / **From raw station readings to useful warnings.** / **Know what your weather station means.**

**Descriptions.** One sentence: “Turn weather-station entities already in Home Assistant into local rain, garden, safety, comfort, and forecast signals—with dashboards and automations included.” Thirty words: “Weather Station Core turns personal weather-station entities in Home Assistant into local rain, irrigation, heat, frost, wind, fire, and forecast intelligence, with guided setup, dashboards, blueprints, and optional cloud enrichment.” Repository subtitle: “Local weather intelligence and ready-made automations for any station already in Home Assistant.” HACS: “Turn existing Home Assistant weather-station entities into local rain, irrigation, comfort, safety, and forecast sensors; includes dashboards and blueprints.” Forum: “A local-first custom integration that converts your PWS entities into actionable rain, ET0, frost, heat, wind, fire-weather, and forecast signals.” Social-preview headline: “Your weather station, ready to automate.”

## D. Competitive Benchmark

Approximate stars/forks are verified by GitHub on 2026-07-11 and are not installs.

| Project | Repository | Category | Adoption signal | Strongest practice | Weakness | Lesson / adopt? |
|---|---|---|---:|---|---|---|
| Thermal Comfort | [dolezsa/thermal_comfort](https://github.com/dolezsa/thermal_comfort) | Derived comfort sensors | 859 / 134 | Narrow, instantly understood job | Narrower outcomes | Lead with a small job; **yes** |
| Smart Irrigation | [jeroenterheerdt/HAsmartirrigation](https://github.com/jeroenterheerdt/HAsmartirrigation) | ET-based irrigation | 528 / 84 | Outcome-specific product/category | More configuration | Build a garden landing path; **yes** |
| Pirate Weather | [Pirate-Weather/pirate-weather-ha](https://github.com/Pirate-Weather/pirate-weather-ha) | Forecast integration | 536 / 30 | Clear replacement story and active releases | Cloud/API dependency | Use crisp alternative framing; **yes, without claiming replacement** |
| Ecowitt custom | [garbled1/homeassistant_ecowitt](https://github.com/garbled1/homeassistant_ecowitt) | PWS ingestion | 157 / 64 | Hardware search intent | Stale and setup-heavy | Publish “works after Ecowitt integration” guide; **yes** |
| Ecowitt official custom | [Ecowitt/ha-ecowitt-iot](https://github.com/Ecowitt/ha-ecowitt-iot) | Local hardware ingestion | current count unavailable here | Model compatibility table | Confusing overlap with core | Copy compatibility-table precision; **yes** |
| WeatherFlow2MQTT | [briis/hass-weatherflow2mqtt](https://github.com/briis/hass-weatherflow2mqtt) | Local ingestion/MQTT | 129 / 31 | Specific local-data promise | Separate service/MQTT complexity | Create source-specific bridge docs; **yes** |
| Weather Card | [bramkragten/weather-card](https://github.com/bramkragten/weather-card) | Dashboard card | 557 / 168 | Immediate animated visual payoff | Not an intelligence engine | Make visuals the shareable entry; **yes** |
| Clock Weather Card | [pkissling/clock-weather-card](https://github.com/pkissling/clock-weather-card) | Dashboard card | ~850 stars | Beautiful, recognizable hero | Display only | Ship one canonical visual; **yes** |
| Platinum Weather Card | [Makin-Things/platinum-weather-card](https://github.com/Makin-Things/platinum-weather-card) | Dashboard card | 209 / 43 | Graphical configuration/customization | Can feel complex | Provide a no-dependency starter; **yes** |
| Weather Conditions Card | [r-renato/ha-card-weather-conditions](https://github.com/r-renato/ha-card-weather-conditions) | Dashboard card | 277 / 38 | Visual focus and steady maintenance | Card dependencies | Maintain screenshot freshness; **yes** |
| Hourly Weather | [decompil3d/lovelace-hourly-weather](https://github.com/decompil3d/lovelace-hourly-weather) | Forecast visualization | ~395 stars | One clear visualization | Narrow | One graphic per outcome; **yes** |
| Waste Collection Schedule | [mampfes/hacs_waste_collection_schedule](https://github.com/mampfes/hacs_waste_collection_schedule) | HA integration framework | 2,116 / 1,243 | Huge compatibility/contributor surface | Different domain, large support cost | Community-maintained compatibility adapters; **selectively** |

Do not copy card projects’ presentation so far that Weather Station Core appears to be a dashboard theme. Do not copy broad frameworks’ provider count as a growth target; support burden is the constraint.

## E. Full User Acquisition Funnel

| Stage | Current state / drop-off | Intervention | Success metric |
|---|---|---|---|
| Discovery | Good keywords; default-HACS submission is queued but not merged | Keep submission healthy, add forum backlinks and source-specific pages | Search impressions, HACS state |
| Repository visit | Strong hero; too many claims | One hook + annotated result | README→docs/CTA click rate |
| Value comprehension | Rain hook clear; 170+ distracts | Four outcome packs | 5-second comprehension test ≥80% |
| Compatibility | Table is broad, not verified per model | Community compatibility matrix | Reports/models added |
| Trust | CI/privacy/science strong; little social proof | Limitations, real screenshots, public reports | Install-intent survey/support sentiment |
| Install attempt | Custom HACS steps | Default HACS; accurate manual fallback | Install-doc exits/support failures |
| Configuration | Seven mappings and many options | auto-discovery score + profiles + required/optional split | Median setup time; errors/session |
| First result | 50+ entities appear | Success screen: 3 named entities + next action | Setup completion; first blueprint import |
| Dashboard/automation | Examples exist | One-click blueprint links and starter dashboard | Imports/downloads |
| Continued use | Entity overload risk | profiles, health summary, disable unused modules | 30/90-day proxy surveys, repeat support |
| Recommendation | No explicit showcase loop | “Show your station” Discussion | showcase posts/referrals |
| Contribution | Code path good, non-code vague | compatibility/translation/gallery forms | first-time contributors |

First 5 seconds: outcome and screenshot are visible. Thirty seconds: compatibility/local promise are understandable. Two minutes: breadth becomes exciting but intimidating. Ten minutes: docs show substance, yet a user still cannot see an independently verified hardware/config example or know the minimal entity set by outcome.

## F. Repository and README Audit

**Keep:** headline outcome, HACS My-link, compatibility table, real dashboard images, automation links, comparison table, privacy disclosure, FAQ. **Rewrite:** “60-Second Quickstart” (unverified), “premium” (commercial-quality claim without evidence), “Nerd Section” (alienates safety/science users), “gold-standard/most accurate/capabilities not available in any other” (requires systematic proof), and the exact 70/30 blend claim unless stable and cited. **Move:** upload targets, complete model list, translation parity, and detailed formulas to docs. **Remove from first screen:** 170+ as the main proof. **Add:** tested HA range, project status, known limits, support link, required-versus-optional input matrix, screenshot annotation, and “what happens next.”

**Recommended README order:**

1. `# Weather Station Core` — searchable name.
2. `## Your weather station, ready to automate` — outcome and local-first promise.
3. Hero screenshot — annotate rain countdown, wind risk, ET0.
4. `## What you can do` — four outcomes.
5. `## Will it work with my station?` — input matrix and verified reports.
6. `## Install` — HACS/default or custom status, manual fallback.
7. `## Five-minute first result` — measured route.
8. `## What appears in Home Assistant` — profiles and entity count.
9. `## Start with an automation` — first five blueprints.
10. `## Start with a dashboard` — vanilla before enhanced.
11. `## Local processing and optional services` — data-flow table.
12. `## Feature packs` — progressive disclosure.
13. `## Accuracy, limitations, and safety` — no official-warning implication.
14. `## Upgrade, remove, and recover`.
15. `## Documentation and support`.
16. `## Contribute`.
17. `## Status, license, attribution`.

**Recommended first screen copy:**

> # Weather Station Core
> **Your weather station, ready to automate.**
>
> Turn the temperature, humidity, pressure, wind, and rain entities already in Home Assistant into useful local signals: rain-start countdowns, irrigation ET0, frost and heat warnings, wind safety, fire-weather indicators, and an offline pressure forecast.
>
> **Primary CTA:** Install with HACS  
> **Secondary CTA:** See the five-minute setup
>
> - Know when rain may start—and compare the forecast with your own gauge.
> - Skip irrigation using locally calculated rainfall and ET0.
> - Protect awnings, gardens, and people with ready-made blueprints.
> - Keep core calculations local; optional network features are off by default.

Badges: HACS status, latest stable release, CI/validation, license, supported HA minimum. Avoid translation-count and coverage badges as primary trust signals. Social preview: 1280×640, product name, tagline, one uncluttered HA screenshot crop, four small labels (Rain · Garden · Safety · Comfort), no sensor count.

## G. Documentation Blueprint

MkDocs Material is the right platform: already configured, low migration cost, navigation/search, GitHub edits, and indexable pages. Do not move to Docusaurus. Keep README as conversion page and docs as task/reference content.

| Page | Audience / question | Content and visual | Links | Priority |
|---|---|---|---|---|
| Getting started | New / “Can I use it?” | prerequisites, compatibility, 5-minute route; setup GIF | install, mapping | Launch |
| Installation | New / “How?” | default/custom HACS, manual, restart, uninstall | troubleshooting | Launch |
| Supported sources | PWS owners | verified models/entities, report form; matrix screenshot | hardware guides | Launch |
| Profiles | New / “Which features?” | Starter/Garden/Safety/Full inputs/entities | reference | Launch |
| Configuration | All / “What does each choice do?” | every step/default; annotated screens | troubleshooting | Launch |
| Sensor reference | Advanced | category, unit, inputs, default enabled, formula link | science | Existing; improve |
| Calculations | Technical/trust | formula, citations, assumptions, range, caveats | sensor pages | Existing |
| Rain/nowcast | Rain users | timeline, confidence, limits | blueprint | Launch |
| Garden/irrigation | Garden | ET0 choice, rain skip, Smart Irrigation | recipes | Existing; improve |
| Safety metrics | Safety | frost/wind/heat/fire/lightning disclaimers | recipes | Launch |
| Dashboards | Builders | vanilla first, dependencies, screenshots | gallery | Existing |
| Automation recipes | Users | five first outcomes, thresholds, testing | blueprints | Existing; improve |
| Privacy/local | Trust | data-flow and retention table | diagnostics | Launch |
| Performance | Advanced | update intervals, entity load, API calls | profiles | Later |
| Troubleshooting/FAQ | Support | symptom→cause→fix, diagnostics | issue form | Existing |
| Upgrade/migration | Existing users | breaking-change policy and version guides | releases | Launch |
| Contributing without code | Community | reports, translations, docs, screenshots | forms | Launch |
| Developer/translation/release policy | Contributors | environment, contracts, locale and cadence | CONTRIBUTING | Later |

## H. Installation and Onboarding Improvements

**Current journey.** Add custom repository → install → restart → add integration → map seven basics → encounter optional inputs/features → receive 50+ entities. Estimated 6–15 minutes for a prepared intermediate user; longer if entity names/units are unclear. **Validate:** record five fresh-user sessions; do not publish “60 seconds” until median measured time supports it.

**Five-minute path:** (1) install from HACS; (2) add integration; (3) choose `Starter` profile; (4) select station device or temperature entity; (5) auto-suggest sibling entities with confidence and units; (6) show missing/optional fields; (7) create only core entities; (8) success screen links directly to Rain Start blueprint and starter dashboard.

**Profiles:** Starter (temperature/humidity/pressure/wind/rain, ~20 high-value entities); Garden (adds solar/soil/ET0); Safety (adds gust/lightning/UV/fire/heat); Full (everything, explicit warning). Prefer default-disabled advanced entities over deleting capabilities.

**Exact UI copy:**

- Welcome: “Choose the weather station already connected to Home Assistant. Weather Station Core will suggest matching entities; you can review every selection before anything is created.”
- Profile: “Start small. You can enable more feature packs later without reinstalling.”
- Required field error: “Select a temperature entity with a numeric state. `{entity}` currently reports `{state}`.”
- Unit error: “`{entity}` uses `{unit}`, which cannot be converted to pressure. Choose an absolute-pressure sensor (usually hPa, mbar, inHg, or kPa).”
- Discovery warning: “We found more than one likely rain-total sensor. Select the cumulative total, not rain rate.”
- Success: “Weather Station Core is ready. `{ready_count}` entities are available; `{skipped_count}` were skipped because optional inputs were not selected. Next: import Rain Start Warning or open the starter dashboard.”
- Network consent: “This feature sends your approximate coordinates to `{provider}`. Core calculations remain local. Nothing is sent while this feature is off.”

**Product changes:** discovery confidence, profiles, post-setup menu, validation summaries, Repairs for stale/missing required entities, diagnostics health block, safe reconfigure, and per-feature API status. Demo mode is lower priority: sample screenshots achieve most benefit without introducing synthetic states into production.

## I. Discoverability and Distribution Plan

| Channel | Eligibility/current blocker/steps | Impact / priority |
|---|---|---|
| HACS custom | Structure, manifest, releases, My-link present | Working; retain |
| HACS default | Submission [hacs/default#7759](https://github.com/hacs/default/pull/7759) has been open since 2026-05-18. All submission checks passed and the HACS bot confirms it is waiting in the review queue. Do not comment, duplicate, or merge the fork's default branch unless a maintainer requests it. Continue keeping the repository and releases valid. | Very high / already in progress |
| HA Brands | Since HA 2026.3 custom integrations can ship local `brand/`; the repository already includes the required local assets. The passing HACS submission checks provide stronger evidence than the earlier path-only search. | Complete for current custom-integration use |
| HA Core | Calculated service integration is not an obvious product/service integration; core submission would require Bronze, full rule evidence, architecture review, tests/typing, docs in HA, and an established user base. Breadth/support may be rejected. | Low now / Strategic only |
| Awesome Home Assistant | Check current contribution rules, propose under weather only after public usage evidence | Medium |
| HA Community | One canonical Show-and-Tell thread, tagged updates, support routed to GitHub | High |
| Blueprint Exchange | Publish five generic blueprints individually with import links and dependency notice | High |
| Dashboard galleries | Submit canonical vanilla dashboard and annotated image where rules allow | Medium |
| PWS communities | Source-specific guides for Ecowitt/Tempest/Davis; request mapping reports, not generic promotion | High |

Current official evidence: [HACS default inclusion](https://www.hacs.xyz/docs/publish/include/), [HACS integration requirements](https://hacs.xyz/docs/publish/integration/), [HACS general requirements](https://hacs.xyz/docs/publish/start/), [HA brand images](https://developers.home-assistant.io/docs/core/integration/brand_images/), [core contribution](https://developers.home-assistant.io/docs/core/integration/contributing_to_core), and [Integration Quality Scale](https://developers.home-assistant.io/docs/core/integration-quality-scale/).

**Search plan.** Primary: Home Assistant weather station, personal weather station Home Assistant, Ecowitt derived sensors, local weather automation. Secondary: rain prediction/countdown, ET0 irrigation, WBGT/UTCI, frost alert, fire weather index, Zambretti, MQTT weather. Long-tail pages: “Use Ecowitt WS90 data for rain-start alerts,” “local ET0 irrigation in Home Assistant,” “WBGT exercise alert,” “offline Zambretti forecast,” “wind-gust awning automation,” “WeatherFlow derived sensors.” Place naturally in page titles, first paragraph, image alt text, and forum titles. Do not create thin comparison pages or claim replacement for hardware-ingestion integrations.

## J. Marketing and Community Plan

| Channel | Content/style/frequency | Risk / CTA / avoid |
|---|---|---|
| HA Community | Detailed launch, screenshots, supported inputs, limitations; monthly meaningful update | Low if helpful; “try starter path/report station”; no release spam |
| Reddit r/homeassistant | Personal build story + one GIF + technical answers; launch and major milestones only | Medium; ask for edge-case testers; no cross-post flood |
| Ecowitt/PWS forums | Exact mapping guide and compatibility request | Low; contribute model mapping; no “works with everything” claim |
| Blueprint Exchange | One solved problem per post | Low; import and report thresholds; no bundle dump |
| GitHub | outcome-led releases, Discussions showcase, good-first issues | Low; star only as optional support; no vanity milestones |
| YouTube creators | Short individualized pitch with demo instance and test checklist | Medium; invite independent evaluation; never request positive coverage |
| Discord/Facebook | Answer existing questions; share only when directly relevant | High; no drive-by promotion |
| Blog/dev.to | methodology and build story every 4–6 weeks | Low; reproduce a useful calculation; avoid generic launch copy |
| Bluesky/Mastodon/X | one clip per meaningful release | Medium; link to use case; no daily feature threads |
| Product Hunt/HN/LinkedIn | Poor audience fit today | High/low impact; defer |

**Sustainable calendar:** one consolidated feature release every 4–6 weeks, patches as needed; docs continuously with monthly digest; one substantial tutorial/month; one Community update/month; one showcase every 2–4 weeks; quarterly roadmap discussion.

**Community model:** Discussions categories `Announcements`, `Show your station`, `Hardware compatibility`, `Ideas`, `Q&A`. Pin “Start here,” “Report your station mapping,” and “Showcase gallery.” Acknowledge issues within 3 days when possible; publish that as a target, not a guarantee.

## K. Examples and Showcase Plan

| Rank | Asset | Story / entities / outcome | Complexity / audience / format |
|---:|---|---|---|
| 1 | Rain starts soon | minutes-until-rain or rain probability → phone/TTS warning | Low; all PWS; blueprint + 45s GIF |
| 2 | High wind protection | gust + threshold → retract awning/close cover | Low; homeowners; blueprint + diagram |
| 3 | Irrigation suppression | rain/forecast/ET0 → skip watering | Medium; garden; blueprint + recipe |
| 4 | Freeze/frost warning | temp/frost risk → protect plants | Low; garden; blueprint + mobile alert |
| 5 | Heat/WBGT exercise warning | WBGT/UTCI → warning | Low; families/athletes; blueprint + safety caveat |
| 6 | Data-quality/stale sensor | health/stale state → maintenance alert | Low; all; blueprint |
| 7 | Fire-weather risk | regional index → contextual notification | Medium; regional; recipe, never official alert |
| 8 | Lightning safety | distance/count → outdoor warning | Medium; WH57/Tempest; blueprint |
| 9 | Vanilla weather dashboard | core entities → immediate value | Medium; all; dashboard package |
| 10 | Morning briefing | summary + alerts → TTS | Medium; Assist users; script/recipe |
| 11 | Rain cross-validation | local gauge + nowcast confidence | Advanced; weather enthusiasts; dashboard |
| 12 | Solar expectation | solar forecast/radiation → energy context | Medium; PV users; dashboard recipe |
| 13 | Storm preparation | wind/rain/lightning composite | Advanced; safety; package |
| 14 | MQTT redistribution | selected derived states → broker | Advanced; integrators; guide |

**Visual set:** social preview 1280×640 static; README hero 1600×900 annotated static; desktop 1600×900 and mobile 1080×1920 real screenshots; config-flow images 1440×900; input→engine→outcomes SVG; setup GIF 1280×720 under ~15 MB; alert screenshot 1080×1920; release card 1200×630. Every image needs a date/version and alt text. Feature-category icons are optional—do not delay proof assets for branding.

**45-second storyboard:** 0–5s raw Ecowitt entities; 5–12s add integration and choose Starter; 12–20s auto-mapped inputs; 20–25s success screen; 25–33s rain countdown changes; 33–39s phone alert fires; 39–45s dashboard with “core local / optional enrichment” label and install CTA. Use a real HA instance, blur location/device IDs, and state that forecast timing is probabilistic.

## L. Measurement Plan

No integration telemetry should be added. Use aggregate platform analytics and voluntary feedback.

| Metric | Why / collection | Privacy | Direction / review / limitation |
|---|---|---|---|
| Stars/forks/watchers | awareness/intent; GitHub API | Public aggregate | up; monthly; weak install proxy |
| Repo unique visitors/referrers | acquisition; GitHub Insights manual export | Aggregate | up and diversified; weekly/monthly; 14-day window |
| Docs visits/search | content demand; privacy-respecting analytics or server logs | disclose, no fingerprinting | search exits down; monthly; blockers/adblock |
| Release asset downloads | upgrade interest; GitHub API | Aggregate | up; release; HACS may not map to installs |
| HACS downloads | adoption if exposed after default listing | Aggregate | up; monthly; availability/definition varies |
| Setup issue rate | friction; label issues `setup` | Public reports | down; monthly; under-reporting |
| Setup time/success | five-user usability sessions + opt-in survey | Consent; no telemetry | median <5 min, ≥80% completion; quarterly; small sample |
| Blueprint/dashboard imports | asset usefulness; release downloads/short links | Aggregate | up; monthly; incomplete |
| Compatibility reports | proof/community | Voluntary model/entity info | 5 then 20+; monthly; selection bias |
| First/returning contributors | community health; GitHub contributors | Public | up; quarterly; bots excluded |
| Response/close time | support trust; GitHub API | Public | stable/down; monthly; complexity varies |
| Translation coverage | reach; key parity CI | Repository data | 100% key parity; release; quality not measured |

**Monthly scorecard:** visitors, top referrers, stars/forks, release downloads, docs top pages/searches, setup/support issues by category, median first response, compatibility models, blueprint/dashboard uses, first-time/returning contributors, shipped experiments, next-month decision. Capture the 2026-07-11 baseline (19 stars, 5 forks, 0 open issues, 8 translations, 10 blueprints); mark unavailable fields “not collected,” never zero.

## M. Prioritized Backlog

| ID | Workstream | Recommendation / evidence | Impact | Effort | Confidence | Dependency | Owner | Success metric | Phase |
|---|---|---|---|---|---|---|---|---|---|
| D01 | Distribution | Keep HACS default PR #7759 healthy and wait for ordered review; custom-only remains the largest discovery tax until merge | Critical | Small | High | passing release/actions | Maintainer | PR accepted | In progress |
| R01 | README | Replace 60-second, premium, nerd, and unsupported superlatives | High | Small | High | none | Writer | comprehension test | Immediate |
| V01 | Visual | Produce annotated hero and 45s real demo | High | Medium | High | stable starter path | Designer/maintainer | views→docs clicks | Short |
| O01 | Onboarding | Measure five fresh installs | High | Small | High | testers | Maintainer/community | median time/errors | Immediate |
| O02 | Onboarding | Starter/Garden/Safety/Full profiles | Critical | Large | High | UX design | Developer | completion/entity use | Medium |
| O03 | Onboarding | Discovery confidence + unit validation | High | Large | High | O02 | Developer | setup errors down | Medium |
| O04 | Onboarding | Post-setup success menu | High | Medium | High | entity IDs stable | Developer | blueprint/dashboard starts | Short |
| T01 | Trust | Publish tested compatibility matrix/report form | High | Small | High | community | Writer/community | verified models | Immediate |
| T02 | Trust | Add limitations, stability, support/version policy | High | Small | High | maintainer judgment | Maintainer | fewer trust questions | Immediate |
| C01 | Community | Configure/pin Discussions and showcase | High | Small | High | none | Maintainer | reports/showcases | Immediate |
| C02 | Community | Add non-code contribution path + issue forms | Medium | Small | High | C01 | Writer | first-time contributors | Immediate |
| M01 | Marketing | One Community launch using ready assets | High | Small | High | R01/V01 | Maintainer | qualified visits/replies | Short |
| M02 | Marketing | Source-specific Ecowitt guide/post | High | Medium | High | T01 | Writer | search visits/reports | Short |
| E01 | Examples | Polish top five blueprints with import links/test steps | High | Medium | High | stable entities | Developer/writer | imports/issues | Short |
| S01 | SEO | Add query-led titles/FAQ/schema-friendly answers | Medium | Medium | Medium | Search Console | Writer | impressions/clicks | Short |
| G01 | GitHub | Add Code of Conduct, support policy, labels | Medium | Small | High | maintainer policy | Maintainer | community score/triage | Immediate |
| Rel01 | Releases | Consolidate cadence and use outcome-led template | High | Small | High | none | Maintainer | release clicks/support | Immediate |
| Ret01 | Retention | Default-disable advanced entities by profile | Critical | Large | High | O02/migration | Developer | enabled/use ratio | Medium |
| Ret02 | Retention | Health summary + Repairs for stale inputs/providers | High | Large | High | diagnostics | Developer | recurring setup issues down | Medium |
| A01 | Analytics | Baseline sheet and monthly review | High | Small | High | Insights access | Maintainer | monthly decisions logged | Immediate |
| Core01 | Distribution | Investigate HA Core candidacy only after adoption proof | Low | Very Large | Low | user base/architecture | Maintainer/developer | go/no-go memo | Strategic |

**Quick wins:** D01 eligibility audit, copy corrections, compatibility form, pinned Discussions, release template, measurement baseline. **Structural:** profiles, discovery, Repairs. **Avoid:** renaming the domain, building more calculation families, paid ads, Product Hunt/HN launches, invasive telemetry, fake testimonials, daily social posting, or rewriting docs platforms. AI can draft matrices, alt text, FAQs, templates, and release variants; humans must validate claims, safety thresholds, user sessions, community tone, and HACS/Core submissions.

## N. 7-Day Action Plan

1. **Day 1:** export GitHub Insights baseline; confirm HACS PR #7759 remains queued and checks pass; remove unverified superlatives and rename the quickstart.
2. **Day 2:** recruit five representative users; observe install without coaching; record time, wrong selections, exits, and questions.
3. **Day 3:** create public compatibility-report form/Discussion; seed with maintainer’s actual station and exact entities; add support/version/limitations copy.
4. **Day 4:** capture one real 45-second setup-to-alert video plus annotated hero; redact private data; add version/date.
5. **Day 5:** polish top five blueprint pages with prerequisites, import CTA, thresholds, test method, and safety caveat.
6. **Day 6:** verify HACS-default PR #7759 remains healthy without disturbing its queue position; configure Discussions categories, pins, and labels.
7. **Day 7:** publish one HA Community launch post; answer every substantive question; log referrals, setup issues, and next decisions after 72 hours.

## O. 30-Day Growth Plan

| Week | Deliverables | Dependency | Measurable outcome |
|---|---|---|---|
| 1 | Seven-day plan, baseline, copy correction, compatibility seed | maintainer access/testers | measured setup median; HACS state known |
| 2 | Video, hero, top-five example pages, Community launch | real HA instance | qualified visits and 3+ compatibility reports |
| 3 | Ecowitt/WS90 and irrigation landing guides; creator test pack | evidence/assets | search indexing and 2 creator replies |
| 4 | onboarding design spec, release template, first monthly scorecard | user-session results | prioritized code backlog; 30–40 stars planning range, not KPI mandate |

## P. 90-Day Adoption Roadmap

**Days 1–30 — Prove and distribute:** accurate promise, measured setup, healthy queued HACS submission, canonical demo, launch thread, compatibility evidence. **Milestone:** discovery path and baseline exist.

**Days 31–60 — Reduce product friction:** ship profiles, validation summary, success menu, top-five starter assets; publish one outcome tutorial. **Milestone:** median prepared-user setup below five minutes and fewer entity-selection failures in tests.

**Days 61–90 — Build the loop:** health/Repairs design or first slice, gallery, translation contribution drive, creator follow-up, quarterly roadmap. **Target range:** 60–100 stars, 15–30 reports, 3–5 non-code contributors, support issues categorized and answered predictably. Validate against baseline; do not optimize stars at the expense of successful installs.

## Q. Ready-to-Use Assets

**Repository description:** `Local weather intelligence and ready-made automations for any personal weather station already in Home Assistant: rain, ET0 irrigation, heat, frost, wind, fire weather, and offline forecasting.`

**GitHub topics:** `home-assistant`, `hacs`, `custom-integration`, `weather-station`, `personal-weather-station`, `ecowitt`, `weatherflow`, `davis-weatherlink`, `netatmo`, `rain-nowcast`, `evapotranspiration`, `smart-irrigation`, `weather-automation`, `wbgt`, `utci`, `fire-weather-index`, `frost-alert`, `zambretti`, `local-first`, `mqtt`. Drop redundant/low-intent topics only if GitHub’s limit requires it.

**Community launch post:**

> **Weather Station Core: turn your existing PWS entities into local rain, garden, and safety automations**
>
> I built Weather Station Core because my station already produced good raw readings, but turning them into reliable Home Assistant automations meant maintaining many templates. The integration maps standard temperature, humidity, pressure, wind, and rain entities and creates derived signals plus ready-to-import blueprints.
>
> The core calculations run locally. Optional forecast, air-quality, and upload features are off until enabled. The starter examples cover rain starting soon, wind protection, irrigation skip, frost, and heat stress. It currently supports any station already exposing compatible HA entities; I have mapping guidance for Ecowitt, WeatherFlow, Davis, Netatmo, MQTT, and templates.
>
> Screenshots/demo: [link] · Install/quickstart: [link] · Methods and limitations: [link]
>
> I especially need real-world compatibility reports: station model, integration used to ingest it, and which entity mappings worked. Please report failures too—this is not an official weather-warning source.

**Reddit post:**

> **I turned my Home Assistant weather-station entities into rain, frost, wind, heat and irrigation automations**
>
> My PWS already exposed raw sensors, but I kept rebuilding templates for decisions. I packaged the calculations and five starter automations into a local-first custom integration. Here is a 45-second real setup and rain-alert demo: [link]. Core calculations stay local; optional providers are opt-in. I’m looking for honest testing across Ecowitt/WS90, Tempest, Davis, Netatmo and MQTT setups. Repo: [link]. Known limits: [link].

**Release announcement:**

> **Weather Station Core vX.Y — [user outcome]**
>
> What changed: [three outcome bullets]. Who should update: [audience]. Before updating: [backup/migration or “no action”]. Try it: [one screenshot/recipe]. Fixed: [short list]. Known limitations: [link]. Full changelog: [link]. Report results with diagnostics: [link].

**Creator outreach:**

> Hi [name]—your [specific video/post] helped PWS users solve [specific problem]. I maintain Weather Station Core, a local-first Home Assistant custom integration that turns existing station entities into rain, irrigation, frost, heat, wind and fire-weather signals. Would you be interested in independently testing its five-minute starter path? I can provide a clean demo, supported-input matrix, and disclosure/limitations sheet. No request for positive coverage; bug reports are equally useful. [repo] [45s demo]

**Contribution invitation:** “No Python required: report a working station mapping, translate missing UI text, test a blueprint, submit a redacted dashboard screenshot, improve a troubleshooting step, or reproduce a calculation against a trusted source.”

### How to Contribute Without Coding

You can materially improve Weather Station Core without writing Python:

1. **Report your station mapping.** Share the station model, the HA integration that supplies its entities, and the temperature/humidity/pressure/wind/rain entities that worked. Do not share precise coordinates or credentials.
2. **Test one starter automation.** State the blueprint version, thresholds, expected result, and what actually happened—including false alerts.
3. **Improve a translation.** Compare the English meaning with your language in `custom_components/ws_core/translations/`; preserve keys and placeholders.
4. **Share a dashboard.** Submit a redacted screenshot, required cards, YAML, screen size, and the Weather Station Core version.
5. **Improve documentation.** Open an issue or PR for a confusing step, missing unit, hardware mapping, or troubleshooting result.
6. **Reproduce a calculation.** Link the authoritative reference and provide anonymized inputs, expected output, actual output, units, and version.

Every release should thank first-time reporters, translators, documentation authors, dashboard contributors, and testers by name with permission.

## R. Final Verdict

1. **Principal problem:** distribution and community reach first; positioning/onboarding second. Product breadth and technical quality are not the primary constraint.
2. **Highest-leverage change:** keep the queued default-HACS submission healthy while presenting a measured five-minute Starter path that converts discovery into successful setup.
3. **Do not work on yet:** more sensor families, a new docs stack, a domain rename, official-Core submission, paid promotion, Product Hunt, or invasive analytics.
4. **Realistic outcome:** after 30 days, an accurate conversion surface, measured setup, submitted/defined HACS path, initial compatibility proof, and 30–40 stars is plausible; after 90 days, 60–100 stars, 15–30 reports, 3–5 non-code contributors, and a lower-friction onboarding flow is plausible. External events can move these ranges substantially.
5. **Evidence it works:** more qualified referrals, higher five-user setup completion, lower median setup time, fewer mapping questions per install proxy, blueprint/dashboard use, compatibility submissions, returning contributors, and organic recommendations—not stars alone.

### Evidence index and limitations

Repository evidence: `README.md` (hero, compatibility, install, dashboards, privacy, FAQ); `hacs.json`; `custom_components/ws_core/manifest.json`; `custom_components/ws_core/config_flow.py` (56 setup/options step functions); `custom_components/ws_core/strings.json` and eight translations; `diagnostics.py`; `SECURITY.md`; `CONTRIBUTING.md`; `mkdocs.yml`; `docs/`; four `screenshots/`; five dashboards; ten blueprints; GitHub workflows and release history; and queued HACS default submission [#7759](https://github.com/hacs/default/pull/7759). Live GitHub snapshot collected with the GitHub API on 2026-07-11.

Unavailable: HACS installs/downloads, repository unique visitors/referrers, documentation traffic, setup completion, time to first sensor, retention, and user sentiment. The maintainer must collect these through aggregate platform analytics, five-user usability sessions, and voluntary reports. No claim in this audit treats stars, forks, issues, or downloads as active installations.
