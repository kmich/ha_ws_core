# ws_core Adoption Roadmap

This roadmap defines the precise sequence of operations required to transition `ws_core` from a technically impressive enthusiast tool into a high-adoption, community-recommended Home Assistant default.

## Phase 1: 48-Hour Polish (The Bleeding Edge)
**Goal:** Fix the immediate embarrassment points that will repel contributors or advanced users.
* [ ] **Fix the Test Suite:** Diagnose and resolve the 247 `pytest` errors. Ensure CI is green.
* [ ] **HACS Metadata:** Update `hacs.json` and ensure the integration aligns with HACS default repository requirements. Move `info.md` content directly into the README.
* [ ] **Issue Templates:** Implement `.github/ISSUE_TEMPLATE` for Bugs and Feature Requests to channel user feedback cleanly.

## Phase 2: 1-Week Launch Readiness (The Product Pivot)
**Goal:** Remove the massive friction points from the onboarding flow and reposition the product.
* [ ] **README Rewrite:** Execute the `README-rewrite-plan.md`. Move the heavy science to a dedicated docs page and focus the README on outcomes, automations, and screenshots.
* [ ] **Entity Taxonomy Enforcement:** Update `sensor.py` and `binary_sensor.py` to disable advanced sensors by default. Reduce the initial entity blast from 50+ to the core 15 most useful entities.
* [ ] **Auto-Discovery Spike:** Research and prototype a Device Picker for the Config Flow that attempts to auto-map the 7 required sensors based on standard HA entity conventions.

## Phase 3: 2-Week Community Push (The Launch)
**Goal:** Safely launch the repositioned integration to the Home Assistant community.
* [ ] **Create the "Trust Pack":** Generate GIFs of the setup process, before/after dashboard screenshots, and a clear list of supported hardware.
* [ ] **Community Forum Post:** Post the launch announcement to the Home Assistant Community Forums (Share your Projects).
* [ ] **Reddit Push:** Post to `/r/homeassistant` focusing on the "Minutes until rain" and "Make your Ecowitt actually useful" angles.
* [ ] **Blueprint Promotion:** Ensure the 5 included blueprints are prominently linked in the announcements.

## Phase 4: 1-Month Growth Loop (The Feedback Cycle)
**Goal:** Capture the first wave of new users, fix their bugs, and encourage them to spread the word.
* [x] **GitHub Discussions:** Enable GitHub discussions for Q&A to keep the issue tracker clean.
* [x] **Hardware Mapping Docs:** Document common hardware quirks (e.g., exactly which Shelly sensors map to which inputs).
* [x] **Dashboard Blueprint:** Decided to skip converting YAML dashboards into shareable HA blueprints to avoid adding Javascript dependencies. Relied on improved docs instead.

## Phase 5: 3-Month Path toward HACS Default
**Goal:** Become the unquestioned default integration for personal weather stations.
* [ ] **Code Refactoring:** Break up `config_flow.py` and `coordinator.py` into manageable submodules. This is critical for accepting community PRs.
* [ ] **HACS Default Repo Submission:** Once the user base is stable and the code meets all HACS quality checks, submit to the HACS default repository list.
* [ ] **YouTuber Outreach:** Reach out to HA content creators (e.g., Smart Home Junkie, Everything Smart Home) with a pre-packaged "Reviewer Guide" demonstrating the Zambretti/Nowcast features.
