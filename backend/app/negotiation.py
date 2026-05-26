from __future__ import annotations
from typing import Any
from . import repo, state_machine
from .llm.client import complete_json

CATEGORY_BASE = {"일반": 50, "이상한": 5, "특수": 250, "전설": 1500}


def market_price(weapon: dict[str, Any]) -> int:
    mat_value = sum(
        CATEGORY_BASE.get(m["category"], 50) * m.get("qty", 1)
        for m in weapon["materials_used"]
    )
    rarity_mult = 1 + weapon["rarity"] / 100
    sharp_mult = 1 + weapon["sharpness"] / 200
    return max(10, int(mat_value * rarity_mult * sharp_mult))


def clamp_price(price: int, base: int) -> int:
    return max(int(base * 0.1), min(int(base * 5.0), price))


async def step_sell(weapon_id: int, hero_id: int, price_offered: int,
                    player_message: str, neg_id: int | None) -> dict[str, Any]:
    weapon = repo.get_weapon(weapon_id)
    hero = repo.get_hero(hero_id)
    base = market_price(weapon)
    safe_price = clamp_price(price_offered, base)

    if neg_id is None:
        player = repo.load_player()
        neg = repo.insert_negotiation({
            "day": player["current_day"], "phase": player["current_phase"],
            "kind": "sell", "counterparty_id": hero_id, "weapon_id": weapon_id,
            "rounds": [], "outcome": "open",
        })
        neg_id = neg["id"]
        prior_rounds: list[dict[str, Any]] = []
    else:
        neg = repo.get_negotiation(neg_id)
        prior_rounds = neg["rounds"]

    fixture_name = "negotiate_accept"  # 픽스처 모드의 기본; 실제 LLM은 prompt 결과 사용
    llm = await complete_json("negotiate_sell", fixture_name,
                              hero=hero, weapon=weapon,
                              market_price=base,
                              prior_rounds=prior_rounds,
                              player_message=player_message,
                              price_offered=safe_price)

    decision = llm["decision"]
    counter = llm.get("counter_price")
    if counter is not None:
        counter = clamp_price(int(counter), base)

    new_rounds = prior_rounds + [
        {"role": "player", "message": player_message, "price": safe_price},
        {"role": "hero", "message": llm["message"], "price": counter},
    ]
    update: dict[str, Any] = {"rounds": new_rounds}
    if decision == "accept":
        update["outcome"] = "accepted"
        update["agreed_price"] = safe_price
    elif decision == "reject":
        update["outcome"] = "rejected"
        # 거절 시 평판 -1, 무기 없이 전투 phase로 진행 (architecture.md §8.4)
        player_now = repo.load_player()
        repo.update_player(
            reputation=player_now["reputation"] - 1,
            current_phase=state_machine.next_phase(player_now["current_phase"]),
        )
    repo.update_negotiation(neg_id, **update)

    return {
        "negotiation_id": neg_id,
        "decision": decision,
        "counter_price": counter,
        "message": llm["message"],
    }


def player_accept_counter(neg_id: int) -> int:
    """플레이어가 용사의 마지막 카운터를 수락. 합의가로 outcome=accepted 설정."""
    neg = repo.get_negotiation(neg_id)
    if neg["outcome"] != "open":
        raise ValueError(f"negotiation already {neg['outcome']}")
    # 가장 최근 hero 라운드의 가격을 합의가로
    hero_rounds = [r for r in neg["rounds"] if r["role"] == "hero" and r.get("price") is not None]
    if not hero_rounds:
        raise ValueError("no hero counter to accept")
    agreed = int(hero_rounds[-1]["price"])
    repo.update_negotiation(neg_id, outcome="accepted", agreed_price=agreed)
    return agreed


def player_reject(neg_id: int) -> None:
    """플레이어가 협상을 결렬시킴. 평판 -1, 전투 phase로 진행."""
    neg = repo.get_negotiation(neg_id)
    if neg["outcome"] != "open":
        raise ValueError(f"negotiation already {neg['outcome']}")
    repo.update_negotiation(neg_id, outcome="rejected")
    player_now = repo.load_player()
    repo.update_player(
        reputation=player_now["reputation"] - 1,
        current_phase=state_machine.next_phase(player_now["current_phase"]),
    )


def finalize_sale(neg_id: int) -> None:
    neg = repo.get_negotiation(neg_id)
    if neg["outcome"] != "accepted":
        raise ValueError("negotiation not accepted")
    player = repo.load_player()
    repo.transfer_weapon_to_hero(neg["weapon_id"], neg["counterparty_id"])
    repo.update_player(gold=player["gold"] + neg["agreed_price"],
                       reputation=player["reputation"] + 1,
                       current_phase=state_machine.next_phase(player["current_phase"]))
    hero = repo.get_hero(neg["counterparty_id"])
    weapon = repo.get_weapon(neg["weapon_id"])
    new_history = (hero["history"] or []) + [
        {"weapon": weapon["name"], "price": neg["agreed_price"], "battle": None}
    ]
    repo.update_hero(neg["counterparty_id"], affinity=hero["affinity"] + 5,
                     history=new_history[-5:])
