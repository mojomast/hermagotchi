/**
 * Pure ranking and bounty presentation helpers for the Desktop Leaderboard tab.
 * No React, no network.
 */

function _array(value) {
  return Array.isArray(value) ? value : [];
}

function _int(value, fallback = 0) {
  const number = Number(value);
  return Number.isFinite(number) ? Math.trunc(number) : fallback;
}

export function displayPlayerName(account = {}, pet = null) {
  const handle =
    account && typeof account.public_handle === "string"
      ? account.public_handle.trim()
      : "";
  if (handle) return handle;
  if (pet && typeof pet.name === "string" && pet.name.trim()) {
    return pet.name.trim();
  }
  return "Unranked pilot";
}

export function normalizeLeaderboard(payload = {}) {
  const entries = _array(payload.entries).map((entry) => ({
    rank: _int(entry.rank),
    accountId: entry.account && entry.account.id ? entry.account.id : null,
    publicHandle:
      entry.account && typeof entry.account.public_handle === "string"
        ? entry.account.public_handle
        : null,
    rating: _int(entry.rating),
    wins: _int(entry.wins),
    losses: _int(entry.losses),
    pet: entry.pet || null,
    player: displayPlayerName(entry.account, entry.pet),
    isMe: false,
  }));

  const meId =
    payload.me && payload.me.account && payload.me.account.id
      ? payload.me.account.id
      : null;
  for (const entry of entries) {
    entry.isMe = Boolean(meId && entry.accountId === meId);
  }

  const nearRank = _array(payload.near_rank).map((entry) => ({
    rank: _int(entry.rank),
    accountId: entry.account && entry.account.id ? entry.account.id : null,
    player: displayPlayerName(entry.account, entry.pet),
    rating: _int(entry.rating),
    petName: entry.pet && entry.pet.name ? entry.pet.name : null,
  }));

  return {
    seasonId: payload.season_id || "season-1",
    rankingVersion: payload.ranking_version || null,
    total: _int(payload.total, entries.length),
    entries,
    me: payload.me
      ? {
          rank: _int(payload.me.rank),
          accountId: meId,
          rating: _int(payload.me.rating),
          player: displayPlayerName(payload.me.account, payload.me.pet),
        }
      : null,
    nearRank,
  };
}

export function leaderboardRows(payload = {}) {
  const normalized = normalizeLeaderboard(payload);
  return normalized.entries.map((entry) => ({
    id: entry.accountId || `rank-${entry.rank}`,
    rank: entry.rank,
    player: entry.player,
    rating: entry.rating,
    wins: entry.wins,
    losses: entry.losses,
    record: `${entry.wins}-${entry.losses}`,
    petName: entry.pet && entry.pet.name ? entry.pet.name : null,
    species: entry.pet && entry.pet.species ? entry.pet.species : null,
    isMe: entry.isMe,
  }));
}

export function bountyRows(payload = {}) {
  return _array(payload.bounties).map((bounty) => {
    const reward = bounty.reward || {};
    const rewardBits = _int(reward.bits || reward.reward_bits);
    const rewardXp = _int(reward.xp || reward.reward_xp);
    return {
      id: bounty.id || "",
      title: bounty.title || bounty.id || "Bounty",
      description: bounty.description || "",
      rewardBits,
      rewardXp,
      rewardText:
        rewardBits > 0 && rewardXp > 0
          ? `${rewardBits} Bits + ${rewardXp} XP`
          : rewardBits > 0
            ? `${rewardBits} Bits`
            : `${rewardXp} XP`,
      claimed: Boolean(bounty.claimed),
      claimable: Boolean(bounty.claimable) && !bounty.claimed,
      status: bounty.claimed
        ? "Claimed"
        : bounty.claimable
          ? "Ready"
          : "Locked",
    };
  });
}

export function mergeBountyClaim(bounties, bountyId, claim = {}) {
  const list = _array(bounties);
  return list.map((bounty) => {
    if (!bounty || bounty.id !== bountyId) return bounty;
    const reward = claim.reward || bounty.reward || {};
    return {
      ...bounty,
      claimed: true,
      claimed_at: claim.claimed_at || bounty.claimed_at || null,
      claimable: false,
      reward,
    };
  });
}
