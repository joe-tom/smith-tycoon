"""미션 시스템 — 모듈 레지스트리.

각 미션 모듈은 다음 함수를 노출한다:
- plan(player, day) -> list[dict]
- evaluate(player, day, mission) -> tuple[str, str | None]
- slot_for(mission) -> dict
- on_action(player, mission, action) -> dict
"""
from . import tax, league_chief

MODULES = {
    "tax": tax,
    "league_chief": league_chief,
}


def module_for(kind: str):
    if kind not in MODULES:
        raise ValueError(f"unknown mission kind: {kind}")
    return MODULES[kind]
