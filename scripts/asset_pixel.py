#!/usr/bin/env python3
"""launch-002 true-pixel-art pipeline helpers.
Generated source -> chroma key -> box downscale to native grid (1 native px = FACTOR canvas px)
-> binary alpha -> palette quantize with shared outline -> 1px outline enforcement
-> nearest-neighbour integer upscale to 512x512."""
from __future__ import annotations
import colorsys
import numpy as np
from PIL import Image
from scipy import ndimage

FACTOR = 4; N = 512 // FACTOR; BASE_N = 448 // FACTOR
OUTLINE = (20, 26, 51)

def to_native(keyed: Image.Image, height=None, width=None) -> Image.Image:
    im = keyed.crop(keyed.getchannel("A").point(lambda v: 255 if v > 20 else 0).getbbox())
    w, h = im.size; s = (height / h) if height else (width / w)
    tw, th = max(1, round(w * s)), max(1, round(h * s))
    a = np.asarray(im).astype(np.float32) / 255
    pre = np.dstack([a[..., :3] * a[..., 3:4], a[..., 3:4]])
    small = np.asarray(Image.fromarray((pre * 255).astype(np.uint8), "RGBA").resize((tw, th), Image.BOX)).astype(np.float32) / 255
    al = small[..., 3]; rgb = small[..., :3] / np.maximum(al[..., None], 1e-3)
    binary = al > 0.5
    out = np.dstack([np.clip(rgb, 0, 1) * 255, binary * 255]).astype(np.uint8)
    return Image.fromarray(out, "RGBA")

def quantize(native: Image.Image, colors=20, outline=True) -> Image.Image:
    a = np.asarray(native).copy(); m = a[..., 3] > 0
    px = a[m][:, :3]
    q = Image.fromarray(px.reshape(-1, 1, 3)).quantize(colors, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE)
    pal = np.array(q.getpalette()[: colors * 3]).reshape(-1, 3)
    idx = np.asarray(q).reshape(-1); newpx = pal[idx]
    dark = newpx.max(1) < 75                       # snap darks to shared outline colour
    newpx[dark] = OUTLINE
    a[m, :3] = newpx
    if outline:                                    # crisp 1px silhouette outline
        edge = m & ~ndimage.binary_erosion(m, structure=np.ones((3, 3)))
        a[edge, :3] = OUTLINE
    a[~m] = 0
    return Image.fromarray(a, "RGBA")

def place_native(native: Image.Image, x: int, y: int) -> Image.Image:
    cv = Image.new("RGBA", (N, N)); cv.paste(native, (x, y), native); return cv

def up(native_canvas: Image.Image) -> Image.Image:
    return native_canvas.resize((native_canvas.width * FACTOR, native_canvas.height * FACTOR), Image.NEAREST)

def down(canvas: Image.Image) -> Image.Image:
    return canvas.resize((canvas.width // FACTOR, canvas.height // FACTOR), Image.NEAREST)

def palette_swap(native: Image.Image, hue_deg, sat_mul, val_mul, protect) -> Image.Image:
    """Index-style swap: build colour->colour LUT over the sprite's unique colours.
    protect(r,g,b)->bool keeps eyes/patch/outline/highlight ramps fixed."""
    a = np.asarray(native).copy(); m = a[..., 3] > 0
    cols = {tuple(c) for c in a[m][:, :3]}
    lut = {}
    for c in cols:
        r, g, b = (v / 255 for v in c); h, s, v = colorsys.rgb_to_hsv(r, g, b)
        if c == OUTLINE or protect(c, h, s, v):
            lut[c] = c; continue
        nr, ng, nb = colorsys.hsv_to_rgb((h + hue_deg / 360) % 1, min(1, s * sat_mul), min(1, v * val_mul))
        lut[c] = (round(nr * 255), round(ng * 255), round(nb * 255))
    flat = a[m][:, :3]
    a[m, :3] = np.array([lut[tuple(c)] for c in flat], dtype=np.uint8)
    return Image.fromarray(a, "RGBA")
