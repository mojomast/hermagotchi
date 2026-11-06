import { useState } from "react";
import { jsx, jsxs } from "react/jsx-runtime";
import { BattleTab } from "./tabs/BattleTab.js";
import { ChatTab } from "./tabs/ChatTab.js";
import { HabitatTab } from "./tabs/HabitatTab.js";
import { LeaderboardTab } from "./tabs/LeaderboardTab.js";
import { SettingsTab } from "./tabs/SettingsTab.js";
import { ShopTab } from "./tabs/ShopTab.js";
import { StateNotice, UI_STATES } from "./states.js";

export const TAB_IDS = Object.freeze(["habitat", "battle", "shop", "leaderboard", "chat", "settings"]);

export const TAB_LABELS = Object.freeze({
  habitat: "Habitat",
  battle: "Battle",
  shop: "Shop",
  leaderboard: "Leaderboard",
  chat: "Chat",
  settings: "Settings",
});

export const TAB_COMPONENTS = Object.freeze({
  habitat: HabitatTab,
  battle: BattleTab,
  shop: ShopTab,
  leaderboard: LeaderboardTab,
  chat: ChatTab,
  settings: SettingsTab,
});

export function HermagotchiPane(props = {}) {
  const initialTab = TAB_IDS.includes(props.initialTab) ? props.initialTab : "habitat";
  const effectiveState = props.state || props.uiState || UI_STATES.READY;
  const startTab = useState(initialTab);
  const activeTab = startTab[0];
  const setActiveTab = startTab[1];
  const ActiveTab = TAB_COMPONENTS[activeTab] || HabitatTab;

  function selectTab(nextTab) {
    setActiveTab(nextTab);
    if (typeof props.onTabChange === "function") {
      props.onTabChange(nextTab);
    }
  }

  const tabButtons = TAB_IDS.map((tabId) =>
    jsx(
      "button",
      {
        type: "button",
        role: "tab",
        "aria-selected": activeTab === tabId ? "true" : "false",
        className: activeTab === tabId ? "hg-tab hg-tab--active" : "hg-tab",
        onClick: function () {
          selectTab(tabId);
        },
        children: TAB_LABELS[tabId],
      },
      tabId
    )
  );

  return jsxs("div", {
    className: "hg-pane",
    "data-plugin": "hermagotchi",
    children: [
      jsxs("header", {
        className: "hg-pane__header",
        children: [
          jsx("h2", { children: "Hermagotchi" }),
          jsx(StateNotice, { state: effectiveState }),
        ],
      }),
      jsx("nav", {
        className: "hg-tabs",
        role: "tablist",
        "aria-label": "Hermagotchi sections",
        children: tabButtons,
      }),
      jsx("main", {
        className: "hg-pane__body",
        role: "tabpanel",
        "aria-label": TAB_LABELS[activeTab],
        children: jsx(ActiveTab, Object.assign({}, props, { uiState: effectiveState, state: effectiveState, initialTab: undefined, onTabChange: undefined })),
      }),
    ],
  });
}
