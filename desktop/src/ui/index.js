export {
  HermagotchiPane,
  TAB_IDS,
  TAB_LABELS,
  TAB_COMPONENTS,
} from "./pane.js";

export {
  UI_STATES,
  UI_STATE_COPY,
  StateNotice,
  resolveUiState,
} from "./states.js";

export {
  PANE_ID,
  PANE_TITLE,
  createPaneContribution,
  registerHermagotchiPane,
  createDesktopPlugin,
} from "./register.js";

export { HabitatTab, HABITAT_PLACEHOLDER } from "./tabs/HabitatTab.js";
export { BattleTab, CHALLENGE_INBOX_PLACEHOLDER } from "./tabs/BattleTab.js";
export { ShopTab, SHOP_PLACEHOLDER_ITEMS } from "./tabs/ShopTab.js";
export { LeaderboardTab } from "./tabs/LeaderboardTab.js";
export { ChatTab } from "./tabs/ChatTab.js";
export { SettingsTab, SETTINGS_PLACEHOLDER } from "./tabs/SettingsTab.js";
export { CareMeter } from "./components/CareMeter.js";

export { NpcHostBanner } from "./components/NpcHostBanner.js";
export { NPC_HOST_DEFAULTS, NPC_NAMES, npcHostLine } from "./npcLines.js";
export {
  setHostTransport,
  getHostTransport,
  dashboardSdkTransport,
} from "./logic/hostTransport.js";
