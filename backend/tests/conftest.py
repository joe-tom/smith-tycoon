import os
from pathlib import Path
import pytest

from tests.fake_repo import FakeRepo


@pytest.fixture(autouse=True)
def llm_fixture_mode(monkeypatch):
    fixture_dir = Path(__file__).parent / "fixtures" / "llm"
    monkeypatch.setenv("LLM_FIXTURE_DIR", str(fixture_dir))
    monkeypatch.setenv("SUPABASE_URL", "http://stub")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "stub")
    from app.config import get_settings
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def fake_repo():
    return FakeRepo()
