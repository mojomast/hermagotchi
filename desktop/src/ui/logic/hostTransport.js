/**
 * Host transport for Hermagotchi UI calls.
 *
 * The pane never reads, stores, or attaches a Hermes host credential itself.
 * It routes every bridge call through a host-sanctioned door instead:
 *
 * - Desktop / Webapp pane: `ctx.rest(path, opts)` from the Desktop plugin SDK
 *   (Hermes >= 0.23.0). Paths are relative to `/api/plugins/hermagotchi`; the
 *   host attaches its own grant. Responses are parsed JSON.
 * - Web dashboard tab: `SDK.authedFetch(url, init)` from
 *   `window.__HERMES_PLUGIN_SDK__`, which handles host auth in both modes.
 *
 * With neither installed (unit tests, a bare browser), calls fall back to a
 * plain `fetch` with no host credential attached.
 */

let current = null;

/** @param {{ rest?: Function, authedFetch?: Function } | null} transport */
export function setHostTransport(transport) {
  if (!transport || typeof transport !== "object") {
    current = null;
    return;
  }
  const next = {};
  if (typeof transport.rest === "function") next.rest = transport.rest;
  if (typeof transport.authedFetch === "function") {
    next.authedFetch = transport.authedFetch;
  }
  current = next.rest || next.authedFetch ? next : null;
}

export function getHostTransport() {
  return current;
}

/** Dashboard SDK door, if this code runs inside the Hermes web dashboard. */
export function dashboardSdkTransport(sdk) {
  const source =
    sdk !== undefined
      ? sdk
      : typeof globalThis !== "undefined"
        ? globalThis.__HERMES_PLUGIN_SDK__
        : undefined;
  if (source && typeof source.authedFetch === "function") {
    return { authedFetch: source.authedFetch };
  }
  return null;
}

/** Decode base64 into bytes without touching any host state. */
export function base64ToBytes(b64) {
  const text = typeof b64 === "string" ? b64 : "";
  if (typeof atob === "function") {
    const bin = atob(text);
    const out = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i += 1) out[i] = bin.charCodeAt(i);
    return out;
  }
  if (typeof Buffer !== "undefined") {
    return Uint8Array.from(Buffer.from(text, "base64"));
  }
  return new Uint8Array(0);
}
