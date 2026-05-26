import pytest
from unittest.mock import patch
from app import forge, negotiation, combat, merchant


class FakeRepo:
    def __init__(self):
        self.player = {"id": 1, "gold": 5000, "reputation": 0, "current_day": 1,
                       "current_phase": "forge_open", "craft_power": 0}
        self.inventory = [
            {"material_id": 1, "qty": 5, "name": "나뭇가지", "category": "일반", "attribute": "바람", "base_price": 5},
            {"material_id": 4, "qty": 5, "name": "철덩이",   "category": "일반", "attribute": "금",   "base_price": 50},
            {"material_id": 8, "qty": 3, "name": "강철",     "category": "일반", "attribute": "금",   "base_price": 120},
        ]
        self.weapons: list = []
        self.heroes = []
        self.negs: list = []
        self.battles: list = []
        self.merchants: list = []
        self.day_events: list = []
        self._wid = 100
        self._nid = 0
        self._mid = 0
        self._bid = 0

    def load_player(self, player_id=None): return self.player
    def update_player(self, player_id=None, **f): self.player.update(f)

    def load_inventory(self, player_id=None): return list(self.inventory)
    def deduct_materials(self, player_id, mq):
        for mid, q in mq.items():
            row = next(r for r in self.inventory if r["material_id"] == mid)
            row["qty"] -= q
    def add_inventory(self, player_id, mid, qty):
        for r in self.inventory:
            if r["material_id"] == mid:
                r["qty"] += qty
                return
        self.inventory.append({"material_id": mid, "qty": qty, "name": "?",
                               "category": "일반", "attribute": None, "base_price": 50})

    def insert_weapon(self, player_id, w):
        self._wid += 1
        w = {**w, "id": self._wid, "player_id": player_id}
        self.weapons.append(w); return w
    def get_weapon(self, wid): return next(w for w in self.weapons if w["id"] == wid)
    def list_sold_weapons(self, player_id=None): return [w for w in self.weapons if w["owner"] == "sold"]
    def list_player_weapons(self, player_id=None): return [w for w in self.weapons if w["owner"] == "player"]
    def transfer_weapon_to_hero(self, wid, _):
        for w in self.weapons:
            if w["id"] == wid: w["owner"] = "sold"

    def insert_hero(self, player_id, h):
        h = {**h, "id": 10 + len(self.heroes), "player_id": player_id}
        self.heroes.append(h); return h
    def get_hero(self, hid): return next(h for h in self.heroes if h["id"] == hid)
    def update_hero(self, hid, **f): self.get_hero(hid).update(f)
    def list_alive_heroes(self, player_id=None): return [h for h in self.heroes if h["status"] == "alive"]
    def list_alive_heroes_ready(self, player_id, day):
        return [h for h in self.heroes if h["status"] == "alive"
                and (h.get("return_day") is None or h["return_day"] <= day)]

    def insert_negotiation(self, player_id, n):
        self._nid += 1
        n = {**n, "id": self._nid, "player_id": player_id}
        self.negs.append(n); return n
    def get_negotiation(self, nid): return next(n for n in self.negs if n["id"] == nid)
    def update_negotiation(self, nid, **f): self.get_negotiation(nid).update(f)

    def get_merchant_today(self, player_id, day):
        return next((m for m in self.merchants if m["day"] == day), None)
    def insert_merchant_today(self, player_id, m):
        self._mid += 1
        m = {**m, "id": self._mid, "player_id": player_id}
        self.merchants.append(m); return m
    def update_merchant_today(self, mid, **f):
        next(m for m in self.merchants if m["id"] == mid).update(f)

    def insert_day_event(self, player_id, day, phase, kind, payload):
        self._bid += 1
        self.day_events.append({"id": self._bid, "player_id": player_id, "day": day,
                                "phase": phase, "kind": kind, "payload": payload})
    def list_day_events(self, player_id, day):
        return [e for e in self.day_events if e["day"] == day and e.get("player_id") == player_id]

    def insert_battle(self, player_id, b):
        b = {**b, "id": len(self.battles) + 1, "player_id": player_id}
        self.battles.append(b); return b

    def count_consecutive_survives(self, player_id, hero_id: int) -> int:
        count = 0
        for b in reversed(self.battles):
            if b.get("hero_id") == hero_id:
                if b.get("outcomes", {}).get("hero") in ("survived", "injured"):
                    count += 1
                else:
                    break
        return count


@pytest.mark.asyncio
async def test_day_one_golden_path():
    fake = FakeRepo()
    for i in range(3):
        fake.heroes.append({
            "id": 10 + i, "name": str(100 + i), "job": "검사",
            "str": 12, "mag": 5, "gold": 2000, "mood": "여유로움",
            "personality_tags": ["호탕"], "affinity": 0, "status": "alive",
            "return_day": None, "history": [],
        })
    from app import hero_registry, day_summary

    with patch.object(forge, "repo", fake), \
         patch.object(negotiation, "repo", fake), \
         patch.object(combat, "repo", fake), \
         patch.object(hero_registry, "repo", fake), \
         patch.object(day_summary, "repo", fake), \
         patch("app.negotiation._client_or_repo_get_merchant",
               side_effect=lambda mid: next(m for m in fake.merchants if m["id"] == mid)):

        # forge_open — 무기 제작
        weapon = await forge.craft(fake.player, "양손검", {1: 2, 4: 2})
        assert weapon["owner"] == "player"
        fake.update_player(current_phase="hero1_negotiate")

        # hero1 협상 — accept (픽스처 모드라 항상 accept)
        todays = hero_registry.heroes_for_today(fake.player["id"], 1)
        h1 = todays[0]
        r = await negotiation.step_sell(fake.player, weapon["id"], h1["id"], 1500, "괜찮으시오?", neg_id=None)
        assert r["decision"] == "accept"
        negotiation.finalize_sale(fake.player, r["negotiation_id"])
        assert fake.player["current_phase"] == "hero1_battle"

        # hero1 전투
        b = await combat.run_battle(fake.player, h1["id"], weapon["id"])
        assert "outcomes" in b
        assert fake.player["current_phase"] == "merchant_negotiate"

        # 상인 — 시뮬레이션상 generate + skip 처리 (skip 엔드포인트 통과 효과만 재현)
        bundle = merchant.generate_today(1, day=1, seed=1)
        m_row = fake.insert_merchant_today(1, {"day": 1, **bundle, "outcome": "pending"})
        fake.update_merchant_today(m_row["id"], outcome="done")
        fake.update_player(current_phase="hero2_negotiate")

        # hero2: 무기가 없으므로 협상 단계는 시뮬레이션상 건너뛰고, 직접 hero2_battle phase로
        h2 = todays[1]
        fake.update_player(current_phase="hero2_battle")
        b2 = await combat.run_battle(fake.player, h2["id"], None)
        assert "outcomes" in b2
        assert fake.player["current_phase"] == "hero3_negotiate"

        # hero3 전투 (맨손)
        fake.update_player(current_phase="hero3_battle")
        b3 = await combat.run_battle(fake.player, todays[2]["id"], None)
        assert fake.player["current_phase"] == "day_summary"

        # day_summary build
        summary = day_summary.build(fake.player, 1)
        assert summary["day"] == 1
        assert summary["summary"]["battles"] == 3
        assert summary["summary"]["forges"] == 1
        assert summary["summary"]["sales"] == 1
