#!/usr/bin/env python3
"""Render opaque shop thumbnails for the launch-003 pixel pack (HGT-W11-C).

The shop pane sits on a dark card, and several aura/habitat layers are both
sparse and near-dark.  Every manifest item therefore gets a
``px3/thumbs/<item>_thumb.png`` composited on a light checkerboard with a dark
frame, so the desktop bridge can serve a readable thumbnail from its local
asset base without touching the source art.

The renderer is standard-library only (no Pillow/NumPy) so it can run and be
tested in the plugin sandbox::

    python3 scripts/render_shop_thumbs.py
    python3 scripts/render_shop_thumbs.py --check
"""

from __future__ import annotations

import argparse
import json
import struct
import sys
import zlib
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
DEFAULT_MANIFEST = ASSETS / "manifest.launch-003.json"
THUMB_DIR = ASSETS / "px3" / "thumbs"
THUMB_SIZE = 144
THUMB_PAD = 8
FRAME = 2
CHECKER_CELL = 8
LIGHT = (242, 245, 252)
SHADE = (215, 221, 237)
FRAME_COLOR = (42, 51, 80)

CHANNELS_BY_COLOR_TYPE = {0: 1, 2: 3, 4: 2, 6: 4}


def thumb_relpath(asset_id: str) -> str:
    """Return the pack-relative thumb path for a catalog/asset id."""

    text = str(asset_id or "").strip()
    short = text.rsplit(".", 1)[-1].lower()
    if short.endswith(".png"):
        short = short[:-4]
    safe = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in short)
    safe = safe.strip("_")
    if not safe:
        return ""
    return f"px3/thumbs/{safe}_thumb.png"


def _paeth(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    return b if pb <= pc else c


def decode_png(path: Path) -> tuple[int, int, int, bytes]:
    """Decode an 8-bit, non-interlaced PNG to ``(w, h, channels, pixels)``."""

    data = Path(path).read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"not a PNG: {Path(path).name}")
    offset = 8
    width = height = None
    color_type = None
    interlace = 0
    idat = bytearray()
    while offset < len(data):
        (length,) = struct.unpack(">I", data[offset : offset + 4])
        kind = data[offset + 4 : offset + 8]
        payload = data[offset + 8 : offset + 8 + length]
        offset += 12 + length
        if kind == b"IHDR":
            width, height, depth, color_type, _comp, _filter, interlace = struct.unpack(
                ">IIBBBBB", payload
            )
            if depth != 8 or interlace != 0:
                raise ValueError(f"unsupported PNG depth/interlace: {Path(path).name}")
            if color_type not in CHANNELS_BY_COLOR_TYPE:
                raise ValueError(f"unsupported PNG colour type: {Path(path).name}")
        elif kind == b"IDAT":
            idat.extend(payload)
        elif kind == b"IEND":
            break
    if width is None or height is None or color_type is None:
        raise ValueError(f"missing IHDR: {Path(path).name}")

    channels = CHANNELS_BY_COLOR_TYPE[color_type]
    stride = width * channels
    raw = zlib.decompress(bytes(idat))
    pixels = bytearray(height * stride)
    previous = bytearray(stride)
    source = 0
    for row in range(height):
        filter_type = raw[source]
        source += 1
        line = bytearray(raw[source : source + stride])
        source += stride
        if filter_type == 1:
            for index in range(channels, stride):
                line[index] = (line[index] + line[index - channels]) & 0xFF
        elif filter_type == 2:
            for index in range(stride):
                line[index] = (line[index] + previous[index]) & 0xFF
        elif filter_type == 3:
            for index in range(stride):
                left = line[index - channels] if index >= channels else 0
                line[index] = (line[index] + ((left + previous[index]) >> 1)) & 0xFF
        elif filter_type == 4:
            for index in range(stride):
                left = line[index - channels] if index >= channels else 0
                upper = previous[index]
                upper_left = previous[index - channels] if index >= channels else 0
                line[index] = (
                    line[index] + _paeth(left, upper, upper_left)
                ) & 0xFF
        elif filter_type != 0:
            raise ValueError(f"unsupported PNG filter {filter_type}")
        pixels[row * stride : (row + 1) * stride] = line
        previous = line
    return width, height, channels, bytes(pixels)


def _chunk(kind: bytes, payload: bytes) -> bytes:
    return (
        struct.pack(">I", len(payload))
        + kind
        + payload
        + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
    )


def encode_png_rgb(width: int, height: int, pixels: bytes) -> bytes:
    if len(pixels) != width * height * 3:
        raise ValueError("pixel buffer does not match RGB dimensions")
    rows = bytearray()
    stride = width * 3
    for row in range(height):
        rows.append(0)
        rows.extend(pixels[row * stride : (row + 1) * stride])
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", header)
        + _chunk(b"IDAT", zlib.compress(bytes(rows), 9))
        + _chunk(b"IEND", b"")
    )


def _rgba_at(channels: int, pixels: bytes, index: int) -> tuple[int, int, int, int]:
    offset = index * channels
    if channels == 4:
        return (
            pixels[offset],
            pixels[offset + 1],
            pixels[offset + 2],
            pixels[offset + 3],
        )
    if channels == 3:
        return (pixels[offset], pixels[offset + 1], pixels[offset + 2], 255)
    if channels == 2:
        gray, alpha = pixels[offset], pixels[offset + 1]
        return (gray, gray, gray, alpha)
    gray = pixels[offset]
    return (gray, gray, gray, 255)


def _checkerboard(size: int) -> bytearray:
    pixels = bytearray(size * size * 3)
    for y in range(size):
        row = y // CHECKER_CELL
        for x in range(size):
            colour = LIGHT if ((x // CHECKER_CELL) + row) % 2 == 0 else SHADE
            offset = (y * size + x) * 3
            pixels[offset : offset + 3] = bytes(colour)
    return pixels


def _paint_frame(canvas: bytearray, size: int) -> None:
    for y in range(size):
        for x in range(size):
            if x < FRAME or y < FRAME or x >= size - FRAME or y >= size - FRAME:
                offset = (y * size + x) * 3
                canvas[offset : offset + 3] = bytes(FRAME_COLOR)


def render_thumbnail(
    source: Path,
    destination: Path,
    size: int = THUMB_SIZE,
    padding: int = THUMB_PAD,
) -> bytes:
    """Composite one source layer over a light checkerboard and save it."""

    width, height, channels, pixels = decode_png(source)
    canvas = _checkerboard(size)

    inner = max(1, size - (padding * 2))
    scale = min(inner / width, inner / height)
    target_w = max(1, round(width * scale))
    target_h = max(1, round(height * scale))
    left = (size - target_w) // 2
    top = (size - target_h) // 2

    for y in range(target_h):
        source_y = min(height - 1, int(y * height / target_h))
        for x in range(target_w):
            source_x = min(width - 1, int(x * width / target_w))
            red, green, blue, alpha = _rgba_at(
                channels, pixels, source_y * width + source_x
            )
            if alpha == 0:
                continue
            offset = ((top + y) * size + (left + x)) * 3
            if alpha >= 255:
                canvas[offset : offset + 3] = bytes((red, green, blue))
            else:
                base = canvas[offset : offset + 3]
                canvas[offset : offset + 3] = bytes(
                    (value * alpha + base[index] * (255 - alpha)) // 255
                    for index, value in enumerate((red, green, blue))
                )

    _paint_frame(canvas, size)
    payload = encode_png_rgb(size, size, bytes(canvas))
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(payload)
    return payload


def manifest_assets(manifest_path: Path = DEFAULT_MANIFEST) -> list[dict]:
    data = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    return [asset for asset in data.get("assets", []) if asset.get("id") and asset.get("path")]


def render_all(
    assets_dir: Path = ASSETS,
    thumbs_dir: Path = THUMB_DIR,
    manifest_path: Path = DEFAULT_MANIFEST,
) -> list[Path]:
    written: list[Path] = []
    for asset in manifest_assets(manifest_path):
        source = Path(assets_dir) / asset["path"]
        if not source.is_file():
            raise FileNotFoundError(f"missing source art for {asset['id']}")
        destination = Path(thumbs_dir) / (thumb_relpath(asset["id"]).rsplit("/", 1)[-1])
        render_thumbnail(source, destination)
        written.append(destination)
    return written


def missing_thumbs(
    assets_dir: Path = ASSETS,
    thumbs_dir: Path = THUMB_DIR,
    manifest_path: Path = DEFAULT_MANIFEST,
) -> list[str]:
    missing: list[str] = []
    for asset in manifest_assets(manifest_path):
        destination = Path(thumbs_dir) / (
            thumb_relpath(asset["id"]).rsplit("/", 1)[-1]
        )
        if not destination.is_file():
            missing.append(asset["id"])
    return missing


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assets", type=Path, default=ASSETS)
    parser.add_argument("--thumbs", type=Path, default=THUMB_DIR)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument(
        "--check",
        action="store_true",
        help="report missing thumbnails without writing anything",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.check:
        missing = missing_thumbs(args.assets, args.thumbs, args.manifest)
        for asset_id in missing:
            print(f"missing thumb: {asset_id}")
        print(f"{len(missing)} missing thumbnail(s)")
        return 1 if missing else 0

    written = render_all(args.assets, args.thumbs, args.manifest)
    print(f"rendered {len(written)} shop thumbnail(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
