from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .api import forge as forge_api, negotiate as negotiate_api

app = FastAPI(title="Smith Tycoon API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(forge_api.router)
app.include_router(negotiate_api.router)


@app.get("/health")
def health():
    return {"ok": True}
