import pytest
from unittest.mock import patch
from app import forge, negotiation, combat


class FakeRepo:
    def __init__(self):
        self.player = {"id": 1, "gold": 5000, "reputation": 0, "current_day": 1,
                       "current_phase": "forge_open", "craft_power": 0}
        self.inventory = [
            {"material_id": 1, "qty": 5, "name": "나뭇가지", "category": "일반", "attribute": "바람", "base_price": 5},
            {"material_id": 4, "qty": 5, "name": "철덩이",   "category": "일반", "attribute": "금",   "base_price": 50},
        ]
        self.weapons: list = []
        self.heroes = [{"id": 10, "name": "라엘", "job": "검사", "str": 10, "mag": 3,
                        "gold": 1500, "mood": "여유로움", "personality_tags": ["호탕"],
                        "affinity": 0, "status": "alive", "history": []}]
        self.negs: list = []
        self.battles: list = []
        self._wid = 100

    def load_player(self): return self.player
    def update_player(self, **f): self.player.update(f)
    def load_inventory(self): return self.inventory
    def deduct_materials(self, mq):
        for mid, q in mq.items():
            row = next(r for r in self.inventory if r["material_id"] == mid)
            row["qty"] -= q
    def insert_weapon(self, w):
        self._wid += 1
        w = {**w, "id": self._wid, "player_id": 1}
        self.weapons.append(w); return w
    def get_weapon(self, wid): return next(w for w in self.weapons if w["id"] == wid)
    def list_sold_weapons(self): return [w for w in self.weapons if w["owner"] == "sold"]
    def transfer_weapon_to_hero(self, wid, _):
        for w in self.weapons:
            if w["id"] == wid: w["owner"] = "sold"
    def insert_hero(self, h): self.heroes.append({**h, "id": 99}); return self.heroes[-1]
    def get_hero(self, hid): return next(h for h in self.heroes if h["id"] == hid)
    def update_hero(self, hid, **f): self.get_hero(hid).update(f)
    def list_alive_heroes(self): return [h for h in self.heroes if h["status"] == "alive"]
    def insert_negotiation(self, n):
        n = {**n, "id": len(self.negs) + 1}
        self.negs.append(n); return n
    def get_negotiation(self, nid): return next(n for n in self.negs if n["id"] == nid)
    def update_negotiation(self, nid, **f): self.get_negotiation(nid).update(f)
    def insert_battle(self, b): self.battles.append(b); return b


@pytest.mark.asyncio
async def test_full_slice_golden_path():
    fake = FakeRepo()
    with patch.object(forge, "repo", fake), \
         patch.object(negotiation, "repo", fake), \
         patch.object(combat, "repo", fake):
        weapon = await forge.craft("양손검", {1: 2, 4: 2})
        assert weapon["owner"] == "player"
        assert fake.player["current_phase"] == "forge_open"  # forge() 자체는 phase 안 바꿈
        fake.update_player(current_phase="hero_negotiate")

        res = await negotiation.step_sell(weapon["id"], 10, 1500, "이거 어떠시오", neg_id=None)
        assert res["decision"] == "accept"
        negotiation.finalize_sale(res["negotiation_id"])
        assert fake.player["current_phase"] == "hero_battle"
        assert fake.player["gold"] > 5000

        battle = await combat.run_battle(10, weapon["id"])
        assert battle["outcomes"]["hero"] == "survived"
        assert fake.player["current_phase"] == "done"
