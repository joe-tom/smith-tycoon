from __future__ import annotations
from typing import Any
from . import repo, state_machine
from .llm.client import complete_json

CATEGORY_BASE = {"일반": 50, "이상한": 5, "특수": 250, "전설": 1500}


def _material_value(m: dict[str, Any]) -> int:
    """재료 한 항목의 값. `base_value` 명시되면 그 값을 사용 (상인 매입품 등)."""
    if "base_value" in m and m["base_value"] is not None:
        return int(m["base_value"])
    return CATEGORY_BASE.get(m["category"], 50) * m.get("qty", 1)


def market_price(weapon: dict[str, Any]) -> int:
    mat_value = sum(_material_value(m) for m in weapon["materials_used"])
    rarity_mult = 1 + weapon["rarity"] / 100
    sharp_mult = 1 + weapon["sharpness"] / 200
    return max(10, int(mat_value * rarity_mult * sharp_mult))


def clamp_price(price: int, base: int) -> int:
    return max(int(base * 0.1), min(int(base * 5.0), price))


async def step_sell(player: dict, weapon_id: int, hero_id: int, price_offered: int,
                    player_message: str, neg_id: int | None) -> dict[str, Any]:
    pid = player["id"]
    weapon = repo.get_weapon(weapon_id)
    hero = repo.get_hero(hero_id)
    base = market_price(weapon)
    hero_gold = max(0, int(hero.get("gold", 0)))
    # 매도: 플레이어 제시가는 용사 보유 금화 이하로만 (용사가 못 살 가격은 비현실).
    safe_price = min(max(1, int(price_offered)), max(1, hero_gold))

    # Plan 3: 호감도 ≤ -50 → 즉시 거부 (협상 진입 자체 거부)
    from . import affinity as affinity_mod
    affinity = int(hero.get("affinity", 0))
    max_pct = affinity_mod.allowed_max_pct(affinity)
    if max_pct == affinity_mod.REJECT_SENTINEL:
        player_now = repo.load_player(pid)
        repo.insert_day_event(
            pid, day=player_now["current_day"], phase=player_now["current_phase"],
            kind="reject", payload={"by": "hero_blacklist", "hero_id": hero_id, "rep_delta": 0},
        )
        return {
            "negotiation_id": -1,
            "decision": "reject",
            "counter_price": None,
            "message": "당신과는 거래하지 않겠소.",
        }
    ceiling = int(base * max_pct)

    if neg_id is None:
        player_now2 = repo.load_player(pid)
        neg = repo.insert_negotiation(pid, {
            "day": player_now2["current_day"], "phase": player_now2["current_phase"],
            "kind": "sell", "counterparty_id": hero_id, "weapon_id": weapon_id,
            "rounds": [], "outcome": "open",
        })
        neg_id = neg["id"]
        prior_rounds: list[dict[str, Any]] = []
    else:
        neg = repo.get_negotiation(neg_id)
        prior_rounds = neg["rounds"]

    # 서버 강제: 용사(매수자) 카운터는 "지불 의향 상한"이므로 시간에 따라 단조 비감소.
    hero_prior_counters = [int(r["price"]) for r in prior_rounds
                            if r["role"] == "hero" and r.get("price") is not None]
    max_hero_counter = max(hero_prior_counters) if hero_prior_counters else None

    # 자동 수락 — prior counter가 있을 때만 발동 (첫 라운드는 LLM 응답 필수).
    # ceiling은 LLM 프롬프트로 안내해 LLM이 자체 판단하도록.
    server_can_accept = (
        max_hero_counter is not None
        and safe_price <= max_hero_counter
        and safe_price <= ceiling
    )

    if server_can_accept:
        llm = {
            "decision": "accept",
            "counter_price": None,
            "message": f"좋소, {safe_price} 골드면 거래합시다.",
        }
    else:
        from . import hero_registry as _hr
        prefs = _hr.preferences_for(hero)
        weapon_fits = weapon["type"] in prefs.get("types", [])
        fixture_name = "negotiate_accept"
        llm = await complete_json("negotiate_sell", fixture_name,
                                  hero=hero, weapon=weapon,
                                  market_price=base,
                                  prior_rounds=prior_rounds,
                                  player_message=player_message,
                                  price_offered=safe_price,
                                  preferences=prefs,
                                  weapon_fits=weapon_fits,
                                  # Plan 3 신규
                                  affinity=affinity,
                                  allowed_max_pct=max_pct,
                                  ceiling=ceiling,
                                  history_recent=(hero.get("history") or [])[-5:],
                                  nickname=hero.get("nickname"))

    decision = llm["decision"]
    counter = llm.get("counter_price")
    original_counter = int(counter) if counter is not None else None
    if counter is not None:
        counter = clamp_price(int(counter), base)
        # 용사의 새 카운터는 이전 최고 카운터보다 낮아질 수 없음 (자기 의향가 후퇴 금지)
        if max_hero_counter is not None and counter < max_hero_counter:
            counter = max_hero_counter
        # 시세 대비 합리적 최저선 — 선호 맞으면 70%, 안 맞으면 50%
        from . import hero_registry as _hr
        _prefs = _hr.preferences_for(hero)
        _fits = weapon["type"] in _prefs.get("types", [])
        floor = int(base * (0.7 if _fits else 0.5))
        if counter < floor:
            counter = floor
        # 용사는 자기 보유 금화 이상으론 못 산다 — counter를 hero_gold로 캡
        counter = min(counter, hero_gold)

        # 서버 조정 후 카운터가 player 제시가 이상 → player의 가격을 hero가 충분히 낼 수 있다는 뜻 → 자동 accept
        if counter >= safe_price:
            decision = "accept"
            llm = {**llm, "decision": "accept", "counter_price": None,
                   "message": f"좋소, {safe_price} 골드에 거래합시다."}
            counter = None
        elif original_counter is not None and counter != original_counter:
            # LLM이 말한 가격과 서버 조정 후 가격이 다르면 메시지를 일관성 있게 교체
            if counter >= hero_gold:
                llm = {**llm, "message": f"이 무기는 내 능력으론 벅차오. 가진 돈 {hero_gold} 골드까진 내겠소만 더는 무리요."}
            else:
                llm = {**llm, "message": f"그 가격은 비싸오. {counter} 골드 정도면 어떻겠소?"}

    # 플레이어 제시가가 용사 금화를 초과하고 LLM이 accept라면 강제 reject 처리
    if decision == "accept" and safe_price > hero_gold:
        decision = "reject"
        llm = {**llm, "decision": "reject",
               "message": f"미안하지만 그 가격엔 사질 못하겠소. 내가 가진 돈은 {hero_gold}골드뿐이오."}

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
        player_now = repo.load_player(pid)
        repo.insert_day_event(
            pid, day=player_now["current_day"], phase=player_now["current_phase"],
            kind="reject", payload={"by": "hero", "hero_id": hero_id, "rep_delta": -1},
        )
        repo.update_player(
            pid,
            reputation=player_now["reputation"] - 1,
        )
    repo.update_negotiation(neg_id, **update)

    return {
        "negotiation_id": neg_id,
        "decision": decision,
        "counter_price": counter,
        "message": llm["message"],
    }


def player_accept_counter(player: dict, neg_id: int) -> int:
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


def player_reject(player: dict, neg_id: int) -> None:
    """플레이어가 협상을 결렬시킴. 평판 -1, 전투 phase로 진행."""
    pid = player["id"]
    neg = repo.get_negotiation(neg_id)
    if neg["outcome"] != "open":
        raise ValueError(f"negotiation already {neg['outcome']}")
    repo.update_negotiation(neg_id, outcome="rejected")
    player_now = repo.load_player(pid)
    repo.insert_day_event(
        pid, day=player_now["current_day"], phase=player_now["current_phase"],
        kind="reject", payload={"by": "player", "negotiation_id": neg_id, "rep_delta": -1},
    )
    repo.update_player(
        pid,
        reputation=player_now["reputation"] - 1,
    )


def finalize_sale(player: dict, neg_id: int) -> None:
    pid = player["id"]
    neg = repo.get_negotiation(neg_id)
    if neg["outcome"] != "accepted":
        raise ValueError("negotiation not accepted")
    if neg.get("finalized"):
        raise ValueError("already_finalized")
    repo.update_negotiation(neg_id, finalized=True)   # 멱등성 — 우선 마킹
    player_now = repo.load_player(pid)
    repo.transfer_weapon_to_hero(neg["weapon_id"], neg["counterparty_id"])
    weapon_for_recover = repo.get_weapon(neg["weapon_id"])
    _base_for_recover = market_price(weapon_for_recover)
    _ratio_for_recover = neg["agreed_price"] / max(_base_for_recover, 1)
    if _ratio_for_recover >= 2.0:
        effort_recover = 20
    elif _ratio_for_recover >= 1.3:
        effort_recover = 10
    else:
        effort_recover = 0
    new_effort_after_sale = min(100, int(player_now.get("effort", 0)) + effort_recover)
    # phase 진행은 호출측(api/negotiate.py)이 dispatch_hero + advance_visitor로 처리한다.
    repo.update_player(pid, gold=player_now["gold"] + neg["agreed_price"],
                       reputation=player_now["reputation"] + 1,
                       effort=new_effort_after_sale)
    hero = repo.get_hero(neg["counterparty_id"])
    weapon = repo.get_weapon(neg["weapon_id"])

    # Plan 3: 호감도 변화 — 합의가/시세 비율 기반
    from . import affinity as affinity_mod
    base = market_price(weapon)
    ratio = neg["agreed_price"] / max(base, 1)
    aff_delta = affinity_mod.delta_from_ratio(ratio)
    new_affinity = affinity_mod.clamp_affinity(int(hero.get("affinity", 0)) + aff_delta)

    new_history = (hero["history"] or []) + [
        {"weapon": weapon["name"], "price": neg["agreed_price"], "ratio": round(ratio, 2),
         "battle": None}
    ]
    repo.update_hero(neg["counterparty_id"], affinity=new_affinity,
                     history=new_history[-5:], held_weapon_id=neg["weapon_id"])
    repo.insert_day_event(
        pid, day=player_now["current_day"], phase=player_now["current_phase"], kind="sale",
        payload={"negotiation_id": neg_id, "weapon_id": neg["weapon_id"],
                 "hero_id": neg["counterparty_id"], "price": neg["agreed_price"],
                 "affinity_delta": aff_delta, "effort_recover": effort_recover},
    )


# --- Plan 2: 상인 협상 (매수) ---

async def step_buy(player: dict, merchant_id: int, price_offered: int, player_message: str,
                   neg_id: int | None,
                   selected_materials: list[dict[str, int]] | None = None,
                   select_weapon: bool = False) -> dict[str, Any]:
    pid = player["id"]
    from . import merchant as merchant_module

    m_row = _client_or_repo_get_merchant(merchant_id)

    if neg_id is None:
        # 첫 라운드 — selection으로 sub-bundle 구성
        full_materials = m_row["materials"]
        sel_map = {s["material_id"]: int(s["qty"]) for s in (selected_materials or [])
                   if int(s.get("qty", 0)) > 0}
        sub_materials = []
        for m in full_materials:
            q = sel_map.get(m["material_id"], 0)
            if q <= 0:
                continue
            if q > m["qty"]:
                raise ValueError(f"selected qty {q} exceeds available {m['qty']} for material {m['material_id']}")
            scaled = dict(m)
            scaled["qty"] = q
            scaled["asking_price"] = int(m["asking_price"] * q / m["qty"])
            sub_materials.append(scaled)
        sub_weapon = m_row.get("weapon") if select_weapon else None
        if not sub_materials and sub_weapon is None:
            raise ValueError("nothing selected")
        bundle = {"materials": sub_materials, "weapon": sub_weapon}

        player_data = repo.load_player(pid)
        neg = repo.insert_negotiation(pid, {
            "day": player_data["current_day"], "phase": player_data["current_phase"],
            "kind": "buy", "counterparty_id": merchant_id, "weapon_id": None,
            "materials": bundle, "rounds": [], "outcome": "open",
        })
        neg_id = neg["id"]
        prior_rounds: list[dict[str, Any]] = []
    else:
        neg = repo.get_negotiation(neg_id)
        prior_rounds = neg["rounds"]
        bundle = neg["materials"]

    base = merchant_module.bundle_market_price(bundle)
    player_now = repo.load_player(pid)
    player_gold = max(0, int(player_now.get("gold", 0)))
    # 매수 측: 플레이어가 보유 금화 이상으로는 제안 못 함 (hard cap).
    safe_price = clamp_price(price_offered, base)
    if safe_price > player_gold:
        safe_price = player_gold

    # 서버 강제: 상인(매도자) 카운터는 "최저 수용가"이므로 시간에 따라 단조 비증가.
    # 플레이어가 상인의 최저 카운터 이상을 제시하면 자동 수락.
    merch_prior_counters = [int(r["price"]) for r in prior_rounds
                             if r["role"] == "merchant" and r.get("price") is not None]
    min_merch_counter = min(merch_prior_counters) if merch_prior_counters else None

    if min_merch_counter is not None and safe_price >= min_merch_counter:
        llm = {
            "decision": "accept",
            "counter_price": None,
            "message": f"좋소, {safe_price} 골드에 드리지요. 말한 대로요.",
        }
    else:
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
        # 상인의 새 카운터는 이전 최저 카운터보다 높아질 수 없음
        if min_merch_counter is not None and counter > min_merch_counter:
            counter = min_merch_counter

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
        # 상인 reject 시 merchant 정리 (평판 변화는 §7.2: 즉시 거절 0).
        # phase advance는 호출측에서 처리.
        repo.update_merchant_today(neg["counterparty_id"], outcome="done")
    repo.update_negotiation(neg_id, **update)

    return {
        "negotiation_id": neg_id,
        "decision": decision,
        "counter_price": counter,
        "message": llm["message"],
    }


def finalize_buy(player: dict, neg_id: int) -> None:
    pid = player["id"]
    neg = repo.get_negotiation(neg_id)
    if neg["outcome"] != "accepted":
        raise ValueError("negotiation not accepted")
    player_now = repo.load_player(pid)
    if player_now["gold"] < neg["agreed_price"]:
        raise ValueError("insufficient gold")
    bundle = neg["materials"]

    for m in bundle["materials"]:
        repo.add_inventory(pid, m["material_id"], m["qty"])

    if bundle.get("weapon"):
        w = bundle["weapon"]
        # 상인 매입품은 materials_used가 빈 배열이라 market_price 계산 시 mat_value=0이 됨.
        # 매입가가 시세 base가 되도록 base_value를 역산해서 sentinel material entry로 저장.
        rarity_mult = 1 + w["rarity"] / 100
        sharp_mult = 1 + w["sharpness"] / 200
        target = w.get("asking_price", 100)
        base_value = max(1, int(target / max(rarity_mult * sharp_mult, 0.01)))
        repo.insert_weapon({
            "owner": "player",
            "name": w["name"], "type": w["type"], "rarity": w["rarity"],
            "sharpness": w["sharpness"], "attribute": w.get("attribute"),
            "skill": w["skill"], "str_req": w["str_req"], "mag_req": w["mag_req"],
            "enhancement_level": 0,
            "materials_used": [{"name": "상인 매입", "category": "merchant", "base_value": base_value}],
            "created_day": player_now["current_day"],
        })

    repo.update_player(
        pid,
        gold=player_now["gold"] - neg["agreed_price"],
        reputation=player_now["reputation"] + 1,
    )

    repo.update_merchant_today(neg["counterparty_id"], outcome="done")

    repo.insert_day_event(
        pid, day=player_now["current_day"], phase=player_now["current_phase"], kind="buy",
        payload={"price": neg["agreed_price"], "materials": bundle["materials"],
                 "weapon": bundle.get("weapon")},
    )


def player_accept_buy_counter(player: dict, neg_id: int) -> int:
    pid = player["id"]
    neg = repo.get_negotiation(neg_id)
    if neg["outcome"] != "open":
        raise ValueError(f"negotiation already {neg['outcome']}")
    merchant_rounds = [r for r in neg["rounds"] if r["role"] == "merchant" and r.get("price") is not None]
    if not merchant_rounds:
        raise ValueError("no merchant counter to accept")
    agreed = int(merchant_rounds[-1]["price"])
    player_now = repo.load_player(pid)
    if agreed > int(player_now.get("gold", 0)):
        raise ValueError(f"insufficient gold: need {agreed}, have {player_now.get('gold', 0)}")
    repo.update_negotiation(neg_id, outcome="accepted", agreed_price=agreed)
    return agreed


def player_reject_buy(player: dict, neg_id: int) -> None:
    pid = player["id"]
    neg = repo.get_negotiation(neg_id)
    if neg["outcome"] != "open":
        raise ValueError(f"negotiation already {neg['outcome']}")
    repo.update_negotiation(neg_id, outcome="rejected")
    player_now = repo.load_player(pid)
    rep_delta = -1 if neg["rounds"] else 0
    if rep_delta != 0:
        repo.insert_day_event(
            pid, day=player_now["current_day"], phase=player_now["current_phase"],
            kind="reject", payload={"by": "player_buy", "negotiation_id": neg_id, "rep_delta": rep_delta},
        )
    repo.update_player(
        pid,
        reputation=player_now["reputation"] + rep_delta,
    )
    repo.update_merchant_today(neg["counterparty_id"], outcome="done")


def _client_or_repo_get_merchant(merchant_id: int) -> dict[str, Any]:
    """merchant_today 행 로드 헬퍼."""
    from . import repo as _repo
    c = _repo._client()
    return c.table("merchants_today").select("*").eq("id", merchant_id).single().execute().data


# --- Plan 3: 강화 협상 ---

async def step_enhance(player: dict, hero_id: int, price_offered: int, player_message: str,
                       neg_id: int | None,
                       selected_materials: list[dict[str, int]] | None = None
                       ) -> dict[str, Any]:
    pid = player["id"]
    from . import enhancement as enh_mod
    hero = repo.get_hero(hero_id)
    weapon_id = hero.get("held_weapon_id")
    if not weapon_id:
        raise ValueError("hero has no held weapon")
    weapon = repo.get_weapon(weapon_id)
    hero_gold = max(0, int(hero.get("gold", 0)))
    affinity = int(hero.get("affinity", 0))

    if neg_id is None:
        inv = repo.load_inventory()
        inv_by_id = {row["material_id"]: row for row in inv}
        sub_materials = []
        for s in (selected_materials or []):
            mid = int(s["material_id"])
            qty = int(s.get("qty", 0))
            if qty <= 0:
                continue
            row = inv_by_id.get(mid)
            if not row or row["qty"] < qty:
                raise ValueError(f"insufficient material {mid}")
            sub_materials.append({"material_id": mid, "name": row["name"],
                                  "category": row["category"],
                                  "attribute": row["attribute"], "qty": qty})
        if not sub_materials:
            raise ValueError("no_materials_selected")

        base_estimate = enh_mod.bundle_estimate(weapon, sub_materials)
        player_data = repo.load_player(pid)
        neg = repo.insert_negotiation(pid, {
            "day": player_data["current_day"], "phase": player_data["current_phase"],
            "kind": "enhance", "counterparty_id": hero_id, "weapon_id": weapon_id,
            "materials": {"selected": sub_materials, "base_estimate": base_estimate},
            "rounds": [], "outcome": "open",
        })
        neg_id = neg["id"]
        prior_rounds: list[dict[str, Any]] = []
    else:
        neg = repo.get_negotiation(neg_id)
        prior_rounds = neg["rounds"]
        sub_materials = neg["materials"]["selected"]
        base_estimate = neg["materials"]["base_estimate"]

    safe_price = min(max(1, int(price_offered)), hero_gold)

    hero_prior_counters = [int(r["price"]) for r in prior_rounds
                            if r["role"] == "hero" and r.get("price") is not None]
    max_hero_counter = max(hero_prior_counters) if hero_prior_counters else None

    if max_hero_counter is not None and safe_price <= max_hero_counter:
        llm = {"decision": "accept", "counter_price": None,
               "message": f"좋소, {safe_price} 골드에 강화 부탁합시다."}
    else:
        llm = await complete_json(
            "negotiate_enhance", "enhance_accept",
            hero=hero, weapon=weapon, materials=sub_materials,
            base_estimate=base_estimate,
            affinity=affinity, nickname=hero.get("nickname"),
            prior_rounds=prior_rounds,
            player_message=player_message,
            price_offered=safe_price,
        )

    decision = llm["decision"]
    counter = llm.get("counter_price")
    if counter is not None:
        counter = max(1, int(counter))
        if max_hero_counter is not None and counter < max_hero_counter:
            counter = max_hero_counter
        counter = min(counter, hero_gold)
        if counter >= safe_price:
            decision = "accept"
            llm = {**llm, "decision": "accept", "counter_price": None,
                   "message": f"좋소, {safe_price} 골드에 강화 부탁합시다."}
            counter = None

    if decision == "accept" and safe_price > hero_gold:
        decision = "reject"
        llm = {**llm, "decision": "reject",
               "message": f"내가 가진 돈은 {hero_gold}골드뿐이라 그 가격엔 못 내겠소."}

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
        player_now = repo.load_player(pid)
        repo.insert_day_event(
            pid, day=player_now["current_day"], phase=player_now["current_phase"],
            kind="reject", payload={"by": "hero", "hero_id": hero_id, "rep_delta": -1,
                                     "context": "enhance"},
        )
        repo.update_player(
            pid,
            reputation=player_now["reputation"] - 1,
        )
    repo.update_negotiation(neg_id, **update)

    return {
        "negotiation_id": neg_id,
        "decision": decision,
        "counter_price": counter,
        "message": llm["message"],
    }


def finalize_enhance(player: dict, neg_id: int) -> None:
    pid = player["id"]
    from . import enhancement as enh_mod, affinity as aff_mod
    neg = repo.get_negotiation(neg_id)
    if neg["outcome"] != "accepted":
        raise ValueError("negotiation not accepted")
    if neg.get("finalized"):
        raise ValueError("already_finalized")
    repo.update_negotiation(neg_id, finalized=True)   # 멱등성 — 우선 마킹

    weapon = repo.get_weapon(neg["weapon_id"])
    sub_materials = neg["materials"]["selected"]
    base_estimate = neg["materials"]["base_estimate"]

    delta = enh_mod.roll_delta(sub_materials)
    new_weapon = enh_mod.apply_to_weapon(weapon, delta, sub_materials)
    repo.update_weapon(
        weapon["id"],
        sharpness=new_weapon["sharpness"],
        rarity=new_weapon["rarity"],
        enhancement_level=new_weapon["enhancement_level"],
        materials_used=new_weapon["materials_used"],
    )

    repo.deduct_materials(pid, {int(m["material_id"]): int(m["qty"]) for m in sub_materials})

    player_now = repo.load_player(pid)
    repo.update_player(
        pid,
        gold=player_now["gold"] + neg["agreed_price"],
        reputation=player_now["reputation"] + 1,
    )

    ratio = neg["agreed_price"] / max(base_estimate, 1)
    aff_delta = aff_mod.delta_from_ratio(ratio)
    hero = repo.get_hero(neg["counterparty_id"])
    new_history = (hero["history"] or []) + [
        {"action": "enhance", "weapon": weapon["name"], "price": neg["agreed_price"],
         "delta": delta, "ratio": round(ratio, 2)}
    ]
    repo.update_hero(neg["counterparty_id"],
                     affinity=aff_mod.clamp_affinity(int(hero.get("affinity", 0)) + aff_delta),
                     history=new_history[-5:])

    repo.insert_day_event(
        pid, day=player_now["current_day"], phase=player_now["current_phase"], kind="enhance",
        payload={"negotiation_id": neg_id, "weapon_id": weapon["id"],
                 "hero_id": neg["counterparty_id"],
                 "price": neg["agreed_price"], "delta": delta,
                 "affinity_delta": aff_delta},
    )


def player_accept_enhance_counter(player: dict, neg_id: int) -> int:
    neg = repo.get_negotiation(neg_id)
    if neg["outcome"] != "open":
        raise ValueError(f"negotiation already {neg['outcome']}")
    hero_rounds = [r for r in neg["rounds"]
                   if r["role"] == "hero" and r.get("price") is not None]
    if not hero_rounds:
        raise ValueError("no hero counter to accept")
    agreed = int(hero_rounds[-1]["price"])
    repo.update_negotiation(neg_id, outcome="accepted", agreed_price=agreed)
    return agreed


def player_reject_enhance(player: dict, neg_id: int) -> None:
    pid = player["id"]
    neg = repo.get_negotiation(neg_id)
    if neg["outcome"] != "open":
        raise ValueError(f"negotiation already {neg['outcome']}")
    repo.update_negotiation(neg_id, outcome="rejected")
    player_now = repo.load_player(pid)
    repo.insert_day_event(
        pid, day=player_now["current_day"], phase=player_now["current_phase"],
        kind="reject", payload={"by": "player", "negotiation_id": neg_id, "rep_delta": -1,
                                 "context": "enhance"},
    )
    repo.update_player(
        pid,
        reputation=player_now["reputation"] - 1,
    )
