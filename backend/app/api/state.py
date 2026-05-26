from fastapi import APIRouter
from .. import repo

router = APIRouter()


@router.get("/state")
def get_state():
    player = repo.load_player()
    inventory = repo.load_inventory()
    weapons = repo.load_player_weapons()
    heroes = repo.list_alive_heroes()
    return {
        "player": player,
        "inventory": inventory,
        "weapons": weapons,
        "hero": heroes[0] if heroes else None,
    }
