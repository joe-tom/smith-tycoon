"""forge_open 진입 직후 호출되어 그 날 스케줄과 우편을 결정한다."""
from __future__ import annotations
from typing import Any

from . import hero_registry, repo, scheduler


def prepare_day(player: dict[str, Any]) -> dict[str, Any]:
    """player 행 in-place + DB 갱신: day_schedule, current_visitor_index 세팅.

    Returns: {"schedule": [...], "death_mails": [...]}
    """
    day = player["current_day"]
    player_id = player["id"]

    pending = repo.list_pending_to_resolve(player_id, day)
    death_mails = [p for p in pending if p["kind"] == "death_mail"]
    revisits = [p for p in pending if p["kind"].startswith("revisit_")]
    revisits.sort(key=lambda p: p["id"])

    revisit_entries = [
        {"id": r["id"], "hero_id": r["hero_id"], "kind": r["kind"]} for r in revisits
    ]

    schedule = scheduler.build_schedule(
        player_id=player_id,
        day=day,
        reputation=player.get("reputation", 0),
        pending_revisits=revisit_entries,
    )

    n_new = sum(1 for s in schedule if s["kind"] == "new_hero")
    if n_new > 0:
        heroes = hero_registry.heroes_for_today(player_id, day, count=n_new)
        idx = 0
        for s in schedule:
            if s["kind"] == "new_hero":
                s["hero_id"] = heroes[idx]["id"]
                idx += 1

    taken_outcome_ids = {s["outcome_id"] for s in schedule if s["kind"] == "returning_hero"}
    for r in revisits:
        if r["id"] not in taken_outcome_ids:
            repo.update_pending_resolve_day(r["id"], day + 1)

    repo.update_player(
        player_id,
        day_schedule=schedule,
        current_visitor_index=0,
    )
    player["day_schedule"] = schedule
    player["current_visitor_index"] = 0

    return {"schedule": schedule, "death_mails": death_mails}
