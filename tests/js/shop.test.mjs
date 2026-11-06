import test from "node:test";
import assert from "node:assert/strict";

import {
  SLOT_ORDER,
  buildPreviewLayers,
  catalogItems,
  groupCatalogBySlot,
  itemAvailability,
  itemView,
  joinAssetUrl,
  loadoutItemId,
  manifestFromCatalog,
  mergeLoadout,
  normaliseWallet,
  readEnvelope,
  removeFromLoadout,
} from "../../desktop/src/ui/logic/shop.js";

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

test("joinAssetUrl builds public asset URLs without changing absolute ones", () => {
  assert.equal(joinAssetUrl("https://cdn.example/assets", "items/a.png"), "https://cdn.example/assets/items/a.png");
  assert.equal(joinAssetUrl("https://cdn.example/assets/", "/items/a.png"), "https://cdn.example/assets/items/a.png");
  assert.equal(joinAssetUrl("https://cdn.example/assets", "https://other.example/a.png"), "https://other.example/a.png");
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
    assetBaseUrl: "https://cdn.example/assets",
  });

  assert.deepEqual(
    layers.map((layer) => layer.kind + ":" + layer.id),
    ["item:aura.custom_glow", "base:species.patchfox", "item:hat.brand_new", "item:emote.wave"]
  );
  assert.equal(layers[1].url, "https://cdn.example/assets/species/patchfox.png");
  assert.equal(layers[0].url, "https://cdn.example/assets/items/custom_glow.png");
  assert.equal(layers[0].scale, 1.25);
  assert.equal(layers[0].z, -30);
});

test("buildPreviewLayers uses an item asset_url even without a manifest entry", () => {
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
  });

  assert.equal(layers.length, 1);
  assert.equal(layers[0].url, "https://cdn.example/direct.png");
  assert.equal(layers[0].z, 40);
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
