from fastapi import APIRouter, Depends, HTTPException
from .. import repo
from ..auth import current_player

router = APIRouter(prefix="/mail", tags=["mail"])


@router.post("/{outcome_id}/ack")
def ack(outcome_id: int, player: dict = Depends(current_player)):
    p = repo.get_pending(outcome_id)
    if not p or p["player_id"] != player["id"]:
        raise HTTPException(404, "mail not found")
    if p["kind"] != "death_mail":
        raise HTTPException(400, "not a death mail")
    repo.mark_pending_consumed(outcome_id)
    return {"ok": True}
