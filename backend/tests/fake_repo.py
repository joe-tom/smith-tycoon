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
        self.materials: list[dict[str, Any]] = []
        self.negotiations: list[dict[str, Any]] = []
        self._neg_seq = 0
        self.inventory: dict[int, list[dict[str, Any]]] = {}
        self.day_events: list[dict[str, Any]] = []
        self._event_seq = 0

    # --- players ---
    def load_player(self, player_id: int) -> dict[str, Any] | None:
        return self.players.get(player_id)

    def update_player(self, player_id: int, **fields: Any) -> None:
        self.players[player_id].update(fields)

    # --- weapons ---
    def get_weapon(self, weapon_id: int) -> dict[str, Any] | None:
        return next((w for w in self.weapons if w["id"] == weapon_id), None)

    def delete_weapon(self, weapon_id: int) -> None:
        for w in self.weapons:
            if w["id"] == weapon_id:
                w["owner"] = "dispatched"
                return

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

    # --- 011: materials / negotiations / lore / loot ---

    def list_materials_by_category(self, category: str) -> list[dict[str, Any]]:
        return [m for m in self.materials if m["category"] == category]

    def get_material(self, material_id: int) -> dict[str, Any] | None:
        return next((m for m in self.materials if m["id"] == material_id), None)

    def update_hero(self, hero_id: int, **fields: Any) -> None:
        for h in self.heroes:
            if h["id"] == hero_id:
                h.update(fields)
                return

    def append_hero_lore(self, hero_id: int, entry: dict[str, Any], cap: int = 20) -> None:
        h = self.get_hero(hero_id)
        if h is None:
            return
        lore = list(h.get("lore") or [])
        lore.append(entry)
        if len(lore) > cap:
            lore = lore[-cap:]
        h["lore"] = lore

    def append_hero_loot(self, hero_id: int, items: list[dict[str, Any]]) -> None:
        h = self.get_hero(hero_id)
        if h is None:
            return
        h["loot_pending"] = list(h.get("loot_pending") or []) + items

    def clear_hero_loot(self, hero_id: int) -> None:
        h = self.get_hero(hero_id)
        if h:
            h["loot_pending"] = []

    def insert_negotiation(self, player_id: int, neg: dict[str, Any]) -> dict[str, Any]:
        self._neg_seq += 1
        saved = {"id": self._neg_seq, "player_id": player_id, **neg}
        self.negotiations.append(saved)
        return saved

    def get_negotiation(self, neg_id: int) -> dict[str, Any] | None:
        return next((n for n in self.negotiations if n["id"] == neg_id), None)

    def update_negotiation(self, neg_id: int, **fields: Any) -> None:
        n = self.get_negotiation(neg_id)
        if n:
            n.update(fields)

    def add_inventory(self, player_id: int, material_id: int, qty: int) -> None:
        rows = self.inventory.setdefault(player_id, [])
        for r in rows:
            if r["material_id"] == material_id:
                r["qty"] += qty
                return
        mat = self.get_material(material_id) or {}
        rows.append({
            "material_id": material_id, "qty": qty,
            "name": mat.get("name", "?"), "category": mat.get("category", "?"),
            "attribute": mat.get("attribute"), "base_price": mat.get("base_price", 0),
        })

    def insert_day_event(self, player_id: int, day: int, phase: str,
                          kind: str, payload: dict[str, Any]) -> None:
        self._event_seq += 1
        self.day_events.append({
            "id": self._event_seq, "player_id": player_id, "day": day,
            "phase": phase, "kind": kind, "payload": payload,
        })

    # --- 부수적인 stub들 (combat 등 통합 테스트용) ---
    def list_defeated_boss_ids(self, player_id: int) -> set[str]:
        return {e["payload"]["boss_id"] for e in self.day_events
                if e["kind"] == "boss_kill" and e.get("payload", {}).get("boss_id")}

    def count_consecutive_survives(self, player_id: int, hero_id: int) -> int:
        return 0

    def insert_battle(self, player_id: int, b: dict[str, Any]) -> dict[str, Any]:
        return {**b, "id": 1, "player_id": player_id}
