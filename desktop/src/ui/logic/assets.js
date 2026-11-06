/**
 * Pure asset-path helpers shared by the Desktop UI. These never touch the DOM,
 * the network or host-specific paths: callers join them against the bridge's
 * `…/assets` root.
 */

export const ANIM_STRIP_TEMPLATE = "px3/anims/{species}_{palette}_{state}.png";

export const NPC_PORTRAITS = Object.freeze({
  "npc.don_piedro": "px3/npcs/don_piedro_portrait.png",
  "npc.nous_girl": "px3/npcs/nous_girl_portrait.png",
  "npc.teknium": "px3/npcs/teknium_portrait.png",
  "npc.southpaw": "px3/npcs/southpaw_portrait.png",
});

export function joinAssetUrl(baseUrl, path) {
  if (!path) return "";
  const value = String(path);
  if (/^(?:https?:|data:|blob:)/i.test(value)) return value;
  const base = typeof baseUrl === "string" ? baseUrl.replace(/\/+$/, "") : "";
  const relative = value.replace(/^(?:\.\/)+/, "").replace(/^\/+/, "");
  if (!base) return relative;
  if (!relative) return base;
  return base + "/" + relative;
}

function petSpecies(pet) {
  if (typeof pet === "string") return pet;
  if (!pet || typeof pet !== "object") return "";
  return pet.species ? String(pet.species) : "";
}

function petPalette(pet) {
  if (!pet || typeof pet !== "object") return "";
  if (pet.appearance && typeof pet.appearance === "object") {
    const fromAppearance = pet.appearance.palette || pet.appearance.palette_id;
    if (fromAppearance) return String(fromAppearance);
  }
  const direct = pet.palette || pet.palette_id;
  return direct ? String(direct) : "";
}

function palettePath(entry, palette) {
  if (!palette || !entry || typeof entry !== "object") return "";
  for (const key of ["palettes", "overrides"]) {
    const group = entry[key];
    if (!group || typeof group !== "object" || Array.isArray(group)) continue;
    const value = group[palette];
    if (typeof value === "string" && value) return value;
    if (value && typeof value === "object") {
      if (typeof value.base === "string" && value.base) return value.base;
      if (typeof value.path === "string" && value.path) return value.path;
    }
  }
  return "";
}

export function speciesBodyPath(manifest, pet) {
  const species = petSpecies(pet);
  if (!species) return "";
  const entry =
    manifest &&
    manifest.species &&
    typeof manifest.species === "object" &&
    manifest.species[species];
  if (entry && typeof entry === "object") {
    const palette = petPalette(pet);
    const override = palettePath(entry, palette);
    if (override) return override;
    if (typeof entry.base === "string" && entry.base) return entry.base;
    if (typeof entry.path === "string" && entry.path) return entry.path;
  }
  return "px3/species/" + species + "_body.png";
}

function itemAssetId(itemOrId) {
  if (typeof itemOrId === "string") return itemOrId;
  if (!itemOrId || typeof itemOrId !== "object") return "";
  const id = itemOrId.asset_id || itemOrId.assetId || itemOrId.id;
  return id ? String(id) : "";
}

export function itemAssetPath(manifest, itemOrId) {
  const assetId = itemAssetId(itemOrId);
  if (!assetId) return "";
  const assets =
    manifest && Array.isArray(manifest.assets) ? manifest.assets : [];
  for (const asset of assets) {
    if (!asset || typeof asset !== "object") continue;
    const id = asset.id ? String(asset.id) : "";
    const alternate = asset.asset_id || asset.assetId;
    if (id === assetId || (alternate && String(alternate) === assetId)) {
      if (typeof asset.path === "string" && asset.path) return asset.path;
    }
  }
  if (itemOrId && typeof itemOrId === "object") {
    const direct =
      itemOrId.asset_url || itemOrId.assetUrl || itemOrId.path || "";
    if (direct) return String(direct);
  }
  const dot = assetId.lastIndexOf(".");
  const shortName = dot >= 0 ? assetId.slice(dot + 1) : assetId;
  return "px3/items/" + shortName + ".png";
}

export function npcPortraitPath(npcId) {
  if (!npcId) return "";
  const id = String(npcId);
  if (NPC_PORTRAITS[id]) return NPC_PORTRAITS[id];
  const prefixed = id.startsWith("npc.") ? id : "npc." + id;
  return NPC_PORTRAITS[prefixed] || "";
}

export function animStripPath(species, palette, state) {
  if (!species) return "";
  return ANIM_STRIP_TEMPLATE
    .replace("{species}", String(species))
    .replace("{palette}", String(palette || "teal"))
    .replace("{state}", String(state || "idle"));
}
