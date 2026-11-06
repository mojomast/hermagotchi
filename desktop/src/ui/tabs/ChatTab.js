import { jsx, jsxs } from "react/jsx-runtime";
import { StateNotice, UI_STATES } from "../states.js";
import { NpcHostBanner } from "../components/NpcHostBanner.js";

export function ChatTab(props = {}) {
  const uiState = props.uiState || UI_STATES.NETWORK_OFF;

  return jsxs("section", {
    className: "hg-chat",
    "data-tab": "chat",
    children: [
      jsx(StateNotice, { state: uiState }),
      jsx(NpcHostBanner, { surface: "chat" }),
      jsxs("div", {
        className: "hg-card",
        children: [
          jsx("h3", { children: "Chat is off by default" }),
          jsx("p", {
            className: "hg-muted",
            children:
              "The lobby and challenge threads stay unavailable until the owner enables chat and the device is paired.",
          }),
          jsxs("label", {
            className: "hg-field",
            children: [
              jsx("span", { children: "Message" }),
              jsx("textarea", {
                disabled: true,
                rows: "3",
                placeholder: "Chat is disabled in this stub",
              }),
            ],
          }),
          jsxs("div", {
            className: "hg-actions",
            children: [
              jsx("button", { type: "button", disabled: true, children: "Send (disabled)" }),
              jsx("button", { type: "button", disabled: true, children: "Mute" }),
              jsx("button", { type: "button", disabled: true, children: "Block" }),
              jsx("button", { type: "button", disabled: true, children: "Report" }),
            ],
          }),
        ],
      }),
    ],
  });
}
