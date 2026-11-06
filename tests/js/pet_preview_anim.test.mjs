import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import {
  animStripPath,
  speciesBodyPath,
} from "../../desktop/src/ui/logic/assets.js";
import { buildPreviewLayers } from "../../desktop/src/ui/logic/shop.js";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const UI = path.join(ROOT, "desktop/src/ui");
const MANIFEST = JSON.parse(
  readFileSync(path.join(ROOT, "assets/manifest.launch-003.json"), "utf8")
);

function source(relative) {
  return readFileSync(path.join(UI, relative), "utf8");
}

test("PetPreview wires the shared petAnimPlayer without showing ? for species", () => {
  const text = source("components/PetPreview.js");
  for (const symbol of ["createPlayer", "findClip", "resolveAnimState", "contract"]) {
    assert.match(text, new RegExp("\\b" + symbol + "\\b"));
  }
  assert.match(text, /from "\.\.\/\.\.\/anim\/petAnimPlayer\.js"/);
  assert.match(text, /buildPreviewLayers/);
  assert.match(text, /speciesBodyPath/);
  assert.match(text, /requestAnimationFrame/);
  assert.match(text, /data-sprite-mode/);
  assert.match(text, /data-anim-state/);
  assert.match(text, /if \(!baseLayer && itemLayers\.length === 0\)/);
});

test("the checked-in manifest resolves both acceptance species to a base image", () => {
  for (const species of ["daemowl", "byteblob"]) {
    assert.equal(
      speciesBodyPath(MANIFEST, { species }),
      MANIFEST.species[species].base
    );
    const layers = buildPreviewLayers({
      pet: { id: "pet-1", species },
      manifest: MANIFEST,
      assetBaseUrl: "/api/plugins/hermagotchi/assets",
    });
    assert.equal(layers[0].kind, "base");
    assert.equal(
      layers[0].url,
      "/api/plugins/hermagotchi/assets/" + MANIFEST.species[species].base
    );
    assert.ok(!layers[0].url.includes("?"));
  }
});

test("animation strip paths match the manifest clip catalogue", () => {
  for (const species of ["daemowl", "byteblob"]) {
    for (const palette of ["teal", "bark"]) {
      for (const state of ["idle", "happy", "eat", "sleep", "hurt", "attack"]) {
        const clip = MANIFEST.animations.clips.find(
          (item) =>
            item.species === species &&
            item.palette === palette &&
            item.state === state
        );
        if (!clip) continue;
        assert.equal(animStripPath(species, palette, state), clip.path);
      }
    }
  }
});

test("HabitatTab loads the manifest and drives care animation states", () => {
  const text = source("tabs/HabitatTab.js");
  assert.match(text, /api\.assets\.manifest\(\)/);
  assert.match(text, /api\.assets\.url\(""\)/);
  assert.match(text, /useState\(props\.animState \|\| "idle"\)/);
  assert.match(text, /feed: "eat"/);
  assert.match(text, /play: "happy"/);
  assert.match(text, /rest: "sleep"/);
  assert.match(text, /setTimeout\(function \(\) \{/);
  assert.match(text, /animState,/);
  assert.match(text, /assetBaseUrl: assetBaseUrl/);
});

test("BattleTab passes attack/hurt preview state and portraits", () => {
  const text = source("tabs/BattleTab.js");
  assert.match(text, /battleAnimState/);
  assert.match(text, /state = "attack"/);
  assert.match(text, /state = "hurt"/);
  assert.match(text, /animState: previewAnimState/);
  assert.match(text, /PetPreview/);
  assert.match(text, /assetBaseUrl: assetBaseUrl/);
});

test("NpcHostBanner renders a portrait only when a base URL exists", () => {
  const text = source("components/NpcHostBanner.js");
  assert.match(text, /npcPortraitPath\(host\.id\)/);
  assert.match(text, /hg-npc-host__portrait/);
  assert.match(text, /portrait && assetBaseUrl \? joinAssetUrl/);
});
