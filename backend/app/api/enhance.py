from fastapi import APIRouter, HTTPException, Depends
from .. import repo, negotiation, state_machine
from ..api.visitor import advance as advance_visitor_phase
from ..models import EnhanceNegotiateRequest, NegotiateResponse, FinalizeRequest
from ..auth import current_player

router = APIRouter()


def _current_hero_id(player: dict) -> int:
    try:
        state_machine.assert_phase(player["current_phase"], "visitor")
    except state_machine.PhaseError:
        raise HTTPException(400, detail={"error": "wrong_phase",
                                         "current_phase": player["current_phase"]})
    schedule = player.get("day_schedule") or []
    idx = player.get("current_visitor_index", 0)
    if idx >= len(schedule):
        raise HTTPException(409, "no current visitor")
    slot = schedule[idx]
    if slot["kind"] not in ("new_hero", "returning_hero"):
        raise HTTPException(409, "current slot is not a hero")
    return slot["hero_id"]


def _refresh_and_advance(player_id: int) -> dict:
    player = repo.load_player(player_id)
    advance_visitor_phase(player)
    return {"current_phase": player["current_phase"]}


@router.post("/enhance/negotiate", response_model=NegotiateResponse)
async def post_enhance_negotiate(req: EnhanceNegotiateRequest, player: dict = Depends(current_player)):
    hero_id = _current_hero_id(player)
    selected = [s.model_dump() for s in (req.selected_materials or [])]
    try:
        return await negotiation.step_enhance(
            player, hero_id, req.price_offered, req.player_message,
            neg_id=req.negotiation_id,
            selected_materials=selected if req.negotiation_id is None else None,
        )
    except ValueError as e:
        raise HTTPException(400, detail={"error": "enhance_invalid", "message": str(e)})


@router.post("/enhance/finalize")
def post_enhance_finalize(req: FinalizeRequest, player: dict = Depends(current_player)):
    try:
        negotiation.finalize_enhance(player, req.negotiation_id)
    except ValueError as e:
        raise HTTPException(400, detail={"error": "cannot_finalize", "message": str(e)})
    return {"ok": True, **_refresh_and_advance(player["id"])}


@router.post("/enhance/player_accept")
def post_enhance_player_accept(req: FinalizeRequest, player: dict = Depends(current_player)):
    try:
        agreed = negotiation.player_accept_enhance_counter(player, req.negotiation_id)
        negotiation.finalize_enhance(player, req.negotiation_id)
    except ValueError as e:
        raise HTTPException(400, detail={"error": "cannot_accept", "message": str(e)})
    return {"ok": True, "agreed_price": agreed, **_refresh_and_advance(player["id"])}


@router.post("/enhance/player_reject")
def post_enhance_player_reject(req: FinalizeRequest, player: dict = Depends(current_player)):
    try:
        negotiation.player_reject_enhance(player, req.negotiation_id)
    except ValueError as e:
        raise HTTPException(400, detail={"error": "cannot_reject", "message": str(e)})
    return {"ok": True, **_refresh_and_advance(player["id"])}


@router.post("/enhance/skip")
def post_enhance_skip(player: dict = Depends(current_player)):
    _current_hero_id(player)  # validate
    return {"ok": True, **_refresh_and_advance(player["id"])}
