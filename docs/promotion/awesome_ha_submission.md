# awesome-home-assistant submission

## Target list

**Repository:** https://github.com/frenck/awesome-home-assistant
**Target section:** `## Custom Integrations` (or the most appropriate subsection;
check the current state of the file before submitting as sections evolve)

If there is a "Weather" or "Sensors" subsection under Custom Integrations, use that.
Otherwise, use the general Custom Integrations section in alphabetical order.

## The entry (one line)

```markdown
- [Weather Station Core](https://github.com/kmich/ha_ws_core) - Derives 150+ sensors from any personal weather station: local Zambretti forecast, precipitation nowcast (minutes until rain), UTCI/WBGT heat stress, fire danger (FWI/FFDI/FFWI), Penman-Monteith ET₀, lightning detection, 8 upload targets, 8 translations.
```

## Submission steps

1. Fork https://github.com/frenck/awesome-home-assistant
2. Open `README.md` in the fork
3. Find the correct section (Custom Integrations, or Weather subsection)
4. Insert the entry in alphabetical order by display name — "Weather Station Core"
   sorts after "Weather" and before most other entries starting with "X" or "Z"
5. Open a PR

## PR title

```
Add Weather Station Core
```

## PR description

```markdown
## What this adds

**Weather Station Core** (`ws_core`) is a Home Assistant custom integration that
derives 150+ sensors from personal weather station data.

Capabilities not available in other HA weather integrations:
- Precipitation nowcast: `sensor.ws_minutes_until_rain` (Open-Meteo 15-min buckets)
- UTCI (Universal Thermal Climate Index, Bröde 2012 polynomial)
- Three fire danger systems: Canadian FWI, McArthur FFDI, Fosberg FFWI
- Zambretti barometric forecast (local, no network, original 1915 lookup table)
- Penman-Monteith ET₀ (Smart Irrigation compatible)

**Repository:** https://github.com/kmich/ha_ws_core
**HACS:** Available as custom repository; default store submission pending.

## Checklist
- [ ] The integration is working and maintained (last release: 2026-06-11)
- [ ] The link points to the repository (not a store page)
- [ ] The description is concise and factual
- [ ] The entry is in alphabetical order within its section
```

## Timing

Submit this PR after the HACS default store submission is open (or accepted) so
the entry can reference both. If awesome-ha requires default-store inclusion, wait
for that first; check the list's contribution guidelines before submitting.
