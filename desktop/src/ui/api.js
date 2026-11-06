/**
 * Local dashboard bridge client for the Hermagotchi Desktop UI.
 *
 * The browser/Desktop layer never sees a session token. Every call goes to the
 * local Hermes bridge, which adds the Bearer header server-side. All methods
 * resolve to the bridge envelope and never reject.
 */

export const DEFAULT_BASE_PATH = "/api/plugins/hermagotchi";
export const PROXY_PREFIX = "/proxy/v1";

const UI_STATE_VALUES = Object.freeze({
  READY: "ready",
  BACKEND_DISABLED: "backend_disabled",
  NETWORK_OFF: "network_off",
  AUTH_MISSING: "auth_missing",
  SERVICE_UNAVAILABLE: "service_unavailable",
});

function randomKey() {
  const source = globalThis.crypto;
  if (source && typeof source.randomUUID === "function") {
    return source.randomUUID();
  }
  return (
    "hg-" +
    Date.now().toString(16) +
    "-" +
    Math.random().toString(16).slice(2, 12)
  );
}

function normalizeBasePath(basePath) {
  if (typeof basePath !== "string") {
    return DEFAULT_BASE_PATH;
  }
  const trimmed = basePath.trim();
  if (!trimmed) {
    return "";
  }
  if (trimmed === "/") {
    return "";
  }
  return trimmed.replace(/\/+$/, "");
}

function normalizePath(path) {
  if (typeof path !== "string") {
    return "";
  }
  return path.startsWith("/") ? path : "/" + path;
}

function errorEnvelope(status, code, message, retryAfterSeconds) {
  return {
    ok: false,
    status: status,
    error: {
      code: code,
      message: message,
      retry_after_s: Number(retryAfterSeconds) || 0,
    },
  };
}

function offlineEnvelope() {
  return errorEnvelope(
    "offline",
    "network_error",
    "Could not reach the local Hermagotchi bridge."
  );
}

function asEnvelope(parsed, response) {
  if (
    parsed &&
    typeof parsed === "object" &&
    typeof parsed.ok === "boolean" &&
    typeof parsed.status === "string"
  ) {
    return parsed;
  }
  const status = response && response.ok === false ? "http_error" : "ok";
  if (status === "http_error") {
    return errorEnvelope(
      "http_error",
      "http_" + (response && response.status ? response.status : "error"),
      "The bridge returned an unexpected response."
    );
  }
  return { ok: true, status: "ok", data: parsed === undefined ? null : parsed };
}

function pairStartBody(input, options) {
  const opts = options || {};
  if (typeof input === "string") {
    const newAccount =
      typeof options === "boolean"
        ? options
        : Boolean(
            opts.new_account === undefined ? opts.newAccount : opts.new_account
          );
    return {
      device_name: input,
      new_account: newAccount,
    };
  }
  if (input && typeof input === "object") {
    const body = Object.assign({}, input);
    if (body.deviceName !== undefined && body.device_name === undefined) {
      body.device_name = body.deviceName;
    }
    if (body.newAccount !== undefined && body.new_account === undefined) {
      body.new_account = body.newAccount;
    }
    delete body.deviceName;
    delete body.newAccount;
    return body;
  }
  return { device_name: "Desktop", new_account: false };
}

function approveBody(input) {
  if (typeof input === "string") {
    return { user_code: input };
  }
  if (input && typeof input === "object") {
    return input;
  }
  return {};
}

function revokeId(input) {
  if (typeof input === "string") {
    return input;
  }
  if (input && typeof input === "object") {
    if (input.device_id !== undefined) return String(input.device_id);
    if (input.id !== undefined) return String(input.id);
  }
  return "";
}

export function createApiClient(options) {
  const config = options || {};
  const basePath = normalizeBasePath(config.basePath);
  const fetchImpl =
    config.fetchImpl ||
    (typeof globalThis.fetch === "function"
      ? globalThis.fetch.bind(globalThis)
      : null);

  async function request(method, url, requestOptions) {
    const opts = requestOptions || {};
    if (typeof fetchImpl !== "function") {
      return offlineEnvelope();
    }
    const headers = {};
    if (opts.hasBody) {
      headers["Content-Type"] = "application/json";
    }
    if (opts.idempotencyKey) {
      headers["Idempotency-Key"] = opts.idempotencyKey;
    }
    const init = { method: method, headers: headers };
    if (opts.hasBody) {
      init.body = JSON.stringify(
        opts.body === undefined || opts.body === null ? {} : opts.body
      );
    }

    let response;
    try {
      response = await fetchImpl(url, init);
    } catch (_error) {
      return offlineEnvelope();
    }

    let parsed;
    try {
      parsed = await response.json();
    } catch (_error) {
      parsed = undefined;
    }
    return asEnvelope(parsed, response);
  }

  function proxyUrl(path) {
    return basePath + PROXY_PREFIX + normalizePath(path);
  }

  function pairUrl(path) {
    return basePath + normalizePath(path);
  }

  return {
    basePath: basePath,
    get: function get(path) {
      return request("GET", proxyUrl(path), {});
    },
    post: function post(path, body, postOptions) {
      const opts = postOptions || {};
      return request("POST", proxyUrl(path), {
        hasBody: true,
        body: body,
        idempotencyKey:
          opts.idempotencyKey || opts.idempotency_key || randomKey(),
      });
    },
    del: function del(path, deleteOptions) {
      const opts = deleteOptions || {};
      return request("DELETE", proxyUrl(path), {
        idempotencyKey:
          opts.idempotencyKey || opts.idempotency_key || randomKey(),
      });
    },
    pair: {
      start: function start(input, startOptions) {
        return request("POST", pairUrl("/pair/start"), {
          hasBody: true,
          body: pairStartBody(input, startOptions),
        });
      },
      poll: function poll() {
        return request("POST", pairUrl("/pair/poll"), {
          hasBody: true,
          body: {},
        });
      },
      approve: function approve(input) {
        return request("POST", pairUrl("/pair/approve"), {
          hasBody: true,
          body: approveBody(input),
        });
      },
      devices: function devices() {
        return request("GET", pairUrl("/pair/devices"), {});
      },
      revoke: function revoke(input) {
        const id = encodeURIComponent(revokeId(input));
        return request("POST", pairUrl("/pair/devices/" + id + "/revoke"), {
          hasBody: true,
          body: {},
        });
      },
      logout: function logout() {
        return request("POST", pairUrl("/pair/logout"), {
          hasBody: true,
          body: {},
        });
      },
    },
  };
}

export function isEnvelopeOk(envelope) {
  return Boolean(
    envelope &&
      typeof envelope === "object" &&
      envelope.ok === true
  );
}

export function uiStateFromEnvelope(envelope) {
  if (!envelope || envelope.ok === true) {
    return UI_STATE_VALUES.READY;
  }
  switch (envelope.status) {
    case "auth_missing":
    case "unauthorized":
    case "expired":
      return UI_STATE_VALUES.AUTH_MISSING;
    case "backend_disabled":
      return UI_STATE_VALUES.BACKEND_DISABLED;
    case "network_off":
      return UI_STATE_VALUES.NETWORK_OFF;
    case "offline":
    case "unavailable":
    case "not_allowed":
    case "http_error":
      return UI_STATE_VALUES.SERVICE_UNAVAILABLE;
    default:
      return UI_STATE_VALUES.SERVICE_UNAVAILABLE;
  }
}

export { UI_STATE_VALUES as API_UI_STATES };
