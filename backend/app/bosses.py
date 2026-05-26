"""7대 죄악 중간보스 + 최종보스 수르트 정의."""
from __future__ import annotations
from typing import Any

# 약 → 강 순서 (등장·선택 순서로 사용)
MID_BOSSES: list[dict[str, Any]] = [
    {"boss_id": "belphegor", "name": "벨페고르",     "sin": "나태", "attribute": "흙",   "difficulty": 70},
    {"boss_id": "beelzebub", "name": "벨제붑",       "sin": "폭식", "attribute": "바람", "difficulty": 75},
    {"boss_id": "mammon",    "name": "맘몬",         "sin": "탐욕", "attribute": "금",   "difficulty": 78},
    {"boss_id": "leviathan", "name": "레비아탄",     "sin": "질투", "attribute": "물",   "difficulty": 82},
    {"boss_id": "asmodeus",  "name": "아스모데우스", "sin": "색욕", "attribute": "불",   "difficulty": 85},
    {"boss_id": "satan",     "name": "사탄",         "sin": "분노", "attribute": "불",   "difficulty": 90},
    {"boss_id": "lucifer",   "name": "루시퍼",       "sin": "교만", "attribute": "금",   "difficulty": 95},
]

FINAL_BOSS: dict[str, Any] = {
    "boss_id": "surt", "name": "수르트", "sin": None, "attribute": "불", "difficulty": 110,
}


def weakest_alive(defeated_ids: set[str]) -> dict[str, Any] | None:
    """MID_BOSSES 중 defeated_ids에 없는 첫 번째 (가장 약한) 보스."""
    for b in MID_BOSSES:
        if b["boss_id"] not in defeated_ids:
            return b
    return None


def find_boss_by_id(boss_id: str) -> dict[str, Any] | None:
    for b in MID_BOSSES:
        if b["boss_id"] == boss_id:
            return b
    if FINAL_BOSS["boss_id"] == boss_id:
        return FINAL_BOSS
    return None


def is_boss_demon(demon: dict[str, Any]) -> bool:
    return bool(demon.get("is_boss"))
