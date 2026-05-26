from __future__ import annotations
import random
from typing import Any
from . import repo, state_machine, hero_registry, nickname as nickname_mod, affinity as affinity_mod
from .llm.client import complete_json
from .bosses import FINAL_BOSS, weakest_alive

# 5행 상성 사이클: 금 → 바람 → 흙 → 물 → 불 → 금 (각 원소가 다음을 억제)
CYCLE_NEXT = {"금": "바람", "바람": "흙", "흙": "물", "물": "불", "불": "금"}


def attribute_bonus(weapon_attr: str | None, demon_attr: str | None) -> float:
    """무기가 적 속성을 억제하면 1.3, 역이면 0.7, 그 외 1.0."""
    if not weapon_attr or not demon_attr:
        return 1.0
    if CYCLE_NEXT.get(weapon_attr) == demon_attr:
        return 1.3
    if CYCLE_NEXT.get(demon_attr) == weapon_attr:
        return 0.7
    return 1.0


DEMONS: list[dict[str, Any]] = [
    # Tier 1 — 잡몹 (난이도 1–15)
    {"type": "고블린",         "attribute": "흙",   "difficulty": (1, 12)},
    {"type": "지옥개",         "attribute": "불",   "difficulty": (2, 14)},
    {"type": "작은 영혼",      "attribute": "물",   "difficulty": (1, 10)},
    {"type": "임프",           "attribute": "불",   "difficulty": (3, 15)},
    {"type": "슬라임",         "attribute": "물",   "difficulty": (1, 8)},
    {"type": "박쥐",           "attribute": "바람", "difficulty": (1, 9)},
    {"type": "좀비",           "attribute": "흙",   "difficulty": (4, 15)},
    {"type": "스켈레톤",       "attribute": "금",   "difficulty": (3, 14)},
    {"type": "진흙두꺼비",     "attribute": "흙",   "difficulty": (2, 12)},
    {"type": "가시쥐",         "attribute": "흙",   "difficulty": (1, 8)},
    {"type": "부랑광대",       "attribute": "바람", "difficulty": (3, 13)},
    {"type": "좀나방",         "attribute": "바람", "difficulty": (1, 10)},
    {"type": "묘지까마귀",     "attribute": "바람", "difficulty": (2, 11)},
    {"type": "그렘린",         "attribute": "금",   "difficulty": (4, 15)},
    {"type": "광부거미",       "attribute": "흙",   "difficulty": (3, 14)},

    # Tier 2 — 중하급 (난이도 10–30)
    {"type": "늑대인간",       "attribute": "바람", "difficulty": (12, 28)},
    {"type": "미노타우로스 아이","attribute": "흙",   "difficulty": (15, 30)},
    {"type": "화염도마뱀",     "attribute": "불",   "difficulty": (10, 25)},
    {"type": "얼음 정령",      "attribute": "물",   "difficulty": (12, 28)},
    {"type": "강철 거미",      "attribute": "금",   "difficulty": (14, 30)},
    {"type": "들개왕",         "attribute": "바람", "difficulty": (10, 24)},
    {"type": "흑마법사 견습",  "attribute": "불",   "difficulty": (12, 27)},
    {"type": "부패한 기사",    "attribute": "금",   "difficulty": (15, 30)},
    {"type": "진흙 골렘",      "attribute": "흙",   "difficulty": (13, 28)},
    {"type": "늪지 헛것",      "attribute": "물",   "difficulty": (11, 25)},
    {"type": "산울림",         "attribute": "바람", "difficulty": (10, 22)},
    {"type": "인큐버스",       "attribute": "불",   "difficulty": (14, 29)},

    # Tier 3 — 중급 (난이도 25–50)
    {"type": "서큐버스",       "attribute": "불",   "difficulty": (28, 48)},
    {"type": "케르베로스 새끼","attribute": "불",   "difficulty": (30, 50)},
    {"type": "가고일",         "attribute": "흙",   "difficulty": (32, 50)},
    {"type": "데몬 졸병",      "attribute": "불",   "difficulty": (28, 46)},
    {"type": "폴터가이스트",   "attribute": "바람", "difficulty": (25, 45)},
    {"type": "와이번 새끼",    "attribute": "바람", "difficulty": (30, 48)},
    {"type": "거대 두꺼비",    "attribute": "물",   "difficulty": (27, 44)},
    {"type": "강철 골렘",      "attribute": "금",   "difficulty": (33, 50)},
    {"type": "파충류 마법사",  "attribute": "물",   "difficulty": (28, 47)},
    {"type": "흡혈귀 시종",    "attribute": "금",   "difficulty": (30, 48)},

    # Tier 4 — 상급 (난이도 45–70)
    {"type": "와이번",         "attribute": "바람", "difficulty": (50, 68)},
    {"type": "케르베로스",     "attribute": "불",   "difficulty": (52, 70)},
    {"type": "진짜 데몬",      "attribute": "불",   "difficulty": (48, 68)},
    {"type": "황금 골렘",      "attribute": "금",   "difficulty": (55, 70)},
    {"type": "빙룡 새끼",      "attribute": "물",   "difficulty": (50, 68)},
    {"type": "흑마법사",       "attribute": "금",   "difficulty": (48, 66)},
    {"type": "흡혈귀",         "attribute": "금",   "difficulty": (52, 70)},
    {"type": "미노타우로스",   "attribute": "흙",   "difficulty": (45, 65)},

    # Tier 5 — 거인급 (난이도 65–95)
    {"type": "빙룡",           "attribute": "물",   "difficulty": (70, 90)},
    {"type": "화염 거인",      "attribute": "불",   "difficulty": (72, 92)},
    {"type": "대지 거인",      "attribute": "흙",   "difficulty": (70, 90)},
    {"type": "폭풍 거인",      "attribute": "바람", "difficulty": (75, 95)},
    {"type": "강철 골렘왕",    "attribute": "금",   "difficulty": (78, 95)},
]

DIFFICULTY_BY_DAY = {1: (1, 10), 2: (3, 15), 3: (8, 22), 4: (14, 30), 5: (20, 40)}


def difficulty_range(day: int) -> tuple[int, int]:
    """100일 난이도 곡선.

    Day 1–5는 DIFFICULTY_BY_DAY의 MVP 튜닝 곡선을 그대로 사용.
    Day 6–99는 (20,40) → (75,95) 선형 보간.
    Day 100+은 (75, 95)로 캡.
    """
    if day <= 0:
        return (1, 10)
    if day in DIFFICULTY_BY_DAY:
        return DIFFICULTY_BY_DAY[day]
    if day >= 100:
        return (75, 95)
    t = (day - 5) / 95.0
    lo = int(round(20 + t * 55))
    hi = int(round(40 + t * 55))
    return (lo, hi)


def boss_spawn_chance(day: int) -> float:
    """전투당 보스 스폰 확률."""
    if day < 40: return 0.0
    if day < 60: return 0.05
    if day < 80: return 0.10
    if day < 90: return 0.25
    return 1.0


def roll_demon(day: int = 1, defeated_boss_ids: set[str] | None = None,
               seed: int | None = None) -> dict[str, Any]:
    """day의 난이도 범위와 보스 스폰 규칙을 적용해 적 1마리를 반환."""
    rng = random.Random(seed)
    defeated = defeated_boss_ids or set()
    surt_dead = "surt" in defeated
    alive_mid = weakest_alive(defeated)

    def _boss_to_demon(b: dict[str, Any]) -> dict[str, Any]:
        return {"type": b["name"], "attribute": b["attribute"],
                "difficulty": b["difficulty"],
                "is_boss": True, "boss_id": b["boss_id"], "sin": b.get("sin")}

    # day 100+ → 수르트 무조건 (살아있을 때)
    if day >= 100 and not surt_dead:
        return _boss_to_demon(FINAL_BOSS)

    # 모든 mid-boss 처치 → 수르트 조기 등장
    if alive_mid is None and not surt_dead:
        return _boss_to_demon(FINAL_BOSS)

    # 확률적 mid-boss
    if alive_mid is not None and rng.random() < boss_spawn_chance(day):
        return _boss_to_demon(alive_mid)

    # 일반 적
    day_lo, day_hi = difficulty_range(day)
    eligible = [d for d in DEMONS
                if d["difficulty"][0] <= day_hi and d["difficulty"][1] >= day_lo]
    pool = eligible or DEMONS
    base = rng.choice(pool)
    d_lo = max(base["difficulty"][0], day_lo)
    d_hi = min(base["difficulty"][1], day_hi)
    if d_lo > d_hi:
        d_lo, d_hi = day_lo, day_hi
    return {"type": base["type"], "attribute": base["attribute"],
            "difficulty": rng.randint(d_lo, d_hi)}


def apply_outcomes(outcomes: dict[str, str]) -> dict[str, int]:
    rep = 0
    if outcomes["hero"] == "survived":
        rep += 1
    elif outcomes["hero"] == "died":
        rep -= 2
    if outcomes["weapon"] == "destroyed":
        rep -= 1
    if outcomes["demon"] == "killed":
        rep += 1
    return {"reputation": rep}


def hero_power(hero: dict[str, Any], weapon: dict[str, Any] | None) -> float:
    """용사의 실제 전투력."""
    p = float(hero.get("str", 0) + hero.get("mag", 0))
    if weapon:
        p += weapon.get("sharpness", 0) / 2.0
        p += weapon.get("rarity", 0) / 5.0
    else:
        p *= 0.7   # 맨손 패널티
    return max(1.0, p)


def demon_threat(demon: dict[str, Any]) -> float:
    """적의 위협력. 난이도 단위를 hero power 스케일로 변환."""
    return max(1.0, float(demon["difficulty"]) * 3.0)


def decide_outcomes(hero: dict[str, Any], weapon: dict[str, Any] | None,
                    demon: dict[str, Any], seed: int | None = None) -> dict[str, str]:
    """전투 결과 코드를 결정 — power/threat 비율 + 노이즈 기반."""
    rng = random.Random(seed)
    power = hero_power(hero, weapon)
    weapon_attr = weapon.get("attribute") if weapon else None
    power *= attribute_bonus(weapon_attr, demon.get("attribute"))
    threat = demon_threat(demon)
    ratio = (power / threat) * rng.uniform(0.75, 1.25)

    if ratio >= 2.0:
        hero_r = "survived" if rng.random() > 0.05 else "injured"
        demon_r = "killed"
    elif ratio >= 1.2:
        hero_r = rng.choices(["survived", "injured"], weights=[7, 3])[0]
        demon_r = rng.choices(["killed", "fled"], weights=[8, 2])[0]
    elif ratio >= 0.8:
        hero_r = rng.choices(["survived", "injured", "died"], weights=[3, 5, 2])[0]
        demon_r = rng.choices(["killed", "fled", "survived"], weights=[4, 4, 2])[0]
    elif ratio >= 0.5:
        hero_r = rng.choices(["injured", "died"], weights=[3, 7])[0]
        demon_r = rng.choices(["fled", "survived"], weights=[3, 7])[0]
    else:
        hero_r = "died"
        demon_r = "survived"

    if weapon is None:
        weapon_r = "none"
    elif hero_r == "died":
        weapon_r = "destroyed"
    else:
        sharp = weapon.get("sharpness", 30)
        # 예리도 낮을수록·열세일수록 파괴 확률 ↑
        destroy_p = max(0.05, 0.5 - sharp / 200) * (1.0 if ratio >= 1.0 else 1.5)
        weapon_r = "destroyed" if rng.random() < destroy_p else "preserved"

    return {"hero": hero_r, "weapon": weapon_r, "demon": demon_r}


async def run_battle(player: dict, hero_id: int, weapon_id: int | None) -> dict[str, Any]:
    pid = player["id"]
    hero = repo.get_hero(hero_id)
    weapon = repo.get_weapon(weapon_id) if weapon_id else None
    player = repo.load_player(pid)
    defeated_boss_ids = repo.list_defeated_boss_ids(pid)
    demon = roll_demon(day=player["current_day"], defeated_boss_ids=defeated_boss_ids)

    # 결과 코드는 서버가 결정. LLM은 서술만.
    outcomes = decide_outcomes(hero, weapon, demon)
    llm = await complete_json("battle", "battle_basic",
                              hero=hero, weapon=weapon, demon=demon,
                              outcomes=outcomes,
                              hero_power=int(hero_power(hero, weapon)),
                              demon_threat=int(demon_threat(demon)))
    # LLM 응답에 outcomes가 같이 와도 무시 — 서버 결정 사용
    script = llm.get("script", "전투가 끝났다.")
    delta = apply_outcomes(outcomes)
    if outcomes["demon"] == "killed" and demon.get("is_boss"):
        delta["reputation"] += 10

    repo.update_player(pid, reputation=player["reputation"] + delta["reputation"],
                       current_phase=state_machine.next_phase(player["current_phase"]))

    # 전투 결과별로 status·return_day 갱신.
    # 'injured'는 일정상 'survived'와 동일 처리 (귀환 3일 내).
    sr_outcome = outcomes["hero"] if outcomes["hero"] in ("survived", "fled", "died") else "survived"
    fields = hero_registry.schedule_return(sr_outcome, current_day=player["current_day"])
    # 무기 파괴 시 held_weapon_id 비움 + affinity -5
    if outcomes.get("weapon") == "destroyed":
        fields["held_weapon_id"] = None
        current_aff = int(hero.get("affinity", 0))
        fields["affinity"] = affinity_mod.clamp_affinity(current_aff - 5)
    repo.update_hero(hero_id, **fields)

    # 별명 부여 트리거
    if outcomes.get("hero") == "survived" and outcomes.get("demon") == "killed":
        consecutive = repo.count_consecutive_survives(pid, hero_id) + 1  # 이번 전투 포함
        refreshed_hero = repo.get_hero(hero_id)
        if nickname_mod.should_award(refreshed_hero, consecutive):
            recent_demons = [demon["type"]]
            picked = await nickname_mod.award(refreshed_hero, consecutive, recent_demons)
            if picked:
                repo.update_hero(hero_id, nickname=picked)
                repo.insert_day_event(
                    pid, day=player["current_day"], phase=player["current_phase"],
                    kind="nickname", payload={"hero_id": hero_id, "nickname": picked},
                )

    battle_row = repo.insert_battle(pid, {
        "day": player["current_day"],
        "hero_id": hero_id,
        "weapon_id": weapon_id,
        "demon": demon,
        "script_text": script,
        "outcomes": outcomes,
    })

    repo.insert_day_event(
        pid, day=player["current_day"],
        phase=player["current_phase"],
        kind="battle",
        payload={"battle_id": battle_row["id"], "outcomes": outcomes,
                 "hero_id": hero_id, "demon": demon, "rep_delta": delta["reputation"]},
    )

    if outcomes["demon"] == "killed" and demon.get("is_boss"):
        repo.insert_day_event(
            pid, day=player["current_day"], phase=player["current_phase"],
            kind="boss_kill",
            payload={"boss_id": demon["boss_id"], "boss_name": demon["type"],
                     "sin": demon.get("sin"), "battle_id": battle_row["id"]},
        )
        if demon["boss_id"] == "surt":
            repo.insert_day_event(
                pid, day=player["current_day"], phase=player["current_phase"],
                kind="surt_kill",
                payload={"boss_id": "surt", "boss_name": demon["type"],
                         "battle_id": battle_row["id"], "final": True},
            )

    return {"script": script, "outcomes": outcomes, "demon": demon,
            "next_phase": repo.load_player(pid)["current_phase"]}
