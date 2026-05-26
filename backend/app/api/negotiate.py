from fastapi import APIRouter, HTTPException
from .. import repo, negotiation, state_machine
from ..models import NegotiateRequest, NegotiateResponse, FinalizeRequest

router = APIRouter()

NEGOTIATE_PHASES = ["hero1_negotiate", "hero2_negotiate", "hero3_negotiate"]


def _hero_index_for_phase(phase: str) -> int:
    return {"hero1_negotiate": 0, "hero2_negotiate": 1, "hero3_negotiate": 2}[phase]


@router.post("/negotiate", response_model=NegotiateResponse)
async def post_negotiate(req: NegotiateRequest):
    player = repo.load_player()
    try:
        state_machine.assert_phase_in(player["current_phase"], NEGOTIATE_PHASES)
    except state_machine.PhaseError:
        raise HTTPException(400, detail={"error": "wrong_phase",
                                          "current_phase": player["current_phase"]})

    weapon = repo.get_weapon(req.weapon_id)
    if weapon["owner"] != "player":
        raise HTTPException(400, detail={"error": "weapon_not_owned"})

    from .. import hero_registry
    todays = hero_registry.heroes_for_today(player["current_day"])
    idx = _hero_index_for_phase(player["current_phase"])
    hero_id = todays[idx]["id"]

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
    try:
        agreed = negotiation.player_accept_counter(req.negotiation_id)
        negotiation.finalize_sale(req.negotiation_id)
    except ValueError as e:
        raise HTTPException(400, detail={"error": "cannot_accept", "message": str(e)})
    player = repo.load_player()
    return {"ok": True, "agreed_price": agreed, "next_phase": player["current_phase"]}


@router.post("/negotiate/player_reject")
def post_player_reject(req: FinalizeRequest):
    try:
        negotiation.player_reject(req.negotiation_id)
    except ValueError as e:
        raise HTTPException(400, detail={"error": "cannot_reject", "message": str(e)})
    player = repo.load_player()
    return {"ok": True, "next_phase": player["current_phase"]}


@router.post("/negotiate/skip")
def post_negotiate_skip():
    """협상을 건너뛰고 전투 phase로 진입. 평판 -1 (용사에 대한 결례)."""
    player = repo.load_player()
    try:
        state_machine.assert_phase_in(player["current_phase"], NEGOTIATE_PHASES)
    except state_machine.PhaseError:
        raise HTTPException(400, detail={"error": "wrong_phase", "current_phase": player["current_phase"]})
    repo.insert_day_event(
        day=player["current_day"], phase=player["current_phase"],
        kind="skip", payload={"reason": "skipped_without_selling", "rep_delta": -1},
    )
    repo.update_player(
        reputation=player["reputation"] - 1,
        current_phase=state_machine.next_phase(player["current_phase"]),
    )
    return {"ok": True, "next_phase": repo.load_player()["current_phase"]}
