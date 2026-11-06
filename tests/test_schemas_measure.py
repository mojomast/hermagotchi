"""Token-budget measurements for the eight Hermagotchi tool schemas."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

pytest = __import__("pytest")
pytest.importorskip("tiktoken")

ROOT = Path(__file__).resolve().parents[1]
EVALS = ROOT / "evals"

EXPECTED_TOOLS = {
    "hermagotchi_status",
    "hermagotchi_pet",
    "hermagotchi_goals",
    "hermagotchi_challenge",
    "hermagotchi_battle",
    "hermagotchi_shop",
    "hermagotchi_social",
    "hermagotchi_meta",
}


def test_measure_all_reports_both_encodings_for_eight_schemas() -> None:
    sys.path.insert(0, str(EVALS))
    try:
        import measure_schemas
    finally:
        sys.path.pop(0)

    result = measure_schemas.measure_all()
    assert set(result["tools"]) == EXPECTED_TOOLS
    assert len(result["tools"]) == 8
    assert set(result["totals"]) == {"o200k_base", "cl100k_base"}
    for encoding in ("o200k_base", "cl100k_base"):
        counts = result["per_encoding"][encoding]
        assert set(counts) == EXPECTED_TOOLS
        assert all(isinstance(value, int) and value > 0 for value in counts.values())
        assert result["totals"][encoding] == sum(counts.values())


def test_cli_emits_machine_readable_o200k_report() -> None:
    completed = subprocess.run(
        [sys.executable, str(EVALS / "measure_schemas.py"), "--json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    report = json.loads(completed.stdout)
    assert set(report["per_encoding"]["o200k_base"]) == EXPECTED_TOOLS
    assert report["totals"]["o200k_base"] > 0
    assert report["totals"]["cl100k_base"] > 0
    assert "o200k_base" in completed.stderr or report["encodings"] == [
        "o200k_base",
        "cl100k_base",
    ]
