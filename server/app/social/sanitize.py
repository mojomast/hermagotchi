"""Text bounds for player-authored content.

The output is always plain text. It is never escaped for a markup language at
storage time (clients must render it as text); instead this layer removes
control/bidi characters, normalizes newlines and enforces a hard length cap.
"""

from __future__ import annotations

import unicodedata

MAX_MESSAGE_CHARS = 400
MAX_REASON_CHARS = 500

# Hidden directional overrides can be used to visually spoof message text.
_BIDI_CONTROLS = frozenset(
    "\u061c\u200e\u200f\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069"
)


def sanitize_display_text(value: object, *, max_chars: int) -> str:
    """Return bounded plain text or raise ``ValueError``.

    ``ValueError`` carries a short machine-readable reason (``empty`` or
    ``too_long``); routes translate it into the contracts-v1 error envelope.
    """

    if not isinstance(value, str):
        raise ValueError("not_text")

    text = unicodedata.normalize("NFC", value)
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    kept: list[str] = []
    for char in text:
        if char in {"\n", "\t"}:
            kept.append(char)
            continue
        code = ord(char)
        if code < 0x20 or code == 0x7F or char in _BIDI_CONTROLS:
            continue
        kept.append(char)

    cleaned = "".join(kept).strip()
    if not cleaned:
        raise ValueError("empty")
    if len(cleaned) > max_chars:
        raise ValueError("too_long")
    return cleaned
