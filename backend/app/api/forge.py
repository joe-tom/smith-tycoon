from fastapi import APIRouter, HTTPException
from .. import repo, forge, state_machine
from ..models import ForgeRequest, WeaponOut

router = APIRouter()


@router.post("/forge", response_model=WeaponOut)
async def post_forge(req: ForgeRequest):
    player = repo.load_player()
    try:
        state_machine.assert_phase(player["current_phase"], "forge_open")
    except state_machine.PhaseError as e:
        raise HTTPException(400, detail={"error": "wrong_phase", "current_phase": player["current_phase"]})

    try:
        weapon = await forge.craft(req.weapon_type, {m.material_id: m.qty for m in req.materials})
    except ValueError as e:
        raise HTTPException(400, detail={"error": "insufficient_materials", "message": str(e)})

    repo.update_player(current_phase=state_machine.next_phase("forge_open"))
    return weapon
