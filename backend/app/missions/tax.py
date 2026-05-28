"""세금관 미션 — day 3 warning, day 10/20/.../90 collect 1000골드."""
from __future__ import annotations
from typing import Any
from .. import repo

AMOUNT = 1000
WARNING_DAY = 3
COLLECT_DAYS = {10, 20, 30, 40, 50, 60, 70, 80, 90}


def plan(player: dict[str, Any], day: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if day == WARNING_DAY:
        rows.append({"player_id": player["id"], "kind": "tax",
                      "phase": "warning", "due_day": day, "payload": {}})
    if day in COLLECT_DAYS:
        rows.append({"player_id": player["id"], "kind": "tax",
                      "phase": "collect", "due_day": day,
                      "payload": {"amount": AMOUNT}})
    return rows


def evaluate(player: dict[str, Any], day: int,
              mission: dict[str, Any]) -> tuple[str, str | None]:
    if mission["status"] != "pending":
        return (mission["status"], None)
    if mission["phase"] == "warning":
        return ("pending", None)
    # collect — 만기일 지났는데 미처리면 fail
    if day > int(mission["due_day"]):
        return ("failed", "mission_tax_unpaid")
    return ("pending", None)


def slot_for(mission: dict[str, Any]) -> dict[str, Any]:
    payload = mission.get("payload") or {}
    return {
        "kind": "mission_npc", "mission_id": mission["id"],
        "mission_kind": "tax", "phase": mission["phase"],
        "amount": int(payload.get("amount", 0)),
    }


def on_action(player: dict[str, Any], mission: dict[str, Any], action: str) -> dict[str, Any]:
    phase = mission["phase"]
    if phase == "warning":
        if action == "ack":
            repo.update_mission(mission["id"], status="done")
            return {"ok": True}
        raise ValueError(f"invalid action {action} for warning")
    # collect
    if action == "pay":
        amount = int((mission.get("payload") or {}).get("amount", AMOUNT))
        gold = int(player.get("gold", 0))
        if gold < amount:
            raise ValueError("insufficient_gold")
        repo.update_player(player["id"], gold=gold - amount)
        player["gold"] = gold - amount
        repo.update_mission(mission["id"], status="done")
        repo.insert_day_event(
            player["id"], day=player["current_day"], phase=player["current_phase"],
            kind="tax_paid", payload={"amount": amount, "mission_id": mission["id"]},
        )
        return {"ok": True, "paid": amount}
    if action == "skip":
        repo.update_mission(mission["id"], status="failed")
        return {"ok": True, "ending_kind": "mission_tax_unpaid"}
    raise ValueError(f"invalid action {action} for collect")
