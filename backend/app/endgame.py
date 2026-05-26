"""엔딩 판정 로직 + 적용 함수."""
from __future__ import annotations
from typing import Any
from . import repo


MID_BOSS_IDS: set[str] = {
    "belphegor", "beelzebub", "mammon", "leviathan",
    "asmodeus", "satan", "lucifer",
}


ENDINGS: list[dict[str, Any]] = [
    {"id": "surt_killed", "title": "🏆 마왕 토벌", "won": True,
     "flavor": "수르트의 화염이 사그라들었다. 7대 죄악도 함께 무너졌고, 인간 세계는 다시 빛을 찾았다. 당신의 망치는 전설이 되었다."},
    {"id": "lonely_demon", "title": "🌒 외로운 마왕", "won": True,
     "flavor": "7대 죄악은 모두 무너졌지만 수르트는 끝내 모습을 드러내지 않았다. 100일의 항전은 끝나고, 세상은 마왕 하나만 남긴 채 평온해졌다."},
    {"id": "forge_burns", "title": "🔥 다 쓰러져가는 대장간은 불타야 해", "won": False,
     "flavor": "100일이 지났지만 수르트는 건재하다. 절반의 죄악을 베어낸 당신의 무기들은 영광스럽지만, 정작 마왕은 닿지 못한 곳에 있다. 대장간 문을 닫을 시간이다."},
    {"id": "retirement", "title": "💤 정년 퇴직", "won": False,
     "flavor": "100일 동안 망치질만 했다. 단 한 명의 죄악도 무너뜨리지 못했고 수르트는 더더욱. 당신은 평범한 대장장이로 늙어간다."},
    {"id": "youth_blood", "title": "💀 이기지도 못할 거면서 왜 싸웠어?", "won": False,
     "flavor": "200명의 용사가 당신 손에서 무기를 받았고, 200명이 돌아오지 못했다. 마을 입구마다 곡소리가 그치지 않는다."},
    {"id": "weapons_broken", "title": "⚔️ 우리나라 청년들은 너 때문에 죽은 거야", "won": False,
     "flavor": "당신이 만든 무기 200개가 마왕군 앞에서 부러졌다. 살아 돌아온 용사들의 손에는 부러진 자루만 남았고, 그들의 분노는 당신을 향한다."},
]


def detect_post_battle(player: dict[str, Any], defeated_boss_ids: set[str]) -> str | None:
    """전투 직후 검사. 우선순위: surt > heroes_died ≥200 > weapons_destroyed ≥200."""
    if "surt" in defeated_boss_ids:
        return "surt_killed"
    if int(player.get("heroes_died_total", 0)) >= 200:
        return "youth_blood"
    if int(player.get("weapons_destroyed_total", 0)) >= 200:
        return "weapons_broken"
    return None


def detect_day_100(player: dict[str, Any], defeated_boss_ids: set[str]) -> str | None:
    """day 100 도달 시 검사. surt 이미 처치돼 있으면 None (post_battle 경로로 끝남)."""
    if "surt" in defeated_boss_ids:
        return None
    mid_dead = len(defeated_boss_ids & MID_BOSS_IDS)
    if mid_dead == 7:
        return "lonely_demon"
    if mid_dead >= 1:
        return "forge_burns"
    return "retirement"


def apply_ending(player_id: int, ending_id: str) -> None:
    """player row에 ending_kind 기록 + phase='game_over' 전이."""
    repo.update_player(player_id, ending_kind=ending_id, current_phase="game_over")
