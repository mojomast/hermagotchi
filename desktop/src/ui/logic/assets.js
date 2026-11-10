/**
 * Pure asset-path helpers shared by the Desktop UI. These never touch the DOM,
 * the network or host-specific paths: callers join them against the bridge's
 * `…/assets` root.
 */

export const ANIM_STRIP_TEMPLATE = "px3/anims/{species}_{palette}_{state}.png";

/** Server appearance.traits.palette (palette_0N) → anim strip palette names. */
export const SERVER_PALETTE_TO_ANIM = Object.freeze({
  palette_01: "teal",
  palette_02: "grape",
  palette_03: "lime",
  palette_04: "brick",
  palette_05: "teal",
  palette_06: "grape",
  teal: "teal",
  grape: "grape",
  lime: "lime",
  brick: "brick",
});

export function resolveAnimPalette(value) {
  if (!value) return "teal";
  const key = String(value);
  return SERVER_PALETTE_TO_ANIM[key] || SERVER_PALETTE_TO_ANIM[key.toLowerCase()] || "teal";
}

export const NPC_PORTRAITS = Object.freeze({
  "npc.don_piedro": "px3/npcs/don_piedro_portrait.png",
  "npc.nous_girl": "px3/npcs/nous_girl_portrait.png",
  "npc.teknium": "px3/npcs/teknium_portrait.png",
  "npc.southpaw": "px3/npcs/southpaw_portrait.png",
});

const INLINE_ASSET = /^(?:data:|blob:)/i;
const URL_SCHEME = /^[a-z][a-z0-9+.-]*:/i;

export function isInlineAssetUrl(value) {
  return typeof value === "string" && INLINE_ASSET.test(value.trim());
}

/** Absolute http(s), protocol-relative, or any other non-inline scheme. */
export function isRemoteAssetUrl(value) {
  if (typeof value !== "string") return false;
  const text = value.trim();
  if (!text || isInlineAssetUrl(text)) return false;
  if (text.startsWith("//") || URL_SCHEME.test(text)) return true;
  const stripped = text.replace(/^(?:\.\/)+/, "").replace(/^\/+/, "");
  return URL_SCHEME.test(stripped) || stripped.startsWith("//");
}

/**
 * Relative path safe to join under the bridge assets route, or a data:/blob: URL.
 * Remote and traversing paths return "".
 */
export function safeRelativeAssetPath(path) {
  if (!path) return "";
  const value = String(path).trim();
  if (!value) return "";
  if (isInlineAssetUrl(value)) return value;
  if (isRemoteAssetUrl(value)) return "";
  const parts = [];
  for (const part of value.replace(/^(?:\.\/)+/, "").replace(/^\/+/, "").split("/")) {
    if (!part || part === ".") continue;
    if (part === ".." || URL_SCHEME.test(part) || part.includes("\\") || part.includes("%")) {
      return "";
    }
    parts.push(part);
  }
  return parts.join("/");
}

function safeAssetBase(baseUrl) {
  if (typeof baseUrl !== "string") return "";
  const base = baseUrl.trim().replace(/\/+$/, "");
  if (!base) return "";
  if (isRemoteAssetUrl(base) || isInlineAssetUrl(base)) return "";
  if (base.split("/").includes("..")) return "";
  return base;
}

export function joinAssetUrl(baseUrl, path) {
  if (!path) return "";
  const value = String(path).trim();
  if (!value) return "";
  if (isInlineAssetUrl(value)) return value;
  const relative = safeRelativeAssetPath(value);
  if (!relative) return "";
  const base = safeAssetBase(baseUrl);
  if (!base) {
    // A remote base must not produce an absolute URL; a missing base may
    // still return the relative path for later joining.
    return isRemoteAssetUrl(String(baseUrl || "")) ? "" : relative;
  }
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
    const appearance = pet.appearance;
    const traits = appearance.traits && typeof appearance.traits === "object" ? appearance.traits : null;
    const fromTraits = traits && (traits.palette || traits.palette_id);
    if (fromTraits) return String(fromTraits);
    const fromAppearance = appearance.palette || appearance.palette_id;
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
    if (direct) return safeRelativeAssetPath(direct);
  }
  // Prefer a silent miss over a guessed path that 404s in the shop grid.
  return "";
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
