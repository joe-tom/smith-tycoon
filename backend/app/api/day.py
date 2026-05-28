from fastapi import APIRouter, HTTPException, Depends
from .. import repo, day_summary, state_machine
from ..auth import current_player

router = APIRouter()


@router.get("/day/summary")
def get_summary(player: dict = Depends(current_player)):
    return day_summary.build(player, player["current_day"])


@router.post("/day/next")
def post_next_day(player: dict = Depends(current_player)):
    if player["current_phase"] != "day_summary":
        raise HTTPException(400, detail={"error": "wrong_phase",
                                          "current_phase": player["current_phase"]})
    if player["current_day"] == 100:
        from .. import endgame
        defeated = repo.list_defeated_boss_ids(player["id"])
        ending = endgame.detect_day_100(player, defeated)
        if ending:
            endgame.apply_ending(player["id"], ending)
            return {"ok": True, "ending": ending,
                    "current_day": 100, "current_phase": "game_over"}
    state_machine.advance_to_next_day(player)
    # 하루 종료 시 노력 +50 자동 회복 (상한 100)
    new_effort = min(100, int(player.get("effort", 0)) + 50)
    repo.update_player(player["id"], current_day=player["current_day"],
                       current_phase=player["current_phase"],
                       effort=new_effort)
    return {"ok": True, "current_day": player["current_day"],
            "current_phase": player["current_phase"]}
