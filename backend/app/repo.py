from __future__ import annotations
import json
from pathlib import Path
from typing import Any
from supabase import create_client, Client
from .config import get_settings


def _client() -> Client:
    s = get_settings()
    return create_client(s.supabase_url, s.supabase_service_key)


_STARTING_INVENTORY = [(1, 5), (2, 5), (4, 5), (5, 5), (8, 3), (15, 3), (16, 3)]


def get_or_create_player_by_nickname(nickname: str) -> dict[str, Any]:
    """닉네임으로 플레이어를 찾거나 새로 생성한다."""
    c = _client()
    rows = c.table("players").select("*").eq("nickname", nickname).limit(1).execute().data
    if rows:
        return rows[0]
    # 새 플레이어 생성
    new_player = c.table("players").insert({
        "nickname": nickname,
        "gold": 0,
        "reputation": 0,
        "craft_power": 0,
        "effort": 50,
        "current_day": 1,
        "current_phase": "forge_open",
    }).execute().data[0]
    player_id = new_player["id"]
    starting = [
        {"player_id": player_id, "material_id": mid, "qty": qty}
        for mid, qty in _STARTING_INVENTORY
    ]
    c.table("inventory").insert(starting).execute()
    return new_player


def reset_game(player_id: int) -> None:
    """해당 player_id의 게임 데이터를 초기화."""
    c = _client()
    c.table("inventory").delete().eq("player_id", player_id).execute()
    for table in ("day_events", "merchants_today", "battles", "negotiations", "heroes", "weapons"):
        c.table(table).delete().eq("player_id", player_id).execute()
    # players 행은 삭제하지 않고 상태만 초기화
    c.table("players").update({
        "gold": 0,
        "reputation": 0,
        "craft_power": 0,
        "effort": 50,
        "current_day": 1,
        "current_phase": "forge_open",
    }).eq("id", player_id).execute()
    # 초기 인벤토리 재시드
    starting = [
        {"player_id": player_id, "material_id": mid, "qty": qty}
        for mid, qty in _STARTING_INVENTORY
    ]
    c.table("inventory").insert(starting).execute()


def load_player(player_id: int) -> dict[str, Any] | None:
    c = _client()
    rows = c.table("players").select("*").eq("id", player_id).limit(1).execute().data
    return rows[0] if rows else None


def update_player(player_id: int, **fields: Any) -> None:
    _client().table("players").update(fields).eq("id", player_id).execute()


def load_inventory(player_id: int) -> list[dict[str, Any]]:
    c = _client()
    rows = c.table("inventory").select("material_id, qty, materials(name, category, attribute, base_price)") \
        .eq("player_id", player_id).execute().data
    return [
        {"material_id": r["material_id"], "qty": r["qty"], **r["materials"]}
        for r in rows
    ]


def deduct_materials(player_id: int, material_qty: dict[int, int]) -> None:
    c = _client()
    for mid, q in material_qty.items():
        cur = c.table("inventory").select("qty").eq("player_id", player_id).eq("material_id", mid).single().execute().data
        c.table("inventory").update({"qty": cur["qty"] - q}).eq("player_id", player_id).eq("material_id", mid).execute()


def insert_weapon(player_id: int, weapon: dict[str, Any]) -> dict[str, Any]:
    c = _client()
    return c.table("weapons").insert({**weapon, "player_id": player_id}).execute().data[0]


def load_player_weapons(player_id: int) -> list[dict[str, Any]]:
    return _client().table("weapons").select("*").eq("player_id", player_id).eq("owner", "player").execute().data


def get_weapon(weapon_id: int) -> dict[str, Any]:
    return _client().table("weapons").select("*").eq("id", weapon_id).single().execute().data


def transfer_weapon_to_hero(weapon_id: int, hero_id: int) -> None:
    _client().table("weapons").update({"owner": "sold"}).eq("id", weapon_id).execute()
    # hero가 무기를 보유한다는 사실은 battles에서 weapon_id로 참조하므로 별도 컬럼 불필요


def insert_hero(player_id: int, hero: dict[str, Any]) -> dict[str, Any]:
    return _client().table("heroes").insert({**hero, "player_id": player_id}).execute().data[0]


def get_hero(hero_id: int) -> dict[str, Any]:
    return _client().table("heroes").select("*").eq("id", hero_id).single().execute().data


def update_hero(hero_id: int, **fields: Any) -> None:
    _client().table("heroes").update(fields).eq("id", hero_id).execute()


def insert_negotiation(player_id: int, neg: dict[str, Any]) -> dict[str, Any]:
    return _client().table("negotiations").insert({**neg, "player_id": player_id}).execute().data[0]


def update_negotiation(neg_id: int, **fields: Any) -> None:
    _client().table("negotiations").update(fields).eq("id", neg_id).execute()


def get_negotiation(neg_id: int) -> dict[str, Any]:
    return _client().table("negotiations").select("*").eq("id", neg_id).single().execute().data


def insert_battle(player_id: int, b: dict[str, Any]) -> dict[str, Any]:
    return _client().table("battles").insert({**b, "player_id": player_id}).execute().data[0]


def list_alive_heroes(player_id: int) -> list[dict[str, Any]]:
    return _client().table("heroes").select("*").eq("player_id", player_id).eq("status", "alive").execute().data


def list_sold_weapons(player_id: int) -> list[dict[str, Any]]:
    return _client().table("weapons").select("*").eq("player_id", player_id).eq("owner", "sold").order("id").execute().data


# --- Plan 2: merchants_today ---

def get_merchant_today(player_id: int, day: int) -> dict[str, Any] | None:
    c = _client()
    rows = c.table("merchants_today").select("*") \
        .eq("player_id", player_id).eq("day", day).limit(1).execute().data
    return rows[0] if rows else None


def insert_merchant_today(player_id: int, m: dict[str, Any]) -> dict[str, Any]:
    return _client().table("merchants_today").insert({**m, "player_id": player_id}).execute().data[0]


def update_merchant_today(merchant_id: int, **fields: Any) -> None:
    _client().table("merchants_today").update(fields).eq("id", merchant_id).execute()


def add_inventory(player_id: int, material_id: int, qty: int) -> None:
    """인벤토리에 재료 추가. 없으면 insert, 있으면 qty 증가."""
    c = _client()
    rows = c.table("inventory").select("qty") \
        .eq("player_id", player_id).eq("material_id", material_id).limit(1).execute().data
    if rows:
        c.table("inventory").update({"qty": rows[0]["qty"] + qty}) \
            .eq("player_id", player_id).eq("material_id", material_id).execute()
    else:
        c.table("inventory").insert(
            {"player_id": player_id, "material_id": material_id, "qty": qty}
        ).execute()


# --- Plan 2: day_events ---

def insert_day_event(player_id: int, day: int, phase: str, kind: str, payload: dict[str, Any]) -> None:
    _client().table("day_events").insert({
        "player_id": player_id, "day": day, "phase": phase,
        "kind": kind, "payload": payload,
    }).execute()


def list_day_events(player_id: int, day: int) -> list[dict[str, Any]]:
    return _client().table("day_events").select("*") \
        .eq("player_id", player_id).eq("day", day).order("created_at").execute().data


# --- Plan 2: hero 조회 확장 ---

def list_alive_heroes_ready(player_id: int, day: int) -> list[dict[str, Any]]:
    """alive 상태이며 (return_day is null or return_day <= day) 인 용사들."""
    c = _client()
    return c.table("heroes").select("*").eq("player_id", player_id).eq("status", "alive") \
        .or_(f"return_day.is.null,return_day.lte.{day}").execute().data


# --- Plan 3 ---

def update_weapon(weapon_id: int, **fields: Any) -> None:
    _client().table("weapons").update(fields).eq("id", weapon_id).execute()


def count_consecutive_survives(player_id: int, hero_id: int) -> int:
    """이 hero의 가장 최근부터 거슬러 올라가며 'hero=survived AND demon=killed'가 끊기지 않는 연속 횟수."""
    c = _client()
    rows = c.table("battles").select("outcomes").eq("player_id", player_id).eq("hero_id", hero_id) \
        .order("id", desc=True).execute().data
    count = 0
    for r in rows:
        out = r.get("outcomes") or {}
        if out.get("hero") == "survived" and out.get("demon") == "killed":
            count += 1
        else:
            break
    return count
