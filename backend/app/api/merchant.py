from fastapi import APIRouter, HTTPException
from .. import repo, negotiation, merchant, state_machine
from ..models import MerchantNegotiateRequest, NegotiateResponse, FinalizeRequest

router = APIRouter()


def _ensure_merchant_today(day: int) -> dict:
    m = repo.get_merchant_today(day)
    if m is None:
        bundle = merchant.generate_today(day)
        m = repo.insert_merchant_today({"day": day, **bundle, "outcome": "pending"})
    return m


@router.post("/merchant/negotiate", response_model=NegotiateResponse)
async def post_merchant_negotiate(req: MerchantNegotiateRequest):
    player = repo.load_player()
    try:
        state_machine.assert_phase(player["current_phase"], "merchant_negotiate")
    except state_machine.PhaseError:
        raise HTTPException(400, detail={"error": "wrong_phase", "current_phase": player["current_phase"]})

    m = _ensure_merchant_today(player["current_day"])
    if m["id"] != req.merchant_id:
        raise HTTPException(400, detail={"error": "merchant_mismatch"})

    result = await negotiation.step_buy(m["id"], req.price_offered, req.player_message,
                                         neg_id=req.negotiation_id)
    return result


@router.post("/merchant/negotiate/finalize")
def post_merchant_finalize(req: FinalizeRequest):
    try:
        negotiation.finalize_buy(req.negotiation_id)
    except ValueError as e:
        raise HTTPException(400, detail={"error": "cannot_finalize", "message": str(e)})
    player = repo.load_player()
    return {"ok": True, "next_phase": player["current_phase"]}


@router.post("/merchant/player_accept")
def post_merchant_player_accept(req: FinalizeRequest):
    try:
        agreed = negotiation.player_accept_buy_counter(req.negotiation_id)
        negotiation.finalize_buy(req.negotiation_id)
    except ValueError as e:
        raise HTTPException(400, detail={"error": "cannot_accept", "message": str(e)})
    player = repo.load_player()
    return {"ok": True, "agreed_price": agreed, "next_phase": player["current_phase"]}


@router.post("/merchant/player_reject")
def post_merchant_player_reject(req: FinalizeRequest):
    try:
        negotiation.player_reject_buy(req.negotiation_id)
    except ValueError as e:
        raise HTTPException(400, detail={"error": "cannot_reject", "message": str(e)})
    player = repo.load_player()
    return {"ok": True, "next_phase": player["current_phase"]}


@router.post("/merchant/skip")
def post_merchant_skip():
    """상인 협상을 건너뛰고 다음 phase로. 평판 변화 없음."""
    player = repo.load_player()
    try:
        state_machine.assert_phase(player["current_phase"], "merchant_negotiate")
    except state_machine.PhaseError:
        raise HTTPException(400, detail={"error": "wrong_phase", "current_phase": player["current_phase"]})
    m = _ensure_merchant_today(player["current_day"])
    repo.update_merchant_today(m["id"], outcome="done")
    repo.update_player(current_phase=state_machine.next_phase(player["current_phase"]))
    return {"ok": True, "next_phase": repo.load_player()["current_phase"]}
