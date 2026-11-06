import { useEffect, useState } from "react";
import { jsx, jsxs } from "react/jsx-runtime";
import { StateNotice, UI_STATES } from "../states.js";
import { NpcHostBanner } from "../components/NpcHostBanner.js";
import { PetPreview } from "../components/PetPreview.js";
import { TurnLog } from "../components/TurnLog.js";
import {
  battleParticipantsFromMatch,
  replaySummary,
} from "../logic/battle.js";

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
    replay && practiceMatch ? replaySummary(replay, participants) : null;
  const previewPet = props.pet || (practiceMatch && practiceMatch.pet) || null;
  const previewLoadout = props.loadout || {};
  const previewAnimState = battleAnimState(replay);

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
