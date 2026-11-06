import { useEffect, useState } from "react";
import { jsx, jsxs } from "react/jsx-runtime";
import { StateNotice, UI_STATES } from "../states.js";
import { NpcHostBanner } from "../components/NpcHostBanner.js";
import {
  bountyRows,
  leaderboardRows,
  mergeBountyClaim,
  normalizeLeaderboard,
} from "../logic/leaderboard.js";

function envelopeMessage(envelope) {
  if (!envelope) return "The bridge did not return a response.";
  if (envelope.ok) return "";
  const error = envelope.error || {};
  return error.message || envelope.status || "Request failed.";
}

function StubLeaderboard(props) {
  return jsxs("section", {
    className: "hg-leaderboard",
    "data-tab": "leaderboard",
    children: [
      jsx(StateNotice, { state: props.state }),
      jsx(NpcHostBanner, { surface: "leaderboard", api: props.api, assetBaseUrl: props.assetBaseUrl }),
      jsxs("div", {
        className: "hg-card",
        children: [
          jsxs("header", {
            className: "hg-card__header",
            children: [
              jsx("h3", { children: "Leaderboard" }),
              jsx("span", { className: "hg-muted", children: "Season not started" }),
            ],
          }),
          jsxs("table", {
            className: "hg-table",
            children: [
              jsx("thead", {
                children: jsxs("tr", {
                  children: [
                    jsx("th", { children: "Rank" }),
                    jsx("th", { children: "Player" }),
                    jsx("th", { children: "Rating" }),
                    jsx("th", { children: "Record" }),
                  ],
                }),
              }),
              jsx("tbody", {
                children: jsx("tr", {
                  children: jsx("td", {
                    colSpan: "4",
                    className: "hg-muted",
                    children: "No ranked matches yet. Play a ranked battle to appear here.",
                  }),
                }),
              }),
            ],
          }),
        ],
      }),
      jsxs("div", {
        className: "hg-card",
        children: [
          jsx("h3", { children: "Your neighborhood" }),
          jsx("p", {
            className: "hg-muted",
            children: "Your nearby ranks appear after the first ranked result is verified.",
          }),
        ],
      }),
    ],
  });
}

function LeaderboardRow(props) {
  const row = props.row;
  return jsxs("tr", {
    className: row.isMe ? "hg-row hg-row--me" : "hg-row",
    "data-rank": String(row.rank),
    children: [
      jsx("td", { children: "#" + row.rank }),
      jsxs("td", {
        children: [
          jsx("strong", { children: row.player }),
          row.petName
            ? jsx("span", { className: "hg-muted", children: " · " + row.petName })
            : null,
        ],
      }),
      jsx("td", { children: String(row.rating) }),
      jsx("td", { children: row.record }),
    ],
  });
}

function BountyRow(props) {
  const bounty = props.bounty;
  return jsxs("tr", {
    className: "hg-row",
    "data-bounty-id": bounty.id,
    children: [
      jsxs("td", {
        children: [
          jsx("strong", { children: bounty.title }),
          bounty.description
            ? jsx("span", { className: "hg-muted", children: " · " + bounty.description })
            : null,
        ],
      }),
      jsx("td", { children: bounty.rewardText }),
      jsxs("td", {
        children: [
          jsx("span", {
            className: "hg-badge hg-badge--" + String(bounty.status).toLowerCase(),
            children: bounty.status,
          }),
          bounty.claimable
            ? jsx("button", {
                type: "button",
                className: "hg-btn hg-btn--primary",
                disabled: props.busy === bounty.id,
                onClick: function () {
                  props.onClaim(bounty.id);
                },
                children: props.busy === bounty.id ? "Claiming..." : "Claim",
              })
            : null,
        ],
      }),
    ],
  });
}

export function LeaderboardTab(props = {}) {
  const api = props.api;
  const uiState = props.uiState || props.state || UI_STATES.READY;
  const [leaderboard, setLeaderboard] = useState(null);
  const [bounties, setBounties] = useState([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState("");

  async function loadBounties() {
    if (!api || typeof api.get !== "function") return;
    const envelope = await api.get("/bounties");
    if (envelope && envelope.ok) {
      setBounties((envelope.data && envelope.data.bounties) || []);
    } else {
      setError(envelopeMessage(envelope));
    }
  }

  useEffect(
    function () {
      let active = true;
      if (!api || typeof api.get !== "function") return undefined;
      Promise.all([api.get("/leaderboard"), api.get("/bounties")]).then(function (results) {
        if (!active) return;
        const leaderboardEnvelope = results[0];
        const bountyEnvelope = results[1];
        if (leaderboardEnvelope && leaderboardEnvelope.ok) {
          setLeaderboard(leaderboardEnvelope.data || {});
        } else {
          setError(envelopeMessage(leaderboardEnvelope));
        }
        if (bountyEnvelope && bountyEnvelope.ok) {
          setBounties((bountyEnvelope.data && bountyEnvelope.data.bounties) || []);
        } else {
          setError(envelopeMessage(bountyEnvelope));
        }
      });
      return function () {
        active = false;
      };
    },
    [api]
  );

  async function claim(bountyId) {
    if (!api || typeof api.post !== "function" || !bountyId) return;
    setBusy(bountyId);
    setError("");
    setNotice("");
    const envelope = await api.post(
      "/bounties/" + encodeURIComponent(bountyId) + "/claim",
      {}
    );
    setBusy("");
    if (envelope && envelope.ok) {
      setBounties(function (current) {
        return mergeBountyClaim(current, bountyId, envelope.data || {});
      });
      setNotice("Bounty claimed.");
      await loadBounties();
    } else {
      setError(envelopeMessage(envelope));
    }
  }

  if (!api) {
    return jsx(StubLeaderboard, { state: uiState });
  }

  const normalized = normalizeLeaderboard(leaderboard || {});
  const rows = leaderboardRows(leaderboard || {});
  const bountiesForDisplay = bountyRows({ bounties });

  return jsxs("section", {
    className: "hg-leaderboard",
    "data-tab": "leaderboard",
    children: [
      uiState && uiState !== UI_STATES.READY
        ? jsx(StateNotice, { state: uiState })
        : null,
      jsx(NpcHostBanner, { surface: "leaderboard", api: props.api, assetBaseUrl: props.assetBaseUrl }),
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
              jsx("h3", { children: "Leaderboard" }),
              jsx("span", {
                className: "hg-muted",
                children: normalized.seasonId + " · " + String(normalized.total) + " ranked",
              }),
            ],
          }),
          jsxs("table", {
            className: "hg-table",
            children: [
              jsx("thead", {
                children: jsxs("tr", {
                  children: [
                    jsx("th", { children: "Rank" }),
                    jsx("th", { children: "Player" }),
                    jsx("th", { children: "Rating" }),
                    jsx("th", { children: "Record" }),
                  ],
                }),
              }),
              jsx("tbody", {
                children: rows.length
                  ? rows.map(function (row) {
                      return jsx(LeaderboardRow, { row }, row.id);
                    })
                  : jsx("tr", {
                      children: jsx("td", {
                        colSpan: "4",
                        className: "hg-muted",
                        children:
                          "No ranked matches yet. Play a ranked battle to appear here.",
                      }),
                    }),
              }),
            ],
          }),
        ],
      }),
      jsxs("div", {
        className: "hg-card",
        children: [
          jsx("h3", { children: "Your neighborhood" }),
          normalized.nearRank.length
            ? jsx("div", {
                className: "hg-grid",
                children: normalized.nearRank.map(function (entry) {
                  return jsxs(
                    "div",
                    {
                      className: "hg-card",
                      "data-rank": String(entry.rank),
                      children: [
                        jsx("strong", { children: "#" + entry.rank + " " + entry.player }),
                        jsx("span", {
                          className: "hg-muted",
                          children: entry.rating + " rating",
                        }),
                      ],
                    },
                    String(entry.rank) + "-" + String(entry.accountId)
                  );
                }),
              })
            : jsx("p", {
                className: "hg-muted",
                children:
                  "Your nearby ranks appear after the first ranked result is verified.",
              }),
        ],
      }),
      jsxs("div", {
        className: "hg-card",
        children: [
          jsx("h3", { children: "Daily bounties" }),
          bountiesForDisplay.length
            ? jsxs("table", {
                className: "hg-table",
                children: [
                  jsx("thead", {
                    children: jsxs("tr", {
                      children: [
                        jsx("th", { children: "Bounty" }),
                        jsx("th", { children: "Reward" }),
                        jsx("th", { children: "Action" }),
                      ],
                    }),
                  }),
                  jsx("tbody", {
                    children: bountiesForDisplay.map(function (bounty) {
                      return jsx(
                        BountyRow,
                        { bounty, busy, onClaim: claim },
                        bounty.id
                      );
                    }),
                  }),
                ],
              })
            : jsx("p", {
                className: "hg-muted",
                "data-placeholder": "bounties",
                children: "No active bounties right now.",
              }),
        ],
      }),
    ],
  });
}
