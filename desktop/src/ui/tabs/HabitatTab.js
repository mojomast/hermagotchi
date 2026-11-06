import { useEffect, useState } from "react";
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
      jsx(NpcHostBanner, { surface: "habitat" }),
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

  useEffect(() => {
    if (!hasApi) return undefined;
    let alive = true;

    async function load() {
      setLoading(true);
      setError("");
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

      const requests = [api.get("/goals").catch(() => null)];
      if (petId && !(meData && meData.pet && meData.pet.id === petId)) {
        requests.push(api.get("/pets/" + encodeURIComponent(petId)).catch(() => null));
      } else {
        requests.push(Promise.resolve(null));
      }

      const [goalEnvelope, petEnvelope] = await Promise.all(requests);
      if (!alive) return;

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
  }, [api, hasApi, requestedPetId]);

  const uiState =
    props.state || props.uiState || bridgeState || UI_STATES.READY;
  if (!hasApi) {
    return jsx(StubHabitat, { uiState });
  }

  const view = habitatView({ pet, me, goal });
  const loadout = props.loadout || {};
  const manifest = props.manifest || props.assetManifest || null;

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
      jsx(NpcHostBanner, { surface: "habitat" }),
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
              catalog: props.catalog,
              manifest,
              assetBaseUrl: props.assetBaseUrl,
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
