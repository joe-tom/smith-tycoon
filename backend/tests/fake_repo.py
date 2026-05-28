"""Shared in-memory repo fake for async-combat tests.

Existing test files maintain their own local FakeRepo classes; new tests
introduced by the async-combat work import this one via the `fake_repo`
fixture in conftest.py.
"""
from __future__ import annotations
from typing import Any


class FakeRepo:
    def __init__(self) -> None:
        self.players: dict[int, dict[str, Any]] = {}
        self.weapons: list[dict[str, Any]] = []
        self.heroes: list[dict[str, Any]] = []
        self.pending_outcomes: list[dict[str, Any]] = []
        self._pending_seq = 0

    # --- players ---
    def load_player(self, player_id: int) -> dict[str, Any] | None:
        return self.players.get(player_id)

    def update_player(self, player_id: int, **fields: Any) -> None:
        self.players[player_id].update(fields)

    # --- weapons ---
    def get_weapon(self, weapon_id: int) -> dict[str, Any] | None:
        return next((w for w in self.weapons if w["id"] == weapon_id), None)

    def delete_weapon(self, weapon_id: int) -> None:
        self.weapons = [w for w in self.weapons if w["id"] != weapon_id]

    # --- heroes ---
    def get_hero(self, hero_id: int) -> dict[str, Any] | None:
        return next((h for h in self.heroes if h["id"] == hero_id), None)

    # --- pending_outcomes ---
    def insert_pending_outcome(self, row: dict[str, Any]) -> dict[str, Any]:
        self._pending_seq += 1
        saved = {"id": self._pending_seq, "consumed": False, **row}
        self.pending_outcomes.append(saved)
        return saved

    def list_pending_to_resolve(self, player_id: int, day: int) -> list[dict[str, Any]]:
        return [
            p for p in self.pending_outcomes
            if p["player_id"] == player_id
            and p["resolve_day"] == day
            and not p["consumed"]
        ]

    def mark_pending_consumed(self, outcome_id: int) -> None:
        for p in self.pending_outcomes:
            if p["id"] == outcome_id:
                p["consumed"] = True
                return

    def update_pending_resolve_day(self, outcome_id: int, new_day: int) -> None:
        for p in self.pending_outcomes:
            if p["id"] == outcome_id:
                p["resolve_day"] = new_day
                return

    def update_pending_outcome(self, outcome_id: int, **fields: Any) -> None:
        for p in self.pending_outcomes:
            if p["id"] == outcome_id:
                p.update(fields)
                return

    def get_pending(self, outcome_id: int) -> dict[str, Any] | None:
        return next((p for p in self.pending_outcomes if p["id"] == outcome_id), None)
