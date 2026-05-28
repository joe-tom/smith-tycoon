"""용사 출정 시점에 outcome을 결정하고 pending_outcomes에 박는다."""
from __future__ import annotations
from typing import Any

from . import combat, repo, scheduler


def _outcome_seed(player_id: int, depart_day: int, hero_id: int) -> int:
    return (player_id * 1_000_003 + depart_day * 31 + hero_id * 7 + 13) & 0xFFFFFFFF


def _kind_for(hero_status: str) -> str:
    if hero_status == "died":
        return "death_mail"
    if hero_status == "injured":
        return "revisit_injure"
    return "revisit_survive"


def _outcome_label(hero_status: str) -> str:
    if hero_status == "died":
        return "die"
    if hero_status == "injured":
        return "injure"
    return "survive"


def dispatch_hero(
    player: dict[str, Any],
    hero: dict[str, Any],
    weapon: dict[str, Any] | None,
    demon: dict[str, Any],
) -> dict[str, Any]:
    """협상 수락 직후 호출. outcome 결정 → pending_outcomes insert → weapon 삭제."""
    depart_day = player["current_day"]
    seed = _outcome_seed(player["id"], depart_day, hero["id"])

    outcome = combat.decide_outcomes(hero, weapon, demon, seed=seed)
    label = _outcome_label(outcome["hero"])
    resolve_day = scheduler.resolve_day_for(label, depart_day, seed=seed + 7)
    kind = _kind_for(outcome["hero"])

    weapon_snapshot = dict(weapon) if weapon else {}

    saved = repo.insert_pending_outcome({
        "player_id": player["id"],
        "hero_id": hero["id"],
        "depart_day": depart_day,
        "resolve_day": resolve_day,
        "kind": kind,
        "outcome_json": outcome,
        "weapon_snapshot": weapon_snapshot,
    })

    if weapon:
        repo.delete_weapon(weapon["id"])

    # 출정 기간 동안 ready 풀에서 제외 (resolve_day 전까진 가게에 안 들름)
    repo.update_hero(hero["id"], return_day=resolve_day)

    return {
        "outcome_id": saved["id"],
        "outcome": outcome,
        "resolve_day": resolve_day,
        "kind": kind,
    }
