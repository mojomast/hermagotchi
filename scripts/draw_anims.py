#!/usr/bin/env python3
"""Hand-author pet state animations at native 32px (NO GenerateImage).

Derives frames from existing palette sprites via pixel transforms + small edits:
  idle   — 1px bob + blink (daemowl blinks all three eyes)
  happy  — hop/bounce
  eat    — chomp (mouth squash)
  sleep  — eyes closed + Zz
  hurt   — flash + recoil
  attack — lunge

Writes horizontal sprite strips under assets/px3/anims/, updates
manifest.launch-003.json animations{} + art_ext.launch-003.json animations{}.
"""
from __future__ import annotations
import hashlib, json, math
from pathlib import Path
from copy import deepcopy
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
A = ROOT / "assets"
OUT = A / "px3" / "anims"
N = 32
OUTLINE = (16, 14, 28)

STATES = ("idle", "happy", "eat", "sleep", "hurt", "attack")

# fps / loop / frame counts
CLIP_META = {
    "idle":   {"fps": 6,  "loop": True,  "n": 4},
    "happy":  {"fps": 8,  "loop": True,  "n": 4},
    "eat":    {"fps": 6,  "loop": True,  "n": 3},
    "sleep":  {"fps": 3,  "loop": True,  "n": 3},
    "hurt":   {"fps": 10, "loop": False, "n": 3},
    "attack": {"fps": 10, "loop": False, "n": 4},
}

# Eye ROIs (x0,y0,x1,y1) inclusive, native — lids painted over these for blink/sleep.
# Tuned to face anchors; daemowl includes forehead third eye.
EYES = {
    "byteblob":   [(11, 15, 13, 17), (16, 15, 18, 17)],
    "patchfox":   [(11, 13, 13, 15), (17, 13, 19, 15)],
    "nullgeist":  [(11, 11, 13, 14), (18, 11, 20, 14)],
    "kernelcrab": [(12, 16, 14, 18), (17, 16, 19, 18)],
    "cachebat":   [(11, 13, 13, 15), (18, 13, 20, 15)],
    "stacktoise": [(12, 11, 14, 13), (17, 11, 19, 13)],
    "daemowl":    [(11, 13, 13, 15), (17, 13, 19, 15), (14, 9, 16, 11)],  # + third
    "shellsnail": [(10, 16, 12, 18), (14, 15, 16, 17)],  # stalk tips approx
    "regexopus":  [(11, 12, 13, 14), (17, 12, 19, 14)],
    "firewyrm":   [(12, 11, 14, 13), (16, 11, 18, 13)],
}

def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()

def load_native(rel: str) -> Image.Image:
    im = Image.open(A / rel).convert("RGBA")
    if im.size != (N, N):
        im = im.resize((N, N), Image.NEAREST)
    return im

def to_arr(im: Image.Image) -> np.ndarray:
    return np.array(im, dtype=np.uint8)

def from_arr(a: np.ndarray) -> Image.Image:
    return Image.fromarray(a, "RGBA")

def shift(im: Image.Image, dx: int, dy: int) -> Image.Image:
    """Translate opaque content; clip to canvas (no wrap)."""
    a = to_arr(im)
    out = np.zeros_like(a)
    src_x0 = max(0, -dx); src_y0 = max(0, -dy)
    dst_x0 = max(0, dx); dst_y0 = max(0, dy)
    w = N - abs(dx); h = N - abs(dy)
    if w <= 0 or h <= 0:
        return from_arr(out)
    out[dst_y0:dst_y0+h, dst_x0:dst_x0+w] = a[src_y0:src_y0+h, src_x0:src_x0+w]
    return from_arr(out)

def sample_lid_color(a: np.ndarray, box) -> tuple[int, int, int]:
    x0, y0, x1, y1 = box
    # sample just above the eye box for body/lid colour
    samples = []
    for y in range(max(0, y0 - 2), y0):
        for x in range(x0, x1 + 1):
            r, g, b, al = a[y, x]
            if al > 200 and (r, g, b) != OUTLINE:
                samples.append((int(r), int(g), int(b)))
    if not samples:
        # fallback: any opaque non-outline near box
        for y in range(max(0, y0 - 3), min(N, y1 + 3)):
            for x in range(max(0, x0 - 3), min(N, x1 + 3)):
                r, g, b, al = a[y, x]
                if al > 200 and (r, g, b) != OUTLINE and not (r > 200 and g > 200 and b > 200):
                    samples.append((int(r), int(g), int(b)))
    if not samples:
        return (80, 70, 90)
    # median
    samples.sort()
    return samples[len(samples) // 2]

def close_eyes(im: Image.Image, species: str, partial: bool = False) -> Image.Image:
    a = to_arr(im).copy()
    for box in EYES.get(species, []):
        x0, y0, x1, y1 = box
        lid = sample_lid_color(a, box)
        mid_y = (y0 + y1) // 2
        if partial:
            # half-lid: only top half of eye
            for y in range(y0, mid_y + 1):
                for x in range(x0, x1 + 1):
                    if a[y, x, 3] > 0:
                        a[y, x, :3] = lid
        else:
            for y in range(y0, y1 + 1):
                for x in range(x0, x1 + 1):
                    if a[y, x, 3] > 0:
                        a[y, x, :3] = lid
            # draw a 1px crease
            for x in range(x0, x1 + 1):
                if 0 <= mid_y < N and a[mid_y, x, 3] > 0:
                    a[mid_y, x, :3] = OUTLINE
    return from_arr(a)

def flash_white(im: Image.Image, amount: float = 0.55) -> Image.Image:
    a = to_arr(im).astype(np.float32)
    mask = a[..., 3] > 0
    for c in range(3):
        a[..., c][mask] = a[..., c][mask] * (1 - amount) + 255 * amount
    a = np.clip(a, 0, 255).astype(np.uint8)
    return from_arr(a)

def squash_y(im: Image.Image, factor: float = 0.85, pivot: int = 28) -> Image.Image:
    """Simple vertical squash toward ground pivot."""
    a = to_arr(im)
    out = np.zeros_like(a)
    for y in range(N):
        # map source y
        src_y = int(round(pivot - (pivot - y) / factor))
        if 0 <= src_y < N:
            out[y] = a[src_y]
    return from_arr(out)

def draw_zz(im: Image.Image, phase: int = 0) -> Image.Image:
    a = to_arr(im).copy()
    # small Zz near top-right of head
    col = (240, 240, 255)
    ox, oy = 22, 6 - (phase % 2)
    # Z shape 3x3
    pts = [(0, 0), (1, 0), (2, 0), (1, 1), (0, 2), (1, 2), (2, 2)]
    for dx, dy in pts:
        x, y = ox + dx, oy + dy
        if 0 <= x < N and 0 <= y < N:
            a[y, x, :3] = col
            a[y, x, 3] = 255
    # smaller z
    for dx, dy in [(0, 0), (1, 0), (1, 1), (0, 2), (1, 2)]:
        x, y = ox + 3 + dx, oy + 3 + dy
        if 0 <= x < N and 0 <= y < N:
            a[y, x, :3] = (200, 200, 230)
            a[y, x, 3] = 255
    return from_arr(a)

def chomp(im: Image.Image, open_amt: int) -> Image.Image:
    """Pull lower half down slightly / push up for chomp."""
    if open_amt == 0:
        return squash_y(im, 0.92, pivot=26)
    # open: shift lower body down 1
    a = to_arr(im)
    out = a.copy()
    split = 20
    out[split + 1 :] = 0
    h = N - split - 1
    out[split + 1 : split + 1 + h - 1] = a[split : split + h - 1]
    return from_arr(out)

def make_frames(base: Image.Image, species: str, state: str) -> list[tuple[Image.Image, list[int]]]:
    """Return list of (frame_image, anchor_delta_xy) for state."""
    n = CLIP_META[state]["n"]
    frames: list[tuple[Image.Image, list[int]]] = []
    if state == "idle":
        # 0 base, 1 bob up, 2 blink (+bob0), 3 bob up
        seq = [
            (base, [0, 0]),
            (shift(base, 0, -1), [0, -1]),
            (close_eyes(base, species), [0, 0]),
            (shift(base, 0, -1), [0, -1]),
        ]
        frames = seq[:n]
    elif state == "happy":
        seq = [
            (shift(base, 0, -1), [0, -1]),
            (shift(base, 0, -3), [0, -3]),
            (shift(squash_y(base, 0.9, 28), 0, -1), [0, -1]),
            (base, [0, 0]),
        ]
        frames = seq[:n]
    elif state == "eat":
        seq = [
            (chomp(base, 1), [0, 0]),
            (chomp(base, 0), [0, 1]),
            (base, [0, 0]),
        ]
        frames = seq[:n]
    elif state == "sleep":
        closed = close_eyes(base, species)
        seq = [
            (draw_zz(closed, 0), [0, 1]),
            (draw_zz(shift(closed, 0, 1), 1), [0, 2]),
            (draw_zz(closed, 0), [0, 1]),
        ]
        frames = seq[:n]
    elif state == "hurt":
        seq = [
            (flash_white(shift(base, -2, 0), 0.65), [-2, 0]),
            (shift(base, -1, 1), [-1, 1]),
            (base, [0, 0]),
        ]
        frames = seq[:n]
    elif state == "attack":
        seq = [
            (shift(base, -1, 0), [-1, 0]),  # wind-up
            (shift(base, 3, -1), [3, -1]),  # lunge
            (shift(base, 2, 0), [2, 0]),
            (base, [0, 0]),
        ]
        frames = seq[:n]
    else:
        frames = [(base, [0, 0])]
    return frames

def strip_from_frames(frames: list[Image.Image]) -> Image.Image:
    strip = Image.new("RGBA", (N * len(frames), N), (0, 0, 0, 0))
    for i, fr in enumerate(frames):
        strip.paste(fr, (i * N, 0), fr)
    return strip

def build_all():
    man = json.loads((A / "manifest.launch-003.json").read_text())
    ext = json.loads((A / "art_ext.launch-003.json").read_text())
    OUT.mkdir(parents=True, exist_ok=True)

    clips = []
    ext_anims = {
        "schema": "hermagotchi-anims-v1",
        "native_size": N,
        "states": list(STATES),
        "clip_meta": CLIP_META,
        "eyes": EYES,
        "clips": {},
    }

    for sp, sd in ext["species"].items():
        for pal, pd in sd["palettes"].items():
            base = load_native(pd["path"])
            for state in STATES:
                framed = make_frames(base, sp, state)
                imgs = [f for f, _ in framed]
                deltas = [d for _, d in framed]
                strip = strip_from_frames(imgs)
                # also write hi-res ×16 for display packs if needed — keep native strip
                # Upscale strip with nearest for consistent px3 delivery (match items)
                F = ext.get("pixel_factor", 16)
                hi = strip.resize((strip.size[0] * F, strip.size[1] * F), Image.NEAREST)
                rel = f"px3/anims/{sp}_{pal}_{state}.png"
                path = A / rel
                hi.save(path, optimize=True)
                cid = f"{sp}.{pal}.{state}"
                meta = CLIP_META[state]
                entry = {
                    "id": cid,
                    "species": sp,
                    "palette": pal,
                    "state": state,
                    "path": rel,
                    "frame_w": N,
                    "frame_h": N,
                    "frame_count": len(imgs),
                    "fps": meta["fps"],
                    "loop": meta["loop"],
                    "sha256": sha(path),
                    "layout": "horizontal",
                    "frames": [
                        {
                            "i": i,
                            "anchor_delta": deltas[i],
                            "duration_ms": int(1000 / meta["fps"]),
                        }
                        for i in range(len(imgs))
                    ],
                }
                clips.append(entry)
                ext_anims["clips"][cid] = {
                    "path": rel,
                    "sha256": entry["sha256"],
                    "frame_count": entry["frame_count"],
                    "fps": entry["fps"],
                    "loop": entry["loop"],
                    "layout": "horizontal",
                    "frame_native": N,
                    "frames": entry["frames"],
                }

    man["animations"] = {
        "version": 1,
        "native_size": N,
        "pixel_factor": ext.get("pixel_factor", 16),
        "states": list(STATES),
        "clip_meta": {k: {"fps": v["fps"], "loop": v["loop"], "frame_count": v["n"]} for k, v in CLIP_META.items()},
        "clips": clips,
    }
    # notes touch
    note = man.get("notes", "")
    if "animations" not in note:
        man["notes"] = note.rstrip() + " Animations: per-palette state strips in px3/anims/ (see animations{})."

    ext["animations"] = ext_anims
    (A / "manifest.launch-003.json").write_text(json.dumps(man, indent=2) + "\n")
    (A / "art_ext.launch-003.json").write_text(json.dumps(ext, indent=2) + "\n")
    print(f"wrote {len(clips)} clips → {OUT}")
    return clips

if __name__ == "__main__":
    build_all()
