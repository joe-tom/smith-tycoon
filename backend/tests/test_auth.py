import pytest
from fastapi import HTTPException
from app import auth


class FakeRepo:
    def __init__(self):
        self.next_id = 1
        self.players = {}

    def get_or_create_player_by_nickname(self, nickname):
        if nickname in self.players:
            return self.players[nickname]
        p = {"id": self.next_id, "nickname": nickname, "gold": 0,
             "effort": 50, "current_day": 1, "current_phase": "forge_open"}
        self.players[nickname] = p
        self.next_id += 1
        return p


def test_current_player_rejects_empty(monkeypatch):
    monkeypatch.setattr(auth, "repo", FakeRepo())
    with pytest.raises(HTTPException) as e:
        auth.current_player("   ")
    assert e.value.status_code == 400


def test_current_player_rejects_too_long(monkeypatch):
    monkeypatch.setattr(auth, "repo", FakeRepo())
    with pytest.raises(HTTPException):
        auth.current_player("a" * 21)


def test_current_player_creates_then_reuses(monkeypatch):
    fake = FakeRepo()
    monkeypatch.setattr(auth, "repo", fake)
    p1 = auth.current_player("Bob")
    p2 = auth.current_player("Bob")
    assert p1["id"] == p2["id"]


def test_current_player_case_sensitive(monkeypatch):
    fake = FakeRepo()
    monkeypatch.setattr(auth, "repo", fake)
    bob = auth.current_player("Bob")
    bob_lower = auth.current_player("bob")
    assert bob["id"] != bob_lower["id"]


def test_current_player_trims_whitespace(monkeypatch):
    fake = FakeRepo()
    monkeypatch.setattr(auth, "repo", fake)
    p1 = auth.current_player("  Bob  ")
    p2 = auth.current_player("Bob")
    assert p1["id"] == p2["id"]
