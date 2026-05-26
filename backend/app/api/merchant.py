from fastapi import APIRouter, HTTPException, Depends
from .. import repo, negotiation, merchant, state_machine
from ..models import MerchantNegotiateRequest, NegotiateResponse, FinalizeRequest
from ..auth import current_player

router = APIRouter()


def _ensure_merchant_today(player_id: int, day: int) -> dict:
    m = repo.get_merchant_today(player_id, day)
    if m is None:
        bundle = merchant.generate_today(player_id, day)
        m = repo.insert_merchant_today(player_id, {"day": day, **bundle, "outcome": "pending"})
    return m


@router.post("/merchant/negotiate", response_model=NegotiateResponse)
async def post_merchant_negotiate(req: MerchantNegotiateRequest, player: dict = Depends(current_player)):
    try:
        state_machine.assert_phase(player["current_phase"], "merchant_negotiate")
    except state_machine.PhaseError:
        raise HTTPException(400, detail={"error": "wrong_phase", "current_phase": player["current_phase"]})

    m = _ensure_merchant_today(player["id"], player["current_day"])
    if m["id"] != req.merchant_id:
        raise HTTPException(400, detail={"error": "merchant_mismatch"})

    selected = [s.model_dump() for s in (req.selected_materials or [])]
    try:
        result = await negotiation.step_buy(
            player,
            m["id"], req.price_offered, req.player_message,
            neg_id=req.negotiation_id,
            selected_materials=selected if req.negotiation_id is None else None,
            select_weapon=req.select_weapon,
        )
    except ValueError as e:
        raise HTTPException(400, detail={"error": "selection_invalid", "message": str(e)})
    return result


@router.post("/merchant/negotiate/finalize")
def post_merchant_finalize(req: FinalizeRequest, player: dict = Depends(current_player)):
    try:
        negotiation.finalize_buy(player, req.negotiation_id)
    except ValueError as e:
        raise HTTPException(400, detail={"error": "cannot_finalize", "message": str(e)})
    player_now = repo.load_player(player["id"])
    return {"ok": True, "next_phase": player_now["current_phase"]}


@router.post("/merchant/player_accept")
def post_merchant_player_accept(req: FinalizeRequest, player: dict = Depends(current_player)):
    try:
        agreed = negotiation.player_accept_buy_counter(player, req.negotiation_id)
        negotiation.finalize_buy(player, req.negotiation_id)
    except ValueError as e:
        raise HTTPException(400, detail={"error": "cannot_accept", "message": str(e)})
    player_now = repo.load_player(player["id"])
    return {"ok": True, "agreed_price": agreed, "next_phase": player_now["current_phase"]}


@router.post("/merchant/player_reject")
def post_merchant_player_reject(req: FinalizeRequest, player: dict = Depends(current_player)):
    try:
        negotiation.player_reject_buy(player, req.negotiation_id)
    except ValueError as e:
        raise HTTPException(400, detail={"error": "cannot_reject", "message": str(e)})
    player_now = repo.load_player(player["id"])
    return {"ok": True, "next_phase": player_now["current_phase"]}


@router.post("/merchant/skip")
def post_merchant_skip(player: dict = Depends(current_player)):
    """상인 협상을 건너뛰고 다음 phase로. 평판 변화 없음."""
    try:
        state_machine.assert_phase(player["current_phase"], "merchant_negotiate")
    except state_machine.PhaseError:
        raise HTTPException(400, detail={"error": "wrong_phase", "current_phase": player["current_phase"]})
    m = _ensure_merchant_today(player["id"], player["current_day"])
    repo.update_merchant_today(m["id"], outcome="done")
    repo.update_player(player["id"], current_phase=state_machine.next_phase(player["current_phase"]))
    player_now = repo.load_player(player["id"])
    return {"ok": True, "next_phase": player_now["current_phase"]}
