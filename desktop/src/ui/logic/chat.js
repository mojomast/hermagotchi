/** Pure chat helpers shared by the Desktop Chat tab and its tests. */

import { npcHostLine } from "../npcLines.js";

export const CHAT_CHANNEL_ID = "lobby";
export const CHAT_MESSAGES_PATH = "/chat/channels/lobby/messages";
export const CHAT_BLOCKS_PATH = "/blocks";
export const CHAT_REPORT_PATH = "/moderation/report";
export const CHAT_INBOX_PATH = "/chat/inbox";
export const CHAT_INBOX_READ_PATH = "/chat/inbox/read";
export const CHAT_TAUNTS_PATH = "/chat/taunts";
export const CHAT_SETTINGS_PATH = "/me/chat-settings";
export const CHAT_POLICY_PATH = "/me/policy";
export const CHAT_MESSAGE_MAX_CHARS = 400;
export const CHAT_TAUNT_MAX_CHARS = 90;
export const CHAT_DM_TARGET_MAX_CHARS = 64;
export const CHAT_REPORT_REASON = "Reported from the Hermagotchi Desktop lobby.";
export const LOBBY_RAIL_BREAKPOINT = 840;
export const LOBBY_RAIL_COLLAPSED_KEY = "hermagotchi.lobbyRail.collapsed";


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


/** Build a human label like "Handle · Pet" without leaking raw UUIDs. */
export function formatPlayerLabel(parts = {}) {
  const handle = normalText(
    parts.handle || parts.public_handle || parts.publicHandle || parts.author_handle
  );
  const pet = normalText(
    parts.pet || parts.pet_name || parts.petName || parts.author_pet_name
  );
  const explicit = normalText(
    parts.display || parts.display_name || parts.displayName || parts.author_name || parts.peer_name
  );
  if (explicit) return explicit;
  if (handle && pet) return handle + " · " + pet;
  if (handle) return handle;
  if (pet) return pet;
  return normalText(parts.fallback, "Player");
}

/** Prefer server author_name; fall back to Player/Agent without IDs. */
export function displayActorLabel(message = {}) {
  const named = formatPlayerLabel({
    display: message.author_name,
    handle: message.author_handle,
    pet: message.author_pet_name,
  });
  if (named && named !== "Player") return named;
  return message.actor_mode === "agent" ? "Agent" : "Player";
}

function _parseIsoMs(value) {
  if (!value || typeof value !== "string") return null;
  const text = value.trim();
  if (!text) return null;
  const normalized = text.endsWith("Z") || /[+-]\d\d:\d\d$/.test(text)
    ? text
    : text + "Z";
  const ms = Date.parse(normalized);
  return Number.isFinite(ms) ? ms : null;
}

/** Relative clock for chat rows; full ISO stays available for tooltips. */
export function formatRelativeTime(iso, nowMs = Date.now()) {
  const ms = _parseIsoMs(iso);
  if (ms == null) return "";
  const delta = Math.max(0, nowMs - ms);
  const sec = Math.floor(delta / 1000);
  if (sec < 45) return "now";
  const min = Math.floor(sec / 60);
  if (min < 60) return min + "m ago";
  const hr = Math.floor(min / 60);
  if (hr < 24) return hr + "h ago";
  try {
    return new Date(ms).toLocaleString("en-US", {
      month: "short",
      day: "numeric",
    });
  } catch (_err) {
    return iso;
  }
}

/** Coerce one server chat row into the display shape without interpreting it. */
export function normalizeMessage(item) {
  if (!item || typeof item !== "object") return null;
  const id = normalText(item.id);
  if (!id) return null;
  const matchContext = normalizeMatchContext(item.match_context || item.matchContext);
  return {
    id,
    channel_id: normalText(item.channel_id, CHAT_CHANNEL_ID),
    account_id: normalText(item.account_id),
    actor_mode: item.actor_mode === "agent" ? "agent" : "human",
    body: normalText(item.body),
    kind: normalText(item.kind),
    phase: normalNullableText(item.phase),
    match_context: matchContext,
    created_at: normalText(item.created_at),
    deleted_at: normalNullableText(item.deleted_at),
    author_name: normalNullableText(item.author_name || item.authorName),
    author_handle: normalNullableText(item.author_handle || item.authorHandle),
    author_pet_name: normalNullableText(
      item.author_pet_name || item.authorPetName
    ),
    peer_name: normalNullableText(item.peer_name || item.peerName),
    peer_id: normalNullableText(item.peer_id || item.peerId),
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

/** Validate an optional direct-message target (player or pet name). */
export function validateDmTarget(target) {
  const value = typeof target === "string" ? target.trim() : "";
  if (!value) return { ok: true, value: "" };
  if (value.length > CHAT_DM_TARGET_MAX_CHARS) {
    return {
      ok: false,
      error: `DM target cannot exceed ${CHAT_DM_TARGET_MAX_CHARS} characters.`,
    };
  }
  return { ok: true, value };
}

/** Plain text is always sent as display data; the server owns sanitization. */
export function chatMessagePayload(value, target) {
  const payload = { body: String(value || ""), actor_mode: "human" };
  const checked = validateDmTarget(target);
  if (checked.ok && checked.value) {
    payload.dm_target = checked.value;
  }
  return payload;
}

/** Validate a short taunt draft before it is sent to the bridge. */
export function validateTauntDraft(draft) {
  const value = typeof draft === "string" ? draft.trim() : "";
  if (!value) {
    return { ok: false, error: "Taunt cannot be empty." };
  }
  if (value.length > CHAT_TAUNT_MAX_CHARS) {
    return {
      ok: false,
      error: `Taunt cannot exceed ${CHAT_TAUNT_MAX_CHARS} characters.`,
    };
  }
  return { ok: true, value };
}

function normalizeMatchContext(source) {
  if (!source || typeof source !== "object") return null;
  const hp = source.hp || source.final_hp || source.finalHp || null;
  return {
    match_id: normalNullableText(source.match_id || source.matchId),
    winner: normalNullableText(source.winner),
    winner_name: normalNullableText(source.winner_name || source.winnerName),
    hp: hp && typeof hp === "object" ? { ...hp } : null,
    rounds:
      source.rounds === undefined || source.rounds === null
        ? null
        : Number(source.rounds) || 0,
  };
}

function formatHp(hp) {
  if (!hp || typeof hp !== "object") return "";
  const a = Number(hp.a);
  const b = Number(hp.b);
  if (Number.isFinite(a) && Number.isFinite(b)) return `${a}-${b}`;
  return "";
}

/** Short display-only callout for a taunt's match summary. */
export function tauntSummary(matchContext) {
  const context = normalizeMatchContext(matchContext);
  if (!context) return "";
  const winner =
    context.winner_name ||
    (context.winner ? `Side ${context.winner}` : "Draw");
  const hp = formatHp(context.hp);
  return "Winner: " + winner + (hp ? " · HP " + hp : "");
}

/** A taunt bubble is any message tagged as a taunt or carrying match context. */
export function isTauntMessage(message) {
  if (!message || typeof message !== "object") return false;
  return (
    message.kind === "taunt" ||
    message.kind === "match_context" ||
    Boolean(message.match_context)
  );
}

/** Build the payload used by the Battle tab post-match taunt composer. */
export function tauntMessagePayload(value, options = {}) {
  const opts = options && typeof options === "object" ? options : {};
  const phase = opts.phase === "pre" ? "pre" : "post";
  const payload = {
    body: String(value || ""),
    kind: "taunt",
    phase,
  };
  const context = normalizeMatchContext(opts.match_context || opts.matchContext);
  if (context) payload.match_context = context;
  if (opts.match_id) payload.match_id = String(opts.match_id);
  return payload;
}

function inboxRows(payload) {
  const candidates = [
    payload.inbox,
    payload.items,
    payload.entries,
    payload.threads,
    payload.dms,
    payload.messages,
    payload.notifications,
  ];
  for (const candidate of candidates) {
    if (Array.isArray(candidate)) return candidate;
  }
  return [];
}

function inboxFromName(item) {
  const source = item && typeof item === "object" ? item : {};
  return (
    normalText(source.peer_name || source.peerName) ||
    normalText(source.author_name || source.authorName) ||
    normalText(source.display_name || source.displayName) ||
    normalText(source.public_handle || source.publicHandle) ||
    normalText(source.from) ||
    normalText(source.sender) ||
    normalText(source.player) ||
    normalText(source.pet_name || source.petName) ||
    normalText(source.actor_name)
  );
}

/** Coerce one inbox row (DM, mention or taunt notification) for display. */
export function normalizeInboxItem(item) {
  if (!item || typeof item !== "object") return null;
  const body =
    normalText(item.preview) ||
    normalText(item.body) ||
    normalText(item.text) ||
    normalText(item.message);
  const channelId = normalText(item.channel_id || item.channelId);
  const id =
    normalText(item.id) ||
    normalText(item.notification_id) ||
    (channelId ? channelId + ":" + normalText(item.created_at) : "");
  if (!id && !body) return null;
  const rawKind = normalText(item.kind || item.type).toLowerCase();
  const kind =
    rawKind === "dm" || rawKind === "direct"
      ? "dm"
      : rawKind === "mention" || rawKind === "@mention"
        ? "mention"
        : rawKind === "taunt"
          ? "taunt"
          : channelId.indexOf("dm:") === 0
            ? "dm"
            : /(^|\s)@[A-Za-z0-9_]/.test(body)
              ? "mention"
              : "notice";
  return {
    id: id || body,
    kind,
    channel_id: channelId || null,
    account_id: normalText(item.account_id || item.accountId) || null,
    from: inboxFromName(item) || null,
    peer_name: normalNullableText(item.peer_name || item.peerName),
    peer_id: normalNullableText(item.peer_id || item.peerId),
    author_name: normalNullableText(item.author_name || item.authorName),
    public_handle: normalNullableText(
      item.public_handle || item.publicHandle
    ),
    body,
    created_at: normalText(item.created_at),
    read: item.read === true || item.unread === false,
    unread: item.unread === true || item.read === false,
    match_context: normalizeMatchContext(
      item.match_context || item.matchContext
    ),
  };
}

/** Read an inbox envelope into unread counts and display rows. */
export function normalizeInbox(envelopeOrData) {
  if (!envelopeOrData || typeof envelopeOrData !== "object") {
    return { items: [], unreadCount: 0, total: 0, dms: [], mentions: [] };
  }
  const payload =
    envelopeOrData.data && typeof envelopeOrData.data === "object"
      ? envelopeOrData.data
      : envelopeOrData;
  const items = inboxRows(payload).map(normalizeInboxItem).filter(Boolean);
  const explicitUnread = Number(
    payload.unread_count !== undefined
      ? payload.unread_count
      : payload.unreadCount !== undefined
        ? payload.unreadCount
        : payload.unread
  );
  const derivedUnread = items.filter(function (item) {
    return item.unread;
  }).length;
  const unreadCount =
    Number.isFinite(explicitUnread) && explicitUnread >= 0
      ? Math.trunc(explicitUnread)
      : derivedUnread;
  return {
    items,
    unreadCount,
    total:
      Number.isFinite(Number(payload.total)) && Number(payload.total) >= 0
        ? Math.trunc(Number(payload.total))
        : items.length,
    dms: items.filter(function (item) {
      return item.kind === "dm";
    }),
    mentions: items.filter(function (item) {
      return item.kind === "mention";
    }),
  };
}

/** The persistent rail collapses below this viewport width. */
export function lobbyRailAutoCollapsed(width) {
  const value = Number(width);
  if (!Number.isFinite(value)) return false;
  return value < LOBBY_RAIL_BREAKPOINT;
}

/** Unread count for the collapsed lobby rail badge. */
export function lobbyUnreadCount(inbox) {
  return normalizeInbox(inbox).unreadCount;
}

/** Compact badge label; empty at zero and capped for very busy lobbies. */
export function lobbyUnreadLabel(count) {
  const value = Math.trunc(Number(count));
  if (!Number.isFinite(value) || value <= 0) return "";
  return value > 99 ? "99+" : String(value);
}

/** Mark every inbox row read locally without mutating the input. */
export function markInboxRead(inbox) {
  if (!inbox || typeof inbox !== "object") {
    return { items: [], unreadCount: 0, total: 0, dms: [], mentions: [] };
  }
  const items = (Array.isArray(inbox.items) ? inbox.items : []).map(
    function (item) {
      return { ...item, read: true, unread: false };
    }
  );
  return {
    ...inbox,
    items,
    unreadCount: 0,
    dms: items.filter(function (item) {
      return item.kind === "dm";
    }),
    mentions: items.filter(function (item) {
      return item.kind === "mention";
    }),
  };
}

/** Best-effort bridge call telling the server the inbox was opened. */
export function markInboxReadRequest(api, ids) {
  const list = (Array.isArray(ids) ? ids : []).filter(Boolean).map(String);
  if (!list.length) return Promise.resolve(null);
  if (api && typeof api.post === "function") {
    return api.post(CHAT_INBOX_READ_PATH, { ids: list });
  }
  if (api && typeof api.patch === "function") {
    return api.patch(CHAT_INBOX_READ_PATH, { ids: list });
  }
  return Promise.resolve(null);
}

/** Payload for the owner Agent-chat toggle. */
export function chatSettingsPayload(enabled) {
  return { chat_enabled: enabled === true };
}

/** Read the confirmed chat flag from a settings/policy envelope. */
export function chatEnabledFromEnvelope(envelope, fallback = false) {
  if (!envelope || envelope.ok !== true) return fallback;
  const data =
    envelope.data && typeof envelope.data === "object"
      ? envelope.data
      : envelope;
  const candidates = [
    data.chat_enabled,
    data.chatEnabled,
    data.policy && data.policy.chat_enabled,
    data.settings && data.settings.chat_enabled,
    data.me && data.me.policy && data.me.policy.chat_enabled,
  ];
  for (const candidate of candidates) {
    if (candidate !== undefined && candidate !== null) {
      return flagValue(candidate);
    }
  }
  return fallback;
}

/**
 * PATCH the owner chat setting through the local bridge.
 *
 * api.js exposes ``patch`` on newer bridges; older bridges fall back to a POST
 * to the same bridge-relative route so the toggle still works in tests.
 */
export function updateChatSetting(api, enabled, options = {}) {
  const opts = options && typeof options === "object" ? options : {};
  const path = opts.path || CHAT_SETTINGS_PATH;
  const payload = chatSettingsPayload(enabled);
  if (api && typeof api.patch === "function") {
    return api.patch(path, payload);
  }
  if (api && typeof api.post === "function") {
    return api.post(path, payload);
  }
  return Promise.resolve({
    ok: false,
    status: "offline",
    error: {
      code: "network_error",
      message: "Could not reach the local Hermagotchi bridge.",
    },
  });
}

const MODERATION_CODES = new Set([
  "blocked",
  "blocked_interaction",
  "forbidden",
  "rate_limited",
  "empty_message",
  "message_too_long",
  "validation_error",
  "chat_disabled",
  "agent_chat_disabled",
  "chat_off",
  "daily_cap",
  "chat_daily_cap",
  "agent_chat_daily_cap",
  "daily_message_cap",
  "cooldown",
  "chat_cooldown",
  "taunt_cooldown",
  "unanswered_cap",
  "taunt_unanswered_cap",
  "unanswered_taunt_cap",
  "invalid_taunt",
  "taunt_invalid",
  "taunt_rejected",
]);

const AUTH_CODES = new Set(["auth_missing", "unauthorized", "expired", "disabled"]);

function cleanCode(value) {
  return typeof value === "string" ? value.slice(0, 64) : "";
}

function moderationLine(code, retryAfterS) {
  const base = npcHostLine("chat.moderation");
  const seconds = Number(retryAfterS);
  if (code === "rate_limited") {
    return seconds > 0
      ? `Easy there. Try again in ${Math.ceil(seconds)}s.`
      : "Easy there. Slow down before sending again.";
  }
  if (
    code === "cooldown" ||
    code === "chat_cooldown" ||
    code === "taunt_cooldown"
  ) {
    return seconds > 0
      ? `Cooldown. Try again in ${Math.ceil(seconds)}s.`
      : "Cooldown. Give it a moment before the next taunt.";
  }
  if (
    code === "chat_disabled" ||
    code === "agent_chat_disabled" ||
    code === "chat_off"
  ) {
    return "Chat is off. Enable Agent chat in Settings first.";
  }
  if (
    code === "daily_cap" ||
    code === "chat_daily_cap" ||
    code === "agent_chat_daily_cap" ||
    code === "daily_message_cap"
  ) {
    return "Daily chat cap reached. Try again tomorrow.";
  }
  if (
    code === "unanswered_cap" ||
    code === "taunt_unanswered_cap" ||
    code === "unanswered_taunt_cap"
  ) {
    return "Too many unanswered taunts. Wait for a reply first.";
  }
  if (
    code === "invalid_taunt" ||
    code === "taunt_invalid" ||
    code === "taunt_rejected"
  ) {
    return "That taunt was rejected. Keep it short and clean.";
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
