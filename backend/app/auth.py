from fastapi import Header, HTTPException
from typing import Any
from . import repo


def current_player(x_player_nickname: str = Header(...)) -> dict[str, Any]:
    nickname = x_player_nickname.strip()
    if not nickname or len(nickname) > 20:
        raise HTTPException(status_code=400, detail={"error": "invalid_nickname"})
    return repo.get_or_create_player_by_nickname(nickname)
