import { useEffect, useRef, useState } from "react";
import { jsx, jsxs } from "react/jsx-runtime";
import { CareMeter } from "../components/CareMeter.js";
import { NpcHostBanner } from "../components/NpcHostBanner.js";
import { PetPreview } from "../components/PetPreview.js";
import { StateNotice, UI_STATES } from "../states.js";
import {
  CARE_ACTIONS,
  CARE_LABELS,
  MODES,
  MODE_LABELS,
  SPECIES,
  SPECIES_LABELS,
  buildAdoptRequest,
  careMeters,
  extractPetId,
  habitatView,
  petFromCareResponse,
  readEnvelope,
} from "../logic/habitat.js";

export const HABITAT_PLACEHOLDER = Object.freeze({
  name: "Not named yet",
  species: "Not adopted",
  xp: "0 / 100",
  mode: "human",
});

const CARE_ANIM = Object.freeze({
  feed: "eat",
  play: "happy",
  rest: "sleep",
});

function loadoutFromPet(pet) {
  if (!pet || typeof pet !== "object") return {};
  const candidates = [
    pet.loadout,
    pet.equipment,
    pet.appearance && pet.appearance.loadout,
  ];
  for (const candidate of candidates) {
    if (candidate && typeof candidate === "object" && !Array.isArray(candidate)) {
      return candidate;
    }
  }
  return {};
}

function stateForEnvelope(result) {
  if (!result || result.ok) return null;
  if (result.status === "auth_missing" || result.status === "unauthorized") {
    return UI_STATES.AUTH_MISSING;
  }
  if (
    result.status === "offline" ||
    result.status === "unavailable" ||
    result.status === "http_error" ||
    result.status === "not_allowed"
  ) {
    return UI_STATES.SERVICE_UNAVAILABLE;
  }
  return null;
}

function MetaRow(props) {
  return jsxs("p", {
    children: [
      jsx("span", { className: "hg-label", children: props.label }),
      jsx("strong", { "data-placeholder": props.placeholder, children: props.value }),
    ],
  });
}

function StubHabitat(props) {
  return jsxs("section", {
    className: "hg-habitat",
    "data-tab": "habitat",
    children: [
      jsx(StateNotice, { state: props.uiState }),
      jsx(NpcHostBanner, {
        surface: "habitat",
        assetBaseUrl: props.assetBaseUrl,
      }),
      jsxs("div", {
        className: "hg-card hg-pet-card",
        children: [
          jsx("div", {
            className: "hg-pet-card__art",
            role: "img",
            "aria-label": "Pet preview placeholder",
            children: "?",
          }),
          jsxs("div", {
            className: "hg-pet-card__meta",
            children: [
              jsx(MetaRow, {
                label: "Pet name",
                placeholder: "pet-name",
                value: HABITAT_PLACEHOLDER.name,
              }),
              jsx(MetaRow, {
                label: "Species",
                placeholder: "pet-species",
                value: HABITAT_PLACEHOLDER.species,
              }),
              jsx(MetaRow, {
                label: "Mode",
                placeholder: "pet-mode",
                value: HABITAT_PLACEHOLDER.mode,
              }),
            ],
          }),
        ],
      }),
      jsxs("div", {
        className: "hg-card",
        children: [
          jsx("h3", { children: "Care" }),
          jsx(CareMeter, { label: "Fullness", value: 0 }),
          jsx(CareMeter, { label: "Happiness", value: 0 }),
          jsx(CareMeter, { label: "Energy", value: 0 }),
          jsx("p", {
            className: "hg-muted",
            children: "Adopt a pet in agent chat to fill these care meters.",
          }),
        ],
      }),
      jsxs("div", {
        className: "hg-card",
        children: [
          jsx("h3", { children: "Progress" }),
          jsxs("dl", {
            children: [
              jsxs("div", {
                children: [
                  jsx("dt", { children: "XP" }),
                  jsx("dd", { children: HABITAT_PLACEHOLDER.xp }),
                ],
              }),
              jsxs("div", {
                children: [
                  jsx("dt", { children: "Agent goal" }),
                  jsx("dd", { children: "No goal set" }),
                ],
              }),
            ],
          }),
        ],
      }),
    ],
  });
}

export function HabitatTab(props = {}) {
  const api = props.api;
  const hasApi = Boolean(api && typeof api.get === "function" && typeof api.post === "function");
  const requestedPetId = props.petId || "";
  const [me, setMe] = useState(null);
  const [pet, setPet] = useState(props.pet || null);
  const [goal, setGoal] = useState(props.goal || null);
  const [name, setName] = useState("");
  const [species, setSpecies] = useState(SPECIES[0]);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [bridgeState, setBridgeState] = useState(null);
  const [loading, setLoading] = useState(hasApi);
  const [manifest, setManifest] = useState(
    props.manifest || props.assetManifest || null
  );
  const [catalog, setCatalog] = useState(props.catalog || null);
  const [assetBaseUrl, setAssetBaseUrl] = useState(props.assetBaseUrl || "");
  const [loadout, setLoadout] = useState(props.loadout || {});
  const [animState, setAnimState] = useState(props.animState || "idle");
  const animTimer = useRef(null);

  useEffect(function () {
    return function () {
      if (animTimer.current) clearTimeout(animTimer.current);
    };
  }, []);

  useEffect(
    function () {
      const fromPet = loadoutFromPet(pet);
      if (Object.keys(fromPet).length) {
        setLoadout(function (previous) {
          return Object.assign({}, fromPet, previous);
        });
      }
    },
    [pet]
  );

  function flashAnim(action) {
    const next = CARE_ANIM[action];
    if (!next) return;
    setAnimState(next);
    if (animTimer.current) clearTimeout(animTimer.current);
    animTimer.current = setTimeout(function () {
      setAnimState("idle");
      animTimer.current = null;
    }, 2000);
  }

  useEffect(() => {
    if (!hasApi) return undefined;
    let alive = true;

    async function load() {
      setLoading(true);
      setError("");
      if (!props.assetBaseUrl && api.assets && typeof api.assets.url === "function") {
        setAssetBaseUrl(api.assets.url(""));
      }
      let meData = null;
      let loadResult = null;

      try {
        loadResult = readEnvelope(await api.get("/me"));
      } catch (_error) {
        loadResult = readEnvelope(null);
      }
      if (!alive) return;
      if (loadResult.ok) {
        meData = loadResult.data;
        setMe(meData);
      } else {
        setBridgeState(stateForEnvelope(loadResult));
      }

      let petId = requestedPetId || extractPetId(meData);
      if (!petId && meData && meData.pet && meData.pet.id) {
        setPet(meData.pet);
        petId = meData.pet.id;
      }

      const manifestRequest =
        api.assets && typeof api.assets.manifest === "function"
          ? api.assets.manifest().catch(() => null)
          : Promise.resolve(null);
      const catalogRequest = props.catalog
        ? Promise.resolve(null)
        : api.get("/catalog").catch(() => null);
      const requests = [
        api.get("/goals").catch(() => null),
        petId && !(meData && meData.pet && meData.pet.id === petId)
          ? api.get("/pets/" + encodeURIComponent(petId)).catch(() => null)
          : Promise.resolve(null),
        manifestRequest,
        catalogRequest,
      ];

      const [goalEnvelope, petEnvelope, manifestEnvelope, catalogEnvelope] =
        await Promise.all(requests);
      if (!alive) return;

      const manifestResult = readEnvelope(manifestEnvelope);
      if (manifestResult.ok && manifestResult.data) {
        setManifest(manifestResult.data);
      }
      const catalogResult = readEnvelope(catalogEnvelope);
      if (catalogResult.ok && catalogResult.data) {
        setCatalog(catalogResult.data);
      }

      const goalResult = readEnvelope(goalEnvelope);
      if (goalResult.ok) {
        const data = goalResult.data || {};
        setGoal(data.goal || (Array.isArray(data.goals) && data.goals[0]) || null);
      }

      if (petEnvelope) {
        const petResult = readEnvelope(petEnvelope);
        if (petResult.ok && petResult.data) {
          setPet(petResult.data);
        } else if (petResult.status !== "http_error" || petResult.code !== "pet_not_found") {
          setBridgeState(stateForEnvelope(petResult));
          if (petResult.message) setError(petResult.message);
        }
      }

      setLoading(false);
    }

    load();
    return function cleanup() {
      alive = false;
    };
  }, [api, hasApi, requestedPetId, props.assetBaseUrl, props.catalog]);

  const uiState =
    props.state || props.uiState || bridgeState || UI_STATES.READY;
  if (!hasApi) {
    return jsx(StubHabitat, {
      uiState,
      assetBaseUrl: props.assetBaseUrl,
    });
  }

  const view = habitatView({ pet, me, goal });

  async function adopt(event) {
    if (event && typeof event.preventDefault === "function") event.preventDefault();
    setBusy("adopt");
    setError("");
    try {
      const result = readEnvelope(
        await api.post("/pets", buildAdoptRequest({ species, name, mode: "human" }))
      );
      if (!result.ok) {
        setBridgeState(stateForEnvelope(result));
        setError(result.message);
        return;
      }
      const adopted = result.data && result.data.pet ? result.data.pet : result.data;
      if (adopted && adopted.id) setPet(adopted);
    } catch (_error) {
      setError("Adoption could not be completed.");
    } finally {
      setBusy("");
    }
  }

  async function care(action) {
    if (!pet || !pet.id) return;
    setBusy(action);
    setError("");
    try {
      const result = readEnvelope(
        await api.post("/pets/" + encodeURIComponent(pet.id) + "/care", { action })
      );
      if (!result.ok) {
        setBridgeState(stateForEnvelope(result));
        setError(result.message);
        return;
      }
      setPet((previous) => petFromCareResponse(result.data, previous));
      flashAnim(action);
    } catch (_error) {
      setError("Care could not be completed.");
    } finally {
      setBusy("");
    }
  }

  return jsxs("section", {
    className: "hg-habitat",
    "data-tab": "habitat",
    children: [
      jsx(StateNotice, { state: uiState }),
      jsx(NpcHostBanner, {
        surface: "habitat",
        assetBaseUrl: assetBaseUrl,
      }),
      error
        ? jsx("p", { className: "hg-error", role: "alert", children: error })
        : null,
      jsxs("div", {
        className: "hg-card hg-pet-card",
        children: [
          jsx("div", {
            className: "hg-pet-card__art",
            children: jsx(PetPreview, {
              pet,
              loadout,
              catalog,
              manifest,
              assetBaseUrl,
              animState,
              label: view.name + " preview",
            }),
          }),
          jsxs("div", {
            className: "hg-pet-card__meta",
            children: [
              jsx(MetaRow, {
                label: "Pet name",
                placeholder: "pet-name",
                value: view.name,
              }),
              jsx(MetaRow, {
                label: "Species",
                placeholder: "pet-species",
                value: view.speciesLabel,
              }),
              jsx(MetaRow, {
                label: "Mode",
                placeholder: "pet-mode",
                value: view.modeLabel,
              }),
              jsx(MetaRow, {
                label: "Level",
                placeholder: "pet-level",
                value: String(view.level),
              }),
            ],
          }),
        ],
      }),
      !pet && !loading
        ? jsxs("form", {
            className: "hg-card hg-col",
            onSubmit: adopt,
            children: [
              jsx("h3", { children: "Adopt" }),
              jsx("label", {
                className: "hg-label",
                htmlFor: "hg-adopt-species",
                children: "Species",
              }),
              jsx(
                "select",
                {
                  id: "hg-adopt-species",
                  className: "hg-input",
                  value: species,
                  onChange: function (event) {
                    setSpecies(event.target.value);
                  },
                  children: SPECIES.map((value) =>
                    jsx("option", { value, children: SPECIES_LABELS[value] || value }, value)
                  ),
                }
              ),
              jsx("label", {
                className: "hg-label",
                htmlFor: "hg-adopt-name",
                children: "Pet name",
              }),
              jsx("input", {
                id: "hg-adopt-name",
                className: "hg-input",
                type: "text",
                maxLength: 32,
                value: name,
                placeholder: "Optional name",
                onChange: function (event) {
                  setName(event.target.value);
                },
              }),
              jsx("button", {
                type: "submit",
                className: "hg-btn hg-btn--primary",
                disabled: busy === "adopt",
                children: busy === "adopt" ? "Adopting..." : "Adopt pet",
              }),
            ],
          })
        : null,
      jsxs("div", {
        className: "hg-card",
        children: [
          jsx("h3", { children: "Care" }),
          careMeters(view.care).map((meter) =>
            jsx(CareMeter, { label: meter.label, value: meter.value }, meter.key)
          ),
          jsx("div", {
            className: "hg-row",
            children: CARE_ACTIONS.map((action) =>
              jsx(
                "button",
                {
                  type: "button",
                  className: "hg-btn",
                  "data-care-action": action,
                  disabled: !pet || Boolean(busy),
                  onClick: function () {
                    care(action);
                  },
                  children: busy === action ? CARE_LABELS[action] + "..." : CARE_LABELS[action],
                },
                action
              )
            ),
          }),
          pet
            ? null
            : jsx("p", {
                className: "hg-muted",
                children: "Adopt a pet in agent chat to fill these care meters.",
              }),
        ],
      }),
      jsxs("div", {
        className: "hg-card",
        children: [
          jsx("h3", { children: "Progress" }),
          jsxs("dl", {
            children: [
              jsxs("div", {
                children: [
                  jsx("dt", { children: "XP" }),
                  jsx("dd", { children: view.xp }),
                ],
              }),
              jsxs("div", {
                children: [
                  jsx("dt", { children: "Agent goal" }),
                  jsx("dd", { children: view.goalLabel }),
                ],
              }),
            ],
          }),
        ],
      }),
      jsx("p", {
        className: "hg-muted",
        children:
          "Available modes: " +
          MODES.map((mode) => MODE_LABELS[mode] || mode).join(", ") +
          ".",
      }),
    ],
  });
}
