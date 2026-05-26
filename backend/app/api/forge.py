from fastapi import APIRouter, HTTPException
from .. import repo, forge, state_machine
from ..models import ForgeRequest, WeaponOut

router = APIRouter()

FORGE_PHASES = ["forge_open"]


@router.post("/forge", response_model=WeaponOut)
async def post_forge(req: ForgeRequest):
    player = repo.load_player()
    try:
        state_machine.assert_phase_in(player["current_phase"], FORGE_PHASES)
    except state_machine.PhaseError:
        raise HTTPException(400, detail={"error": "wrong_phase", "current_phase": player["current_phase"]})

    try:
        weapon = await forge.craft(req.weapon_type, {m.material_id: m.qty for m in req.materials})
    except ValueError as e:
        raise HTTPException(400, detail={"error": "insufficient_materials", "message": str(e)})

    # forge phase 동안 여러 무기 제작 가능. phase는 /forge/skip 호출로 명시적 완료.
    return weapon


@router.post("/forge/skip")
def post_forge_skip():
    player = repo.load_player()
    try:
        state_machine.assert_phase_in(player["current_phase"], FORGE_PHASES)
    except state_machine.PhaseError:
        raise HTTPException(400, detail={"error": "wrong_phase", "current_phase": player["current_phase"]})
    repo.update_player(current_phase=state_machine.next_phase(player["current_phase"]))
    return {"ok": True, "next_phase": repo.load_player()["current_phase"]}
