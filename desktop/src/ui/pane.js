import { useEffect, useState } from "react";
import { jsx, jsxs } from "react/jsx-runtime";
import { deriveConnectionStatus, resolveConnectionUiState } from "./logic/connection.js";
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

function callMaybe(fn) {
  try {
    const result = fn();
    return result && typeof result.catch === "function"
      ? result.catch(function () {
          return null;
        })
      : Promise.resolve(result);
  } catch (_error) {
    return Promise.resolve(null);
  }
}

function statusEnvelopeFor(api) {
  if (api && typeof api.status === "function") {
    return callMaybe(function () {
      return api.status();
    });
  }
  if (api && typeof api.get === "function") {
    return callMaybe(function () {
      return api.get("/status");
    });
  }
  return Promise.resolve(null);
}

function healthEnvelopeFor(api) {
  if (api && typeof api.health === "function") {
    return callMaybe(function () {
      return api.health();
    });
  }
  if (api && typeof api.get === "function") {
    return callMaybe(function () {
      return api.get("/health");
    });
  }
  return Promise.resolve(null);
}

function pairEnvelopeFor(api) {
  if (api && api.pair && typeof api.pair.poll === "function") {
    return callMaybe(function () {
      return api.pair.poll();
    });
  }
  return Promise.resolve(null);
}

export function HermagotchiPane(props = {}) {
  const initialTab = TAB_IDS.includes(props.initialTab) ? props.initialTab : "habitat";
  const api = props.api;
  const hasApi = Boolean(api && typeof api === "object");
  const fallbackState = props.state || props.uiState || UI_STATES.READY;
  const startTab = useState(initialTab);
  const activeTab = startTab[0];
  const setActiveTab = startTab[1];
  const ActiveTab = TAB_COMPONENTS[activeTab] || HabitatTab;
  const connectionState = useState(null);
  const connection = connectionState[0];
  const setConnection = connectionState[1];

  useEffect(
    function pollConnection() {
      if (!hasApi) {
        return undefined;
      }
      let cancelled = false;
      async function run() {
        const [statusEnvelope, healthEnvelope, pairEnvelope] = await Promise.all([
          statusEnvelopeFor(api),
          healthEnvelopeFor(api),
          pairEnvelopeFor(api),
        ]);
        if (cancelled) {
          return;
        }
        setConnection(
          deriveConnectionStatus({
            statusEnvelope: statusEnvelope,
            healthEnvelope: healthEnvelope,
            pairEnvelope: pairEnvelope,
          })
        );
      }
      run();
      const timer = setInterval(run, 15000);
      return function () {
        cancelled = true;
        clearInterval(timer);
      };
    },
    [api, hasApi]
  );

  const effectiveState = hasApi
    ? connection
      ? resolveConnectionUiState(connection)
      : UI_STATES.READY
    : fallbackState;

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
