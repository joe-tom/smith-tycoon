from fastapi import APIRouter, HTTPException
from .. import repo, combat, state_machine
from ..models import BattleResponse

router = APIRouter()


@router.post("/battle", response_model=BattleResponse)
async def post_battle():
    player = repo.load_player()
    try:
        state_machine.assert_phase(player["current_phase"], "hero_battle")
    except state_machine.PhaseError:
        raise HTTPException(400, detail={"error": "wrong_phase",
                                          "current_phase": player["current_phase"]})

    heroes = repo.list_alive_heroes()
    if not heroes:
        raise HTTPException(400, detail={"error": "no_hero_present"})
    hero = heroes[0]

    # slice: 가장 최근 sold 무기를 그 용사가 들고 있다고 가정
    sold = repo.list_sold_weapons()
    weapon_id = sold[-1]["id"] if sold else None
    return await combat.run_battle(hero["id"], weapon_id)
