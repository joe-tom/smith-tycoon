from fastapi import APIRouter, HTTPException, Depends
from .. import repo, negotiation, state_machine
from ..models import EnhanceNegotiateRequest, NegotiateResponse, FinalizeRequest
from ..auth import current_player

router = APIRouter()

NEGOTIATE_PHASES = ["hero1_negotiate", "hero2_negotiate", "hero3_negotiate"]


def _hero_index_for_phase(phase: str) -> int:
    return {"hero1_negotiate": 0, "hero2_negotiate": 1, "hero3_negotiate": 2}[phase]


@router.post("/enhance/negotiate", response_model=NegotiateResponse)
async def post_enhance_negotiate(req: EnhanceNegotiateRequest, player: dict = Depends(current_player)):
    try:
        state_machine.assert_phase_in(player["current_phase"], NEGOTIATE_PHASES)
    except state_machine.PhaseError:
        raise HTTPException(400, detail={"error": "wrong_phase",
                                          "current_phase": player["current_phase"]})

    from .. import hero_registry
    todays = hero_registry.heroes_for_today(player["id"], player["current_day"])
    idx = _hero_index_for_phase(player["current_phase"])
    hero_id = todays[idx]["id"]

    selected = [s.model_dump() for s in (req.selected_materials or [])]
    try:
        result = await negotiation.step_enhance(
            player,
            hero_id, req.price_offered, req.player_message,
            neg_id=req.negotiation_id,
            selected_materials=selected if req.negotiation_id is None else None,
        )
    except ValueError as e:
        raise HTTPException(400, detail={"error": "enhance_invalid", "message": str(e)})
    return result


@router.post("/enhance/finalize")
def post_enhance_finalize(req: FinalizeRequest, player: dict = Depends(current_player)):
    try:
        negotiation.finalize_enhance(player, req.negotiation_id)
    except ValueError as e:
        raise HTTPException(400, detail={"error": "cannot_finalize", "message": str(e)})
    player_now = repo.load_player(player["id"])
    return {"ok": True, "next_phase": player_now["current_phase"]}


@router.post("/enhance/player_accept")
def post_enhance_player_accept(req: FinalizeRequest, player: dict = Depends(current_player)):
    try:
        agreed = negotiation.player_accept_enhance_counter(player, req.negotiation_id)
        negotiation.finalize_enhance(player, req.negotiation_id)
    except ValueError as e:
        raise HTTPException(400, detail={"error": "cannot_accept", "message": str(e)})
    player_now = repo.load_player(player["id"])
    return {"ok": True, "agreed_price": agreed, "next_phase": player_now["current_phase"]}


@router.post("/enhance/player_reject")
def post_enhance_player_reject(req: FinalizeRequest, player: dict = Depends(current_player)):
    try:
        negotiation.player_reject_enhance(player, req.negotiation_id)
    except ValueError as e:
        raise HTTPException(400, detail={"error": "cannot_reject", "message": str(e)})
    player_now = repo.load_player(player["id"])
    return {"ok": True, "next_phase": player_now["current_phase"]}


@router.post("/enhance/skip")
def post_enhance_skip(player: dict = Depends(current_player)):
    """강화 phase 건너뛰기 — 평판 변화 없음, phase advance."""
    try:
        state_machine.assert_phase_in(player["current_phase"], NEGOTIATE_PHASES)
    except state_machine.PhaseError:
        raise HTTPException(400, detail={"error": "wrong_phase",
                                          "current_phase": player["current_phase"]})
    repo.update_player(player["id"], current_phase=state_machine.next_phase(player["current_phase"]))
    player_now = repo.load_player(player["id"])
    return {"ok": True, "next_phase": player_now["current_phase"]}
