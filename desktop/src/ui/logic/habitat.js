/**
 * Pure Habitat helpers. No React, network or DOM access so the same rules can
 * be exercised directly with `node --test`.
 */

export const SPECIES = Object.freeze(["byteblob", "patchfox", "nullgeist"]);

export const SPECIES_LABELS = Object.freeze({
  byteblob: "Byteblob",
  patchfox: "Patchfox",
  nullgeist: "Nullgeist",
});

export const CARE_ACTIONS = Object.freeze(["feed", "play", "rest"]);

export const CARE_LABELS = Object.freeze({
  feed: "Feed",
  play: "Play",
  rest: "Rest",
});

export const CARE_EFFECTS = Object.freeze({
  feed: Object.freeze({ hunger: 25 }),
  play: Object.freeze({ comfort: 20, energy: -10 }),
  rest: Object.freeze({ energy: 25 }),
});

export const CARE_METERS = Object.freeze([
  { key: "hunger", label: "Fullness" },
  { key: "comfort", label: "Happiness" },
  { key: "energy", label: "Energy" },
  { key: "health", label: "Health" },
]);

export const MODES = Object.freeze(["human", "agent", "coop"]);

export const MODE_LABELS = Object.freeze({
  human: "human",
  agent: "agent",
  coop: "co-op",
});

export function clampMeter(value, max = 100) {
  const limit = Number(max) > 0 ? Number(max) : 100;
  const number = Number(value);
  if (!Number.isFinite(number)) return 0;
  return Math.max(0, Math.min(Math.round(number), limit));
}

export function normaliseCare(raw) {
  const care = raw && typeof raw === "object" ? raw : {};
  const result = {};
  for (const field of ["health", "comfort", "hunger", "energy"]) {
    result[field] = clampMeter(care[field]);
  }
  return result;
}

export function applyCareAction(care, action) {
  const next = normaliseCare(care);
  const effects = CARE_EFFECTS[action];
  if (!effects) return next;
  for (const field of Object.keys(effects)) {
    next[field] = clampMeter(next[field] + effects[field]);
  }
  return next;
}

export function careMeters(care) {
  const normalised = normaliseCare(care);
  return CARE_METERS.map((meter) => ({
    key: meter.key,
    label: meter.label,
    value: normalised[meter.key],
  }));
}

export function xpProgressLabel(pet) {
  const level = Math.max(1, Number(pet && pet.level) || 1);
  const xp = Math.max(0, Number(pet && pet.xp) || 0);
  const next = Math.max(100, level * 100, Math.ceil((xp + 1) / 100) * 100);
  return xp + " / " + next;
}

export function goalLabel(goal) {
  if (!goal || typeof goal !== "object" || !goal.target_id) return "No goal set";
  const type = goal.type ? String(goal.type) : "goal";
  return type.charAt(0).toUpperCase() + type.slice(1) + ": " + goal.target_id;
}

export function extractPetId(me) {
  if (!me || typeof me !== "object") return null;
  if (typeof me.pet_id === "string" && me.pet_id) return me.pet_id;
  if (me.pet && typeof me.pet.id === "string" && me.pet.id) return me.pet.id;
  if (me.account && typeof me.account.pet_id === "string" && me.account.pet_id) {
    return me.account.pet_id;
  }
  return null;
}

export function resolveMode(me, pet, fallback = "human") {
  const candidates = [
    me && me.policy && me.policy.mode,
    me && me.mode,
    pet && pet.mode,
    fallback,
  ];
  for (const candidate of candidates) {
    if (typeof candidate === "string" && candidate) return candidate;
  }
  return "human";
}

export function habitatView(options = {}) {
  const pet = options.pet || null;
  const me = options.me || null;
  const goal = options.goal || null;
  const mode = resolveMode(me, pet);
  return {
    adopted: Boolean(pet && pet.id),
    petId: pet && pet.id ? pet.id : null,
    name: pet && pet.name ? pet.name : "Not named yet",
    species: pet && pet.species ? pet.species : "Not adopted",
    speciesLabel:
      pet && pet.species ? SPECIES_LABELS[pet.species] || pet.species : "Not adopted",
    mode,
    modeLabel: MODE_LABELS[mode] || mode,
    level: Math.max(1, Number(pet && pet.level) || 1),
    xp: xpProgressLabel(pet),
    care: normaliseCare(pet && pet.care),
    goal,
    goalLabel: goalLabel(goal),
  };
}

export function buildAdoptRequest(options = {}) {
  const species = SPECIES.includes(options.species) ? options.species : SPECIES[0];
  const mode = MODES.includes(options.mode) ? options.mode : "human";
  const body = { species, mode };
  const name = typeof options.name === "string" ? options.name.trim() : "";
  if (name) body.name = name.slice(0, 32);
  return body;
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

export function petFromCareResponse(data, previous) {
  if (!data || typeof data !== "object") return previous || null;
  if (data.pet && typeof data.pet === "object") return data.pet;
  if (!previous) return null;
  if (data.care && typeof data.care === "object") {
    return {
      ...previous,
      care: normaliseCare(data.care),
      revision: Number(data.revision) || previous.revision,
    };
  }
  return previous;
}
