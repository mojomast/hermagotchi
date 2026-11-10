import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import {
  ANIM_STRIP_TEMPLATE,
  animStripPath,
  isRemoteAssetUrl,
  itemAssetPath,
  joinAssetUrl,
  npcPortraitPath,
  resolveAnimPalette,
  safeRelativeAssetPath,
  speciesBodyPath,
} from "../../desktop/src/ui/logic/assets.js";
import { buildPreviewLayers } from "../../desktop/src/ui/logic/shop.js";
import { createApiClient } from "../../desktop/src/ui/api.js";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const CONTRACT = JSON.parse(
  readFileSync(path.join(ROOT, "desktop/src/anim/petAnimContract.json"), "utf8")
);

function jsonResponse(body, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status: status,
    async json() {
      return body;
    },
  };
}

test("joinAssetUrl joins a bridge root without double slashes", () => {
  assert.equal(joinAssetUrl("/api/plugins/hermagotchi/assets", "px3/a.png"), "/api/plugins/hermagotchi/assets/px3/a.png");
  assert.equal(joinAssetUrl("/api/plugins/hermagotchi/assets/", "/px3/a.png"), "/api/plugins/hermagotchi/assets/px3/a.png");
  assert.equal(joinAssetUrl("/api/plugins/hermagotchi/assets", "./px3/a.png"), "/api/plugins/hermagotchi/assets/px3/a.png");
  assert.equal(joinAssetUrl("", "px3/a.png"), "px3/a.png");
});

test("joinAssetUrl accepts data and blob URLs and rejects remote ones", () => {
  assert.equal(joinAssetUrl("/api/plugins/hermagotchi/assets", "data:image/png;base64,aaa"), "data:image/png;base64,aaa");
  assert.equal(joinAssetUrl("/api/plugins/hermagotchi/assets", "blob:http://localhost/1"), "blob:http://localhost/1");
  assert.equal(joinAssetUrl("/api/plugins/hermagotchi/assets", "https://other.example/a.png"), "");
  assert.equal(joinAssetUrl("/api/plugins/hermagotchi/assets", "http://other.example/a.png"), "");
  assert.equal(joinAssetUrl("https://cdn.example/assets", "px3/a.png"), "");
  assert.equal(joinAssetUrl("https://cdn.example/assets", "https://other.example/a.png"), "");
  assert.equal(joinAssetUrl("/api/plugins/hermagotchi/assets", "//evil.example/a.png"), "");
  assert.equal(joinAssetUrl("/api/plugins/hermagotchi/assets", "javascript:alert(1)"), "");
  assert.equal(joinAssetUrl("/api/plugins/hermagotchi/assets", "../secret"), "");
  assert.equal(safeRelativeAssetPath("https://cdn.example/x.png"), "");
  assert.equal(safeRelativeAssetPath("px3/items/x.png"), "px3/items/x.png");
  assert.equal(isRemoteAssetUrl("https://other.example/a.png"), true);
  assert.equal(isRemoteAssetUrl("/api/plugins/hermagotchi/assets/px3/a.png"), false);
});

test("speciesBodyPath prefers the manifest base for every known species", () => {
  const manifest = {
    species: {
      daemowl: { base: "px3/species/daemowl_body.png" },
      byteblob: { base: "px3/species/byteblob_body.png" },
    },
  };
  assert.equal(speciesBodyPath(manifest, { species: "daemowl" }), "px3/species/daemowl_body.png");
  assert.equal(speciesBodyPath(manifest, { species: "byteblob" }), "px3/species/byteblob_body.png");
});

test("speciesBodyPath falls back to the px3 convention", () => {
  assert.equal(speciesBodyPath(null, { species: "daemowl" }), "px3/species/daemowl_body.png");
  assert.equal(speciesBodyPath({ species: {} }, { species: "byteblob" }), "px3/species/byteblob_body.png");
  assert.equal(speciesBodyPath({}, "patchfox"), "px3/species/patchfox_body.png");
  assert.equal(speciesBodyPath(null, null), "");
});

test("speciesBodyPath honours a palette-specific manifest path", () => {
  const manifest = {
    species: {
      daemowl: {
        base: "px3/species/daemowl_body.png",
        palettes: {
          bark: { path: "px3/species/daemowl_bark.png" },
          snowy: "px3/species/daemowl_snowy.png",
        },
      },
    },
  };
  assert.equal(
    speciesBodyPath(manifest, { species: "daemowl", appearance: { palette: "bark" } }),
    "px3/species/daemowl_bark.png"
  );
  assert.equal(
    speciesBodyPath(manifest, { species: "daemowl", palette: "snowy" }),
    "px3/species/daemowl_snowy.png"
  );
  assert.equal(
    speciesBodyPath(manifest, { species: "daemowl", palette: "teal" }),
    "px3/species/daemowl_body.png"
  );
});

test("itemAssetPath reads manifest assets and skips unknown ids", () => {
  const manifest = {
    assets: [{ id: "hat.binary_crown", path: "px3/items/binary_crown.png" }],
  };
  assert.equal(itemAssetPath(manifest, { id: "hat.binary_crown" }), "px3/items/binary_crown.png");
  assert.equal(itemAssetPath(manifest, "hat.binary_crown"), "px3/items/binary_crown.png");
  assert.equal(itemAssetPath(null, { id: "aura.ping_pulse", asset_id: "aura.ping_pulse" }), "");
  assert.equal(itemAssetPath(manifest, { assetUrl: "https://cdn.example/x.png", id: "x" }), "");
  assert.equal(itemAssetPath(manifest, { assetUrl: "px3/items/x.png", id: "x" }), "px3/items/x.png");
});

test("npcPortraitPath maps the four launch NPCs", () => {
  assert.equal(npcPortraitPath("npc.don_piedro"), "px3/npcs/don_piedro_portrait.png");
  assert.equal(npcPortraitPath("nous_girl"), "px3/npcs/nous_girl_portrait.png");
  assert.equal(npcPortraitPath("npc.teknium"), "px3/npcs/teknium_portrait.png");
  assert.equal(npcPortraitPath("southpaw"), "px3/npcs/southpaw_portrait.png");
  assert.equal(npcPortraitPath("npc.unknown"), "");
});

test("animStripPath matches the desktop animation contract", () => {
  assert.equal(ANIM_STRIP_TEMPLATE, CONTRACT.strip_path_template);
  assert.equal(
    animStripPath("daemowl", "bark", "idle"),
    "px3/anims/daemowl_bark_idle.png"
  );
  for (const state of CONTRACT.states) {
    assert.equal(
      animStripPath("byteblob", "teal", state),
      CONTRACT.strip_path_template
        .replace("{species}", "byteblob")
        .replace("{palette}", "teal")
        .replace("{state}", state)
    );
  }
});

test("buildPreviewLayers always emits a base layer when species is known", () => {
  for (const species of ["daemowl", "byteblob"]) {
    const layers = buildPreviewLayers({
      pet: { id: "pet-1", species },
      assetBaseUrl: "/api/plugins/hermagotchi/assets",
    });
    assert.equal(layers.length, 1);
    assert.equal(layers[0].kind, "base");
    assert.equal(
      layers[0].url,
      "/api/plugins/hermagotchi/assets/px3/species/" + species + "_body.png"
    );
  }
});

test("api.assets builds safe asset URLs and resolves the raw manifest envelope", async () => {
  const calls = [];
  const client = createApiClient({
    basePath: "/api/plugins/hermagotchi",
    fetchImpl: async (url, init) => {
      calls.push({ url, init });
      return jsonResponse({ asset_pack_id: "launch-003", species: {} });
    },
  });

  assert.equal(client.assets.url(""), "/api/plugins/hermagotchi/assets");
  assert.equal(client.assets.url("assets/px3/species/byteblob_body.png"), "/api/plugins/hermagotchi/assets/px3/species/byteblob_body.png");
  assert.equal(client.assets.url("/px3//species/byteblob_body.png"), "/api/plugins/hermagotchi/assets/px3/species/byteblob_body.png");
  assert.equal(client.assets.url("../px3/a.png"), "/api/plugins/hermagotchi/assets/px3/a.png");

  const envelope = await client.assets.manifest();
  assert.equal(envelope.ok, true);
  assert.equal(envelope.status, "ok");
  assert.equal(envelope.data.asset_pack_id, "launch-003");
  assert.equal(calls[0].url, "/api/plugins/hermagotchi/assets/manifest");
  assert.equal(calls[0].init.method, "GET");
});

test("resolveAnimPalette maps server palette_0N names onto anim strips", () => {
  assert.equal(resolveAnimPalette("palette_01"), "teal");
  assert.equal(resolveAnimPalette("palette_04"), "brick");
  assert.equal(resolveAnimPalette("grape"), "grape");
  assert.equal(resolveAnimPalette(""), "teal");
});

test("itemAssetPath returns empty when the manifest has no matching asset", () => {
  assert.equal(itemAssetPath({ assets: [] }, { id: "hat.wizard_hat", asset_id: "hat.wizard_hat" }), "");
  assert.equal(
    itemAssetPath(
      { assets: [{ id: "hat.binary_crown", path: "px3/items/binary_crown.png" }] },
      { id: "hat.binary_crown", asset_id: "hat.binary_crown" }
    ),
    "px3/items/binary_crown.png"
  );
});
