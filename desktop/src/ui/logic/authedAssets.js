/**
 * Resolve plugin asset URLs through authenticated fetch into blob:/data: URLs.
 *
 * Hermes dashboard/webapp auth puts the session on fetch headers (or cookies),
 * but bare img tag / CSS background-image requests omit those headers and
 * 401. Fetching via the same window.fetch the pane already patches, then
 * swapping in an object URL, keeps non-secret art loading without weakening
 * the host auth gate.
 */

const cache = new Map();

function isInlineUrl(value) {
  return typeof value === "string" && /^(?:data:|blob:)/i.test(value);
}

function fetchImpl() {
  if (typeof globalThis.fetch === "function") return globalThis.fetch.bind(globalThis);
  return null;
}

/**
 * @param {string} url
 * @param {{ fetchImpl?: typeof fetch }=} options
 * @returns {Promise of string}
 */
export function resolveAuthedAssetUrl(url, options = {}) {
  if (typeof url !== "string") return Promise.resolve("");
  const trimmed = url.trim();
  if (!trimmed) return Promise.resolve("");
  if (isInlineUrl(trimmed)) return Promise.resolve(trimmed);

  const existing = cache.get(trimmed);
  if (existing) return existing.promise;

  const fetchFn = options.fetchImpl || fetchImpl();
  if (!fetchFn) {
    // No fetch available (SSR / node without polyfill): keep the raw URL.
    return Promise.resolve(trimmed);
  }

  const entry = { objectUrl: null, promise: null };
  entry.promise = Promise.resolve()
    .then(() =>
      fetchFn(trimmed, {
        method: "GET",
        credentials: "same-origin",
        cache: "force-cache",
      })
    )
    .then((response) => {
      if (!response || !response.ok) {
        const status = response && response.status;
        throw new Error("asset_fetch_failed:" + String(status || "network"));
      }
      return response.blob();
    })
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
