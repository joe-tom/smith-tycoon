from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from .. import repo, state_machine
from ..auth import current_player

router = APIRouter(prefix="/visitor", tags=["visitor"])


def _current_slot(player: dict) -> dict:
    try:
        state_machine.assert_phase(player["current_phase"], "visitor")
    except state_machine.PhaseError as e:
        raise HTTPException(400, detail={"error": "wrong_phase",
                                         "current_phase": player["current_phase"]}) from e
    schedule = player.get("day_schedule") or []
    idx = player.get("current_visitor_index", 0)
    if idx >= len(schedule):
        raise HTTPException(409, "no current visitor (schedule exhausted)")
    return schedule[idx]


def advance(player: dict) -> dict:
    """슬롯 advance + 새 phase 반환. 라우터 + negotiate accept 둘 다 사용."""
    state_machine.advance_visitor(player)
    repo.update_player(
        player["id"],
        current_phase=player["current_phase"],
        current_visitor_index=player.get("current_visitor_index", 0),
    )
    return {"current_phase": player["current_phase"],
            "current_visitor_index": player.get("current_visitor_index", 0)}


@router.post("/current/return")
def finish_returning_hero(player: dict = Depends(current_player)):
    slot = _current_slot(player)
    if slot["kind"] != "returning_hero":
        raise HTTPException(409, "current slot is not returning_hero")
    repo.mark_pending_consumed(slot["outcome_id"])
    return {"ok": True, **advance(player)}


@router.post("/current/skip")
def skip_visitor(player: dict = Depends(current_player)):
    """협상 거절·상인 패스 등 일반 advance. mission_npc 슬롯은 on_action skip 거침."""
    slot = _current_slot(player)
    if slot["kind"] == "mission_npc":
        from .. import endgame
        from ..missions import module_for
        mission = repo.get_mission(int(slot["mission_id"]))
        if mission:
            mod = module_for(mission["kind"])
            try:
                result = mod.on_action(player, mission, "skip")
            except ValueError as e:
                raise HTTPException(400, detail={"error": "invalid_action",
                                                 "message": str(e)})
            ending = result.get("ending_kind")
            if ending:
                endgame.apply_ending(player["id"], ending)
                return {"ok": True, "ending": ending}
    return {"ok": True, **advance(player)}
