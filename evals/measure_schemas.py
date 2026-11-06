#!/usr/bin/env python3
"""Report tiktoken token counts for the eight Hermagotchi tool schemas.

Usage:
    python3 evals/measure_schemas.py          # human-readable table
    python3 evals/measure_schemas.py --json   # machine-readable report
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from schemas import TOOL_NAMES, TOOL_SCHEMAS  # noqa: E402

ENCODINGS = ("o200k_base", "cl100k_base")


def _canonical(schema: dict) -> str:
    return json.dumps(schema, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def measure_all() -> dict:
    """Return per-tool and total token counts for both encodings."""

    try:
        import tiktoken
    except ImportError as exc:  # pragma: no cover - environment setup guard
        raise SystemExit(
            "tiktoken is required: python3 -m pip install --user tiktoken"
        ) from exc

    encoders = {name: tiktoken.get_encoding(name) for name in ENCODINGS}
    per_encoding: dict[str, dict[str, int]] = {name: {} for name in ENCODINGS}
    tools: dict[str, dict[str, int]] = {}

    for tool in TOOL_NAMES:
        text = _canonical(TOOL_SCHEMAS[tool])
        row: dict[str, int] = {"chars": len(text)}
        for encoding_name, encoder in encoders.items():
            count = len(encoder.encode(text))
            row[encoding_name] = count
            per_encoding[encoding_name][tool] = count
        tools[tool] = row

    totals = {
        encoding_name: sum(per_encoding[encoding_name].values())
        for encoding_name in ENCODINGS
    }
    return {
        "encodings": list(ENCODINGS),
        "contracts": "contracts-v1",
        "tool_count": len(TOOL_NAMES),
        "per_encoding": per_encoding,
        "tools": tools,
        "totals": totals,
    }


def _print_table(report: dict) -> None:
    print(f"contracts={report['contracts']} tools={report['tool_count']}")
    print(f"{'o200k_base':>11} {'cl100k_base':>12} {'chars':>8}  tool")
    for tool in TOOL_NAMES:
        row = report["tools"][tool]
        print(
            f"{row['o200k_base']:>11} {row['cl100k_base']:>12} "
            f"{row['chars']:>8}  {tool}"
        )
    print(
        f"{report['totals']['o200k_base']:>11} "
        f"{report['totals']['cl100k_base']:>12} {'':>8}  TOTAL"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit a JSON report")
    args = parser.parse_args(argv)

    report = measure_all()
    if args.json:
        print(json.dumps(report, sort_keys=True))
    else:
        _print_table(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
