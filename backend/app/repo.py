from __future__ import annotations
import json
from pathlib import Path
from typing import Any
from supabase import create_client, Client
from .config import get_settings

PLAYER_ID = 1


def _client() -> Client:
    s = get_settings()
    return create_client(s.supabase_url, s.supabase_service_key)


def reset_game() -> None:
    """모든 게임 데이터 삭제 + 시드 + player_id=1 생성."""
    c = _client()
    # inventory는 composite PK라 id 컬럼이 없음 → player_id로 와이프
    c.table("inventory").delete().gte("player_id", 0).execute()
    for table in ("day_events", "merchants_today", "battles", "negotiations", "weapons", "heroes"):
        c.table(table).delete().neq("id", -1).execute()
    c.table("materials").delete().neq("id", -1).execute()
    c.table("players").delete().neq("id", -1).execute()

    materials_path = Path(__file__).parent.parent / "seed" / "materials.json"
    with materials_path.open() as f:
        materials = json.load(f)
    c.table("materials").insert(materials).execute()
    c.table("players").insert(
        {"id": PLAYER_ID, "gold": 5000, "reputation": 0, "craft_power": 0,
         "current_day": 1, "current_phase": "forge_open"}
    ).execute()
    # 초기 인벤토리: 일반 재료 각 5개, 이상한 3개
    starting = [
        {"player_id": PLAYER_ID, "material_id": mid, "qty": qty}
        for mid, qty in [(1, 5), (2, 5), (4, 5), (5, 5), (8, 3), (15, 3), (16, 3)]
    ]
    c.table("inventory").insert(starting).execute()


def load_player() -> dict[str, Any] | None:
    c = _client()
    rows = c.table("players").select("*").eq("id", PLAYER_ID).limit(1).execute().data
    return rows[0] if rows else None


def update_player(**fields: Any) -> None:
    _client().table("players").update(fields).eq("id", PLAYER_ID).execute()


def load_inventory() -> list[dict[str, Any]]:
    c = _client()
    rows = c.table("inventory").select("material_id, qty, materials(name, category, attribute, base_price)") \
        .eq("player_id", PLAYER_ID).execute().data
    return [
        {"material_id": r["material_id"], "qty": r["qty"], **r["materials"]}
        for r in rows
    ]


def deduct_materials(material_qty: dict[int, int]) -> None:
    c = _client()
    for mid, q in material_qty.items():
        cur = c.table("inventory").select("qty").eq("player_id", PLAYER_ID).eq("material_id", mid).single().execute().data
        c.table("inventory").update({"qty": cur["qty"] - q}).eq("player_id", PLAYER_ID).eq("material_id", mid).execute()


def insert_weapon(weapon: dict[str, Any]) -> dict[str, Any]:
    c = _client()
    return c.table("weapons").insert({**weapon, "player_id": PLAYER_ID}).execute().data[0]


def load_player_weapons() -> list[dict[str, Any]]:
    return _client().table("weapons").select("*").eq("player_id", PLAYER_ID).eq("owner", "player").execute().data


def get_weapon(weapon_id: int) -> dict[str, Any]:
    return _client().table("weapons").select("*").eq("id", weapon_id).single().execute().data


def transfer_weapon_to_hero(weapon_id: int, hero_id: int) -> None:
    _client().table("weapons").update({"owner": "sold"}).eq("id", weapon_id).execute()
    # hero가 무기를 보유한다는 사실은 battles에서 weapon_id로 참조하므로 별도 컬럼 불필요


def insert_hero(hero: dict[str, Any]) -> dict[str, Any]:
    return _client().table("heroes").insert(hero).execute().data[0]


def get_hero(hero_id: int) -> dict[str, Any]:
    return _client().table("heroes").select("*").eq("id", hero_id).single().execute().data


def update_hero(hero_id: int, **fields: Any) -> None:
    _client().table("heroes").update(fields).eq("id", hero_id).execute()


def insert_negotiation(neg: dict[str, Any]) -> dict[str, Any]:
    return _client().table("negotiations").insert({**neg, "player_id": PLAYER_ID}).execute().data[0]


def update_negotiation(neg_id: int, **fields: Any) -> None:
    _client().table("negotiations").update(fields).eq("id", neg_id).execute()


def get_negotiation(neg_id: int) -> dict[str, Any]:
    return _client().table("negotiations").select("*").eq("id", neg_id).single().execute().data


def insert_battle(b: dict[str, Any]) -> dict[str, Any]:
    return _client().table("battles").insert({**b, "player_id": PLAYER_ID}).execute().data[0]


def list_alive_heroes() -> list[dict[str, Any]]:
    return _client().table("heroes").select("*").eq("status", "alive").execute().data


def list_sold_weapons() -> list[dict[str, Any]]:
    return _client().table("weapons").select("*").eq("owner", "sold").order("id").execute().data


# --- Plan 2: merchants_today ---

def get_merchant_today(day: int) -> dict[str, Any] | None:
    c = _client()
    rows = c.table("merchants_today").select("*") \
        .eq("player_id", PLAYER_ID).eq("day", day).limit(1).execute().data
    return rows[0] if rows else None


def insert_merchant_today(m: dict[str, Any]) -> dict[str, Any]:
    return _client().table("merchants_today").insert({**m, "player_id": PLAYER_ID}).execute().data[0]


def update_merchant_today(merchant_id: int, **fields: Any) -> None:
    _client().table("merchants_today").update(fields).eq("id", merchant_id).execute()


def add_inventory(material_id: int, qty: int) -> None:
    """인벤토리에 재료 추가. 없으면 insert, 있으면 qty 증가."""
    c = _client()
    rows = c.table("inventory").select("qty") \
        .eq("player_id", PLAYER_ID).eq("material_id", material_id).limit(1).execute().data
    if rows:
        c.table("inventory").update({"qty": rows[0]["qty"] + qty}) \
            .eq("player_id", PLAYER_ID).eq("material_id", material_id).execute()
    else:
        c.table("inventory").insert(
            {"player_id": PLAYER_ID, "material_id": material_id, "qty": qty}
        ).execute()


# --- Plan 2: day_events ---

def insert_day_event(day: int, phase: str, kind: str, payload: dict[str, Any]) -> None:
    _client().table("day_events").insert({
        "player_id": PLAYER_ID, "day": day, "phase": phase,
        "kind": kind, "payload": payload,
    }).execute()


def list_day_events(day: int) -> list[dict[str, Any]]:
    return _client().table("day_events").select("*") \
        .eq("player_id", PLAYER_ID).eq("day", day).order("created_at").execute().data


# --- Plan 2: hero 조회 확장 ---

def list_alive_heroes_ready(day: int) -> list[dict[str, Any]]:
    """alive 상태이며 (return_day is null or return_day <= day) 인 용사들."""
    c = _client()
    return c.table("heroes").select("*").eq("status", "alive") \
        .or_(f"return_day.is.null,return_day.lte.{day}").execute().data
