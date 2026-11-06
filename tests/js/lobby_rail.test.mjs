import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

import {
  LOBBY_RAIL_BREAKPOINT,
  LOBBY_RAIL_COLLAPSED_KEY,
  LOBBY_RAIL_WIDTH_KEY,
  LOBBY_RAIL_WIDTH_MIN,
  LOBBY_RAIL_WIDTH_MAX,
  LOBBY_RAIL_WIDTH_DEFAULT,
  clampLobbyRailWidth,
  defaultLobbyRailWidth,
  groupLobbyMessages,
  lobbyRailAutoCollapsed,
  lobbyUnreadCount,
  lobbyUnreadLabel,
  shouldStickLobbyScroll,
} from "../../desktop/src/ui/logic/chat.js";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const UI = path.join(ROOT, "desktop", "src", "ui");
const RAIL = readFileSync(path.join(UI, "components", "LobbyRail.js"), "utf8");
const PANE = readFileSync(path.join(UI, "pane.js"), "utf8");
const STYLES = readFileSync(path.join(UI, "styles.css"), "utf8");

test("lobby rail collapses below the 840px breakpoint", () => {
  assert.equal(LOBBY_RAIL_BREAKPOINT, 840);
  assert.equal(lobbyRailAutoCollapsed(320), true);
  assert.equal(lobbyRailAutoCollapsed(839), true);
  assert.equal(lobbyRailAutoCollapsed(840), false);
  assert.equal(lobbyRailAutoCollapsed(1280), false);
  assert.equal(lobbyRailAutoCollapsed(undefined), false);
});

test("lobby unread helpers prefer the server count and bound the badge", () => {
  assert.equal(
    lobbyUnreadCount({
      ok: true,
      data: {
        unread_count: 4,
        items: [{ id: "n1", unread: true, body: "hi" }],
      },
    }),
    4
  );
  assert.equal(
    lobbyUnreadCount({
      items: [
        { id: "n1", unread: true, body: "hi" },
        { id: "n2", unread: true, body: "yo" },
      ],
    }),
    2
  );
  assert.equal(lobbyUnreadCount(null), 0);
  assert.equal(lobbyUnreadLabel(0), "");
  assert.equal(lobbyUnreadLabel(7), "7");
  assert.equal(lobbyUnreadLabel(120), "99+");
  assert.equal(lobbyUnreadLabel(-1), "");
});

test("LobbyRail owns messages, taunt bubbles, composer and reason notices", () => {
  assert.match(RAIL, /export function LobbyRail/);
  for (const className of [
    "hg-lobby-rail",
    "hg-lobby-rail--collapsed",
    "hg-lobby-rail__header",
    "hg-lobby-rail__toggle",
    "hg-lobby-rail__badge",
    "hg-lobby-rail__messages",
    "hg-lobby-rail__taunt",
    "hg-lobby-rail__compose",
    "hg-lobby-rail__notice",
    "hg-lobby-rail__menu",
    "hg-lobby-rail__host",
    "hg-lobby-rail__resize",
    "hg-lobby-rail__new",
  ]) {
    assert.ok(RAIL.includes(className), `missing ${className}`);
  }
  for (const helper of [
    "CHAT_MESSAGES_PATH",
    "CHAT_INBOX_PATH",
    "normalizeMessages",
    "mergeMessages",
    "messageFromEnvelope",
    "validateChatDraft",
    "chatMessagePayload",
    "chatNoticeFromEnvelope",
    "isTauntMessage",
    "tauntSummary",
    "shouldShowChatStub",
    "groupLobbyMessages",
    "shouldStickLobbyScroll",
  ]) {
    assert.ok(RAIL.includes(helper), `LobbyRail must reuse chat helper ${helper}`);
  }
  assert.ok(RAIL.includes('"data-rail": "lobby"') || RAIL.includes('"data-rail": "chat"'));
  assert.ok(RAIL.includes("aria-expanded"));
  assert.ok(RAIL.includes("data-lobby-toggle"));
  assert.ok(RAIL.includes('"LOBBY"') || RAIL.includes("'LOBBY'"));
  assert.ok(RAIL.includes("hg-lobby-rail__toggle--collapsed"));
  assert.ok(RAIL.includes("Chat is off by default"));
  assert.doesNotMatch(RAIL, /dangerouslySetInnerHTML/);
  assert.doesNotMatch(RAIL, /innerHTML/);
});

test("pane mounts the lobby rail beside every tab and collapses it", () => {
  assert.match(PANE, /from "\.\/components\/LobbyRail\.js"/);
  assert.ok(PANE.includes("hg-pane__layout"), "pane needs a main + rail layout");
  assert.ok(PANE.includes("hg-pane__layout--rail-collapsed"));
  assert.ok(PANE.includes("hg-pane__main"));
  assert.ok(PANE.includes("LobbyRail"));
  assert.ok(PANE.includes("lobbyRailAutoCollapsed"));
  assert.ok(PANE.includes("matchMedia"));
  assert.ok(PANE.includes("839") || PANE.includes("LOBBY_RAIL_BREAKPOINT"));
  assert.ok(PANE.includes("onToggle"));
  assert.ok(PANE.includes("LOBBY_RAIL_COLLAPSED_KEY"));
  assert.ok(PANE.includes("localStorage"));
  assert.ok(PANE.includes("persistRailCollapsed"));
  assert.ok(PANE.includes("LOBBY_RAIL_WIDTH_KEY"));
  assert.ok(PANE.includes("changeRailWidth"));
  assert.ok(PANE.includes("--hg-lobby-rail-width"));
});

test("stylesheet lays out the rail, badge and narrow toggle breakpoint", () => {
  for (const selector of [
    ".hg-pane__layout",
    ".hg-pane__layout--rail-collapsed",
    ".hg-pane__main",
    ".hg-lobby-rail",
    ".hg-lobby-rail--collapsed",
    ".hg-lobby-rail__badge",
    ".hg-lobby-rail__toggle",
    ".hg-lobby-rail__compose",
  ]) {
    assert.ok(STYLES.includes(selector), `missing ${selector}`);
  }
  assert.match(STYLES, /@media \(max-width: 839px\)/);
  assert.ok(STYLES.includes("writing-mode"), "collapsed LOBBY label stays visible");
  assert.ok(STYLES.includes("hg-lobby-rail__toggle--collapsed"));
  assert.ok(STYLES.includes("100vh"), "rail uses viewport height");
  assert.ok(STYLES.includes("--hg-lobby-rail-width"));
  assert.ok(STYLES.includes("hg-lobby-rail__menu"));
  assert.ok(STYLES.includes("hg-lobby-rail__host"));
});

test("lobby collapse preference key is stable", () => {
  assert.equal(LOBBY_RAIL_COLLAPSED_KEY, "hermagotchi.lobbyRail.collapsed");
});

test("groupLobbyMessages skips repeated author headers", () => {
  const grouped = groupLobbyMessages([
    { id: "1", account_id: "a", body: "one", author_name: "Ada · Bit" },
    { id: "2", account_id: "a", body: "two", author_name: "Ada · Bit" },
    { id: "3", account_id: "b", body: "three", author_name: "Bo · Fox" },
  ]);
  assert.equal(grouped.length, 3);
  assert.equal(grouped[0].showHeader, true);
  assert.equal(grouped[1].showHeader, false);
  assert.equal(grouped[1].grouped, true);
  assert.equal(grouped[2].showHeader, true);
});

test("shouldStickLobbyScroll is true near the bottom", () => {
  assert.equal(shouldStickLobbyScroll(null), true);
  assert.equal(
    shouldStickLobbyScroll({ scrollHeight: 500, scrollTop: 440, clientHeight: 50 }),
    true
  );
  assert.equal(
    shouldStickLobbyScroll({ scrollHeight: 500, scrollTop: 100, clientHeight: 50 }),
    false
  );
});

test("lobby rail width clamps and widens on large panes", () => {
  assert.equal(LOBBY_RAIL_WIDTH_DEFAULT, 320);
  assert.equal(defaultLobbyRailWidth(1400), 380);
  assert.equal(defaultLobbyRailWidth(900), 320);
  assert.equal(clampLobbyRailWidth(100, 1400), LOBBY_RAIL_WIDTH_MIN);
  assert.equal(clampLobbyRailWidth(999, 1400), LOBBY_RAIL_WIDTH_MAX);
  assert.equal(LOBBY_RAIL_WIDTH_KEY, "hermagotchi.lobbyRail.width");
});
