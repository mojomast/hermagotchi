"""Moderated social primitives: chat, DMs, taunts, blocks and abuse reports.

Everything in this package stores player-authored text as untrusted display
data. Text is length-bounded, control characters are removed, and no value is
ever interpreted as markup, code or an instruction to an agent.
"""

from __future__ import annotations

from .blocks import (
    block_account,
    blocked_account_ids,
    is_blocked,
    is_blocked_either_way,
    list_blocks,
    unblock_account,
)
from .chat import (
    AGENT_DM_DAILY_CAP,
    AGENT_LOBBY_COOLDOWN_S,
    AGENT_LOBBY_DAILY_CAP,
    AGENT_RECIPIENT_COOLDOWN_S,
    AGENT_UNANSWERED_DM_CAP,
    INBOX_CURSOR_CHANNEL,
    MAX_CHANNEL_CHARS,
    MAX_MESSAGE_CHARS,
    MAX_TAUNT_CHARS,
    dm_channel_for,
    get_chat_settings,
    inbox,
    list_messages,
    mark_inbox_read,
    message_payload,
    resolve_dm_channel,
    resolve_target_account,
    send_message,
    send_taunt,
    set_agent_chat_enabled,
)
from .errors import (
    AgentChatDisabled,
    BlockedInteraction,
    ChatCooldown,
    ChatDailyCap,
    DMBlocked,
    DMCooldown,
    DMUnansweredCap,
    EmptyMessage,
    InvalidChannel,
    InvalidTarget,
    MessageTooLong,
    RateLimited,
    SocialError,
    TauntInvalidMatch,
)
from .moderation import create_report, report_payload
from .sanitize import MAX_REASON_CHARS, sanitize_display_text

__all__ = [
    "AGENT_DM_DAILY_CAP",
    "AGENT_LOBBY_COOLDOWN_S",
    "AGENT_LOBBY_DAILY_CAP",
    "AGENT_RECIPIENT_COOLDOWN_S",
    "AGENT_UNANSWERED_DM_CAP",
    "AgentChatDisabled",
    "BlockedInteraction",
    "ChatCooldown",
    "ChatDailyCap",
    "DMBlocked",
    "DMCooldown",
    "DMUnansweredCap",
    "EmptyMessage",
    "INBOX_CURSOR_CHANNEL",
    "InvalidChannel",
    "InvalidTarget",
    "MAX_CHANNEL_CHARS",
    "MAX_MESSAGE_CHARS",
    "MAX_REASON_CHARS",
    "MAX_TAUNT_CHARS",
    "MessageTooLong",
    "RateLimited",
    "SocialError",
    "TauntInvalidMatch",
    "block_account",
    "blocked_account_ids",
    "create_report",
    "dm_channel_for",
    "get_chat_settings",
    "inbox",
    "is_blocked",
    "is_blocked_either_way",
    "list_blocks",
    "list_messages",
    "mark_inbox_read",
    "message_payload",
    "report_payload",
    "resolve_dm_channel",
    "resolve_target_account",
    "sanitize_display_text",
    "send_message",
    "send_taunt",
    "set_agent_chat_enabled",
    "unblock_account",
]
