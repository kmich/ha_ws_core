# ws_core Prioritized Backlog

This backlog translates the adoption review findings into actionable engineering tasks.

## P0: Critical Adoption Blockers (Do Immediately)
| Task | Description | Effort | Impact | Owner Skill |
|---|---|---|---|---|
| **Fix Test Suite** | Resolve the 247 `pytest` errors caused by async/fixture issues or HA core updates. | High | High | Python/HA Core |
| **Entity Taxonomy** | Update `sensor.py` to disable advanced scientific sensors by default, reducing the post-install entity count from 50+ to ~15. | Low | High | Python |
| **README Rewrite** | Execute the `README-rewrite-plan.md` to flip the funnel from math-heavy to outcome-heavy. | Medium | High | Copywriting |
| **Update HACS Info** | Update `hacs.json` and move `info.md` content into the README per modern HACS standards. | Low | Medium | Markdown |

## P1: High-Impact UX Improvements (Launch Prep)
| Task | Description | Effort | Impact | Owner Skill |
|---|---|---|---|---|
| **Auto-Map Devices** | Add logic to `config_flow.py` to allow selecting an HA Device (e.g., Ecowitt hub) and auto-populating the 7 required sensor dropdowns based on state classes. | High | High | Python/HA Config Flow |
| **GitHub Templates** | Add `.github/ISSUE_TEMPLATE` and `PULL_REQUEST_TEMPLATE` to guide community contributions. | Low | Medium | GitHub Admin |
| **Dashboard Import** | Create a streamlined way (or better documentation) to import the `dashboards/` YAML, perhaps using a Lovelace strategy or Blueprint. | Medium | High | HA Frontend/YAML |

## P2: Community & Growth (Post-Launch)
| Task | Description | Effort | Impact | Owner Skill |
|---|---|---|---|---|
| **HACS Default Repo** | Submit `ws_core` to the HACS default repository list to remove the "add custom repository" friction. | Low | High | GitHub PRs |
| **Brands Repo PR** | Submit the `ws_core` icon to the `home-assistant/brands` repository so it looks native in the UI. | Low | Medium | Image editing/GitHub |
| **Enable Discussions** | Turn on GitHub Discussions and seed it with a "Show off your dashboard!" thread. | Low | Medium | GitHub Admin |

## P3: Long-Term Architecture
| Task | Description | Effort | Impact | Owner Skill |
|---|---|---|---|---|
| **De-couple Config Flow** | Split the monolithic 3,000-line `config_flow.py` into smaller, manageable files. | High | Low (Internal) | Python Architecture |
| **De-couple Coordinator** | Split the 6,000-line `coordinator.py` into distinct update classes based on feature flags. | High | Low (Internal) | Python Architecture |
