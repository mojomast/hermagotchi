import { useEffect, useRef, useState } from "react";
import { jsx } from "react/jsx-runtime";
import { buildPreviewLayers } from "../logic/shop.js";
import { joinAssetUrl, resolveAnimPalette, speciesBodyPath } from "../logic/assets.js";
import {
  contract,
  createPlayer,
  findClip,
  resolveAnimState,
} from "../../anim/petAnimPlayer.js";

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

function stripStyle(url, clip, frameIndex) {
  const count = Math.max(
    1,
    Number(clip && clip.frame_count) ||
      (clip && Array.isArray(clip.frames) ? clip.frames.length : 1)
  );
  const countSafe = Math.max(1, count);
  const pos =
    countSafe > 1
      ? (Math.max(0, Math.min(frameIndex, countSafe - 1)) / (countSafe - 1)) * 100
      : 0;
  return {
    position: "absolute",
    inset: "0",
    width: "100%",
    height: "100%",
    backgroundImage: "url(" + JSON.stringify(url) + ")",
    backgroundRepeat: "no-repeat",
    backgroundSize: String(countSafe * 100) + "% 100%",
    backgroundPosition: String(pos) + "% 0%",
    imageRendering: "pixelated",
    zIndex: "0",
    pointerEvents: "none",
  };
}

function followAnchors() {
  const list =
    contract &&
    contract.cosmetics &&
    Array.isArray(contract.cosmetics.follow_anchor_delta)
      ? contract.cosmetics.follow_anchor_delta
      : [];
  return list.map((value) => String(value));
}

function withAnchorDelta(layer, delta, anchors, frameScale) {
  const anchor = String(layer.anchor || layer.slot || "");
  if (!anchors.includes(anchor)) return layer;
  const offset = Array.isArray(layer.offsetPx) ? layer.offsetPx : [0, 0];
  return Object.assign({}, layer, {
    offsetPx: [
      (Number(offset[0]) || 0) + (Number(delta[0]) || 0) * frameScale,
      (Number(offset[1]) || 0) + (Number(delta[1]) || 0) * frameScale,
    ],
  });
}

/**
 * Layered, read-only pet preview. The species base always resolves from the
 * manifest (or the px3 convention) and animation clips come from
 * manifest.animations.clips via the shared petAnimPlayer clock.
 */
export function PetPreview(props = {}) {
  const pet = props.pet || null;
  const manifest = props.manifest || props.assetManifest || null;
  const assetBaseUrl = props.assetBaseUrl || props.asset_base_url || "";
  const species = pet && pet.species ? String(pet.species) : "";
  const rawPalette =
    props.palette ||
    (pet &&
      pet.appearance &&
      pet.appearance.traits &&
      pet.appearance.traits.palette) ||
    (pet && pet.appearance && pet.appearance.palette) ||
    (pet && pet.palette) ||
    "";
  const palette = resolveAnimPalette(rawPalette || "teal");
  const layers = buildPreviewLayers({
    pet: pet,
    loadout: props.loadout,
    catalog: props.catalog,
    manifest: manifest,
    assetBaseUrl: assetBaseUrl,
  });

  let baseLayer = null;
  const itemLayers = [];
  for (const layer of layers) {
    if (layer.kind === "base" && !baseLayer) {
      baseLayer = layer;
    } else {
      itemLayers.push(layer);
    }
  }
  if (!baseLayer && species) {
    const path = speciesBodyPath(manifest, pet);
    baseLayer = {
      kind: "base",
      id: "species." + species,
      slot: "body",
      label: (pet && pet.name) || "Pet",
      url: joinAssetUrl(assetBaseUrl, path),
      z: 0,
      scale: 1,
      offsetPx: [0, 0],
      anchor: "ground",
    };
  }

  const clips = Array.isArray(props.clips)
    ? props.clips
    : manifest &&
        manifest.animations &&
        Array.isArray(manifest.animations.clips)
      ? manifest.animations.clips
      : null;
  const requestedState =
    props.animState ||
    (props.petState ? resolveAnimState(props.petState) : "");
  const clip =
    species && clips && requestedState
      ? findClip(clips, { species: species, palette: palette, state: requestedState })
      : null;
  const animated = Boolean(clip && baseLayer && baseLayer.url);

  const [frameIndex, setFrameIndex] = useState(0);
  const [anchorDelta, setAnchorDelta] = useState([0, 0]);
  const [auraFrame, setAuraFrame] = useState(0);
  const playerRef = useRef(null);
  const clipId = clip ? String(clip.id || clip.path || "") : "";

  useEffect(
    function () {
      if (!clip) {
        playerRef.current = null;
        setFrameIndex(0);
        setAnchorDelta([0, 0]);
        setAuraFrame(0);
        return undefined;
      }
      const player = createPlayer(clip);
      playerRef.current = player;
      setFrameIndex(player.frameIndex);
      setAnchorDelta(player.anchorDelta);
      setAuraFrame(player.auraFrame);
      if (typeof requestAnimationFrame !== "function") {
        return function () {
          playerRef.current = null;
        };
      }
      let raf = 0;
      let last = null;
      let stopped = false;
      function step(now) {
        if (stopped) return;
        const time = typeof now === "number" ? now : Date.now();
        if (last === null) last = time;
        const deltaMs = Math.max(0, time - last);
        last = time;
        player.tick(deltaMs);
        setFrameIndex(player.frameIndex);
        setAnchorDelta(player.anchorDelta);
        setAuraFrame(player.auraFrame);
        if (!(player.done && !clip.loop)) {
          raf = requestAnimationFrame(step);
        }
      }
      raf = requestAnimationFrame(step);
      return function () {
        stopped = true;
        if (typeof cancelAnimationFrame === "function") {
          cancelAnimationFrame(raf);
        }
        playerRef.current = null;
      };
    },
    [clipId]
  );

  if (!baseLayer && itemLayers.length === 0) {
    return jsx("div", {
      className: "hg-sprite hg-sprite--empty",
      role: "img",
      "aria-label": props.label || "Pet preview",
      "data-preview-empty": "true",
      style: { width: props.size || "100%", height: props.size || "100%" },
      children: "?",
    });
  }

  const label =
    props.label ||
    (pet && pet.name ? pet.name + " preview" : "Pet preview");
  const spriteSize = props.size || "100%";
  const anchors = followAnchors();
  const numericSize = parseFloat(spriteSize);
  const nativeSize = Number(contract && contract.native_size) || 32;
  const frameScale =
    Number.isFinite(numericSize) && numericSize > 0
      ? numericSize / nativeSize
      : 1;

  const children = [];
  if (animated) {
    const stripUrl = joinAssetUrl(assetBaseUrl, clip.path || "") || baseLayer.url;
    children.push(
      jsx(
        "div",
        {
          className: "hg-sprite__base hg-sprite__base--anim",
          "data-layer-kind": "base",
          "data-layer-id": baseLayer.id,
          "data-layer-slot": "body",
          "data-anim-state": requestedState,
          "data-frame-index": String(frameIndex),
          "data-strip-path": clip.path || "",
          "aria-hidden": "true",
          style: stripStyle(stripUrl, clip, frameIndex),
        },
        "anim:" + baseLayer.id
      )
    );
  } else if (baseLayer) {
    children.push(
      jsx(
        "img",
        {
          className: "hg-sprite__layer hg-sprite__base",
          src: baseLayer.url,
          alt: label,
          "data-layer-kind": "base",
          "data-layer-id": baseLayer.id,
          "data-layer-slot": "body",
          loading: "lazy",
          decoding: "async",
          draggable: "false",
          style: layerStyle(baseLayer),
        },
        "base:" + baseLayer.id
      )
    );
  }

  for (const layer of itemLayers) {
    const adjusted = animated
      ? withAnchorDelta(layer, anchorDelta, anchors, frameScale)
      : layer;
    children.push(
      jsx(
        "img",
        {
          className: "hg-sprite__layer",
          src: layer.url,
          alt: "",
          "aria-hidden": "true",
          "data-layer-kind": layer.kind,
          "data-layer-id": layer.id,
          "data-layer-slot": layer.slot,
          "data-aura-frame":
            animated && layer.slot === "aura" ? String(auraFrame) : undefined,
          loading: "lazy",
          decoding: "async",
          draggable: "false",
          style: layerStyle(adjusted),
        },
        layer.kind + ":" + layer.id
      )
    );
  }

  return jsx("div", {
    className: "hg-sprite",
    role: "img",
    "aria-label": label,
    "data-pet-id": (pet && pet.id) || undefined,
    "data-anim-state": animated ? requestedState : undefined,
    "data-sprite-mode": animated ? "anim" : "static",
    style: {
      position: "relative",
      width: spriteSize,
      height: spriteSize,
      isolation: "isolate",
    },
    children: children,
  });
}
