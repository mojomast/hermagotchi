import { jsx, jsxs } from "react/jsx-runtime";
import { StateNotice, UI_STATES } from "../states.js";
import { NpcHostBanner } from "../components/NpcHostBanner.js";

export const CHALLENGE_INBOX_PLACEHOLDER = "No pending challenges.";

export function BattleTab(props = {}) {
  const uiState = props.uiState || UI_STATES.READY;

  return jsxs("section", {
    className: "hg-battle",
    "data-tab": "battle",
    children: [
      jsx(StateNotice, { state: uiState }),
      jsx(NpcHostBanner, { surface: "battle" }),
      jsxs("div", {
        className: "hg-card",
        children: [
          jsx("h3", { children: "Challenge inbox" }),
          jsx("p", {
            className: "hg-muted",
            "data-placeholder": "challenge-inbox",
            children: CHALLENGE_INBOX_PLACEHOLDER,
          }),
          jsx("p", {
            className: "hg-muted",
            children: "Accepted matches and replays appear here after multiplayer is enabled.",
          }),
        ],
      }),
      jsxs("div", {
        className: "hg-card",
        children: [
          jsx("h3", { children: "Practice" }),
          jsx("p", {
            className: "hg-muted",
            children: "Practice battles stay local and never change rank or Bits.",
          }),
          jsx("button", {
            type: "button",
            disabled: true,
            children: "Practice battle (disabled in stub)",
          }),
        ],
      }),
    ],
  });
}
