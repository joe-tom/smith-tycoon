from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from .. import repo, state_machine, endgame
from ..auth import current_player
from ..missions import module_for
from ..api.visitor import advance as advance_visitor_phase

router = APIRouter(tags=["mission"])


class ActionReq(BaseModel):
    action: str  # "pay" | "ack" | "skip"


def _current_mission(player: dict) -> dict:
    try:
        state_machine.assert_phase(player["current_phase"], "visitor")
    except state_machine.PhaseError:
        raise HTTPException(400, detail={"error": "wrong_phase"})
    sched = player.get("day_schedule") or []
    idx = player.get("current_visitor_index", 0)
    if idx >= len(sched):
        raise HTTPException(409, "no current visitor")
    slot = sched[idx]
    if slot["kind"] != "mission_npc":
        raise HTTPException(409, "current slot is not a mission_npc")
    mission = repo.get_mission(int(slot["mission_id"]))
    if not mission:
        raise HTTPException(404, "mission not found")
    return mission


@router.post("/visitor/current/mission_action")
def post_mission_action(req: ActionReq, player: dict = Depends(current_player)):
    mission = _current_mission(player)
    mod = module_for(mission["kind"])
    try:
        result = mod.on_action(player, mission, req.action)
    except ValueError as e:
        raise HTTPException(400, detail={"error": "invalid_action", "message": str(e)})
    ending = result.get("ending_kind")
    if ending:
        endgame.apply_ending(player["id"], ending)
        return {"ok": True, "ending": ending}
    player = repo.load_player(player["id"])
    if player["current_phase"] == "visitor":
        advance_visitor_phase(player)
    return {"ok": True, "current_phase": player["current_phase"]}
