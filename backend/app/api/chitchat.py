from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from .. import repo, state_machine, chitchat
from ..auth import current_player

router = APIRouter(tags=["chitchat"])


class ChitchatReq(BaseModel):
    player_message: str = ""


@router.post("/visitor/current/chitchat")
async def post_chitchat(req: ChitchatReq, player: dict = Depends(current_player)):
    try:
        state_machine.assert_phase(player["current_phase"], "visitor")
    except state_machine.PhaseError:
        raise HTTPException(400, detail={"error": "wrong_phase"})
    sched = player.get("day_schedule") or []
    idx = player.get("current_visitor_index", 0)
    if idx >= len(sched):
        raise HTTPException(409, "no current visitor")
    slot = sched[idx]
    if slot["kind"] not in ("new_hero", "returning_hero"):
        raise HTTPException(409, "chitchat only with heroes")
    hero = repo.get_hero(slot["hero_id"])
    if not hero:
        raise HTTPException(404, "hero not found")
    try:
        return await chitchat.converse(player, hero, req.player_message)
    except ValueError as e:
        raise HTTPException(400, detail={"error": str(e)})
