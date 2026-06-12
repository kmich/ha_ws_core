# Social preview image

GitHub shows a 1280x640 pixel image when the repository URL is shared on social
media, messaging apps, and link previews.

---

## Specification

| Property | Value |
|---|---|
| Dimensions | 1280 x 640 px |
| Format | PNG or JPG |
| Background | Dark (HA dark theme colours: `#111827` or `#1c1c2e`) |
| Primary text | Weather Station Core |
| Tagline | 150+ sensors · nowcast · UTCI · fire danger · Zambretti |
| Content | Dashboard screenshot composite |

---

## Recommended content

Use a composite of two screenshots:
1. The "Now" view of `ws_core_dashboard.yaml` showing `sensor.ws_minutes_until_rain`
   with a live value, current conditions, and UTCI heat index
2. The "Advanced" view showing fire risk, ET₀, and pressure trend

Arrange them side-by-side with a dark background strip on the left containing the
integration name and tagline.

---

## Tooling options

### Option A: Canva (browser-based, free)

1. Create a new design at 1280x640 px
2. Set background to dark (#111827)
3. Add a left column with text:
   - Large: "Weather Station Core"
   - Small: "ws_core for Home Assistant"
   - Bullet list: "150+ sensors · Nowcast · UTCI · Fire danger · Zambretti"
4. Add screenshots on the right half
5. Export as PNG

### Option B: GIMP / Photoshop (desktop)

Create a 1280x640 px canvas, dark background, paste screenshots, add text layer.

### Option C: Python (automated)

```python
from PIL import Image, ImageDraw, ImageFont

bg = Image.new('RGB', (1280, 640), '#111827')

# Paste dashboard screenshot (crop to fit right half)
screenshot = Image.open('screenshots/dashboard-weather.png')
screenshot = screenshot.resize((700, 640), Image.LANCZOS)
bg.paste(screenshot, (580, 0))

# Add dark overlay on left
overlay = Image.new('RGBA', (620, 640), (17, 24, 39, 220))
bg.paste(overlay, (0, 0))

# Add text (requires font file)
draw = ImageDraw.Draw(bg)
# ... add text

bg.save('docs/promotion/social_preview/social_preview.png')
```

---

## How to set the social preview

1. Go to https://github.com/kmich/ha_ws_core
2. Click **Settings** (top navigation)
3. Scroll to **Social preview** in the main settings page
4. Click **Edit** and upload the PNG file
5. Save

The preview updates within a few minutes and is visible when the URL is shared.
