from __future__ import annotations
from typing import Any
from . import repo


def summarize_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    s: dict[str, Any] = {
        "forges": 0, "sales": 0, "buys": 0, "battles": 0,
        "heroes_survived": 0, "heroes_injured": 0, "heroes_died": 0,
        "rep_delta": 0, "gold_delta": 0,
        # 평판 변화 항목별 누적 (UI에서 풀어쓰기 위함)
        "rep_breakdown": {"battle": 0, "sale": 0, "buy": 0, "skip": 0, "reject": 0},
    }
    for e in events:
        k = e["kind"]; p = e.get("payload", {})
        if k == "forge":
            s["forges"] += 1
        elif k == "sale":
            s["sales"] += 1
            s["gold_delta"] += int(p.get("price", 0))
            s["rep_delta"] += 1
            s["rep_breakdown"]["sale"] += 1
        elif k == "buy":
            s["buys"] += 1
            s["gold_delta"] -= int(p.get("price", 0))
            s["rep_delta"] += 1
            s["rep_breakdown"]["buy"] += 1
        elif k == "battle":
            s["battles"] += 1
            out = p.get("outcomes", {})
            if out.get("hero") == "survived":  s["heroes_survived"] += 1
            elif out.get("hero") == "injured": s["heroes_injured"] += 1
            elif out.get("hero") == "died":    s["heroes_died"] += 1
            d = int(p.get("rep_delta", 0))
            s["rep_delta"] += d
            s["rep_breakdown"]["battle"] += d
        elif k == "skip":
            d = int(p.get("rep_delta", -1))
            s["rep_delta"] += d
            s["rep_breakdown"]["skip"] += d
        elif k == "reject":
            d = int(p.get("rep_delta", -1))
            s["rep_delta"] += d
            s["rep_breakdown"]["reject"] += d
    return s


def build(day: int) -> dict[str, Any]:
    events = repo.list_day_events(day)
    summary = summarize_events(events)
    return {"day": day, "events": events, "summary": summary}
