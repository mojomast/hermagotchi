#!/usr/bin/env python3
"""Validate a Hermagotchi asset manifest against contracts-v1.

Checks performed:
  * manifest shape against assets/manifest.schema.json
  * unique asset ids and existing paths
  * 512x512 8-bit RGBA PNGs with non-empty alpha inside the safe region
  * sha256 of every item layer
  * valid slot, z-order, rig and anchor names
  * total referenced pack size budget

No third-party dependencies and no network access.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
import sys
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SLOTS = {"head", "face", "back", "front", "aura", "emote", "habitat", "title"}
Z_ORDER = {-30, -20, -10, 0, 5, 10, 20, 30, 40, 50}
SAFE_X_MIN, SAFE_Y_MIN, SAFE_X_MAX, SAFE_Y_MAX = 65, 75, 447, 450
CANVAS_SIZE = 512
MAX_PACK_BYTES = 64 * 1024 * 1024
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class PngError(ValueError):
    pass


@dataclass(frozen=True)
class PngInfo:
    width: int
    height: int
    bit_depth: int
    color_type: int
    interlace: int
    alpha_nonzero: int | None = None
    alpha_bbox: tuple[int, int, int, int] | None = None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _paeth(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    if pb <= pc:
        return b
    return c


def read_png(path: Path) -> PngInfo:
    """Read PNG header and (for 8-bit RGBA) alpha statistics."""
    raw = Path(path).read_bytes()
    if not raw.startswith(PNG_SIGNATURE):
        raise PngError("not a PNG file")

    pos = len(PNG_SIGNATURE)
    width = height = bit_depth = color_type = interlace = None
    idat = bytearray()
    saw_ihdr = saw_iend = False

    while pos < len(raw):
        if pos + 8 > len(raw):
            raise PngError("truncated PNG chunk header")
        length = struct.unpack(">I", raw[pos : pos + 4])[0]
        kind = raw[pos + 4 : pos + 8]
        start = pos + 8
        end = start + length
        if end + 4 > len(raw):
            raise PngError("truncated PNG chunk payload")
        payload = raw[start:end]
        pos = end + 4
        if kind == b"IHDR":
            if length != 13:
                raise PngError("invalid IHDR length")
            width, height, bit_depth, color_type, compression, filtering, interlace = struct.unpack(
                ">IIBBBBB", payload
            )
            if compression != 0 or filtering != 0:
                raise PngError("unsupported PNG compression/filter method")
            saw_ihdr = True
        elif kind == b"IDAT":
            idat.extend(payload)
        elif kind == b"IEND":
            saw_iend = True
            break

    if not saw_ihdr or width is None or height is None:
        raise PngError("missing IHDR")
    if not saw_iend:
        raise PngError("missing IEND")
    if not idat:
        raise PngError("missing IDAT")

    info = PngInfo(width, height, bit_depth, color_type, interlace)
    if color_type != 6 or bit_depth != 8 or interlace != 0:
        return info

    channels = 4
    stride = width * channels
    try:
        decompressed = zlib.decompress(bytes(idat))
    except zlib.error as exc:
        raise PngError(f"bad IDAT stream: {exc}") from exc
    expected = height * (stride + 1)
    if len(decompressed) < expected:
        raise PngError("truncated pixel data")

    previous = bytearray(stride)
    alpha_nonzero = 0
    min_x, min_y = width, height
    max_x = max_y = -1
    offset = 0
    for y in range(height):
        filter_type = decompressed[offset]
        offset += 1
        line = bytearray(decompressed[offset : offset + stride])
        offset += stride
        if filter_type == 1:
            for i in range(channels, stride):
                line[i] = (line[i] + line[i - channels]) & 0xFF
        elif filter_type == 2:
            for i in range(stride):
                line[i] = (line[i] + previous[i]) & 0xFF
        elif filter_type == 3:
            for i in range(stride):
                left = line[i - channels] if i >= channels else 0
                line[i] = (line[i] + ((left + previous[i]) >> 1)) & 0xFF
        elif filter_type == 4:
            for i in range(stride):
                left = line[i - channels] if i >= channels else 0
                upper_left = previous[i - channels] if i >= channels else 0
                line[i] = (line[i] + _paeth(left, previous[i], upper_left)) & 0xFF
        elif filter_type != 0:
            raise PngError(f"invalid PNG filter type {filter_type}")
        for x in range(width):
            if line[x * 4 + 3] != 0:
                alpha_nonzero += 1
                if x < min_x:
                    min_x = x
                if x > max_x:
                    max_x = x
                if y < min_y:
                    min_y = y
                if y > max_y:
                    max_y = y
        previous = line

    bbox = None if alpha_nonzero == 0 else (min_x, min_y, max_x, max_y)
    return PngInfo(
        width=width,
        height=height,
        bit_depth=bit_depth,
        color_type=color_type,
        interlace=interlace,
        alpha_nonzero=alpha_nonzero,
        alpha_bbox=bbox,
    )


def _json_type_matches(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "null":
        return value is None
    return True


def _resolve_ref(ref: str, root: dict[str, Any]) -> dict[str, Any]:
    if not ref.startswith("#/"):
        raise ValueError(f"unsupported $ref {ref!r}")
    node: Any = root
    for part in ref[2:].split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        node = node[part]
    if not isinstance(node, dict):
        raise ValueError(f"$ref {ref!r} does not resolve to a schema object")
    return node


def validate_schema(
    instance: Any, schema: Any, root: dict[str, Any], path: str = "$"
) -> list[str]:
    """Validate a small, dependency-free JSON Schema subset."""
    if schema is True or schema == {}:
        return []
    if schema is False:
        return [f"{path}: value is not allowed"]
    if not isinstance(schema, dict):
        return [f"{path}: invalid schema node"]

    errors: list[str] = []
    if "$ref" in schema:
        try:
            target = _resolve_ref(schema["$ref"], root)
        except (KeyError, ValueError) as exc:
            return [f"{path}: cannot resolve {schema['$ref']!r}: {exc}"]
        errors.extend(validate_schema(instance, target, root, path))

    if "const" in schema and instance != schema["const"]:
        errors.append(f"{path}: expected constant {schema['const']!r}, got {instance!r}")
    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path}: {instance!r} is not one of {schema['enum']!r}")

    expected_type = schema.get("type")
    if expected_type is not None:
        types = expected_type if isinstance(expected_type, list) else [expected_type]
        if not any(_json_type_matches(instance, item) for item in types):
            errors.append(f"{path}: expected type {expected_type!r}, got {type(instance).__name__}")
            return errors

    if isinstance(instance, str):
        if "minLength" in schema and len(instance) < schema["minLength"]:
            errors.append(f"{path}: string shorter than {schema['minLength']}")
        if "maxLength" in schema and len(instance) > schema["maxLength"]:
            errors.append(f"{path}: string longer than {schema['maxLength']}")
        if "pattern" in schema and re.search(schema["pattern"], instance) is None:
            errors.append(f"{path}: {instance!r} does not match pattern {schema['pattern']!r}")

    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            errors.append(f"{path}: {instance!r} is below minimum {schema['minimum']!r}")
        if "maximum" in schema and instance > schema["maximum"]:
            errors.append(f"{path}: {instance!r} is above maximum {schema['maximum']!r}")

    if isinstance(instance, list):
        if "minItems" in schema and len(instance) < schema["minItems"]:
            errors.append(f"{path}: needs at least {schema['minItems']} items")
        if "maxItems" in schema and len(instance) > schema["maxItems"]:
            errors.append(f"{path}: allows at most {schema['maxItems']} items")
        if schema.get("uniqueItems"):
            seen = set()
            for item in instance:
                key = json.dumps(item, sort_keys=True, separators=(",", ":"))
                if key in seen:
                    errors.append(f"{path}: duplicate item {item!r}")
                seen.add(key)
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(instance):
                errors.extend(validate_schema(item, item_schema, root, f"{path}[{index}]"))

    if isinstance(instance, dict):
        required = schema.get("required", [])
        for key in required:
            if key not in instance:
                errors.append(f"{path}: missing required property {key!r}")
        if "minProperties" in schema and len(instance) < schema["minProperties"]:
            errors.append(f"{path}: needs at least {schema['minProperties']} properties")
        if "maxProperties" in schema and len(instance) > schema["maxProperties"]:
            errors.append(f"{path}: allows at most {schema['maxProperties']} properties")
        properties = schema.get("properties", {})
        for key, subschema in properties.items():
            if key in instance:
                errors.extend(validate_schema(instance[key], subschema, root, f"{path}.{key}"))
        additional = schema.get("additionalProperties", True)
        for key, value in instance.items():
            if key in properties:
                continue
            if additional is False:
                errors.append(f"{path}: unexpected property {key!r}")
            elif isinstance(additional, dict):
                errors.extend(validate_schema(value, additional, root, f"{path}.{key}"))

    for subschema in schema.get("allOf", []):
        errors.extend(validate_schema(instance, subschema, root, path))
    if "anyOf" in schema:
        branches = [validate_schema(instance, item, root, path) for item in schema["anyOf"]]
        if all(branch for branch in branches):
            errors.append(f"{path}: does not match any allowed variant")
    if "oneOf" in schema:
        branches = [validate_schema(instance, item, root, path) for item in schema["oneOf"]]
        if sum(1 for branch in branches if not branch) != 1:
            errors.append(f"{path}: must match exactly one allowed variant")

    return errors


def _display(path: Path, base_dir: Path) -> str:
    try:
        return path.resolve().relative_to(base_dir.resolve()).as_posix()
    except ValueError:
        return path.name


def _check_png(path: Path, label: str, errors: list[str]) -> PngInfo | None:
    try:
        info = read_png(path)
    except (OSError, PngError) as exc:
        errors.append(f"{label}: cannot read PNG: {exc}")
        return None
    if info.color_type != 6 or info.bit_depth != 8 or info.interlace != 0:
        errors.append(
            f"{label}: expected RGBA PNG (color type 6, 8-bit, non-interlaced), "
            f"got color type {info.color_type}, bit depth {info.bit_depth}, interlace {info.interlace}"
        )
        return info
    if (info.width, info.height) != (CANVAS_SIZE, CANVAS_SIZE):
        errors.append(
            f"{label}: expected 512x512 RGBA canvas, got {info.width}x{info.height}"
        )
    if not info.alpha_nonzero:
        errors.append(f"{label}: empty alpha (no non-transparent pixels)")
    elif info.alpha_bbox is not None:
        min_x, min_y, max_x, max_y = info.alpha_bbox
        if min_x < SAFE_X_MIN or max_x > SAFE_X_MAX or min_y < SAFE_Y_MIN or max_y > SAFE_Y_MAX:
            errors.append(
                f"{label}: alpha bounds ({min_x},{min_y})-({max_x},{max_y}) exceed "
                f"safe region x={SAFE_X_MIN}..{SAFE_X_MAX} y={SAFE_Y_MIN}..{SAFE_Y_MAX}"
            )
    return info


def _check_referenced_file(
    base_dir: Path, relative: str, label: str, errors: list[str]
) -> Path | None:
    path = (base_dir / relative).resolve()
    try:
        path.relative_to(base_dir.resolve())
    except ValueError:
        errors.append(f"{label}: path escapes the asset pack: {relative}")
        return None
    if not path.is_file():
        errors.append(f"{label}: path not found: {relative}")
        return None
    return path


def validate_manifest_data(
    manifest: Any,
    *,
    base_dir: Path,
    schema_path: Path | None = None,
) -> list[str]:
    base_dir = Path(base_dir)
    errors: list[str] = []

    if schema_path is not None:
        schema_path = Path(schema_path)
        if not schema_path.is_file():
            errors.append(f"schema not found: {_display(schema_path, base_dir)}")
        else:
            try:
                schema = json.loads(schema_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                errors.append(f"cannot read schema: {exc}")
            else:
                errors.extend(validate_schema(manifest, schema, schema))

    if not isinstance(manifest, dict):
        return errors or ["manifest root must be an object"]

    canvas = manifest.get("canvas")
    if isinstance(canvas, dict):
        if canvas.get("width") != CANVAS_SIZE or canvas.get("height") != CANVAS_SIZE:
            errors.append("canvas must be 512x512")
        if canvas.get("baseline_y") != 448:
            errors.append("canvas baseline_y must be 448")

    rigs = manifest.get("rigs")
    rig_anchors: dict[str, set[str]] = {}
    if isinstance(rigs, dict):
        for rig_name, rig in rigs.items():
            if isinstance(rig, dict) and isinstance(rig.get("anchors"), dict):
                rig_anchors[rig_name] = set(rig["anchors"])
    else:
        errors.append("rigs must be an object")

    referenced_paths: list[Path] = []
    species = manifest.get("species")
    if isinstance(species, dict):
        for name, entry in species.items():
            if not isinstance(entry, dict):
                continue
            label = f"species {name!r}"
            rig_name = entry.get("rig")
            if rig_name not in rig_anchors:
                errors.append(f"{label}: unknown rig {rig_name!r}")
            overrides = entry.get("overrides")
            if isinstance(overrides, dict) and rig_name in rig_anchors:
                for anchor in overrides:
                    if anchor not in rig_anchors[rig_name]:
                        errors.append(
                            f"{label}: override anchor {anchor!r} is not declared by rig {rig_name!r}"
                        )
            base = entry.get("base")
            if isinstance(base, str):
                file_path = _check_referenced_file(base_dir, base, f"{label} base", errors)
                if file_path is not None:
                    referenced_paths.append(file_path)
                    _check_png(file_path, f"{label} base", errors)

    assets = manifest.get("assets")
    seen_ids: set[str] = set()
    if isinstance(assets, list):
        for index, asset in enumerate(assets):
            if not isinstance(asset, dict):
                errors.append(f"assets[{index}]: must be an object")
                continue
            asset_id = asset.get("id")
            label = f"asset {asset_id!r}" if isinstance(asset_id, str) else f"assets[{index}]"
            if isinstance(asset_id, str):
                if asset_id in seen_ids:
                    errors.append(f"{label}: duplicate asset id")
                seen_ids.add(asset_id)

            slot = asset.get("slot")
            if slot not in SLOTS:
                errors.append(f"{label}: invalid slot {slot!r}")
            z = asset.get("z")
            if z not in Z_ORDER:
                errors.append(f"{label}: invalid z-order {z!r}")

            families = asset.get("rig_families")
            if isinstance(families, list):
                for family in families:
                    if family not in rig_anchors:
                        errors.append(f"{label}: unknown rig family {family!r}")
            else:
                errors.append(f"{label}: rig_families must be an array")

            anchor = asset.get("anchor")
            if isinstance(anchor, str) and isinstance(families, list):
                for family in families:
                    if family in rig_anchors and anchor not in rig_anchors[family]:
                        errors.append(
                            f"{label}: anchor {anchor!r} is not declared by rig {family!r}"
                        )

            path_value = asset.get("path")
            if isinstance(path_value, str):
                file_path = _check_referenced_file(base_dir, path_value, label, errors)
                if file_path is not None:
                    referenced_paths.append(file_path)
                    _check_png(file_path, label, errors)
                    expected_hash = asset.get("sha256")
                    if isinstance(expected_hash, str):
                        actual_hash = sha256_file(file_path)
                        if actual_hash != expected_hash:
                            errors.append(
                                f"{label}: sha256 mismatch (expected {expected_hash}, got {actual_hash})"
                            )
    else:
        errors.append("assets must be an array")

    unique_paths = {path.resolve() for path in referenced_paths}
    total_bytes = sum(path.stat().st_size for path in unique_paths if path.is_file())
    if total_bytes > MAX_PACK_BYTES:
        errors.append(
            f"pack size {total_bytes} exceeds budget of {MAX_PACK_BYTES} bytes"
        )

    errors.extend(validate_animations(manifest, base_dir))

    return errors


def validate_animations(manifest: dict, base_dir: Path) -> list[str]:
    """Optional animations{} block: strips exist, sha matches, deltas in bounds."""
    errors: list[str] = []
    anim = manifest.get("animations")
    if anim is None:
        return errors
    if not isinstance(anim, dict):
        return ["animations must be an object"]
    clips = anim.get("clips")
    if not isinstance(clips, list):
        return ["animations.clips must be an array"]
    species = set((manifest.get("species") or {}).keys())
    pf = int(anim.get("pixel_factor") or 1)
    try:
        from PIL import Image
    except ImportError:
        return ["Pillow required to validate animation strips"]
    for i, clip in enumerate(clips):
        label = f"animations.clips[{i}]"
        if not isinstance(clip, dict):
            errors.append(f"{label}: must be object")
            continue
        cid = clip.get("id", label)
        path = clip.get("path")
        if not isinstance(path, str):
            errors.append(f"{cid}: path required")
            continue
        fp = (base_dir / path).resolve()
        if not fp.is_file():
            errors.append(f"{cid}: missing strip {path}")
            continue
        expected_hash = clip.get("sha256")
        if isinstance(expected_hash, str):
            actual = sha256_file(fp)
            if actual != expected_hash:
                errors.append(f"{cid}: sha256 mismatch")
        sp = clip.get("species")
        if isinstance(sp, str) and sp not in species:
            errors.append(f"{cid}: unknown species {sp!r}")
        fw = int(clip.get("frame_w") or 0)
        fh = int(clip.get("frame_h") or 0)
        fc = int(clip.get("frame_count") or 0)
        if fw < 1 or fh < 1 or fc < 1:
            errors.append(f"{cid}: invalid frame geometry")
            continue
        im = Image.open(fp)
        expect_hi = (fw * fc * pf, fh * pf)
        expect_lo = (fw * fc, fh)
        if im.size not in (expect_hi, expect_lo):
            errors.append(f"{cid}: strip size {im.size} != {expect_hi} or {expect_lo}")
        for fr in clip.get("frames") or []:
            if not isinstance(fr, dict):
                continue
            ad = fr.get("anchor_delta") or [0, 0]
            if not (isinstance(ad, list) and len(ad) == 2):
                errors.append(f"{cid}: bad anchor_delta")
                continue
            if abs(int(ad[0])) > 8 or abs(int(ad[1])) > 8:
                errors.append(f"{cid}: anchor_delta out of bounds {ad}")
    return errors



def default_schema_path() -> Path:
    return Path(__file__).resolve().parent.parent / "assets" / "manifest.schema.json"


def validate_manifest(
    manifest_path: Path,
    *,
    schema_path: Path | None = None,
    base_dir: Path | None = None,
) -> list[str]:
    manifest_path = Path(manifest_path)
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"cannot read manifest: {exc}"]
    return validate_manifest_data(
        manifest,
        base_dir=Path(base_dir) if base_dir is not None else manifest_path.parent,
        schema_path=Path(schema_path) if schema_path is not None else default_schema_path(),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a Hermagotchi asset manifest.")
    parser.add_argument("manifest", help="path to assets/manifest.json")
    parser.add_argument("--schema", help="override schema path")
    parser.add_argument("--base-dir", help="resolve asset paths from this directory")
    args = parser.parse_args(argv)

    manifest_path = Path(args.manifest)
    errors = validate_manifest(
        manifest_path,
        schema_path=Path(args.schema) if args.schema else None,
        base_dir=Path(args.base_dir) if args.base_dir else None,
    )
    if errors:
        for error in errors:
            print(f"FAIL: {error}", file=sys.stderr)
        print(f"{len(errors)} validation error(s)", file=sys.stderr)
        return 1
    print(f"OK: {manifest_path.name} is a valid contracts-v1 asset manifest")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
