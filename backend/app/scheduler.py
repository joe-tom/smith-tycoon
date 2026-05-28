"""하루 방문자 스케줄 생성. 결정성 시드로 재현 가능."""
from __future__ import annotations
import random
from typing import Any

REP_TIERS: list[tuple[int, tuple[int, int]]] = [
    (10, (3, 3)),
    (20, (3, 5)),
    (40, (5, 7)),
    (60, (8, 10)),
    (10**9, (10, 10)),
]


def schedule_seed(player_id: int, day: int) -> int:
    return (player_id * 1_000_003 + day * 31 + 11) & 0xFFFFFFFF


def hero_slot_count(reputation: int, seed: int) -> int:
    for upper, (lo, hi) in REP_TIERS:
        if reputation <= upper:
            if lo == hi:
                return lo
            return random.Random(seed).randint(lo, hi)
    return 10


def resolve_day_for(outcome: str, depart_day: int, seed: int) -> int:
    """outcome: 'survive'|'injure'|'die'. seed 별로 범위 내 결정성 선택."""
    rng = random.Random(seed)
    if outcome == "survive":
        return depart_day + rng.randint(2, 3)
    if outcome == "injure":
        return depart_day + rng.randint(5, 7)
    if outcome == "die":
        return depart_day + rng.randint(1, 2)
    raise ValueError(f"unknown outcome: {outcome}")


def build_schedule(
    player_id: int,
    day: int,
    reputation: int,
    pending_revisits: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """그 날 방문자 큐 생성.

    pending_revisits: [{id, hero_id, kind}] — 오늘 resolve될 revisit_* 항목 (id 오름차순).
    신규 용사 hero_id는 placeholder(None) — 호출측에서 채운다.
    """
    seed = schedule_seed(player_id, day)
    rng = random.Random(seed)

    n_hero_slots = hero_slot_count(reputation, seed=seed ^ 0x5A5A5A5A)
    taken_revisits = pending_revisits[:n_hero_slots]
    n_new = n_hero_slots - len(taken_revisits)

    entries: list[dict[str, Any]] = []
    for r in taken_revisits:
        entries.append({
            "kind": "returning_hero",
            "hero_id": r["hero_id"],
            "outcome_id": r["id"],
        })
    for _ in range(n_new):
        entries.append({"kind": "new_hero", "hero_id": None})

    merchant_pos = rng.randrange(len(entries) + 1)
    entries.insert(merchant_pos, {"kind": "merchant"})
    return entries


def postponed_outcome_ids(
    pending_revisits: list[dict[str, Any]],
    taken: list[dict[str, Any]],
) -> list[int]:
    """슬롯에 못 들어간 outcome_id 목록 (resolve_day += 1 대상)."""
    taken_ids = {t["outcome_id"] for t in taken if t.get("kind") == "returning_hero"}
    return [r["id"] for r in pending_revisits if r["id"] not in taken_ids]
