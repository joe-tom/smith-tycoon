"""미션 스케줄러 — forge_open에서 plan → evaluate → endgame, today_slots 제공."""
from __future__ import annotations
from typing import Any
from .. import repo, endgame
from . import MODULES, module_for


def advance(player: dict[str, Any]) -> None:
    """plan + evaluate. ending 발생 시 endgame.apply_ending 후 종료."""
    day = int(player["current_day"])
    pid = player["id"]

    for kind, mod in MODULES.items():
        for row in mod.plan(player, day):
            repo.insert_mission(row)

    for mission in repo.list_pending_missions(pid):
        mod = module_for(mission["kind"])
        new_status, ending_kind = mod.evaluate(player, day, mission)
        if new_status != mission["status"]:
            repo.update_mission(mission["id"], status=new_status)
        if ending_kind:
            endgame.apply_ending(pid, ending_kind)
            player["ending_kind"] = ending_kind
            return


def today_slots(player_id: int, day: int) -> list[dict[str, Any]]:
    missions = repo.list_missions_today(player_id, day)
    return [module_for(m["kind"]).slot_for(m) for m in missions]
