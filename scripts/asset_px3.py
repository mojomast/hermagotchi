#!/usr/bin/env python3
"""launch-003 low-res pixel helpers: native 32x32 grid, x16 nearest upscale to 512."""
from __future__ import annotations
import numpy as np
from PIL import Image
from scipy import ndimage

FACTOR = 16; N = 512 // FACTOR; BASE_N = 448 // FACTOR   # 32 grid, baseline row 28
OUTLINE = (16, 14, 28)

def to_native_mode(keyed, colors, height=None, width=None, min_area_frac=0.0, outline=True):
    """Palette-first downscale: quantize the full-res source to `colors` flat colours, then each
    native cell takes the MODE colour of its source pixels (alpha = coverage > 50%). Mode keeps
    tiny flat accents (eyes, patches) that box-averaging smears."""
    a0 = np.asarray(keyed).copy()
    if min_area_frac:  # drop detached confetti
        lab, n = ndimage.label(a0[..., 3] > 128); sizes = ndimage.sum(np.ones_like(lab), lab, range(1, n + 1))
        keep = np.isin(lab, [i + 1 for i, s in enumerate(sizes) if s >= sizes.max() * min_area_frac])
        a0[..., 3] = np.where(keep, a0[..., 3], 0)
    m0 = a0[..., 3] > 128
    ys, xs = np.nonzero(m0); a0 = a0[ys.min():ys.max() + 1, xs.min():xs.max() + 1]; m0 = a0[..., 3] > 128
    h, w = m0.shape; s = (height / h) if height else (width / w)
    tw, th = max(1, round(w * s)), max(1, round(h * s))
    q = Image.fromarray(a0[m0][:, :3].reshape(-1, 1, 3)).quantize(colors, method=Image.Quantize.MAXCOVERAGE, dither=Image.Dither.NONE)
    pal = np.array(q.getpalette()[: colors * 3]).reshape(-1, 3)
    idx = np.full(m0.shape, -1, int); idx[m0] = np.asarray(q).reshape(-1)
    out = np.zeros((th, tw, 4), np.uint8)
    yb = np.linspace(0, h, th + 1).astype(int); xb = np.linspace(0, w, tw + 1).astype(int)
    for j in range(th):
        for i in range(tw):
            cell = idx[yb[j]:yb[j + 1], xb[i]:xb[i + 1]].ravel()
            if cell.size == 0 or (cell >= 0).mean() < 0.5: continue
            v = cell[cell >= 0]; out[j, i, :3] = pal[np.bincount(v, minlength=colors).argmax()]; out[j, i, 3] = 255
    m = out[..., 3] > 0
    out[m & (out[..., :3].max(-1) < 70), :3] = OUTLINE          # shared outline colour
    if outline:                                                 # 1px silhouette outline
        edge = m & ~ndimage.binary_erosion(m, structure=np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]]))
        out[edge, :3] = OUTLINE
    return Image.fromarray(out, "RGBA")

def place_native(native, x, y):
    cv = Image.new("RGBA", (N, N)); cv.paste(native, (x, y), native); return cv

def up(cv): return cv.resize((cv.width * FACTOR, cv.height * FACTOR), Image.NEAREST)
