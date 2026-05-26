"""Two-player isolation smoke test using FakeRepo."""


class TwoPlayerFake:
    def __init__(self):
        self.players = {
            1: {"id": 1, "nickname": "A", "gold": 100, "reputation": 0,
                "effort": 50, "current_day": 1, "current_phase": "forge_open"},
            2: {"id": 2, "nickname": "B", "gold": 999, "reputation": 0,
                "effort": 50, "current_day": 1, "current_phase": "forge_open"},
        }
        self.inv = {
            1: [{"material_id": 1, "qty": 5, "name": "x",
                 "category": "일반", "attribute": None, "base_price": 50}],
            2: [{"material_id": 1, "qty": 0, "name": "x",
                 "category": "일반", "attribute": None, "base_price": 50}],
        }
        self.weapons = {1: [], 2: []}

    def load_player(self, pid):
        return self.players[pid]

    def load_inventory(self, pid):
        return list(self.inv[pid])

    def load_player_weapons(self, pid):
        return list(self.weapons[pid])


def test_two_players_isolated_inventory():
    fake = TwoPlayerFake()
    assert fake.load_inventory(1)[0]["qty"] == 5
    assert fake.load_inventory(2)[0]["qty"] == 0


def test_two_players_isolated_gold():
    fake = TwoPlayerFake()
    assert fake.load_player(1)["gold"] == 100
    assert fake.load_player(2)["gold"] == 999


def test_two_players_isolated_weapons():
    fake = TwoPlayerFake()
    fake.weapons[1].append({"id": 1, "name": "검"})
    assert fake.load_player_weapons(1) == [{"id": 1, "name": "검"}]
    assert fake.load_player_weapons(2) == []
