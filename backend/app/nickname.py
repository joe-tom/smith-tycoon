"""별명 부여 — 조건 체크 + LLM 호출."""
from __future__ import annotations
import random
from typing import Any
from .llm.client import complete_json


def should_award(hero: dict[str, Any], consecutive_survives: int) -> bool:
    """별명 부여 자격 — affinity ≥20, nickname None, 연속 생존 ≥2."""
    if hero.get("nickname"):
        return False
    if int(hero.get("affinity", 0)) < 20:
        return False
    if consecutive_survives < 2:
        return False
    return True


async def award(hero: dict[str, Any], consecutive: int, recent_demons: list[str],
                seed: int | None = None) -> str | None:
    """LLM에 별명 3개 후보 요청 → 랜덤 1개 픽. 실패 시 None 반환."""
    try:
        llm = await complete_json(
            "nickname", "nickname_candidates",
            hero=hero, consecutive=consecutive, recent_demons=recent_demons,
        )
        candidates = llm.get("nicknames") or []
        if not candidates:
            return None
        rng = random.Random(seed)
        return rng.choice(candidates)
    except Exception:
        return None
