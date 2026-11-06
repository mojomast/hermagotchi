"""Demo, handoff and in-repo catalog documentation checks (HGT-W6-O).

These tests are intentionally dependency-light: they use PyYAML when it is
available and otherwise fall back to a tiny parser for the deliberately simple
subset used by ``docs/catalog/hermagotchi.yaml``.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "docs" / "DEMO.md"
HANDOFF = ROOT / "docs" / "HANDOFF.md"
CATALOG = ROOT / "docs" / "catalog" / "hermagotchi.yaml"
README = ROOT / "README.md"
LICENSE = ROOT / "LICENSE"
DEMO_SCRIPT = ROOT / "scripts" / "demo_local.sh"

EXPECTED_TOOLS = [
    "hermagotchi_status",
    "hermagotchi_pet",
    "hermagotchi_goals",
    "hermagotchi_challenge",
    "hermagotchi_battle",
    "hermagotchi_shop",
    "hermagotchi_social",
    "hermagotchi_meta",
]

SHA_RE = re.compile(r"^[0-9a-f]{40}$")
PLACEHOLDER_SHA = "REPLACE_WITH_40_CHAR_SHA"


def _scalar(value: str):
    value = value.strip()
    if value == "[]":
        return []
    if value == "{}":
        return {}
    if value in {"null", "~"}:
        return None
    if value.lower() in {"true", "false"}:
        return value.lower() == "true"
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def _parse_block(tokens: list[tuple[int, str]], index: int, indent: int):
    if tokens[index][1].startswith("- "):
        items: list = []
        while (
            index < len(tokens)
            and tokens[index][0] == indent
            and tokens[index][1].startswith("- ")
        ):
            items.append(_scalar(tokens[index][1][2:]))
            index += 1
        return items, index

    mapping: dict = {}
    while index < len(tokens) and tokens[index][0] == indent:
        content = tokens[index][1]
        if content.startswith("- "):
            break
        key, separator, rest = content.partition(":")
        assert separator, f"not a mapping entry: {content!r}"
        key = key.strip()
        rest = rest.strip()
        index += 1
        if rest:
            mapping[key] = _scalar(rest)
        elif index < len(tokens) and tokens[index][0] > indent:
            child, index = _parse_block(tokens, index, tokens[index][0])
            mapping[key] = child
        else:
            mapping[key] = None
    return mapping, index


def _fallback_yaml(text: str):
    tokens: list[tuple[int, str]] = []
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        tokens.append((len(raw) - len(raw.lstrip(" ")), raw.strip()))
    if not tokens:
        return {}
    parsed, index = _parse_block(tokens, 0, tokens[0][0])
    assert index == len(tokens), "unparsed trailing YAML tokens"
    return parsed


def _load_yaml(path: Path):
    text = path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore[import-not-found]
    except ImportError:
        return _fallback_yaml(text)
    loaded = yaml.safe_load(text)
    assert isinstance(loaded, dict)
    return loaded


def _plugin_version() -> str:
    text = (ROOT / "plugin.yaml").read_text(encoding="utf-8")
    match = re.search(r"^version:\s*(\S+)\s*$", text, re.MULTILINE)
    assert match, "plugin.yaml is missing a version"
    return match.group(1).strip("'\"")


def test_demo_handoff_and_catalog_files_exist() -> None:
    assert DEMO.is_file(), "docs/DEMO.md is missing"
    assert HANDOFF.is_file(), "docs/HANDOFF.md is missing"
    assert CATALOG.is_file(), "docs/catalog/hermagotchi.yaml is missing"
    assert LICENSE.is_file(), "LICENSE is missing"
    assert DEMO_SCRIPT.is_file(), "scripts/demo_local.sh is missing"


def test_catalog_yaml_parses_and_mirrors_plugin_manifest() -> None:
    catalog = _load_yaml(CATALOG)

    assert catalog["name"] == "hermagotchi"
    assert catalog["repo"] == "https://github.com/mojomast/hermagotchi"

    sha = str(catalog["sha"])
    assert SHA_RE.match(sha) or sha == PLACEHOLDER_SHA, (
        "catalog sha must be a full 40-character hex SHA or the explicit "
        "REPLACE_WITH_40_CHAR_SHA placeholder"
    )

    assert catalog["maintainer"] == "mojomast"
    assert catalog["tier"] == "community"
    assert catalog["category"] in {"games", "tools"}
    assert catalog["version"] == _plugin_version()
    assert catalog["requires_hermes"]

    capabilities = catalog["capabilities"]
    assert capabilities["provides_tools"] == EXPECTED_TOOLS
    assert len(capabilities["provides_tools"]) == 8
    assert capabilities["hooks"] == []
    assert capabilities["middleware"] == []
    assert catalog["requires_env"] == []


def test_catalog_has_no_secret_material() -> None:
    text = CATALOG.read_text(encoding="utf-8").lower()
    for forbidden in ("api_key", "token:", "secret:", "password"):
        assert forbidden not in text


def test_demo_is_honest_about_current_status() -> None:
    text = DEMO.read_text(encoding="utf-8")
    lowered = text.lower()

    for required in ("placeholder", "partial", "practice", "ranked", "open"):
        assert required in lowered, f"DEMO.md must mention {required!r}"
    assert "not deployed" in lowered
    assert "never" in lowered and "fake" in lowered
    assert "90" in lowered

    # The storyboard must explicitly separate practice from ranked/PvP claims.
    assert "practice" in lowered and ("pvp" in lowered or "player-versus-player" in lowered)


def test_handoff_has_tip_sha_commands_gaps_and_manual_checklist() -> None:
    text = HANDOFF.read_text(encoding="utf-8")
    lowered = text.lower()

    assert "tip sha" in lowered
    assert "git rev-parse head" in lowered
    assert "hermes plugins doctor" in lowered
    assert "hermes plugins validate" in lowered
    assert "submission checklist" in lowered
    assert "manual" in lowered
    assert "catalog pr" in lowered and "not opened" in lowered
    assert "hosted" in lowered and "open" in lowered


def test_demo_script_is_local_only_and_documents_healthz_and_adopt() -> None:
    text = DEMO_SCRIPT.read_text(encoding="utf-8")

    assert "requirements-dev.txt" in text
    assert "uvicorn" in text
    assert "127.0.0.1" in text
    assert "healthz" in text
    assert "/v1/pets" in text
    assert "X-Account-Id" in text

    # Never expose a public bind or point at a hosted deployment.
    assert "0.0.0.0" not in text
    assert "::" not in text
    assert "--host 127.0.0.1" in text
    assert not re.search(r"curl\s+https?://(?!127\.0\.0\.1|localhost)", text)


def test_readme_discloses_network_off_and_hosted_target() -> None:
    text = README.read_text(encoding="utf-8")
    lowered = text.lower()

    assert re.search(
        r"network[^\n]*(default[^\n]*off|off[^\n]*default)", lowered
    ), "README must state that network is off by default"
    assert "hosted target chosen" in lowered
    assert "api.hermagotchi.rizz.click" in lowered
    assert "retention" in lowered
    assert "data deletion" in lowered
    assert "permissions" in lowered
    assert "limitations" in lowered

    for link in ("docs/demo.md", "docs/handoff.md", "docs/contracts.md", "security.md"):
        assert link in lowered, f"README must link to {link}"

    assert "pip install -r requirements-dev.txt" in lowered
    assert "hermes plugins doctor" in lowered
    assert "hermes plugins validate" in lowered


def test_license_is_mit() -> None:
    text = LICENSE.read_text(encoding="utf-8")
    assert "MIT License" in text
    assert "Permission is hereby granted" in text
    assert "WITHOUT WARRANTY" in text


def test_files_contain_no_private_paths() -> None:
    forbidden_fragments = (
        "/" + "home/",
        "/" + "workspace/",
        "C:" + "\\Users\\",
    )
    for path in (DEMO, HANDOFF, CATALOG, README, DEMO_SCRIPT, LICENSE):
        text = path.read_text(encoding="utf-8")
        for fragment in forbidden_fragments:
            assert fragment not in text, f"{path.name} leaks a private path"
