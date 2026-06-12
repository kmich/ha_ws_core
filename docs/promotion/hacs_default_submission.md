# HACS Default Store Submission

## Pre-submission checklist

Complete every item before opening the PR. A failed item is a rejection.

- [ ] **Brands PR merged.** The `ws_core` brand must appear in `home-assistant/brands` under `custom_integrations/ws_core/` before HACS will accept a default-store submission. See `docs/promotion/brands_pr/` for the exact files and PR description.
- [ ] **`ignore: brands` removed from `.github/workflows/hacs.yml`** (line 18). Only do this after the brands PR is merged; removing it before will break CI.
- [ ] **CI green on `main`.** All six jobs in `validate.yml` must pass: hassfest, hacs, lint, tests, no-bytecode, version-consistency, entity-validator.
- [ ] **GitHub release exists for the current version.** The release tag must exactly match the `version` field in `manifest.json`. Releases are at https://github.com/kmich/ha_ws_core/releases.
- [ ] **At least one tagged release is available.** HACS requires the latest release to be downloadable; verify the release ZIP contains `custom_components/ws_core/` at the root.
- [ ] **Repository is public.**
- [ ] **`codeowners` in `manifest.json` lists your actual GitHub username** (currently `@kmich`). Verify by visiting `https://github.com/kmich` — if that redirects or 404s, correct it.
- [ ] **`documentation` URL in `manifest.json` resolves** to a page that describes the integration.
- [ ] **GitHub topics set** on the repository. See the topics list below.
- [ ] **README renders cleanly** with `render_readme: true` in `hacs.json`. Check by viewing the repo in a browser.

## Required GitHub topics

Set these in the repository settings (About section, gear icon, "Topics"):

```
home-assistant
hacs
custom-integration
weather
weather-station
personal-weather-station
zambretti
nowcasting
fire-weather-index
utci
evapotranspiration
lightning-detection
thermal-comfort
```

That is 13 topics. GitHub allows up to 20, leaving room for: `mqtt`, `home-automation`, `open-meteo`, `penman-monteith`, `fwi`, `kalman-filter`.

## PR to hacs/default

Fork `hacs/default`, edit `custom_integrations.json`, open a PR.

### Fork and edit steps

1. Fork https://github.com/hacs/default
2. In the fork, open `custom_integrations.json`
3. Add the following entry in alphabetical order (between existing entries starting with "W"):

```json
{
  "kmich/ha_ws_core": "integration"
}
```

The file is a JSON object where each key is `owner/repo` and each value is the category string.

### PR title

```
Add Weather Station Core (ws_core)
```

### PR description

```markdown
## Category
Integration

## Repository
https://github.com/kmich/ha_ws_core

## Description
Weather Station Core transforms raw personal weather station data into a complete
weather intelligence system. It produces 150+ derived sensors from 7 required
inputs: temperature, humidity, pressure, wind speed, wind gust, wind direction,
and cumulative rainfall.

Key capabilities not available in any other Home Assistant weather integration:
- Precipitation nowcast: `sensor.ws_minutes_until_rain` from Open-Meteo 15-min buckets
- UTCI (Universal Thermal Climate Index, full Bröde 2012 polynomial)
- McArthur FFDI (Australia) + Fosberg FFWI (US/global) fire danger
- Complete Canadian FWI system with persistent daily moisture memory (Van Wagner 1987)
- Zambretti barometric forecast (original Negretti & Zambra 1915 lookup table)
- 8 independent upload targets (Weather Underground, Weathercloud, PWSWeather, WOW, AWEKAS, CWOP, OpenWeatherMap Stations, Windy)
- MQTT Discovery republishing of 70+ derived sensors

## Checklist
- [x] I've read and followed the submission guidelines
- [x] The integration passes `hacs/action` validation (validate.yml CI)
- [x] The integration passes `home-assistant/actions/hassfest` (validate.yml CI)
- [x] A GitHub release exists for the current version (v2.0.7)
- [x] Brand assets are registered in home-assistant/brands (PR #XXXX — fill in after brands merge)
- [x] The repository is public
```

Replace `#XXXX` with the actual home-assistant/brands PR number after it merges.

## After submission

- HACS maintainers usually review within 1-4 weeks.
- They may request changes to `manifest.json` or `hacs.json`. Watch for PR review comments.
- Once merged, the integration appears in the HACS default store within ~24 hours of the next store index rebuild.
- Update the README badge from `HACS-Custom` to `HACS` (see badge URLs in README footer).

## HACS badge update

After default-store acceptance, update the badge at the bottom of `README.md`:

```markdown
[hacs-badge]: https://img.shields.io/badge/HACS-Default-41BDF5.svg
[hacs-url]: https://hacs.xyz
```

(Change "Custom" to "Default" and point the URL to hacs.xyz instead of the integration page.)
