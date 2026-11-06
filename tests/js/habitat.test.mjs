import test from "node:test";
import assert from "node:assert/strict";

import {
  CARE_ACTIONS,
  CARE_METERS,
  SPECIES,
  SPECIES_LABELS,
  applyCareAction,
  buildAdoptRequest,
  careMeters,
  clampMeter,
  extractPetId,
  goalLabel,
  habitatView,
  normaliseCare,
  petFromCareResponse,
  readEnvelope,
  xpProgressLabel,
} from "../../desktop/src/ui/logic/habitat.js";

test("clampMeter keeps every care value inside 0..100", () => {
  assert.equal(clampMeter(150), 100);
  assert.equal(clampMeter(-9), 0);
  assert.equal(clampMeter("42"), 42);
  assert.equal(clampMeter("not-a-number"), 0);
  assert.equal(clampMeter(100.4), 100);
});

test("normaliseCare fills all four server care fields", () => {
  assert.deepEqual(normaliseCare({ hunger: 130, comfort: -3 }), {
    health: 0,
    comfort: 0,
    hunger: 100,
    energy: 0,
  });
});

test("care actions mirror the server effects and clamp", () => {
  assert.deepEqual(CARE_ACTIONS, ["feed", "play", "rest"]);

  const care = { health: 50, comfort: 90, hunger: 90, energy: 5 };
  assert.equal(applyCareAction(care, "feed").hunger, 100);
  assert.equal(applyCareAction(care, "play").comfort, 100);
  assert.equal(applyCareAction(care, "play").energy, 0);
  assert.equal(applyCareAction(care, "rest").energy, 30);
  assert.deepEqual(applyCareAction(care, "unknown"), normaliseCare(care));
});

test("careMeters exposes the labels used by the Habitat tab", () => {
  assert.deepEqual(
    CARE_METERS.map((meter) => meter.label),
    ["Fullness", "Happiness", "Energy", "Health"]
  );
  const meters = careMeters({ hunger: 10, comfort: 20, energy: 30, health: 40 });
  assert.deepEqual(
    meters.map((meter) => meter.value),
    [10, 20, 30, 40]
  );
});

test("habitatView falls back to the frozen placeholder copy", () => {
  const view = habitatView({});
  assert.equal(view.adopted, false);
  assert.equal(view.name, "Not named yet");
  assert.equal(view.species, "Not adopted");
  assert.equal(view.mode, "human");
  assert.equal(view.xp, "0 / 100");
  assert.equal(view.goalLabel, "No goal set");
});

test("habitatView derives pet, mode, XP and goal from live data", () => {
  const view = habitatView({
    me: { policy: { mode: "coop" } },
    pet: {
      id: "pet-1",
      name: "Nibbles",
      species: "patchfox",
      level: 2,
      xp: 25,
      care: { health: 99, comfort: 80, hunger: 70, energy: 60 },
    },
    goal: { type: "cosmetic", target_id: "hat.binary_crown" },
  });

  assert.equal(view.adopted, true);
  assert.equal(view.petId, "pet-1");
  assert.equal(view.speciesLabel, "Patchfox");
  assert.equal(view.mode, "coop");
  assert.equal(view.modeLabel, "co-op");
  assert.equal(view.xp, "25 / 200");
  assert.equal(view.goalLabel, "Cosmetic: hat.binary_crown");
  assert.equal(view.care.hunger, 70);
});

test("xpProgressLabel always advances by at least 100", () => {
  assert.equal(xpProgressLabel(null), "0 / 100");
  assert.equal(xpProgressLabel({ level: 3, xp: 3 }), "3 / 300");
  assert.equal(xpProgressLabel({ level: 1, xp: 150 }), "150 / 200");
});

test("goalLabel renders a safe display string or the empty copy", () => {
  assert.equal(goalLabel(null), "No goal set");
  assert.equal(goalLabel({ type: "rank", target_id: "silver" }), "Rank: silver");
});

test("SPECIES exposes all ten launch-003 species with labels", () => {
  const expected = [
    "byteblob",
    "patchfox",
    "nullgeist",
    "kernelcrab",
    "cachebat",
    "stacktoise",
    "daemowl",
    "shellsnail",
    "regexopus",
    "firewyrm",
  ];
  assert.equal(SPECIES.length, 10);
  assert.deepEqual([...SPECIES], expected);
  assert.equal(new Set(SPECIES).size, 10);
  for (const id of expected) {
    assert.equal(SPECIES_LABELS[id], id.charAt(0).toUpperCase() + id.slice(1));
  }
});

test("buildAdoptRequest only sends allowlisted species and modes", () => {
  assert.deepEqual(buildAdoptRequest({ species: "nullgeist", name: "  Wisp  " }), {
    species: "nullgeist",
    mode: "human",
    name: "Wisp",
  });
  assert.deepEqual(buildAdoptRequest({ species: "firewyrm" }), {
    species: "firewyrm",
    mode: "human",
  });
  assert.deepEqual(buildAdoptRequest({ species: "regexopus", mode: "coop" }), {
    species: "regexopus",
    mode: "coop",
  });
  assert.deepEqual(buildAdoptRequest({ species: "dragon", mode: "nope" }), {
    species: SPECIES[0],
    mode: "human",
  });
});

test("extractPetId understands the shapes the bridge may return", () => {
  assert.equal(extractPetId(null), null);
  assert.equal(extractPetId({ pet_id: "a" }), "a");
  assert.equal(extractPetId({ pet: { id: "b" } }), "b");
  assert.equal(extractPetId({ account: { pet_id: "c" } }), "c");
});

test("readEnvelope normalises bridge success and failure without throwing", () => {
  const ok = readEnvelope({ ok: true, status: "ok", data: { care: {} } });
  assert.equal(ok.ok, true);
  assert.deepEqual(ok.data, { care: {} });

  const missing = readEnvelope({
    ok: false,
    status: "auth_missing",
    error: { code: "unauthorized", message: "Pair first", retry_after_s: 3 },
  });
  assert.equal(missing.ok, false);
  assert.equal(missing.status, "auth_missing");
  assert.equal(missing.code, "unauthorized");
  assert.equal(missing.retryAfterS, 3);

  assert.equal(readEnvelope(null).ok, false);
});

test("petFromCareResponse prefers the returned pet and falls back to care", () => {
  const pet = { id: "p", care: { hunger: 10 }, revision: 2 };
  const replaced = petFromCareResponse({ pet: { id: "p", care: { hunger: 90 } } }, pet);
  assert.equal(replaced.care.hunger, 90);

  const patched = petFromCareResponse(
    { care: { hunger: 77 }, revision: 9 },
    { id: "p", care: { hunger: 10 }, revision: 2 }
  );
  assert.equal(patched.care.hunger, 77);
  assert.equal(patched.revision, 9);
  assert.equal(petFromCareResponse(null, pet), pet);
});
