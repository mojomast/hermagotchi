import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import {
  DEFAULT_NATIVE_SIZE,
  EMBEDDED_ANCHORS,
  anchorsFor,
  composeItem,
  composeLayer,
  transformNativeFor,
} from "../../desktop/src/ui/logic/compose.js";
import { buildPreviewLayers } from "../../desktop/src/ui/logic/shop.js";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const SNAPSHOT = JSON.parse(
  readFileSync(path.join(ROOT, "desktop/src/ui/logic/composeAnchors.json"), "utf8")
);
const ART_EXT = JSON.parse(
  readFileSync(path.join(ROOT, "assets/art_ext.launch-003.json"), "utf8")
);

test("composeAnchors snapshot matches art_ext anchors and transforms", () => {
  assert.equal(SNAPSHOT.asset_pack_id, ART_EXT.asset_pack_id);
  assert.equal(SNAPSHOT.native_size, ART_EXT.native_size);
  for (const species of Object.keys(ART_EXT.species)) {
    assert.deepEqual(
      SNAPSHOT.species[species].anchors_native,
      ART_EXT.species[species].anchors_native
    );
    assert.equal(
      SNAPSHOT.species[species].item_scale,
      ART_EXT.species[species].item_scale
    );
  }
  for (const itemId of Object.keys(ART_EXT.items)) {
    for (const species of Object.keys(ART_EXT.species)) {
      assert.deepEqual(
        SNAPSHOT.items[itemId].per_species[species],
        ART_EXT.items[itemId].per_species[species].transform_native
      );
    }
  }
});

test("the embedded snapshot is byte-equivalent to composeAnchors.json", () => {
  assert.deepEqual(EMBEDDED_ANCHORS, SNAPSHOT);
});

test("composeItem reproduces the Python anchor + offset/factor + dx/dy math", () => {
  const artExt = {
    pixel_factor: 16,
    native_size: 32,
    species: {
      test: {
        anchors_native: { head: [16, 11], face: [16, 16], ground: [16, 28] },
        item_scale: 1,
      },
    },
    items: {
      "hat.sample": {
        per_species: { test: { transform_native: [1, -2, 0.5] } },
      },
    },
  };
  const manifestAsset = {
    id: "hat.sample",
    slot: "head",
    anchor: "head",
    offset_px: [32, -16],
    scale: 2,
    z: 30,
  };
  const result = composeItem({
    species: "test",
    itemId: "hat.sample",
    manifestAsset,
    artExt,
    nativeSize: 32,
    displaySize: 320,
  });
  // offset_px // pixel_factor -> [2, -1]; anchor [16,11]; transform [1,-2,0.5]
  // scale = 2 * 1 * 0.5 = 1; center native = [19, 8].
  assert.deepEqual(result.centerNative, [19, 8]);
  assert.deepEqual(result.topLeftNative, [3, -8]);
  assert.equal(result.scale, 1);
  assert.deepEqual(result.offsetPercent, [(19 / 32 - 0.5) * 100, (8 / 32 - 0.5) * 100]);
  assert.deepEqual(result.offsetPx, [((19 / 32 - 0.5) * 320), ((8 / 32 - 0.5) * 320)]);
  assert.deepEqual(result.topLeftPx, [30, -80]);
  assert.equal(result.z, 30);
});

test("composeItem defaults to the shipped snapshot and native size", () => {
  const result = composeItem({
    species: "byteblob",
    itemId: "hat.bloom_filter",
    manifestAsset: {
      id: "hat.bloom_filter",
      slot: "head",
      anchor: "head",
      offset_px: [0, 0],
      scale: 1,
      z: 30,
    },
  });
  assert.equal(result.nativeSize, DEFAULT_NATIVE_SIZE);
  assert.equal(result.displaySize, DEFAULT_NATIVE_SIZE);
  assert.equal(result.anchor, "head");
  assert.deepEqual(
    result.transformNative,
    transformNativeFor("hat.bloom_filter", "byteblob", EMBEDDED_ANCHORS)
  );
  assert.deepEqual(anchorsFor("byteblob", EMBEDDED_ANCHORS).head, [16, 11]);
});

test("Bloom Filter Beret sits above Byteblob's face in compose math", () => {
  const result = composeItem({
    species: "byteblob",
    itemId: "hat.bloom_filter",
    manifestAsset: {
      id: "hat.bloom_filter",
      slot: "head",
      anchor: "head",
      offset_px: [0, 0],
      scale: 1,
      z: 30,
    },
    artExt: ART_EXT,
    displaySize: 320,
  });
  const faceY = ART_EXT.species.byteblob.anchors_native.face[1];
  const headY = ART_EXT.species.byteblob.anchors_native.head[1];
  assert.ok(result.scale <= 1);
  assert.ok(result.centerNative[1] < faceY);
  assert.ok(result.centerNative[1] <= headY - 2);
});

test("composeLayer is an alias of composeItem", () => {
  assert.equal(composeLayer, composeItem);
});

test("shop buildPreviewLayers applies compose offsets for known items", () => {
  const manifest = JSON.parse(
    readFileSync(path.join(ROOT, "assets/manifest.launch-003.json"), "utf8")
  );
  const layers = buildPreviewLayers({
    pet: { id: "pet-1", species: "byteblob" },
    loadout: { head: "hat.bloom_filter" },
    manifest,
    assetBaseUrl: "/assets",
  });
  const hat = layers.find((layer) => layer.id === "hat.bloom_filter");
  assert.ok(hat);
  assert.equal(hat.z, 30);
  assert.equal(hat.anchor, "head");
  assert.ok(hat.compose);
  assert.ok(Array.isArray(hat.offsetPercent));
  assert.ok(hat.offsetPercent[1] < 0);
  assert.equal(hat.scale, hat.compose.scale);
});
