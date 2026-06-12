# Brands PR for home-assistant/brands

This document contains everything needed to open the PR that registers ws_core in the
official Home Assistant brands repository. This is a prerequisite for HACS default
store inclusion.

## Background

The `home-assistant/brands` repository stores logo assets for all integrations that
appear in the Home Assistant UI and the HACS default store. Your brand assets already
exist in the repo under `custom_components/ws_core/brand/`. This PR copies them to the
correct location in the brands repository.

## Files to copy

The brands repository expects this directory structure:

```
custom_integrations/
  ws_core/
    icon.png        (256 x 256 px, PNG with transparency)
    icon@2x.png     (512 x 512 px, PNG with transparency)
    dark_icon.png   (256 x 256 px, for dark themes)
    dark_icon@2x.png (512 x 512 px, for dark themes)
```

Source files are in your repo at:
- `custom_components/ws_core/brand/icon.png`
- `custom_components/ws_core/brand/icon@2x.png`
- `custom_components/ws_core/brand/dark_icon.png`
- `custom_components/ws_core/brand/dark_icon@2x.png`

Verify the pixel dimensions before submitting:
```bash
python3 -c "
from PIL import Image
for name in ['icon.png', 'icon@2x.png', 'dark_icon.png', 'dark_icon@2x.png']:
    img = Image.open(f'custom_components/ws_core/brand/{name}')
    print(name, img.size)
"
```

Expected: `(256, 256)`, `(512, 512)`, `(256, 256)`, `(512, 512)`.

If sizes differ, resize with:
```bash
pip install pillow
python3 - <<'PY'
from PIL import Image
sizes = {'icon.png': 256, 'icon@2x.png': 512, 'dark_icon.png': 256, 'dark_icon@2x.png': 512}
for name, size in sizes.items():
    img = Image.open(f'custom_components/ws_core/brand/{name}').convert('RGBA')
    img = img.resize((size, size), Image.LANCZOS)
    img.save(f'/tmp/brands_ws_core/{name}')
PY
```

## Submission steps

1. Fork https://github.com/home-assistant/brands
2. In the fork, create the directory `custom_integrations/ws_core/`
3. Copy the four PNG files (at correct sizes) into that directory
4. Open a PR

## PR title

```
Add ws_core (Weather Station Core) brand assets
```

## PR description

```markdown
## Integration details

- **Domain:** `ws_core`
- **Repository:** https://github.com/kmich/ha_ws_core
- **HACS:** Currently available as a custom repository; submitting to HACS default store.

## What this PR adds

Brand assets for the `ws_core` integration (Weather Station Core), a Home Assistant
custom integration that derives 150+ sensors from personal weather station data.

Assets included:
- `icon.png` (256x256)
- `icon@2x.png` (512x512)
- `dark_icon.png` (256x256)
- `dark_icon@2x.png` (512x512)

## Checklist

- [ ] The domain `ws_core` matches the integration's `manifest.json` domain field
- [ ] All four PNG files are included at the correct pixel dimensions
- [ ] Icons use transparency (RGBA) and are readable on both light and dark backgrounds
- [ ] This is a new entry (not an update to an existing brand)
```

## After the PR is merged

1. Update `.github/workflows/hacs.yml`: remove the `ignore: brands` line (line 18)
2. Commit and push — CI will now run full HACS validation including brand check
3. Proceed with the hacs/default submission (see `hacs_default_submission.md`)
