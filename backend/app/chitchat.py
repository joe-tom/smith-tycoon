"""chitchat 서비스 — LLM 한 문단 → heroes.lore 누적."""
from __future__ import annotations
from typing import Any
from . import repo
from .llm.client import complete_json


async def converse(player: dict[str, Any], hero: dict[str, Any],
                    player_message: str = "") -> dict[str, Any]:
    if int(hero.get("affinity", 0)) < 10:
        raise ValueError("affinity_too_low")
    recent_lore = (hero.get("lore") or [])[-3:]
    llm = await complete_json(
        "chitchat", "chitchat",
        hero=hero, recent_lore=recent_lore,
        player_message=player_message,
        recent_history=(hero.get("history") or [])[-3:],
    )
    text = llm.get("lore_text", "...")
    entry = {"day": player["current_day"], "text": text}
    repo.append_hero_lore(hero["id"], entry, cap=20)
    return {"lore_text": text, "entry": entry}
