import { useEffect, useState } from "react";
import { jsx } from "react/jsx-runtime";
import { resolveAuthedAssetUrl } from "../logic/authedAssets.js";

/**
 * Hook: resolve a plugin asset URL through authenticated fetch → blob/data URL.
 * Returns { url, status } where status is idle | loading | ready | error.
 */
export function useAuthedAssetUrl(src) {
  const inline =
    typeof src === "string" && /^(?:data:|blob:)/i.test(src) ? src : "";
  const [state, setState] = useState(function () {
    if (!src || typeof src !== "string" || !src.trim()) {
      return { url: "", status: "idle" };
    }
    if (inline) return { url: inline, status: "ready" };
    return { url: "", status: "loading" };
  });

  useEffect(
    function () {
      let cancelled = false;
      if (typeof src !== "string" || !src.trim()) {
        setState({ url: "", status: "idle" });
        return undefined;
      }
      if (/^(?:data:|blob:)/i.test(src)) {
        setState({ url: src, status: "ready" });
        return undefined;
      }
      setState({ url: "", status: "loading" });
      resolveAuthedAssetUrl(src).then(function (url) {
        if (cancelled) return;
        if (!url) {
          setState({ url: "", status: "error" });
          return;
        }
        setState({ url: url, status: "ready" });
      });
      return function () {
        cancelled = true;
      };
    },
    [src]
  );
  return state;
}

/**
 * img element that loads plugin assets through authenticated fetch → blob URL.
 * Pass-through for data:/blob: sources. While pending (or on failure) renders
 * `placeholder` (default null).
 */
export function AuthedImg(props = {}) {
  const src = typeof props.src === "string" ? props.src : "";
  const placeholder = Object.prototype.hasOwnProperty.call(props, "placeholder")
    ? props.placeholder
    : null;
  const { url, status } = useAuthedAssetUrl(src);

  useEffect(
    function () {
      if (status !== "error") return;
      if (typeof props.onResolveError === "function") {
        try {
          props.onResolveError();
        } catch (_err) {
          /* ignore */
        }
      }
    },
    [status, props.onResolveError]
  );

  if (status !== "ready" || !url) return placeholder;

  const imgProps = Object.assign({}, props);
  delete imgProps.placeholder;
  delete imgProps.onResolveError;
  imgProps.src = url;
  return jsx("img", imgProps);
}
