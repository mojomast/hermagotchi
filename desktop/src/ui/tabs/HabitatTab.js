import { jsx, jsxs } from "react/jsx-runtime";
import { CareMeter } from "../components/CareMeter.js";
import { StateNotice, UI_STATES } from "../states.js";

export const HABITAT_PLACEHOLDER = Object.freeze({
  name: "Not named yet",
  species: "Not adopted",
  xp: "0 / 100",
  mode: "human",
});

function MetaRow(props) {
  return jsxs("p", {
    children: [
      jsx("span", { className: "hg-label", children: props.label }),
      jsx("strong", { "data-placeholder": props.placeholder, children: props.value }),
    ],
  });
}

export function HabitatTab(props = {}) {
  const uiState = props.uiState || UI_STATES.READY;

  return jsxs("section", {
    className: "hg-habitat",
    "data-tab": "habitat",
    children: [
      jsx(StateNotice, { state: uiState }),
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
