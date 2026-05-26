import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .api import forge as forge_api, negotiate as negotiate_api, battle as battle_api, state as state_api, game as game_api, merchant as merchant_api, day as day_api
from .llm.client import session_totals

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")

app = FastAPI(title="Smith Tycoon API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(state_api.router)
app.include_router(forge_api.router)
app.include_router(negotiate_api.router)
app.include_router(battle_api.router)
app.include_router(game_api.router)
app.include_router(merchant_api.router)
app.include_router(day_api.router)


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/llm/usage")
def llm_usage():
    """프로세스 시작 이후 누적된 LLM 호출 통계."""
    return session_totals()
