import { jsx, jsxs } from "react/jsx-runtime";
import { StateNotice, UI_STATES } from "../states.js";

export function LeaderboardTab(props = {}) {
  const uiState = props.uiState || UI_STATES.READY;

  return jsxs("section", {
    className: "hg-leaderboard",
    "data-tab": "leaderboard",
    children: [
      jsx(StateNotice, { state: uiState }),
      jsxs("div", {
        className: "hg-card",
        children: [
          jsxs("header", {
            className: "hg-card__header",
            children: [
              jsx("h3", { children: "Leaderboard" }),
              jsx("span", { className: "hg-muted", children: "Season not started" }),
            ],
          }),
          jsxs("table", {
            className: "hg-table",
            children: [
              jsx("thead", {
                children: jsxs("tr", {
                  children: [
                    jsx("th", { children: "Rank" }),
                    jsx("th", { children: "Player" }),
                    jsx("th", { children: "Rating" }),
                    jsx("th", { children: "Record" }),
                  ],
                }),
              }),
              jsx("tbody", {
                children: jsx("tr", {
                  children: jsx("td", {
                    colSpan: "4",
                    className: "hg-muted",
                    children: "No ranked matches yet. Play a ranked battle to appear here.",
                  }),
                }),
              }),
            ],
          }),
        ],
      }),
      jsxs("div", {
        className: "hg-card",
        children: [
          jsx("h3", { children: "Your neighborhood" }),
          jsx("p", {
            className: "hg-muted",
            children: "Your nearby ranks appear after the first ranked result is verified.",
          }),
        ],
      }),
    ],
  });
}
