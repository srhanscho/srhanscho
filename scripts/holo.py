"""Turn a cut-out portrait and the logo into hologram assets for the hero.

Usage:
    python scripts/holo.py portrait.png isotipo.png data/holo.json preview.png

Portrait: RGBA with a transparent background. The photo is mapped to a cyan
ramp and gets baked scanlines and a bottom fade.
"""
import base64
import io
import json
import sys

import numpy as np
from PIL import Image, ImageFilter, ImageOps

PORTRAIT, LOGO, OUT_JSON, OUT_PREVIEW = sys.argv[1:5]

CROP = (40, 150, 1064, 1180)
OUT_W = 460
DEEP, MID, HOT = np.array([8, 46, 60]), np.array([63, 232, 240]), np.array([232, 254, 255])

# ---- photo -> hologram ----------------------------------------------------------------
src = Image.open(PORTRAIT).convert("RGBA").crop(CROP)
scale = OUT_W / src.width
src = src.resize((OUT_W, round(src.height * scale)), Image.LANCZOS)
W, H = src.size

alpha = np.asarray(src.getchannel("A"), dtype=float) / 255.0
gray = ImageOps.autocontrast(src.convert("L"), cutoff=1)
lum = np.asarray(gray, dtype=float) / 255.0
edges = np.asarray(gray.filter(ImageFilter.FIND_EDGES).filter(ImageFilter.GaussianBlur(0.6)), dtype=float) / 255.0

tone = np.clip(lum ** 1.15 + edges * 1.0, 0, 1)
rgb = np.where(tone[..., None] < 0.55,
               DEEP + (MID - DEEP) * (tone[..., None] / 0.55),
               MID + (HOT - MID) * ((tone[..., None] - 0.55) / 0.45))

a = alpha * (0.22 + 0.78 * tone)
a[::3, :] *= 0.42                                   # scanlines
ys = np.linspace(0, 1, H)[:, None]
a *= np.clip((0.86 - ys) / 0.26, 0, 1) ** 1.3       # fade the shirt out
holo = np.dstack([rgb, a * 255]).clip(0, 255).astype(np.uint8)
holo_img = Image.fromarray(holo, "RGBA")

buf = io.BytesIO()
holo_img.save(buf, "WEBP", quality=82, method=6)
photo_b64 = base64.b64encode(buf.getvalue()).decode()

# ---- logo ---------------------------------------------------------------------------------
logo = Image.open(LOGO).convert("RGBA")
logo = logo.resize((140, round(140 * logo.height / logo.width)), Image.LANCZOS)
la = np.asarray(logo.getchannel("A"))
logo_img = Image.fromarray(np.dstack([np.full(la.shape + (3,), MID, dtype=np.uint8), la]), "RGBA")
lbuf = io.BytesIO()
logo_img.save(lbuf, "PNG", optimize=True)

json.dump({
    "size": [W, H],
    "photo": "data:image/webp;base64," + photo_b64,
    "logo": "data:image/png;base64," + base64.b64encode(lbuf.getvalue()).decode(),
    "logoSize": list(logo_img.size),
}, open(OUT_JSON, "w", encoding="utf-8"))

prev = Image.new("RGBA", (W, H), (20, 18, 31, 255))
prev.alpha_composite(holo_img)
prev.convert("RGB").save(OUT_PREVIEW)
print("photo kb", len(photo_b64) // 1024)
