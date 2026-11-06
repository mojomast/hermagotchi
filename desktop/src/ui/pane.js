import { useEffect, useState } from "react";
import { jsx, jsxs } from "react/jsx-runtime";
import { LobbyRail } from "./components/LobbyRail.js";
import { deriveConnectionStatus, resolveConnectionUiState } from "./logic/connection.js";
import {
  LOBBY_RAIL_COLLAPSED_KEY,
  LOBBY_RAIL_WIDTH_KEY,
  clampLobbyRailWidth,
  defaultLobbyRailWidth,
  lobbyRailAutoCollapsed,
} from "./logic/chat.js";
import { BattleTab } from "./tabs/BattleTab.js";
import { ChatTab } from "./tabs/ChatTab.js";
import { HabitatTab } from "./tabs/HabitatTab.js";
import { LeaderboardTab } from "./tabs/LeaderboardTab.js";
import { SettingsTab } from "./tabs/SettingsTab.js";
import { ShopTab } from "./tabs/ShopTab.js";
import { StateNotice, UI_STATES } from "./states.js";
import { WORDMARK_HEIGHT, WORDMARK_SRC, WORDMARK_SRC_2X, WORDMARK_WIDTH } from "./wordmark.js";

export const TAB_IDS = Object.freeze(["habitat", "battle", "shop", "leaderboard", "chat", "settings"]);

export const TAB_LABELS = Object.freeze({
  habitat: "Habitat",
  battle: "Battle",
  shop: "Shop",
  leaderboard: "Leaderboard",
  chat: "Social",
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

function readStoredRailCollapsed() {
  if (typeof window === "undefined" || !window.localStorage) {
    return null;
  }
  try {
    const raw = window.localStorage.getItem(LOBBY_RAIL_COLLAPSED_KEY);
    if (raw === "1" || raw === "true") return true;
    if (raw === "0" || raw === "false") return false;
  } catch (_err) {
    /* ignore quota / private mode */
  }
  return null;
}

function persistRailCollapsed(collapsed) {
  if (typeof window === "undefined" || !window.localStorage) {
    return;
  }
  try {
    window.localStorage.setItem(
      LOBBY_RAIL_COLLAPSED_KEY,
      collapsed ? "1" : "0"
    );
  } catch (_err) {
    /* ignore */
  }
}

function readStoredRailWidth() {
  if (typeof window === "undefined" || !window.localStorage) {
    return null;
  }
  try {
    const raw = window.localStorage.getItem(LOBBY_RAIL_WIDTH_KEY);
    if (raw == null || raw === "") return null;
    const value = Number(raw);
    return Number.isFinite(value) ? value : null;
  } catch (_err) {
    return null;
  }
}

function persistRailWidth(width) {
  if (typeof window === "undefined" || !window.localStorage) {
    return;
  }
  try {
    window.localStorage.setItem(LOBBY_RAIL_WIDTH_KEY, String(width));
  } catch (_err) {
    /* ignore */
  }
}

function initialRailWidth() {
  const viewport =
    typeof window !== "undefined" && typeof window.innerWidth === "number"
      ? window.innerWidth
      : 1280;
  const stored = readStoredRailWidth();
  if (stored != null) return clampLobbyRailWidth(stored, viewport);
  return defaultLobbyRailWidth(viewport);
}

function initialRailCollapsed() {
  const stored = readStoredRailCollapsed();
  if (stored !== null) return stored;
  if (typeof window === "undefined" || typeof window.innerWidth !== "number") {
    return false;
  }
  return lobbyRailAutoCollapsed(window.innerWidth);
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
  const railState = useState(initialRailCollapsed);
  const railCollapsed = railState[0];
  const setRailCollapsed = railState[1];
  const widthState = useState(initialRailWidth);
  const railWidth = widthState[0];
  const setRailWidth = widthState[1];

  function changeRailWidth(next) {
    const viewport =
      typeof window !== "undefined" && typeof window.innerWidth === "number"
        ? window.innerWidth
        : 1280;
    const clamped = clampLobbyRailWidth(next, viewport);
    setRailWidth(clamped);
    persistRailWidth(clamped);
  }

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

  useEffect(
    function syncLobbyRail() {
      if (
        typeof window === "undefined" ||
        typeof window.matchMedia !== "function"
      ) {
        return undefined;
      }
      const query = window.matchMedia("(max-width: 839px)");
      function sync(event) {
        if (event && event.matches) {
          setRailCollapsed(true);
        }
      }
      sync(query);
      if (typeof query.addEventListener === "function") {
        query.addEventListener("change", sync);
        return function () {
          query.removeEventListener("change", sync);
        };
      }
      if (typeof query.addListener === "function") {
        query.addListener(sync);
        return function () {
          query.removeListener(sync);
        };
      }
      return undefined;
    },
    []
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

  function toggleLobbyRail() {
    setRailCollapsed(function (current) {
      const next = !current;
      persistRailCollapsed(next);
      return next;
    });
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
          jsx("h2", {
            className: "hg-pane__title",
            children: jsx("img", {
              className: "hg-pane__wordmark",
              src: WORDMARK_SRC,
              srcSet: `${WORDMARK_SRC} 1x, ${WORDMARK_SRC_2X} 2x`,
              width: WORDMARK_WIDTH,
              height: WORDMARK_HEIGHT,
              alt: "Hermagotchi",
              draggable: false,
            }),
          }),
          jsx(StateNotice, { state: effectiveState }),
        ],
      }),
      jsx("nav", {
        className: "hg-tabs",
        role: "tablist",
        "aria-label": "Hermagotchi sections",
        children: tabButtons,
      }),
      jsxs("div", {
        className: railCollapsed
          ? "hg-pane__layout hg-pane__layout--rail-collapsed"
          : "hg-pane__layout",
        style: railCollapsed
          ? undefined
          : { ["--hg-lobby-rail-width"]: railWidth + "px" },
        children: [
          jsx("main", {
            className: "hg-pane__body hg-pane__main",
            role: "tabpanel",
            "aria-label": TAB_LABELS[activeTab],
            children: jsx(ActiveTab, Object.assign({}, props, { uiState: effectiveState, state: effectiveState, initialTab: undefined, onTabChange: undefined })),
          }),
          jsx(LobbyRail, Object.assign({}, props, {
            api: api,
            uiState: effectiveState,
            state: effectiveState,
            collapsed: railCollapsed,
            onToggle: toggleLobbyRail,
            width: railWidth,
            onWidthChange: changeRailWidth,
            initialTab: undefined,
            onTabChange: undefined,
          })),
        ],
      }),
    ],
  });
}
