/**
 * Pure pairing/session view-model helpers.
 *
 * This module intentionally has no React import so it can be exercised with
 * Node's built-in test runner. It only transforms bridge envelopes into the
 * small state objects rendered by SettingsTab.
 */

export const PAIRING_STATES = Object.freeze({
  IDLE: "idle",
  STARTING: "starting",
  PENDING: "pending",
  PAIRED: "paired",
  EXPIRED: "expired",
  ERROR: "error",
});

export const PAIRING_STATUS = PAIRING_STATES;
export const SESSION_STATES = PAIRING_STATES;

const USER_CODE_ALPHABET = "BCDFGHJKLMNPQRSTVWXZ23456789";

export function normalizeUserCode(value) {
  return String(value === undefined || value === null ? "" : value)
    .replace(/[\s-]+/g, "")
    .toUpperCase();
}

export const normaliseUserCode = normalizeUserCode;

export function formatUserCode(value) {
  const normalized = normalizeUserCode(value);
  if (normalized.length === 8) {
    return normalized.slice(0, 4) + "-" + normalized.slice(4);
  }
  return normalized;
}

export const formatUserCodeDisplay = formatUserCode;

export function isValidUserCode(value) {
  const normalized = normalizeUserCode(value);
  if (normalized.length !== 8) {
    return false;
  }
  for (const char of normalized) {
    if (USER_CODE_ALPHABET.indexOf(char) === -1) {
      return false;
    }
  }
  return true;
}

export function parseExpiry(value) {
  if (value === undefined || value === null || value === "") {
    return 0;
  }
  if (typeof value === "number") {
    if (!Number.isFinite(value) || value <= 0) {
      return 0;
    }
    return value < 100000000000 ? Math.round(value * 1000) : Math.round(value);
  }
  if (value instanceof Date) {
    return value.getTime();
  }
  const text = String(value);
  if (/^\d+$/.test(text)) {
    const numeric = Number(text);
    return numeric < 100000000000 ? numeric * 1000 : numeric;
  }
  const parsed = Date.parse(text);
  return Number.isFinite(parsed) ? parsed : 0;
}

export function secondsRemaining(expiresAt, now) {
  const expiry = parseExpiry(expiresAt);
  if (!expiry) {
    return 0;
  }
  const current = typeof now === "number" ? now : Date.now();
  const remaining = Math.ceil((expiry - current) / 1000);
  return remaining > 0 ? remaining : 0;
}

export function formatCountdown(seconds) {
  const value = Math.max(0, Math.floor(Number(seconds) || 0));
  if (value <= 0) {
    return "Expired";
  }
  const minutes = Math.floor(value / 60);
  const rest = value % 60;
  return minutes + ":" + String(rest).padStart(2, "0");
}

export function isExpired(expiresAt, now) {
  const expiry = parseExpiry(expiresAt);
  if (!expiry) {
    return false;
  }
  const current = typeof now === "number" ? now : Date.now();
  return expiry <= current;
}

export function envelopeData(value) {
  if (
    value &&
    typeof value === "object" &&
    typeof value.ok === "boolean"
  ) {
    if (!value.ok) {
      return {};
    }
    return value.data && typeof value.data === "object" ? value.data : {};
  }
  return value && typeof value === "object" ? value : {};
}

export function envelopeError(value) {
  if (value && typeof value === "object" && value.ok === false) {
    const error = value.error || {};
    return {
      status: value.status || "unavailable",
      code: error.code || value.status || "unavailable",
      message: error.message || "The request could not be completed.",
      retryAfterS: Number(error.retry_after_s) || 0,
    };
  }
  return null;
}

export function emptyPairingState() {
  return {
    status: PAIRING_STATES.IDLE,
    paired: false,
    accountId: null,
    userCode: "",
    userCodeDisplay: "",
    expiresAt: null,
    expiresAtMs: 0,
    intervalS: 5,
    secondsRemaining: 0,
    countdown: "",
    retryAfterS: 0,
    error: null,
  };
}

function withCountdown(state, now) {
  const remaining = state.expiresAtMs
    ? secondsRemaining(state.expiresAtMs, now)
    : 0;
  const next = Object.assign({}, state);
  next.secondsRemaining = remaining;
  next.countdown = state.expiresAtMs
    ? formatCountdown(remaining)
    : "";
  if (
    state.status === PAIRING_STATES.PENDING &&
    state.expiresAtMs &&
    remaining === 0 &&
    !state.paired
  ) {
    next.status = PAIRING_STATES.EXPIRED;
  }
  return next;
}

export function pairingStateFromStart(value, now) {
  const failure = envelopeError(value);
  if (failure) {
    return Object.assign(emptyPairingState(), {
      status:
        failure.status === "expired"
          ? PAIRING_STATES.EXPIRED
          : PAIRING_STATES.ERROR,
      error: failure,
    });
  }
  const data = envelopeData(value);
  const userCode = normalizeUserCode(data.user_code || data.userCode);
  if (!userCode) {
    return Object.assign(emptyPairingState(), {
      status: PAIRING_STATES.ERROR,
      error: {
        status: "unavailable",
        code: "invalid_response",
        message: "The bridge did not return a pairing code.",
        retryAfterS: 0,
      },
    });
  }
  const expiresAt = data.expires_at || data.expiresAt || null;
  const state = Object.assign(emptyPairingState(), {
    status: PAIRING_STATES.PENDING,
    paired: Boolean(data.paired),
    accountId: data.account_id || data.accountId || null,
    userCode: userCode,
    userCodeDisplay: formatUserCode(userCode),
    expiresAt: expiresAt,
    expiresAtMs: parseExpiry(expiresAt),
    intervalS: Number(data.interval_s || data.intervalS) || 5,
  });
  return withCountdown(state, now);
}

export function pairingStateFromPoll(value, previous, now) {
  const prior = Object.assign(emptyPairingState(), previous || {});
  const failure = envelopeError(value);
  if (failure) {
    const expired =
      failure.status === "expired" ||
      failure.code === "expired_token";
    if (expired) {
      return Object.assign(prior, {
        status: PAIRING_STATES.EXPIRED,
        paired: false,
        secondsRemaining: 0,
        countdown: "Expired",
        error: failure,
      });
    }
    return Object.assign(prior, {
      status: PAIRING_STATES.ERROR,
      error: failure,
    });
  }

  const data = envelopeData(value);
  if (data.paired === true) {
    return Object.assign(prior, {
      status: PAIRING_STATES.PAIRED,
      paired: true,
      accountId: data.account_id || data.accountId || prior.accountId || null,
      secondsRemaining: 0,
      countdown: "",
      retryAfterS: 0,
      error: null,
    });
  }

  if (data.status === "expired") {
    return Object.assign(prior, {
      status: PAIRING_STATES.EXPIRED,
      paired: false,
      secondsRemaining: 0,
      countdown: "Expired",
      error: null,
    });
  }

  if (data.status === "idle" && !prior.userCode) {
    return Object.assign(prior, {
      status: PAIRING_STATES.IDLE,
      paired: false,
      error: null,
    });
  }

  return withCountdown(
    Object.assign(prior, {
      status: PAIRING_STATES.PENDING,
      paired: false,
      retryAfterS: Number(data.retry_after_s || data.retryAfterS) || 0,
      error: null,
    }),
    now
  );
}

export function pairingStateFromError(value, previous) {
  const prior = Object.assign(emptyPairingState(), previous || {});
  const failure =
    envelopeError(value) || {
      status: "unavailable",
      code: "unavailable",
      message: "The request could not be completed.",
      retryAfterS: 0,
    };
  return Object.assign(prior, {
    status: PAIRING_STATES.ERROR,
    paired: false,
    error: failure,
  });
}

export function deviceRowsFromEnvelope(value) {
  let devices = [];
  if (Array.isArray(value)) {
    devices = value;
  } else {
    const data = envelopeData(value);
    if (Array.isArray(data.devices)) {
      devices = data.devices;
    } else if (Array.isArray(value && value.devices)) {
      devices = value.devices;
    }
  }
  return devices.map((device) => {
    const source = device || {};
    const id = String(
      source.device_id || source.deviceId || source.id || ""
    );
    const name = source.device_name || source.deviceName || source.name || "Device";
    const revoked = Boolean(source.revoked);
    const current = Boolean(source.current);
    return {
      id: id,
      deviceId: id,
      device_id: id,
      name: name,
      deviceName: name,
      device_name: name,
      createdAt: source.created_at || source.createdAt || null,
      lastSeenAt: source.last_seen_at || source.lastSeenAt || null,
      current: current,
      revoked: revoked,
      active: !revoked,
      canRevoke: !revoked,
      revokeLabel: current ? "Revoke this device" : "Revoke",
    };
  });
}

export const devicesFromEnvelope = deviceRowsFromEnvelope;

export function countdownLabel(state, now) {
  if (!state) {
    return "";
  }
  if (state.status === PAIRING_STATES.PAIRED) {
    return "Paired";
  }
  if (state.status === PAIRING_STATES.EXPIRED) {
    return "Expired";
  }
  if (!state.expiresAtMs) {
    return "";
  }
  return formatCountdown(secondsRemaining(state.expiresAtMs, now));
}

export function buildPairingViewModel(input, now) {
  const source = input || {};
  let state;
  if (source.error) {
    state = pairingStateFromError(source.error, source.previous);
  } else if (source.poll) {
    const prior = source.start
      ? pairingStateFromStart(source.start, now)
      : source.previous;
    state = pairingStateFromPoll(source.poll, prior, now);
  } else if (source.start) {
    state = pairingStateFromStart(source.start, now);
  } else {
    state = Object.assign(emptyPairingState(), source.previous || {});
  }

  const devices = deviceRowsFromEnvelope(source.devices);
  return Object.assign({}, state, {
    devices: devices,
    deviceCount: devices.length,
    hasDevices: devices.length > 0,
    hasPending: state.status === PAIRING_STATES.PENDING,
    isPaired: state.status === PAIRING_STATES.PAIRED,
    canApprove: state.status === PAIRING_STATES.PAIRED,
    countdownLabel: countdownLabel(state, now),
  });
}

export const createPairingViewModel = buildPairingViewModel;
