/**
 * Standalone pet animation helper for Hermagotchi desktop.
 * Pane UI imports this; do not put React/UI here.
 *
 * Clip metadata lives in assets/manifest.launch-003.json → animations.clips
 * (also mirrored in art_ext). This module only needs the contract JSON + a
 * clip list (or fetch of the manifest animations block).
 */

import contract from './petAnimContract.json';

/** @typedef {{ i:number, anchor_delta:number[], duration_ms?:number }} AnimFrame */
/** @typedef {{ id:string, species:string, palette:string, state:string, path:string, frame_count:number, fps:number, loop:boolean, frames:AnimFrame[] }} AnimClip */

export function resolveAnimState(petState) {
  if (!petState) return 'idle';
  const key = String(petState).toLowerCase();
  return contract.state_from_pet[key] || (contract.states.includes(key) ? key : 'idle');
}

export function clipId(species, palette, state) {
  return `${species}.${palette}.${state}`;
}

/**
 * @param {AnimClip[]} clips
 * @param {{species:string, palette:string, state?:string, petState?:string}} query
 * @returns {AnimClip|null}
 */
export function findClip(clips, { species, palette, state, petState }) {
  const st = state || resolveAnimState(petState);
  const id = clipId(species, palette, st);
  return clips.find((c) => c.id === id) || null;
}

/**
 * Mutable player clock. Call tick(dtMs) from rAF.
 * @param {AnimClip} clip
 */
export function createPlayer(clip) {
  let elapsed = 0;
  let index = 0;
  let done = false;
  const frameMs = () => {
    const fr = clip.frames?.[index];
    if (fr?.duration_ms) return fr.duration_ms;
    return 1000 / (clip.fps || 6);
  };
  return {
    get frameIndex() { return index; },
    get done() { return done; },
    get anchorDelta() {
      const fr = clip.frames?.[index];
      return fr?.anchor_delta ? [...fr.anchor_delta] : [0, 0];
    },
    get auraFrame() {
      // auras keep independent 2-frame cycle by wall time
      return Math.floor(elapsed / frameMs()) % (contract.cosmetics.aura_frame_cycle || 2);
    },
    reset() { elapsed = 0; index = 0; done = false; },
    tick(dtMs) {
      if (done) return index;
      elapsed += dtMs;
      while (elapsed >= frameMs()) {
        elapsed -= frameMs();
        if (index + 1 >= clip.frame_count) {
          if (clip.loop) index = 0;
          else { done = true; break; }
        } else {
          index += 1;
        }
      }
      return index;
    },
    /** Source rect into a horizontal strip (native px). */
    sourceRect(native = 32) {
      return { x: index * native, y: 0, w: native, h: native };
    },
  };
}

export { contract };
