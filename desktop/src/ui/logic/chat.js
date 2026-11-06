/** Pure chat helpers shared by the Desktop Chat tab and its tests. */

import { npcHostLine } from "../npcLines.js";

export const CHAT_CHANNEL_ID = "lobby";
export const CHAT_MESSAGES_PATH = "/chat/channels/lobby/messages";
export const CHAT_BLOCKS_PATH = "/blocks";
export const CHAT_REPORT_PATH = "/moderation/report";
export const CHAT_MESSAGE_MAX_CHARS = 400;
export const CHAT_REPORT_REASON = "Reported from the Hermagotchi Desktop lobby.";

const TRUE_FLAGS = new Set(["1", "true", "yes", "on"]);

function flagValue(value) {
  if (value === true || value === 1) return true;
  if (value === false || value === 0 || value === null || value === undefined) {
    return false;
  }
  return TRUE_FLAGS.has(String(value).trim().toLowerCase());
}

/**
 * Return whether the owner enabled chat.
 *
 * The policy/status payload uses ``chat_enabled``; accepted aliases keep the
 * Desktop pane compatible with the host's camelCase props.
 */
export function isChatEnabled(props = {}) {
  const source = props || {};
  const candidates = [
    source.chatEnabled,
    source.chat_enabled,
    source.features && source.features.chat,
    source.features && source.features.chat_enabled,
    source.policy && source.policy.chat_enabled,
    source.permissions && source.permissions.chat,
    source.status && source.status.policy && source.status.policy.chat_enabled,
    source.status &&
      source.status.me &&
      source.status.me.policy &&
      source.status.me.policy.chat_enabled,
  ];
  for (const candidate of candidates) {
    if (candidate !== undefined && candidate !== null) {
      return flagValue(candidate);
    }
  }
  return false;
}

export function shouldShowChatStub(props = {}) {
  const source = props || {};
  return !source.api || !isChatEnabled(source);
}

function normalText(value, fallback = "") {
  return typeof value === "string" ? value : fallback;
}

function normalNullableText(value) {
  return typeof value === "string" ? value : null;
}

/** Coerce one server chat row into the display shape without interpreting it. */
export function normalizeMessage(item) {
  if (!item || typeof item !== "object") return null;
  const id = normalText(item.id);
  if (!id) return null;
  return {
    id,
    channel_id: normalText(item.channel_id, CHAT_CHANNEL_ID),
    account_id: normalText(item.account_id),
    actor_mode: item.actor_mode === "agent" ? "agent" : "human",
    body: normalText(item.body),
    created_at: normalText(item.created_at),
    deleted_at: normalNullableText(item.deleted_at),
  };
}

/** Read the message list from either a bridge envelope or decoded data. */
export function normalizeMessages(envelopeOrData) {
  if (!envelopeOrData || typeof envelopeOrData !== "object") return [];
  const payload =
    envelopeOrData.data && typeof envelopeOrData.data === "object"
      ? envelopeOrData.data
      : envelopeOrData;
  const rows = Array.isArray(payload.messages) ? payload.messages : [];
  return rows.map(normalizeMessage).filter(Boolean);
}

/** Read the message returned by a send envelope. */
export function messageFromEnvelope(envelope) {
  if (!envelope || envelope.ok !== true || !envelope.data) return null;
  return normalizeMessage(envelope.data.message);
}

/** Merge messages by id and sort oldest first. */
export function mergeMessages(existing, incoming) {
  const byId = new Map();
  for (const message of [...(existing || []), ...(incoming || [])]) {
    const normalized = normalizeMessage(message);
    if (normalized) byId.set(normalized.id, normalized);
  }
  return [...byId.values()].sort(function (left, right) {
    if (left.created_at === right.created_at) {
      return left.id < right.id ? -1 : left.id > right.id ? 1 : 0;
    }
    return left.created_at < right.created_at ? -1 : 1;
  });
}

/** Validate a composer draft before it is sent to the bridge. */
export function validateChatDraft(draft) {
  const value = typeof draft === "string" ? draft.trim() : "";
  if (!value) {
    return { ok: false, error: "Message cannot be empty." };
  }
  if (value.length > CHAT_MESSAGE_MAX_CHARS) {
    return {
      ok: false,
      error: `Message cannot exceed ${CHAT_MESSAGE_MAX_CHARS} characters.`,
    };
  }
  return { ok: true, value };
}

/** Plain text is always sent as display data; the server owns sanitization. */
export function chatMessagePayload(value) {
  return { body: String(value || ""), actor_mode: "human" };
}

const MODERATION_CODES = new Set([
  "blocked",
  "blocked_interaction",
  "forbidden",
  "rate_limited",
  "empty_message",
  "message_too_long",
  "validation_error",
]);

const AUTH_CODES = new Set(["auth_missing", "unauthorized", "expired", "disabled"]);

function cleanCode(value) {
  return typeof value === "string" ? value.slice(0, 64) : "";
}

function moderationLine(code, retryAfterS) {
  const base = npcHostLine("chat.moderation");
  if (code === "rate_limited") {
    const seconds = Number(retryAfterS);
    return seconds > 0
      ? `Easy there. Try again in ${Math.ceil(seconds)}s.`
      : "Easy there. Slow down before sending again.";
  }
  if (code === "blocked" || code === "blocked_interaction") {
    return "That message was blocked. Stay calm. Stay open.";
  }
  if (
    code === "empty_message" ||
    code === "message_too_long" ||
    code === "validation_error"
  ) {
    return "That message was rejected. Keep it short and kind.";
  }
  if (code === "auth_missing" || code === "unauthorized" || code === "expired") {
    return "Pair this device before sending lobby messages.";
  }
  if (code === "offline" || code === "unavailable" || code === "network_disabled") {
    return "The lobby is unavailable right now. Try again later.";
  }
  return base ? base.line : "The message was not sent.";
}

/** Turn a failed bridge envelope into a display-only moderation notice. */
export function chatNoticeFromEnvelope(envelope) {
  if (envelope && envelope.ok === true) return null;
  const source = envelope && typeof envelope === "object" ? envelope : {};
  const status = cleanCode(source.status) || "unavailable";
  const error = source.error && typeof source.error === "object" ? source.error : {};
  const code = cleanCode(error.code) || cleanCode(source.status) || "unavailable";
  const retryAfterS = Number(error.retry_after_s);
  const message = normalText(error.message).slice(0, 240);
  const kind = AUTH_CODES.has(code)
    ? "auth"
    : MODERATION_CODES.has(code)
      ? "moderation"
      : "error";
  return {
    kind,
    status,
    code,
    retryAfterS: Number.isFinite(retryAfterS) && retryAfterS > 0 ? retryAfterS : null,
    message,
    hostLine: moderationLine(code, retryAfterS),
  };
}

/** Build a notice for a successful block or report. */
export function chatActionNotice(kind) {
  if (kind === "blocked") {
    return {
      kind: "moderation",
      status: "ok",
      code: "blocked",
      retryAfterS: null,
      message: "That account is blocked.",
      hostLine: "Blocked. Their messages are hidden now.",
    };
  }
  if (kind === "reported") {
    return {
      kind: "moderation",
      status: "ok",
      code: "reported",
      retryAfterS: null,
      message: "The report is queued for review.",
      hostLine: "Report sent. A moderator will review it.",
    };
  }
  return null;
}

/** Nous Girl hosts every moderation notice; the line never renders markup. */
export function chatModerationHost(notice) {
  const base = npcHostLine("chat.moderation");
  if (!base) return null;
  const line = notice && typeof notice.hostLine === "string" && notice.hostLine
    ? notice.hostLine
    : base.line;
  return {
    id: base.id,
    name: base.name,
    context: base.context,
    line,
    displayOnly: true,
  };
}

/** Provider for the normal lobby banner. */
export function chatHost() {
  return npcHostLine("chat");
}
