import { useEffect, useState } from "react";
import { jsx, jsxs } from "react/jsx-runtime";
import { NpcHostBanner } from "../components/NpcHostBanner.js";
import { npcHostLine } from "../npcLines.js";
import { StateNotice, UI_STATES } from "../states.js";
import {
  CHAT_BLOCKS_PATH,
  CHAT_MESSAGES_PATH,
  CHAT_REPORT_PATH,
  CHAT_REPORT_REASON,
  chatActionNotice,
  chatMessagePayload,
  chatModerationHost,
  chatNoticeFromEnvelope,
  isChatEnabled,
  mergeMessages,
  messageFromEnvelope,
  normalizeMessages,
  validateChatDraft,
} from "../logic/chat.js";

function ChatOffStub(props) {
  const uiState = props.uiState || UI_STATES.NETWORK_OFF;

  return jsxs("section", {
    className: "hg-chat",
    "data-tab": "chat",
    children: [
      jsx(StateNotice, { state: uiState }),
      jsx(NpcHostBanner, { surface: "chat" }),
      jsxs("div", {
        className: "hg-card",
        children: [
          jsx("h3", { children: "Chat is off by default" }),
          jsx("p", {
            className: "hg-muted",
            children:
              "The lobby and challenge threads stay unavailable until the owner enables chat and the device is paired.",
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

function MessageRow(props) {
  const message = props.message;
  const busy = props.busy;
  const actor = message.actor_mode === "agent" ? "Agent" : "Player";

  return jsxs("li", {
    className: "hg-log__item",
    "data-message-id": message.id,
    "data-actor-mode": message.actor_mode,
    children: [
      jsxs("div", {
        className: "hg-row hg-row--between",
        children: [
          jsx("strong", { children: actor }),
          jsx("span", {
            className: "hg-muted",
            children: message.created_at || "Unknown time",
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

function ChatLive(props) {
  const api = props.api;
  const uiState = props.uiState || props.state || UI_STATES.READY;
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [draft, setDraft] = useState("");
  const [composerError, setComposerError] = useState("");
  const [notice, setNotice] = useState(null);
  const [busy, setBusy] = useState(false);
  const [refreshTick, setRefreshTick] = useState(0);

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

  async function submitMessage(event) {
    if (event && typeof event.preventDefault === "function") {
      event.preventDefault();
    }
    const checked = validateChatDraft(draft);
    if (!checked.ok) {
      setComposerError(checked.error);
      return;
    }

    setComposerError("");
    setBusy(true);
    try {
      const envelope = await api.post(
        CHAT_MESSAGES_PATH,
        chatMessagePayload(checked.value)
      );
      if (envelope && envelope.ok === true) {
        const sent = messageFromEnvelope(envelope);
        if (sent) {
          setMessages(function (current) {
            return mergeMessages(current, [sent]);
          });
        } else {
          setRefreshTick(function (tick) {
            return tick + 1;
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

  function refresh() {
    setRefreshTick(function (tick) {
      return tick + 1;
    });
  }

  const moderationHost = notice
    ? chatModerationHost(notice) || npcHostLine("chat.moderation")
    : null;

  const rows = messages.map(function (message) {
    return jsx(
      MessageRow,
      {
        message: message,
        busy: busy,
        onReport: reportMessage,
        onBlock: blockMessage,
      },
      message.id
    );
  });

  const emptyState =
    !loading && messages.length === 0
      ? jsx("li", {
          className: "hg-muted",
          children: "No lobby messages yet. Say hello below.",
        })
      : null;

  return jsxs("section", {
    className: "hg-chat",
    "data-tab": "chat",
    "data-chat-mode": "live",
    children: [
      jsx(StateNotice, { state: uiState }),
      notice
        ? jsx(NpcHostBanner, {
            surface: "chat.moderation",
            host: moderationHost,
          })
        : jsx(NpcHostBanner, { surface: "chat" }),
      notice && notice.message
        ? jsx("p", {
            className: notice.kind === "moderation" ? "hg-muted" : "hg-error",
            "data-chat-notice": notice.code,
            children: notice.message,
          })
        : null,
      jsxs("div", {
        className: "hg-card",
        children: [
          jsxs("header", {
            className: "hg-card__header",
            children: [
              jsx("h3", { children: "Lobby" }),
              jsx("span", {
                className: "hg-badge",
                children: loading ? "Refreshing" : "Live",
              }),
            ],
          }),
          jsx("p", {
            className: "hg-muted",
            children:
              "Lobby messages are untrusted display text. They are shown exactly as plain text and never executed.",
          }),
          loading && messages.length === 0
            ? jsx("p", { className: "hg-muted", children: "Loading lobby messages..." })
            : null,
          jsx("ol", {
            className: "hg-log",
            "aria-live": "polite",
            children: [emptyState, ...rows],
          }),
          jsxs("form", {
            className: "hg-chat__compose",
            onSubmit: submitMessage,
            children: [
              jsxs("label", {
                className: "hg-field",
                children: [
                  jsx("span", { children: "Message" }),
                  jsx("textarea", {
                    className: "hg-input",
                    rows: "3",
                    maxLength: String(400),
                    value: draft,
                    disabled: busy,
                    placeholder: "Write a plain-text lobby message",
                    onChange: function (event) {
                      setDraft(event.target.value);
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
      }),
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
