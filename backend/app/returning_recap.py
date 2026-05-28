"""재방문 용사의 회고 LLM narration. outcome_json에 캐시."""
from __future__ import annotations
from typing import Any

from . import repo
from .llm.client import complete_json


async def get_or_generate(player: dict[str, Any], pending: dict[str, Any],
                           hero: dict[str, Any]) -> str:
    outcome = pending.get("outcome_json") or {}
    if outcome.get("recap"):
        return outcome["recap"]
    llm = await complete_json(
        "returning_recap", "returning_recap",
        hero=hero, weapon=pending.get("weapon_snapshot") or {},
        depart_day=pending.get("depart_day"),
        today=player["current_day"],
        outcome=outcome,
    )
    recap = llm.get("recap", "...")
    new_outcome = {**outcome, "recap": recap}
    repo.update_pending_outcome(pending["id"], outcome_json=new_outcome)
    pending["outcome_json"] = new_outcome
    return recap
