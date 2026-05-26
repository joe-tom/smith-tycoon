import pytest
from unittest.mock import patch
from app import forge, negotiation, combat


class FakeRepo:
    def __init__(self):
        self.player = {"id": 1, "gold": 5000, "reputation": 0, "current_day": 1,
                       "current_phase": "forge_open", "craft_power": 0}
        self.inventory = [
            {"material_id": 1, "qty": 5, "name": "나뭇가지", "category": "일반",
             "attribute": "바람", "base_price": 5},
            {"material_id": 4, "qty": 5, "name": "철덩이", "category": "일반",
             "attribute": "금", "base_price": 50},
            {"material_id": 11, "qty": 2, "name": "다이아몬드", "category": "특수",
             "attribute": "금", "base_price": 800},
        ]
        self.weapons: list = []
        self.heroes = []
        self.negs: list = []
        self.battles: list = []
        self.day_events: list = []
        self._wid = 100
        self._nid = 0

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
                r["qty"] += qty; return
        self.inventory.append({"material_id": mid, "qty": qty, "name": "?", "category": "일반",
                               "attribute": None, "base_price": 50})
    def insert_weapon(self, player_id, w):
        self._wid += 1
        w = {**w, "id": self._wid, "player_id": player_id}
        self.weapons.append(w); return w
    def get_weapon(self, wid): return next(w for w in self.weapons if w["id"] == wid)
    def update_weapon(self, wid, **f):
        w = self.get_weapon(wid)
        w.update(f)
    def list_sold_weapons(self, player_id=None): return [w for w in self.weapons if w["owner"] == "sold"]
    def transfer_weapon_to_hero(self, wid, _):
        for w in self.weapons:
            if w["id"] == wid: w["owner"] = "sold"
    def insert_hero(self, player_id, h):
        h = {**h, "id": 10 + len(self.heroes), "player_id": player_id}
        self.heroes.append(h); return h
    def get_hero(self, hid): return next(h for h in self.heroes if h["id"] == hid)
    def update_hero(self, hid, **f): self.get_hero(hid).update(f)
    def list_alive_heroes_ready(self, player_id, day):
        return [h for h in self.heroes if h["status"] == "alive"
                and (h.get("return_day") is None or h["return_day"] <= day)]
    def insert_negotiation(self, player_id, n):
        self._nid += 1
        n = {**n, "id": self._nid, "player_id": player_id}
        self.negs.append(n); return n
    def get_negotiation(self, nid): return next(n for n in self.negs if n["id"] == nid)
    def update_negotiation(self, nid, **f): self.get_negotiation(nid).update(f)
    def insert_battle(self, player_id, b):
        b = {**b, "id": len(self.battles) + 1, "player_id": player_id}
        self.battles.append(b); return b
    def insert_day_event(self, player_id, day, phase, kind, payload):
        self.day_events.append({"id": len(self.day_events) + 1, "player_id": player_id,
                                "day": day, "phase": phase, "kind": kind, "payload": payload})
    def list_day_events(self, player_id, day):
        return [e for e in self.day_events if e["day"] == day and e.get("player_id") == player_id]
    def count_consecutive_survives(self, player_id, hero_id):
        c = 0
        for b in reversed(self.battles):
            if b["hero_id"] != hero_id: continue
            o = b["outcomes"]
            if o.get("hero") == "survived" and o.get("demon") == "killed":
                c += 1
            else:
                break
        return c


@pytest.mark.asyncio
async def test_returning_hero_enhance_flow():
    fake = FakeRepo()
    fake.heroes.append({
        "id": 10, "name": "100", "job": "검사",
        "str": 12, "mag": 5, "gold": 3000, "mood": "여유로움",
        "personality_tags": ["호탕"], "affinity": 25, "status": "alive",
        "return_day": None, "history": [], "nickname": None, "held_weapon_id": None,
        "visit_count": 1,
    })
    from app import hero_registry

    with patch.object(forge, "repo", fake), \
         patch.object(negotiation, "repo", fake), \
         patch.object(combat, "repo", fake), \
         patch.object(hero_registry, "repo", fake):

        # Day 1: 무기 제작 → hero에게 판매 → held_weapon_id 세팅 확인
        weapon = await forge.craft(fake.player, "한손검", {1: 2, 4: 2})
        weapon_id = weapon["id"]
        fake.update_player(current_phase="hero1_negotiate")

        r = await negotiation.step_sell(fake.player, weapon_id, 10, 100, "이거", neg_id=None)
        assert r["decision"] == "accept"
        negotiation.finalize_sale(fake.player, r["negotiation_id"])
        assert fake.player["current_phase"] == "hero1_battle"
        assert fake.heroes[0]["held_weapon_id"] == weapon_id

        # Day 4로 점프 → 재방문 + held_weapon이 있으므로 mode=enhance
        fake.update_player(current_day=4, current_phase="forge_open")
        todays = hero_registry.heroes_for_today(fake.player["id"], 4)
        h = todays[0]
        assert h.get("held_weapon_id") == weapon_id

        # 강화 협상 (다이아몬드 1개 — 특수 재료)
        fake.update_player(current_phase="hero1_negotiate")
        r2 = await negotiation.step_enhance(
            fake.player, h["id"], 1000, "강화해주시오", neg_id=None,
            selected_materials=[{"material_id": 11, "qty": 1}],
        )
        # fixture가 accept를 반환 (또는 server force accept)
        assert r2["decision"] in ("accept", "counter")
        if r2["decision"] == "accept":
            negotiation.finalize_enhance(fake.player, r2["negotiation_id"])
            assert fake.player["current_phase"] == "hero1_battle"
            # 무기 강화 효과 확인
            w = fake.get_weapon(weapon_id)
            assert w["enhancement_level"] == 1
            assert any(m.get("action") == "enhance" for m in w["materials_used"])
            # 다이아몬드 1개 차감
            assert next(r for r in fake.inventory if r["material_id"] == 11)["qty"] == 1


def test_nickname_should_award_logic():
    from app.nickname import should_award
    hero = {"affinity": 25, "nickname": None}
    assert should_award(hero, consecutive_survives=2) is True
    assert should_award(hero, consecutive_survives=1) is False
    hero2 = {"affinity": 10, "nickname": None}
    assert should_award(hero2, consecutive_survives=5) is False
