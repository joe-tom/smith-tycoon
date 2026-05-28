from fastapi import APIRouter, Depends
from .. import repo, hero_registry, merchant as merchant_module, negotiation, returning_recap
from ..auth import current_player

router = APIRouter()


async def _hydrate_visitor(slot: dict, player: dict, pid: int, day: int) -> dict:
    """current_visitor 슬롯에 표시용 데이터 attach."""
    kind = slot["kind"]
    hydrated = dict(slot)
    if kind == "new_hero":
        h = repo.get_hero(slot["hero_id"])
        if h:
            mode = "enhance" if h.get("held_weapon_id") else "sell"
            held_weapon = None
            if mode == "enhance":
                w = repo.get_weapon(h["held_weapon_id"])
                held_weapon = {**w, "market_price": negotiation.market_price(w)}
            hydrated["hero"] = {
                **h,
                "preferences": hero_registry.preferences_for(h),
                "mode": mode,
                "held_weapon": held_weapon,
            }
    elif kind == "returning_hero":
        pending = repo.get_pending(slot["outcome_id"])
        hero = repo.get_hero(slot["hero_id"])
        if pending and hero:
            recap = await returning_recap.get_or_generate(player, pending, hero)
            hydrated["hero"] = hero
            hydrated["outcome"] = pending["outcome_json"]
            hydrated["weapon_snapshot"] = pending["weapon_snapshot"]
            hydrated["depart_day"] = pending["depart_day"]
            hydrated["recap"] = recap
    elif kind == "merchant":
        m = repo.get_merchant_today(pid, day)
        if m is None:
            bundle = merchant_module.generate_today(pid, day)
            m = repo.insert_merchant_today(pid, {"day": day, **bundle, "outcome": "pending"})
        hydrated["merchant"] = m
    return hydrated


@router.get("/state")
async def get_state(player: dict = Depends(current_player)):
    pid = player["id"]
    day = player["current_day"]
    phase = player["current_phase"]
    inventory = repo.load_inventory(pid)
    weapons = [{**w, "market_price": negotiation.market_price(w)}
               for w in repo.load_player_weapons(pid)]

    schedule = player.get("day_schedule") or []
    idx = player.get("current_visitor_index", 0)
    current_visitor = None
    if phase == "visitor" and idx < len(schedule):
        current_visitor = await _hydrate_visitor(schedule[idx], player, pid, day)

    death_mails: list = []
    if phase == "forge_open":
        pending = repo.list_pending_to_resolve(pid, day)
        death_mails = [
            {"id": p["id"], "hero_id": p["hero_id"],
             "weapon_snapshot": p["weapon_snapshot"], "outcome": p["outcome_json"]}
            for p in pending if p["kind"] == "death_mail" and not p["consumed"]
        ]

    boss_kill_count = len(repo.list_defeated_boss_ids(pid))

    return {
        "player": player,
        "inventory": inventory,
        "weapons": weapons,
        "current_visitor": current_visitor,
        "day_schedule": schedule,
        "current_visitor_index": idx,
        "death_mails": death_mails,
        "boss_kill_count": boss_kill_count,
    }
