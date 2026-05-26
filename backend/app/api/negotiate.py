from fastapi import APIRouter, HTTPException
from .. import repo, negotiation, state_machine
from ..models import NegotiateRequest, NegotiateResponse, FinalizeRequest

router = APIRouter()


@router.post("/negotiate", response_model=NegotiateResponse)
async def post_negotiate(req: NegotiateRequest):
    player = repo.load_player()
    try:
        state_machine.assert_phase(player["current_phase"], "hero_negotiate")
    except state_machine.PhaseError:
        raise HTTPException(400, detail={"error": "wrong_phase",
                                          "current_phase": player["current_phase"]})

    weapon = repo.get_weapon(req.weapon_id)
    if weapon["owner"] != "player":
        raise HTTPException(400, detail={"error": "weapon_not_owned"})

    heroes = repo.list_alive_heroes()
    if not heroes:
        raise HTTPException(400, detail={"error": "no_hero_present"})
    hero_id = heroes[0]["id"]

    result = await negotiation.step_sell(req.weapon_id, hero_id, req.price_offered,
                                         req.player_message, neg_id=req.negotiation_id)
    return result


@router.post("/negotiate/finalize")
def post_finalize(req: FinalizeRequest):
    try:
        negotiation.finalize_sale(req.negotiation_id)
    except ValueError as e:
        raise HTTPException(400, detail={"error": "cannot_finalize", "message": str(e)})
    player = repo.load_player()
    return {"ok": True, "next_phase": player["current_phase"]}


@router.post("/negotiate/player_accept")
def post_player_accept(req: FinalizeRequest):
    """플레이어가 용사 카운터를 수락하고 거래를 즉시 확정."""
    try:
        agreed = negotiation.player_accept_counter(req.negotiation_id)
        negotiation.finalize_sale(req.negotiation_id)
    except ValueError as e:
        raise HTTPException(400, detail={"error": "cannot_accept", "message": str(e)})
    player = repo.load_player()
    return {"ok": True, "agreed_price": agreed, "next_phase": player["current_phase"]}


@router.post("/negotiate/player_reject")
def post_player_reject(req: FinalizeRequest):
    """플레이어가 협상 결렬 — 평판 -1, 전투 phase로."""
    try:
        negotiation.player_reject(req.negotiation_id)
    except ValueError as e:
        raise HTTPException(400, detail={"error": "cannot_reject", "message": str(e)})
    player = repo.load_player()
    return {"ok": True, "next_phase": player["current_phase"]}
