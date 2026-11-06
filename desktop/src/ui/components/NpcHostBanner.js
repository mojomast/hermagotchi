import { jsx, jsxs } from "react/jsx-runtime";
import { npcHostLine } from "../npcLines.js";
import { joinAssetUrl, npcPortraitPath } from "../logic/assets.js";

/** Display-only NPC quip strip for a Desktop tab. */
export function NpcHostBanner(props = {}) {
  const surface = props.surface;
  const host = props.host || (surface ? npcHostLine(surface) : null);
  if (!host || !host.line) return null;
  const assetBaseUrl = props.assetBaseUrl || props.asset_base_url || "";
  const portrait = npcPortraitPath(host.id);
  const portraitUrl =
    portrait && assetBaseUrl ? joinAssetUrl(assetBaseUrl, portrait) : "";
  return jsxs("aside", {
    className: "hg-npc-host",
    "data-npc-id": host.id,
    "data-npc-context": host.context,
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
            width: 56,
            height: 56,
          })
        : null,
      jsx("strong", { className: "hg-npc-host__name", children: host.name }),
      jsx("p", {
        className: "hg-npc-host__line",
        children: host.line,
      }),
    ],
  });
}
