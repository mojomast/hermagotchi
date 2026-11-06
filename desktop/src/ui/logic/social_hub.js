/** Pure social-hub helpers shared by the Desktop Chat tab and its tests. */

import { normalizeInbox, tauntSummary } from "./chat.js";

export const SOCIAL_HUB_CONTEXT = "lobby.social";
export const SOCIAL_HUB_SECTIONS = Object.freeze([
  Object.freeze({ id: "dms", label: "Direct messages" }),
  Object.freeze({ id: "friends", label: "Friends" }),
  Object.freeze({ id: "challenges", label: "Challenges" }),
  Object.freeze({ id: "history", label: "Taunts & mentions" }),
]);

export const SOCIAL_HUB_HOST = Object.freeze({
  id: "npc.nous_girl",
  name: "Nous Girl",
  context: SOCIAL_HUB_CONTEXT,
  line: "Welcome to the hub. DMs, friends, challenges, all one signal.",
  displayOnly: true,
});

export const CHALLENGES_PATH = "/challenges";
export const CHALLENGE_INBOX_PATH = "/challenges/inbox";
export const CHALLENGE_MODES = Object.freeze(["casual", "ranked"]);

function text(value, fallback = "") {
  return typeof value === "string" ? value : fallback;
}

function list(value) {
  return Array.isArray(value) ? value : [];
}

export function socialHubHost() {
  return { ...SOCIAL_HUB_HOST };
}

function bridgeSafeChannel(value) {
  return (
    typeof value === "string" &&
    /^[A-Za-z0-9_.:~-]+$/.test(value) &&
    value !== "." &&
    value !== ".."
  );
}

/** Return the bridge-relative message path for one DM channel. */
export function threadMessagePath(channelId) {
  const channel = text(channelId).trim();
  if (!channel) return "";
  const segment = bridgeSafeChannel(channel)
    ? channel
    : encodeURIComponent(channel).replace(/[.]/g, "%2E");
  return "/chat/channels/" + segment + "/messages";
}

function isDmChannel(channelId) {
  return (
    channelId.indexOf("dm:") === 0 || channelId.indexOf("direct:") === 0
  );
}

function threadPeerId(item, channelId) {
  return (
    text(item.peer_id) ||
    text(item.peerId) ||
    text(item.account_id) ||
    text(item.from) ||
    text(item.player) ||
    text(channelId)
  );
}

function threadPeerLabel(item, channelId) {
  const label =
    text(item.peer_name) ||
    text(item.peerName) ||
    text(item.author_name) ||
    text(item.authorName) ||
    text(item.public_handle) ||
    text(item.publicHandle) ||
    null;
  if (label) return label;
  // Prefer a human from/player only when it is not a raw id-looking token.
  const soft = text(item.from) || text(item.player) || "";
  if (soft && soft.indexOf(":") === -1 && soft.length < 48) return soft;
  return "Player";
}

function threadFromItem(item) {
  if (!item || typeof item !== "object") return null;
  const channelId = text(item.channel_id);
  if (!channelId || !isDmChannel(channelId)) return null;
  const peerId = threadPeerId(item, channelId);
  return {
    id: channelId,
    channel_id: channelId,
    peer: threadPeerLabel(item, channelId),
    peer_id: peerId,
    preview: text(item.body),
    updated_at: text(item.created_at),
    unread: Boolean(item.unread),
    kind: "dm",
  };
}

/** Group inbox DM rows into one thread per channel, newest first. */
export function normalizeThreads(envelopeOrData) {
  const inbox = normalizeInbox(envelopeOrData);
  const byChannel = new Map();
  for (const item of inbox.items) {
    const thread = threadFromItem(item);
    if (!thread) continue;
    const current = byChannel.get(thread.channel_id);
    if (!current) {
      byChannel.set(thread.channel_id, thread);
      continue;
    }
    const newer = thread.updated_at >= current.updated_at;
    byChannel.set(thread.channel_id, {
      ...current,
      peer: thread.peer || current.peer,
      peer_id: thread.peer_id || current.peer_id,
      preview: newer ? thread.preview : current.preview,
      updated_at: newer ? thread.updated_at : current.updated_at,
      unread: current.unread || thread.unread,
    });
  }
  return [...byChannel.values()].sort(function (left, right) {
    if (left.updated_at === right.updated_at) {
      return left.channel_id < right.channel_id ? 1 : -1;
    }
    return left.updated_at < right.updated_at ? 1 : -1;
  });
}

function normalizeMode(value) {
  const mode = text(value).trim().toLowerCase();
  return CHALLENGE_MODES.indexOf(mode) >= 0 ? mode : "casual";
}

function modeLabel(mode) {
  const label = normalizeMode(mode);
  return label.charAt(0).toUpperCase() + label.slice(1) + " challenge";
}

/** Coerce one challenge row for the hub's pending list. */
export function normalizeChallenge(item) {
  if (!item || typeof item !== "object") return null;
  const id = text(item.id);
  if (!id) return null;
  const mode = normalizeMode(item.mode);
  return {
    id,
    challenger_id: text(item.challenger_id) || null,
    defender_id: text(item.defender_id) || null,
    mode,
    label: modeLabel(mode),
    direction: item.direction === "incoming" ? "incoming" : "outgoing",
    status: text(item.status) || "pending",
    created_at: text(item.created_at) || null,
    expires_at: text(item.expires_at) || null,
  };
}

/** Read pending incoming/outgoing challenges from an inbox envelope. */
export function normalizeChallengeInbox(envelopeOrData) {
  if (!envelopeOrData || typeof envelopeOrData !== "object") {
    return { incoming: [], outgoing: [], pending: [] };
  }
  const payload =
    envelopeOrData.data && typeof envelopeOrData.data === "object"
      ? envelopeOrData.data
      : envelopeOrData;
  const incoming = list(payload.incoming)
    .map(function (item) {
      return normalizeChallenge({ ...item, direction: "incoming" });
    })
    .filter(Boolean);
  const outgoing = list(payload.outgoing)
    .map(function (item) {
      return normalizeChallenge({ ...item, direction: "outgoing" });
    })
    .filter(Boolean);
  const combined = list(payload.challenges)
    .map(normalizeChallenge)
    .filter(Boolean);
  const pending =
    incoming.length || outgoing.length ? [...incoming, ...outgoing] : combined;
  return { incoming, outgoing, pending };
}

export function challengeCreatePayload(target, mode) {
  return {
    defender_id: typeof target === "string" ? target : String(target || ""),
    mode: normalizeMode(mode),
  };
}

export function challengeRespondPath(challengeId) {
  const id =
    typeof challengeId === "string" ? challengeId : String(challengeId || "");
  return CHALLENGES_PATH + "/" + encodeURIComponent(id) + "/respond";
}

export function challengeResponsePayload(action) {
  return { action: action === "accept" ? "accept" : "decline" };
}

function historyKind(item) {
  if (!item || typeof item !== "object") return "";
  if (item.kind === "dm" || item.kind === "direct") return "";
  if (item.kind === "taunt" || item.match_context || item.matchContext) {
    return "taunt";
  }
  if (item.kind === "mention" || item.kind === "@mention") return "mention";
  const body = text(item.body) || text(item.preview) || text(item.text);
  return /(^|\s)@[A-Za-z0-9_]/.test(body) ? "mention" : "";
}

function matchContext(item) {
  const source = item.match_context || item.matchContext;
  return source && typeof source === "object" ? source : null;
}

/** Coerce one taunt or @mention row for the filterable history list. */
export function normalizeHistoryItem(item) {
  if (!item || typeof item !== "object") return null;
  const kind = historyKind(item);
  const body =
    text(item.body) || text(item.preview) || text(item.text) || text(item.message);
  if (!kind || !body) return null;
  const context = matchContext(item);
  const matchId = text(item.match_id) || (context && text(context.match_id));
  return {
    id: text(item.id) || matchId || kind + ":" + body.slice(0, 24),
    kind,
    body,
    from:
      text(item.author_name) ||
      text(item.authorName) ||
      text(item.from) ||
      text(item.sender) ||
      text(item.player) ||
      text(item.public_handle) ||
      null,
    created_at: text(item.created_at) || null,
    match_id: matchId || null,
    match_context: context,
    match_summary: context ? tauntSummary(context) : "",
  };
}

function historyRows(payload) {
  const rows = [];
  for (const key of ["history", "items", "messages", "taunts", "mentions"]) {
    rows.push(...list(payload[key]));
  }
  return rows;
}

/** Read taunts and mentions from an envelope, deduplicated by id. */
export function normalizeHistory(envelopeOrData) {
  if (!envelopeOrData || typeof envelopeOrData !== "object") return [];
  const payload =
    envelopeOrData.data && typeof envelopeOrData.data === "object"
      ? envelopeOrData.data
      : envelopeOrData;
  const seen = new Set();
  const rows = [];
  for (const item of historyRows(payload)) {
    const row = normalizeHistoryItem(item);
    if (!row || seen.has(row.id)) continue;
    seen.add(row.id);
    rows.push(row);
  }
  return rows.sort(function (left, right) {
    if (left.created_at === right.created_at) return 0;
    return left.created_at < right.created_at ? 1 : -1;
  });
}

export function historyFilterCounts(items) {
  const rows = list(items);
  return {
    all: rows.length,
    taunt: rows.filter(function (item) {
      return item && item.kind === "taunt";
    }).length,
    mention: rows.filter(function (item) {
      return item && item.kind === "mention";
    }).length,
  };
}

/** Filter history rows by kind and a plain-text query. */
export function filterHistory(items, filter, query) {
  const kind = text(filter) || "all";
  const search = text(query).trim().toLowerCase();
  return list(items).filter(function (item) {
    if (!item) return false;
    if (kind !== "all" && item.kind !== kind) return false;
    if (!search) return true;
    const haystack = [
      item.body,
      item.from,
      item.match_id,
      item.match_summary,
      item.match_context && item.match_context.winner_name,
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    return haystack.indexOf(search) >= 0;
  });
}

export function replayHref(matchId) {
  const id = text(matchId).trim();
  return id ? "#replay/" + encodeURIComponent(id) : "";
}

export function replayPath(matchId) {
  const id = text(matchId).trim();
  return id ? "/matches/" + encodeURIComponent(id) : "";
}
