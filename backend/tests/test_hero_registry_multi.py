from app import hero_registry


class FakeRepoForHero:
    def __init__(self):
        self.heroes = []
        self.events = []
        self.next_id = 100

    def list_day_events(self, player_id, day):
        return [e for e in self.events
                if e["player_id"] == player_id and e["day"] == day]

    def list_alive_heroes_ready(self, player_id, day):
        return []  # 항상 신규 생성 경로

    def insert_hero(self, player_id, h):
        new = {**h, "id": self.next_id, "player_id": player_id}
        self.next_id += 1
        self.heroes.append(new)
        return new

    def update_hero(self, hero_id, **f):
        for h in self.heroes:
            if h["id"] == hero_id:
                h.update(f)

    def get_hero(self, hero_id):
        return next(h for h in self.heroes if h["id"] == hero_id)

    def insert_day_event(self, player_id, day, phase, kind, payload):
        self.events.append({"player_id": player_id, "day": day, "phase": phase,
                            "kind": kind, "payload": payload})


def test_same_player_same_day_deterministic(monkeypatch):
    fake1 = FakeRepoForHero()
    monkeypatch.setattr(hero_registry, "repo", fake1)
    a = hero_registry.heroes_for_today(player_id=1, day=1)

    fake2 = FakeRepoForHero()
    monkeypatch.setattr(hero_registry, "repo", fake2)
    b = hero_registry.heroes_for_today(player_id=1, day=1)

    assert [h["job"] for h in a] == [h["job"] for h in b]
    assert [h["name"] for h in a] == [h["name"] for h in b]


def test_different_players_different_heroes(monkeypatch):
    fake_a = FakeRepoForHero()
    monkeypatch.setattr(hero_registry, "repo", fake_a)
    a = hero_registry.heroes_for_today(player_id=1, day=1)

    fake_b = FakeRepoForHero()
    monkeypatch.setattr(hero_registry, "repo", fake_b)
    b = hero_registry.heroes_for_today(player_id=2, day=1)

    # 적어도 한 슬롯의 job 또는 name이 달라야 함
    differ = [
        a[i]["job"] != b[i]["job"] or a[i]["name"] != b[i]["name"]
        for i in range(len(a))
    ]
    assert any(differ)


def test_persists_roster_then_reuses(monkeypatch):
    fake = FakeRepoForHero()
    monkeypatch.setattr(hero_registry, "repo", fake)
    a = hero_registry.heroes_for_today(player_id=1, day=1)
    b = hero_registry.heroes_for_today(player_id=1, day=1)
    assert [h["id"] for h in a] == [h["id"] for h in b]
