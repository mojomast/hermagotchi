import test from "node:test";
import assert from "node:assert/strict";

import {
  EFFECTIVENESS,
  battleParticipantsFromMatch,
  battleSummary,
  effectivenessForTypes,
  effectivenessLabel,
  effectivenessText,
  eventEffectiveness,
  formatTurnLog,
  replaySummary,
  typeMultiplier,
} from "../../desktop/src/ui/logic/battle.js";

const participants = {
  a: { id: "pet-a", name: "Wisp", species: "nullgeist", type: "glitch" },
  b: { id: "bot", name: "Teknium", species: "byteblob", type: "kernel" },
};

test("five-type chart mirrors the server pentagon", () => {
  assert.deepEqual(typeMultiplier("signal", "kernel"), [17, 16]);
  assert.deepEqual(typeMultiplier("signal", "payload"), [17, 16]);
  assert.deepEqual(typeMultiplier("kernel", "signal"), [16, 17]);
  assert.deepEqual(typeMultiplier("glitch", "kernel"), [17, 16]);
  assert.deepEqual(typeMultiplier("kernel", "glitch"), [16, 17]);
  assert.deepEqual(typeMultiplier("signal", "signal"), [1, 1]);
  assert.deepEqual(typeMultiplier("unknown", "kernel"), [1, 1]);
});

test("effectiveness labels and text are stable", () => {
  assert.equal(effectivenessLabel([17, 16]), EFFECTIVENESS.SUPER);
  assert.equal(effectivenessLabel({ numerator: 16, denominator: 17 }), EFFECTIVENESS.RESISTED);
  assert.equal(effectivenessLabel(1), EFFECTIVENESS.NEUTRAL);
  assert.equal(effectivenessText("super"), "Super effective");
  assert.equal(effectivenessText("resisted"), "Not very effective");

  assert.deepEqual(effectivenessForTypes("glitch", "kernel"), {
    moveType: "glitch",
    defenderType: "kernel",
    numerator: 17,
    denominator: 16,
    value: 17 / 16,
    label: "super",
    text: "Super effective",
  });
});

test("eventEffectiveness prefers server type multipliers", () => {
  const event = {
    move: "basic_attack",
    status_delta: {
      move_type: "kernel",
      type_multiplier: [16, 17],
      stab_multiplier: [17, 16],
    },
  };
  assert.deepEqual(eventEffectiveness(event), {
    label: "resisted",
    text: "Not very effective",
    numerator: 16,
    denominator: 17,
    value: 16 / 17,
  });
  assert.equal(eventEffectiveness({ move: "guard", status_delta: {} }), null);
});

test("formatTurnLog renders damage, types, and effectiveness badges", () => {
  const events = [
    {
      round: 1,
      actor: "a",
      move: "basic_attack",
      hp_before: { a: 100, b: 100 },
      hp_after: { a: 100, b: 91 },
      status_delta: {
        target: "b",
        damage: 9,
        move_type: "glitch",
        type_multiplier: [17, 16],
        stab_multiplier: [17, 16],
      },
      result: "hit",
    },
    {
      round: 1,
      actor: "b",
      move: "guard",
      hp_before: { a: 100, b: 91 },
      hp_after: { a: 100, b: 91 },
      status_delta: { guarding: true },
      result: "guard",
    },
  ];

  const rows = formatTurnLog(events, { participants });
  assert.equal(rows.length, 2);
  assert.equal(rows[0].actorName, "Wisp");
  assert.equal(rows[0].actorType, "glitch");
  assert.equal(rows[0].defenderType, "kernel");
  assert.equal(rows[0].moveLabel, "Basic attack");
  assert.equal(rows[0].damage, 9);
  assert.equal(rows[0].effectiveness, "super");
  assert.equal(rows[0].effectivenessText, "Super effective");
  assert.deepEqual(rows[0].multiplier, {
    numerator: 17,
    denominator: 16,
    value: 17 / 16,
  });
  assert.match(rows[0].text, /Wisp used Basic attack for 9 damage/);

  assert.equal(rows[1].effectiveness, null);
  assert.equal(rows[1].actorName, "Teknium");
  assert.equal(rows[1].text, "Teknium used Guard (guard)");
});

test("formatTurnLog tolerates missing events and participants", () => {
  assert.deepEqual(formatTurnLog(null), []);
  const rows = formatTurnLog([
    { round: 2, actor: "b", move: "focus", result: "focus", status_delta: {} },
  ]);
  assert.equal(rows[0].actorName, "Side b");
  assert.equal(rows[0].moveLabel, "Focus");
});

test("battleParticipantsFromMatch and replaySummary shape UI data", () => {
  const match = {
    pet: { id: "pet-a", name: "Wisp", species: "nullgeist", type: "glitch" },
    bot: { id: "bot", name: "Teknium", species: "byteblob", type: "kernel" },
  };
  const parsed = battleParticipantsFromMatch(match);
  assert.equal(parsed.a.name, "Wisp");
  assert.equal(parsed.b.type, "kernel");

  const summary = replaySummary(
    {
      winner: "a",
      result: "ko",
      rounds: 4,
      replay_hash: "a".repeat(64),
      ruleset_version: "battle-2",
      events: [{}, {}],
    },
    parsed
  );
  assert.equal(summary.winnerName, "Wisp");
  assert.equal(summary.eventCount, 2);
  assert.equal(summary.replayHash, "a".repeat(64));
});

test("battleSummary reads the match header first and falls back to replay", () => {
  const fromMatch = battleSummary(
    {
      winner: "b",
      result: "ko",
      rounds: 5,
      final_hp: { a: 0, b: 37 },
      replay_hash: "b".repeat(64),
      ruleset_version: "battle-1",
    },
    {
      winner: "a",
      result: "decision",
      rounds: 99,
      replay_hash: "a".repeat(64),
      events: [{}, {}, {}],
    },
    participants
  );

  assert.equal(fromMatch.winner, "b");
  assert.equal(fromMatch.winnerName, "Teknium");
  assert.equal(fromMatch.result, "ko");
  assert.equal(fromMatch.rounds, 5);
  assert.deepEqual(fromMatch.finalHp, { a: 0, b: 37 });
  assert.equal(fromMatch.replayHash, "b".repeat(64));
  assert.equal(fromMatch.eventCount, 3);

  const fallback = battleSummary(
    { winner: null, result: null, rounds: null, final_hp: null },
    {
      winner: "a",
      result: "decision",
      rounds: 4,
      final_hp: { a: 22, b: 0 },
      replay_hash: "c".repeat(64),
      events: [{}],
    },
    participants
  );

  assert.equal(fallback.winner, "a");
  assert.equal(fallback.winnerName, "Wisp");
  assert.equal(fallback.result, "decision");
  assert.equal(fallback.rounds, 4);
  assert.deepEqual(fallback.finalHp, { a: 22, b: 0 });
  assert.equal(fallback.replayHash, "c".repeat(64));
});
