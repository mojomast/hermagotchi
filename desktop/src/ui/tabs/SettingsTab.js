import { jsx, jsxs } from "react/jsx-runtime";
import { StateNotice, UI_STATES } from "../states.js";

export const SETTINGS_PLACEHOLDER = Object.freeze([
  { key: "backend", label: "Python backend", value: "Disabled" },
  { key: "network", label: "Multiplayer", value: "Off" },
  { key: "identity", label: "Identity", value: "Not paired" },
  { key: "chat", label: "Chat", value: "Off" },
  { key: "autonomy", label: "Agent autonomy", value: "Off" },
  { key: "service", label: "Multiplayer URL", value: "Not configured" },
]);

function SettingRow(props) {
  const setting = props.setting;
  return jsxs("div", {
    className: "hg-setting",
    "data-setting": setting.key,
    children: [
      jsx("span", { className: "hg-label", children: setting.label }),
      jsx("strong", { children: setting.value }),
    ],
  });
}

export function SettingsTab(props = {}) {
  const uiState = props.uiState || UI_STATES.READY;

  return jsxs("section", {
    className: "hg-settings",
    "data-tab": "settings",
    children: [
      jsx(StateNotice, { state: uiState }),
      jsxs("div", {
        className: "hg-card",
        children: [
          jsx("h3", { children: "Settings" }),
          jsx("p", {
            className: "hg-muted",
            children:
              "Read-only placeholders. A later integration binds real owner toggles and persists changes through the gateway.",
          }),
          jsx("div", {
            className: "hg-settings__list",
            children: SETTINGS_PLACEHOLDER.map((setting) =>
              jsx(SettingRow, { setting }, setting.key)
            ),
          }),
        ],
      }),
      jsxs("div", {
        className: "hg-card",
        children: [
          jsx("h3", { children: "Diagnostics" }),
          jsx("p", {
            className: "hg-muted",
            children: "Version and connection diagnostics appear after backend wiring.",
          }),
        ],
      }),
    ],
  });
}
