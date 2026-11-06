import { jsx } from "react/jsx-runtime";
import { buildPreviewLayers } from "../logic/shop.js";

function layerStyle(layer) {
  const offset = Array.isArray(layer.offsetPx) ? layer.offsetPx : [0, 0];
  const scale = Number(layer.scale) > 0 ? Number(layer.scale) : 1;
  return {
    position: "absolute",
    inset: "0",
    width: "100%",
    height: "100%",
    objectFit: "contain",
    zIndex: String(layer.z),
    transform:
      "translate(" +
      (Number(offset[0]) || 0) +
      "px, " +
      (Number(offset[1]) || 0) +
      "px) scale(" +
      scale +
      ")",
    transformOrigin: "center",
    pointerEvents: "none",
  };
}

/**
 * Layered, read-only pet preview. Layer order comes from the asset manifest's
 * z values (with a documented slot fallback), never from a hardcoded item list.
 */
export function PetPreview(props = {}) {
  const layers = buildPreviewLayers({
    pet: props.pet,
    loadout: props.loadout,
    catalog: props.catalog,
    manifest: props.manifest,
    assetBaseUrl: props.assetBaseUrl || props.asset_base_url,
  });
  const label =
    props.label ||
    (props.pet && props.pet.name ? props.pet.name + " preview" : "Pet preview");
  const spriteSize = props.size || "256px";

  if (layers.length === 0) {
    return jsx("div", {
      className: "hg-sprite hg-sprite--empty",
      role: "img",
      "aria-label": label,
      "data-preview-empty": "true",
      style: { width: spriteSize, height: spriteSize },
      children: "?",
    });
  }

  return jsx("div", {
    className: "hg-sprite",
    role: "img",
    "aria-label": label,
    "data-pet-id": (props.pet && props.pet.id) || undefined,
    style: {
      position: "relative",
      width: spriteSize,
      height: spriteSize,
      isolation: "isolate",
    },
    children: layers.map((layer) =>
      jsx(
        "img",
        {
          className:
            "hg-sprite__layer" +
            (layer.kind === "base" ? " hg-sprite__base" : ""),
          src: layer.url,
          alt: layer.kind === "base" ? label : "",
          "aria-hidden": layer.kind === "base" ? undefined : "true",
          "data-layer-kind": layer.kind,
          "data-layer-id": layer.id,
          "data-layer-slot": layer.slot,
          loading: "lazy",
          decoding: "async",
          draggable: "false",
          style: layerStyle(layer),
        },
        layer.kind + ":" + layer.id
      )
    ),
  });
}
