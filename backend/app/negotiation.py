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
    repo.insert_day_event(
        day=player["current_day"], phase=player["current_phase"], kind="sale",
        payload={"negotiation_id": neg_id, "weapon_id": neg["weapon_id"],
                 "hero_id": neg["counterparty_id"], "price": neg["agreed_price"]},
    )


# --- Plan 2: 상인 협상 (매수) ---

async def step_buy(merchant_id: int, price_offered: int, player_message: str,
                   neg_id: int | None) -> dict[str, Any]:
    from . import merchant as merchant_module

    m_row = _client_or_repo_get_merchant(merchant_id)
    bundle = {"materials": m_row["materials"], "weapon": m_row.get("weapon")}
    base = merchant_module.bundle_market_price(bundle)
    safe_price = clamp_price(price_offered, base)

    if neg_id is None:
        player = repo.load_player()
        neg = repo.insert_negotiation({
            "day": player["current_day"], "phase": player["current_phase"],
            "kind": "buy", "counterparty_id": merchant_id, "weapon_id": None,
            "materials": bundle, "rounds": [], "outcome": "open",
        })
        neg_id = neg["id"]
        prior_rounds: list[dict[str, Any]] = []
    else:
        neg = repo.get_negotiation(neg_id)
        prior_rounds = neg["rounds"]

    llm = await complete_json(
        "negotiate_buy", "negotiate_buy_accept",
        materials=bundle["materials"], weapon=bundle.get("weapon"),
        market_price=base, asking_price=base,
        prior_rounds=prior_rounds,
        player_message=player_message,
        price_offered=safe_price,
    )

    decision = llm["decision"]
    counter = llm.get("counter_price")
    if counter is not None:
        counter = clamp_price(int(counter), base)

    new_rounds = prior_rounds + [
        {"role": "player", "message": player_message, "price": safe_price},
        {"role": "merchant", "message": llm["message"], "price": counter},
    ]
    update: dict[str, Any] = {"rounds": new_rounds}
    if decision == "accept":
        update["outcome"] = "accepted"
        update["agreed_price"] = safe_price
    elif decision == "reject":
        update["outcome"] = "rejected"
        # 상인 reject 시 phase advance + merchant 정리 (평판 변화는 §7.2: 즉시 거절 0)
        player_now = repo.load_player()
        repo.update_player(current_phase=state_machine.next_phase(player_now["current_phase"]))
        repo.update_merchant_today(neg["counterparty_id"], outcome="done")
    repo.update_negotiation(neg_id, **update)

    return {
        "negotiation_id": neg_id,
        "decision": decision,
        "counter_price": counter,
        "message": llm["message"],
    }


def finalize_buy(neg_id: int) -> None:
    neg = repo.get_negotiation(neg_id)
    if neg["outcome"] != "accepted":
        raise ValueError("negotiation not accepted")
    player = repo.load_player()
    if player["gold"] < neg["agreed_price"]:
        raise ValueError("insufficient gold")
    bundle = neg["materials"]

    for m in bundle["materials"]:
        repo.add_inventory(m["material_id"], m["qty"])

    if bundle.get("weapon"):
        w = bundle["weapon"]
        repo.insert_weapon({
            "owner": "player",
            "name": w["name"], "type": w["type"], "rarity": w["rarity"],
            "sharpness": w["sharpness"], "attribute": w.get("attribute"),
            "skill": w["skill"], "str_req": w["str_req"], "mag_req": w["mag_req"],
            "enhancement_level": 0, "materials_used": [], "created_day": player["current_day"],
        })

    repo.update_player(
        gold=player["gold"] - neg["agreed_price"],
        reputation=player["reputation"] + 1,
        current_phase=state_machine.next_phase(player["current_phase"]),
    )

    repo.update_merchant_today(neg["counterparty_id"], outcome="done")

    repo.insert_day_event(
        day=player["current_day"], phase=player["current_phase"], kind="buy",
        payload={"price": neg["agreed_price"], "materials": bundle["materials"],
                 "weapon": bundle.get("weapon")},
    )


def player_accept_buy_counter(neg_id: int) -> int:
    neg = repo.get_negotiation(neg_id)
    if neg["outcome"] != "open":
        raise ValueError(f"negotiation already {neg['outcome']}")
    merchant_rounds = [r for r in neg["rounds"] if r["role"] == "merchant" and r.get("price") is not None]
    if not merchant_rounds:
        raise ValueError("no merchant counter to accept")
    agreed = int(merchant_rounds[-1]["price"])
    repo.update_negotiation(neg_id, outcome="accepted", agreed_price=agreed)
    return agreed


def player_reject_buy(neg_id: int) -> None:
    neg = repo.get_negotiation(neg_id)
    if neg["outcome"] != "open":
        raise ValueError(f"negotiation already {neg['outcome']}")
    repo.update_negotiation(neg_id, outcome="rejected")
    player_now = repo.load_player()
    rep_delta = -1 if neg["rounds"] else 0
    repo.update_player(
        reputation=player_now["reputation"] + rep_delta,
        current_phase=state_machine.next_phase(player_now["current_phase"]),
    )
    repo.update_merchant_today(neg["counterparty_id"], outcome="done")


def _client_or_repo_get_merchant(merchant_id: int) -> dict[str, Any]:
    """merchant_today 행 로드 헬퍼."""
    from . import repo as _repo
    c = _repo._client()
    return c.table("merchants_today").select("*").eq("id", merchant_id).single().execute().data
