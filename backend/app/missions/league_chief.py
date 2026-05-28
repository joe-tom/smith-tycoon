"""상인조합장 미션 — day 11~15 random spawn, d+3 안에 평판 50 도달."""
from __future__ import annotations
import random
from typing import Any
from .. import repo

THRESHOLD = 50
WINDOW_DAYS = 3


def spawn_day(player_id: int) -> int:
    seed = (player_id * 1_000_003 + 47) & 0xFFFFFFFF
    return random.Random(seed).randint(11, 15)


def plan(player: dict[str, Any], day: int) -> list[dict[str, Any]]:
    if day != spawn_day(player["id"]):
        return []
    return [{
        "player_id": player["id"], "kind": "league_chief",
        "phase": "challenge", "due_day": day,
        "payload": {"threshold": THRESHOLD, "deadline": day + WINDOW_DAYS},
    }]


def evaluate(player: dict[str, Any], day: int,
              mission: dict[str, Any]) -> tuple[str, str | None]:
    if mission["status"] != "pending":
        return (mission["status"], None)
    phase = mission["phase"]
    payload = mission.get("payload") or {}
    if phase == "challenge":
        threshold = int(payload.get("threshold", THRESHOLD))
        if int(player.get("reputation", 0)) >= threshold:
            repo.insert_mission({
                "player_id": player["id"], "kind": "league_chief",
                "phase": "praise", "due_day": day + 1, "payload": {},
            })
            return ("condition_met", None)
        deadline = int(payload.get("deadline", day + WINDOW_DAYS))
        if day > deadline:
            return ("failed", "mission_league_failed")
        return ("pending", None)
    if phase == "praise":
        if day > int(mission["due_day"]):
            return ("done", None)
        return ("pending", None)
    return ("pending", None)


def slot_for(mission: dict[str, Any]) -> dict[str, Any]:
    payload = mission.get("payload") or {}
    return {
        "kind": "mission_npc", "mission_id": mission["id"],
        "mission_kind": "league_chief", "phase": mission["phase"],
        "threshold": int(payload.get("threshold", THRESHOLD)),
        "deadline": int(payload.get("deadline", 0)),
    }


def on_action(player: dict[str, Any], mission: dict[str, Any], action: str) -> dict[str, Any]:
    if action != "ack":
        raise ValueError(f"invalid action {action}")
    if mission["phase"] == "praise":
        repo.update_mission(mission["id"], status="done")
    return {"ok": True}
