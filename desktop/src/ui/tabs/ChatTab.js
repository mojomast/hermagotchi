import { useEffect, useState } from "react";
import { jsx, jsxs } from "react/jsx-runtime";
import { NpcHostBanner } from "../components/NpcHostBanner.js";
import { npcHostLine } from "../npcLines.js";
import { StateNotice, UI_STATES } from "../states.js";
import {
  CHAT_BLOCKS_PATH,
  CHAT_DM_TARGET_MAX_CHARS,
  CHAT_INBOX_PATH,
  CHAT_MESSAGES_PATH,
  CHAT_MESSAGE_MAX_CHARS,
  CHAT_REPORT_PATH,
  CHAT_REPORT_REASON,
  chatActionNotice,
  chatMessagePayload,
  chatModerationHost,
  chatNoticeFromEnvelope,
  isChatEnabled,
  isTauntMessage,
  markInboxRead,
  markInboxReadRequest,
  mergeMessages,
  messageFromEnvelope,
  normalizeInbox,
  normalizeMessages,
  tauntSummary,
  validateChatDraft,
  validateDmTarget,
  displayActorLabel,
  formatRelativeTime,
} from "../logic/chat.js";
import { FRIENDS_PATH,
  FRIEND_REQUESTS_PATH,
  filterFriends,
  friendPresenceCounts,
  friendRemovePath,
  friendRequestPayload,
  friendRequestRespondPath,
  friendRequestResponsePayload,
  normalizeFriends,
  validateFriendTarget,
} from "../logic/friends.js";
import {
  CHALLENGES_PATH,
  CHALLENGE_INBOX_PATH,
  SOCIAL_HUB_SECTIONS,
  challengeCreatePayload,
  challengeRespondPath,
  challengeResponsePayload,
  filterHistory,
  historyFilterCounts,
  normalizeChallengeInbox,
  normalizeHistory,
  normalizeThreads,
  replayHref,
  socialHubHost,
  threadMessagePath,
} from "../logic/social_hub.js";

const HISTORY_FILTERS = Object.freeze([
  Object.freeze({ id: "all", label: "All" }),
  Object.freeze({ id: "taunt", label: "Taunts" }),
  Object.freeze({ id: "mention", label: "@mentions" }),
]);

function ChatOffStub(props) {
  const uiState = props.uiState || UI_STATES.NETWORK_OFF;

  return jsxs("section", {
    className: "hg-chat",
    "data-tab": "chat",
    children: [
      uiState && uiState !== UI_STATES.READY
        ? jsx(StateNotice, { state: uiState })
        : null,
      jsx(NpcHostBanner, { surface: "chat", api: props.api, assetBaseUrl: props.assetBaseUrl }),
      jsxs("div", {
        className: "hg-card",
        children: [
          jsx("h3", { children: "Chat is off by default" }),
          jsx("p", {
            className: "hg-muted",
            children:
              "The social hub stays unavailable until the owner enables chat and the device is paired.",
          }),
          jsxs("label", {
            className: "hg-field",
            children: [
              jsx("span", { children: "Message" }),
              jsx("textarea", {
                disabled: true,
                rows: "3",
                placeholder: "Chat is disabled in this stub",
              }),
            ],
          }),
          jsxs("div", {
            className: "hg-actions",
            children: [
              jsx("button", { type: "button", disabled: true, children: "Send (disabled)" }),
              jsx("button", { type: "button", disabled: true, children: "Mute" }),
              jsx("button", { type: "button", disabled: true, children: "Block" }),
              jsx("button", { type: "button", disabled: true, children: "Report" }),
            ],
          }),
        ],
      }),
    ],
  });
}

function SocialSection(props) {
  return jsxs("div", {
    className: "hg-card hg-social__section",
    "data-social-section": props.id,
    children: [
      jsxs("header", {
        className: "hg-card__header",
        children: [
          jsx("h3", { children: props.title }),
          props.badge ? jsx("span", { className: "hg-badge", children: props.badge }) : null,
        ],
      }),
      props.children,
    ],
  });
}

function InboxBadge(props) {
  const count = Number(props.count) || 0;
  return jsx("span", {
    className:
      count > 0
        ? "hg-badge hg-inbox__badge hg-inbox__badge--unread"
        : "hg-badge hg-inbox__badge",
    "data-inbox-unread": String(count),
    children: count > 0 ? String(count) + " unread" : "Clear",
  });
}

function TauntActions(props) {
  return jsxs("div", {
    className: "hg-actions hg-actions--tight",
    children: [
      jsx("button", {
        type: "button",
        className: "hg-btn",
        disabled: props.busy,
        onClick: function () {
          props.onReport(props.message);
        },
        children: "Report",
      }),
      jsx("button", {
        type: "button",
        className: "hg-btn",
        disabled: props.busy,
        onClick: function () {
          props.onBlock(props.message);
        },
        children: "Block",
      }),
    ],
  });
}

function MessageRow(props) {
  const message = props.message;
  const busy = props.busy;
  const actor = displayActorLabel(message);

  if (isTauntMessage(message)) {
    const summary = tauntSummary(message.match_context);
    return jsxs("li", {
      className: "hg-log__item hg-taunt",
      "data-message-id": message.id,
      "data-actor-mode": message.actor_mode,
      "data-message-kind": "taunt",
      children: [
        jsxs("div", {
          className: "hg-taunt__bubble",
          children: [
            jsxs("div", {
              className: "hg-row hg-row--between",
              children: [
                jsx("strong", { children: actor + " taunt" }),
                jsx("time", {
                  className: "hg-muted hg-time",
                  dateTime: message.created_at || undefined,
                  title: message.created_at || undefined,
                  children: formatRelativeTime(message.created_at) || message.created_at || "Unknown time",
                }),
              ],
            }),
            jsx("p", {
              className: "hg-taunt__body",
              children: message.body,
            }),
            summary
              ? jsx("p", {
                  className: "hg-taunt__match",
                  "data-taunt-match": "true",
                  children: summary,
                })
              : null,
            jsx(TauntActions, {
              message,
              busy,
              onReport: props.onReport,
              onBlock: props.onBlock,
            }),
          ],
        }),
      ],
    });
  }

  return jsxs("li", {
    className: "hg-log__item",
    "data-message-id": message.id,
    "data-actor-mode": message.actor_mode,
    children: [
      jsxs("div", {
        className: "hg-row hg-row--between",
        children: [
          jsx("strong", { children: actor }),
          jsx("time", {
            className: "hg-muted hg-time",
            dateTime: message.created_at || undefined,
            title: message.created_at || undefined,
            children: formatRelativeTime(message.created_at) || message.created_at || "Unknown time",
          }),
        ],
      }),
      jsx("p", {
        className: "hg-log__body",
        children: message.body,
      }),
      jsxs("div", {
        className: "hg-actions hg-actions--tight",
        children: [
          jsx("button", {
            type: "button",
            className: "hg-btn",
            disabled: busy,
            onClick: function () {
              props.onReport(message);
            },
            children: "Report",
          }),
          jsx("button", {
            type: "button",
            className: "hg-btn",
            disabled: busy,
            onClick: function () {
              props.onBlock(message);
            },
            children: "Block",
          }),
        ],
      }),
    ],
  });
}

function DmSection(props) {
  const threads = props.threads || [];
  const inbox = props.inbox || { unreadCount: 0 };
  const conversation = props.conversation || [];
  const activeThread = props.activeThread;

  return jsx(SocialSection, {
    id: "dms",
    title: "Direct messages",
    badge: jsx(InboxBadge, { count: inbox.unreadCount }),
    children: [
      jsx("p", {
        className: "hg-muted",
        children:
          "DM threads stay plain text. Pick a thread or type a player or pet name to start one.",
      }),
      jsxs("div", {
        className: "hg-social__split",
        children: [
          jsxs("div", {
            className: "hg-col hg-social__threads",
            "aria-label": "DM threads",
            children: [
              jsx("div", {
                className: "hg-actions hg-actions--tight",
                children: [
                  jsx("button", {
                    type: "button",
                    className: "hg-btn",
                    onClick: props.onRefresh,
                    disabled: props.busy,
                    children: "Refresh inbox",
                  }),
                  jsx("button", {
                    type: "button",
                    className: "hg-btn",
                    onClick: props.onOpenInbox,
                    disabled: props.busy,
                    "data-inbox-open": props.inboxOpen ? "true" : "false",
                    children: props.inboxOpen ? "Hide inbox" : "Open inbox",
                  }),
                ],
              }),
              threads.length
                ? jsx("ul", {
                    className: "hg-inbox__list hg-chat__thread",
                    children: threads.map(function (thread) {
                      const active = activeThread && activeThread.channel_id === thread.channel_id;
                      return jsxs(
                        "li",
                        {
                          className:
                            "hg-inbox__item hg-inbox__item--dm" +
                            (thread.unread ? " hg-inbox__item--unread" : "") +
                            (active ? " hg-inbox__item--active" : ""),
                          "data-inbox-id": thread.channel_id,
                          "data-inbox-kind": "dm",
                          children: [
                            jsxs("button", {
                              type: "button",
                              className: "hg-btn hg-btn--ghost",
                              onClick: function () {
                                props.onSelectThread(thread);
                              },
                              children: [
                                jsx("strong", { children: thread.peer || "DM" }),
                                thread.unread
                                  ? jsx("span", { className: "hg-badge", children: "unread" })
                                  : null,
                              ],
                            }),
                            jsx("p", {
                              className: "hg-inbox__preview",
                              children: thread.preview || "",
                            }),
                            jsx("time", {
                              className: "hg-muted hg-time",
                              dateTime: thread.updated_at || undefined,
                              title: thread.updated_at || undefined,
                              children:
                                formatRelativeTime(thread.updated_at) ||
                                thread.updated_at ||
                                "",
                            }),
                          ],
                        },
                        thread.channel_id
                      );
                    }),
                  })
                : jsx("p", {
                    className: "hg-muted",
                    "data-placeholder": "social-dm-empty",
                    children: "No direct messages yet.",
                  }),
            ],
          }),
          jsxs("div", {
            className: "hg-col hg-social__conversation",
            "aria-label": "DM conversation",
            children: [
              jsx("h4", {
                children: activeThread
                  ? "Conversation with " + (activeThread.peer || "your friend")
                  : "Conversation",
              }),
              conversation.length
                ? jsx("ol", {
                    className: "hg-log",
                    "aria-live": "polite",
                    children: conversation.map(function (message) {
                      return jsx(
                        MessageRow,
                        {
                          message,
                          busy: props.busy,
                          onReport: props.onReport,
                          onBlock: props.onBlock,
                        },
                        message.id
                      );
                    }),
                  })
                : jsx("p", {
                    className: "hg-muted",
                    "data-placeholder": "social-conversation-empty",
                    children: activeThread
                      ? "No messages in this thread yet."
                      : "Select a thread or enter a name below.",
                  }),
            ],
          }),
        ],
      }),
      jsxs("form", {
        className: "hg-chat__compose",
        onSubmit: props.onSubmit,
        children: [
          jsxs("label", {
            className: "hg-field",
            children: [
              jsx("span", { children: "Message" }),
              jsx("textarea", {
                className: "hg-input",
                rows: "3",
                maxLength: String(CHAT_MESSAGE_MAX_CHARS),
                value: props.draft,
                disabled: props.busy,
                placeholder: "Write a plain-text direct message",
                onChange: function (event) {
                  props.onDraft(event.target.value);
                },
              }),
            ],
          }),
          jsxs("label", {
            className: "hg-field hg-chat__dm-target",
            children: [
              jsx("span", { children: "Send to player or pet" }),
              jsx("input", {
                className: "hg-input",
                type: "text",
                maxLength: String(CHAT_DM_TARGET_MAX_CHARS),
                value: props.dmTarget,
                disabled: props.busy,
                placeholder: "Player or pet name",
                "data-chat-dm-target": "true",
                onChange: function (event) {
                  props.onTarget(event.target.value);
                },
              }),
            ],
          }),
          props.composerError
            ? jsx("p", {
                className: "hg-error",
                role: "alert",
                children: props.composerError,
              })
            : null,
          jsxs("div", {
            className: "hg-actions",
            children: [
              jsx("button", {
                type: "submit",
                className: "hg-btn hg-btn--primary",
                disabled: props.busy,
                children: props.busy ? "Working..." : "Send DM",
              }),
            ],
          }),
        ],
      }),
    ],
  });
}

function FriendsSection(props) {
  const roster = props.roster || { friends: [], incoming: [], outgoing: [] };
  const counts = friendPresenceCounts(roster.friends);
  const friends = filterFriends(roster.friends, {
    status: props.statusFilter,
    query: props.query,
  });

  return jsx(SocialSection, {
    id: "friends",
    title: "Friends",
    badge: counts.online + " online",
    children: [
      jsxs("form", {
        className: "hg-actions",
        onSubmit: props.onAdd,
        children: [
          jsxs("label", {
            className: "hg-field",
            children: [
              jsx("span", { children: "Add friend" }),
              jsx("input", {
                className: "hg-input",
                type: "text",
                value: props.friendTarget,
                disabled: props.busy,
                placeholder: "Player or pet name",
                "data-friend-target": "true",
                onChange: function (event) {
                  props.onFriendTarget(event.target.value);
                },
              }),
            ],
          }),
          jsx("button", {
            type: "submit",
            className: "hg-btn hg-btn--primary",
            disabled: props.busy,
            children: "Add",
          }),
        ],
      }),
      roster.incoming.length
        ? jsxs("div", {
            className: "hg-col",
            "data-friend-requests": "incoming",
            children: [
              jsx("h4", { children: "Friend requests" }),
              ...roster.incoming.map(function (request) {
                return jsxs(
                  "div",
                  {
                    className: "hg-row hg-row--between hg-friend__request",
                    "data-friend-request-id": request.id,
                    children: [
                      jsx("strong", { children: request.name || "Unknown player" }),
                      jsxs("div", {
                        className: "hg-actions hg-actions--tight",
                        children: [
                          jsx("button", {
                            type: "button",
                            className: "hg-btn hg-btn--primary",
                            disabled: props.busy,
                            onClick: function () {
                              props.onRespondRequest(request, "accept");
                            },
                            children: "Accept",
                          }),
                          jsx("button", {
                            type: "button",
                            className: "hg-btn",
                            disabled: props.busy,
                            onClick: function () {
                              props.onRespondRequest(request, "decline");
                            },
                            children: "Decline",
                          }),
                        ],
                      }),
                    ],
                  },
                  request.id
                );
              }),
            ],
          })
        : null,
      jsxs("div", {
        className: "hg-actions",
        children: [
          jsx("label", {
            className: "hg-field",
            children: [
              jsx("span", { children: "Filter" }),
              jsx("input", {
                className: "hg-input",
                type: "search",
                value: props.query,
                placeholder: "Search friends",
                "data-friend-search": "true",
                onChange: function (event) {
                  props.onQuery(event.target.value);
                },
              }),
            ],
          }),
          jsx("button", {
            type: "button",
            className: "hg-btn",
            onClick: function () {
              props.onStatus("all");
            },
            children: "All (" + roster.friends.length + ")",
          }),
          jsx("button", {
            type: "button",
            className: "hg-btn",
            onClick: function () {
              props.onStatus("online");
            },
            children: "Online (" + counts.online + ")",
          }),
          jsx("button", {
            type: "button",
            className: "hg-btn",
            onClick: function () {
              props.onStatus("away");
            },
            children: "Away (" + counts.away + ")",
          }),
          jsx("button", {
            type: "button",
            className: "hg-btn",
            onClick: function () {
              props.onStatus("offline");
            },
            children: "Offline (" + counts.offline + ")",
          }),
        ],
      }),
      friends.length
        ? jsx("ul", {
            className: "hg-social__friends",
            children: friends.map(function (friend) {
              return jsxs(
                "li",
                {
                  className: "hg-row hg-row--between hg-friend",
                  "data-friend-id": friend.id,
                  "data-friend-status": friend.status,
                  children: [
                    jsxs("div", {
                      className: "hg-col",
                      children: [
                        jsx("strong", { children: friend.name }),
                        jsxs("span", {
                          className: "hg-muted",
                          children: [
                            friend.status_label,
                            friend.pet_name &&
                            (!friend.name || friend.name.indexOf(friend.pet_name) === -1)
                              ? " · " + friend.pet_name
                              : "",
                          ],
                        }),
                      ],
                    }),
                    jsxs("div", {
                      className: "hg-actions hg-actions--tight",
                      children: [
                        jsx("button", {
                          type: "button",
                          className: "hg-btn hg-btn--primary",
                          disabled: props.busy || !(friend.account_id || friend.id),
                          onClick: function () {
                            props.onChallenge(friend);
                          },
                          "data-challenge-friend": friend.id,
                          children: "Challenge",
                        }),
                        jsx("button", {
                          type: "button",
                          className: "hg-btn",
                          disabled: props.busy,
                          onClick: function () {
                            props.onRemove(friend);
                          },
                          children: "Remove",
                        }),
                      ],
                    }),
                  ],
                },
                friend.id
              );
            }),
          })
        : jsx("p", {
            className: "hg-muted",
            "data-placeholder": "social-friends-empty",
            children: "No friends match this filter.",
          }),
    ],
  });
}

function ChallengesSection(props) {
  const inbox = props.challengeInbox || { pending: [] };
  const pending = inbox.pending || [];

  return jsx(SocialSection, {
    id: "challenges",
    title: "Challenges",
    badge: String(pending.length) + " pending",
    children: [
      jsx("p", {
        className: "hg-muted",
        children:
          "Challenge a friend from the roster. Incoming challenges can be accepted or declined here.",
      }),
      pending.length
        ? jsx("div", {
            className: "hg-col",
            children: pending.map(function (challenge) {
              const incoming = challenge.direction === "incoming";
              return jsxs(
                "div",
                {
                  className: "hg-row hg-row--between hg-challenge",
                  "data-challenge-id": challenge.id,
                  "data-direction": challenge.direction,
                  children: [
                    jsxs("div", {
                      className: "hg-col",
                      children: [
                        jsx("strong", { children: challenge.label }),
                        jsxs("span", {
                          className: "hg-muted",
                          children: [
                            (incoming ? "Incoming" : "Outgoing") + " · ",
                            jsx("time", {
                              className: "hg-time",
                              dateTime: challenge.created_at || undefined,
                              title: challenge.created_at || undefined,
                              children:
                                formatRelativeTime(challenge.created_at) ||
                                challenge.created_at ||
                                "",
                            }),
                          ],
                        }),
                      ],
                    }),
                    jsxs("div", {
                      className: "hg-actions hg-actions--tight",
                      children: [
                        incoming
                          ? jsx("button", {
                              type: "button",
                              className: "hg-btn hg-btn--primary",
                              disabled: props.busy,
                              onClick: function () {
                                props.onRespond(challenge, "accept");
                              },
                              children: "Accept",
                            })
                          : null,
                        jsx("button", {
                          type: "button",
                          className: "hg-btn",
                          disabled: props.busy,
                          onClick: function () {
                            props.onRespond(challenge, "decline");
                          },
                          children: "Decline",
                        }),
                      ],
                    }),
                  ],
                },
                challenge.id
              );
            }),
          })
        : jsx("p", {
            className: "hg-muted",
            "data-placeholder": "social-challenges-empty",
            children: "No pending challenges.",
          }),
    ],
  });
}

function HistorySection(props) {
  const counts = historyFilterCounts(props.history);
  const rows = filterHistory(props.history, props.filter, props.query);

  return jsx(SocialSection, {
    id: "history",
    title: "Taunts & mentions",
    badge: String(counts.all) + " recent",
    children: [
      jsxs("div", {
        className: "hg-actions",
        children: [
          ...HISTORY_FILTERS.map(function (filter) {
            return jsx(
              "button",
              {
                type: "button",
                className:
                  props.filter === filter.id ? "hg-btn hg-btn--primary" : "hg-btn",
                onClick: function () {
                  props.onFilter(filter.id);
                },
                children: filter.label + " (" + counts[filter.id] + ")",
              },
              filter.id
            );
          }),
          jsx("input", {
            className: "hg-input",
            type: "search",
            value: props.query,
            placeholder: "Search taunts and mentions",
            "data-history-search": "true",
            onChange: function (event) {
              props.onQuery(event.target.value);
            },
          }),
        ],
      }),
      rows.length
        ? jsx("ul", {
            className: "hg-social__history",
            children: rows.map(function (item) {
              return jsxs(
                "li",
                {
                  className:
                    item.kind === "taunt"
                      ? "hg-taunt hg-taunt--row"
                      : "hg-inbox__item hg-inbox__item--mention",
                  "data-history-id": item.id,
                  "data-history-kind": item.kind,
                  children: [
                    jsxs("div", {
                      className: "hg-row hg-row--between",
                      children: [
                        jsx("strong", {
                          children:
                            (item.kind === "taunt" ? "Taunt" : "@mention") +
                            (item.from ? " · " + item.from : ""),
                        }),
                        jsx("time", {
                          className: "hg-muted hg-time",
                          dateTime: item.created_at || undefined,
                          title: item.created_at || undefined,
                          children: formatRelativeTime(item.created_at) || item.created_at || "",
                        }),
                      ],
                    }),
                    jsx("p", {
                      className:
                        item.kind === "taunt" ? "hg-taunt__body" : "hg-log__body",
                      children: item.body,
                    }),
                    item.match_summary
                      ? jsx("p", {
                          className: "hg-muted hg-taunt__match",
                          "data-taunt-match": "true",
                          children: item.match_summary,
                        })
                      : null,
                    item.match_id
                      ? jsx("a", {
                          className: "hg-btn",
                          href: replayHref(item.match_id),
                          "data-replay-link": item.match_id,
                          children: "Replay match",
                        })
                      : null,
                  ],
                },
                item.id
              );
            }),
          })
        : jsx("p", {
            className: "hg-muted",
            "data-placeholder": "social-history-empty",
            children: "No taunts or @mentions match this filter.",
          }),
    ],
  });
}

function ChatLive(props) {
  const api = props.api;
  const uiState = props.uiState || props.state || UI_STATES.READY;
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [draft, setDraft] = useState("");
  const [dmTarget, setDmTarget] = useState("");
  const [composerError, setComposerError] = useState("");
  const [notice, setNotice] = useState(null);
  const [busy, setBusy] = useState(false);
  const [refreshTick, setRefreshTick] = useState(0);
  const [inbox, setInbox] = useState({
    items: [],
    unreadCount: 0,
    total: 0,
    dms: [],
    mentions: [],
  });
  const [inboxOpen, setInboxOpen] = useState(false);
  const [inboxBusy, setInboxBusy] = useState(false);
  const [activeThread, setActiveThread] = useState(null);
  const [conversation, setConversation] = useState([]);
  const [roster, setRoster] = useState({
    friends: [],
    incoming: [],
    outgoing: [],
    total: 0,
  });
  const [friendTarget, setFriendTarget] = useState("");
  const [friendQuery, setFriendQuery] = useState("");
  const [friendStatus, setFriendStatus] = useState("all");
  const [challengeInbox, setChallengeInbox] = useState({
    incoming: [],
    outgoing: [],
    pending: [],
  });
  const [challengeBusy, setChallengeBusy] = useState(false);
  const [historyFilter, setHistoryFilter] = useState("all");
  const [historyQuery, setHistoryQuery] = useState("");

  useEffect(
    function () {
      let cancelled = false;
      setLoading(true);

      api
        .get(CHAT_MESSAGES_PATH)
        .then(function (envelope) {
          if (cancelled) return;
          if (envelope && envelope.ok === true) {
            setMessages(normalizeMessages(envelope));
            setNotice(null);
          } else {
            setNotice(chatNoticeFromEnvelope(envelope));
          }
        })
        .catch(function () {
          if (!cancelled) setNotice(chatNoticeFromEnvelope(null));
        })
        .then(function () {
          if (!cancelled) setLoading(false);
        });

      return function () {
        cancelled = true;
      };
    },
    [api, refreshTick]
  );

  async function loadInbox() {
    if (!api || typeof api.get !== "function") return;
    const envelope = await api.get(CHAT_INBOX_PATH);
    if (envelope && envelope.ok === true) {
      setInbox(normalizeInbox(envelope));
    } else {
      setNotice(chatNoticeFromEnvelope(envelope));
    }
  }

  useEffect(
    function pollInbox() {
      if (!api || typeof api.get !== "function") {
        return undefined;
      }
      let cancelled = false;
      async function load() {
        try {
          const envelope = await api.get(CHAT_INBOX_PATH);
          if (!cancelled && envelope && envelope.ok === true) {
            setInbox(normalizeInbox(envelope));
          }
        } catch (_error) {
          /* Inbox polling stays quiet; the hub notice owns errors. */
        }
      }
      load();
      const timer = setInterval(load, 30000);
      return function () {
        cancelled = true;
        clearInterval(timer);
      };
    },
    [api]
  );

  useEffect(
    function loadRoster() {
      if (!api || typeof api.get !== "function") return undefined;
      let cancelled = false;
      api.get("/friends").then(
        function (envelope) {
          if (cancelled) return;
          if (envelope && envelope.ok === true) {
            setRoster(normalizeFriends(envelope));
          }
        },
        function () {}
      );
      return function () {
        cancelled = true;
      };
    },
    [api, refreshTick]
  );

  async function loadChallenges() {
    if (!api || typeof api.get !== "function") return;
    const envelope = await api.get(CHALLENGE_INBOX_PATH);
    if (envelope && envelope.ok === true) {
      setChallengeInbox(normalizeChallengeInbox(envelope));
    }
  }

  useEffect(
    function loadChallengeInbox() {
      if (!api || typeof api.get !== "function") return undefined;
      let cancelled = false;
      api.get(CHALLENGE_INBOX_PATH).then(
        function (envelope) {
          if (cancelled) return;
          if (envelope && envelope.ok === true) {
            setChallengeInbox(normalizeChallengeInbox(envelope));
          }
        },
        function () {}
      );
      return function () {
        cancelled = true;
      };
    },
    [api, refreshTick]
  );

  useEffect(
    function loadConversation() {
      if (
        !activeThread ||
        !activeThread.channel_id ||
        !api ||
        typeof api.get !== "function"
      ) {
        setConversation([]);
        return undefined;
      }
      let cancelled = false;
      const path = threadMessagePath(activeThread.channel_id);
      api.get(path).then(
        function (envelope) {
          if (cancelled) return;
          if (envelope && envelope.ok === true) {
            setConversation(normalizeMessages(envelope));
          } else {
            setConversation([]);
          }
        },
        function () {
          if (!cancelled) setConversation([]);
        }
      );
      return function () {
        cancelled = true;
      };
    },
    [api, activeThread]
  );

  async function refreshInbox() {
    setInboxBusy(true);
    try {
      await loadInbox();
    } catch (_error) {
      setNotice(chatNoticeFromEnvelope(null));
    } finally {
      setInboxBusy(false);
    }
  }

  async function openInbox() {
    if (inboxOpen) {
      setInboxOpen(false);
      return;
    }
    setInboxOpen(true);
    const unreadIds = (inbox.items || [])
      .filter(function (item) {
        return item.unread;
      })
      .map(function (item) {
        return item.id;
      });
    if (!unreadIds.length) return;
    setInbox(function (current) {
      return markInboxRead(current);
    });
    try {
      await markInboxReadRequest(api, unreadIds);
    } catch (_error) {
      /* Local read state is still useful if the bridge cannot persist it. */
    }
  }

  function selectThread(thread) {
    setActiveThread(thread);
    setDmTarget(thread.peer_id || thread.peer || "");
    setComposerError("");
  }

  async function submitMessage(event) {
    if (event && typeof event.preventDefault === "function") {
      event.preventDefault();
    }
    const checked = validateChatDraft(draft);
    if (!checked.ok) {
      setComposerError(checked.error);
      return;
    }
    const target = dmTarget || (activeThread && (activeThread.peer_id || activeThread.peer)) || "";
    const checkedTarget = validateDmTarget(target);
    if (!checkedTarget.ok) {
      setComposerError(checkedTarget.error);
      return;
    }
    if (!checkedTarget.value) {
      setComposerError("Choose a player or pet to DM.");
      return;
    }

    setComposerError("");
    setBusy(true);
    try {
      const envelope = await api.post(
        CHAT_MESSAGES_PATH,
        chatMessagePayload(checked.value, checkedTarget.value)
      );
      if (envelope && envelope.ok === true) {
        const sent = messageFromEnvelope(envelope);
        if (sent) {
          setConversation(function (current) {
            return mergeMessages(current, [sent]);
          });
        }
        setDraft("");
        setNotice(null);
      } else {
        setNotice(chatNoticeFromEnvelope(envelope));
      }
    } catch (_error) {
      setNotice(chatNoticeFromEnvelope(null));
    } finally {
      setBusy(false);
    }
  }

  async function blockMessage(message) {
    if (!message || !message.account_id) return;
    setBusy(true);
    try {
      const envelope = await api.post(CHAT_BLOCKS_PATH, {
        blocked_id: message.account_id,
      });
      if (envelope && envelope.ok === true) {
        setConversation(function (current) {
          return current.filter(function (item) {
            return item.account_id !== message.account_id;
          });
        });
        setNotice(chatActionNotice("blocked"));
      } else {
        setNotice(chatNoticeFromEnvelope(envelope));
      }
    } catch (_error) {
      setNotice(chatNoticeFromEnvelope(null));
    } finally {
      setBusy(false);
    }
  }

  async function reportMessage(message) {
    if (!message || !message.id) return;
    setBusy(true);
    try {
      const envelope = await api.post(CHAT_REPORT_PATH, {
        target_type: "message",
        target_id: message.id,
        reason: CHAT_REPORT_REASON,
      });
      setNotice(
        envelope && envelope.ok === true
          ? chatActionNotice("reported")
          : chatNoticeFromEnvelope(envelope)
      );
    } catch (_error) {
      setNotice(chatNoticeFromEnvelope(null));
    } finally {
      setBusy(false);
    }
  }

  async function addFriend(event) {
    if (event && typeof event.preventDefault === "function") {
      event.preventDefault();
    }
    const checked = validateFriendTarget(friendTarget);
    if (!checked.ok) {
      setNotice({
        kind: "error",
        code: "friend_target",
        message: checked.error,
        hostLine: npcHostLine("chat").line,
      });
      return;
    }
    setBusy(true);
    try {
      const envelope = await api.post(
        FRIENDS_PATH,
        friendRequestPayload(checked.value)
      );
      if (envelope && envelope.ok === true) {
        setFriendTarget("");
        setNotice(null);
        setRefreshTick(function (tick) {
          return tick + 1;
        });
      } else {
        setNotice(chatNoticeFromEnvelope(envelope));
      }
    } catch (_error) {
      setNotice(chatNoticeFromEnvelope(null));
    } finally {
      setBusy(false);
    }
  }

  async function respondToRequest(request, action) {
    if (!request || !request.id) return;
    setBusy(true);
    try {
      const envelope = await api.post(
        friendRequestRespondPath(request.id),
        friendRequestResponsePayload(action)
      );
      if (envelope && envelope.ok === true) {
        setNotice(null);
        setRefreshTick(function (tick) {
          return tick + 1;
        });
      } else {
        setNotice(chatNoticeFromEnvelope(envelope));
      }
    } catch (_error) {
      setNotice(chatNoticeFromEnvelope(null));
    } finally {
      setBusy(false);
    }
  }

  async function removeFriend(friend) {
    if (!friend || !friend.id) return;
    setBusy(true);
    try {
      const envelope =
        api && typeof api.del === "function"
          ? await api.del(friendRemovePath(friend.id))
          : await api.post(friendRemovePath(friend.id), {});
      if (envelope && envelope.ok === true) {
        setRoster(function (current) {
          return {
            ...current,
            friends: current.friends.filter(function (item) {
              return item.id !== friend.id;
            }),
          };
        });
        setNotice(null);
      } else {
        setNotice(chatNoticeFromEnvelope(envelope));
      }
    } catch (_error) {
      setNotice(chatNoticeFromEnvelope(null));
    } finally {
      setBusy(false);
    }
  }

  async function challengeFriend(friend) {
    const target = friend && (friend.account_id || friend.id);
    if (!target) return;
    setChallengeBusy(true);
    try {
      const envelope = await api.post(
        CHALLENGES_PATH,
        challengeCreatePayload(target, "casual")
      );
      if (envelope && envelope.ok === true) {
        setNotice(null);
        await loadChallenges();
      } else {
        setNotice(chatNoticeFromEnvelope(envelope));
      }
    } catch (_error) {
      setNotice(chatNoticeFromEnvelope(null));
    } finally {
      setChallengeBusy(false);
    }
  }

  async function respondToChallenge(challenge, action) {
    if (!challenge || !challenge.id) return;
    setChallengeBusy(true);
    try {
      const envelope = await api.post(
        challengeRespondPath(challenge.id),
        challengeResponsePayload(action)
      );
      if (envelope && envelope.ok === true) {
        setNotice(null);
        await loadChallenges();
      } else {
        setNotice(chatNoticeFromEnvelope(envelope));
      }
    } catch (_error) {
      setNotice(chatNoticeFromEnvelope(null));
    } finally {
      setChallengeBusy(false);
    }
  }

  const threads = normalizeThreads(inbox);
  const historyItems = normalizeHistory({
    data: { messages: [...messages, ...inbox.items] },
  });
  const moderationHost = notice
    ? chatModerationHost(notice) || npcHostLine("chat.moderation")
    : null;
  const hubHost = notice ? moderationHost : socialHubHost();

  return jsxs("section", {
    className: "hg-chat hg-social",
    "data-tab": "chat",
    "data-chat-mode": "live",
    children: [
      uiState && uiState !== UI_STATES.READY
        ? jsx(StateNotice, { state: uiState })
        : null,
      jsx(NpcHostBanner, {
        surface: notice ? "chat.moderation" : "chat",
        host: hubHost,
        api: props.api,
        assetBaseUrl: props.assetBaseUrl,
      }),
      notice && (notice.message || notice.hostLine)
        ? jsx("p", {
            className: notice.kind === "moderation" ? "hg-muted" : "hg-error",
            "data-chat-notice": notice.code,
            role: "status",
            children: notice.message || notice.hostLine,
          })
        : null,
      jsxs("div", {
        className: "hg-social__sections",
        "data-social-sections": SOCIAL_HUB_SECTIONS.map(function (section) {
          return section.id;
        }).join(" "),
        children: [
          jsx(DmSection, {
            inbox,
            threads,
            activeThread,
            conversation,
            draft,
            dmTarget,
            composerError,
            busy: busy || inboxBusy,
            inboxOpen,
            onRefresh: refreshInbox,
            onOpenInbox: openInbox,
            onSelectThread: selectThread,
            onDraft: setDraft,
            onTarget: setDmTarget,
            onSubmit: submitMessage,
            onReport: reportMessage,
            onBlock: blockMessage,
          }),
          jsx(FriendsSection, {
            roster,
            query: friendQuery,
            statusFilter: friendStatus,
            friendTarget,
            busy,
            onFriendTarget: setFriendTarget,
            onAdd: addFriend,
            onQuery: setFriendQuery,
            onStatus: setFriendStatus,
            onRespondRequest: respondToRequest,
            onChallenge: challengeFriend,
            onRemove: removeFriend,
          }),
          jsx(ChallengesSection, {
            challengeInbox,
            busy: challengeBusy,
            onRespond: respondToChallenge,
          }),
          jsx(HistorySection, {
            history: historyItems,
            filter: historyFilter,
            query: historyQuery,
            onFilter: setHistoryFilter,
            onQuery: setHistoryQuery,
          }),
        ],
      }),
      loading && messages.length === 0
        ? jsx("p", { className: "hg-muted", children: "Loading social hub..." })
        : null,
    ],
  });
}

export function ChatTab(props = {}) {
  const baseState = props.uiState || props.state;

  if (props.api && isChatEnabled(props)) {
    return jsx(ChatLive, {
      ...props,
      api: props.api,
      uiState: baseState || UI_STATES.READY,
    });
  }
  return jsx(ChatOffStub, {
    ...props,
    uiState: baseState || UI_STATES.NETWORK_OFF,
  });
}
