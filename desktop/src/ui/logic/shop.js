/**
 * Pure Shop helpers. Catalog data always comes from the server response; item
 * ids are never hardcoded here so new cosmetics show up automatically.
 */

import { joinAssetUrl, speciesBodyPath } from "./assets.js";

export { joinAssetUrl };

export const SLOT_ORDER = Object.freeze([
  "head",
  "face",
  "back",
  "front",
  "aura",
  "emote",
  "habitat",
  "title",
]);

export const SLOT_LABELS = Object.freeze({
  head: "Head",
  face: "Face",
  back: "Back",
  front: "Front",
  aura: "Aura",
  emote: "Emote",
  habitat: "Habitat",
  title: "Title",
});

export const SLOT_Z = Object.freeze({
  aura: -30,
  habitat: -20,
  back: -10,
  front: 40,
  face: 20,
  head: 30,
  emote: 50,
  title: 50,
});

function number(value, fallback = 0) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

export function readEnvelope(envelope) {
  const value = envelope && typeof envelope === "object" ? envelope : {};
  const ok = value.ok === true;
  const error = value.error && typeof value.error === "object" ? value.error : {};
  return {
    ok,
    status: value.status || (ok ? "ok" : "unavailable"),
    data: ok ? value.data : null,
    error,
    code: error.code || null,
    message: error.message || (ok ? "" : "The game service did not apply that action."),
    retryAfterS: Math.max(0, Number(error.retry_after_s) || 0),
  };
}

export function catalogItems(catalog) {
  if (Array.isArray(catalog)) return catalog.filter((item) => item && item.id);
  if (!catalog || typeof catalog !== "object") return [];
  if (Array.isArray(catalog.items)) return catalog.items.filter((item) => item && item.id);
  if (catalog.catalog && Array.isArray(catalog.catalog.items)) {
    return catalog.catalog.items.filter((item) => item && item.id);
  }
  return [];
}

export function itemView(item) {
  const slot = String(item && item.slot ? item.slot : "front");
  return {
    raw: item,
    id: String(item.id),
    name: String(item.name || item.id),
    slot,
    slotLabel: SLOT_LABELS[slot] || slot,
    rarity: String(item.rarity || "common"),
    priceBits: Math.max(0, Math.round(number(item.price_bits, number(item.priceBits, 0)))),
    assetId: String(item.asset_id || item.assetId || item.id),
    assetUrl: item.asset_url || item.assetUrl || "",
    compatibleRigs: Array.isArray(item.compatible_rigs)
      ? item.compatible_rigs
      : Array.isArray(item.compatibleRigs)
        ? item.compatibleRigs
        : [],
    owned: Boolean(item.owned || item.inventory_owned || item.inventoryOwned),
  };
}

export function groupCatalogBySlot(catalog) {
  const groups = new Map();
  for (const raw of catalogItems(catalog)) {
    const item = itemView(raw);
    if (!groups.has(item.slot)) groups.set(item.slot, []);
    groups.get(item.slot).push(item);
  }

  const slotRank = (slot) => {
    const index = SLOT_ORDER.indexOf(slot);
    return index === -1 ? SLOT_ORDER.length : index;
  };

  return Array.from(groups.entries())
    .map(([slot, items]) => ({
      slot,
      label: SLOT_LABELS[slot] || slot,
      items: items.slice().sort((a, b) => a.id.localeCompare(b.id)),
    }))
    .sort((a, b) => {
      const rank = slotRank(a.slot) - slotRank(b.slot);
      return rank === 0 ? a.slot.localeCompare(b.slot) : rank;
    });
}

export function normaliseWallet(wallet) {
  const value = wallet && typeof wallet === "object" ? wallet : {};
  return {
    balance: Math.max(0, Math.round(number(value.balance, 0))),
    currency: value.currency || "bits",
    revision: Math.max(0, Math.round(number(value.revision, 0))),
  };
}

export function manifestFromCatalog(catalog) {
  if (!catalog || typeof catalog !== "object") return null;
  if (catalog.manifest && typeof catalog.manifest === "object") return catalog.manifest;
  if (catalog.asset_manifest && typeof catalog.asset_manifest === "object") {
    return catalog.asset_manifest;
  }
  if (catalog.assetManifest && typeof catalog.assetManifest === "object") {
    return catalog.assetManifest;
  }
  return null;
}

function manifestAssetMap(manifest) {
  const map = new Map();
  if (!manifest || !Array.isArray(manifest.assets)) return map;
  for (const asset of manifest.assets) {
    if (!asset || !asset.id) continue;
    map.set(String(asset.id), asset);
  }
  return map;
}

function normaliseLoadout(loadout) {
  if (!loadout) return [];
  if (Array.isArray(loadout)) {
    return loadout
      .filter((value) => value && typeof value === "object")
      .map((value) => [value.slot, value]);
  }
  if (typeof loadout !== "object") return [];
  return Object.entries(loadout).filter(([, value]) => value != null);
}

function zFor(slot, manifestAsset) {
  if (manifestAsset && Number.isFinite(Number(manifestAsset.z))) {
    return Number(manifestAsset.z);
  }
  return Number.isFinite(SLOT_Z[slot]) ? SLOT_Z[slot] : 0;
}

export function buildPreviewLayers(options = {}) {
  const pet = options.pet || null;
  const manifest = options.manifest || null;
  const catalog = options.catalog || null;
  const baseUrl =
    options.assetBaseUrl ||
    options.asset_base_url ||
    (manifest && (manifest.base_url || manifest.baseUrl)) ||
    "";

  const byId = new Map();
  const byAssetId = new Map();
  for (const raw of catalogItems(catalog)) {
    const item = itemView(raw);
    byId.set(item.id, item);
    byAssetId.set(item.assetId, item);
  }
  const assetMap = manifestAssetMap(manifest);
  const layers = [];

  const species = pet && pet.species ? String(pet.species) : "";
  const speciesPath = speciesBodyPath(manifest, pet);
  const conventionPath = species ? "px3/species/" + species + "_body.png" : "";
  const explicitBase =
    (pet && pet.asset_url) ||
    (pet && pet.assetUrl) ||
    (pet && pet.appearance && (pet.appearance.asset_url || pet.appearance.assetUrl)) ||
    "";
  const basePath = speciesPath || explicitBase;
  const manifestDerived = Boolean(speciesPath && speciesPath !== conventionPath);
  const includeBase = Boolean(basePath) && Boolean(baseUrl || manifestDerived || explicitBase);
  if (includeBase) {
    layers.push({
      kind: "base",
      id: "species." + String((pet && pet.species) || "pet"),
      slot: "body",
      label: (pet && pet.name) || "Pet",
      url: joinAssetUrl(baseUrl, basePath),
      z: 0,
      scale: 1,
      offsetPx: [0, 0],
      anchor: "ground",
    });
  }

  for (const [slotKey, value] of normaliseLoadout(options.loadout)) {
    const valueObject = value && typeof value === "object" ? value : {};
    const itemId =
      typeof value === "string"
        ? value
        : String(valueObject.id || valueObject.item_id || "");
    if (!itemId) continue;

    const catalogItem = byId.get(itemId) || byAssetId.get(itemId) || null;
    const slot = String(valueObject.slot || (catalogItem && catalogItem.slot) || slotKey);
    const assetId = String(
      valueObject.asset_id ||
        valueObject.assetId ||
        (catalogItem && catalogItem.assetId) ||
        itemId
    );
    const manifestAsset = assetMap.get(assetId) || assetMap.get(itemId) || null;
    const assetUrl =
      valueObject.asset_url ||
      valueObject.assetUrl ||
      (catalogItem && catalogItem.assetUrl) ||
      (manifestAsset && manifestAsset.path) ||
      "";

    layers.push({
      kind: "item",
      id: itemId,
      slot,
      label:
        valueObject.name ||
        (catalogItem && catalogItem.name) ||
        itemId,
      url: joinAssetUrl(baseUrl, assetUrl),
      z: zFor(slot, manifestAsset),
      scale: number(
        valueObject.scale != null
          ? valueObject.scale
          : manifestAsset && manifestAsset.scale,
        1
      ),
      offsetPx:
        valueObject.offset_px ||
        valueObject.offsetPx ||
        (manifestAsset && manifestAsset.offset_px) ||
        [0, 0],
      anchor:
        valueObject.anchor || (manifestAsset && manifestAsset.anchor) || "body",
    });
  }

  return layers
    .filter((layer) => layer.url)
    .sort((a, b) => {
      const z = a.z - b.z;
      return z === 0 ? a.id.localeCompare(b.id) : z;
    });
}

export function mergeLoadout(loadout, slot, itemId) {
  const next = {};
  for (const [key, value] of normaliseLoadout(loadout)) {
    const id = typeof value === "string" ? value : value && (value.id || value.item_id);
    if (key !== slot && id) next[key] = id;
  }
  if (itemId) next[slot] = itemId;
  return next;
}

export function removeFromLoadout(loadout, slot) {
  return mergeLoadout(loadout, slot, null);
}

export function loadoutItemId(loadout, slot) {
  for (const [key, value] of normaliseLoadout(loadout)) {
    if (key !== slot) continue;
    if (typeof value === "string") return value;
    if (value && typeof value === "object") {
      return value.id || value.item_id || null;
    }
  }
  return null;
}

export function itemAvailability(options = {}) {
  const item = options.item && options.item.id ? options.item : itemView(options.item || {});
  const wallet = normaliseWallet(options.wallet);
  const petId = options.petId || null;
  const equippedId = loadoutItemId(options.loadout, item.slot);
  const equipped = equippedId === item.id;
  return {
    equipped,
    affordable: wallet.balance >= item.priceBits,
    canBuy: !item.owned && wallet.balance >= item.priceBits,
    canEquip: Boolean(petId) && !equipped,
    canUnequip: Boolean(petId) && equipped,
  };
}
