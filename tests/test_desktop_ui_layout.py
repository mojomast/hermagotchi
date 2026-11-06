"""Filesystem contracts for the Hermagotchi Desktop UI sources (HGT-W3-I).

These checks intentionally stay in Python (no browser, no Node, no network) so
the integrator can validate the source layout before packing
``desktop/plugin.js``.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "desktop" / "src" / "ui"

TAB_MODULES = {
    "HabitatTab": UI / "tabs" / "HabitatTab.js",
    "BattleTab": UI / "tabs" / "BattleTab.js",
    "ShopTab": UI / "tabs" / "ShopTab.js",
    "LeaderboardTab": UI / "tabs" / "LeaderboardTab.js",
    "ChatTab": UI / "tabs" / "ChatTab.js",
    "SettingsTab": UI / "tabs" / "SettingsTab.js",
}

REQUIRED_FILES = [
    UI / "index.js",
    UI / "pane.js",
    UI / "states.js",
    UI / "register.js",
    UI / "components" / "CareMeter.js",
    UI / "README.md",
    *TAB_MODULES.values(),
    ROOT / "docs" / "DESKTOP_UI.md",
]

EXPECTED_EXPORTS = {
    UI / "index.js": {
        "HermagotchiPane",
        "PANE_ID",
        "PANE_TITLE",
        "TAB_IDS",
        "TAB_LABELS",
        "UI_STATES",
        "UI_STATE_COPY",
        "StateNotice",
        "resolveUiState",
        "registerHermagotchiPane",
        "createPaneContribution",
        "createDesktopPlugin",
        "HabitatTab",
        "BattleTab",
        "ShopTab",
        "LeaderboardTab",
        "ChatTab",
        "SettingsTab",
    },
    UI / "pane.js": {
        "HermagotchiPane",
        "TAB_IDS",
        "TAB_LABELS",
        "TAB_COMPONENTS",
    },
    UI / "states.js": {
        "UI_STATES",
        "UI_STATE_COPY",
        "resolveUiState",
        "StateNotice",
    },
    UI / "register.js": {
        "PANE_ID",
        "PANE_TITLE",
        "createPaneContribution",
        "registerHermagotchiPane",
        "createDesktopPlugin",
    },
    UI / "components" / "CareMeter.js": {"CareMeter"},
    UI / "tabs" / "HabitatTab.js": {"HabitatTab", "HABITAT_PLACEHOLDER"},
    UI / "tabs" / "BattleTab.js": {"BattleTab", "CHALLENGE_INBOX_PLACEHOLDER"},
    UI / "tabs" / "ShopTab.js": {"ShopTab", "SHOP_PLACEHOLDER_ITEMS"},
    UI / "tabs" / "LeaderboardTab.js": {"LeaderboardTab"},
    UI / "tabs" / "ChatTab.js": {"ChatTab"},
    UI / "tabs" / "SettingsTab.js": {"SettingsTab", "SETTINGS_PLACEHOLDER"},
}

TAB_ORDER = ["habitat", "battle", "shop", "leaderboard", "chat", "settings"]
TAB_LABELS = ["Habitat", "Battle", "Shop", "Leaderboard", "Chat", "Settings"]

ALLOWED_IMPORTS = {"react", "react/jsx-runtime", "@hermes/plugin-sdk"}

_EXPORT_DECL = re.compile(
    r"export\s+(?:async\s+)?(?:function|const|let|var|class)\s+([A-Za-z_$][\w$]*)"
)
_EXPORT_LIST = re.compile(r"export\s*\{([^}]*)\}", re.DOTALL)
_IMPORT = re.compile(
    r"""\bfrom\s+["']([^"']+)["']|^\s*import\s+["']([^"']+)["']""",
    re.MULTILINE,
)

_FORBIDDEN_PATTERNS = [
    re.compile(r"(?:^|[^A-Za-z0-9])/(?:home|workspace)/[^\s\"']*"),
    re.compile(r"[A-Za-z]:\\\\Users\\\\"),
    re.compile(r"\.ts\.net\b"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\bsk-[A-Za-z0-9]{12,}\b"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\b"),
    re.compile(
        r"""(?i)\b(?:api[_-]?key|client[_-]?secret|access[_-]?token)\s*[:=]\s*["'][^"']{8,}["']"""
    ),
]


def _source(path: Path) -> str:
    assert path.is_file(), f"missing required file: {path.relative_to(ROOT)}"
    return path.read_text(encoding="utf-8")


def _exported_names(source: str) -> set[str]:
    names = set(_EXPORT_DECL.findall(source))
    for block in _EXPORT_LIST.findall(source):
        for item in block.split(","):
            item = item.strip()
            if not item:
                continue
            names.add(item.split()[-1])
    return names


def test_required_desktop_ui_files_exist() -> None:
    missing = [str(path.relative_to(ROOT)) for path in REQUIRED_FILES if not path.is_file()]
    assert not missing, f"missing required Desktop UI files: {missing}"


def test_ui_modules_export_expected_symbols() -> None:
    for path, expected in EXPECTED_EXPORTS.items():
        exported = _exported_names(_source(path))
        missing = sorted(expected - exported)
        assert not missing, f"{path.relative_to(ROOT)} does not export {missing}"


def test_pane_declares_the_six_tabs_in_order() -> None:
    pane = _source(UI / "pane.js")
    match = re.search(r"TAB_IDS\s*=\s*Object\.freeze\(\[(.*?)\]\)", pane, re.DOTALL)
    assert match is not None, "pane.js must declare TAB_IDS"
    assert re.findall(r'"([a-z_]+)"', match.group(1)) == TAB_ORDER

    index = _source(UI / "index.js")
    for label in TAB_LABELS:
        assert f'"{label}"' in pane, f"pane.js is missing the {label} tab label"
        assert f'"{label}"' in index or f'./tabs/{label}Tab.js' in index


def test_each_tab_stub_contains_its_required_placeholder_content() -> None:
    expected_text = {
        "HabitatTab": ["Pet name", "Species", "Fullness", "Happiness", "Energy"],
        "BattleTab": ["Challenge inbox", "No pending challenges"],
        "ShopTab": ["Bits balance", "Price", "Buy (disabled)", "Preview only"],
        "LeaderboardTab": ["Leaderboard", "No ranked matches yet", "Rating"],
        "ChatTab": ["Chat is off by default", "disabled"],
        "SettingsTab": ["Settings", "Python backend", "Multiplayer URL", "Not paired"],
    }
    for name, needles in expected_text.items():
        source = _source(TAB_MODULES[name])
        missing = [needle for needle in needles if needle not in source]
        assert not missing, f"{name} is missing placeholder content: {missing}"


def test_ui_states_cover_the_required_offline_and_setup_conditions() -> None:
    states = _source(UI / "states.js")
    required_codes = [
        "ready",
        "backend_disabled",
        "network_off",
        "auth_missing",
        "service_unavailable",
    ]
    required_labels = [
        "Backend disabled",
        "Network off",
        "Auth missing",
        "Service unavailable",
    ]
    for code in required_codes:
        assert code in states, f"states.js is missing the {code} state"
    for label in required_labels:
        assert label in states, f"states.js is missing the {label} copy"


def test_sources_use_only_allowed_imports_and_no_jsx_syntax() -> None:
    for path in sorted(UI.rglob("*.js")):
        source = _source(path)
        assert "eval(" not in source, f"{path.name} must not use eval"
        assert not re.search(r"\brequire\s*\(", source), f"{path.name} must not use require"
        assert not re.search(r"\bimport\s*\(", source), f"{path.name} must not use dynamic import"
        assert not re.search(r"<[A-Za-z][^>\n]*>", source), f"{path.name} must not contain JSX tags"
        for first, second in _IMPORT.findall(source):
            specifier = first or second
            if specifier.startswith("."):
                continue
            assert specifier in ALLOWED_IMPORTS, (
                f"{path.name} imports unsupported module {specifier!r}"
            )

    pane = _source(UI / "pane.js")
    assert "jsx(" in pane and "jsxs(" in pane, "pane.js must use the jsx/jsxs runtime"


def test_docs_and_sources_do_not_contain_secrets_or_private_paths() -> None:
    paths = [*sorted(UI.rglob("*.js")), UI / "README.md", ROOT / "docs" / "DESKTOP_UI.md"]
    for path in paths:
        text = _source(path)
        for pattern in _FORBIDDEN_PATTERNS:
            assert not pattern.search(text), (
                f"{path.relative_to(ROOT)} contains a forbidden secret/path pattern"
            )


def test_readme_documents_tab_map_and_integrator_import() -> None:
    readme = _source(UI / "README.md")
    doc = _source(ROOT / "docs" / "DESKTOP_UI.md")
    for label in TAB_LABELS:
        assert label in readme, f"README is missing the {label} tab"
        assert label in doc, f"docs/DESKTOP_UI.md is missing the {label} tab"
    for needle in ["registerHermagotchiPane", "src/ui/index.js", "desktop/plugin.js"]:
        assert needle in readme, f"README is missing integrator guidance for {needle}"
    for needle in ["registerHermagotchiPane", "src/ui/index.js", "desktop/plugin.js"]:
        assert needle in doc, f"docs/DESKTOP_UI.md is missing {needle}"
