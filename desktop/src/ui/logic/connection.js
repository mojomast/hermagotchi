/**
 * Pure connection/pairing status helpers.
 *
 * The pane header and Settings tab share this module so both read the same
 * bridge envelopes. It has no React and no network imports, which keeps it
 * directly testable with Node's built-in test runner.
 */

const AUTH_FAILURES = new Set(["auth_missing", "unauthorized", "expired"]);

function normaliseEnvelope(value) {
  if (!value || typeof value !== "object") {
    return null;
  }
  const ok = value.ok === true;
  const error = value.error && typeof value.error === "object" ? value.error : {};
  const body =
    value.data && typeof value.data === "object"
      ? value.data
      : value.ok === false
        ? {}
        : value;
  return {
    ok: ok,
    status: value.status || (ok ? "ok" : "unavailable"),
    code: error.code || null,
    error: error,
    body: body,
  };
}

function policyFrom(status, health) {
  const sources = [
    status && status.body && status.body.policy,
    health && health.body && health.body.policy,
  ];
  for (const source of sources) {
    if (source && typeof source === "object") {
      return source;
    }
  }
  return null;
}

function accountFromStatus(status) {
  if (!status || !status.ok) {
    return null;
  }
  const body = status.body || {};
  const me = body.me && typeof body.me === "object" ? body.me : null;
  if (me) {
    if (me.account && typeof me.account === "object" && me.account.id) {
      return String(me.account.id);
    }
    if (me.account_id || me.accountId || me.id) {
      return String(me.account_id || me.accountId || me.id);
    }
  }
  if (body.account_id || body.accountId) {
    return String(body.account_id || body.accountId);
  }
  return null;
}

function authenticatedFrom(pair, status) {
  if (pair) {
    const data = pair.body || {};
    if (pair.ok && data.paired === true) {
      return true;
    }
    if (pair.ok && data.paired === false) {
      return false;
    }
    if (!pair.ok) {
      if (AUTH_FAILURES.has(pair.status) || AUTH_FAILURES.has(pair.code)) {
        return false;
      }
      return null;
    }
  }
  const accountId = accountFromStatus(status);
  if (accountId) {
    return true;
  }
  return null;
}

function booleanPolicy(policy, keys) {
  if (!policy) {
    return null;
  }
  for (const key of keys) {
    if (typeof policy[key] === "boolean") {
      return policy[key];
    }
  }
  return null;
}

function pairImpliesBackend(pair) {
  if (!pair) {
    return null;
  }
  if (pair.ok) {
    return true;
  }
  if (
    pair.status === "offline" ||
    pair.status === "unavailable" ||
    pair.code === "network_error"
  ) {
    return false;
  }
  // A bridge that answers with auth_missing/expired is still alive.
  return true;
}

function serviceConfigured(policy, statusOk, healthOk) {
  if (policy) {
    if (typeof policy.service_configured === "boolean") {
      return policy.service_configured;
    }
    if (
      policy.service_url ||
      policy.serviceUrl ||
      policy.multiplayer_url ||
      policy.multiplayerUrl ||
      policy.api_url ||
      policy.apiUrl
    ) {
      return true;
    }
  }
  if (statusOk || healthOk) {
    return true;
  }
  return null;
}

export function deriveConnectionStatus(options = {}) {
  const status = normaliseEnvelope(
    options.statusEnvelope || options.status || options.statusResult
  );
  const health = normaliseEnvelope(
    options.healthEnvelope || options.health || options.healthResult
  );
  const pair = normaliseEnvelope(
    options.pairEnvelope || options.pair || options.pairResult
  );

  const statusOk = Boolean(status && status.ok);
  const healthOk = Boolean(health && health.ok);
  const anyStatus = Boolean(status || health);
  const backendEnabled =
    statusOk || healthOk
      ? true
      : anyStatus
        ? false
        : pairImpliesBackend(pair);
  const serviceReachable = backendEnabled;

  const policy = policyFrom(status, health);
  // Prefer account chat_settings / me.policy when the bridge policy is still default-off.
  const mePolicy =
    status && status.body && status.body.me && status.body.me.policy
      ? status.body.me.policy
      : status && status.me && status.me.policy
        ? status.me.policy
        : null;
  const policyNetwork = booleanPolicy(policy, ["network_enabled", "networkEnabled"]);
  const networkEnabled =
    policyNetwork === null
      ? backendEnabled === true
        ? true
        : null
      : policyNetwork;

  return {
    backendEnabled: backendEnabled,
    networkEnabled: networkEnabled,
    authenticated: authenticatedFrom(pair, status),
    serviceReachable: serviceReachable,
    serviceConfigured: serviceConfigured(policy, statusOk, healthOk),
    chatEnabled: (function () {
      const fromMe = booleanPolicy(mePolicy, ["chat_enabled", "chatEnabled"]);
      if (fromMe !== null) return fromMe;
      return booleanPolicy(policy, ["chat_enabled", "chatEnabled"]);
    })(),
    autonomyEnabled: booleanPolicy(policy, [
      "autonomy_enabled",
      "autonomyEnabled",
      "agent_autonomy_enabled",
    ]),
    accountId: pair && pair.ok && (pair.body.account_id || pair.body.accountId)
      ? String(pair.body.account_id || pair.body.accountId)
      : accountFromStatus(status),
    policy: policy,
  };
}

function label(value, enabled, disabled, unknown) {
  if (value === true) return enabled;
  if (value === false) return disabled;
  return unknown;
}

export function connectionRows(connection = {}) {
  const service =
    connection.serviceReachable === true
      ? "Reachable"
      : connection.serviceReachable === false
        ? "Unavailable"
        : connection.serviceConfigured === true
          ? "Configured"
          : "Not configured";

  return [
    {
      key: "backend",
      label: "Python backend",
      value: label(connection.backendEnabled, "Enabled", "Disabled", "Unknown"),
    },
    {
      key: "network",
      label: "Multiplayer",
      value: label(connection.networkEnabled, "On", "Off", "Unknown"),
    },
    {
      key: "identity",
      label: "Identity",
      value: connection.authenticated === true ? "Paired" : "Not paired",
    },
    {
      key: "chat",
      label: "Chat",
      value: label(connection.chatEnabled, "On", "Off", "Unknown"),
    },
    {
      key: "autonomy",
      label: "Agent autonomy",
      value: label(connection.autonomyEnabled, "On", "Off", "Unknown"),
    },
    { key: "service", label: "Service", value: service },
  ];
}

export function resolveConnectionUiState(connection = {}) {
  if (connection.backendEnabled === false) {
    return "backend_disabled";
  }
  if (connection.networkEnabled === false) {
    return "network_off";
  }
  if (connection.authenticated === false) {
    return "auth_missing";
  }
  if (connection.serviceReachable === false) {
    return "service_unavailable";
  }
  return "ready";
}
