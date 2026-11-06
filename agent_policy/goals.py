"""Goal record, validation, and the zero-token goal proposer.

The proposer consumes only an allowlisted, structured summary (wallet balance,
catalog prices, and open bounties). Chat bodies, opponent names, prompts, and
other free text are never copied into its input, so untrusted game text cannot
steer goal selection.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

GOAL_TYPES = ("cosmetic", "rank", "achievement")
CHOSEN_BY = ("human", "agent", "co-op", "coop")
_SAFE_TARGET = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$")

# Only these top-level keys can feed the heuristic. Everything else is dropped.
ALLOWED_SUMMARY_KEYS = frozenset(
    {
        "wallet",
        "wallet_bits",
        "balance",
        "bits",
        "catalog",
        "items",
        "prices",
        "open_bounties",
        "bounties",
        "rating",
        "rank",
    }
)
_ITEM_KEYS = frozenset(
    {"item_id", "id", "price_bits", "price", "slot", "owned", "rarity", "active"}
)
_BOUNTY_KEYS = frozenset(
    {
        "bounty_id",
        "id",
        "reward_bits",
        "reward_xp",
        "open",
        "claimed",
        "active",
        "expires_at",
    }
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def now_iso() -> str:
    return utc_now().isoformat(timespec="seconds").replace("+00:00", "Z")


def _parse_iso(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_target(target_id: Any) -> bool:
    if not isinstance(target_id, str):
        return False
    value = target_id.strip()
    if not value or "://" in value or "/" in value or "\\" in value:
        return False
    return bool(_SAFE_TARGET.fullmatch(value))


@dataclass
class Goal:
    """Owner-authorised cosmetic, rank, or achievement target."""

    type: str
    target_id: str
    chosen_by: str = "agent"
    chosen_at: str = field(default_factory=now_iso)
    spending_limit_bits: int = 0
    max_battles: int = 0
    expires_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "target_id": self.target_id,
            "chosen_by": self.chosen_by,
            "chosen_at": self.chosen_at,
            "spending_limit_bits": int(self.spending_limit_bits),
            "max_battles": int(self.max_battles),
            "expires_at": self.expires_at,
        }

    as_dict = to_dict

    def __getitem__(self, key: str) -> Any:
        return self.to_dict()[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self.to_dict().get(key, default)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any] | "Goal") -> "Goal":
        if isinstance(value, cls):
            return value
        raw = dict(value or {})
        return cls(
            type=str(raw.get("type") or raw.get("target_type") or ""),
            target_id=str(raw.get("target_id") or ""),
            chosen_by=str(raw.get("chosen_by") or "agent"),
            chosen_at=str(raw.get("chosen_at") or now_iso()),
            spending_limit_bits=_as_int(raw.get("spending_limit_bits"), 0),
            max_battles=_as_int(raw.get("max_battles"), 0),
            expires_at=raw.get("expires_at"),
        )

    from_mapping = from_dict


def make_goal(
    type: str | None = None,
    target_id: str = "",
    *,
    target_type: str | None = None,
    chosen_by: str = "agent",
    chosen_at: str | None = None,
    spending_limit_bits: int = 0,
    max_battles: int = 0,
    expires_at: str | None = None,
) -> Goal:
    return Goal(
        type=str(type or target_type or ""),
        target_id=str(target_id or ""),
        chosen_by=str(chosen_by or "agent"),
        chosen_at=str(chosen_at or now_iso()),
        spending_limit_bits=_as_int(spending_limit_bits, 0),
        max_battles=_as_int(max_battles, 0),
        expires_at=expires_at,
    )


def validate_goal(
    goal: Goal | Mapping[str, Any],
    *,
    now: datetime | None = None,
) -> str:
    """Validate a goal record and return ``"ok"`` or a stable error code."""

    record = Goal.from_dict(goal).to_dict()
    goal_type = str(record.get("type") or "").strip().lower()
    if goal_type not in GOAL_TYPES:
        return "invalid_goal_type"

    if not _safe_target(record.get("target_id")):
        return "invalid_target"

    chosen_by = str(record.get("chosen_by") or "").strip().lower()
    if chosen_by not in CHOSEN_BY:
        return "invalid_chosen_by"

    spending = record.get("spending_limit_bits")
    if not isinstance(spending, int) or spending < 0:
        return "invalid_spending_limit"

    max_battles = record.get("max_battles")
    if not isinstance(max_battles, int) or max_battles < 0:
        return "invalid_max_battles"

    expires_at = record.get("expires_at")
    if expires_at is not None:
        parsed = _parse_iso(expires_at)
        if parsed is None:
            return "invalid_expires_at"
        current = (now or utc_now()).astimezone(timezone.utc)
        if parsed <= current:
            return "goal_expired"

    chosen_at = record.get("chosen_at")
    if chosen_at is not None and _parse_iso(chosen_at) is None:
        return "invalid_chosen_at"

    return "ok"


def is_valid_goal(goal: Goal | Mapping[str, Any], **kwargs: Any) -> bool:
    return validate_goal(goal, **kwargs) == "ok"


def _safe_token(value: Any, limit: int = 64) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text or len(text) > limit or "://" in text or "/" in text or "\\" in text:
        return None
    return text


def _sanitize_wallet(value: Any) -> Any:
    if isinstance(value, Mapping):
        raw = value.get(
            "balance",
            value.get(
                "balance_bits",
                value.get("bits", value.get("wallet_bits")),
            ),
        )
        return {"balance": max(0, _as_int(raw, 0))}
    return max(0, _as_int(value, 0))


def _item_rows(value: Any) -> list[Mapping[str, Any]]:
    if isinstance(value, (list, tuple)):
        return [row for row in value if isinstance(row, Mapping)]
    if isinstance(value, Mapping):
        rows: list[Mapping[str, Any]] = []
        for item_id, raw in value.items():
            if isinstance(raw, Mapping):
                row = {
                    key: raw[key]
                    for key in _ITEM_KEYS
                    if key in raw
                }
                row.setdefault("item_id", item_id)
                rows.append(row)
            else:
                rows.append({"item_id": item_id, "price_bits": raw})
        return rows
    return []


def _sanitize_items(value: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in _item_rows(value):
        clean = {key: row[key] for key in _ITEM_KEYS if key in row}
        item_id = _safe_token(clean.get("item_id") or clean.get("id"))
        if item_id is None:
            continue
        clean["item_id"] = item_id
        clean.pop("id", None)
        price = clean.get("price_bits", clean.get("price"))
        if price is not None:
            clean["price_bits"] = max(0, _as_int(price, 0))
        clean.pop("price", None)
        rows.append(clean)
    return rows


def _bounty_rows(value: Any) -> list[Mapping[str, Any]]:
    if isinstance(value, (list, tuple)):
        return [row for row in value if isinstance(row, Mapping)]
    if isinstance(value, Mapping):
        return [
            {"bounty_id": bounty_id, "reward_bits": raw}
            for bounty_id, raw in value.items()
        ]
    return []


def _sanitize_bounties(value: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in _bounty_rows(value):
        clean = {key: row[key] for key in _BOUNTY_KEYS if key in row}
        bounty_id = _safe_token(clean.get("bounty_id") or clean.get("id"))
        if bounty_id is None:
            continue
        clean["bounty_id"] = bounty_id
        clean.pop("id", None)
        for key in ("reward_bits", "reward_xp"):
            if key in clean:
                clean[key] = max(0, _as_int(clean[key], 0))
        rows.append(clean)
    return rows


def sanitize_summary(summary: Mapping[str, Any] | None) -> dict[str, Any]:
    """Project an arbitrary summary onto the allowlisted proposer inputs."""

    if not isinstance(summary, Mapping):
        return {}
    clean: dict[str, Any] = {}
    for key in summary:
        if key not in ALLOWED_SUMMARY_KEYS:
            continue
        value = summary[key]
        if key == "wallet":
            clean[key] = _sanitize_wallet(value)
        elif key in {"wallet_bits", "balance", "bits"}:
            clean[key] = max(0, _as_int(value, 0))
        elif key in {"catalog", "items", "prices"}:
            clean[key] = _sanitize_items(value)
        elif key in {"open_bounties", "bounties"}:
            clean[key] = _sanitize_bounties(value)
        elif key == "rating":
            clean[key] = max(0, _as_int(value, 0))
        elif key == "rank":
            token = _safe_token(value)
            if token is not None:
                clean[key] = token
    return clean


def _balance_from(summary: Mapping[str, Any]) -> int:
    wallet = summary.get("wallet")
    if isinstance(wallet, Mapping):
        raw = wallet.get(
            "balance",
            wallet.get("balance_bits", wallet.get("bits", wallet.get("wallet_bits"))),
        )
        return max(0, _as_int(raw, 0))
    if isinstance(wallet, int):
        return max(0, wallet)
    for key in ("wallet_bits", "balance", "bits"):
        if key in summary:
            return max(0, _as_int(summary[key], 0))
    return 0


def _items_from(summary: Mapping[str, Any]) -> list[dict[str, Any]]:
    for key in ("catalog", "items", "prices"):
        value = summary.get(key)
        if value:
            rows = _sanitize_items(value)
            if rows:
                return rows
    return []


def _bounties_from(summary: Mapping[str, Any]) -> list[dict[str, Any]]:
    for key in ("open_bounties", "bounties"):
        value = summary.get(key)
        if value is not None:
            return [
                row
                for row in _sanitize_bounties(value)
                if not row.get("claimed", False)
                and row.get("open", True) is not False
                and row.get("active", True) is not False
            ]
    return []


def _max_battles(summary: Mapping[str, Any], fallback: int) -> int:
    bounties = _bounties_from(summary)
    if bounties:
        return 3
    return fallback


def propose_goal(
    summary: Mapping[str, Any] | None,
    *,
    policy: Any = None,
    now: datetime | None = None,
    ttl_hours: int = 24,
) -> dict[str, Any] | None:
    """Pick one cosmetic or rank goal using local rules only.

    Returns ``None`` when the owner has not enabled goal selection. The input is
    first projected onto :data:`ALLOWED_SUMMARY_KEYS`, so chat text and opponent
    free text cannot influence the decision.
    """

    if policy is not None:
        allowed = bool(
            policy.get("allow_goal_selection", False)
            if isinstance(policy, Mapping)
            else getattr(policy, "allow_goal_selection", False)
        )
        if not allowed:
            return None

    clean = sanitize_summary(summary)
    balance = _balance_from(clean)
    items = _items_from(clean)
    current = (now or utc_now()).astimezone(timezone.utc)
    expires_at = (current + timedelta(hours=max(1, int(ttl_hours)))).isoformat(
        timespec="seconds"
    ).replace("+00:00", "Z")

    unowned = [row for row in items if row.get("owned") is not True]
    candidates = unowned or items
    priced = [
        (max(0, _as_int(row.get("price_bits"), 0)), str(row["item_id"]))
        for row in candidates
        if row.get("item_id")
    ]

    if priced:
        unaffordable = [(price, item) for price, item in priced if price > balance]
        if unaffordable:
            price, item_id = min(unaffordable, key=lambda row: (row[0] - balance, row[0], row[1]))
        else:
            price, item_id = max(priced, key=lambda row: (row[0], row[1]))
        record = Goal(
            type="cosmetic",
            target_id=item_id,
            chosen_by="agent",
            chosen_at=current.isoformat(timespec="seconds").replace("+00:00", "Z"),
            spending_limit_bits=price,
            max_battles=_max_battles(clean, 2),
            expires_at=expires_at,
        )
        return record.to_dict()

    rank_hint = clean.get("rank")
    target_id = (
        rank_hint
        if isinstance(rank_hint, str) and rank_hint.startswith("rank.")
        else "rank.top_100"
    )
    record = Goal(
        type="rank",
        target_id=target_id,
        chosen_by="agent",
        chosen_at=current.isoformat(timespec="seconds").replace("+00:00", "Z"),
        spending_limit_bits=0,
        max_battles=_max_battles(clean, 1),
        expires_at=expires_at,
    )
    return record.to_dict()


def goal_progress(
    goal: Goal | Mapping[str, Any] | None,
    *,
    wallet_bits: int = 0,
    battles_completed: int = 0,
    rating: int | None = None,
) -> dict[str, Any]:
    """Return a compact, display-safe progress view for one goal."""

    if goal is None:
        return {"goal": None, "progress": 0, "progress_pct": 0, "done": False}
    record = Goal.from_dict(goal).to_dict()
    target = max(1, int(record["spending_limit_bits"]))
    if record["type"] == "cosmetic":
        progress = min(max(0, int(wallet_bits)), target)
        pct = int(round(progress * 100 / target))
        done = int(wallet_bits) >= int(record["spending_limit_bits"])
    elif record["type"] == "rank":
        progress = int(battles_completed)
        target = max(1, int(record["max_battles"]))
        pct = min(100, int(round(progress * 100 / target)))
        done = progress >= int(record["max_battles"])
        rating = rating
    else:
        progress = int(battles_completed)
        pct = min(100, int(round(progress * 100 / max(1, int(record["max_battles"])))))
        done = progress >= int(record["max_battles"])
    return {
        "goal": record,
        "progress": progress,
        "progress_pct": pct,
        "done": done,
        "rating": rating,
    }


__all__ = [
    "ALLOWED_SUMMARY_KEYS",
    "CHOSEN_BY",
    "GOAL_TYPES",
    "Goal",
    "goal_progress",
    "is_valid_goal",
    "make_goal",
    "now_iso",
    "propose_goal",
    "sanitize_summary",
    "utc_now",
    "validate_goal",
]
