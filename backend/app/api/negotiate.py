from fastapi import APIRouter, HTTPException, Depends
from .. import repo, negotiation, state_machine, combat
from ..api.visitor import advance as advance_visitor_phase
from ..models import NegotiateRequest, NegotiateResponse, FinalizeRequest
from ..auth import current_player

router = APIRouter()


def _current_visitor_hero_id(player: dict) -> int:
    try:
        state_machine.assert_phase(player["current_phase"], "visitor")
    except state_machine.PhaseError as e:
        raise HTTPException(400, detail={"error": "wrong_phase",
                                         "current_phase": player["current_phase"]}) from e
    schedule = player.get("day_schedule") or []
    idx = player.get("current_visitor_index", 0)
    if idx >= len(schedule):
        raise HTTPException(409, "no current visitor")
    slot = schedule[idx]
    if slot["kind"] not in ("new_hero", "returning_hero"):
        raise HTTPException(409, f"current slot is {slot['kind']}, not a hero")
    return slot["hero_id"]


@router.post("/negotiate", response_model=NegotiateResponse)
async def post_negotiate(req: NegotiateRequest, player: dict = Depends(current_player)):
    weapon = repo.get_weapon(req.weapon_id)
    if weapon["owner"] != "player":
        raise HTTPException(400, detail={"error": "weapon_not_owned"})
    hero_id = _current_visitor_hero_id(player)
    return await negotiation.step_sell(player, req.weapon_id, hero_id, req.price_offered,
                                       req.player_message, neg_id=req.negotiation_id)


async def _accept_and_dispatch(player: dict, neg_id: int, agreed_price: int | None = None) -> dict:
    """공통: 거래 finalize → dispatch_async_battle → advance."""
    try:
        negotiation.finalize_sale(player, neg_id)
    except ValueError as e:
        raise HTTPException(400, detail={"error": "cannot_finalize", "message": str(e)})
    player = repo.load_player(player["id"])
    neg = repo.get_negotiation(neg_id)
    dispatch = await combat.dispatch_async_battle(player, neg["counterparty_id"], neg["weapon_id"])
    player = repo.load_player(player["id"])
    if dispatch.get("ending"):
        return {"ok": True, "agreed_price": agreed_price or neg["agreed_price"],
                "outcome_id": dispatch["outcome_id"],
                "current_phase": player["current_phase"], "ending": dispatch["ending"]}
    advance_visitor_phase(player)
    return {"ok": True, "agreed_price": agreed_price or neg["agreed_price"],
            "outcome_id": dispatch["outcome_id"],
            "current_phase": player["current_phase"]}


@router.post("/negotiate/finalize")
async def post_finalize(req: FinalizeRequest, player: dict = Depends(current_player)):
    return await _accept_and_dispatch(player, req.negotiation_id)


@router.post("/negotiate/player_accept")
async def post_player_accept(req: FinalizeRequest, player: dict = Depends(current_player)):
    try:
        agreed = negotiation.player_accept_counter(player, req.negotiation_id)
    except ValueError as e:
        raise HTTPException(400, detail={"error": "cannot_accept", "message": str(e)})
    return await _accept_and_dispatch(player, req.negotiation_id, agreed_price=agreed)


@router.post("/negotiate/player_reject")
def post_player_reject(req: FinalizeRequest, player: dict = Depends(current_player)):
    try:
        negotiation.player_reject(player, req.negotiation_id)
    except ValueError as e:
        raise HTTPException(400, detail={"error": "cannot_reject", "message": str(e)})
    return {"ok": True, "current_phase": player["current_phase"]}


@router.post("/negotiate/skip")
def post_negotiate_skip(player: dict = Depends(current_player)):
    """협상 건너뛰기 = 슬롯 advance + 평판 -1."""
    try:
        state_machine.assert_phase(player["current_phase"], "visitor")
    except state_machine.PhaseError:
        raise HTTPException(400, detail={"error": "wrong_phase", "current_phase": player["current_phase"]})
    repo.insert_day_event(
        player["id"], day=player["current_day"], phase=player["current_phase"],
        kind="skip", payload={"reason": "skipped_without_selling", "rep_delta": -1},
    )
    repo.update_player(player["id"], reputation=player["reputation"] - 1)
    player = repo.load_player(player["id"])
    advance_visitor_phase(player)
    return {"ok": True, "current_phase": player["current_phase"]}
