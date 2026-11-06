import { jsx, jsxs } from "react/jsx-runtime";
import { npcHostLine } from "../npcLines.js";

/** Display-only NPC quip strip for a Desktop tab. */
export function NpcHostBanner(props = {}) {
  const surface = props.surface;
  const host = props.host || (surface ? npcHostLine(surface) : null);
  if (!host || !host.line) return null;
  return jsxs("aside", {
    className: "hg-npc-host",
    "data-npc-id": host.id,
    "data-npc-context": host.context,
    "data-display-only": "true",
    children: [
      jsx("strong", { className: "hg-npc-host__name", children: host.name }),
      jsx("p", {
        className: "hg-npc-host__line",
        children: host.line,
      }),
    ],
  });
}
