/**
 * Resolve plugin asset URLs into blob:/data: URLs through the host's own door.
 *
 * Bare img tags / CSS background-image requests carry no host auth and 401.
 * Instead of reading any host token, we load art through:
 * - Desktop: `ctx.rest('/assets-data/{path}')` (JSON `{mime, data_b64}`),
 * - Dashboard: the SDK's `authedFetch(url)`,
 * then swap in an object URL. Nothing here sees a credential.
 */

import { isInlineAssetUrl, isRemoteAssetUrl } from "./assets.js";
import { base64ToBytes, getHostTransport } from "./hostTransport.js";

const ASSET_MARKER = "/assets/";

/** Relative asset path for the bridge's `/assets-data/` route. */
export function assetDataPath(url) {
  const at = url.indexOf(ASSET_MARKER);
  if (at === -1) return "";
  const rel = url.slice(at + ASSET_MARKER.length).split(/[?#]/, 1)[0];
  if (!rel || rel.split("/").includes("..")) return "";
  return "/assets-data/" + rel;
}

function loadViaRest(rest, url) {
  const path = assetDataPath(url);
  if (!path) return Promise.reject(new Error("asset_path_invalid"));
  return Promise.resolve(rest(path, { method: "GET" })).then((payload) => {
    if (!payload || payload.ok !== true || typeof payload.data_b64 !== "string") {
      throw new Error("asset_fetch_failed:rest");
    }
    return new Blob([base64ToBytes(payload.data_b64)], {
      type: payload.mime || "application/octet-stream",
    });
  });
}

function loadViaFetch(fetchFn, url) {
  return Promise.resolve(
    fetchFn(url, { method: "GET", credentials: "same-origin", cache: "force-cache" })
  ).then((response) => {
    if (!response || !response.ok) {
      const status = response && response.status;
      throw new Error("asset_fetch_failed:" + String(status || "network"));
    }
    return response.blob();
  });
}

const cache = new Map();

function isInlineUrl(value) {
  return isInlineAssetUrl(value);
}

/**
 * Dashboard authedFetch may only be pointed at a same-origin plugin assets
 * route. Absolute http(s) URLs (and anything else with a scheme other than
 * data:/blob:) are rejected so the Hermes session token cannot leave the host.
 */
export function isAuthedFetchSafeUrl(url) {
  if (typeof url !== "string") return false;
  const trimmed = url.trim();
  if (!trimmed || isInlineUrl(trimmed) || isRemoteAssetUrl(trimmed)) return false;
  if (!trimmed.startsWith("/") || trimmed.startsWith("//")) return false;
  if (trimmed.split("/").includes("..")) return false;
  const path = trimmed.split(/[?#]/, 1)[0];
  return /\/assets(?:-data)?(?:\/|$)/.test(path);
}

function fetchImpl() {
  if (typeof globalThis.fetch === "function") return globalThis.fetch.bind(globalThis);
  return null;
}

/**
 * @param {string} url
 * @param {object=} options
 * @returns {Promise of string}
 */
export function resolveAuthedAssetUrl(url, options = {}) {
  if (typeof url !== "string") return Promise.resolve("");
  const trimmed = url.trim();
  if (!trimmed) return Promise.resolve("");
  if (isInlineUrl(trimmed)) return Promise.resolve(trimmed);
  // Never hand an absolute or otherwise off-route URL to authedFetch.
  if (!isAuthedFetchSafeUrl(trimmed)) return Promise.resolve("");

  const existing = cache.get(trimmed);
  if (existing) return existing.promise;

  const host = getHostTransport();
  const rest = options.rest || (!options.fetchImpl && host && host.rest) || null;
  const fetchFn =
    options.fetchImpl ||
    options.authedFetch ||
    (host && host.authedFetch) ||
    fetchImpl();
  if (!rest && !fetchFn) {
    // No fetch available (SSR / node without polyfill): do not return a
    // remote URL that a later image tag could request unauthenticated, and do
    // not invent a same-origin load. Callers retry when a transport exists.
    return Promise.resolve("");
  }

  const entry = { objectUrl: null, promise: null };
  entry.promise = Promise.resolve()
    .then(() => (rest ? loadViaRest(rest, trimmed) : loadViaFetch(fetchFn, trimmed)))
    .then((blob) => {
      if (typeof URL !== "undefined" && typeof URL.createObjectURL === "function") {
        entry.objectUrl = URL.createObjectURL(blob);
        return entry.objectUrl;
      }
      // Extremely constrained hosts: fall back to the original URL.
      return trimmed;
    })
    .catch(() => {
      // Drop the failed cache entry so a later retry can try again.
      if (cache.get(trimmed) === entry) cache.delete(trimmed);
      return "";
    });

  cache.set(trimmed, entry);
  return entry.promise;
}

/** Test helper: clear the in-memory blob cache (revokes object URLs). */
export function clearAuthedAssetCache() {
  for (const entry of cache.values()) {
    if (entry.objectUrl && typeof URL !== "undefined" && URL.revokeObjectURL) {
      try {
        URL.revokeObjectURL(entry.objectUrl);
      } catch (_err) {
        /* ignore */
      }
    }
  }
  cache.clear();
}

export function authedAssetCacheSize() {
  return cache.size;
}
