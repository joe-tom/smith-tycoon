from fastapi import APIRouter, HTTPException, Depends
from .. import repo, forge, state_machine, day_open
from ..models import ForgeRequest, WeaponOut
from ..auth import current_player

router = APIRouter()

FORGE_PHASES = ["forge_open"]


@router.post("/forge", response_model=WeaponOut)
async def post_forge(req: ForgeRequest, player: dict = Depends(current_player)):
    try:
        state_machine.assert_phase_in(player["current_phase"], FORGE_PHASES)
    except state_machine.PhaseError:
        raise HTTPException(400, detail={"error": "wrong_phase", "current_phase": player["current_phase"]})

    try:
        weapon = await forge.craft(player, req.weapon_type, {m.material_id: m.qty for m in req.materials})
    except ValueError as e:
        raise HTTPException(400, detail={"error": "insufficient_materials", "message": str(e)})

    # forge phase 동안 여러 무기 제작 가능. phase는 /forge/skip 호출로 명시적 완료.
    return weapon


@router.post("/forge/skip")
def post_forge_skip(player: dict = Depends(current_player)):
    try:
        state_machine.assert_phase_in(player["current_phase"], FORGE_PHASES)
    except state_machine.PhaseError:
        raise HTTPException(400, detail={"error": "wrong_phase", "current_phase": player["current_phase"]})
    # forge_open → visitor 전이 시 그 날 스케줄 생성
    day_open.prepare_day(player)
    repo.update_player(player["id"], current_phase=state_machine.next_phase(player["current_phase"]))
    player_now = repo.load_player(player["id"])
    return {"ok": True, "next_phase": player_now["current_phase"]}
