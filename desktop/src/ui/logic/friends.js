/** Pure friend roster and request helpers for the Desktop social hub. */

export const FRIENDS_PATH = "/friends";
export const FRIEND_REQUESTS_PATH = "/friends/requests";
export const FRIEND_TARGET_MAX_CHARS = 64;

export const FRIEND_STATUSES = Object.freeze(["online", "away", "offline"]);

const STATUS_LABELS = Object.freeze({
  online: "Online",
  away: "Away",
  offline: "Offline",
});

function text(value, fallback = "") {
  return typeof value === "string" ? value : fallback;
}

function list(value) {
  return Array.isArray(value) ? value : [];
}

export function normalizeFriendStatus(value) {
  const status = text(value).trim().toLowerCase();
  return FRIEND_STATUSES.indexOf(status) >= 0 ? status : "offline";
}

export function friendStatusLabel(value) {
  return STATUS_LABELS[normalizeFriendStatus(value)];
}

function friendIdentity(item) {
  return (
    text(item.account_id) ||
    text(item.accountId) ||
    text(item.friend_id) ||
    text(item.friendId) ||
    text(item.id)
  );
}

function friendName(item) {
  return (
    text(item.name) ||
    text(item.public_handle) ||
    text(item.publicHandle) ||
    text(item.handle) ||
    text(item.pet_name) ||
    text(item.petName) ||
    text(item.player) ||
    friendIdentity(item)
  );
}

/** Coerce one friend row into the display shape without trusting its text. */
export function normalizeFriend(item) {
  if (!item || typeof item !== "object") return null;
  const accountId = friendIdentity(item);
  const name = friendName(item);
  if (!accountId && !name) return null;
  const id = accountId || name;
  return {
    id,
    account_id: accountId || null,
    name,
    pet_name:
      text(item.pet_name) ||
      text(item.petName) ||
      text(item.pet && item.pet.name) ||
      null,
    status: normalizeFriendStatus(item.status || item.presence),
    status_label: friendStatusLabel(item.status || item.presence),
    last_seen: text(item.last_seen) || text(item.lastSeen) || null,
    direction: text(item.direction) || null,
    created_at: text(item.created_at) || null,
  };
}

function requestRows(payload, keys) {
  for (const key of keys) {
    if (Array.isArray(payload[key])) return payload[key];
  }
  return [];
}

function normalizeRequest(item, direction) {
  const row = normalizeFriend(item);
  if (!row) return null;
  return {
    ...row,
    id:
      text(item.id) ||
      text(item.request_id) ||
      text(item.requestId) ||
      row.id,
    direction,
  };
}

/** Read friends plus incoming/outgoing requests from an envelope or payload. */
export function normalizeFriends(envelopeOrData) {
  if (!envelopeOrData || typeof envelopeOrData !== "object") {
    return { friends: [], incoming: [], outgoing: [], total: 0 };
  }
  const payload =
    envelopeOrData.data && typeof envelopeOrData.data === "object"
      ? envelopeOrData.data
      : envelopeOrData;
  const friends = list(payload.friends)
    .concat(list(payload.items))
    .map(normalizeFriend)
    .filter(Boolean);
  const requests =
    payload.requests && typeof payload.requests === "object"
      ? payload.requests
      : {};
  const incoming = requestRows(payload, ["incoming", "incoming_requests"])
    .concat(requestRows(requests, ["incoming", "incoming_requests"]))
    .map(function (item) {
      return normalizeRequest(item, "incoming");
    })
    .filter(Boolean);
  const outgoing = requestRows(payload, ["outgoing", "outgoing_requests"])
    .concat(requestRows(requests, ["outgoing", "outgoing_requests"]))
    .map(function (item) {
      return normalizeRequest(item, "outgoing");
    })
    .filter(Boolean);
  return {
    friends,
    incoming,
    outgoing,
    total: friends.length + incoming.length + outgoing.length,
  };
}

export function friendPresenceCounts(friends) {
  const counts = { online: 0, away: 0, offline: 0 };
  for (const friend of list(friends)) {
    const status = normalizeFriendStatus(friend && friend.status);
    counts[status] += 1;
  }
  return counts;
}

/** Filter the roster by presence and a plain-text name query. */
export function filterFriends(friends, options = {}) {
  const opts = options && typeof options === "object" ? options : {};
  const status = text(opts.status).trim().toLowerCase();
  const query = text(opts.query).trim().toLowerCase();
  return list(friends).filter(function (friend) {
    if (!friend) return false;
    if (status && status !== "all" && normalizeFriendStatus(friend.status) !== status) {
      return false;
    }
    if (!query) return true;
    const haystack = [friend.name, friend.pet_name, friend.account_id]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    return haystack.indexOf(query) >= 0;
  });
}

export function validateFriendTarget(value) {
  const target = typeof value === "string" ? value.trim() : "";
  if (!target) {
    return { ok: false, error: "Enter a player or pet name." };
  }
  if (target.length > FRIEND_TARGET_MAX_CHARS) {
    return {
      ok: false,
      error: `Friend names cannot exceed ${FRIEND_TARGET_MAX_CHARS} characters.`,
    };
  }
  return { ok: true, value: target };
}

export function friendRequestPayload(value) {
  const checked = validateFriendTarget(value);
  return { target: checked.ok ? checked.value : "" };
}

export function friendRequestRespondPath(requestId) {
  const id = typeof requestId === "string" ? requestId : String(requestId || "");
  return FRIEND_REQUESTS_PATH + "/" + encodeURIComponent(id) + "/respond";
}

export function friendRequestResponsePayload(action) {
  return { action: action === "accept" ? "accept" : "decline" };
}

export function friendRemovePath(friendId) {
  const id = typeof friendId === "string" ? friendId : String(friendId || "");
  return FRIENDS_PATH + "/" + encodeURIComponent(id);
}
