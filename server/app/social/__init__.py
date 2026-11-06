"""Moderated social primitives: chat, blocks and abuse reports.

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
    MAX_MESSAGE_CHARS,
    list_messages,
    message_payload,
    send_message,
)
from .errors import (
    BlockedInteraction,
    InvalidChannel,
    InvalidTarget,
    RateLimited,
    SocialError,
)
from .moderation import create_report, report_payload
from .sanitize import MAX_REASON_CHARS, sanitize_display_text

__all__ = [
    "BlockedInteraction",
    "InvalidChannel",
    "InvalidTarget",
    "MAX_MESSAGE_CHARS",
    "MAX_REASON_CHARS",
    "RateLimited",
    "SocialError",
    "block_account",
    "blocked_account_ids",
    "create_report",
    "is_blocked",
    "is_blocked_either_way",
    "list_blocks",
    "list_messages",
    "message_payload",
    "report_payload",
    "sanitize_display_text",
    "send_message",
    "unblock_account",
]
