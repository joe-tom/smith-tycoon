from fastapi import APIRouter
from .. import repo, hero_registry, merchant as merchant_module, negotiation

router = APIRouter()

NEGOTIATE_PHASES = ["hero1_negotiate", "hero2_negotiate", "hero3_negotiate"]
BATTLE_PHASES = ["hero1_battle", "hero2_battle", "hero3_battle"]


def _hero_index(phase: str) -> int | None:
    mapping = {"hero1_negotiate": 0, "hero1_battle": 0,
               "hero2_negotiate": 1, "hero2_battle": 1,
               "hero3_negotiate": 2, "hero3_battle": 2}
    return mapping.get(phase)


@router.get("/state")
def get_state():
    player = repo.load_player()
    if player is None:
        return {"player": None, "inventory": [], "weapons": [],
                "hero": None, "merchant": None}

    inventory = repo.load_inventory()
    weapons = [{**w, "market_price": negotiation.market_price(w)}
               for w in repo.load_player_weapons()]

    hero = None
    if player["current_phase"] in NEGOTIATE_PHASES + BATTLE_PHASES:
        todays = hero_registry.heroes_for_today(player["current_day"])
        idx = _hero_index(player["current_phase"])
        if idx is not None and idx < len(todays):
            h = todays[idx]
            mode = "enhance" if h.get("held_weapon_id") else "sell"
            held_weapon = None
            if mode == "enhance":
                w = repo.get_weapon(h["held_weapon_id"])
                held_weapon = {**w, "market_price": negotiation.market_price(w)}
            hero = {
                **h,
                "preferences": hero_registry.preferences_for(h),
                "mode": mode,
                "held_weapon": held_weapon,
            }

    merchant_today = None
    if player["current_phase"] == "merchant_negotiate":
        m = repo.get_merchant_today(player["current_day"])
        if m is None:
            bundle = merchant_module.generate_today(player["current_day"])
            m = repo.insert_merchant_today({"day": player["current_day"], **bundle,
                                             "outcome": "pending"})
        merchant_today = m

    return {
        "player": player,
        "inventory": inventory,
        "weapons": weapons,
        "hero": hero,
        "merchant": merchant_today,
    }
