# Engagement status

Last updated: 2026-06-12

---

## What was done in this engagement

### Phase 1 — HACS default store readiness

**Audit findings:**
- `hacs.json` and `manifest.json` are structurally valid. No blocking issues.
- Brand assets exist at `custom_components/ws_core/brand/` (icon.png, icon@2x.png,
  dark_icon.png, dark_icon@2x.png) but are NOT yet registered in `home-assistant/brands`.
  This is the only blocking item for default-store submission.
- `hacs.yml` uses `ignore: brands` as a temporary workaround until brands are registered.
- `validate.yml` runs hassfest + HACS action + ruff + tests + no-bytecode +
  version-consistency — all required CI is in place.
- 156 sensor descriptions in sensor.py. All numeric sensors have `state_class` set correctly.
- No stray zero-byte files remain (removed in v1.4.0 per CHANGELOG).

**Deliverables committed:**
- `docs/promotion/hacs_default_submission.md` — pre-submission checklist and exact PR content
- `docs/promotion/brands_pr/BRANDS_PR.md` — brands PR filing instructions and PR description

### Phase 2 — Repo front door

**Deliverables committed:**
- `README.md` — restructured with problem-first pitch, "Why ws_core" comparison block,
  60-second quickstart, anchor-linked sections, and a translations badge. All existing
  technical content and scientific references preserved.
- `docs/promotion/repo_description.md` — three description options with recommended selection

### Phase 3 — Promotional content

All six drafts committed under `docs/promotion/`:

- `forum_launch_thread.md` — 600-900 word forum post, community.home-assistant.io
- `docs/migrating_from_thermal_comfort.md` — full entity mapping + 5-step procedure
  (also committed to the repo root docs/ for README linking)
- `forum_replies.md` — three evergreen reply drafts for recurring question threads
- `reddit_post.md` — r/homeassistant post with pre-written FAQ comment
- `youtuber_outreach.md` — two email variants + one-page fact sheet appendix
- `awesome_ha_submission.md` — exact entry line + PR content
- `smart_irrigation_docs_pr.md` — proposed PR to Smart Irrigation documentation

### Phase 4 — Documentation site

**Deliverables committed:**
- `mkdocs.yml` — MkDocs Material configuration
- `.github/workflows/docs.yml` — GitHub Actions deploy to GitHub Pages on push to main
- `docs/index.md` — home page with capability overview
- `docs/quickstart.md` — step-by-step installation and configuration
- `docs/sensors.md` — complete sensor reference (all 150+ entities)
- `docs/forecast_providers.md` — all seven providers documented
- `docs/dashboards.md` — dashboard installation guide
- `docs/blueprints.md` — all five blueprints documented with automation examples
- `docs/guides/fire_danger.md` — fire danger guide (FWI/FFDI/FFWI)
- `docs/guides/irrigation.md` — ET₀ and irrigation scheduling guide
- `docs/guides/smart_irrigation.md` — Smart Irrigation integration bridge
- `docs/guides/lightning.md` — lightning detection guide
- `docs/guides/nowcast.md` — precipitation nowcast guide
- `docs/migrating_from_thermal_comfort.md` — Thermal Comfort migration guide
- `docs/troubleshooting.md` — troubleshooting guide
- `docs/contributing.md` — contribution guide

### Phase 5 — Measurement

**Deliverables committed:**
- `docs/promotion/metrics.md` — weekly tracking table with baseline row (2026-06-12)
- State_class audit: all 156 numeric sensors verified to have correct `state_class`.
  No code changes needed.
- `docs/promotion/social_preview/INSTRUCTIONS.md` — social preview image specification
  and tooling options

---

## Manual actions required (in recommended order)

The following actions require the maintainer's direct involvement. They cannot be
performed by an automated agent.

**1. Submit brands PR to home-assistant/brands**
- Timing: immediately — this is the blocking item for everything else
- Instructions: `docs/promotion/brands_pr/BRANDS_PR.md`
- What to do: fork `home-assistant/brands`, create `custom_integrations/ws_core/`
  with the four PNG files from `custom_components/ws_core/brand/`, open PR
- After PR is merged: remove `ignore: brands` from `.github/workflows/hacs.yml` line 18

**2. Set GitHub topics on the repository**
- Timing: immediately (no blocking dependency)
- Instructions: `docs/promotion/hacs_default_submission.md` (topics list)
- What to do: repository Settings → About gear icon → Topics → add the 13 listed topics

**3. Set GitHub repository description**
- Timing: immediately
- Instructions: `docs/promotion/repo_description.md` (Option A recommended)
- What to do: repository Settings → About gear icon → Description

**4. Enable GitHub Pages**
- Timing: before the forum launch thread (so the docs site URL can be included)
- What to do: repository Settings → Pages → Source: GitHub Actions
- The docs deploy workflow (`.github/workflows/docs.yml`) will trigger on the
  next push to main

**5. Submit to hacs/default**
- Timing: after brands PR is merged and CI is green without `ignore: brands`
- Instructions: `docs/promotion/hacs_default_submission.md`
- What to do: fork `hacs/default`, add entry to `custom_integrations.json`, open PR

**6. Post the forum launch thread**
- Timing: within 48 hours of HACS default-store acceptance
- Draft: `docs/promotion/forum_launch_thread.md`
- What to do: copy-paste to community.home-assistant.io → Share your Projects;
  add two screenshots; reply to every comment in the first 48 hours

**7. Submit to awesome-home-assistant**
- Timing: after HACS default-store PR is open (or after acceptance if the list requires it)
- Instructions: `docs/promotion/awesome_ha_submission.md`
- What to do: fork `frenck/awesome-home-assistant`, add the one-line entry, open PR

**8. Post to r/homeassistant**
- Timing: one week after the forum launch thread (gives the thread time to accumulate
  replies, which you can link to in comments)
- Draft: `docs/promotion/reddit_post.md`
- What to do: post the text, then post the FAQ as a top-level comment on your own post

**9. Creator outreach (optional, higher effort)**
- Timing: after the forum thread has replies to point to
- Draft: `docs/promotion/youtuber_outreach.md`
- What to do: personalise Variant A or B, send to relevant creators

**10. Submit Smart Irrigation documentation PR**
- Timing: after the forum thread is live
- Draft: `docs/promotion/smart_irrigation_docs_pr.md`
- What to do: open PR to the Smart Irrigation repo documentation

**11. Create social preview image**
- Timing: before the forum launch thread
- Instructions: `docs/promotion/social_preview/INSTRUCTIONS.md`
- What to do: create 1280x640 composite from dashboard screenshots, upload via
  repository Settings → Social preview

**12. Update metrics table weekly**
- Start date: day the forum thread is posted
- File: `docs/promotion/metrics.md`
- What to do: fill in stars, forks, open issues, forum replies, Reddit score,
  analytics installs each week
