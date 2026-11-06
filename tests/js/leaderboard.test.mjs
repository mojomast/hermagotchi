import test from "node:test";
import assert from "node:assert/strict";

import {
  bountyRows,
  displayPlayerName,
  leaderboardRows,
  mergeBountyClaim,
  normalizeLeaderboard,
} from "../../desktop/src/ui/logic/leaderboard.js";

const LEADERBOARD = {
  season_id: "season-test",
  ranking_version: "rating-1",
  total: 3,
  entries: [
    {
      rank: 1,
      account: { id: "acct-c", public_handle: "Nyx" },
      rating: 1400,
      wins: 9,
      losses: 1,
      pet: { id: "pet-c", name: "Wisp", species: "nullgeist", loadout: {} },
    },
    {
      rank: 2,
      account: { id: "acct-a", public_handle: null },
      rating: 1200,
      wins: 3,
      losses: 2,
      pet: { id: "pet-a", name: "Nib", species: "byteblob", loadout: {} },
    },
    {
      rank: 3,
      account: { id: "acct-e", public_handle: null },
      rating: 1100,
      wins: 1,
      losses: 3,
      pet: null,
    },
  ],
  me: {
    rank: 2,
    account: { id: "acct-a", public_handle: null },
    rating: 1200,
    wins: 3,
    losses: 2,
    pet: { id: "pet-a", name: "Nib", species: "byteblob", loadout: {} },
  },
  near_rank: [
    {
      rank: 1,
      account: { id: "acct-c", public_handle: "Nyx" },
      rating: 1400,
      wins: 9,
      losses: 1,
      pet: { id: "pet-c", name: "Wisp", species: "nullgeist" },
    },
    {
      rank: 2,
      account: { id: "acct-a", public_handle: null },
      rating: 1200,
      wins: 3,
      losses: 2,
      pet: { id: "pet-a", name: "Nib", species: "byteblob" },
    },
  ],
};

test("leaderboard rows use public handles with pet-name fallback", () => {
  const rows = leaderboardRows(LEADERBOARD);
  assert.deepEqual(
    rows.map((row) => [row.rank, row.player, row.rating, row.record]),
    [
      [1, "Nyx", 1400, "9-1"],
      [2, "Nib", 1200, "3-2"],
      [3, "Unranked pilot", 1100, "1-3"],
    ]
  );
  assert.equal(rows[1].isMe, true);
  assert.equal(rows[0].isMe, false);
  assert.equal(rows[1].species, "byteblob");
});

test("normalizeLeaderboard exposes near-rank and totals", () => {
  const normalized = normalizeLeaderboard(LEADERBOARD);
  assert.equal(normalized.seasonId, "season-test");
  assert.equal(normalized.total, 3);
  assert.equal(normalized.me.rank, 2);
  assert.equal(normalized.nearRank.length, 2);
  assert.equal(normalized.nearRank[1].player, "Nib");
  assert.equal(normalized.entries[1].isMe, true);
});

test("normalizeLeaderboard handles empty and malformed payloads", () => {
  const normalized = normalizeLeaderboard();
  assert.equal(normalized.total, 0);
  assert.deepEqual(normalized.entries, []);
  assert.deepEqual(normalized.nearRank, []);
  assert.equal(normalized.me, null);
  assert.equal(displayPlayerName(null, null), "Unranked pilot");
});

test("bounty rows expose claimability and reward text", () => {
  const rows = bountyRows({
    bounties: [
      {
        id: "daily.practice",
        title: "Daily practice",
        description: "Finish one practice match.",
        reward: { bits: 150, xp: 30 },
        claimed: false,
        claimable: true,
      },
      {
        id: "daily.chat",
        title: "Say hello",
        reward: { bits: 20 },
        claimed: true,
        claimable: false,
      },
    ],
  });
  assert.equal(rows[0].rewardText, "150 Bits + 30 XP");
  assert.equal(rows[0].status, "Ready");
  assert.equal(rows[0].claimable, true);
  assert.equal(rows[1].rewardText, "20 Bits");
  assert.equal(rows[1].status, "Claimed");
  assert.equal(rows[1].claimable, false);
});

test("mergeBountyClaim marks the claimed bounty without touching others", () => {
  const source = [
    { id: "one", claimed: false, claimable: true, reward: { bits: 10 } },
    { id: "two", claimed: false, claimable: true, reward: { bits: 20 } },
  ];
  const merged = mergeBountyClaim(source, "one", {
    claimed_at: "2026-11-06T00:00:00Z",
    reward: { bits: 10 },
  });
  assert.equal(merged[0].claimed, true);
  assert.equal(merged[0].claimable, false);
  assert.equal(merged[0].claimed_at, "2026-11-06T00:00:00Z");
  assert.equal(merged[1], source[1]);
});
