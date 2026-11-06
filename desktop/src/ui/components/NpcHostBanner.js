import { jsx, jsxs } from "react/jsx-runtime";
import { npcHostLine } from "../npcLines.js";
import { joinAssetUrl, npcPortraitPath } from "../logic/assets.js";

const PORTRAIT_PX = Object.freeze({
  featured: 180,
  compact: 64,
});

function resolveAssetBase(props) {
  const direct = props.assetBaseUrl || props.asset_base_url || "";
  if (direct) return direct;
  const api = props.api;
  if (api && api.assets && typeof api.assets.url === "function") {
    try {
      return api.assets.url("") || "";
    } catch (_err) {
      return "";
    }
  }
  return "";
}

/** Display-only NPC host panel for a Desktop tab (or compact lobby rail). */
export function NpcHostBanner(props = {}) {
  const surface = props.surface;
  const host = props.host || (surface ? npcHostLine(surface) : null);
  if (!host || !host.line) return null;
  const size = props.size === "compact" ? "compact" : "featured";
  const px = PORTRAIT_PX[size];
  const assetBaseUrl = resolveAssetBase(props);
  const portrait = npcPortraitPath(host.id);
  const portraitUrl =
    portrait && assetBaseUrl ? joinAssetUrl(assetBaseUrl, portrait) : "";
  return jsxs("aside", {
    className:
      size === "compact"
        ? "hg-npc-host hg-npc-host--compact"
        : "hg-npc-host hg-npc-host--featured",
    "data-npc-id": host.id,
    "data-npc-context": host.context,
    "data-npc-size": size,
    "data-display-only": "true",
    children: [
      portraitUrl
        ? jsx("img", {
            className: "hg-npc-host__portrait",
            src: portraitUrl,
            alt: "",
            "aria-hidden": "true",
            loading: "lazy",
            decoding: "async",
            draggable: "false",
            width: px,
            height: px,
          })
        : jsx("span", {
            className: "hg-npc-host__portrait hg-npc-host__portrait--empty",
            "aria-hidden": "true",
          }),
      jsxs("div", {
        className: "hg-npc-host__speech",
        children: [
          jsx("strong", { className: "hg-npc-host__name", children: host.name }),
          jsx("p", {
            className: "hg-npc-host__line",
            children: host.line,
          }),
        ],
      }),
    ],
  });
}
