from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from .. import repo, negotiation, state_machine
from ..auth import current_player

router = APIRouter(prefix="/loot", tags=["loot"])


class NegotiateReq(BaseModel):
    price_offered: int
    player_message: str = ""
    negotiation_id: int | None = None


class FinalizeReq(BaseModel):
    negotiation_id: int


def _current_hero_id(player: dict) -> int:
    try:
        state_machine.assert_phase(player["current_phase"], "visitor")
    except state_machine.PhaseError:
        raise HTTPException(400, detail={"error": "wrong_phase"})
    sched = player.get("day_schedule") or []
    idx = player.get("current_visitor_index", 0)
    if idx >= len(sched):
        raise HTTPException(409, "no current visitor")
    slot = sched[idx]
    if slot["kind"] != "returning_hero":
        raise HTTPException(409, "loot trade only for returning_hero")
    return slot["hero_id"]


@router.post("/negotiate")
async def post_negotiate(req: NegotiateReq, player: dict = Depends(current_player)):
    hero_id = _current_hero_id(player)
    try:
        return await negotiation.step_buy_loot(
            player, hero_id, req.price_offered, req.player_message, req.negotiation_id,
        )
    except ValueError as e:
        raise HTTPException(400, detail={"error": "invalid", "message": str(e)})


@router.post("/player_accept")
def post_player_accept(req: FinalizeReq, player: dict = Depends(current_player)):
    neg = repo.get_negotiation(req.negotiation_id)
    if not neg:
        raise HTTPException(404, "negotiation not found")
    if neg["outcome"] == "open":
        hero_counters = [int(r["price"]) for r in neg["rounds"]
                         if r["role"] == "hero" and r.get("price") is not None]
        if not hero_counters:
            raise HTTPException(400, detail={"error": "no counter to accept"})
        repo.update_negotiation(req.negotiation_id, outcome="accepted",
                                 agreed_price=int(hero_counters[-1]))
    try:
        negotiation.finalize_buy_loot(player, req.negotiation_id)
    except ValueError as e:
        raise HTTPException(400, detail={"error": "cannot_finalize", "message": str(e)})
    return {"ok": True}


@router.post("/finalize")
def post_finalize(req: FinalizeReq, player: dict = Depends(current_player)):
    try:
        negotiation.finalize_buy_loot(player, req.negotiation_id)
    except ValueError as e:
        raise HTTPException(400, detail={"error": "cannot_finalize", "message": str(e)})
    return {"ok": True}


@router.post("/player_reject")
def post_player_reject(req: FinalizeReq, player: dict = Depends(current_player)):
    repo.update_negotiation(req.negotiation_id, outcome="rejected")
    return {"ok": True}
