import { useEffect, useState } from "react";
import { jsx, jsxs } from "react/jsx-runtime";
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
  isTauntMessage,
  lobbyUnreadCount,
  lobbyUnreadLabel,
  mergeMessages,
  messageFromEnvelope,
  normalizeInbox,
  normalizeMessages,
  shouldShowChatStub,
  tauntSummary,
  validateChatDraft,
  validateDmTarget,
  displayActorLabel,
  formatRelativeTime,
} from "../logic/chat.js";
import { NpcHostBanner } from "./NpcHostBanner.js";

function emptyInbox() {
  return { items: [], unreadCount: 0, total: 0, dms: [], mentions: [] };
}

function actorLabel(message) {
  return displayActorLabel(message);
}

function TimeLabel(props) {
  const iso = props.iso || "";
  const relative = formatRelativeTime(iso);
  return jsx("time", {
    className: "hg-muted hg-time",
    dateTime: iso || undefined,
    title: iso || undefined,
    children: relative || iso || "Unknown time",
  });
}

function LobbyActions(props) {
  const message = props.message;
  return jsxs("div", {
    className: "hg-actions hg-actions--tight",
    children: [
      jsx("button", {
        type: "button",
        className: "hg-btn",
        disabled: props.busy,
        onClick: function () {
          props.onReport(message);
        },
        children: "Report",
      }),
      jsx("button", {
        type: "button",
        className: "hg-btn",
        disabled: props.busy || !message.account_id,
        onClick: function () {
          props.onBlock(message);
        },
        children: "Block",
      }),
    ],
  });
}

function LobbyMessageRow(props) {
  const message = props.message;

  if (isTauntMessage(message)) {
    const summary = tauntSummary(message.match_context);
    return jsxs("li", {
      className: "hg-lobby-rail__message hg-lobby-rail__taunt",
      "data-message-id": message.id,
      "data-actor-mode": message.actor_mode,
      "data-message-kind": "taunt",
      children: [
        jsxs("div", {
          className: "hg-lobby-rail__bubble",
          children: [
            jsxs("div", {
              className: "hg-row hg-row--between",
              children: [
                jsx("strong", { children: actorLabel(message) + " taunt" }),
                jsx(TimeLabel, { iso: message.created_at }),
              ],
            }),
            jsx("p", {
              className: "hg-lobby-rail__text",
              children: message.body,
            }),
            summary
              ? jsx("p", {
                  className: "hg-lobby-rail__match",
                  "data-taunt-match": "true",
                  children: summary,
                })
              : null,
            jsx(LobbyActions, {
              message,
              busy: props.busy,
              onReport: props.onReport,
              onBlock: props.onBlock,
            }),
          ],
        }),
      ],
    });
  }

  return jsxs("li", {
    className: "hg-lobby-rail__message",
    "data-message-id": message.id,
    "data-actor-mode": message.actor_mode,
    children: [
      jsxs("div", {
        className: "hg-row hg-row--between",
        children: [
          jsx("strong", { children: actorLabel(message) }),
          jsx(TimeLabel, { iso: message.created_at }),
        ],
      }),
      jsx("p", {
        className: "hg-lobby-rail__text",
        children: message.body,
      }),
      jsx(LobbyActions, {
        message,
        busy: props.busy,
        onReport: props.onReport,
        onBlock: props.onBlock,
      }),
    ],
  });
}

function LobbyStub(props) {
  const uiState = props.uiState || UI_STATES.NETWORK_OFF;
  return jsxs("div", {
    className: "hg-lobby-rail__stub",
    "data-chat-mode": "stub",
    children: [
      uiState && uiState !== UI_STATES.READY
        ? jsx(StateNotice, { state: uiState })
        : null,
      jsx(NpcHostBanner, { surface: "chat" }),
      jsx("p", { className: "hg-lobby-rail__stub-title", children: "Chat is off by default" }),
      jsx("p", {
        className: "hg-muted",
        children:
          "The lobby stays unavailable until the owner enables chat and this device is paired.",
      }),
      jsx("label", {
        className: "hg-field",
        children: [
          jsx("span", { children: "Message" }),
          jsx("textarea", {
            rows: "3",
            disabled: true,
            placeholder: "Chat is disabled in this stub",
          }),
        ],
      }),
      jsx("button", {
        type: "button",
        className: "hg-btn",
        disabled: true,
        children: "Send (disabled)",
      }),
    ],
  });
}

export function LobbyRail(props = {}) {
  const api = props.api;
  const uiState = props.uiState || props.state || UI_STATES.READY;
  const enabled = !shouldShowChatStub(props);
  const collapsedState = useState(false);
  const collapsed =
    props.collapsed === undefined ? collapsedState[0] : props.collapsed === true;
  const setInternalCollapsed = collapsedState[1];

  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [draft, setDraft] = useState("");
  const [dmTarget, setDmTarget] = useState("");
  const [composerError, setComposerError] = useState("");
  const [notice, setNotice] = useState(null);
  const [busy, setBusy] = useState(false);
  const [refreshTick, setRefreshTick] = useState(0);
  const [inbox, setInbox] = useState(emptyInbox);

  useEffect(
    function loadMessages() {
      if (!enabled || !api || typeof api.get !== "function") {
        setMessages([]);
        setLoading(false);
        return undefined;
      }
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
    [api, enabled, refreshTick]
  );

  useEffect(
    function pollInbox() {
      if (!enabled || !api || typeof api.get !== "function") {
        setInbox(emptyInbox());
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
          /* The rail badge stays quiet; the lobby notice owns errors. */
        }
      }
      load();
      const timer = setInterval(load, 30000);
      return function () {
        cancelled = true;
        clearInterval(timer);
      };
    },
    [api, enabled]
  );

  const unread = lobbyUnreadCount(inbox);

  function toggle() {
    if (typeof props.onToggle === "function") {
      props.onToggle();
      return;
    }
    setInternalCollapsed(function (current) {
      return !current;
    });
  }

  function refresh() {
    setRefreshTick(function (tick) {
      return tick + 1;
    });
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
    const checkedTarget = validateDmTarget(dmTarget);
    if (!checkedTarget.ok) {
      setComposerError(checkedTarget.error);
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
          setMessages(function (current) {
            return mergeMessages(current, [sent]);
          });
        } else {
          refresh();
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
        setMessages(function (current) {
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

  const moderationHost = notice
    ? chatModerationHost(notice) || npcHostLine("chat.moderation")
    : null;
  const unreadLabel = lobbyUnreadLabel(unread);

  const rows = messages.map(function (message) {
    return jsx(
      LobbyMessageRow,
      {
        message,
        busy,
        onReport: reportMessage,
        onBlock: blockMessage,
      },
      message.id
    );
  });

  const emptyState =
    enabled && !loading && messages.length === 0
      ? jsx("li", {
          className: "hg-muted",
          children: "No lobby messages yet. Say hello below.",
        })
      : null;

  const unreadBadge =
    unread > 0
      ? jsx("span", {
          className: "hg-lobby-rail__badge",
          "data-rail-unread": String(unread),
          "aria-label": unread + " unread",
          children: unreadLabel,
        })
      : null;

  const header = jsxs("header", {
    className: "hg-lobby-rail__header",
    children: [
      jsxs("button", {
        type: "button",
        className: collapsed
          ? "hg-lobby-rail__toggle hg-lobby-rail__toggle--collapsed"
          : "hg-lobby-rail__toggle",
        onClick: toggle,
        "aria-expanded": collapsed ? "false" : "true",
        "aria-label": collapsed ? "Expand lobby chat" : "Collapse lobby chat",
        title: collapsed ? "Expand lobby chat" : "Collapse lobby chat",
        "data-lobby-toggle": "true",
        children: [
          jsx("span", {
            className: "hg-lobby-rail__icon",
            "aria-hidden": "true",
            children: collapsed ? "«" : "»",
          }),
          jsx("span", {
            className: "hg-lobby-rail__label",
            children: "LOBBY",
          }),
          unreadBadge,
        ],
      }),
    ],
  });

  const body = collapsed
    ? null
    : enabled
      ? jsxs("div", {
          className: "hg-lobby-rail__body",
          "data-chat-mode": "live",
          children: [
            uiState && uiState !== UI_STATES.READY
              ? jsx(StateNotice, { state: uiState })
              : null,
            notice
              ? jsx(NpcHostBanner, {
                  surface: "chat.moderation",
                  host: moderationHost,
                })
              : jsx(NpcHostBanner, { surface: "chat" }),
            notice && (notice.message || notice.hostLine)
              ? jsx("p", {
                  className:
                    notice.kind === "moderation"
                      ? "hg-lobby-rail__notice hg-muted"
                      : "hg-lobby-rail__notice hg-error",
                  "data-chat-notice": notice.code,
                  role: "status",
                  children: notice.message || notice.hostLine,
                })
              : null,
            jsx("ol", {
              className: "hg-lobby-rail__messages",
              "aria-live": "polite",
              children: [emptyState, ...rows],
            }),
            jsxs("form", {
              className: "hg-lobby-rail__compose",
              onSubmit: submitMessage,
              children: [
                jsxs("label", {
                  className: "hg-field",
                  children: [
                    jsx("span", { children: "Message" }),
                    jsx("textarea", {
                      className: "hg-input",
                      rows: "3",
                      maxLength: String(CHAT_MESSAGE_MAX_CHARS),
                      value: draft,
                      disabled: busy,
                      placeholder: "Write a plain-text lobby message",
                      onChange: function (event) {
                        setDraft(event.target.value);
                      },
                    }),
                  ],
                }),
                jsxs("label", {
                  className: "hg-field hg-chat__dm-target",
                  children: [
                    jsx("span", { children: "Direct message to (optional)" }),
                    jsx("input", {
                      className: "hg-input",
                      type: "text",
                      maxLength: String(CHAT_DM_TARGET_MAX_CHARS),
                      value: dmTarget,
                      disabled: busy,
                      placeholder: "Player or pet name — blank keeps the lobby",
                      "data-chat-dm-target": "true",
                      onChange: function (event) {
                        setDmTarget(event.target.value);
                      },
                    }),
                  ],
                }),
                composerError
                  ? jsx("p", {
                      className: "hg-error",
                      role: "alert",
                      children: composerError,
                    })
                  : null,
                jsxs("div", {
                  className: "hg-actions",
                  children: [
                    jsx("button", {
                      type: "submit",
                      className: "hg-btn hg-btn--primary",
                      disabled: busy,
                      children: busy ? "Working..." : "Send",
                    }),
                    jsx("button", {
                      type: "button",
                      className: "hg-btn",
                      disabled: busy,
                      onClick: refresh,
                      children: "Refresh",
                    }),
                  ],
                }),
              ],
            }),
          ],
        })
      : jsx(LobbyStub, { uiState });

  return jsxs("aside", {
    className: collapsed
      ? "hg-lobby-rail hg-lobby-rail--collapsed"
      : "hg-lobby-rail",
    "data-rail": "lobby",
    "data-collapsed": collapsed ? "true" : "false",
    "aria-label": "Lobby",
    children: [header, body],
  });
}
