# Adoption tracking

Update this table weekly. The goal is to track leading indicators (stars, forum
engagement) against lagging indicators (analytics installs) so you know which
distribution channel is driving actual adoption.

---

## Weekly metrics

| Date | Stars | Forks | Open issues | Forum thread replies | Reddit upvotes | Analytics installs |
|---|---|---|---|---|---|---|
| 2026-06-12 (baseline) | 11 | — | — | 0 (thread not posted) | 0 | not yet available |

---

## How to fill in each column

**Stars:** visible on the repository homepage (top right).

**Forks:** visible on the repository homepage under the fork count.

**Open issues:** go to the Issues tab and note the count on the "Open" label.

**Forum thread replies:** count the replies on the community.home-assistant.io
launch thread once it is posted.

**Reddit upvotes:** check the r/homeassistant post score after 24 hours, then weekly.

**Analytics installs:** once the integration appears in the HACS default store and
brands are registered, visit https://analytics.home-assistant.io and search for
`ws_core`. This typically becomes available 2-4 weeks after default-store acceptance.

---

## Analytics eligibility

HA analytics counts installations that are:
1. In the HACS default store (not custom repositories)
2. Have brand assets registered in `home-assistant/brands`
3. Reported by installations with analytics enabled

The expected timeline from HACS default-store acceptance to analytics data:
- Analytics data is collected and reported daily
- The brand must appear in `home-assistant/brands` for the integration to be
  counted in analytics (the brand lookup happens at the analytics endpoint)
- First analytics data: approximately 24-72 hours after default-store acceptance
  and brands merge

---

## Leading indicators to watch

The star count should grow by at least 50% within 2 weeks of the forum thread launch.
If it does not, the thread needs a more compelling opening or better screenshots.

Forum thread reply velocity (replies per day) is the best signal for whether the
content resonated. A thread with 5+ replies in the first 48 hours is performing well.

Reddit posts in r/homeassistant: a score of 50+ within 24 hours indicates good fit.

---

## Target milestones

| Milestone | Target date | Status |
|---|---|---|
| Forum launch thread posted | Within 48h of HACS default-store acceptance | Pending |
| Reddit post | 1 week after forum thread | Pending |
| 100 GitHub stars | 30 days after forum launch | Pending |
| First analytics data | 2-4 weeks after HACS default-store acceptance | Pending |
| 500 analytics installs | 90 days after HACS default-store acceptance | Pending |
