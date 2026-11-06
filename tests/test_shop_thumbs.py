"""Shop thumbnail pack checks (HGT-W11-C).

The desktop bridge serves ``assets/`` at its asset base, so every launch-003
catalog item must resolve a ``px3/thumbs/*_thumb.png`` file whose backdrop is
opaque.  These tests use only the standard library and the renderer module so
they also run on a box without Pillow or pytest.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
MANIFEST = ASSETS / "manifest.launch-003.json"
THUMBS = ASSETS / "px3" / "thumbs"

sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

import render_shop_thumbs as renderer  # noqa: E402


def load_manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def thumb_for(asset_id: str) -> Path:
    return ASSETS / renderer.thumb_relpath(asset_id)


def opaque_count(channels: int, pixels: bytes) -> int:
    if channels not in (2, 4):
        return len(pixels) // channels
    return sum(
        1
        for index in range(channels - 1, len(pixels), channels)
        if pixels[index] > 0
    )


def luminance_range(channels: int, pixels: bytes) -> tuple[float, float]:
    lows: list[float] = []
    highs: list[float] = []
    for index in range(0, len(pixels), channels):
        if channels in (2, 4) and pixels[index + channels - 1] == 0:
            continue
        red, green, blue = pixels[index], pixels[index + 1], pixels[index + 2]
        luminance = 0.2126 * red + 0.7152 * green + 0.0722 * blue
        lows.append(luminance)
        highs.append(luminance)
    if not lows:
        return (0.0, 0.0)
    return (min(lows), max(highs))


def test_manifest_source_art_exists_and_is_not_empty() -> None:
    manifest = load_manifest()
    assert len(manifest["assets"]) == 81
    for asset in manifest["assets"]:
        source = ASSETS / asset["path"]
        assert source.is_file(), f"missing source art for {asset['id']}"
        width, height, channels, pixels = renderer.decode_png(source)
        assert width > 0 and height > 0
        assert opaque_count(channels, pixels) > 0, (
            f"source art has no opaque pixels for {asset['id']}"
        )


def test_every_manifest_asset_has_an_opaque_thumb() -> None:
    manifest = load_manifest()
    for asset in manifest["assets"]:
        thumb = thumb_for(asset["id"])
        assert thumb.is_file(), f"missing thumb for {asset['id']}"
        width, height, channels, pixels = renderer.decode_png(thumb)
        assert opaque_count(channels, pixels) == width * height, (
            f"thumb has transparent pixels for {asset['id']}"
        )
        low, high = luminance_range(channels, pixels)
        assert high - low >= 40, (
            f"thumb lacks visible contrast for {asset['id']}"
        )


def test_thumb_names_follow_the_js_convention() -> None:
    manifest = load_manifest()
    names = {asset["id"]: renderer.thumb_relpath(asset["id"]) for asset in manifest["assets"]}
    assert len(set(names.values())) == len(names), "thumb paths must be unique"
    for asset_id, relative in names.items():
        short = asset_id.rsplit(".", 1)[-1]
        assert relative == f"px3/thumbs/{short}_thumb.png"
    assert renderer.thumb_relpath("hat.future_item") == "px3/thumbs/future_item_thumb.png"


def test_dark_sparse_art_renders_on_a_light_backdrop() -> None:
    manifest = load_manifest()
    by_id = {asset["id"]: asset for asset in manifest["assets"]}
    source = ASSETS / by_id["aura.static_haze"]["path"]
    with tempfile.TemporaryDirectory() as tmp:
        first = Path(tmp) / "first.png"
        second = Path(tmp) / "second.png"
        renderer.render_thumbnail(source, first)
        renderer.render_thumbnail(source, second)
        assert first.read_bytes() == second.read_bytes(), "rendering must be deterministic"
        width, height, channels, pixels = renderer.decode_png(first)
        assert opaque_count(channels, pixels) == width * height
        low, high = luminance_range(channels, pixels)
        assert high >= 200, "light checkerboard backdrop must be present"
        assert low <= 80, "dark aura art must remain visible"


def _run_standalone() -> int:
    failures = 0
    tests = [
        (name, value)
        for name, value in sorted(globals().items())
        if name.startswith("test_") and callable(value)
    ]
    for name, test in tests:
        try:
            test()
        except Exception as exc:  # noqa: BLE001 - tiny stdlib runner
            failures += 1
            print(f"FAIL {name}: {exc}")
        else:
            print(f"PASS {name}")
    print(f"{len(tests) - failures}/{len(tests)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(_run_standalone())
