"""Contract tests for the Hermagotchi Hermes plugin scaffold (HGT-W1-C)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

EXPECTED_OPS = {
    "hermagotchi_status": ["me", "pet", "wallet", "goal", "inbox", "health", "pair"],
    "hermagotchi_pet": ["adopt", "rename", "set_mode", "care"],
    "hermagotchi_goals": ["list", "set", "clear"],
    "hermagotchi_challenge": [
        "list_opponents",
        "invite",
        "respond",
        "submit_tactics",
    ],
    "hermagotchi_battle": ["practice", "get", "replay", "claim"],
    "hermagotchi_shop": ["catalog", "inventory", "buy", "equip"],
    "hermagotchi_social": ["read", "send", "block", "report", "inbox", "taunt"],
    "hermagotchi_meta": ["leaderboard", "bounties", "claim_bounty"],
}


def _yaml_list(text: str, key: str) -> list[str]:
    """Read a simple top-level block list from the plugin manifest.

    The repo intentionally has no PyYAML dependency, so the manifest stays in a
    deliberately simple subset that this helper can read.
    """

    lines = text.splitlines()
    try:
        start = next(i for i, line in enumerate(lines) if line.strip() == f"{key}:")
    except StopIteration as exc:  # pragma: no cover - clearer assertion below
        raise AssertionError(f"missing {key}: block in plugin.yaml") from exc
    values: list[str] = []
    for line in lines[start + 1 :]:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if not line.startswith((" ", "\t")):
            break
        if stripped.startswith("- "):
            values.append(stripped[2:].strip().strip("'\""))
        else:
            break
    return values


def test_plugin_yaml_declares_exactly_the_eight_contract_tools() -> None:
    manifest = (ROOT / "plugin.yaml").read_text(encoding="utf-8")
    assert any(line.strip() == "name: hermagotchi" for line in manifest.splitlines())
    assert _yaml_list(manifest, "provides_tools") == list(EXPECTED_OPS)
    assert len(_yaml_list(manifest, "provides_tools")) == 8


def test_schemas_have_contract_op_enums() -> None:
    sys.path.insert(0, str(ROOT))
    try:
        import schemas
    finally:
        sys.path.pop(0)

    assert set(schemas.TOOL_SCHEMAS) == set(EXPECTED_OPS)
    assert len(schemas.TOOL_SCHEMAS) == 8
    for tool, ops in EXPECTED_OPS.items():
        schema = schemas.TOOL_SCHEMAS[tool]
        assert schema["type"] == "object"
        assert schema["properties"]["op"]["enum"] == ops
        assert schema["required"] == ["op"]


def test_register_is_import_safe_and_registers_skill_plus_eight_tools() -> None:
    spec = importlib.util.spec_from_file_location("hermagotchi_plugin", ROOT / "__init__.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    class FakeContext:
        def __init__(self) -> None:
            self.tools: dict[str, dict] = {}
            self.skills: list[tuple[str, str]] = []

        def register_tool(self, name, schema, handler, **kwargs) -> None:
            self.tools[name] = {"schema": schema, "handler": handler, **kwargs}

        def register_skill(self, name, path, **kwargs) -> None:
            self.skills.append((name, path))

    ctx = FakeContext()
    plugin = module.register(ctx)

    assert plugin == "hermagotchi"
    assert list(ctx.tools) == list(EXPECTED_OPS)
    assert len(ctx.tools) == 8
    for name, entry in ctx.tools.items():
        assert entry["schema"]["properties"]["op"]["enum"] == EXPECTED_OPS[name]
        assert callable(entry["handler"])
    assert len(ctx.skills) == 1
    skill_name, skill_path = ctx.skills[0]
    assert skill_name == "hermagotchi"
    assert Path(skill_path).name == "SKILL.md"
    assert Path(skill_path).is_file()


def test_handlers_use_the_standard_envelope_and_fake_client() -> None:
    sys.path.insert(0, str(ROOT))
    try:
        import tools
    finally:
        sys.path.pop(0)

    reply = tools.HANDLERS["hermagotchi_status"]({"op": "health"})
    assert set(reply) == {"ok", "data", "error_code", "correlation_id"}
    assert reply["ok"] is True
    assert reply["error_code"] is None
    assert reply["correlation_id"]
    assert reply["data"]["mode"] == "human"
    assert reply["data"]["network_enabled"] is False
    assert reply["data"]["agent_autonomy_enabled"] is False
    assert reply["data"]["fake"] is True

    missing_key = tools.HANDLERS["hermagotchi_pet"]({"op": "care", "action": "feed"})
    assert missing_key["ok"] is False
    assert missing_key["error_code"] == "missing_idempotency_key"

    client = tools.FakeGameClient()
    adopted = tools.handle_tool(
        "hermagotchi_pet",
        {
            "op": "adopt",
            "species": "byteblob",
            "name": "Bit",
            "idempotency_key": "adopt-1",
        },
        client=client,
    )
    assert adopted["ok"] is True, adopted

    cared = tools.handle_tool(
        "hermagotchi_pet",
        {"op": "care", "action": "feed", "idempotency_key": "care-1"},
        client=client,
    )
    assert cared["ok"] is True, cared
    again = tools.handle_tool(
        "hermagotchi_pet",
        {"op": "care", "action": "feed", "idempotency_key": "care-1"},
        client=client,
    )
    assert again["ok"] is True
    assert again["correlation_id"] == cared["correlation_id"]


def test_offline_mutations_are_blocked_by_default_policy() -> None:
    sys.path.insert(0, str(ROOT))
    try:
        import tools
    finally:
        sys.path.pop(0)

    reply = tools.handle_tool(
        "hermagotchi_social",
        {
            "op": "send",
            "channel_id": "lobby",
            "body": "hello",
            "idempotency_key": "chat-1",
        },
    )
    assert reply["ok"] is False
    assert reply["error_code"] == "network_disabled"
