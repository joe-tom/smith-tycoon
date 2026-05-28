from fastapi import APIRouter, HTTPException, Depends
from .. import repo, negotiation, merchant, state_machine
from ..api.visitor import advance as advance_visitor_phase
from ..models import MerchantNegotiateRequest, NegotiateResponse, FinalizeRequest
from ..auth import current_player

router = APIRouter()


def _assert_merchant_slot(player: dict) -> None:
    try:
        state_machine.assert_phase(player["current_phase"], "visitor")
    except state_machine.PhaseError:
        raise HTTPException(400, detail={"error": "wrong_phase", "current_phase": player["current_phase"]})
    schedule = player.get("day_schedule") or []
    idx = player.get("current_visitor_index", 0)
    if idx >= len(schedule) or schedule[idx]["kind"] != "merchant":
        raise HTTPException(409, "current slot is not merchant")


def _ensure_merchant_today(player_id: int, day: int) -> dict:
    m = repo.get_merchant_today(player_id, day)
    if m is None:
        bundle = merchant.generate_today(player_id, day)
        m = repo.insert_merchant_today(player_id, {"day": day, **bundle, "outcome": "pending"})
    return m


def _refresh_and_advance(player_id: int) -> dict:
    player = repo.load_player(player_id)
    advance_visitor_phase(player)
    return {"current_phase": player["current_phase"]}


@router.post("/merchant/negotiate", response_model=NegotiateResponse)
async def post_merchant_negotiate(req: MerchantNegotiateRequest, player: dict = Depends(current_player)):
    _assert_merchant_slot(player)
    m = _ensure_merchant_today(player["id"], player["current_day"])
    if m["id"] != req.merchant_id:
        raise HTTPException(400, detail={"error": "merchant_mismatch"})
    selected = [s.model_dump() for s in (req.selected_materials or [])]
    try:
        result = await negotiation.step_buy(
            player, m["id"], req.price_offered, req.player_message,
            neg_id=req.negotiation_id,
            selected_materials=selected if req.negotiation_id is None else None,
            select_weapon=req.select_weapon,
        )
    except ValueError as e:
        raise HTTPException(400, detail={"error": "selection_invalid", "message": str(e)})
    # 협상 결렬되면 상인 슬롯 끝 — 자동으로 다음 visitor로 advance
    if result.get("decision") == "reject":
        repo.update_merchant_today(m["id"], outcome="done")
        _refresh_and_advance(player["id"])
    return result


@router.post("/merchant/negotiate/finalize")
def post_merchant_finalize(req: FinalizeRequest, player: dict = Depends(current_player)):
    try:
        negotiation.finalize_buy(player, req.negotiation_id)
    except ValueError as e:
        raise HTTPException(400, detail={"error": "cannot_finalize", "message": str(e)})
    return {"ok": True, **_refresh_and_advance(player["id"])}


@router.post("/merchant/player_accept")
def post_merchant_player_accept(req: FinalizeRequest, player: dict = Depends(current_player)):
    try:
        agreed = negotiation.player_accept_buy_counter(player, req.negotiation_id)
        negotiation.finalize_buy(player, req.negotiation_id)
    except ValueError as e:
        raise HTTPException(400, detail={"error": "cannot_accept", "message": str(e)})
    return {"ok": True, "agreed_price": agreed, **_refresh_and_advance(player["id"])}


@router.post("/merchant/player_reject")
def post_merchant_player_reject(req: FinalizeRequest, player: dict = Depends(current_player)):
    try:
        negotiation.player_reject_buy(player, req.negotiation_id)
    except ValueError as e:
        raise HTTPException(400, detail={"error": "cannot_reject", "message": str(e)})
    return {"ok": True, **_refresh_and_advance(player["id"])}


@router.post("/merchant/skip")
def post_merchant_skip(player: dict = Depends(current_player)):
    _assert_merchant_slot(player)
    m = _ensure_merchant_today(player["id"], player["current_day"])
    repo.update_merchant_today(m["id"], outcome="done")
    return {"ok": True, **_refresh_and_advance(player["id"])}
