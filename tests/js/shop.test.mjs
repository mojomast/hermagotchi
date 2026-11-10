import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import {
  SLOT_ORDER,
  buildPreviewLayers,
  catalogItems,
  groupCatalogBySlot,
  itemAvailability,
  itemThumbPath,
  itemThumbUrl,
  itemView,
  joinAssetUrl,
  loadoutItemId,
  manifestFromCatalog,
  mergeLoadout,
  normaliseWallet,
  readEnvelope,
  removeFromLoadout,
  SHOP_THUMB_DIR,
} from "../../desktop/src/ui/logic/shop.js";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const LAUNCH_MANIFEST = JSON.parse(
  readFileSync(path.join(ROOT, "assets", "manifest.launch-003.json"), "utf8")
);
const SHOP_TAB_SOURCE = readFileSync(
  path.join(ROOT, "desktop", "src", "ui", "tabs", "ShopTab.js"),
  "utf8"
);

const CATALOG = {
  contracts_version: "contracts-v1",
  catalog_version: "test",
  items: [
    {
      id: "hat.brand_new",
      name: "Brand New Hat",
      slot: "head",
      rarity: "rare",
      price_bits: 700,
      asset_id: "hat.brand_new",
      active: true,
    },
    {
      id: "aura.custom_glow",
      name: "Custom Glow",
      slot: "aura",
      rarity: "epic",
      price_bits: 1200,
      asset_id: "aura.custom_glow",
      active: true,
    },
    {
      id: "emote.wave",
      name: "Wave",
      slot: "emote",
      rarity: "common",
      price_bits: 150,
      asset_id: "emote.wave",
      active: true,
    },
  ],
};

const MANIFEST = {
  asset_pack_id: "test-pack",
  species: {
    patchfox: { base: "species/patchfox.png" },
  },
  assets: [
    {
      id: "hat.brand_new",
      slot: "head",
      path: "items/brand_new.png",
      z: 30,
      anchor: "head",
      offset_px: [0, -4],
      scale: 1,
    },
    {
      id: "aura.custom_glow",
      slot: "aura",
      path: "items/custom_glow.png",
      z: -30,
      anchor: "face",
      offset_px: [0, 0],
      scale: 1.25,
    },
    {
      id: "emote.wave",
      slot: "emote",
      path: "items/wave.png",
      z: 50,
      anchor: "head",
      offset_px: [2, 0],
      scale: 1,
    },
  ],
};

test("catalogItems accepts the raw server catalog and refuses hardcoded lists", () => {
  assert.equal(catalogItems(CATALOG).length, 3);
  assert.equal(catalogItems({ catalog: CATALOG }).length, 3);
  assert.equal(catalogItems(null).length, 0);

  const withNewItem = {
    items: [
      ...CATALOG.items,
      { id: "hat.future_item", name: "Future", slot: "head", price_bits: 10 },
    ],
  };
  assert.ok(catalogItems(withNewItem).some((item) => item.id === "hat.future_item"));
});

test("groupCatalogBySlot groups server items in stable slot order", () => {
  const groups = groupCatalogBySlot(CATALOG);
  assert.deepEqual(
    groups.map((group) => group.slot),
    ["head", "aura", "emote"]
  );
  assert.deepEqual(
    groups.map((group) => group.items.length),
    [1, 1, 1]
  );
  assert.ok(SLOT_ORDER.indexOf("head") < SLOT_ORDER.indexOf("aura"));
  assert.equal(groups[0].label, "Head");
});

test("itemView normalises snake_case and camelCase field names", () => {
  const view = itemView({
    id: "front.scarf",
    name: "Scarf",
    slot: "front",
    rarity: "common",
    priceBits: 350,
    assetId: "front.scarf_px",
    owned: true,
  });
  assert.equal(view.priceBits, 350);
  assert.equal(view.assetId, "front.scarf_px");
  assert.equal(view.owned, true);
});

test("normaliseWallet never lets a negative balance leak into the UI", () => {
  assert.deepEqual(normaliseWallet({ balance: -5, revision: 2 }), {
    balance: 0,
    currency: "bits",
    revision: 2,
  });
  assert.equal(normaliseWallet({ balance: "350" }).balance, 350);
});

test("joinAssetUrl builds same-origin asset URLs and drops absolute ones", () => {
  assert.equal(joinAssetUrl("/api/plugins/hermagotchi/assets", "items/a.png"), "/api/plugins/hermagotchi/assets/items/a.png");
  assert.equal(joinAssetUrl("/api/plugins/hermagotchi/assets/", "/items/a.png"), "/api/plugins/hermagotchi/assets/items/a.png");
  assert.equal(joinAssetUrl("https://cdn.example/assets", "https://other.example/a.png"), "");
  assert.equal(joinAssetUrl("", "items/a.png"), "items/a.png");
});

test("buildPreviewLayers composes base plus equipped layers ordered by manifest z", () => {
  const layers = buildPreviewLayers({
    pet: { id: "pet-1", name: "Bit", species: "patchfox" },
    loadout: {
      head: "hat.brand_new",
      aura: "aura.custom_glow",
      emote: "emote.wave",
    },
    catalog: CATALOG,
    manifest: MANIFEST,
    assetBaseUrl: "/api/plugins/hermagotchi/assets",
  });

  assert.deepEqual(
    layers.map((layer) => layer.kind + ":" + layer.id),
    ["item:aura.custom_glow", "base:species.patchfox", "item:hat.brand_new", "item:emote.wave"]
  );
  assert.equal(layers[1].url, "/api/plugins/hermagotchi/assets/species/patchfox.png");
  assert.equal(layers[0].url, "/api/plugins/hermagotchi/assets/items/custom_glow.png");
  assert.equal(layers[0].scale, 1.25);
  assert.equal(layers[0].z, -30);
});

test("buildPreviewLayers uses a relative item asset_url even without a manifest entry", () => {
  const layers = buildPreviewLayers({
    pet: { id: "pet-1", species: "byteblob" },
    loadout: { front: "front.direct" },
    catalog: {
      items: [
        {
          id: "front.direct",
          name: "Direct",
          slot: "front",
          asset_id: "front.direct",
          asset_url: "px3/items/direct.png",
        },
      ],
    },
    manifest: { species: {}, assets: [] },
    assetBaseUrl: "/api/plugins/hermagotchi/assets",
  });

  const itemLayer = layers.find((layer) => layer.kind === "item");
  assert.equal(itemLayer.url, "/api/plugins/hermagotchi/assets/px3/items/direct.png");
  assert.equal(itemLayer.z, 40);
});

test("buildPreviewLayers drops an absolute item asset_url so authedFetch never sees it", () => {
  const layers = buildPreviewLayers({
    pet: { id: "pet-1", species: "byteblob" },
    loadout: { front: "front.direct" },
    catalog: {
      items: [
        {
          id: "front.direct",
          name: "Direct",
          slot: "front",
          asset_id: "front.direct",
          asset_url: "https://cdn.example/direct.png",
        },
      ],
    },
    manifest: { species: {}, assets: [] },
    assetBaseUrl: "/api/plugins/hermagotchi/assets",
  });

  assert.equal(layers.some((layer) => layer.kind === "item"), false);
  assert.ok(layers.every((layer) => !/^https?:/i.test(layer.url)));
});

test("manifestFromCatalog reads an embedded manifest when the server supplies one", () => {
  assert.equal(manifestFromCatalog({ manifest: MANIFEST }), MANIFEST);
  assert.equal(manifestFromCatalog({ assetManifest: MANIFEST }), MANIFEST);
  assert.equal(manifestFromCatalog({}), null);
});

test("loadout merge/remove keeps one item per slot", () => {
  const first = mergeLoadout({}, "head", "hat.a");
  const second = mergeLoadout(first, "head", "hat.b");
  assert.deepEqual(second, { head: "hat.b" });
  assert.equal(loadoutItemId(second, "head"), "hat.b");
  assert.deepEqual(removeFromLoadout(second, "head"), {});
  assert.equal(loadoutItemId({ head: { id: "hat.c" } }, "head"), "hat.c");
});

test("itemAvailability gates buy, equip and unequip from live state", () => {
  const item = itemView(CATALOG.items[0]);
  const wallet = normaliseWallet({ balance: 500 });
  const avail = itemAvailability({ item, wallet, petId: "pet-1", loadout: {} });
  assert.equal(avail.affordable, false);
  assert.equal(avail.canBuy, false);
  assert.equal(avail.canEquip, true);
  assert.equal(avail.canUnequip, false);

  const equipped = itemAvailability({
    item,
    wallet: normaliseWallet({ balance: 2000 }),
    petId: "pet-1",
    loadout: { head: "hat.brand_new" },
  });
  assert.equal(equipped.equipped, true);
  assert.equal(equipped.canEquip, false);
  assert.equal(equipped.canUnequip, true);

  const noPet = itemAvailability({
    item,
    wallet: normaliseWallet({ balance: 2000 }),
    loadout: {},
  });
  assert.equal(noPet.canEquip, false);
});

test("readEnvelope is safe for bridge failures", () => {
  const result = readEnvelope({
    ok: false,
    status: "offline",
    error: { code: "network_error", message: "No network", retry_after_s: 2 },
  });
  assert.equal(result.ok, false);
  assert.equal(result.status, "offline");
  assert.equal(result.retryAfterS, 2);
  assert.equal(readEnvelope({ ok: true, data: { balance: 5 } }).data.balance, 5);
});

function launchShopItems() {
  return LAUNCH_MANIFEST.assets.map((asset) =>
    itemView({
      id: asset.id,
      name: asset.id,
      slot: asset.slot,
      asset_id: asset.id,
    })
  );
}

test("itemThumbPath resolves a visible thumb for every launch-003 slot", () => {
  const items = launchShopItems();
  const slots = new Set(items.map((item) => item.slot));
  assert.deepEqual(
    Array.from(slots).sort(),
    SLOT_ORDER.slice().sort(),
    "manifest covers every shop slot"
  );

  const seen = new Set();
  for (const item of items) {
    const thumbPath = itemThumbPath(item, LAUNCH_MANIFEST);
    const shortName = item.assetId.slice(item.assetId.lastIndexOf(".") + 1);
    assert.equal(
      thumbPath,
      SHOP_THUMB_DIR + "/" + shortName + "_thumb.png",
      "unexpected thumb path for " + item.id
    );
    assert.ok(!seen.has(thumbPath), "duplicate thumb path " + thumbPath);
    seen.add(thumbPath);

    const url = itemThumbUrl("/api/plugins/hermagotchi/assets", item, LAUNCH_MANIFEST);
    assert.equal(url, "/api/plugins/hermagotchi/assets/" + thumbPath);
    assert.match(url, /\/px3\/thumbs\/[a-z0-9_]+_thumb\.png$/);
  }
});

test("itemThumbPath falls back to the id convention when the manifest is absent", () => {
  const future = itemView({
    id: "hat.future_item",
    name: "Future",
    slot: "head",
    asset_id: "hat.future_item",
  });
  assert.equal(itemThumbPath(future, null), "px3/thumbs/future_item_thumb.png");
  assert.equal(
    itemThumbUrl("", future, null),
    "px3/thumbs/future_item_thumb.png"
  );
  assert.equal(itemThumbPath({}, null), "");
  assert.equal(itemThumbUrl("/api/plugins/hermagotchi/assets", {}, null), "");
  assert.equal(itemThumbUrl("https://cdn.example/assets", future, null), "");
});

test("ShopTab uses the shared thumb helper and a labelled image fallback", () => {
  assert.ok(SHOP_TAB_SOURCE.includes("itemThumbUrl"), "ShopTab must use itemThumbUrl");
  assert.ok(!/function\s+itemThumbPath/.test(SHOP_TAB_SOURCE), "ShopTab must not duplicate thumb logic");
  assert.ok(SHOP_TAB_SOURCE.includes("onError"), "image errors must be handled");
  assert.ok(
    SHOP_TAB_SOURCE.includes("hg-shop-card__thumb-fallback"),
    "missing labelled fallback"
  );
  assert.ok(SHOP_TAB_SOURCE.includes('"data-blank"'), "thumb needs data-blank state");
});
