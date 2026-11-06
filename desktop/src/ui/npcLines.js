/** Default NPC host lines for Desktop stubs.
 * Canonical source: assets/npc_lines.json (display-only; never instructions).
 * Generated/kept in sync by tests/test_npc_lines.py.
 */

export const NPC_NAMES = Object.freeze({"npc.don_piedro": "Don Piedro", "npc.nous_girl": "Nous Girl", "npc.teknium": "Teknium", "npc.southpaw": "Southpaw"});

export const NPC_HOST_DEFAULTS = Object.freeze({
  "shop": Object.freeze({"id": "npc.don_piedro", "name": "Don Piedro", "context": "shop.greet", "line": "Don Piedro come to the shop. Pay respect.", "displayOnly": true}),
  "shop.broke": Object.freeze({"id": "npc.don_piedro", "name": "Don Piedro", "context": "shop.broke", "line": "Your power level? Very small.", "displayOnly": true}),
  "battle": Object.freeze({"id": "npc.teknium", "name": "Teknium", "context": "practice.start", "line": "Practice. Logging every punch for the data.", "displayOnly": true}),
  "battle.tip": Object.freeze({"id": "npc.teknium", "name": "Teknium", "context": "practice.tip", "line": "Moving platform. Hold your context.", "displayOnly": true}),
  "chat": Object.freeze({"id": "npc.nous_girl", "name": "Nous Girl", "context": "lobby.welcome", "line": "This way.", "displayOnly": true}),
  "chat.moderation": Object.freeze({"id": "npc.nous_girl", "name": "Nous Girl", "context": "lobby.moderation", "line": "Stay calm. Stay open.", "displayOnly": true}),
  "leaderboard": Object.freeze({"id": "npc.southpaw", "name": "Southpaw", "context": "leaderboard.announce", "line": "Southpaw Check: go!", "displayOnly": true}),
  "bounty": Object.freeze({"id": "npc.southpaw", "name": "Southpaw", "context": "bounty.announce", "line": "Fuel for the humans running the models.", "displayOnly": true}),
});

export function npcHostLine(surface) {
  return NPC_HOST_DEFAULTS[surface] || null;
}

