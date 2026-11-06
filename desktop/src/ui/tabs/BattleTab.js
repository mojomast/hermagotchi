import { useEffect, useState } from "react";
import { jsx, jsxs } from "react/jsx-runtime";
import { StateNotice, UI_STATES } from "../states.js";
import { NpcHostBanner } from "../components/NpcHostBanner.js";
import { PetPreview } from "../components/PetPreview.js";
import { TurnLog } from "../components/TurnLog.js";
import {
  battleParticipantsFromMatch,
  battleSummary,
  battleTauntContext,
  battleTaunts,
  rewardCapNotice,
  rewardCapReason,
} from "../logic/battle.js";
import {
  CHAT_TAUNT_MAX_CHARS,
  CHAT_TAUNTS_PATH,
  chatNoticeFromEnvelope,
  tauntMessagePayload,
  tauntSummary,
  validateTauntDraft,
} from "../logic/chat.js";

export const CHALLENGE_INBOX_PLACEHOLDER = "No pending challenges.";
export const PRACTICE_BOT_NAME = "Teknium";

function envelopeMessage(envelope) {
  if (!envelope) return "The bridge did not return a response.";
  if (envelope.ok) return "";
  const error = envelope.error || {};
  return error.message || envelope.status || "Request failed.";
}

function challengeLine(challenge) {
  const mode = challenge.mode || "casual";
  const label = mode.charAt(0).toUpperCase() + mode.slice(1);
  return label + " challenge";
}

function battleAnimState(replay) {
  const events = replay && Array.isArray(replay.events) ? replay.events : [];
  let state = "idle";
  for (const event of events) {
    const status = event && event.status_delta ? event.status_delta : {};
    const damage = Number(status.damage || (event && event.damage) || 0);
    if (damage <= 0) continue;
    if (event.actor === "a") state = "attack";
    else if (event.actor === "b") state = "hurt";
  }
  return state;
}

function ChallengeRow(props) {
  const challenge = props.challenge || {};
  const busy = props.busy === challenge.id;
  const incoming = challenge.direction === "incoming";
  return jsxs("div", {
    className: "hg-row hg-challenge",
    "data-challenge-id": challenge.id || "",
    "data-direction": challenge.direction || "",
    children: [
      jsxs("div", {
        className: "hg-col",
        children: [
          jsx("strong", { children: challengeLine(challenge) }),
          jsx("span", {
            className: "hg-muted",
            children:
              (incoming ? "Incoming" : "Outgoing") +
              " · " +
              (challenge.created_at || ""),
          }),
        ],
      }),
      jsxs("div", {
        className: "hg-row",
        children: [
          incoming
            ? jsx("button", {
                type: "button",
                className: "hg-btn hg-btn--primary",
                disabled: busy,
                onClick: function () {
                  props.onRespond(challenge, "accept");
                },
                children: "Accept",
              })
            : null,
          jsx("button", {
            type: "button",
            className: "hg-btn",
            disabled: busy,
            onClick: function () {
              props.onRespond(challenge, "decline");
            },
            children: "Decline",
          }),
        ],
      }),
    ],
  });
}

function StubBattle(props) {
  return jsxs("section", {
    className: "hg-battle",
    "data-tab": "battle",
    children: [
      props.state && props.state !== UI_STATES.READY
        ? jsx(StateNotice, { state: props.state })
        : null,
      jsx(NpcHostBanner, {
        surface: "battle",
        assetBaseUrl: props.assetBaseUrl,
      }),
      jsxs("div", {
        className: "hg-card",
        children: [
          jsx("h3", { children: "Challenge inbox" }),
          jsx("p", {
            className: "hg-muted",
            "data-placeholder": "challenge-inbox",
            children: CHALLENGE_INBOX_PLACEHOLDER,
          }),
          jsx("p", {
            className: "hg-muted",
            children: "Accepted matches and replays appear here after multiplayer is enabled.",
          }),
        ],
      }),
      jsxs("div", {
        className: "hg-card",
        children: [
          jsx("h3", { children: "Practice" }),
          jsx("p", {
            className: "hg-muted",
            children: "Practice battles stay local and never change rank or Bits.",
          }),
          jsx("button", {
            type: "button",
            disabled: true,
            children: "Practice battle (disabled in stub)",
          }),
        ],
      }),
    ],
  });
}

export function BattleTab(props = {}) {
  const api = props.api;
  const uiState = props.uiState || props.state || UI_STATES.READY;
  const propPetId =
    props.petId ||
    props.pet_id ||
    (props.pet && typeof props.pet === "object" ? props.pet.id : null);
  const [mePetId, setMePetId] = useState(null);
  const petId = propPetId || mePetId;
  useEffect(() => {
    if (propPetId || !api || typeof api.get !== "function") return undefined;
    let alive = true;
    api.get("/me").then((env) => {
      if (alive && env && env.ok && env.data && env.data.pet_id) setMePetId(env.data.pet_id);
    }, () => {});
    return () => {
      alive = false;
    };
  }, [api, propPetId]);
  const [inbox, setInbox] = useState(null);
  const [practice, setPractice] = useState(null);
  const [replay, setReplay] = useState(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState("");
  const [tauntDraft, setTauntDraft] = useState("");
  const [tauntBusy, setTauntBusy] = useState(false);
  const [tauntNotice, setTauntNotice] = useState("");
  const [sentTaunts, setSentTaunts] = useState([]);
  const [manifest, setManifest] = useState(
    props.manifest || props.assetManifest || null
  );
  const [assetBaseUrl, setAssetBaseUrl] = useState(props.assetBaseUrl || "");

  useEffect(
    function () {
      if (!api || !api.assets) return undefined;
      if (!props.assetBaseUrl && typeof api.assets.url === "function") {
        setAssetBaseUrl(api.assets.url(""));
      }
      if (props.manifest || typeof api.assets.manifest !== "function") {
        return undefined;
      }
      let alive = true;
      api.assets.manifest().then(
        function (envelope) {
          if (alive && envelope && envelope.ok && envelope.data) {
            setManifest(envelope.data);
          }
        },
        function () {}
      );
      return function () {
        alive = false;
      };
    },
    [api, props.assetBaseUrl, props.manifest]
  );

  async function refreshInbox() {
    if (!api || typeof api.get !== "function") return;
    const envelope = await api.get("/challenges/inbox");
    if (envelope && envelope.ok) {
      setInbox(envelope.data || { incoming: [], outgoing: [] });
      setError("");
    } else {
      setError(envelopeMessage(envelope));
    }
  }

  useEffect(
    function () {
      let active = true;
      if (!api || typeof api.get !== "function") return undefined;
      api.get("/challenges/inbox").then(function (envelope) {
        if (!active) return;
        if (envelope && envelope.ok) {
          setInbox(envelope.data || { incoming: [], outgoing: [] });
        } else {
          setError(envelopeMessage(envelope));
        }
      });
      return function () {
        active = false;
      };
    },
    [api]
  );

  async function respond(challenge, action) {
    if (!api || typeof api.post !== "function" || !challenge || !challenge.id) return;
    setBusy(challenge.id);
    setNotice("");
    const envelope = await api.post(
      "/challenges/" + encodeURIComponent(challenge.id) + "/respond",
      { action }
    );
    setBusy("");
    if (envelope && envelope.ok) {
      setNotice(action === "accept" ? "Challenge accepted." : "Challenge declined.");
      await refreshInbox();
    } else {
      setError(envelopeMessage(envelope));
    }
  }

  async function startPractice() {
    if (!api || typeof api.post !== "function" || !petId) return;
    setBusy("practice");
    setError("");
    setNotice("");
    const body = { pet_id: petId };
    if (props.tactics) body.tactics = props.tactics;
    const envelope = await api.post("/practice", body);
    setBusy("");
    if (envelope && envelope.ok) {
      const data = envelope.data || {};
      setPractice(data);
      setReplay(data.replay || null);
      setNotice("Practice match resolved. Ratings are unchanged.");
    } else {
      setError(envelopeMessage(envelope));
    }
  }

  async function loadReplay(matchId) {
    if (!api || typeof api.get !== "function" || !matchId) return;
    setBusy("replay");
    const envelope = await api.get("/matches/" + encodeURIComponent(matchId));
    setBusy("");
    if (envelope && envelope.ok) {
      setReplay((envelope.data && envelope.data.replay) || null);
      setNotice("Replay loaded from the server.");
    } else {
      setError(envelopeMessage(envelope));
    }
  }

  if (!api) {
    return jsx(StubBattle, {
      state: uiState,
      assetBaseUrl: props.assetBaseUrl,
    });
  }

  const data = inbox || {};
  const incoming = Array.isArray(data.incoming) ? data.incoming : [];
  const outgoing = Array.isArray(data.outgoing) ? data.outgoing : [];
  const pending = [...incoming, ...outgoing];
  const practiceMatch = practice && practice.match ? practice.match : null;
  const participants = practiceMatch
    ? battleParticipantsFromMatch(practiceMatch)
    : {};
  const summary =
    practiceMatch &&
    (practiceMatch.status === "resolved" || replay)
      ? battleSummary(practiceMatch, replay || {}, participants)
      : null;
  const previewPet = props.pet || (practiceMatch && practiceMatch.pet) || null;
  const previewLoadout = props.loadout || {};
  const previewAnimState = battleAnimState(replay);
  const capNotice = rewardCapNotice(practice);
  const capReason = rewardCapReason(practice);
  const opponentTaunts = battleTaunts(practice);

  async function submitTaunt(event) {
    if (event && typeof event.preventDefault === "function") {
      event.preventDefault();
    }
    const checked = validateTauntDraft(tauntDraft);
    if (!checked.ok) {
      setTauntNotice(checked.error);
      return;
    }
    if (!api || typeof api.post !== "function" || !practiceMatch) return;
    setTauntBusy(true);
    setTauntNotice("");
    try {
      const context = battleTauntContext(practiceMatch, summary || {});
      const envelope = await api.post(
        CHAT_TAUNTS_PATH,
        tauntMessagePayload(checked.value, {
          phase: "post",
          match_context: context,
          match_id: practiceMatch.id,
        })
      );
      if (envelope && envelope.ok === true) {
        const sent =
          envelope.data && envelope.data.taunt
            ? envelope.data.taunt
            : {
                id: "sent-" + String(sentTaunts.length + 1),
                body: checked.value,
                kind: "taunt",
                phase: "post",
                actor_mode: "human",
                match_context: context,
              };
        setSentTaunts(function (current) {
          return [...current, sent];
        });
        setTauntDraft("");
        setTauntNotice("Taunt sent.");
      } else {
        const mapped = chatNoticeFromEnvelope(envelope);
        setTauntNotice(
          (mapped && (mapped.message || mapped.hostLine)) ||
            envelopeMessage(envelope)
        );
      }
    } catch (_error) {
      const mapped = chatNoticeFromEnvelope(null);
      setTauntNotice((mapped && mapped.hostLine) || "Taunt was not sent.");
    } finally {
      setTauntBusy(false);
    }
  }

  function renderTauntRow(taunt, key) {
    const summaryLine = tauntSummary(taunt.match_context);
    return jsxs(
      "li",
      {
        className: "hg-taunt hg-taunt--row",
        "data-taunt-id": taunt.id || "",
        children: [
          jsx("strong", { children: "Taunt" }),
          jsx("p", { className: "hg-taunt__body", children: taunt.body }),
          summaryLine
            ? jsx("p", {
                className: "hg-muted hg-taunt__match",
                children: summaryLine,
              })
            : null,
        ],
      },
      key
    );
  }

  return jsxs("section", {
    className: "hg-battle",
    "data-tab": "battle",
    children: [
      uiState && uiState !== UI_STATES.READY
        ? jsx(StateNotice, { state: uiState })
        : null,
      jsx(NpcHostBanner, {
        surface: "battle",
        assetBaseUrl: assetBaseUrl,
      }),
      error
        ? jsx("p", { className: "hg-error", role: "alert", children: error })
        : null,
      notice ? jsx("p", { className: "hg-muted", children: notice }) : null,
      capNotice
        ? jsx("p", {
            className: "hg-muted",
            role: "status",
            "data-reward-cap": capReason || "",
            children: capNotice,
          })
        : null,
      jsxs("div", {
        className: "hg-card",
        children: [
          jsxs("header", {
            className: "hg-card__header",
            children: [
              jsx("h3", { children: "Challenge inbox" }),
              jsx("button", {
                type: "button",
                className: "hg-btn",
                onClick: refreshInbox,
                children: "Refresh",
              }),
            ],
          }),
          pending.length
            ? jsx("div", {
                className: "hg-col",
                children: pending.map(function (challenge) {
                  return jsx(
                    ChallengeRow,
                    {
                      challenge,
                      busy,
                      onRespond: respond,
                    },
                    challenge.id
                  );
                }),
              })
            : jsx("p", {
                className: "hg-muted",
                "data-placeholder": "challenge-inbox",
                children: CHALLENGE_INBOX_PLACEHOLDER,
              }),
        ],
      }),
      jsxs("div", {
        className: "hg-card",
        children: [
          jsx("h3", { children: "Practice" }),
          jsx("p", {
            className: "hg-muted",
            children:
              "Practice battles use the " +
              PRACTICE_BOT_NAME +
              " bot, run battle-2 type matchups, and never change rank.",
          }),
          petId
            ? jsx("button", {
                type: "button",
                className: "hg-btn hg-btn--primary",
                disabled: busy === "practice",
                onClick: startPractice,
                children:
                  busy === "practice"
                    ? "Practice battle in progress..."
                    : "Battle " + PRACTICE_BOT_NAME,
              })
            : jsx("p", {
                className: "hg-muted",
                "data-placeholder": "practice-pet",
                children: "Adopt a pet to start a practice battle.",
              }),
        ],
      }),
      practiceMatch
        ? jsxs("div", {
            className: "hg-card",
            "data-match-id": practiceMatch.id || "",
            children: [
              jsx("h3", { children: "Practice result" }),
              jsxs("div", {
                className: "hg-row",
                children: [
                  jsx("span", {
                    className: "hg-badge",
                    children: practiceMatch.ruleset_version || "battle-2",
                  }),
                  jsx("span", {
                    className: "hg-badge hg-badge--" + (summary ? summary.result : ""),
                    children: summary ? summary.result : practiceMatch.result || "",
                  }),
                  jsx("span", {
                    className: "hg-muted",
                    children:
                      "Match " + String(practiceMatch.id || "").slice(0, 8),
                  }),
                ],
              }),
              summary
                ? jsxs("p", {
                    className: "hg-muted",
                    children: [
                      "Winner: ",
                      jsx("strong", { children: summary.winnerName }),
                      " · rounds ",
                      String(summary.rounds),
                      " · hash ",
                      String(summary.replayHash || "").slice(0, 12),
                    ],
                  })
                : null,
              previewPet
                ? jsx("div", {
                    className: "hg-pet-card__art hg-battle-preview",
                    "data-battle-anim-state": previewAnimState,
                    children: jsx(PetPreview, {
                      pet: previewPet,
                      loadout: previewLoadout,
                      catalog: props.catalog,
                      manifest,
                      assetBaseUrl,
                      animState: previewAnimState,
                      label:
                        (previewPet.name || "Pet") + " battle preview",
                    }),
                  })
                : null,
              jsx("button", {
                type: "button",
                className: "hg-btn",
                disabled: busy === "replay",
                onClick: function () {
                  loadReplay(practiceMatch.id);
                },
                children: "Replay match",
              }),
              jsxs("form", {
                className: "hg-taunt__compose",
                "data-taunt-phase": "post",
                onSubmit: submitTaunt,
                children: [
                  jsx("h4", { children: "Taunt after the match" }),
                  jsx("p", {
                    className: "hg-muted",
                    children:
                      "Short, display-only trash talk. Sent with phase post and the match summary.",
                  }),
                  jsxs("label", {
                    className: "hg-field",
                    children: [
                      jsx("span", { children: "Taunt" }),
                      jsx("input", {
                        className: "hg-input",
                        type: "text",
                        maxLength: String(CHAT_TAUNT_MAX_CHARS),
                        value: tauntDraft,
                        disabled: tauntBusy,
                        placeholder: "Keep it short and clean",
                        "data-taunt-input": "true",
                        onChange: function (event) {
                          setTauntDraft(event.target.value);
                        },
                      }),
                    ],
                  }),
                  tauntNotice
                    ? jsx("p", {
                        className: "hg-muted",
                        role: "status",
                        "data-taunt-notice": "true",
                        children: tauntNotice,
                      })
                    : null,
                  jsx("button", {
                    type: "submit",
                    className: "hg-btn hg-btn--primary",
                    disabled: tauntBusy,
                    "data-taunt-submit": "true",
                    children: tauntBusy ? "Sending..." : "Send taunt",
                  }),
                ],
              }),
            ],
          })
        : null,
      opponentTaunts.length || sentTaunts.length
        ? jsxs("div", {
            className: "hg-card hg-taunt-log",
            "data-section": "battle-taunts",
            children: [
              jsx("h3", { children: "Taunts" }),
              opponentTaunts.length
                ? jsx("ul", {
                    className: "hg-taunt__list",
                    "aria-label": "Opponent taunts",
                    children: opponentTaunts.map(function (taunt, index) {
                      return renderTauntRow(taunt, "opponent-" + (taunt.id || index));
                    }),
                  })
                : null,
              sentTaunts.length
                ? jsx("ul", {
                    className: "hg-taunt__list",
                    "aria-label": "Your taunts",
                    children: sentTaunts.map(function (taunt, index) {
                      return renderTauntRow(taunt, "sent-" + (taunt.id || index));
                    }),
                  })
                : null,
            ],
          })
        : null,
      replay
        ? jsx(TurnLog, {
            events: replay.events || [],
            participants,
            emptyText: "This replay has no recorded turns.",
          })
        : null,
    ],
  });
}
