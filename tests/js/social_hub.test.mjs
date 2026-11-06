import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

import {
  FRIENDS_PATH,
  FRIEND_REQUESTS_PATH,
  filterFriends,
  friendPresenceCounts,
  friendRemovePath,
  friendRequestPayload,
  friendRequestRespondPath,
  friendRequestResponsePayload,
  friendStatusLabel,
  normalizeFriends,
  validateFriendTarget,
} from "../../desktop/src/ui/logic/friends.js";
import {
  CHALLENGE_INBOX_PATH,
  CHALLENGES_PATH,
  SOCIAL_HUB_CONTEXT,
  SOCIAL_HUB_SECTIONS,
  challengeCreatePayload,
  challengeRespondPath,
  challengeResponsePayload,
  filterHistory,
  historyFilterCounts,
  normalizeChallenge,
  normalizeChallengeInbox,
  normalizeHistory,
  normalizeThreads,
  replayHref,
  replayPath,
  socialHubHost,
  threadMessagePath,
} from "../../desktop/src/ui/logic/social_hub.js";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const CHAT_TAB = readFileSync(
  path.join(ROOT, "desktop/src/ui/tabs/ChatTab.js"),
  "utf8"
);

test("social hub exposes the four Nous Girl sections", () => {
  assert.deepEqual(
    SOCIAL_HUB_SECTIONS.map((section) => section.id),
    ["dms", "friends", "challenges", "history"]
  );
  assert.equal(SOCIAL_HUB_CONTEXT, "lobby.social");
  const host = socialHubHost();
  assert.equal(host.id, "npc.nous_girl");
  assert.equal(host.name, "Nous Girl");
  assert.equal(host.context, SOCIAL_HUB_CONTEXT);
  assert.equal(host.displayOnly, true);
  assert.ok(host.line.length <= 90);
});

test("DM threads group inbox rows by channel and keep newest preview", () => {
  const threads = normalizeThreads({
    ok: true,
    data: {
      messages: [
        {
          id: "m1",
          channel_id: "dm:acct-a:acct-b",
          account_id: "acct-b",
          body: "first ping",
          created_at: "2026-11-06T00:00:00.000Z",
        },
        {
          id: "m2",
          channel_id: "dm:acct-a:acct-b",
          account_id: "acct-b",
          body: "newest ping",
          created_at: "2026-11-06T00:05:00.000Z",
          read: false,
        },
        {
          id: "m3",
          channel_id: "dm:acct-a:acct-c",
          account_id: "acct-c",
          body: "other thread",
          created_at: "2026-11-06T00:02:00.000Z",
        },
      ],
    },
  });

  assert.equal(threads.length, 2);
  assert.equal(threads[0].channel_id, "dm:acct-a:acct-b");
  assert.equal(threads[0].preview, "newest ping");
  assert.equal(threads[0].unread, true);
  assert.equal(threads[1].channel_id, "dm:acct-a:acct-c");
  assert.equal(threads[0].updated_at, "2026-11-06T00:05:00.000Z");
});

test("thread message paths stay bridge-relative and encoded", () => {
  assert.equal(
    threadMessagePath("dm:acct-a:acct-b"),
    "/chat/channels/dm:acct-a:acct-b/messages"
  );
  assert.equal(threadMessagePath("dm:space id"), "/chat/channels/dm%3Aspace%20id/messages");
  assert.equal(threadMessagePath(""), "");
});

test("challenge helpers use the existing /v1 challenge routes", () => {
  assert.equal(CHALLENGES_PATH, "/challenges");
  assert.equal(CHALLENGE_INBOX_PATH, "/challenges/inbox");
  assert.deepEqual(challengeCreatePayload("acct-friend", "ranked"), {
    defender_id: "acct-friend",
    mode: "ranked",
  });
  assert.deepEqual(challengeCreatePayload("", "bogus"), {
    defender_id: "",
    mode: "casual",
  });
  assert.equal(
    challengeRespondPath("challenge / 1"),
    "/challenges/challenge%20%2F%201/respond"
  );
  assert.deepEqual(challengeResponsePayload("accept"), { action: "accept" });
  assert.deepEqual(challengeResponsePayload("decline"), { action: "decline" });
  assert.deepEqual(challengeResponsePayload("other"), { action: "decline" });
});

test("challenge inbox normalizes incoming and outgoing rows", () => {
  const inbox = normalizeChallengeInbox({
    ok: true,
    data: {
      incoming: [
        {
          id: "c1",
          challenger_id: "acct-a",
          defender_id: "acct-b",
          mode: "casual",
          created_at: "2026-11-06T00:00:00.000Z",
        },
      ],
      outgoing: [
        {
          id: "c2",
          challenger_id: "acct-b",
          defender_id: "acct-c",
          mode: "ranked",
        },
      ],
    },
  });

  assert.equal(inbox.incoming.length, 1);
  assert.equal(inbox.outgoing.length, 1);
  assert.equal(inbox.pending.length, 2);
  assert.equal(inbox.incoming[0].direction, "incoming");
  assert.equal(inbox.outgoing[0].direction, "outgoing");
  assert.equal(inbox.incoming[0].label, "Casual challenge");
  assert.equal(normalizeChallenge({ id: "c3", mode: "weird" }).mode, "casual");
  assert.equal(normalizeChallenge(null), null);
});

test("history keeps taunts and mentions with replay links", () => {
  const history = normalizeHistory({
    ok: true,
    data: {
      messages: [
        {
          id: "t1",
          kind: "taunt",
          body: "GG",
          match_context: {
            match_id: "match-1",
            winner: "a",
            winner_name: "Wisp",
            hp: { a: 20, b: 0 },
          },
        },
        {
          id: "m1",
          body: "@Bit rematch?",
          channel_id: "lobby",
        },
        {
          id: "x1",
          body: "unrelated lobby chatter",
          channel_id: "lobby",
        },
      ],
    },
  });

  assert.equal(history.length, 2);
  assert.equal(history[0].kind, "taunt");
  assert.equal(history[0].match_id, "match-1");
  assert.equal(history[1].kind, "mention");
  assert.equal(replayHref("match-1"), "#replay/match-1");
  assert.equal(replayPath("match 1"), "/matches/match%201");
  assert.equal(replayHref(""), "");

  const counts = historyFilterCounts(history);
  assert.deepEqual(counts, { all: 2, taunt: 1, mention: 1 });
  assert.equal(filterHistory(history, "taunt").length, 1);
  assert.equal(filterHistory(history, "mention").length, 1);
  assert.equal(filterHistory(history, "all").length, 2);
  assert.equal(filterHistory(history, "all", "wisp").length, 1);
  assert.equal(filterHistory(history, "all", "missing").length, 0);
});

test("friend rows normalize presence and support roster actions", () => {
  assert.equal(FRIENDS_PATH, "/friends");
  assert.equal(FRIEND_REQUESTS_PATH, "/friends/requests");
  const roster = normalizeFriends({
    ok: true,
    data: {
      friends: [
        { account_id: "a1", public_handle: "Ada", status: "ONLINE" },
        { id: "a2", pet_name: "Bit", presence: "away" },
        { id: "a3", name: "Ghost", status: "something-else" },
      ],
      incoming: [{ id: "r1", from: "Moss" }],
      outgoing: [{ id: "r2", to: "Ember" }],
    },
  });

  assert.equal(roster.friends.length, 3);
  assert.equal(roster.friends[0].status, "online");
  assert.equal(roster.friends[1].status, "away");
  assert.equal(roster.friends[2].status, "offline");
  assert.equal(roster.incoming.length, 1);
  assert.equal(roster.outgoing.length, 1);
  assert.deepEqual(friendPresenceCounts(roster.friends), {
    online: 1,
    away: 1,
    offline: 1,
  });
  assert.equal(friendStatusLabel("away"), "Away");
  assert.equal(friendStatusLabel("bogus"), "Offline");
  assert.equal(filterFriends(roster.friends, { status: "online" }).length, 1);
  assert.equal(filterFriends(roster.friends, { query: "bit" }).length, 1);

  assert.deepEqual(validateFriendTarget(" Ada "), { ok: true, value: "Ada" });
  assert.equal(validateFriendTarget("").ok, false);
  assert.equal(validateFriendTarget("x".repeat(65)).ok, false);
  assert.deepEqual(friendRequestPayload(" Ada "), { target: "Ada" });
  assert.equal(
    friendRequestRespondPath("r 1"),
    "/friends/requests/r%201/respond"
  );
  assert.deepEqual(friendRequestResponsePayload("accept"), { action: "accept" });
  assert.deepEqual(friendRequestResponsePayload("decline"), { action: "decline" });
  assert.equal(friendRemovePath("a 1"), "/friends/a%201");
});

test("ChatTab is a Nous Girl hosted hub with DM, friend, challenge and history wiring", () => {
  assert.doesNotMatch(CHAT_TAB, /dangerouslySetInnerHTML/);
  assert.doesNotMatch(CHAT_TAB, /innerHTML/);
  assert.match(CHAT_TAB, /children:\s*message\.body/);
  assert.match(CHAT_TAB, /NpcHostBanner/);
  assert.match(CHAT_TAB, /socialHubHost/);
  assert.match(CHAT_TAB, /normalizeThreads/);
  assert.match(CHAT_TAB, /normalizeFriends/);
  assert.match(CHAT_TAB, /normalizeChallengeInbox/);
  assert.match(CHAT_TAB, /normalizeHistory/);
  assert.match(CHAT_TAB, /challengeCreatePayload/);
  assert.match(CHAT_TAB, /data-social-section/);
  assert.match(CHAT_TAB, /data-chat-dm-target/);
  assert.match(CHAT_TAB, /hg-taunt/);
  assert.match(CHAT_TAB, /tauntSummary/);
  assert.match(CHAT_TAB, /CHAT_MESSAGES_PATH/);
  assert.match(CHAT_TAB, /CHAT_INBOX_PATH/);
});
