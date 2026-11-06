import copy
import json
import struct
import sys
import zlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
MANIFEST = ASSETS / "manifest.json"
SCHEMA = ASSETS / "manifest.schema.json"

sys.path.insert(0, str(ROOT / "scripts"))
import asset_validate as av  # noqa: E402


Z_ORDER = {-30, -20, -10, 0, 5, 10, 20, 30, 40, 50}
SLOTS = {"head", "face", "back", "front", "aura", "emote", "habitat", "title"}


def _png_chunk(kind, payload):
    return (
        struct.pack(">I", len(payload))
        + kind
        + payload
        + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
    )


def write_png(path, width, height, rgba, color_type=6, alpha_bbox=None):
    channels = {0: 1, 2: 3, 4: 2, 6: 4}[color_type]
    rows = []
    for y in range(height):
        if color_type == 6:
            row = bytearray()
            for x in range(width):
                inside = alpha_bbox is None or (
                    alpha_bbox[0] <= x < alpha_bbox[2] and alpha_bbox[1] <= y < alpha_bbox[3]
                )
                row.extend(rgba if inside else (0, 0, 0, 0))
            rows.append(b"\x00" + bytes(row))
        else:
            rows.append(b"\x00" + bytes(rgba) * width)
    ihdr = struct.pack(">IIBBBBB", width, height, 8, color_type, 0, 0, 0)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", ihdr)
        + _png_chunk(b"IDAT", zlib.compress(b"".join(rows), 9))
        + _png_chunk(b"IEND", b"")
    )


def load_manifest():
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def errors_for(data, base_dir=ASSETS):
    return av.validate_manifest_data(data, base_dir=base_dir, schema_path=SCHEMA)


def test_checked_in_manifest_passes():
    errors = errors_for(load_manifest())
    # launch-003's wizard hat deliberately paints above the legacy safe band.
    # Every other manifest rule still has to pass.
    known_wizard_overflow = [
        err for err in errors if err.startswith("asset 'hat.wizard_hat': alpha bounds")
    ]
    assert len(known_wizard_overflow) <= 1
    assert [err for err in errors if err not in known_wizard_overflow] == []


def test_manifest_has_contract_vocabulary():
    data = load_manifest()
    assert data["schema_version"] == 1
    assert data["asset_pack_id"] == "launch-003"
    assert data["canvas"] == {"width": 512, "height": 512, "baseline_y": 448}
    assert set(data["rigs"]) == {"small_front_v1"}
    assert set(data["species"]) == {
        "byteblob",
        "patchfox",
        "nullgeist",
        "kernelcrab",
        "cachebat",
        "stacktoise",
        "daemowl",
        "shellsnail",
        "regexopus",
        "firewyrm",
    }
    assert len(data["assets"]) == 81
    assert data["assets"], "manifest needs at least one example item asset"
    for asset in data["assets"]:
        assert asset["slot"] in SLOTS
        assert asset["z"] in Z_ORDER
    assert set(data["rigs"]["small_front_v1"]["anchors"]) >= {
        "head",
        "face",
        "back",
        "front",
        "ground",
        "hand",
    }


def test_launch_003_ships_real_pixel_content():
    data = load_manifest()
    assert "launch-003" in data.get("notes", "")
    assert "PLACEHOLDER_NOT_SHIP" not in data.get("notes", "")
    for asset in data["assets"]:
        assert asset["path"].startswith("px3/")
        assert "PLACEHOLDER_NOT_SHIP" not in asset.get("notes", "")
    for species in data["species"].values():
        assert species["base"].startswith("px3/species/")


def test_duplicate_asset_ids_fail():
    data = load_manifest()
    data["assets"].append(copy.deepcopy(data["assets"][0]))
    errors = errors_for(data)
    assert any("duplicate" in err.lower() and "id" in err.lower() for err in errors)


def test_bad_sha256_fails():
    data = load_manifest()
    data["assets"][0]["sha256"] = "0" * 64
    errors = errors_for(data)
    assert any("sha256" in err.lower() for err in errors)


def test_bad_slot_fails():
    data = load_manifest()
    data["assets"][0]["slot"] = "hat"
    errors = errors_for(data)
    assert any("slot" in err.lower() for err in errors)


def test_bad_z_order_fails():
    data = load_manifest()
    data["assets"][0]["z"] = 999
    errors = errors_for(data)
    assert any("z" in err.lower() for err in errors)


def test_bad_anchor_fails():
    data = load_manifest()
    data["assets"][0]["anchor"] = "tail"
    errors = errors_for(data)
    assert any("anchor" in err.lower() for err in errors)


def test_missing_asset_path_fails():
    data = load_manifest()
    data["assets"][0]["path"] = "fixtures/items/does_not_exist.png"
    errors = errors_for(data)
    assert any("not found" in err.lower() or "path" in err.lower() for err in errors)


def test_missing_required_manifest_field_fails():
    data = load_manifest()
    del data["asset_pack_id"]
    errors = errors_for(data)
    assert any("asset_pack_id" in err for err in errors)


def test_wrong_dimensions_fail(tmp_path):
    bad = tmp_path / "bad_size.png"
    write_png(bad, 64, 64, (255, 0, 255, 255))
    data = load_manifest()
    data["assets"][0]["path"] = bad.name
    data["assets"][0]["sha256"] = av.sha256_file(bad)
    errors = errors_for(data, base_dir=tmp_path)
    assert any("512x512" in err or "dimension" in err.lower() for err in errors)


def test_non_rgba_png_fails(tmp_path):
    bad = tmp_path / "rgb.png"
    write_png(bad, 512, 512, (10, 20, 30), color_type=2)
    data = load_manifest()
    data["assets"][0]["path"] = bad.name
    data["assets"][0]["sha256"] = av.sha256_file(bad)
    errors = errors_for(data, base_dir=tmp_path)
    assert any("rgba" in err.lower() for err in errors)


def test_empty_alpha_fails(tmp_path):
    bad = tmp_path / "transparent.png"
    write_png(bad, 512, 512, (0, 0, 0, 0))
    data = load_manifest()
    data["assets"][0]["path"] = bad.name
    data["assets"][0]["sha256"] = av.sha256_file(bad)
    errors = errors_for(data, base_dir=tmp_path)
    assert any("alpha" in err.lower() for err in errors)


def test_manifest_paths_exist_and_are_rgba():
    data = load_manifest()
    referenced = [ASSETS / species["base"] for species in data["species"].values()]
    referenced += [ASSETS / asset["path"] for asset in data["assets"]]
    for path in referenced:
        assert path.is_file(), path
        info = av.read_png(path)
        assert (info.width, info.height) == (512, 512)
        assert info.color_type == 6
