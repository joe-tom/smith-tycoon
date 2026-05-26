from fastapi import APIRouter, HTTPException
from .. import repo, day_summary, state_machine

router = APIRouter()


@router.get("/day/summary")
def get_summary():
    player = repo.load_player()
    return day_summary.build(player["current_day"])


@router.post("/day/next")
def post_next_day():
    player = repo.load_player()
    if player["current_phase"] != "day_summary":
        raise HTTPException(400, detail={"error": "wrong_phase",
                                          "current_phase": player["current_phase"]})
    state_machine.advance_to_next_day(player)
    repo.update_player(current_day=player["current_day"],
                       current_phase=player["current_phase"])
    return {"ok": True, "current_day": player["current_day"],
            "current_phase": player["current_phase"]}
