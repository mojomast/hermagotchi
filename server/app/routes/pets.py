"""Adopt-once pet creation and sanitised public pet reads."""

from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
import uuid
from sqlite3 import Connection
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .. import ASSET_PACK_VERSION, CONTRACTS_VERSION
from ..db import account_exists, get_current_account_id, get_db, utc_now_iso
from ..economy import credit
from ..shop import loadout_for_pet

router = APIRouter(tags=["pets"])

STARTER_BITS = 300
STARTER_REASON = "economy.starter_grant"

Species = Literal[
    "byteblob",
    "patchfox",
    "nullgeist",
    "kernelcrab",
    "cachebat",
    "stacktoise",
    "daemowl",
    "shellsnail",
    "regexopus",
    "firewyrm",
]

SPECIES_STATS: dict[str, dict[str, int]] = {
    "byteblob": {"attack": 6, "defense": 8, "speed": 5, "control": 7},
    "patchfox": {"attack": 7, "defense": 5, "speed": 8, "control": 6},
    "nullgeist": {"attack": 6, "defense": 6, "speed": 6, "control": 9},
    "kernelcrab": {"attack": 5, "defense": 8, "speed": 3, "control": 4},
    "cachebat": {"attack": 6, "defense": 3, "speed": 8, "control": 3},
    "stacktoise": {"attack": 4, "defense": 9, "speed": 2, "control": 5},
    "daemowl": {"attack": 5, "defense": 4, "speed": 6, "control": 5},
    "shellsnail": {"attack": 6, "defense": 5, "speed": 3, "control": 6},
    "regexopus": {"attack": 5, "defense": 3, "speed": 6, "control": 6},
    "firewyrm": {"attack": 8, "defense": 4, "speed": 5, "control": 3},
}
PALETTES = ["palette_01", "palette_02", "palette_03", "palette_04", "palette_05", "palette_06"]
FEATURES = {
    "byteblob": ["crown_nub", "bubble_antenna", "seam_glow"],
    "patchfox": ["split_ear", "patch_tail", "wire_whisker"],
    "nullgeist": ["signal_horn", "phase_veil", "static_wisp"],
    "kernelcrab": ["claw_chip", "shell_plate", "stalk_eyes"],
    "cachebat": ["jagged_wing", "echo_ear", "fang_glint"],
    "stacktoise": ["stack_shell", "slow_step", "ridge_spike"],
    "daemowl": ["horn_tuft", "bark_mask", "blink_lid"],
    "shellsnail": ["spiral_shell", "eye_stalk", "slime_trail"],
    "regexopus": ["tentacle_curl", "pattern_skin", "ink_jet"],
    "firewyrm": ["ember_horn", "scale_ridge", "tail_flame"],
}
MARKINGS = ["dorsal_stripe", "cheek_dots", "banded_limb", "hex_speckle"]
TEMPERAMENTS = ["calm", "curious", "bold"]
QUIRKS = [
    "hums when calculating",
    "collects stray brackets",
    "judges your indentation",
    "naps in warm caches",
]


class AdoptRequest(BaseModel):
    species: Species
    name: str | None = Field(default=None, max_length=32)
    mode: Literal["human", "agent", "coop"] = "human"
    model_config = ConfigDict(extra="ignore")

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not 1 <= len(value) <= 32:
            raise ValueError("name must be 1-32 characters")
        return value


def _digest(species: str, seed: str, salt: str) -> str:
    return hashlib.sha256(f"{species}:{seed}:{salt}".encode("utf-8")).hexdigest()


def _pick(options: list[str], digest: str, offset: int) -> str:
    return options[int(digest[offset : offset + 8], 16) % len(options)]


def build_appearance(species: str, seed: str) -> dict[str, Any]:
    visual = _digest(species, seed, "appearance")
    return {
        "contracts_version": CONTRACTS_VERSION,
        "species": species,
        "seed": seed,
        "traits": {
            "palette": _pick(PALETTES, visual, 0),
            "feature": _pick(FEATURES[species], visual, 8),
            "marking": _pick(MARKINGS, visual, 16),
        },
        "rig": "small_front_v1",
        "asset_pack_version": ASSET_PACK_VERSION,
    }


def build_personality(species: str, seed: str) -> dict[str, str]:
    personality = _digest(species, seed, "personality")
    return {
        "temperament": _pick(TEMPERAMENTS, personality, 0),
        "quirk": _pick(QUIRKS, personality, 8),
    }


def _private_pet(row: sqlite3.Row, conn: Connection | None = None) -> dict[str, Any]:
    pet = {
        "contracts_version": CONTRACTS_VERSION,
        "id": row["id"],
        "account_id": row["account_id"],
        "name": row["name"],
        "species": row["species"],
        "appearance_seed": row["appearance_seed"],
        "appearance": build_appearance(row["species"], row["appearance_seed"]),
        "level": row["level"],
        "xp": row["xp"],
        "traits": json.loads(row["traits_json"]),
        "stats": json.loads(row["stats_json"]),
        "care": json.loads(row["care_json"]),
        "care_updated_at": row["care_updated_at"],
        "created_at": row["created_at"],
        "revision": row["revision"],
    }
    if conn is not None:
        # slot -> item payload (same shape as equip/care responses)
        pet["loadout"] = loadout_for_pet(conn, row["id"])
        pet["equipment"] = {
            slot: (item.get("id") if isinstance(item, dict) else item)
            for slot, item in pet["loadout"].items()
        }
    return pet


def _public_pet(row: sqlite3.Row, conn: Connection | None = None) -> dict[str, Any]:
    pet = _private_pet(row, conn)
    pet.pop("account_id", None)
    pet.pop("appearance_seed", None)
    pet.pop("care_updated_at", None)
    return pet


def _already_adopted_error() -> HTTPException:
    return HTTPException(
        status_code=409,
        detail={
            "code": "pet_already_adopted",
            "message": "This account already adopted its pet.",
        },
    )


@router.post("/pets", status_code=201)
def adopt_pet(
    payload: AdoptRequest,
    account_id: str = Depends(get_current_account_id),
    conn: Connection = Depends(get_db),
) -> dict[str, Any]:
    if not account_exists(conn, account_id):
        raise HTTPException(
            status_code=401,
            detail={"code": "unauthorized", "message": "A valid account session is required."},
        )

    if conn.execute("SELECT 1 FROM pets WHERE account_id = ?", (account_id,)).fetchone():
        raise _already_adopted_error()

    seed = secrets.token_hex(16)
    now = utc_now_iso()
    name = payload.name or payload.species.capitalize()
    pet_id = str(uuid.uuid4())
    care = {"health": 100, "comfort": 100, "hunger": 100, "energy": 100}

    try:
        with conn:
            conn.execute(
                """
                INSERT INTO pets (
                    id, account_id, species, name, appearance_seed, traits_json,
                    stats_json, care_json, care_updated_at, level, xp, created_at, revision
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 0, ?, 1)
                """,
                (
                    pet_id,
                    account_id,
                    payload.species,
                    name,
                    seed,
                    json.dumps(build_personality(payload.species, seed), sort_keys=True),
                    json.dumps(SPECIES_STATS[payload.species], sort_keys=True),
                    json.dumps(care, sort_keys=True),
                    now,
                    now,
                ),
            )
            credit(
                conn,
                account_id,
                STARTER_BITS,
                STARTER_REASON,
                f"{STARTER_REASON}:{account_id}",
            )
    except sqlite3.IntegrityError as exc:
        raise _already_adopted_error() from exc

    row = conn.execute("SELECT * FROM pets WHERE id = ?", (pet_id,)).fetchone()
    return _private_pet(row, conn)


@router.get("/pets/{pet_id}")
def get_pet(pet_id: str, conn: Connection = Depends(get_db)) -> dict[str, Any]:
    row = conn.execute("SELECT * FROM pets WHERE id = ?", (pet_id,)).fetchone()
    if row is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "pet_not_found", "message": "No pet exists for that id."},
        )
    return _public_pet(row, conn)
