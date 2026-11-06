/**
 * Pure battle presentation helpers for the Desktop Battle tab.
 *
 * No React and no network imports live here: the same five-type chart used by
 * the server is mirrored so tests can assert labels without running the UI.
 */

export const TYPE_ORDER = Object.freeze([
  "signal",
  "kernel",
  "payload",
  "firewall",
  "glitch",
]);

export const EFFECTIVENESS = Object.freeze({
  SUPER: "super",
  RESISTED: "resisted",
  NEUTRAL: "neutral",
});

export const EFFECTIVENESS_TEXT = Object.freeze({
  super: "Super effective",
  resisted: "Not very effective",
  neutral: "Neutral",
});

const SUPER = Object.freeze([17, 16]);
const RESISTED = Object.freeze([16, 17]);
const NEUTRAL = Object.freeze([1, 1]);

const MOVE_LABELS = Object.freeze({
  basic_attack: "Basic attack",
  quick_strike: "Quick strike",
  glitch_pulse: "Glitch pulse",
  guard: "Guard",
  focus: "Focus",
  recover: "Recover",
});

function _typeIndex(type) {
  const index = TYPE_ORDER.indexOf(type);
  return index < 0 ? -1 : index;
}

/** Return the integer [numerator, denominator] type multiplier. */
export function typeMultiplier(moveType, defenderType) {
  const attacker = _typeIndex(moveType);
  const defender = _typeIndex(defenderType);
  if (attacker < 0 || defender < 0) {
    return [NEUTRAL[0], NEUTRAL[1]];
  }
  const delta = (defender - attacker + TYPE_ORDER.length) % TYPE_ORDER.length;
  if (delta === 1 || delta === 2) {
    return [SUPER[0], SUPER[1]];
  }
  if (delta === 3 || delta === 4) {
    return [RESISTED[0], RESISTED[1]];
  }
  return [NEUTRAL[0], NEUTRAL[1]];
}

export function multiplierValue(multiplier) {
  if (Array.isArray(multiplier) && multiplier.length >= 2) {
    const numerator = Number(multiplier[0]);
    const denominator = Number(multiplier[1]);
    return denominator > 0 ? numerator / denominator : 1;
  }
  if (multiplier && typeof multiplier === "object") {
    if (typeof multiplier.value === "number") {
      return multiplier.value;
    }
    const numerator = Number(multiplier.numerator);
    const denominator = Number(multiplier.denominator);
    return denominator > 0 ? numerator / denominator : 1;
  }
  if (typeof multiplier === "number" && Number.isFinite(multiplier)) {
    return multiplier;
  }
  return 1;
}

/** Map a fraction (array/object/number) to super/resisted/neutral. */
export function effectivenessLabel(multiplier) {
  const value = multiplierValue(multiplier);
  if (value > 1) return EFFECTIVENESS.SUPER;
  if (value < 1) return EFFECTIVENESS.RESISTED;
  return EFFECTIVENESS.NEUTRAL;
}

export function effectivenessText(label) {
  return EFFECTIVENESS_TEXT[label] || EFFECTIVENESS_TEXT.neutral;
}

export function effectivenessForTypes(moveType, defenderType) {
  const multiplier = typeMultiplier(moveType, defenderType);
  const label = effectivenessLabel(multiplier);
  return {
    moveType: moveType || null,
    defenderType: defenderType || null,
    numerator: multiplier[0],
    denominator: multiplier[1],
    value: multiplier[0] / multiplier[1],
    label,
    text: effectivenessText(label),
  };
}

function _normalizeMultiplier(value) {
  if (Array.isArray(value) && value.length >= 2) {
    return { numerator: Number(value[0]), denominator: Number(value[1]) };
  }
  if (value && typeof value === "object") {
    const numerator = Number(value.numerator);
    const denominator = Number(value.denominator);
    if (Number.isFinite(numerator) && Number.isFinite(denominator) && denominator > 0) {
      return { numerator, denominator };
    }
  }
  return null;
}

/**
 * Read effectiveness from a raw engine event or an already-enriched turn-log
 * item. Always prefers the server's type multipliers when present.
 */
export function eventEffectiveness(event = {}) {
  const status = event.status_delta || {};
  const moveType = status.move_type || event.move_type || null;
  const defenderType = event.defender_type || null;
  const multiplierSource =
    status.type_multiplier ||
    event.type_multiplier ||
    event.effectiveness_multiplier ||
    event.multiplier_fraction ||
    event.multiplier ||
    (moveType && defenderType ? typeMultiplier(moveType, defenderType) : null);

  if (!moveType && !multiplierSource) {
    return null;
  }

  const normalized = _normalizeMultiplier(multiplierSource);
  if (!normalized) {
    if (event.effectiveness) {
      return {
        label: event.effectiveness,
        text: event.effectiveness_text || effectivenessText(event.effectiveness),
        numerator: null,
        denominator: null,
        value: null,
      };
    }
    return null;
  }

  const label = event.effectiveness || effectivenessLabel([
    normalized.numerator,
    normalized.denominator,
  ]);
  return {
    label,
    text: event.effectiveness_text || effectivenessText(label),
    numerator: normalized.numerator,
    denominator: normalized.denominator,
    value: normalized.numerator / normalized.denominator,
  };
}

export function moveLabel(move) {
  return MOVE_LABELS[move] || String(move || "Move").replace(/_/g, " ");
}

export function battleParticipantsFromMatch(match = {}) {
  const participants = {};
  if (match.pet && typeof match.pet === "object") {
    participants.a = {
      id: match.pet.id || null,
      name: match.pet.name || "Your pet",
      species: match.pet.species || null,
      type: match.pet.type || null,
    };
  }
  if (match.bot && typeof match.bot === "object") {
    participants.b = {
      id: match.bot.id || null,
      name: match.bot.name || "Bot",
      species: match.bot.species || null,
      type: match.bot.type || null,
    };
  }
  return participants;
}

export function formatTurnLog(events, options = {}) {
  const source = Array.isArray(events) ? events : [];
  const participants = options.participants || {};
  return source.map((event, index) => {
    const actor = event.actor || null;
    const defender = actor === "a" ? "b" : actor === "b" ? "a" : null;
    const actorInfo = actor ? participants[actor] || {} : {};
    const defenderInfo = defender ? participants[defender] || {} : {};
    const status = event.status_delta || {};
    const effectiveness = eventEffectiveness({
      ...event,
      defender_type: event.defender_type || defenderInfo.type || null,
    });
    const damage = Number(status.damage || event.damage || 0);
    const actorName = event.actor_name || actorInfo.name || (actor ? `Side ${actor}` : "Fighter");
    const label = moveLabel(event.move);
    const text =
      damage > 0
        ? `${actorName} used ${label} for ${damage} damage` +
          (effectiveness ? ` (${effectiveness.text})` : "")
        : `${actorName} used ${label}` +
          (event.result ? ` (${String(event.result).replace(/_/g, " ")})` : "");

    return {
      index,
      round: Number(event.round || 0),
      actor,
      actorName,
      actorType: event.attacker_type || actorInfo.type || null,
      defenderType: event.defender_type || defenderInfo.type || null,
      move: event.move || null,
      moveLabel: label,
      damage,
      result: event.result || null,
      hpBefore: event.hp_before || null,
      hpAfter: event.hp_after || null,
      effectiveness: effectiveness ? effectiveness.label : null,
      effectivenessText: effectiveness ? effectiveness.text : null,
      multiplier: effectiveness
        ? {
            numerator: effectiveness.numerator,
            denominator: effectiveness.denominator,
            value: effectiveness.value,
          }
        : null,
      statusDelta: status,
      text,
    };
  });
}

export function battleSummary(match = {}, replay = {}, participants = {}) {
  const matchSource = match && typeof match === "object" ? match : {};
  const replaySource = replay && typeof replay === "object" ? replay : {};

  const winner =
    matchSource.winner !== undefined && matchSource.winner !== null
      ? matchSource.winner
      : replaySource.winner || null;
  const result =
    matchSource.result !== undefined && matchSource.result !== null
      ? matchSource.result
      : replaySource.result || "unknown";
  const rounds =
    matchSource.rounds !== undefined && matchSource.rounds !== null
      ? matchSource.rounds
      : replaySource.rounds || 0;
  const finalHp =
    matchSource.final_hp !== undefined && matchSource.final_hp !== null
      ? matchSource.final_hp
      : replaySource.final_hp || null;
  const replayHash =
    matchSource.replay_hash !== undefined && matchSource.replay_hash !== null
      ? matchSource.replay_hash
      : replaySource.replay_hash || null;
  const rulesetVersion =
    matchSource.ruleset_version !== undefined &&
    matchSource.ruleset_version !== null
      ? matchSource.ruleset_version
      : replaySource.ruleset_version || null;

  const winnerName =
    winner && participants[winner] && participants[winner].name
      ? participants[winner].name
      : winner
        ? `Side ${winner}`
        : "Draw";
  return {
    winner,
    winnerName,
    result,
    rounds: Number(rounds || 0),
    finalHp,
    replayHash,
    rulesetVersion,
    eventCount: Array.isArray(replaySource.events)
      ? replaySource.events.length
      : 0,
  };
}

export function replaySummary(replay = {}, participants = {}) {
  return battleSummary({}, replay, participants);
}
