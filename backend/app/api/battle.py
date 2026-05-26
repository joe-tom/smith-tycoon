from fastapi import APIRouter, HTTPException
from .. import repo, combat, state_machine
from ..models import BattleResponse

router = APIRouter()

BATTLE_PHASES = ["hero1_battle", "hero2_battle", "hero3_battle"]


def _hero_index_for_phase(phase: str) -> int:
    return {"hero1_battle": 0, "hero2_battle": 1, "hero3_battle": 2}[phase]


@router.post("/battle", response_model=BattleResponse)
async def post_battle():
    player = repo.load_player()
    try:
        state_machine.assert_phase_in(player["current_phase"], BATTLE_PHASES)
    except state_machine.PhaseError:
        raise HTTPException(400, detail={"error": "wrong_phase",
                                          "current_phase": player["current_phase"]})

    from .. import hero_registry
    todays = hero_registry.heroes_for_today(player["current_day"])
    idx = _hero_index_for_phase(player["current_phase"])
    hero = todays[idx]

    sold = repo.list_sold_weapons()
    weapon_id = sold[-1]["id"] if sold else None
    return await combat.run_battle(hero["id"], weapon_id)
