/**
 * Hermes host (gateway) credentials for same-origin bridge calls.
 *
 * The Hermagotchi bridge itself adds the game Bearer server-side; the pane
 * never sees that. But the Hermes webapp gates `/api/plugins/...` behind a
 * host session: the SPA stores a launch-link grant in sessionStorage and
 * sends it as `X-Hermes-Session-Token`. Bare fetch / img tags omit that
 * header and 401. Electron injects the same header at the network layer, so
 * this helper is a no-op there when sessionStorage has no webapp grant.
 */

export const HERMES_SESSION_HEADER = "X-Hermes-Session-Token";
export const WEBAPP_SESSION_KEY_PREFIX = "hermes.webapp.session.v1:";

/**
 * @param {object=} options
 * @returns {string}
 */
export function readHermesWebappSessionToken(options = {}) {
  const store =
    options.sessionStorage !== undefined
      ? options.sessionStorage
      : typeof globalThis.sessionStorage !== "undefined"
        ? globalThis.sessionStorage
        : null;
  if (!store || typeof store.length !== "number") return "";
  try {
    for (let i = 0; i < store.length; i += 1) {
      const key = store.key(i);
      if (typeof key === "string" && key.startsWith(WEBAPP_SESSION_KEY_PREFIX)) {
        const value = store.getItem(key);
        if (typeof value === "string" && value.trim()) return value.trim();
      }
    }
  } catch (_err) {
    return "";
  }
  return "";
}

/**
 * @param {object=} options
 * @returns {Record of string to string}
 */
export function hermesHostAuthHeaders(options = {}) {
  const token = readHermesWebappSessionToken(options);
  if (!token) return {};
  return { [HERMES_SESSION_HEADER]: token };
}
