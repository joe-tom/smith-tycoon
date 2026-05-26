from fastapi import APIRouter, Depends
from .. import repo
from ..auth import current_player

router = APIRouter()


@router.post("/game/reset")
def post_reset(player: dict = Depends(current_player)):
    """모든 게임 데이터 truncate + 시드. 용사는 hero_registry가 lazily 생성하므로 여기선 안 만듦."""
    repo.reset_game(player["id"])
    return {"ok": True}
