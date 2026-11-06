"""Hermagotchi Hermes plugin entrypoint.

``register(ctx)`` only declares the skill and the frozen eight composable
tools. Importing this module is side-effect free: it performs no network I/O and
does not require Hermes to be installed.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

try:  # Imported as a package (``hermagotchi``).
    from .schemas import TOOL_NAMES, TOOL_SCHEMAS
    from .tools import HANDLERS
except ImportError:  # Imported directly from the plugin root.
    from schemas import TOOL_NAMES, TOOL_SCHEMAS
    from tools import HANDLERS

PLUGIN_ID = "hermagotchi"
SKILL_PATH = _ROOT / "skills" / "hermagotchi" / "SKILL.md"


def register(ctx: Any) -> str:
    """Register the Hermagotchi skill and its eight tools with Hermes."""

    for name in TOOL_NAMES:
        ctx.register_tool(
            name=name,
            toolset=PLUGIN_ID,
            schema=TOOL_SCHEMAS[name],
            handler=HANDLERS[name],
        )
    ctx.register_skill(name=PLUGIN_ID, path=str(SKILL_PATH))
    return PLUGIN_ID


__all__ = [
    "PLUGIN_ID",
    "SKILL_PATH",
    "TOOL_NAMES",
    "TOOL_SCHEMAS",
    "HANDLERS",
    "register",
]
