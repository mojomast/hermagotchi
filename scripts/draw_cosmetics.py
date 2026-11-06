#!/usr/bin/env python3
"""Hand-author ~60 launch-003 cosmetics at native 32px (×16 display).

No GenerateImage. Writes px3/items PNGs, updates manifest.launch-003.json +
art_ext.launch-003.json with per-species transforms for all 10 species.
Existing 13 items keep paths; their per_species maps are filled out.
"""
from __future__ import annotations
import hashlib, json
from pathlib import Path
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
A = ROOT / "assets"
OUT = A / "px3" / "items"
N, F = 32, 16
OUTLINE = (16, 14, 28)
SPECIES = [
    "byteblob", "patchfox", "nullgeist", "kernelcrab", "cachebat",
    "stacktoise", "daemowl", "shellsnail", "regexopus", "firewyrm",
]

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

class C:
    def __init__(self):
        self.a = np.zeros((N, N, 4), np.uint8)
    def p(self, x, y, c):
        if 0 <= x < N and 0 <= y < N:
            self.a[y, x, :3] = c; self.a[y, x, 3] = 255
    def rect(self, x0, y0, x1, y1, c):
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                self.p(x, y, c)
    def hline(self, y, x0, x1, c):
        for x in range(x0, x1 + 1): self.p(x, y, c)
    def vline(self, x, y0, y1, c):
        for y in range(y0, y1 + 1): self.p(x, y, c)
    def disc(self, cx, cy, r, c):
        for y in range(cy - r, cy + r + 1):
            for x in range(cx - r, cx + r + 1):
                if (x - cx) ** 2 + (y - cy) ** 2 <= r * r: self.p(x, y, c)
    def outline(self):
        from scipy import ndimage
        m = self.a[..., 3] > 0
        edge = m & ~ndimage.binary_erosion(m, structure=np.array([[0,1,0],[1,1,1],[0,1,0]]))
        self.a[edge, :3] = OUTLINE
    def img(self):
        return Image.fromarray(self.a, "RGBA")
    def save(self, name: str) -> Path:
        self.outline()
        up = self.img().resize((N * F, N * F), Image.NEAREST)
        path = OUT / f"{name}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        up.save(path, optimize=True)
        return path

# ---------- drawers (content around canvas centre 16,16) ----------
W = (255, 255, 255); K = OUTLINE
def hat_cap(c, body, brim, tip=None):
    c.rect(11, 12, 20, 16, body)
    c.hline(16, 9, 22, brim)
    c.hline(11, 12, 19, tip or body)
    c.p(13, 13, W)  # UL light
def face_shades(c, lens, frame):
    c.rect(10, 14, 14, 17, lens); c.rect(17, 14, 21, 17, lens)
    c.hline(14, 10, 21, frame); c.hline(17, 10, 21, frame)
    c.vline(10, 14, 17, frame); c.vline(14, 14, 17, frame)
    c.vline(17, 14, 17, frame); c.vline(21, 14, 17, frame)
    c.hline(15, 14, 17, frame)
    c.p(11, 15, W); c.p(18, 15, W)
def back_cape(c, cloth, lining):
    c.rect(10, 14, 21, 26, cloth)
    c.rect(12, 16, 19, 24, lining)
    c.hline(14, 11, 20, W)
def front_scarf(c, a, b):
    c.hline(18, 11, 20, a); c.hline(19, 11, 20, b)
    c.rect(14, 19, 17, 25, a); c.p(15, 20, W)
def held_stick(c, shaft, tip):
    c.vline(20, 12, 24, shaft)
    c.disc(20, 11, 2, tip); c.p(19, 10, W)
def aura_ring(c, col, col2, phase=0):
    pts = [(16, 8), (22, 12), (24, 18), (20, 24), (12, 24), (8, 18), (10, 12)]
    for i, (x, y) in enumerate(pts):
        if (i + phase) % 2 == 0: c.disc(x, y, 1, col)
        else: c.disc(x, y, 1, col2)
    c.p(14, 9, W)

# Item catalog: id -> (slot, z, anchor, rarity, price, name, draw_fn, scale, frames?)
# draw_fn(c) or for 2-frame aura draw_fn(c, frame)

GOLD=(220,170,40); RED=(200,40,40); BLUE=(40,90,200); CYAN=(40,200,220)
GREEN=(40,160,80); PURPLE=(140,60,200); PINK=(240,120,180); ORANGE=(240,140,40)
GREY=(120,120,130); BROWN=(120,70,30); YELLOW=(240,220,60); TEAL=(30,160,150)

def D_hats():
    items = []
    def add(iid, name, rarity, price, fn):
        items.append((iid, "head", 30, "head", rarity, price, name, fn, 1.0, 1))
    add("hat.topo_beanie", "Topo Beanie", "common", 150, lambda c: (hat_cap(c, RED, RED, ORANGE), c.p(16,10,ORANGE)))
    add("hat.packet_cap", "Packet Cap", "common", 150, lambda c: (c.rect(11,13,20,16,BLUE), c.hline(16,10,21,BLUE), c.p(12,14,W)))
    add("hat.nginx_visor", "Nginx Visor Cap", "uncommon", 350, lambda c: (hat_cap(c, GREEN, DARK:= (20,80,40)), c.rect(12,14,19,15,W)))
    add("hat.kernel_helm", "Kernel Helm", "rare", 700, lambda c: (c.rect(11,11,20,17,GREY), c.hline(11,12,19,W), c.rect(14,13,17,15,CYAN)))
    add("hat.git_bandana", "Git Bandana", "common", 150, lambda c: (c.hline(13,10,21,RED), c.hline(14,11,20,ORANGE), c.p(12,13,W)))
    add("hat.rss_antenna", "RSS Antenna", "uncommon", 350, lambda c: (c.vline(16,8,14,GREY), c.disc(16,7,2,ORANGE), c.p(15,7,W), c.rect(12,14,19,16,BROWN)))
    add("hat.debug_bowler", "Debug Bowler", "rare", 700, lambda c: (c.disc(16,14,5,K), c.disc(16,14,4,GREY), c.hline(17,10,22,GREY), c.p(13,12,W)))
    add("hat.lambda_tiara", "Lambda Tiara", "epic", 1200, lambda c: (c.hline(13,11,20,GOLD), c.p(16,11,GOLD), c.p(15,10,GOLD), c.p(17,10,GOLD), c.p(14,12,W)))
    add("hat.cron_crown", "Cron Crown", "legendary", 2000, lambda c: (c.rect(12,12,19,16,GOLD), c.p(13,11,GOLD), c.p(16,11,RED), c.p(19,11,GOLD), c.p(14,13,W)))
    add("hat.clippy_hat", "Clippy Hat", "uncommon", 350, lambda c: (hat_cap(c, YELLOW, ORANGE), c.rect(14,14,17,15,W)))
    add("hat.sudo_cap", "Sudo Cap", "rare", 700, lambda c: (hat_cap(c, K, RED), c.rect(13,14,18,15,RED), c.p(14,13,W)))
    add("hat.bloom_filter", "Bloom Filter Beret", "epic", 1200, lambda c: (c.disc(16,14,5,PINK), c.disc(16,14,3,PURPLE), c.p(13,12,W)))
    return items

def D_face():
    items = []
    def add(iid, name, rarity, price, fn):
        items.append((iid, "face", 20, "face", rarity, price, name, fn, 1.0, 1))
    add("face.regex_rims", "Regex Rims", "common", 150, lambda c: face_shades(c, CYAN, K))
    add("face.hex_specs", "Hex Specs", "common", 150, lambda c: face_shades(c, GREEN, GOLD))
    add("face.privacy_mask", "Privacy Mask", "uncommon", 350, lambda c: (c.rect(11,15,20,19,GREY), c.hline(15,12,19,W), c.p(13,16,W)))
    add("face.bug_eye", "Bug-Eye Goggles", "rare", 700, lambda c: (c.disc(13,16,3,LIME:=(180,240,60)), c.disc(19,16,3,LIME), c.hline(16,13,19,K), c.p(12,15,W), c.p(18,15,W)))
    add("face.noir_shades", "Noir Shades", "uncommon", 350, lambda c: face_shades(c, K, GREY))
    add("face.telemetry_lens", "Telemetry Lens", "rare", 700, lambda c: (c.disc(18,16,3,GOLD), c.disc(18,16,2,CYAN), c.p(17,15,W), c.vline(20,16,20,GREY)))
    add("face.happy_path", "Happy-Path Smile", "common", 150, lambda c: (c.hline(18,13,18,RED), c.p(13,17,RED), c.p(18,17,RED)))
    add("face.stack_trace", "Stack-Trace Specs", "epic", 1200, lambda c: (face_shades(c, ORANGE, RED), c.hline(13,11,20,RED)))
    add("face.oauth_eyepatch", "OAuth Eyepatch", "uncommon", 350, lambda c: (c.rect(10,14,15,18,K), c.p(11,15,W), c.hline(15,15,20,GREY)))
    add("face.pixel_mustache", "Pixel Mustache", "common", 150, lambda c: (c.hline(18,12,19,BROWN), c.p(14,17,BROWN), c.p(17,17,BROWN)))
    add("face.three_lens", "Triclops Frame", "rare", 700, lambda c: (
        c.rect(10,15,13,17,CYAN), c.rect(14,13,17,15,CYAN), c.rect(18,15,21,17,CYAN),
        c.p(11,15,W), c.p(15,13,W), c.p(19,15,W)))  # daemowl-friendly
    add("face.laser_focus", "Laser Focus", "legendary", 2000, lambda c: (face_shades(c, RED, GOLD), c.hline(16,8,10,RED), c.hline(16,21,23,RED)))
    return items

def D_back_neck():
    items = []
    def add(iid, slot, z, anc, name, rarity, price, fn, scale=1.0):
        items.append((iid, slot, z, anc, rarity, price, name, fn, scale, 1))
    # backs
    add("back.payload_pack", "back", -10, "back", "Payload Pack", "common", 150,
        lambda c: (c.rect(12,14,19,24,GREY), c.rect(13,15,18,20,BLUE), c.p(14,16,W)))
    add("back.caped_crusader", "back", -10, "back", "Caped Crusader", "rare", 700,
        lambda c: back_cape(c, RED, ORANGE))
    add("back.webhook_wings", "back", -10, "back", "Webhook Wings", "epic", 1200,
        lambda c: (c.rect(6,14,12,22,CYAN), c.rect(19,14,25,22,CYAN), c.p(8,15,W), c.p(21,15,W)))
    add("back.docker_whale", "back", -10, "back", "Docker Whale Fin", "uncommon", 350,
        lambda c: (c.rect(14,12,17,18,BLUE), c.hline(12,12,19,BLUE), c.p(15,13,W)))
    add("back.scroll_quiver", "back", -10, "back", "Scroll Quiver", "rare", 700,
        lambda c: (c.rect(18,12,22,24,BROWN), c.vline(19,13,22,W), c.vline(21,13,22,YEL:=YELLOW)))
    add("back.battery_pack", "back", -10, "back", "Battery Pack", "common", 150,
        lambda c: (c.rect(13,14,18,23,GREEN), c.rect(14,15,17,17,YEL:=YELLOW), c.p(15,16,W)))
    add("back.glider_cloak", "back", -10, "back", "Glider Cloak", "legendary", 2000,
        lambda c: back_cape(c, PURPLE, PINK))
    add("back.antenna_array", "back", -10, "back", "Antenna Array", "uncommon", 350,
        lambda c: (c.vline(14,10,18,GREY), c.vline(18,10,18,GREY), c.disc(14,9,1,RED), c.disc(18,9,1,CYAN)))
    # neck / front scarves & collars
    add("front.cache_scarf", "front", 40, "front", "Cache Scarf", "common", 150,
        lambda c: front_scarf(c, TEAL, CYAN))
    add("front.silk_tie", "front", 40, "front", "Silk Commit Tie", "uncommon", 350,
        lambda c: (c.vline(16,17,25,PURPLE), c.hline(17,15,17,PURPLE), c.p(16,18,W)))
    add("front.bow_tie", "front", 40, "front", "Boolean Bowtie", "common", 150,
        lambda c: (c.rect(12,17,15,19,RED), c.rect(16,17,19,19,RED), c.p(15,18,K), c.p(13,17,W)))
    add("front.medal_ribbon", "front", 40, "front", "Uptime Medal", "rare", 700,
        lambda c: (c.vline(15,16,20,RED), c.vline(16,16,20,GOLD), c.disc(16,21,2,GOLD), c.p(15,20,W)))
    return items

def D_held():
    # Held props: draw centred on (16,16); compose attaches via per-species `hand` anchor.
    items = []
    def add(iid, name, rarity, price, fn):
        items.append((iid, "front", 40, "hand", rarity, price, name, fn, 1.0, 1))
    add("front.rubber_duck", "Rubber Duck", "common", 150,
        lambda c: (c.disc(16,17,3,YELLOW), c.disc(18,15,2,YELLOW), c.p(18,14,ORANGE), c.p(17,16,K), c.p(15,16,W)))
    add("front.coffee_mug", "Coffee Mug", "common", 150,
        lambda c: (c.rect(13,14,18,21,BROWN), c.rect(14,15,17,18,W), c.p(19,16,BROWN), c.p(19,18,BROWN), c.p(14,15,W)))
    add("front.pointer_wand", "Null Pointer Wand", "rare", 700,
        lambda c: (c.vline(16,10,22,PURPLE), c.disc(16,9,2,CYAN), c.p(15,8,W)))
    add("front.usb_sword", "USB Sword", "epic", 1200,
        lambda c: (c.vline(16,8,20,CYAN), c.rect(14,18,18,20,GREY), c.p(16,9,W)))
    add("front.bug_net", "Bug Net", "uncommon", 350,
        lambda c: (c.vline(16,10,22,BROWN), c.disc(16,9,3,GREEN), c.p(15,8,W)))
    add("front.scroll", "RFC Scroll", "uncommon", 350,
        lambda c: (c.rect(13,12,19,20,W), c.hline(14,13,18,(220,200,160)), c.hline(13,14,17,(220,200,160)), c.p(15,15,K)))
    add("front.keyboard", "Mini Keyboard", "rare", 700,
        lambda c: (c.rect(11,14,21,19,GREY), c.rect(12,15,20,17,K), c.p(13,15,W), c.p(15,15,CYAN)))
    add("front.banana_phone", "Banana Phone", "common", 150,
        lambda c: (c.vline(16,10,20,YELLOW), c.disc(16,9,2,YELLOW), c.disc(16,21,1,BROWN), c.p(15,11,W)))
    add("front.flag", "Ship-It Flag", "rare", 700,
        lambda c: (c.vline(14,8,22,GREY), c.rect(15,9,21,14,GREEN), c.p(16,10,W)))
    add("front.toast", "Deploy Toast", "common", 150,
        lambda c: (c.rect(12,13,19,19,ORANGE), c.rect(13,14,18,18,YELLOW), c.p(14,15,W)))
    add("front.magnifier", "Log Magnifier", "uncommon", 350,
        lambda c: (c.disc(15,14,3,CYAN), c.disc(15,14,2,W), c.vline(17,16,22,GOLD), c.p(14,13,W)))
    add("front.pixel_blade", "Pixel Blade", "legendary", 2000,
        lambda c: (c.vline(16,7,18,W), c.vline(15,8,17,CYAN), c.rect(14,18,18,21,GOLD), c.p(16,8,W)))
    return items

def D_auras():
    items = []
    def add(iid, name, rarity, price, fn, frames=1):
        items.append((iid, "aura", -30, "face", rarity, price, name, fn, 1.25, frames))
    add("aura.ping_pulse", "Ping Pulse", "common", 150, lambda c, f=0: aura_ring(c, CYAN, BLUE, f), 2)
    add("aura.spark_trail", "Spark Trail", "uncommon", 350, lambda c, f=0: aura_ring(c, YELLOW, ORANGE, f), 2)
    add("aura.ghost_cache", "Ghost Cache", "rare", 700, lambda c, f=0: aura_ring(c, W, GREY, f), 2)
    add("aura.flame_wall", "Flame Wall", "epic", 1200, lambda c, f=0: aura_ring(c, RED, ORANGE, f), 2)
    add("aura.leaf_orbit", "Leaf Orbit", "common", 150, lambda c, f=0: aura_ring(c, GREEN, TEAL, f), 2)
    add("aura.hex_shield", "Hex Shield", "rare", 700, lambda c, f=0: (aura_ring(c, PURPLE, PINK, f), c.p(16,16,PURPLE)))
    add("aura.snow_globe", "Snow Globe", "uncommon", 350, lambda c, f=0: aura_ring(c, W, CYAN, f), 2)
    add("aura.virus_scan", "Virus Scan", "rare", 700, lambda c, f=0: aura_ring(c, GREEN, RED, f), 2)
    add("aura.starfield", "Starfield", "epic", 1200, lambda c, f=0: aura_ring(c, YELLOW, W, f), 2)
    add("aura.rainbow_arc", "Rainbow Arc", "legendary", 2000,
        lambda c, f=0: (c.hline(10,10,21,RED), c.hline(11,9,22,ORANGE), c.hline(12,8,23,YELLOW),
                        c.hline(13,8,23,GREEN), c.hline(14,9,22,BLUE), c.hline(15,10,21,PURPLE)))
    add("aura.static_haze", "Static Haze", "common", 150, lambda c, f=0: aura_ring(c, GREY, K, f), 2)
    add("aura.heart_beat", "Heart Beat", "uncommon", 350, lambda c, f=0: aura_ring(c, PINK, RED, f), 2)
    return items

ALL_NEW = D_hats() + D_face() + D_back_neck() + D_held() + D_auras()

# Per-species transform overrides (dx, dy, scale) — native pixels
def transforms_for(iid: str, slot: str) -> dict:
    base = {sp: {"compatible": True, "transform_native": [0, 0, 1.0]} for sp in SPECIES}
    # daemowl face: sit on lower eyes, clear third eye
    if slot == "face":
        base["daemowl"]["transform_native"] = [0, 2, 1.0]
        base["shellsnail"]["transform_native"] = [0, 1, 1.0]
        base["kernelcrab"]["transform_native"] = [0, 1, 1.0]
    if slot == "head":
        base["stacktoise"]["transform_native"] = [0, -1, 1.0]
        base["firewyrm"]["transform_native"] = [0, -1, 1.0]
        base["cachebat"]["transform_native"] = [0, -1, 1.0]
        base["shellsnail"]["transform_native"] = [0, 2, 1.0]
    if slot == "back":
        base["byteblob"]["transform_native"] = [0, -1, 1.0]
        base["cachebat"]["transform_native"] = [0, 1, 1.0]
        base["nullgeist"]["transform_native"] = [0, 1, 1.0]
    if slot == "front" and iid.startswith("front.") and any(
        k in iid for k in ("duck","mug","wand","sword","net","scroll","keyboard","phone","flag","toast","magnifier","blade")
    ):
        # held props sit on `hand`; light per-species nudges only
        for sp in SPECIES:
            base[sp]["transform_native"] = [0, 0, 1.0]
        base["kernelcrab"]["transform_native"] = [1, 0, 1.0]
        base["shellsnail"]["transform_native"] = [0, 1, 1.0]
        base["cachebat"]["transform_native"] = [1, 0, 1.0]
        base["firewyrm"]["transform_native"] = [1, 0, 1.0]
    if slot == "aura":
        base["shellsnail"]["transform_native"] = [0, 2, 1.0]
        base["kernelcrab"]["transform_native"] = [0, 2, 1.0]
    # item-specific
    SPEC = {
        "face.three_lens": {"daemowl": [0, 0, 1.0]},  # designed for third eye
        "back.webhook_wings": {"cachebat": [0, 0, 0.9], "byteblob": [0, -2, 1.0]},
        "hat.rss_antenna": {"nullgeist": [0, -2, 1.0]},
    }
    if iid in SPEC:
        for sp, tr in SPEC[iid].items():
            base[sp]["transform_native"] = list(tr)
    return base

EXISTING_IDS = [
    "hat.binary_crown", "hat.propeller_beanie", "hat.syntax_wizard",
    "face.pixel_shades", "face.gold_monocle",
    "back.circuit_wings", "back.tiny_jetpack",
    "aura.ember_halo", "aura.data_orbit",
    "front.cozy_scarf", "emote.heart_bubble",
    "habitat.plush_cushion", "title.royal_ribbon",
]

def draw_all():
    OUT.mkdir(parents=True, exist_ok=True)
    drawn = []
    for iid, slot, z, anc, rarity, price, name, fn, scale, frames in ALL_NEW:
        short = iid.split(".", 1)[1]
        c = C()
        if frames > 1:
            # frame 0
            fn(c, 0)
            p0 = c.save(short)
            c1 = C(); fn(c1, 1); p1 = c1.save(f"{short}_f1")
            drawn.append((iid, slot, z, anc, rarity, price, name, scale, frames, p0, p1))
        else:
            fn(c)
            p0 = c.save(short)
            drawn.append((iid, slot, z, anc, rarity, price, name, scale, frames, p0, None))
    return drawn

def update_manifests(drawn):
    man = json.loads((A / "manifest.launch-003.json").read_text())
    ext = json.loads((A / "art_ext.launch-003.json").read_text())
    # index existing
    by_id = {a["id"]: a for a in man["assets"]}
    for sp in SPECIES:
        if sp not in ext["species"]:
            raise SystemExit(f"missing species {sp}")

    def upsert(iid, slot, z, anc, path_rel, scale, notes, per_sp, source="scripts/draw_cosmetics.py"):
        entry = {
            "id": iid, "slot": slot, "path": path_rel,
            "rig_families": ["small_front_v1"], "z": z, "anchor": anc,
            "offset_px": [0, 0], "scale": scale,
            "notes": notes,
            "sha256": sha(A / path_rel),
        }
        if slot == "head":
            entry["occludes"] = ["ear_base"]
        if iid in by_id:
            # keep path if existing file and not redrawing existing
            old = by_id[iid]
            if iid in EXISTING_IDS:
                entry["path"] = old["path"]
                entry["sha256"] = sha(A / old["path"]) if (A / old["path"]).exists() else old.get("sha256", "")
                entry["offset_px"] = old.get("offset_px", [0, 0])
                entry["notes"] = old.get("notes", notes)
                entry["z"] = old.get("z", z)
                entry["scale"] = old.get("scale", scale)
            by_id[iid] = entry
        else:
            by_id[iid] = entry
        ext["items"][iid] = {
            "source": source,
            "attach": "cy",
            "colors": 8,
            "per_species": per_sp,
        }

    # fill existing 13 per_species
    for iid in EXISTING_IDS:
        if iid not in by_id:
            continue
        slot = by_id[iid]["slot"]
        per = transforms_for(iid, slot)
        # preserve known CORR from art_ext if present
        old = ext.get("items", {}).get(iid, {}).get("per_species", {})
        for sp, tr in old.items():
            if sp in per:
                per[sp] = tr
        # apply category defaults on top for species missing meaningful offsets
        defaults = transforms_for(iid, slot)
        for sp in SPECIES:
            if sp not in per:
                per[sp] = defaults[sp]
        upsert(iid, slot, by_id[iid]["z"], by_id[iid]["anchor"], by_id[iid]["path"],
               by_id[iid].get("scale", 1.0), by_id[iid].get("notes", ""), per,
               source=ext.get("items", {}).get(iid, {}).get("source", "source/legacy"))

    # new items
    shop_rows = []
    for iid, slot, z, anc, rarity, price, name, scale, frames, p0, p1 in drawn:
        rel = f"px3/items/{p0.name}"
        per = transforms_for(iid, slot)
        notes = f"{name}. Hand-authored 32-grid cosmetic."
        upsert(iid, slot, z, anc, rel, scale, notes, per)
        if frames > 1 and p1:
            ext["items"][iid]["frames"] = [
                {"path": rel, "sha256": sha(p0)},
                {"path": f"px3/items/{p1.name}", "sha256": sha(p1)},
            ]
        shop_rows.append((iid, name, slot, rarity, price))

    # Ensure hand anchor exists on the shared front rig + per-species overrides
    # (held props attach here). Native coords come from art_ext anchors_native.
    HAND_DEFAULTS = {
        "byteblob": [19, 23], "patchfox": [18, 18], "nullgeist": [19, 19],
        "kernelcrab": [24, 18], "cachebat": [22, 17], "stacktoise": [19, 19],
        "daemowl": [18, 19], "shellsnail": [10, 22], "regexopus": [18, 19],
        "firewyrm": [20, 18],
    }
    for sp, xy in HAND_DEFAULTS.items():
        ext["species"][sp]["anchors_native"]["hand"] = list(xy)
    rig = man.setdefault("rigs", {}).setdefault("small_front_v1", {}).setdefault("anchors", {})
    rig["hand"] = [0.58, 0.66]
    for sp, sd in man.get("species", {}).items():
        hx, hy = ext["species"][sp]["anchors_native"]["hand"]
        sd.setdefault("overrides", {})["hand"] = [round(hx / 32, 4), round(hy / 32, 4)]
    man["notes"] = (
        "launch-003: low-res handheld pixel art (native 32x32 grid, x16 nearest upscale, "
        "binary alpha, 8-12 colours/species, 3-5/item). Cosmetics pack hand-authored via "
        "scripts/draw_cosmetics.py; hand anchor for held props. See PROVENANCE.md."
    )

    man["assets"] = list(by_id.values())
    # stable order: existing first then new by id
    exist_set = set(EXISTING_IDS)
    man["assets"] = [by_id[i] for i in EXISTING_IDS if i in by_id] + sorted(
        [a for a in man["assets"] if a["id"] not in exist_set], key=lambda a: a["id"]
    )
    (A / "manifest.launch-003.json").write_text(json.dumps(man, indent=2) + "\n")
    (A / "art_ext.launch-003.json").write_text(json.dumps(ext, indent=2) + "\n")
    return shop_rows

def write_migration(shop_rows):
    mig = ROOT / "server/app/migrations/0008_cosmetics_pack.sql"
    lines = [
        "-- Wave-2 cosmetics pack (~60 hand-authored items). catalog_version stays launch-001",
        "-- so existing clients/tests keep a stable version string.",
        "INSERT OR IGNORE INTO items (",
        "    id, name, slot, rarity, price_bits, asset_id,",
        "    compatible_rigs_json, catalog_version, active",
        ") VALUES",
    ]
    vals = []
    for iid, name, slot, rarity, price in shop_rows:
        safe = name.replace("'", "''")
        vals.append(
            f"    ('{iid}', '{safe}', '{slot}', '{rarity}', {price},\n"
            f"     '{iid}', '[\"small_front_v1\"]', 'launch-001', 1)"
        )
    # also register existing launch-003 art items missing from shop
    extra = [
        ("hat.propeller_beanie", "Propeller Beanie", "head", "uncommon", 350),
        ("hat.syntax_wizard", "Syntax Wizard Hat", "head", "rare", 700),
        ("face.pixel_shades", "Pixel Shades", "face", "common", 150),
        ("face.gold_monocle", "Gold Monocle", "face", "uncommon", 350),
        ("back.circuit_wings", "Circuit Wings", "back", "rare", 700),
        ("back.tiny_jetpack", "Tiny Jetpack", "back", "epic", 1200),
        ("aura.ember_halo", "Ember Halo", "aura", "epic", 1200),
        ("aura.data_orbit", "Data Orbit", "aura", "rare", 700),
        ("front.cozy_scarf", "Cozy Scarf", "front", "common", 150),
        ("emote.heart_bubble", "Heart Bubble", "emote", "common", 150),
        ("habitat.plush_cushion", "Plush Cushion", "habitat", "uncommon", 350),
        ("title.royal_ribbon", "Royal Ribbon", "title", "rare", 700),
    ]
    for iid, name, slot, rarity, price in extra:
        vals.append(
            f"    ('{iid}', '{name}', '{slot}', '{rarity}', {price},\n"
            f"     '{iid}', '[\"small_front_v1\"]', 'launch-001', 1)"
        )
    lines.append(",\n".join(vals) + ";\n")
    mig.write_text("\n".join(lines))
    return mig

def main():
    print("drawing", len(ALL_NEW), "new cosmetics…")
    drawn = draw_all()
    shop_rows = update_manifests(drawn)
    mig = write_migration(shop_rows)
    print("wrote", len(drawn), "items; migration", mig.name)
    # counts
    from collections import Counter
    cats = Counter()
    for iid, slot, *_ in [(d[0], d[1]) for d in drawn]:
        if slot == "head": cats["hats"] += 1
        elif slot == "face": cats["face"] += 1
        elif slot == "back": cats["back"] += 1
        elif slot == "front" and any(x in iid for x in ("scarf","tie","bow","medal")): cats["neck"] += 1
        elif slot == "front": cats["held"] += 1
        elif slot == "aura": cats["aura"] += 1
        else: cats[slot] += 1
    # recount neck+back together
    print("by rough category", dict(cats))
    print("total new", len(drawn))

if __name__ == "__main__":
    main()
