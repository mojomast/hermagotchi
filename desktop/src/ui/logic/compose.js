/**
 * Pure cosmetic composition math for the Hermagotchi desktop preview.
 *
 * Mirrors scripts/asset_px3_compose.py::_item: an item layer is centred on its
 * species anchor (head / face / back / front / hand / ground) plus the
 * manifest offset, per-species transform (dx, dy, scale) and item scale.
 *
 * No React and no filesystem access: composeAnchors.json is embedded below so
 * the browser never has to fetch Python-side art data.
 */

export const DEFAULT_NATIVE_SIZE = 32;
export const DEFAULT_PIXEL_FACTOR = 16;

/** Slim launch-003 snapshot generated from assets/art_ext.launch-003.json. */
export const EMBEDDED_ANCHORS = Object.freeze({"schema":"hermagotchi-compose-anchors-v1","asset_pack_id":"launch-003","pixel_factor":16,"native_size":32,"species":{"byteblob":{"anchors_native":{"head":[16,11],"face":[16,16],"back":[16,17],"front":[16,23],"ground":[16,28],"hand":[19,23]},"item_scale":1.0},"patchfox":{"anchors_native":{"head":[15,11],"face":[15,15],"back":[15,20],"front":[15,18],"ground":[16,28],"hand":[18,18]},"item_scale":1.0},"nullgeist":{"anchors_native":{"head":[16,9],"face":[16,13],"back":[16,16],"front":[16,19],"ground":[16,28],"hand":[19,19]},"item_scale":1.0},"kernelcrab":{"anchors_native":{"head":[16,13],"face":[16,17],"back":[16,19],"front":[16,21],"ground":[16,28],"hand":[24,18]},"item_scale":1.0},"cachebat":{"anchors_native":{"head":[16,12],"face":[16,15],"back":[16,16],"front":[16,18],"ground":[16,28],"hand":[22,17]},"item_scale":1.0},"stacktoise":{"anchors_native":{"head":[16,7],"face":[16,13],"back":[16,16],"front":[16,19],"ground":[16,28],"hand":[19,19]},"item_scale":1.0},"daemowl":{"anchors_native":{"head":[15,8],"face":[15,13],"back":[15,16],"front":[15,19],"ground":[16,28],"hand":[18,19]},"item_scale":1.0},"shellsnail":{"anchors_native":{"head":[10,15],"face":[10,18],"back":[16,20],"front":[16,22],"ground":[16,28],"hand":[10,22]},"item_scale":1.0},"regexopus":{"anchors_native":{"head":[15,9],"face":[15,14],"back":[15,17],"front":[15,19],"ground":[16,28],"hand":[18,19]},"item_scale":1.0},"firewyrm":{"anchors_native":{"head":[15,7],"face":[15,13],"back":[15,16],"front":[15,19],"ground":[16,28],"hand":[20,18]},"item_scale":1.0}},"items":{"aura.data_orbit":{"slot":"aura","z":-30,"anchor":"front","offset_px":[0,0],"scale":1.25,"per_species":{"byteblob":[0,-8,1.0],"patchfox":[1,-3,1.0],"nullgeist":[0,-4,1.0],"kernelcrab":[0,-6,1.0],"cachebat":[0,-3,1.0],"stacktoise":[0,-4,1.0],"daemowl":[1,-4,1.0],"shellsnail":[0,-7,1.0],"regexopus":[1,-4,1.0],"firewyrm":[1,-4,1.0]}},"aura.ember_halo":{"slot":"aura","z":-30,"anchor":"face","offset_px":[0,0],"scale":1.25,"per_species":{"byteblob":[0,-1,1.0],"patchfox":[1,0,1.0],"nullgeist":[0,2,1.0],"kernelcrab":[0,-2,1.0],"cachebat":[0,0,1.0],"stacktoise":[0,2,1.0],"daemowl":[1,2,1.0],"shellsnail":[6,-3,1.0],"regexopus":[1,1,1.0],"firewyrm":[1,2,1.0]}},"aura.flame_wall":{"slot":"aura","z":-30,"anchor":"face","offset_px":[0,0],"scale":1.25,"per_species":{"byteblob":[-1,-1,1.0],"patchfox":[0,0,1.0],"nullgeist":[-1,2,1.0],"kernelcrab":[-1,-2,1.0],"cachebat":[-1,0,1.0],"stacktoise":[-1,2,1.0],"daemowl":[0,2,1.0],"shellsnail":[5,-3,1.0],"regexopus":[0,1,1.0],"firewyrm":[0,2,1.0]}},"aura.ghost_cache":{"slot":"aura","z":-30,"anchor":"face","offset_px":[0,0],"scale":1.25,"per_species":{"byteblob":[-1,-1,1.0],"patchfox":[0,0,1.0],"nullgeist":[-1,2,1.0],"kernelcrab":[-1,-2,1.0],"cachebat":[-1,0,1.0],"stacktoise":[-1,2,1.0],"daemowl":[0,2,1.0],"shellsnail":[5,-3,1.0],"regexopus":[0,1,1.0],"firewyrm":[0,2,1.0]}},"aura.heart_beat":{"slot":"aura","z":-30,"anchor":"face","offset_px":[0,0],"scale":1.25,"per_species":{"byteblob":[-1,-1,1.0],"patchfox":[0,0,1.0],"nullgeist":[-1,2,1.0],"kernelcrab":[-1,-2,1.0],"cachebat":[-1,0,1.0],"stacktoise":[-1,2,1.0],"daemowl":[0,2,1.0],"shellsnail":[5,-3,1.0],"regexopus":[0,1,1.0],"firewyrm":[0,2,1.0]}},"aura.hex_shield":{"slot":"aura","z":-30,"anchor":"face","offset_px":[0,0],"scale":1.25,"per_species":{"byteblob":[-1,-1,1.0],"patchfox":[0,0,1.0],"nullgeist":[-1,2,1.0],"kernelcrab":[-1,-2,1.0],"cachebat":[-1,0,1.0],"stacktoise":[-1,2,1.0],"daemowl":[0,2,1.0],"shellsnail":[5,-3,1.0],"regexopus":[0,1,1.0],"firewyrm":[0,2,1.0]}},"aura.leaf_orbit":{"slot":"aura","z":-30,"anchor":"face","offset_px":[0,0],"scale":1.25,"per_species":{"byteblob":[-1,-1,1.0],"patchfox":[0,0,1.0],"nullgeist":[-1,2,1.0],"kernelcrab":[-1,-2,1.0],"cachebat":[-1,0,1.0],"stacktoise":[-1,2,1.0],"daemowl":[0,2,1.0],"shellsnail":[5,-3,1.0],"regexopus":[0,1,1.0],"firewyrm":[0,2,1.0]}},"aura.ping_pulse":{"slot":"aura","z":-30,"anchor":"face","offset_px":[0,0],"scale":1.25,"per_species":{"byteblob":[-1,-1,1.0],"patchfox":[0,0,1.0],"nullgeist":[-1,2,1.0],"kernelcrab":[-1,-2,1.0],"cachebat":[-1,0,1.0],"stacktoise":[-1,2,1.0],"daemowl":[0,2,1.0],"shellsnail":[5,-3,1.0],"regexopus":[0,1,1.0],"firewyrm":[0,2,1.0]}},"aura.rainbow_arc":{"slot":"aura","z":-30,"anchor":"face","offset_px":[0,0],"scale":1.25,"per_species":{"byteblob":[0,4,1.0],"patchfox":[1,5,1.0],"nullgeist":[0,7,1.0],"kernelcrab":[0,3,1.0],"cachebat":[0,5,1.0],"stacktoise":[0,7,1.0],"daemowl":[1,7,1.0],"shellsnail":[6,2,1.0],"regexopus":[1,6,1.0],"firewyrm":[1,7,1.0]}},"aura.snow_globe":{"slot":"aura","z":-30,"anchor":"face","offset_px":[0,0],"scale":1.25,"per_species":{"byteblob":[-1,-1,1.0],"patchfox":[0,0,1.0],"nullgeist":[-1,2,1.0],"kernelcrab":[-1,-2,1.0],"cachebat":[-1,0,1.0],"stacktoise":[-1,2,1.0],"daemowl":[0,2,1.0],"shellsnail":[5,-3,1.0],"regexopus":[0,1,1.0],"firewyrm":[0,2,1.0]}},"aura.spark_aura":{"slot":"aura","z":-30,"anchor":"face","offset_px":[0,0],"scale":1.0,"per_species":{"byteblob":[-1,0,1.0],"patchfox":[0,1,1.0],"nullgeist":[-1,3,1.0],"kernelcrab":[-1,-1,1.0],"cachebat":[-1,1,1.0],"stacktoise":[-1,3,1.0],"daemowl":[0,3,1.0],"shellsnail":[5,-2,1.0],"regexopus":[0,2,1.0],"firewyrm":[0,3,1.0]}},"aura.spark_trail":{"slot":"aura","z":-30,"anchor":"face","offset_px":[0,0],"scale":1.25,"per_species":{"byteblob":[-1,-1,1.0],"patchfox":[0,0,1.0],"nullgeist":[-1,2,1.0],"kernelcrab":[-1,-2,1.0],"cachebat":[-1,0,1.0],"stacktoise":[-1,2,1.0],"daemowl":[0,2,1.0],"shellsnail":[5,-3,1.0],"regexopus":[0,1,1.0],"firewyrm":[0,2,1.0]}},"aura.starfield":{"slot":"aura","z":-30,"anchor":"face","offset_px":[0,0],"scale":1.25,"per_species":{"byteblob":[-1,-1,1.0],"patchfox":[0,0,1.0],"nullgeist":[-1,2,1.0],"kernelcrab":[-1,-2,1.0],"cachebat":[-1,0,1.0],"stacktoise":[-1,2,1.0],"daemowl":[0,2,1.0],"shellsnail":[5,-3,1.0],"regexopus":[0,1,1.0],"firewyrm":[0,2,1.0]}},"aura.static_haze":{"slot":"aura","z":-30,"anchor":"face","offset_px":[0,0],"scale":1.25,"per_species":{"byteblob":[-1,-1,1.0],"patchfox":[0,0,1.0],"nullgeist":[-1,2,1.0],"kernelcrab":[-1,-2,1.0],"cachebat":[-1,0,1.0],"stacktoise":[-1,2,1.0],"daemowl":[0,2,1.0],"shellsnail":[5,-3,1.0],"regexopus":[0,1,1.0],"firewyrm":[0,2,1.0]}},"aura.virus_scan":{"slot":"aura","z":-30,"anchor":"face","offset_px":[0,0],"scale":1.25,"per_species":{"byteblob":[-1,-1,1.0],"patchfox":[0,0,1.0],"nullgeist":[-1,2,1.0],"kernelcrab":[-1,-2,1.0],"cachebat":[-1,0,1.0],"stacktoise":[-1,2,1.0],"daemowl":[0,2,1.0],"shellsnail":[5,-3,1.0],"regexopus":[0,1,1.0],"firewyrm":[0,2,1.0]}},"back.antenna_array":{"slot":"back","z":-10,"anchor":"back","offset_px":[0,0],"scale":1.0,"per_species":{"byteblob":[0,3,1.0],"patchfox":[0,3,1.0],"nullgeist":[0,3,1.0],"kernelcrab":[0,3,1.0],"cachebat":[0,3,1.0],"stacktoise":[0,3,1.0],"daemowl":[0,3,1.0],"shellsnail":[0,3,1.0],"regexopus":[0,3,1.0],"firewyrm":[0,3,1.0]}},"back.battery_pack":{"slot":"back","z":-10,"anchor":"back","offset_px":[0,0],"scale":1.0,"per_species":{"byteblob":[0,-3,1.0],"patchfox":[0,-3,1.0],"nullgeist":[0,-3,1.0],"kernelcrab":[0,-3,1.0],"cachebat":[0,-3,1.0],"stacktoise":[0,-3,1.0],"daemowl":[0,-3,1.0],"shellsnail":[0,-3,1.0],"regexopus":[0,-3,1.0],"firewyrm":[0,-3,1.0]}},"back.caped_crusader":{"slot":"back","z":-10,"anchor":"back","offset_px":[0,0],"scale":1.0,"per_species":{"byteblob":[0,-4,1.0],"patchfox":[0,-4,1.0],"nullgeist":[-1,-4,1.0],"kernelcrab":[0,-4,1.0],"cachebat":[0,-4,1.0],"stacktoise":[-1,-4,1.0],"daemowl":[0,-4,1.0],"shellsnail":[0,-4,1.0],"regexopus":[0,-4,1.0],"firewyrm":[-1,-4,1.0]}},"back.circuit_cape":{"slot":"back","z":-10,"anchor":"back","offset_px":[0,0],"scale":1.0,"per_species":{"byteblob":[0,-3,1.0],"patchfox":[0,-3,1.0],"nullgeist":[0,-3,1.0],"kernelcrab":[0,-3,1.0],"cachebat":[0,-3,1.0],"stacktoise":[0,-3,1.0],"daemowl":[0,-3,1.0],"shellsnail":[0,-3,1.0],"regexopus":[0,-3,1.0],"firewyrm":[0,-3,1.0]}},"back.circuit_wings":{"slot":"back","z":-10,"anchor":"back","offset_px":[0,0],"scale":1.0,"per_species":{"byteblob":[0,0,1.0],"patchfox":[0,0,1.0],"nullgeist":[0,0,1.0],"kernelcrab":[0,0,1.0],"cachebat":[0,0,1.0],"stacktoise":[0,0,1.0],"daemowl":[0,0,1.0],"shellsnail":[0,0,1.0],"regexopus":[0,0,1.0],"firewyrm":[0,0,1.0]}},"back.docker_whale":{"slot":"back","z":-10,"anchor":"back","offset_px":[0,0],"scale":1.0,"per_species":{"byteblob":[0,1,1.0],"patchfox":[0,1,1.0],"nullgeist":[0,1,1.0],"kernelcrab":[0,1,1.0],"cachebat":[0,1,1.0],"stacktoise":[0,1,1.0],"daemowl":[0,1,1.0],"shellsnail":[0,1,1.0],"regexopus":[0,1,1.0],"firewyrm":[0,1,1.0]}},"back.glider_cloak":{"slot":"back","z":-10,"anchor":"back","offset_px":[0,0],"scale":1.0,"per_species":{"byteblob":[0,-4,1.0],"patchfox":[0,-4,1.0],"nullgeist":[-1,-4,1.0],"kernelcrab":[0,-4,1.0],"cachebat":[0,-4,1.0],"stacktoise":[-1,-4,1.0],"daemowl":[0,-4,1.0],"shellsnail":[0,-4,1.0],"regexopus":[0,-4,1.0],"firewyrm":[-1,-4,1.0]}},"back.payload_pack":{"slot":"back","z":-10,"anchor":"back","offset_px":[0,0],"scale":1.0,"per_species":{"byteblob":[0,-3,1.0],"patchfox":[0,-3,1.0],"nullgeist":[0,-3,1.0],"kernelcrab":[0,-3,1.0],"cachebat":[0,-3,1.0],"stacktoise":[0,-3,1.0],"daemowl":[0,-3,1.0],"shellsnail":[0,-3,1.0],"regexopus":[0,-3,1.0],"firewyrm":[0,-3,1.0]}},"back.scroll_quiver":{"slot":"back","z":-10,"anchor":"back","offset_px":[0,0],"scale":1.0,"per_species":{"byteblob":[0,-2,1.0],"patchfox":[0,-2,1.0],"nullgeist":[0,-2,1.0],"kernelcrab":[0,-2,1.0],"cachebat":[0,-2,1.0],"stacktoise":[0,-2,1.0],"daemowl":[0,-2,1.0],"shellsnail":[0,-2,1.0],"regexopus":[0,-2,1.0],"firewyrm":[0,-2,1.0]}},"back.tiny_jetpack":{"slot":"back","z":-10,"anchor":"back","offset_px":[0,0],"scale":1.0,"per_species":{"byteblob":[0,0,1.0],"patchfox":[0,0,1.0],"nullgeist":[0,0,1.0],"kernelcrab":[0,0,1.0],"cachebat":[0,0,1.0],"stacktoise":[0,0,1.0],"daemowl":[0,0,1.0],"shellsnail":[0,0,1.0],"regexopus":[0,0,1.0],"firewyrm":[0,0,1.0]}},"back.webhook_wings":{"slot":"back","z":-10,"anchor":"back","offset_px":[0,0],"scale":1.0,"per_species":{"byteblob":[0,-2,1.0],"patchfox":[0,-2,1.0],"nullgeist":[0,-2,1.0],"kernelcrab":[0,-2,1.0],"cachebat":[0,-2,0.9],"stacktoise":[0,-2,1.0],"daemowl":[0,-2,1.0],"shellsnail":[0,-2,1.0],"regexopus":[0,-2,1.0],"firewyrm":[0,-2,1.0]}},"emote.heart_bubble":{"slot":"emote","z":50,"anchor":"head","offset_px":[128,-48],"scale":1.0,"per_species":{"byteblob":[0,0,1.0],"patchfox":[0,0,1.0],"nullgeist":[0,0,1.0],"kernelcrab":[0,0,1.0],"cachebat":[0,0,1.0],"stacktoise":[0,0,1.0],"daemowl":[0,0,1.0],"shellsnail":[0,0,1.0],"regexopus":[0,0,1.0],"firewyrm":[0,0,1.0]}},"emote.sparkle":{"slot":"emote","z":50,"anchor":"face","offset_px":[0,0],"scale":1.0,"per_species":{"byteblob":[0,0,1.0],"patchfox":[0,0,1.0],"nullgeist":[0,0,1.0],"kernelcrab":[0,0,1.0],"cachebat":[0,0,1.0],"stacktoise":[0,0,1.0],"daemowl":[0,0,1.0],"shellsnail":[0,0,1.0],"regexopus":[0,0,1.0],"firewyrm":[0,0,1.0]}},"face.bug_eye":{"slot":"face","z":20,"anchor":"face","offset_px":[0,0],"scale":1.0,"per_species":{"byteblob":[0,0,1.0],"patchfox":[0,0,1.0],"nullgeist":[0,0,1.0],"kernelcrab":[0,1,1.0],"cachebat":[0,0,1.0],"stacktoise":[0,0,1.0],"daemowl":[0,2,1.0],"shellsnail":[0,1,1.0],"regexopus":[0,0,1.0],"firewyrm":[0,0,1.0]}},"face.gold_monocle":{"slot":"face","z":20,"anchor":"face","offset_px":[48,0],"scale":1.0,"per_species":{"byteblob":[0,0,1.0],"patchfox":[0,0,1.0],"nullgeist":[0,0,1.0],"kernelcrab":[0,0,1.0],"cachebat":[0,0,1.0],"stacktoise":[0,0,1.0],"daemowl":[0,0,1.0],"shellsnail":[0,0,1.0],"regexopus":[0,0,1.0],"firewyrm":[0,0,1.0]}},"face.happy_path":{"slot":"face","z":20,"anchor":"face","offset_px":[0,0],"scale":1.0,"per_species":{"byteblob":[0,0,1.0],"patchfox":[0,0,1.0],"nullgeist":[0,0,1.0],"kernelcrab":[0,1,1.0],"cachebat":[0,0,1.0],"stacktoise":[0,0,1.0],"daemowl":[0,2,1.0],"shellsnail":[0,1,1.0],"regexopus":[0,0,1.0],"firewyrm":[0,0,1.0]}},"face.hex_specs":{"slot":"face","z":20,"anchor":"face","offset_px":[0,0],"scale":1.0,"per_species":{"byteblob":[0,0,1.0],"patchfox":[0,0,1.0],"nullgeist":[0,0,1.0],"kernelcrab":[0,1,1.0],"cachebat":[0,0,1.0],"stacktoise":[0,0,1.0],"daemowl":[0,2,1.0],"shellsnail":[0,1,1.0],"regexopus":[0,0,1.0],"firewyrm":[0,0,1.0]}},"face.laser_focus":{"slot":"face","z":20,"anchor":"face","offset_px":[0,0],"scale":1.0,"per_species":{"byteblob":[0,0,1.0],"patchfox":[0,0,1.0],"nullgeist":[0,0,1.0],"kernelcrab":[0,1,1.0],"cachebat":[0,0,1.0],"stacktoise":[0,0,1.0],"daemowl":[0,2,1.0],"shellsnail":[0,1,1.0],"regexopus":[0,0,1.0],"firewyrm":[0,0,1.0]}},"face.noir_shades":{"slot":"face","z":20,"anchor":"face","offset_px":[0,0],"scale":1.0,"per_species":{"byteblob":[0,0,1.0],"patchfox":[0,0,1.0],"nullgeist":[0,0,1.0],"kernelcrab":[0,1,1.0],"cachebat":[0,0,1.0],"stacktoise":[0,0,1.0],"daemowl":[0,2,1.0],"shellsnail":[0,1,1.0],"regexopus":[0,0,1.0],"firewyrm":[0,0,1.0]}},"face.oauth_eyepatch":{"slot":"face","z":20,"anchor":"face","offset_px":[0,0],"scale":1.0,"per_species":{"byteblob":[0,0,1.0],"patchfox":[0,0,1.0],"nullgeist":[0,0,1.0],"kernelcrab":[0,1,1.0],"cachebat":[0,0,1.0],"stacktoise":[0,0,1.0],"daemowl":[0,2,1.0],"shellsnail":[0,1,1.0],"regexopus":[0,0,1.0],"firewyrm":[0,0,1.0]}},"face.pixel_mustache":{"slot":"face","z":20,"anchor":"face","offset_px":[0,0],"scale":1.0,"per_species":{"byteblob":[0,0,1.0],"patchfox":[0,0,1.0],"nullgeist":[0,0,1.0],"kernelcrab":[0,1,1.0],"cachebat":[0,0,1.0],"stacktoise":[0,0,1.0],"daemowl":[0,2,1.0],"shellsnail":[0,1,1.0],"regexopus":[0,0,1.0],"firewyrm":[0,0,1.0]}},"face.pixel_shades":{"slot":"face","z":20,"anchor":"face","offset_px":[0,0],"scale":1.0,"per_species":{"byteblob":[0,0,1.0],"patchfox":[0,0,1.0],"nullgeist":[0,0,1.0],"kernelcrab":[0,0,1.0],"cachebat":[0,0,1.0],"stacktoise":[0,0,1.0],"daemowl":[0,0,1.0],"shellsnail":[0,0,1.0],"regexopus":[0,0,1.0],"firewyrm":[0,0,1.0]}},"face.privacy_mask":{"slot":"face","z":20,"anchor":"face","offset_px":[0,0],"scale":1.0,"per_species":{"byteblob":[0,0,1.0],"patchfox":[0,0,1.0],"nullgeist":[0,0,1.0],"kernelcrab":[0,1,1.0],"cachebat":[0,0,1.0],"stacktoise":[0,0,1.0],"daemowl":[0,2,1.0],"shellsnail":[0,1,1.0],"regexopus":[0,0,1.0],"firewyrm":[0,0,1.0]}},"face.regex_rims":{"slot":"face","z":20,"anchor":"face","offset_px":[0,0],"scale":1.0,"per_species":{"byteblob":[0,0,1.0],"patchfox":[0,0,1.0],"nullgeist":[0,0,1.0],"kernelcrab":[0,1,1.0],"cachebat":[0,0,1.0],"stacktoise":[0,0,1.0],"daemowl":[0,2,1.0],"shellsnail":[0,1,1.0],"regexopus":[0,0,1.0],"firewyrm":[0,0,1.0]}},"face.scan_visor":{"slot":"face","z":20,"anchor":"face","offset_px":[0,0],"scale":1.0,"per_species":{"byteblob":[0,0,1.0],"patchfox":[0,0,1.0],"nullgeist":[0,0,1.0],"kernelcrab":[0,0,1.0],"cachebat":[0,0,1.0],"stacktoise":[0,0,1.0],"daemowl":[0,0,1.0],"shellsnail":[0,0,1.0],"regexopus":[0,0,1.0],"firewyrm":[0,0,1.0]}},"face.stack_trace":{"slot":"face","z":20,"anchor":"face","offset_px":[0,0],"scale":1.0,"per_species":{"byteblob":[0,0,1.0],"patchfox":[0,0,1.0],"nullgeist":[0,0,1.0],"kernelcrab":[0,1,1.0],"cachebat":[0,0,1.0],"stacktoise":[0,0,1.0],"daemowl":[0,2,1.0],"shellsnail":[0,1,1.0],"regexopus":[0,0,1.0],"firewyrm":[0,0,1.0]}},"face.telemetry_lens":{"slot":"face","z":20,"anchor":"face","offset_px":[0,0],"scale":1.0,"per_species":{"byteblob":[0,0,1.0],"patchfox":[0,0,1.0],"nullgeist":[0,0,1.0],"kernelcrab":[0,1,1.0],"cachebat":[0,0,1.0],"stacktoise":[0,0,1.0],"daemowl":[0,2,1.0],"shellsnail":[0,1,1.0],"regexopus":[0,0,1.0],"firewyrm":[0,0,1.0]}},"face.three_lens":{"slot":"face","z":20,"anchor":"face","offset_px":[0,0],"scale":1.0,"per_species":{"byteblob":[0,0,1.0],"patchfox":[0,0,1.0],"nullgeist":[0,0,1.0],"kernelcrab":[0,1,1.0],"cachebat":[0,0,1.0],"stacktoise":[0,0,1.0],"daemowl":[0,0,1.0],"shellsnail":[0,1,1.0],"regexopus":[0,0,1.0],"firewyrm":[0,0,1.0]}},"front.banana_phone":{"slot":"front","z":40,"anchor":"hand","offset_px":[0,0],"scale":1.0,"per_species":{"byteblob":[0,1,1.0],"patchfox":[0,1,1.0],"nullgeist":[0,1,1.0],"kernelcrab":[0,1,1.0],"cachebat":[0,1,1.0],"stacktoise":[0,1,1.0],"daemowl":[0,1,1.0],"shellsnail":[0,1,1.0],"regexopus":[0,1,1.0],"firewyrm":[0,1,1.0]}},"front.bow_tie":{"slot":"front","z":40,"anchor":"front","offset_px":[0,0],"scale":1.0,"per_species":{"byteblob":[0,-7,1.0],"patchfox":[0,-3,1.0],"nullgeist":[0,-6,1.0],"kernelcrab":[0,-4,1.0],"cachebat":[0,-3,1.0],"stacktoise":[0,-6,1.0],"daemowl":[0,-6,1.0],"shellsnail":[0,-4,1.0],"regexopus":[0,-5,1.0],"firewyrm":[0,-6,1.0]}},"front.bug_net":{"slot":"front","z":40,"anchor":"hand","offset_px":[0,0],"scale":1.0,"per_species":{"byteblob":[0,2,1.0],"patchfox":[0,2,1.0],"nullgeist":[0,2,1.0],"kernelcrab":[0,2,1.0],"cachebat":[0,2,1.0],"stacktoise":[0,2,1.0],"daemowl":[0,2,1.0],"shellsnail":[0,2,1.0],"regexopus":[0,2,1.0],"firewyrm":[0,2,1.0]}},"front.cache_scarf":{"slot":"front","z":40,"anchor":"front","offset_px":[0,0],"scale":1.0,"per_species":{"byteblob":[0,-11,1.0],"patchfox":[0,-7,1.0],"nullgeist":[0,-10,1.0],"kernelcrab":[0,-8,1.0],"cachebat":[0,-7,1.0],"stacktoise":[0,-10,1.0],"daemowl":[0,-10,1.0],"shellsnail":[0,-8,1.0],"regexopus":[0,-9,1.0],"firewyrm":[0,-10,1.0]}},"front.coffee_mug":{"slot":"front","z":40,"anchor":"hand","offset_px":[0,0],"scale":1.0,"per_species":{"byteblob":[0,-2,1.0],"patchfox":[0,-2,1.0],"nullgeist":[0,-2,1.0],"kernelcrab":[0,-2,1.0],"cachebat":[0,-2,1.0],"stacktoise":[0,-2,1.0],"daemowl":[0,-2,1.0],"shellsnail":[0,-2,1.0],"regexopus":[0,-2,1.0],"firewyrm":[0,-2,1.0]}},"front.cozy_scarf":{"slot":"front","z":40,"anchor":"front","offset_px":[0,0],"scale":1.0,"per_species":{"byteblob":[0,-9,1.0],"patchfox":[0,-5,1.0],"nullgeist":[0,-8,1.0],"kernelcrab":[0,-6,1.0],"cachebat":[0,-5,1.0],"stacktoise":[0,-8,1.0],"daemowl":[0,-8,1.0],"shellsnail":[0,-6,1.0],"regexopus":[0,-7,1.0],"firewyrm":[0,-8,1.0]}},"front.flag":{"slot":"front","z":40,"anchor":"hand","offset_px":[0,0],"scale":1.0,"per_species":{"byteblob":[-2,1,1.0],"patchfox":[-2,1,1.0],"nullgeist":[-2,1,1.0],"kernelcrab":[-2,1,1.0],"cachebat":[-2,1,1.0],"stacktoise":[-2,1,1.0],"daemowl":[-2,1,1.0],"shellsnail":[-2,1,1.0],"regexopus":[-2,1,1.0],"firewyrm":[-2,1,1.0]}},"front.keyboard":{"slot":"front","z":40,"anchor":"hand","offset_px":[0,0],"scale":1.0,"per_species":{"byteblob":[0,-1,1.0],"patchfox":[0,-1,1.0],"nullgeist":[0,-1,1.0],"kernelcrab":[0,-1,1.0],"cachebat":[0,-1,1.0],"stacktoise":[0,-1,1.0],"daemowl":[0,-1,1.0],"shellsnail":[0,-1,1.0],"regexopus":[0,-1,1.0],"firewyrm":[0,-1,1.0]}},"front.magnifier":{"slot":"front","z":40,"anchor":"hand","offset_px":[0,0],"scale":1.0,"per_species":{"byteblob":[1,-1,1.0],"patchfox":[1,-1,1.0],"nullgeist":[1,-1,1.0],"kernelcrab":[1,-1,1.0],"cachebat":[1,-1,1.0],"stacktoise":[1,-1,1.0],"daemowl":[1,-1,1.0],"shellsnail":[1,-1,1.0],"regexopus":[1,-1,1.0],"firewyrm":[1,-1,1.0]}},"front.medal_ribbon":{"slot":"front","z":40,"anchor":"front","offset_px":[0,0],"scale":1.0,"per_species":{"byteblob":[0,-9,1.0],"patchfox":[0,-5,1.0],"nullgeist":[0,-8,1.0],"kernelcrab":[0,-6,1.0],"cachebat":[0,-5,1.0],"stacktoise":[0,-8,1.0],"daemowl":[0,-8,1.0],"shellsnail":[0,-6,1.0],"regexopus":[0,-7,1.0],"firewyrm":[0,-8,1.0]}},"front.pixel_badge":{"slot":"front","z":40,"anchor":"hand","offset_px":[0,0],"scale":1.0,"per_species":{"byteblob":[0,-2,1.0],"patchfox":[0,-2,1.0],"nullgeist":[0,-2,1.0],"kernelcrab":[0,-2,1.0],"cachebat":[0,-2,1.0],"stacktoise":[0,-2,1.0],"daemowl":[0,-2,1.0],"shellsnail":[0,-2,1.0],"regexopus":[0,-2,1.0],"firewyrm":[0,-2,1.0]}},"front.pixel_blade":{"slot":"front","z":40,"anchor":"hand","offset_px":[0,0],"scale":1.0,"per_species":{"byteblob":[0,2,1.0],"patchfox":[0,2,1.0],"nullgeist":[0,2,1.0],"kernelcrab":[0,2,1.0],"cachebat":[0,2,1.0],"stacktoise":[0,2,1.0],"daemowl":[0,2,1.0],"shellsnail":[0,2,1.0],"regexopus":[0,2,1.0],"firewyrm":[0,2,1.0]}},"front.pointer_wand":{"slot":"front","z":40,"anchor":"hand","offset_px":[0,0],"scale":1.0,"per_species":{"byteblob":[0,1,1.0],"patchfox":[0,1,1.0],"nullgeist":[0,1,1.0],"kernelcrab":[0,1,1.0],"cachebat":[0,1,1.0],"stacktoise":[0,1,1.0],"daemowl":[0,1,1.0],"shellsnail":[0,1,1.0],"regexopus":[0,1,1.0],"firewyrm":[0,1,1.0]}},"front.rubber_duck":{"slot":"front","z":40,"anchor":"hand","offset_px":[0,0],"scale":1.0,"per_species":{"byteblob":[-1,-1,1.0],"patchfox":[-1,-1,1.0],"nullgeist":[-1,-1,1.0],"kernelcrab":[-1,-1,1.0],"cachebat":[-1,-1,1.0],"stacktoise":[-1,-1,1.0],"daemowl":[-1,-1,1.0],"shellsnail":[-1,-1,1.0],"regexopus":[-1,-1,1.0],"firewyrm":[-1,-1,1.0]}},"front.scroll":{"slot":"front","z":40,"anchor":"hand","offset_px":[0,0],"scale":1.0,"per_species":{"byteblob":[0,0,1.0],"patchfox":[0,0,1.0],"nullgeist":[0,0,1.0],"kernelcrab":[0,0,1.0],"cachebat":[0,0,1.0],"stacktoise":[0,0,1.0],"daemowl":[0,0,1.0],"shellsnail":[0,0,1.0],"regexopus":[0,0,1.0],"firewyrm":[0,0,1.0]}},"front.silk_tie":{"slot":"front","z":40,"anchor":"front","offset_px":[0,0],"scale":1.0,"per_species":{"byteblob":[0,-10,1.0],"patchfox":[0,-6,1.0],"nullgeist":[0,-9,1.0],"kernelcrab":[0,-7,1.0],"cachebat":[0,-6,1.0],"stacktoise":[0,-9,1.0],"daemowl":[0,-9,1.0],"shellsnail":[0,-7,1.0],"regexopus":[0,-8,1.0],"firewyrm":[0,-9,1.0]}},"front.toast":{"slot":"front","z":40,"anchor":"hand","offset_px":[0,0],"scale":1.0,"per_species":{"byteblob":[0,0,1.0],"patchfox":[0,0,1.0],"nullgeist":[0,0,1.0],"kernelcrab":[0,0,1.0],"cachebat":[0,0,1.0],"stacktoise":[0,0,1.0],"daemowl":[0,0,1.0],"shellsnail":[0,0,1.0],"regexopus":[0,0,1.0],"firewyrm":[0,0,1.0]}},"front.usb_sword":{"slot":"front","z":40,"anchor":"hand","offset_px":[0,0],"scale":1.0,"per_species":{"byteblob":[0,2,1.0],"patchfox":[0,2,1.0],"nullgeist":[0,2,1.0],"kernelcrab":[0,2,1.0],"cachebat":[0,2,1.0],"stacktoise":[0,2,1.0],"daemowl":[0,2,1.0],"shellsnail":[0,2,1.0],"regexopus":[0,2,1.0],"firewyrm":[0,2,1.0]}},"habitat.glow_moss":{"slot":"habitat","z":-20,"anchor":"ground","offset_px":[0,0],"scale":1.0,"per_species":{"byteblob":[0,0,1.0],"patchfox":[0,0,1.0],"nullgeist":[0,0,1.0],"kernelcrab":[0,0,1.0],"cachebat":[0,0,1.0],"stacktoise":[0,0,1.0],"daemowl":[0,0,1.0],"shellsnail":[0,0,1.0],"regexopus":[0,0,1.0],"firewyrm":[0,0,1.0]}},"habitat.plush_cushion":{"slot":"habitat","z":-20,"anchor":"ground","offset_px":[0,-16],"scale":1.0,"per_species":{"byteblob":[0,0,1.0],"patchfox":[0,0,1.0],"nullgeist":[0,0,1.0],"kernelcrab":[0,0,1.0],"cachebat":[0,0,1.0],"stacktoise":[0,0,1.0],"daemowl":[0,0,1.0],"shellsnail":[0,0,1.0],"regexopus":[0,0,1.0],"firewyrm":[0,0,1.0]}},"hat.binary_crown":{"slot":"head","z":30,"anchor":"head","offset_px":[0,0],"scale":1.0,"per_species":{"byteblob":[0,1,1.0],"patchfox":[0,1,1.0],"nullgeist":[0,1,1.0],"kernelcrab":[0,1,1.0],"cachebat":[0,1,1.0],"stacktoise":[0,1,1.0],"daemowl":[0,1,1.0],"shellsnail":[0,1,1.0],"regexopus":[0,1,1.0],"firewyrm":[0,1,1.0]}},"hat.bloom_filter":{"slot":"head","z":30,"anchor":"head","offset_px":[0,0],"scale":1.0,"per_species":{"byteblob":[0,-2,1.0],"patchfox":[0,-2,1.0],"nullgeist":[0,-2,0.914],"kernelcrab":[0,-2,1.0],"cachebat":[0,-2,1.0],"stacktoise":[0,-1,0.731],"daemowl":[0,-2,0.823],"shellsnail":[0,-2,1.0],"regexopus":[0,-2,0.914],"firewyrm":[0,-1,0.731]}},"hat.clippy_hat":{"slot":"head","z":30,"anchor":"head","offset_px":[0,0],"scale":1.0,"per_species":{"byteblob":[0,1,1.0],"patchfox":[0,1,1.0],"nullgeist":[0,1,1.0],"kernelcrab":[0,1,1.0],"cachebat":[0,1,1.0],"stacktoise":[0,1,1.0],"daemowl":[0,1,1.0],"shellsnail":[0,1,1.0],"regexopus":[0,1,1.0],"firewyrm":[0,1,1.0]}},"hat.cron_crown":{"slot":"head","z":30,"anchor":"head","offset_px":[0,0],"scale":1.0,"per_species":{"byteblob":[0,1,1.0],"patchfox":[0,1,1.0],"nullgeist":[0,1,1.0],"kernelcrab":[0,1,1.0],"cachebat":[0,1,1.0],"stacktoise":[0,1,1.0],"daemowl":[0,1,1.0],"shellsnail":[0,1,1.0],"regexopus":[0,1,1.0],"firewyrm":[0,1,1.0]}},"hat.debug_bowler":{"slot":"head","z":30,"anchor":"head","offset_px":[0,0],"scale":1.0,"per_species":{"byteblob":[0,-2,1.0],"patchfox":[0,-2,1.0],"nullgeist":[0,-2,0.914],"kernelcrab":[0,-2,1.0],"cachebat":[0,-2,1.0],"stacktoise":[0,-1,0.731],"daemowl":[0,-2,0.823],"shellsnail":[0,-2,1.0],"regexopus":[0,-2,0.914],"firewyrm":[0,-1,0.731]}},"hat.git_bandana":{"slot":"head","z":30,"anchor":"head","offset_px":[0,0],"scale":1.0,"per_species":{"byteblob":[0,2,1.0],"patchfox":[0,2,1.0],"nullgeist":[0,2,1.0],"kernelcrab":[0,2,1.0],"cachebat":[0,2,1.0],"stacktoise":[0,2,1.0],"daemowl":[0,2,1.0],"shellsnail":[0,2,1.0],"regexopus":[0,2,1.0],"firewyrm":[0,2,1.0]}},"hat.kernel_helm":{"slot":"head","z":30,"anchor":"head","offset_px":[0,0],"scale":1.0,"per_species":{"byteblob":[0,0,1.0],"patchfox":[0,0,1.0],"nullgeist":[0,0,1.0],"kernelcrab":[0,0,1.0],"cachebat":[0,0,1.0],"stacktoise":[0,0,1.0],"daemowl":[0,0,1.0],"shellsnail":[0,0,1.0],"regexopus":[0,0,1.0],"firewyrm":[0,0,1.0]}},"hat.lambda_tiara":{"slot":"head","z":30,"anchor":"head","offset_px":[0,0],"scale":1.0,"per_species":{"byteblob":[0,4,1.0],"patchfox":[0,4,1.0],"nullgeist":[0,4,1.0],"kernelcrab":[0,4,1.0],"cachebat":[0,4,1.0],"stacktoise":[0,4,1.0],"daemowl":[0,4,1.0],"shellsnail":[0,4,1.0],"regexopus":[0,4,1.0],"firewyrm":[0,4,1.0]}},"hat.nginx_visor":{"slot":"head","z":30,"anchor":"head","offset_px":[0,0],"scale":1.0,"per_species":{"byteblob":[0,1,1.0],"patchfox":[0,1,1.0],"nullgeist":[0,1,1.0],"kernelcrab":[0,1,1.0],"cachebat":[0,1,1.0],"stacktoise":[0,1,1.0],"daemowl":[0,1,1.0],"shellsnail":[0,1,1.0],"regexopus":[0,1,1.0],"firewyrm":[0,1,1.0]}},"hat.packet_cap":{"slot":"head","z":30,"anchor":"head","offset_px":[0,0],"scale":1.0,"per_species":{"byteblob":[0,1,1.0],"patchfox":[0,1,1.0],"nullgeist":[0,1,1.0],"kernelcrab":[0,1,1.0],"cachebat":[0,1,1.0],"stacktoise":[0,1,1.0],"daemowl":[0,1,1.0],"shellsnail":[0,1,1.0],"regexopus":[0,1,1.0],"firewyrm":[0,1,1.0]}},"hat.propeller_beanie":{"slot":"head","z":30,"anchor":"head","offset_px":[0,0],"scale":1.0,"per_species":{"byteblob":[0,0,1.0],"patchfox":[0,0,1.0],"nullgeist":[0,0,1.0],"kernelcrab":[0,0,1.0],"cachebat":[0,0,1.0],"stacktoise":[0,0,0.895],"daemowl":[0,0,1.0],"shellsnail":[0,0,1.0],"regexopus":[0,0,1.0],"firewyrm":[0,0,0.895]}},"hat.rss_antenna":{"slot":"head","z":30,"anchor":"head","offset_px":[0,0],"scale":1.0,"per_species":{"byteblob":[0,1,1.0],"patchfox":[0,1,1.0],"nullgeist":[0,1,0.838],"kernelcrab":[0,1,1.0],"cachebat":[0,1,1.0],"stacktoise":[0,1,0.67],"daemowl":[0,1,0.754],"shellsnail":[0,1,1.0],"regexopus":[0,1,0.838],"firewyrm":[0,1,0.67]}},"hat.sudo_cap":{"slot":"head","z":30,"anchor":"head","offset_px":[0,0],"scale":1.0,"per_species":{"byteblob":[0,1,1.0],"patchfox":[0,1,1.0],"nullgeist":[0,1,1.0],"kernelcrab":[0,1,1.0],"cachebat":[0,1,1.0],"stacktoise":[0,1,1.0],"daemowl":[0,1,1.0],"shellsnail":[0,1,1.0],"regexopus":[0,1,1.0],"firewyrm":[0,1,1.0]}},"hat.syntax_wizard":{"slot":"head","z":30,"anchor":"head","offset_px":[0,0],"scale":1.0,"per_species":{"byteblob":[0,0,1.0],"patchfox":[0,0,1.0],"nullgeist":[0,0,1.0],"kernelcrab":[0,0,1.0],"cachebat":[0,0,1.0],"stacktoise":[0,0,0.805],"daemowl":[0,0,0.906],"shellsnail":[0,0,1.0],"regexopus":[0,0,1.0],"firewyrm":[0,0,0.805]}},"hat.topo_beanie":{"slot":"head","z":30,"anchor":"head","offset_px":[0,0],"scale":1.0,"per_species":{"byteblob":[0,1,1.0],"patchfox":[0,1,1.0],"nullgeist":[0,1,1.0],"kernelcrab":[0,1,1.0],"cachebat":[0,1,1.0],"stacktoise":[0,1,1.0],"daemowl":[0,1,1.0],"shellsnail":[0,1,1.0],"regexopus":[0,1,1.0],"firewyrm":[0,1,1.0]}},"hat.wizard_hat":{"slot":"head","z":30,"anchor":"head","offset_px":[0,0],"scale":1.0,"per_species":{"byteblob":[0,2,1.0],"patchfox":[0,2,1.0],"nullgeist":[0,2,0.838],"kernelcrab":[0,2,1.0],"cachebat":[0,2,1.0],"stacktoise":[0,2,0.67],"daemowl":[0,2,0.754],"shellsnail":[0,2,1.0],"regexopus":[0,2,0.838],"firewyrm":[0,2,0.67]}},"title.pixel_pilot":{"slot":"title","z":50,"anchor":"face","offset_px":[0,0],"scale":1.0,"per_species":{"byteblob":[0,0,1.0],"patchfox":[0,0,1.0],"nullgeist":[0,0,1.0],"kernelcrab":[0,0,1.0],"cachebat":[0,0,1.0],"stacktoise":[0,0,1.0],"daemowl":[0,0,1.0],"shellsnail":[0,0,1.0],"regexopus":[0,0,1.0],"firewyrm":[0,0,1.0]}},"title.royal_ribbon":{"slot":"title","z":50,"anchor":"ground","offset_px":[0,32],"scale":1.0,"per_species":{"byteblob":[0,0,1.0],"patchfox":[0,0,1.0],"nullgeist":[0,0,1.0],"kernelcrab":[0,0,1.0],"cachebat":[0,0,1.0],"stacktoise":[0,0,1.0],"daemowl":[0,0,1.0],"shellsnail":[0,0,1.0],"regexopus":[0,0,1.0],"firewyrm":[0,0,1.0]}}}});

function number(value, fallback) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function resolveSource(source) {
  if (source && typeof source === "object" && source.species && source.items) {
    return source;
  }
  return EMBEDDED_ANCHORS;
}

function speciesEntry(source, species) {
  if (!species || !source || !source.species) return null;
  return source.species[species] || source.species[String(species)] || null;
}

function itemEntry(source, itemId) {
  if (!itemId || !source || !source.items) return null;
  return source.items[itemId] || source.items[String(itemId)] || null;
}

function transformArray(raw) {
  if (Array.isArray(raw)) return raw;
  if (raw && Array.isArray(raw.transform_native)) return raw.transform_native;
  return null;
}

/** Species anchor points on the native 32x32 grid. */
export function anchorsFor(species, source) {
  const entry = speciesEntry(resolveSource(source), species);
  return entry && entry.anchors_native ? entry.anchors_native : null;
}

/** Species-wide cosmetic scale multiplier. */
export function itemScaleFor(species, source) {
  const entry = speciesEntry(resolveSource(source), species);
  return entry ? number(entry.item_scale, 1) : 1;
}

/** [dx, dy, scale] for one item on one species. */
export function transformNativeFor(itemId, species, source) {
  const entry = itemEntry(resolveSource(source), itemId);
  if (!entry || !entry.per_species) return [0, 0, 1];
  const raw = entry.per_species[species] || entry.per_species[String(species)];
  const transform = transformArray(raw);
  if (!transform || transform.length < 3) return [0, 0, 1];
  return [
    number(transform[0], 0),
    number(transform[1], 0),
    number(transform[2], 1),
  ];
}

/**
 * Compose one cosmetic layer.
 *
 * @param {object} options
 * @param {string} options.species
 * @param {string} [options.itemId]
 * @param {object} [options.manifestAsset] manifest asset entry (anchor/offset/scale/z)
 * @param {object} [options.artExt] full art_ext object (optional)
 * @param {object} [options.anchors] composeAnchors snapshot (optional)
 * @param {number} [options.nativeSize=32]
 * @param {number} [options.displaySize=nativeSize]
 * @returns {object|null}
 */
export function composeItem(options = {}) {
  const manifestAsset = options.manifestAsset || options.asset || null;
  const species = options.species ? String(options.species) : "";
  const itemId = String(
    options.itemId || (manifestAsset && (manifestAsset.id || manifestAsset.asset_id)) || ""
  );
  if (!species) return null;

  const source = resolveSource(
    options.artExt || options.anchors || options.composeAnchors
  );
  const speciesData = speciesEntry(source, species);
  if (!speciesData) return null;

  const itemData = itemEntry(source, itemId) || {};
  const transform = transformNativeFor(itemId, species, source);
  const nativeSize = Math.max(
    1,
    number(options.nativeSize, number(source.native_size, DEFAULT_NATIVE_SIZE))
  );
  const displaySize = Math.max(1, number(options.displaySize, nativeSize));
  const pixelFactor = Math.max(
    1,
    number(options.pixelFactor, number(source.pixel_factor, DEFAULT_PIXEL_FACTOR))
  );

  const anchorName = String(
    (manifestAsset && manifestAsset.anchor) || itemData.anchor || "front"
  );
  const anchorSet = speciesData.anchors_native || {};
  const anchorNative = anchorSet[anchorName] ||
    anchorSet.front ||
    anchorSet.body || [nativeSize / 2, nativeSize / 2];

  const rawOffset =
    manifestAsset && Array.isArray(manifestAsset.offset_px)
      ? manifestAsset.offset_px
      : Array.isArray(itemData.offset_px)
        ? itemData.offset_px
        : [0, 0];
  const explicitOffset =
    (manifestAsset && manifestAsset.offset_native) || itemData.offset_native;
  const offsetNative = Array.isArray(explicitOffset)
    ? [number(explicitOffset[0], 0), number(explicitOffset[1], 0)]
    : [
        Math.floor(number(rawOffset[0], 0) / pixelFactor),
        Math.floor(number(rawOffset[1], 0) / pixelFactor),
      ];

  const baseScale = number(
    manifestAsset && manifestAsset.scale != null
      ? manifestAsset.scale
      : itemData.scale,
    1
  );
  const itemScale = number(speciesData.item_scale, 1);
  const transformScale = number(transform[2], 1);
  const scale = baseScale * itemScale * transformScale;
  const centerNative = [
    number(anchorNative[0], nativeSize / 2) + offsetNative[0] + number(transform[0], 0),
    number(anchorNative[1], nativeSize / 2) + offsetNative[1] + number(transform[1], 0),
  ];
  const topLeftNative = [
    centerNative[0] - (nativeSize * scale) / 2,
    centerNative[1] - (nativeSize * scale) / 2,
  ];
  const fraction = [
    centerNative[0] / nativeSize - 0.5,
    centerNative[1] / nativeSize - 0.5,
  ];
  const offsetPercent = [fraction[0] * 100, fraction[1] * 100];
  const offsetPx = [fraction[0] * displaySize, fraction[1] * displaySize];
  const topLeftPx = [
    (topLeftNative[0] / nativeSize) * displaySize,
    (topLeftNative[1] / nativeSize) * displaySize,
  ];
  const zValue =
    manifestAsset && Number.isFinite(Number(manifestAsset.z))
      ? Number(manifestAsset.z)
      : Number.isFinite(Number(itemData.z))
        ? Number(itemData.z)
        : null;

  return {
    itemId,
    species,
    slot: String((manifestAsset && manifestAsset.slot) || itemData.slot || ""),
    anchor: anchorName,
    anchorNative: [number(anchorNative[0], nativeSize / 2), number(anchorNative[1], nativeSize / 2)],
    transformNative: [transform[0], transform[1], transform[2]],
    itemScale,
    baseScale,
    scale,
    nativeSize,
    displaySize,
    pixelFactor,
    offsetNative,
    centerNative,
    topLeftNative,
    fraction,
    offsetPercent,
    offsetPx,
    topLeftPx,
    z: zValue,
  };
}

/** Layer-shaped alias used by buildPreviewLayers / PetPreview. */
export const composeLayer = composeItem;
