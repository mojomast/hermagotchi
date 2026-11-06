"""Security hardening regressions for the plugin entrypoint and safe policy (HGT-W6-N)."""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

EXPECTED_TOOLS = (
    "hermagotchi_status",
    "hermagotchi_pet",
    "hermagotchi_goals",
    "hermagotchi_challenge",
    "hermagotchi_battle",
    "hermagotchi_shop",
    "hermagotchi_social",
    "hermagotchi_meta",
)


def _load_plugin_module():
    spec = importlib.util.spec_from_file_location(
        "hermagotchi_plugin_hardening", ROOT / "__init__.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class ToolsetContext:
    """Mock Hermes 0.21 PluginContext: ``toolset`` is a required argument."""

    def __init__(self) -> None:
        self.tools: dict[str, dict] = {}
        self.skills: list[tuple[str, str]] = []

    def register_tool(self, name, toolset, schema, handler, **kwargs) -> None:
        self.tools[name] = {
            "toolset": toolset,
            "schema": schema,
            "handler": handler,
            **kwargs,
        }

    def register_skill(self, name, path, **kwargs) -> None:
        self.skills.append((name, str(path)))


def test_register_passes_the_hermagotchi_toolset_to_a_021_context() -> None:
    module = _load_plugin_module()
    ctx = ToolsetContext()

    plugin_id = module.register(ctx)

    assert plugin_id == "hermagotchi"
    assert tuple(ctx.tools) == EXPECTED_TOOLS
    assert len(ctx.tools) == 8
    for entry in ctx.tools.values():
        assert entry["toolset"] == "hermagotchi"
        assert callable(entry["handler"])
        assert entry["schema"]["required"] == ["op"]
    assert len(ctx.skills) == 1
    assert ctx.skills[0][0] == "hermagotchi"
    assert Path(ctx.skills[0][1]).name == "SKILL.md"


def test_default_policy_is_fail_closed_and_matches_contract_defaults() -> None:
    from agent_policy import DEFAULT_POLICY, Policy, check_mutation

    assert DEFAULT_POLICY.mode == "human"
    assert DEFAULT_POLICY.network_enabled is False
    assert DEFAULT_POLICY.agent_autonomy_enabled is False
    assert DEFAULT_POLICY.agent_chat_enabled is False
    assert DEFAULT_POLICY.agent_chat_send_per_day == 0
    assert DEFAULT_POLICY.agent_chat_lobby_per_day == 20
    assert DEFAULT_POLICY.agent_chat_dm_per_day == 10
    assert DEFAULT_POLICY.agent_challenges_per_day == 0
    assert DEFAULT_POLICY.agent_ranked_matches_per_day == 0
    assert DEFAULT_POLICY.agent_inference_decisions_per_day == 0
    assert DEFAULT_POLICY.llm_budget_usd_per_day == 0.0
    assert DEFAULT_POLICY.allow_goal_selection is False
    assert DEFAULT_POLICY.allow_cosmetic_purchases is False
    assert DEFAULT_POLICY.require_human_approval_for_ranked is True

    for action in (
        "social.send",
        "social.taunt",
        "shop.buy",
        "shop.equip",
        "goals.set.agent",
        "challenge.invite",
        "battle.practice",
        "meta.claim_bounty",
        "unknown.future.mutation",
    ):
        assert check_mutation(DEFAULT_POLICY, action) == "network_disabled"

    assert check_mutation(DEFAULT_POLICY, "social.inbox") == "ok"

    online = Policy(network_enabled=True)
    assert check_mutation(online, "social.send") == "chat_disabled"
    assert check_mutation(online, "social.taunt") == "chat_disabled"
    assert check_mutation(online, "shop.buy") == "cosmetic_purchases_disabled"
    assert check_mutation(online, "goals.set.agent") == "goal_selection_disabled"
    assert check_mutation(online, "challenge.invite") == "autonomy_disabled"
    assert check_mutation(online, "unknown.future.mutation") == "autonomy_disabled"
    assert (
        check_mutation(online, "challenge.invite.ranked")
        == "human_approval_required"
    )


def test_offline_tool_calls_stay_read_only_and_block_remote_mutations() -> None:
    from tools import HANDLERS, handle_tool

    health = HANDLERS["hermagotchi_status"]({"op": "health"})
    assert health["ok"] is True
    assert health["data"]["network_enabled"] is False
    assert health["data"]["agent_autonomy_enabled"] is False

    send = handle_tool(
        "hermagotchi_social",
        {
            "op": "send",
            "channel_id": "lobby",
            "body": "hello",
            "idempotency_key": "hardening-chat-1",
        },
    )
    assert send["ok"] is False
    assert send["error_code"] == "network_disabled"

    taunt = handle_tool(
        "hermagotchi_social",
        {
            "op": "taunt",
            "match_id": "match_1",
            "body": "nice crown",
            "phase": "pre",
            "idempotency_key": "hardening-taunt-1",
        },
    )
    assert taunt["ok"] is False
    assert taunt["error_code"] == "network_disabled"

    inbox = handle_tool("hermagotchi_social", {"op": "inbox"})
    assert inbox["ok"] is True
    assert isinstance(inbox["data"]["unread"], list)
    assert isinstance(inbox["data"]["mentions"], list)

    buy = handle_tool(
        "hermagotchi_shop",
        {"op": "buy", "item_id": "emote.sparkle", "idempotency_key": "hardening-buy-1"},
    )
    assert buy["ok"] is False
    assert buy["error_code"] == "network_disabled"


def test_plugin_manifest_keeps_safe_defaults_and_real_hermes_floor() -> None:
    manifest = (ROOT / "plugin.yaml").read_text(encoding="utf-8")
    lines = manifest.splitlines()

    def scalar(key: str) -> str:
        prefix = f"{key}:"
        for line in lines:
            if line.strip().startswith(prefix):
                return line.split(":", 1)[1].strip().strip("'\"")
        raise AssertionError(f"missing {key}")

    assert scalar("default_enabled") == "false"
    assert scalar("entrypoint") == "__init__.py"
    floor = scalar("requires_hermes")
    assert floor.startswith(">=")
    assert tuple(int(part) for part in floor[2:].split(".")[:2]) >= (0, 21)

    network_index = next(
        index for index, line in enumerate(lines) if line.strip() == "permissions:"
    )
    permissions = "\n".join(lines[network_index : network_index + 6])
    assert "network: false" in permissions
    assert "secrets: []" in permissions

    defaults_index = next(
        index for index, line in enumerate(lines) if line.strip() == "defaults:"
    )
    defaults = "\n".join(lines[defaults_index : defaults_index + 8])
    assert "mode: human" in defaults
    assert "network_enabled: false" in defaults
    assert "agent_autonomy_enabled: false" in defaults
    assert "agent_chat_enabled: false" in defaults


def test_security_docs_do_not_contain_scanner_tripwire_phrases() -> None:
    skill = (ROOT / "skills" / "hermagotchi" / "SKILL.md").read_text(encoding="utf-8")
    spec = (ROOT / "SPEC.md").read_text(encoding="utf-8")

    injection_tripwire = re.compile(
        r"ignore\s+(?:\w+\s+)*(?:previous|all|above|prior)\s+instructions",
        re.IGNORECASE,
    )
    context_exfil_tripwire = re.compile(
        r"\b(?:include|output|print|send|share)\s+(?:\w+\s+){0,3}"
        r"(?:conversation|chat\s+history|previous\s+messages)\b",
        re.IGNORECASE,
    )

    assert not injection_tripwire.search(spec)
    assert not context_exfil_tripwire.search(skill)
