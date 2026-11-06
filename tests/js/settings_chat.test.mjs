import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

import {
  CHAT_POLICY_PATH,
  CHAT_SETTINGS_PATH,
  chatEnabledFromEnvelope,
  chatSettingsPayload,
  isChatEnabled,
  updateChatSetting,
} from "../../desktop/src/ui/logic/chat.js";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const SETTINGS = readFileSync(
  path.join(ROOT, "desktop/src/ui/tabs/SettingsTab.js"),
  "utf8"
);
const CHAT = readFileSync(
  path.join(ROOT, "desktop/src/ui/tabs/ChatTab.js"),
  "utf8"
);

test("settings toggle payload uses the canonical chat_enabled key", () => {
  assert.deepEqual(chatSettingsPayload(true), { chat_enabled: true });
  assert.deepEqual(chatSettingsPayload(false), { chat_enabled: false });
  assert.deepEqual(chatSettingsPayload("yes"), { chat_enabled: false });
});

test("updateChatSetting prefers PATCH on the bridge chat-settings route", async () => {
  const calls = [];
  const api = {
    patch(path, body) {
      calls.push({ method: "patch", path, body });
      return Promise.resolve({
        ok: true,
        status: "ok",
        data: { chat_enabled: true },
      });
    },
    post() {
      throw new Error("POST must not be used when PATCH exists");
    },
  };

  const envelope = await updateChatSetting(api, true);
  assert.equal(envelope.ok, true);
  assert.deepEqual(calls, [
    {
      method: "patch",
      path: CHAT_SETTINGS_PATH,
      body: { chat_enabled: true },
    },
  ]);
  assert.equal(CHAT_SETTINGS_PATH, "/me/chat-settings");
  assert.equal(CHAT_POLICY_PATH, "/me/policy");
});

test("updateChatSetting falls back to POST when the bridge lacks PATCH", async () => {
  const calls = [];
  const api = {
    post(path, body) {
      calls.push({ method: "post", path, body });
      return Promise.resolve({ ok: true, status: "ok", data: {} });
    },
  };

  await updateChatSetting(api, false);
  assert.deepEqual(calls, [
    {
      method: "post",
      path: CHAT_SETTINGS_PATH,
      body: { chat_enabled: false },
    },
  ]);
});

test("updateChatSetting reports offline without a bridge", async () => {
  const envelope = await updateChatSetting(null, true);
  assert.equal(envelope.ok, false);
  assert.equal(envelope.status, "offline");
});

test("chatEnabledFromEnvelope confirms nested policy values", () => {
  assert.equal(
    chatEnabledFromEnvelope(
      { ok: true, data: { policy: { chat_enabled: true } } },
      false
    ),
    true
  );
  assert.equal(
    chatEnabledFromEnvelope({ ok: true, data: { chat_enabled: "on" } }, false),
    true
  );
  assert.equal(
    chatEnabledFromEnvelope(
      { ok: true, data: { me: { policy: { chat_enabled: false } } } },
      true
    ),
    false
  );
  assert.equal(
    chatEnabledFromEnvelope({ ok: false, error: { code: "offline" } }, true),
    true
  );
  assert.equal(isChatEnabled({ chatEnabled: true }), true);
});

test("SettingsTab replaces the placeholder chat row with a real toggle", () => {
  assert.ok(SETTINGS.includes("updateChatSetting"));
  assert.ok(SETTINGS.includes("CHAT_SETTINGS_PATH"));
  assert.ok(SETTINGS.includes("chatEnabledFromEnvelope"));
  assert.ok(SETTINGS.includes('"data-chat-toggle": "true"'));
  assert.ok(SETTINGS.includes("Agent chat"));
  assert.ok(SETTINGS.includes("onChatEnabledChange"));
  assert.ok(SETTINGS.includes("data-chat-setting-notice"));
  assert.ok(SETTINGS.includes("SETTINGS_PLACEHOLDER"));
  assert.ok(SETTINGS.includes("Multiplayer URL"));
  assert.ok(SETTINGS.includes("Not paired"));
  assert.doesNotMatch(SETTINGS, /\bfetch\s*\(/);
});

test("Chat stays stubbed while the Agent-chat toggle is off", () => {
  assert.ok(CHAT.includes("Chat is off by default"));
  assert.ok(CHAT.includes("Chat is disabled in this stub"));
  assert.ok(CHAT.includes("disabled: true"));
  assert.ok(CHAT.includes("isChatEnabled"));
  assert.doesNotMatch(CHAT, /\bfetch\s*\(/);
});
