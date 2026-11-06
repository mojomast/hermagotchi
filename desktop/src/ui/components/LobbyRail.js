import { useEffect, useRef, useState } from "react";
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
  LOBBY_RAIL_HOST_DISMISSED_KEY,
  chatActionNotice,
  chatMessagePayload,
  chatModerationHost,
  chatNoticeFromEnvelope,
  displayActorLabel,
  formatRelativeTime,
  groupLobbyMessages,
  isTauntMessage,
  isUpsetMessage,
  lobbyAuthorHue,
  lobbyUnreadCount,
  lobbyUnreadLabel,
  mergeMessages,
  messageFromEnvelope,
  normalizeInbox,
  normalizeMessages,
  shouldShowChatStub,
  shouldStickLobbyScroll,
  tauntSummary,
  validateChatDraft,
  validateDmTarget,
} from "../logic/chat.js";
import { NpcHostBanner } from "./NpcHostBanner.js";

function emptyInbox() {
  return { items: [], unreadCount: 0, total: 0, dms: [], mentions: [] };
}

function actorLabel(message) {
  return displayActorLabel(message);
}

function authorKey(message) {
  if (message && message.account_id) return String(message.account_id);
  return actorLabel(message);
}

function TimeLabel(props) {
  const iso = props.iso || "";
  const relative = formatRelativeTime(iso);
  return jsx("time", {
    className: "hg-lobby-rail__time hg-muted",
    dateTime: iso || undefined,
    title: iso || undefined,
    children: relative || iso || "",
  });
}

function MessageMenu(props) {
  const message = props.message;
  const open = props.open === true;
  return jsxs("div", {
    className: "hg-lobby-rail__menu",
    children: [
      jsx("button", {
        type: "button",
        className: "hg-lobby-rail__menu-toggle",
        "aria-haspopup": "menu",
        "aria-expanded": open ? "true" : "false",
        "aria-label": "Message actions",
        title: "Message actions",
        "data-lobby-menu-toggle": message.id,
        disabled: props.busy,
        onClick: function (event) {
          event.stopPropagation();
          props.onToggle(message.id);
        },
        children: "⋯",
      }),
      open
        ? jsxs("div", {
            className: "hg-lobby-rail__menu-panel",
            role: "menu",
            children: [
              jsx("button", {
                type: "button",
                role: "menuitem",
                className: "hg-lobby-rail__menu-item",
                disabled: props.busy,
                onClick: function () {
                  props.onReport(message);
                  props.onClose();
                },
                children: "Report",
              }),
              jsx("button", {
                type: "button",
                role: "menuitem",
                className: "hg-lobby-rail__menu-item",
                disabled: props.busy || !message.account_id,
                onClick: function () {
                  props.onBlock(message);
                  props.onClose();
                },
                children: "Block",
              }),
            ],
          })
        : null,
    ],
  });
}

function LobbyMessageRow(props) {
  const message = props.message;
  const showHeader = props.showHeader !== false;
  const grouped = props.grouped === true;
  const taunt = isTauntMessage(message);
  const upset = isUpsetMessage(message);
  const summary = taunt || upset ? tauntSummary(message.match_context) : "";
  const label = actorLabel(message);
  const hue = lobbyAuthorHue(authorKey(message));
  const kind = taunt ? "taunt" : upset ? "upset" : "chat";
  const className =
    "hg-lobby-rail__message" +
    (grouped ? " hg-lobby-rail__message--grouped" : "") +
    (taunt ? " hg-lobby-rail__taunt" : "") +
    (upset ? " hg-lobby-rail__upset" : "");

  return jsxs("li", {
    className: className,
    "data-message-id": message.id,
    "data-actor-mode": message.actor_mode,
    "data-message-kind": kind,
    "data-grouped": grouped ? "true" : "false",
    children: [
      showHeader
        ? jsxs("div", {
            className: "hg-lobby-rail__meta",
            children: [
              jsx("strong", {
                className: "hg-lobby-rail__author",
                style: { color: "hsl(" + hue + " 70% 68%)" },
                children: label,
              }),
              taunt
                ? jsx("span", {
                    className: "hg-lobby-rail__kind",
                    children: "taunt",
                  })
                : null,
              upset
                ? jsx("span", {
                    className: "hg-lobby-rail__kind hg-lobby-rail__kind--upset",
                    children: "upset",
                  })
                : null,
              summary
                ? jsx("span", {
                    className: "hg-lobby-rail__match",
                    "data-taunt-match": "true",
                    title: summary,
                    children: summary,
                  })
                : null,
              jsx(TimeLabel, { iso: message.created_at }),
              jsx(MessageMenu, {
                message,
                busy: props.busy,
                open: props.menuOpen,
                onToggle: props.onMenuToggle,
                onClose: props.onMenuClose,
                onReport: props.onReport,
                onBlock: props.onBlock,
              }),
            ],
          })
        : jsxs("div", {
            className: "hg-lobby-rail__meta hg-lobby-rail__meta--grouped",
            children: [
              jsx(TimeLabel, { iso: message.created_at }),
              jsx(MessageMenu, {
                message,
                busy: props.busy,
                open: props.menuOpen,
                onToggle: props.onMenuToggle,
                onClose: props.onMenuClose,
                onReport: props.onReport,
                onBlock: props.onBlock,
              }),
            ],
          }),
      jsx("p", {
        className: "hg-lobby-rail__text",
        children: message.body,
      }),
    ],
  });
}

function HostStrip(props) {
  if (props.dismissed) return null;
  const host = props.host;
  if (!host || !host.line) return null;
  return jsxs("div", {
    className: "hg-lobby-rail__host",
    "data-npc-id": host.id,
    children: [
      jsx("strong", { className: "hg-lobby-rail__host-name", children: host.name }),
      jsx("span", { className: "hg-lobby-rail__host-line", children: host.line }),
      jsx("button", {
        type: "button",
        className: "hg-lobby-rail__host-dismiss",
        "aria-label": "Dismiss host tip",
        title: "Dismiss",
        onClick: props.onDismiss,
        children: "×",
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
      jsx(NpcHostBanner, {
        surface: "chat",
        size: "compact",
        api: props.api,
        assetBaseUrl: props.assetBaseUrl,
      }),
      jsx("p", {
        className: "hg-lobby-rail__stub-title",
        children: "Chat is off by default",
      }),
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
            rows: "2",
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

function readHostDismissed() {
  if (typeof window === "undefined" || !window.localStorage) return false;
  try {
    return window.localStorage.getItem(LOBBY_RAIL_HOST_DISMISSED_KEY) === "1";
  } catch (_err) {
    return false;
  }
}

function persistHostDismissed(value) {
  if (typeof window === "undefined" || !window.localStorage) return;
  try {
    window.localStorage.setItem(LOBBY_RAIL_HOST_DISMISSED_KEY, value ? "1" : "0");
  } catch (_err) {
    /* ignore */
  }
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
  const [dmOpen, setDmOpen] = useState(false);
  const [composerError, setComposerError] = useState("");
  const [notice, setNotice] = useState(null);
  const [busy, setBusy] = useState(false);
  const [refreshTick, setRefreshTick] = useState(0);
  const [inbox, setInbox] = useState(emptyInbox);
  const [menuId, setMenuId] = useState(null);
  const [hostDismissed, setHostDismissed] = useState(readHostDismissed);
  const [stickToBottom, setStickToBottom] = useState(true);
  const [pendingNew, setPendingNew] = useState(false);
  const listRef = useRef(null);
  const prevCountRef = useRef(0);

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

  useEffect(
    function autoScroll() {
      const el = listRef.current;
      if (!el) return;
      const grew = messages.length > prevCountRef.current;
      prevCountRef.current = messages.length;
      if (!grew) return;
      if (stickToBottom) {
        el.scrollTop = el.scrollHeight;
        setPendingNew(false);
      } else {
        setPendingNew(true);
      }
    },
    [messages, stickToBottom]
  );

  useEffect(
    function closeMenuOnOutside() {
      if (!menuId) return undefined;
      function onKey(event) {
        if (event.key === "Escape") setMenuId(null);
      }
      function onPointer() {
        setMenuId(null);
      }
      window.addEventListener("keydown", onKey);
      window.addEventListener("pointerdown", onPointer);
      return function () {
        window.removeEventListener("keydown", onKey);
        window.removeEventListener("pointerdown", onPointer);
      };
    },
    [menuId]
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

  function onListScroll() {
    const el = listRef.current;
    const stuck = shouldStickLobbyScroll(el);
    setStickToBottom(stuck);
    if (stuck) setPendingNew(false);
  }

  function jumpToLatest() {
    const el = listRef.current;
    if (el) el.scrollTop = el.scrollHeight;
    setStickToBottom(true);
    setPendingNew(false);
  }

  function dismissHost() {
    setHostDismissed(true);
    persistHostDismissed(true);
  }

  function startResize(event) {
    if (typeof props.onWidthChange !== "function") return;
    event.preventDefault();
    const startX = event.clientX;
    const startWidth =
      typeof props.width === "number" ? props.width : LOBBY_DEFAULT_WIDTH();
    function onMove(moveEvent) {
      const delta = startX - moveEvent.clientX;
      props.onWidthChange(startWidth + delta);
    }
    function onUp() {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
    }
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
  }

  function LOBBY_DEFAULT_WIDTH() {
    return 320;
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
    const checkedTarget = validateDmTarget(dmOpen ? dmTarget : "");
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
        setStickToBottom(true);
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
  const host = notice ? moderationHost : npcHostLine("chat");
  const grouped = groupLobbyMessages(messages);

  const rows = grouped.map(function (entry) {
    return jsx(
      LobbyMessageRow,
      {
        message: entry.message,
        showHeader: entry.showHeader,
        grouped: entry.grouped,
        busy,
        menuOpen: menuId === entry.message.id,
        onMenuToggle: function (id) {
          setMenuId(function (current) {
            return current === id ? null : id;
          });
        },
        onMenuClose: function () {
          setMenuId(null);
        },
        onReport: reportMessage,
        onBlock: blockMessage,
      },
      entry.message.id
    );
  });

  const emptyState =
    enabled && !loading && messages.length === 0
      ? jsx("li", {
          className: "hg-muted hg-lobby-rail__empty",
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

  const resizeHandle =
    collapsed || typeof props.onWidthChange !== "function"
      ? null
      : jsx("div", {
          className: "hg-lobby-rail__resize",
          role: "separator",
          "aria-orientation": "vertical",
          "aria-label": "Resize lobby chat",
          "data-lobby-resize": "true",
          onPointerDown: startResize,
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
            jsx(HostStrip, {
              host,
              dismissed: hostDismissed && !notice,
              onDismiss: dismissHost,
            }),
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
            jsxs("div", {
              className: "hg-lobby-rail__scroller",
              children: [
                jsx("ol", {
                  className: "hg-lobby-rail__messages",
                  "aria-live": "polite",
                  ref: function (node) {
                    listRef.current = node;
                  },
                  onScroll: onListScroll,
                  children: [emptyState, ...rows],
                }),
                pendingNew
                  ? jsx("button", {
                      type: "button",
                      className: "hg-lobby-rail__new",
                      onClick: jumpToLatest,
                      children: "New messages ↓",
                    })
                  : null,
              ],
            }),
            jsxs("form", {
              className: "hg-lobby-rail__compose",
              onSubmit: submitMessage,
              children: [
                jsxs("div", {
                  className: "hg-lobby-rail__compose-row",
                  children: [
                    jsx("textarea", {
                      className: "hg-input hg-lobby-rail__draft",
                      rows: "1",
                      maxLength: String(CHAT_MESSAGE_MAX_CHARS),
                      value: draft,
                      disabled: busy,
                      placeholder: "Message lobby…",
                      "aria-label": "Lobby message",
                      onChange: function (event) {
                        setDraft(event.target.value);
                        const el = event.target;
                        el.style.height = "auto";
                        const next = Math.min(el.scrollHeight, 66);
                        el.style.height = next + "px";
                      },
                      onKeyDown: function (event) {
                        if (event.key === "Enter" && !event.shiftKey) {
                          event.preventDefault();
                          submitMessage(event);
                        }
                      },
                    }),
                    jsx("button", {
                      type: "button",
                      className: dmOpen
                        ? "hg-btn hg-lobby-rail__dm-toggle hg-lobby-rail__dm-toggle--on"
                        : "hg-btn hg-lobby-rail__dm-toggle",
                      "aria-pressed": dmOpen ? "true" : "false",
                      "aria-label": "Toggle direct message target",
                      title: "Direct message",
                      disabled: busy,
                      onClick: function () {
                        setDmOpen(function (open) {
                          return !open;
                        });
                      },
                      children: "@",
                    }),
                    jsx("button", {
                      type: "submit",
                      className: "hg-btn hg-btn--primary",
                      disabled: busy,
                      children: busy ? "…" : "Send",
                    }),
                  ],
                }),
                dmOpen
                  ? jsx("input", {
                      className: "hg-input hg-lobby-rail__dm-input",
                      type: "text",
                      maxLength: String(CHAT_DM_TARGET_MAX_CHARS),
                      value: dmTarget,
                      disabled: busy,
                      placeholder: "DM to player or pet",
                      "data-chat-dm-target": "true",
                      "aria-label": "Direct message target",
                      onChange: function (event) {
                        setDmTarget(event.target.value);
                      },
                    })
                  : null,
                composerError
                  ? jsx("p", {
                      className: "hg-error",
                      role: "alert",
                      children: composerError,
                    })
                  : null,
              ],
            }),
          ],
        })
      : jsx(LobbyStub, {
          uiState,
          api: props.api,
          assetBaseUrl: props.assetBaseUrl,
        });

  return jsxs("aside", {
    className: collapsed
      ? "hg-lobby-rail hg-lobby-rail--collapsed"
      : "hg-lobby-rail",
    "data-rail": "lobby",
    "data-collapsed": collapsed ? "true" : "false",
    "aria-label": "Lobby",
    children: [resizeHandle, header, body],
  });
}
