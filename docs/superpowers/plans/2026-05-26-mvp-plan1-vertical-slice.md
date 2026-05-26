# MVP Plan 1 — Vertical Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 한 번의 vertical slice를 끝낸다 — 재료를 골라 무기 1개 제작, 용사 1명과 LLM 협상으로 판매, 그 용사가 마왕군 1마리와 전투 후 결과 표시. 백엔드·프론트·DB·LLM 게이트웨이가 실제로 연결되어 동작.

**Architecture:** FastAPI 백엔드가 모든 상태·LLM 호출을 책임지는 server-authoritative 구조. Supabase(Postgres)를 DB로 사용하며 `repo` 모듈만 Supabase 클라이언트를 안다. LLM 게이트웨이는 OpenAI 호환 API를 호출하되 테스트 시 `LLM_FIXTURE_DIR`을 통해 픽스처 응답을 읽어 결정적 테스트를 가능하게 한다.

**Tech Stack:** Python 3.12 + FastAPI + supabase-py + httpx + pytest + Jinja2 (프롬프트 템플릿) / React + Vite + TypeScript / Supabase (Postgres) / OpenAI 호환 LLM API.

---

## File Structure

### Backend (`backend/`)

```
backend/
├── pyproject.toml                       프로젝트·의존성 정의
├── .env.example                         환경변수 템플릿
├── app/
│   ├── __init__.py
│   ├── main.py                          FastAPI app 진입점, 라우터 등록
│   ├── config.py                        env 로딩 (Pydantic Settings)
│   ├── models.py                        Pydantic DTO (API 입출력)
│   ├── repo.py                          Supabase CRUD 한 곳
│   ├── state_machine.py                 phase 전환·검증
│   ├── forge.py                         재료 → Weapon 생성
│   ├── negotiation.py                   판매 협상 로직
│   ├── combat.py                        전투 + 결과 적용
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── client.py                    OpenAI 호환 호출 + 픽스처 모드 + JSON 파싱
│   │   └── prompts/
│   │       ├── forge_name.j2
│   │       ├── forge_skill.j2
│   │       ├── negotiate_sell.j2
│   │       └── battle.j2
│   └── api/
│       ├── __init__.py
│       ├── state.py                     GET /state
│       ├── forge.py                     POST /forge
│       ├── negotiate.py                 POST /negotiate, POST /negotiate/finalize
│       ├── battle.py                    POST /battle
│       └── game.py                      POST /game/reset
├── migrations/
│   └── 001_initial.sql                  Supabase 초기 스키마
├── seed/
│   └── materials.json                   재료 카탈로그 (slice용 20종)
└── tests/
    ├── conftest.py                      픽스처·페이크 repo
    ├── test_state_machine.py
    ├── test_forge.py
    ├── test_negotiation.py
    ├── test_combat.py
    ├── test_llm_client.py
    └── fixtures/llm/                    LLM 응답 픽스처
        ├── forge_name_basic.json
        ├── forge_skill_basic.json
        ├── negotiate_accept.json
        ├── negotiate_counter.json
        ├── negotiate_reject.json
        └── battle_basic.json
```

### Frontend (`frontend/`)

```
frontend/
├── package.json
├── vite.config.ts
├── tsconfig.json
├── index.html
└── src/
    ├── main.tsx
    ├── App.tsx
    ├── api.ts                           백엔드 호출 래퍼
    ├── types.ts                         서버 DTO 타입
    ├── styles.css
    └── components/
        ├── DayRouter.tsx                phase에 따라 컴포넌트 스왑
        ├── SidePanel.tsx                플레이어 상태·인벤토리
        ├── ForgePanel.tsx               재료 선택 + 제작 버튼
        ├── NegotiationChat.tsx          채팅 + 가격 입력
        └── BattleResult.tsx             결과 모달
```

---

## Task 1: 백엔드 프로젝트 스캐폴드

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/.env.example`
- Create: `backend/app/__init__.py`
- Create: `backend/app/main.py`
- Create: `backend/app/config.py`

- [ ] **Step 1: `backend/pyproject.toml` 작성**

```toml
[project]
name = "smith-tycoon-backend"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "fastapi>=0.115",
  "uvicorn[standard]>=0.32",
  "pydantic>=2.9",
  "pydantic-settings>=2.6",
  "supabase>=2.9",
  "httpx>=0.27",
  "jinja2>=3.1",
  "python-dotenv>=1.0",
]

[project.optional-dependencies]
dev = [
  "pytest>=8",
  "pytest-asyncio>=0.24",
  "ruff>=0.7",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 2: `backend/.env.example` 작성**

```
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=eyJ...
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=sk-...
LLM_MODEL=gpt-4o-mini
# 테스트 모드: 설정 시 LLM 대신 픽스처 파일 사용
# LLM_FIXTURE_DIR=tests/fixtures/llm
```

- [ ] **Step 3: `backend/app/config.py` 작성**

```python
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    supabase_url: str = ""
    supabase_service_key: str = ""
    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    llm_fixture_dir: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 4: `backend/app/main.py` 작성 (FastAPI app, 헬스 체크만)**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Smith Tycoon API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"ok": True}
```

- [ ] **Step 5: `backend/app/__init__.py` 빈 파일 생성**

```python
```

- [ ] **Step 6: 의존성 설치 + 서버 실행 확인**

Run: `cd backend && python -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"`
Run: `uvicorn app.main:app --reload --port 8000`
다른 터미널에서: `curl http://localhost:8000/health`
Expected: `{"ok":true}`

- [ ] **Step 7: Commit**

```bash
git add backend/pyproject.toml backend/.env.example backend/app/
git commit -m "feat(backend): scaffold FastAPI app with health endpoint"
```

---

## Task 2: Supabase 스키마 마이그레이션 (slice 범위)

**Files:**
- Create: `backend/migrations/001_initial.sql`

- [ ] **Step 1: `backend/migrations/001_initial.sql` 작성**

```sql
-- 단일 플레이어 MVP. player_id = 1 고정
create table if not exists players (
  id bigint primary key,
  gold int not null default 5000,
  reputation int not null default 0,
  craft_power int not null default 0,
  current_day int not null default 1,
  current_phase text not null default 'forge_open'
);

create table if not exists materials (
  id bigint primary key,
  name text not null,
  category text not null,
  attribute text,
  base_price int not null
);

create table if not exists inventory (
  player_id bigint references players(id) on delete cascade,
  material_id bigint references materials(id),
  qty int not null default 0,
  primary key (player_id, material_id)
);

create table if not exists weapons (
  id bigserial primary key,
  player_id bigint references players(id) on delete cascade,
  owner text not null check (owner in ('player','hero','sold')),
  name text not null,
  type text not null,
  rarity int not null,
  sharpness int not null,
  attribute text,
  skill text not null,
  str_req int not null,
  mag_req int not null,
  enhancement_level int not null default 0,
  materials_used jsonb not null,
  created_day int not null
);

create table if not exists heroes (
  id bigserial primary key,
  name text not null,
  job text not null,
  str int not null,
  mag int not null,
  gold int not null,
  mood text not null,
  personality_tags text[] not null default '{}',
  affinity int not null default 0,
  nickname text,
  return_day int,
  status text not null default 'alive' check (status in ('alive','fled','dead')),
  history jsonb not null default '[]'::jsonb
);

create table if not exists negotiations (
  id bigserial primary key,
  player_id bigint references players(id) on delete cascade,
  day int not null,
  phase text not null,
  kind text not null check (kind in ('sell','buy','enhance')),
  counterparty_id bigint not null,
  weapon_id bigint references weapons(id),
  materials jsonb,
  rounds jsonb not null default '[]'::jsonb,
  outcome text not null default 'open' check (outcome in ('accepted','rejected','open')),
  agreed_price int
);

create table if not exists battles (
  id bigserial primary key,
  player_id bigint references players(id) on delete cascade,
  day int not null,
  hero_id bigint references heroes(id),
  weapon_id bigint references weapons(id),
  demon jsonb not null,
  script_text text not null,
  outcomes jsonb not null
);
```

- [ ] **Step 2: Supabase SQL Editor에서 실행**

수동 단계: Supabase 프로젝트의 SQL Editor에 위 내용을 붙여넣고 실행.

검증: Supabase Table Editor에서 7개 테이블이 보여야 함.

- [ ] **Step 3: Commit**

```bash
git add backend/migrations/
git commit -m "feat(db): initial schema for slice (players, materials, weapons, heroes, negotiations, battles)"
```

---

## Task 3: 재료 시드 데이터 + repo 모듈

**Files:**
- Create: `backend/seed/materials.json`
- Create: `backend/app/repo.py`

- [ ] **Step 1: `backend/seed/materials.json` 작성 (slice용 20종)**

```json
[
  {"id": 1,  "name": "나뭇가지",     "category": "일반",   "attribute": "바람", "base_price": 5},
  {"id": 2,  "name": "나무판자",     "category": "일반",   "attribute": "바람", "base_price": 15},
  {"id": 3,  "name": "원목",         "category": "일반",   "attribute": "바람", "base_price": 30},
  {"id": 4,  "name": "철덩이",       "category": "일반",   "attribute": "금",   "base_price": 50},
  {"id": 5,  "name": "구리",         "category": "일반",   "attribute": "금",   "base_price": 40},
  {"id": 6,  "name": "고무",         "category": "일반",   "attribute": null,   "base_price": 20},
  {"id": 7,  "name": "플라스틱",     "category": "일반",   "attribute": null,   "base_price": 25},
  {"id": 8,  "name": "강철",         "category": "일반",   "attribute": "금",   "base_price": 120},
  {"id": 9,  "name": "가죽",         "category": "일반",   "attribute": null,   "base_price": 35},
  {"id": 10, "name": "유리",         "category": "일반",   "attribute": null,   "base_price": 30},
  {"id": 11, "name": "다이아몬드",   "category": "특수",   "attribute": "금",   "base_price": 800},
  {"id": 12, "name": "사파이어",     "category": "특수",   "attribute": "물",   "base_price": 600},
  {"id": 13, "name": "금괴",         "category": "특수",   "attribute": "금",   "base_price": 1000},
  {"id": 14, "name": "운석",         "category": "특수",   "attribute": "흙",   "base_price": 1200},
  {"id": 15, "name": "생선뼈",       "category": "이상한", "attribute": null,   "base_price": 2},
  {"id": 16, "name": "계란껍질",     "category": "이상한", "attribute": null,   "base_price": 1},
  {"id": 17, "name": "담배꽁초",     "category": "이상한", "attribute": "불",   "base_price": 1},
  {"id": 18, "name": "드래곤의 깃털","category": "전설",   "attribute": "불",   "base_price": 5000},
  {"id": 19, "name": "테세우스의 배 조각","category": "전설","attribute": "물", "base_price": 4500},
  {"id": 20, "name": "프로메테우스의 불","category": "전설","attribute": "불", "base_price": 6000}
]
```

- [ ] **Step 2: `backend/app/repo.py` 작성**

```python
from __future__ import annotations
import json
from pathlib import Path
from typing import Any
from supabase import create_client, Client
from .config import get_settings

PLAYER_ID = 1


def _client() -> Client:
    s = get_settings()
    return create_client(s.supabase_url, s.supabase_service_key)


def reset_game() -> None:
    """모든 게임 데이터 삭제 + 시드 + player_id=1 생성."""
    c = _client()
    for table in ("battles", "negotiations", "inventory", "weapons", "heroes"):
        c.table(table).delete().neq("id", -1).execute()
    c.table("materials").delete().neq("id", -1).execute()
    c.table("players").delete().neq("id", -1).execute()

    materials_path = Path(__file__).parent.parent / "seed" / "materials.json"
    with materials_path.open() as f:
        materials = json.load(f)
    c.table("materials").insert(materials).execute()
    c.table("players").insert(
        {"id": PLAYER_ID, "gold": 5000, "reputation": 0, "craft_power": 0,
         "current_day": 1, "current_phase": "forge_open"}
    ).execute()
    # 초기 인벤토리: 일반 재료 각 5개, 이상한 3개
    starting = [
        {"player_id": PLAYER_ID, "material_id": mid, "qty": qty}
        for mid, qty in [(1, 5), (2, 5), (4, 5), (5, 5), (8, 3), (15, 3), (16, 3)]
    ]
    c.table("inventory").insert(starting).execute()


def load_player() -> dict[str, Any]:
    c = _client()
    return c.table("players").select("*").eq("id", PLAYER_ID).single().execute().data


def update_player(**fields: Any) -> None:
    _client().table("players").update(fields).eq("id", PLAYER_ID).execute()


def load_inventory() -> list[dict[str, Any]]:
    c = _client()
    rows = c.table("inventory").select("material_id, qty, materials(name, category, attribute, base_price)") \
        .eq("player_id", PLAYER_ID).execute().data
    return [
        {"material_id": r["material_id"], "qty": r["qty"], **r["materials"]}
        for r in rows
    ]


def deduct_materials(material_qty: dict[int, int]) -> None:
    c = _client()
    for mid, q in material_qty.items():
        cur = c.table("inventory").select("qty").eq("player_id", PLAYER_ID).eq("material_id", mid).single().execute().data
        c.table("inventory").update({"qty": cur["qty"] - q}).eq("player_id", PLAYER_ID).eq("material_id", mid).execute()


def insert_weapon(weapon: dict[str, Any]) -> dict[str, Any]:
    c = _client()
    return c.table("weapons").insert({**weapon, "player_id": PLAYER_ID}).execute().data[0]


def load_player_weapons() -> list[dict[str, Any]]:
    return _client().table("weapons").select("*").eq("player_id", PLAYER_ID).eq("owner", "player").execute().data


def get_weapon(weapon_id: int) -> dict[str, Any]:
    return _client().table("weapons").select("*").eq("id", weapon_id).single().execute().data


def transfer_weapon_to_hero(weapon_id: int, hero_id: int) -> None:
    _client().table("weapons").update({"owner": "sold"}).eq("id", weapon_id).execute()
    # hero가 무기를 보유한다는 사실은 battles에서 weapon_id로 참조하므로 별도 컬럼 불필요


def insert_hero(hero: dict[str, Any]) -> dict[str, Any]:
    return _client().table("heroes").insert(hero).execute().data[0]


def get_hero(hero_id: int) -> dict[str, Any]:
    return _client().table("heroes").select("*").eq("id", hero_id).single().execute().data


def update_hero(hero_id: int, **fields: Any) -> None:
    _client().table("heroes").update(fields).eq("id", hero_id).execute()


def insert_negotiation(neg: dict[str, Any]) -> dict[str, Any]:
    return _client().table("negotiations").insert({**neg, "player_id": PLAYER_ID}).execute().data[0]


def update_negotiation(neg_id: int, **fields: Any) -> None:
    _client().table("negotiations").update(fields).eq("id", neg_id).execute()


def get_negotiation(neg_id: int) -> dict[str, Any]:
    return _client().table("negotiations").select("*").eq("id", neg_id).single().execute().data


def insert_battle(b: dict[str, Any]) -> dict[str, Any]:
    return _client().table("battles").insert({**b, "player_id": PLAYER_ID}).execute().data[0]
```

- [ ] **Step 3: Commit**

```bash
git add backend/seed/ backend/app/repo.py
git commit -m "feat(backend): material seed and Supabase repo module"
```

---

## Task 4: LLM 게이트웨이 (픽스처 모드 포함)

**Files:**
- Create: `backend/app/llm/__init__.py`
- Create: `backend/app/llm/client.py`
- Create: `backend/app/llm/prompts/forge_name.j2`
- Create: `backend/app/llm/prompts/forge_skill.j2`
- Create: `backend/app/llm/prompts/negotiate_sell.j2`
- Create: `backend/app/llm/prompts/battle.j2`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/fixtures/llm/forge_name_basic.json`
- Create: `backend/tests/fixtures/llm/forge_skill_basic.json`
- Create: `backend/tests/fixtures/llm/negotiate_accept.json`
- Create: `backend/tests/fixtures/llm/battle_basic.json`
- Test: `backend/tests/test_llm_client.py`

- [ ] **Step 1: `backend/app/llm/__init__.py` 빈 파일**

```python
```

- [ ] **Step 2: 프롬프트 템플릿 4개 작성**

`backend/app/llm/prompts/forge_name.j2`:
```
당신은 판타지 대장간의 작명가입니다. 다음 재료로 만든 무기의 이름을 한국어로 지어주세요.
무기 종류: {{ weapon_type }}
재료: {% for m in materials %}{{ m.name }} ({{ m.category }}){% if not loop.last %}, {% endif %}{% endfor %}

다음 JSON 형식으로만 답하세요:
{"name": "<무기 이름>"}
```

`backend/app/llm/prompts/forge_skill.j2`:
```
당신은 판타지 대장간의 마법사입니다. 무기에 깃든 스킬을 1~2문장으로 설명하세요.
무기 이름: {{ weapon_name }}
무기 종류: {{ weapon_type }}
희귀도: {{ rarity }} / 예리도: {{ sharpness }}

다음 JSON 형식으로만 답하세요:
{"skill": "<스킬 설명>"}
```

`backend/app/llm/prompts/negotiate_sell.j2`:
```
당신은 무기를 사려는 용사입니다. 대장장이가 무기를 팔려고 합니다.

용사 정보:
- 이름: {{ hero.name }}, 직업: {{ hero.job }}
- 보유 금화: {{ hero.gold }}, 기분: {{ hero.mood }}
- 성격: {{ hero.personality_tags|join(", ") }}

무기 정보 (스킬은 비공개):
- 이름: {{ weapon.name }}
- 종류: {{ weapon.type }}, 희귀도: {{ weapon.rarity }}, 예리도: {{ weapon.sharpness }}
- 요구 근력: {{ weapon.str_req }}, 요구 마력: {{ weapon.mag_req }}
- 시세(참고): {{ market_price }} 골드

지금까지의 대화:
{% for r in prior_rounds %}
- {{ r.role }}: "{{ r.message }}"{% if r.price %} (가격: {{ r.price }}){% endif %}
{% endfor %}

대장장이의 새 제안: "{{ player_message }}" (가격: {{ price_offered }} 골드)

성격과 보유 금화에 맞춰 응답하세요. 다음 JSON 형식으로만 답하세요:
{"decision": "accept" | "reject" | "counter", "counter_price": <정수, counter일 때만>, "message": "<용사의 대사>"}
```

`backend/app/llm/prompts/battle.j2`:
```
당신은 판타지 세계의 전투 뉴스 기자입니다. 다음 정보로 전투 결과를 뉴스 한 단락(3~5문장)으로 묘사하고 결과 코드를 정해주세요.

용사: {{ hero.name }} ({{ hero.job }}, 근력 {{ hero.str }}, 마력 {{ hero.mag }})
무기: {% if weapon %}{{ weapon.name }} (예리도 {{ weapon.sharpness }}, 희귀도 {{ weapon.rarity }}){% else %}없음(맨손){% endif %}
적: {{ demon.type }} (난이도 {{ demon.difficulty }})

다음 JSON 형식으로만 답하세요:
{"script": "<뉴스 단락>", "outcomes": {"hero": "survived"|"injured"|"died", "weapon": "preserved"|"destroyed"|"none", "demon": "killed"|"fled"|"survived"}}
```

- [ ] **Step 3: 픽스처 파일 4개 작성**

`backend/tests/fixtures/llm/forge_name_basic.json`:
```json
{"name": "원목 양손검"}
```

`backend/tests/fixtures/llm/forge_skill_basic.json`:
```json
{"skill": "단단한 원목의 결을 살린 묵직한 일격을 가합니다."}
```

`backend/tests/fixtures/llm/negotiate_accept.json`:
```json
{"decision": "accept", "message": "좋소, 그 가격이면 사겠소.", "counter_price": null}
```

`backend/tests/fixtures/llm/battle_basic.json`:
```json
{"script": "용사 라엘이 원목 양손검을 휘둘러 고블린을 단숨에 베어 넘겼다. 무기는 멀쩡했고 용사는 무사히 귀환했다.", "outcomes": {"hero": "survived", "weapon": "preserved", "demon": "killed"}}
```

- [ ] **Step 4: `backend/app/llm/client.py` 작성**

```python
from __future__ import annotations
import json
from pathlib import Path
from typing import Any
import httpx
from jinja2 import Environment, FileSystemLoader, select_autoescape
from ..config import get_settings

_PROMPTS_DIR = Path(__file__).parent / "prompts"
_env = Environment(loader=FileSystemLoader(_PROMPTS_DIR), autoescape=select_autoescape())


def render(template: str, **vars: Any) -> str:
    return _env.get_template(f"{template}.j2").render(**vars)


def _load_fixture(name: str) -> dict[str, Any]:
    s = get_settings()
    assert s.llm_fixture_dir, "LLM_FIXTURE_DIR not set"
    path = Path(s.llm_fixture_dir) / f"{name}.json"
    return json.loads(path.read_text())


async def complete_json(template: str, fixture_name: str, **vars: Any) -> dict[str, Any]:
    """프롬프트를 렌더하고 OpenAI 호환 API에 호출. JSON 응답을 강제.

    `LLM_FIXTURE_DIR` 환경변수가 설정되면 실제 호출 없이 fixture_name 파일을 읽어 반환.
    """
    s = get_settings()
    if s.llm_fixture_dir:
        return _load_fixture(fixture_name)

    prompt = render(template, **vars)
    payload = {
        "model": s.llm_model,
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "json_object"},
        "temperature": 0.8,
    }
    headers = {"Authorization": f"Bearer {s.llm_api_key}"}

    async with httpx.AsyncClient(timeout=30.0) as cli:
        for attempt in range(3):
            try:
                resp = await cli.post(f"{s.llm_base_url}/chat/completions",
                                      json=payload, headers=headers)
                resp.raise_for_status()
                content = resp.json()["choices"][0]["message"]["content"]
                return json.loads(content)
            except (httpx.HTTPError, json.JSONDecodeError, KeyError):
                if attempt == 2:
                    raise
                continue
        raise RuntimeError("unreachable")
```

- [ ] **Step 5: `backend/tests/__init__.py` 빈 파일**

```python
```

- [ ] **Step 6: `backend/tests/conftest.py` 작성**

```python
import os
from pathlib import Path
import pytest


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
```

- [ ] **Step 7: `backend/tests/test_llm_client.py` 작성 (실패 테스트 먼저)**

```python
import pytest
from app.llm.client import complete_json


@pytest.mark.asyncio
async def test_complete_json_returns_fixture():
    result = await complete_json("forge_name", "forge_name_basic",
                                 weapon_type="양손검",
                                 materials=[{"name": "원목", "category": "일반"}])
    assert result == {"name": "원목 양손검"}


@pytest.mark.asyncio
async def test_complete_json_battle_fixture():
    result = await complete_json("battle", "battle_basic",
                                 hero={"name": "라엘", "job": "검사", "str": 10, "mag": 3},
                                 weapon={"name": "원목 양손검", "sharpness": 50, "rarity": 30},
                                 demon={"type": "고블린", "difficulty": 5})
    assert result["outcomes"]["hero"] == "survived"
    assert "라엘" in result["script"]
```

- [ ] **Step 8: 테스트 실행 (먼저 fail 확인)**

Run: `cd backend && pytest tests/test_llm_client.py -v`
Expected: PASS (구현이 이미 있으므로 통과). 만약 import 에러나 fixture 경로 에러가 나면 conftest.py와 client.py를 점검.

- [ ] **Step 9: Commit**

```bash
git add backend/app/llm/ backend/tests/
git commit -m "feat(backend): LLM gateway with prompt templates and fixture mode"
```

---

## Task 5: 상태 머신 (slice용 phase)

**Files:**
- Create: `backend/app/state_machine.py`
- Test: `backend/tests/test_state_machine.py`

slice의 phase 순서: `forge_open → hero_negotiate → hero_battle → done`

- [ ] **Step 1: `backend/tests/test_state_machine.py` 작성 (실패 테스트 먼저)**

```python
import pytest
from app.state_machine import next_phase, assert_phase, INITIAL_PHASE, PhaseError


def test_initial_phase_is_forge_open():
    assert INITIAL_PHASE == "forge_open"


def test_phase_progression():
    assert next_phase("forge_open") == "hero_negotiate"
    assert next_phase("hero_negotiate") == "hero_battle"
    assert next_phase("hero_battle") == "done"


def test_next_phase_after_done_raises():
    with pytest.raises(PhaseError):
        next_phase("done")


def test_assert_phase_match():
    assert_phase("forge_open", "forge_open")  # no raise


def test_assert_phase_mismatch_raises():
    with pytest.raises(PhaseError):
        assert_phase("hero_negotiate", "forge_open")
```

- [ ] **Step 2: 테스트 실행 (fail 확인)**

Run: `cd backend && pytest tests/test_state_machine.py -v`
Expected: FAIL — `ModuleNotFoundError: app.state_machine`

- [ ] **Step 3: `backend/app/state_machine.py` 작성**

```python
class PhaseError(Exception):
    pass


PHASES = ["forge_open", "hero_negotiate", "hero_battle", "done"]
INITIAL_PHASE = PHASES[0]


def next_phase(current: str) -> str:
    if current not in PHASES:
        raise PhaseError(f"unknown phase: {current}")
    idx = PHASES.index(current)
    if idx + 1 >= len(PHASES):
        raise PhaseError(f"no phase after {current}")
    return PHASES[idx + 1]


def assert_phase(current: str, expected: str) -> None:
    if current != expected:
        raise PhaseError(f"expected phase {expected}, got {current}")
```

- [ ] **Step 4: 테스트 실행 (pass 확인)**

Run: `cd backend && pytest tests/test_state_machine.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/state_machine.py backend/tests/test_state_machine.py
git commit -m "feat(backend): state machine for slice phases"
```

---

## Task 6: forge 모듈 + API

**Files:**
- Create: `backend/app/models.py`
- Create: `backend/app/forge.py`
- Create: `backend/app/api/__init__.py`
- Create: `backend/app/api/forge.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_forge.py`

- [ ] **Step 1: `backend/app/models.py` 작성 (Pydantic DTO)**

```python
from pydantic import BaseModel


class MaterialIn(BaseModel):
    material_id: int
    qty: int


class ForgeRequest(BaseModel):
    materials: list[MaterialIn]
    weapon_type: str  # 한손검, 양손검, ...


class WeaponOut(BaseModel):
    id: int
    name: str
    type: str
    rarity: int
    sharpness: int
    attribute: str | None
    skill: str
    str_req: int
    mag_req: int


class NegotiateRequest(BaseModel):
    weapon_id: int
    price_offered: int
    player_message: str
    idempotency_key: str | None = None


class NegotiateResponse(BaseModel):
    negotiation_id: int
    decision: str  # accept / reject / counter
    counter_price: int | None
    message: str


class FinalizeRequest(BaseModel):
    negotiation_id: int


class BattleResponse(BaseModel):
    script: str
    outcomes: dict
    next_phase: str
```

- [ ] **Step 2: `backend/tests/test_forge.py` 작성 (실패 테스트 먼저)**

```python
import pytest
from app.forge import roll_weapon_stats


def test_roll_weapon_stats_deterministic_with_seed():
    stats1 = roll_weapon_stats(["일반", "일반"], seed=42)
    stats2 = roll_weapon_stats(["일반", "일반"], seed=42)
    assert stats1 == stats2


def test_legendary_material_boosts_rarity():
    common = roll_weapon_stats(["일반", "일반"], seed=1)
    legendary = roll_weapon_stats(["전설", "전설"], seed=1)
    assert legendary["rarity"] > common["rarity"]


def test_stats_clamped_0_100():
    for s in range(20):
        stats = roll_weapon_stats(["전설", "전설", "전설", "전설"], seed=s)
        assert 0 <= stats["rarity"] <= 100
        assert 0 <= stats["sharpness"] <= 100
```

- [ ] **Step 3: 테스트 실행 (fail 확인)**

Run: `cd backend && pytest tests/test_forge.py -v`
Expected: FAIL — `ModuleNotFoundError: app.forge`

- [ ] **Step 4: `backend/app/forge.py` 작성**

```python
from __future__ import annotations
import random
from typing import Any
from . import repo
from .llm.client import complete_json

CATEGORY_MULT = {"일반": 1.0, "이상한": 0.5, "특수": 1.8, "전설": 3.5}


def roll_weapon_stats(categories: list[str], seed: int | None = None) -> dict[str, int]:
    """재료 카테고리 리스트 → rarity, sharpness."""
    rng = random.Random(seed)
    mult = sum(CATEGORY_MULT.get(c, 1.0) for c in categories) / max(len(categories), 1)
    base_rarity = rng.gauss(35 * mult, 15)
    base_sharp = rng.gauss(40 * mult, 15)
    return {
        "rarity": max(0, min(100, int(base_rarity))),
        "sharpness": max(0, min(100, int(base_sharp))),
    }


def _choose_attribute(materials: list[dict[str, Any]]) -> str | None:
    counts: dict[str, int] = {}
    for m in materials:
        a = m.get("attribute")
        if a:
            counts[a] = counts.get(a, 0) + 1
    if not counts:
        return None
    return max(counts, key=counts.get)


async def craft(weapon_type: str, material_qty: dict[int, int]) -> dict[str, Any]:
    """재료를 차감하고 무기를 생성. LLM으로 이름·스킬 생성."""
    inv = repo.load_inventory()
    inv_by_id = {row["material_id"]: row for row in inv}
    materials_used: list[dict[str, Any]] = []
    for mid, q in material_qty.items():
        row = inv_by_id.get(mid)
        if not row or row["qty"] < q:
            raise ValueError(f"insufficient material {mid}")
        materials_used.append({"id": mid, "name": row["name"], "category": row["category"],
                               "attribute": row["attribute"], "qty": q})

    stats = roll_weapon_stats([m["category"] for m in materials_used for _ in range(m["qty"])])
    attribute = _choose_attribute(materials_used)

    name_res = await complete_json("forge_name", "forge_name_basic",
                                   weapon_type=weapon_type, materials=materials_used)
    name = name_res["name"]
    skill_res = await complete_json("forge_skill", "forge_skill_basic",
                                    weapon_name=name, weapon_type=weapon_type,
                                    rarity=stats["rarity"], sharpness=stats["sharpness"])
    skill = skill_res["skill"]

    repo.deduct_materials(material_qty)
    player = repo.load_player()
    weapon = repo.insert_weapon({
        "owner": "player",
        "name": name,
        "type": weapon_type,
        "rarity": stats["rarity"],
        "sharpness": stats["sharpness"],
        "attribute": attribute,
        "skill": skill,
        "str_req": max(1, stats["sharpness"] // 10),
        "mag_req": max(1, stats["rarity"] // 15),
        "enhancement_level": 0,
        "materials_used": materials_used,
        "created_day": player["current_day"],
    })
    return weapon
```

- [ ] **Step 5: 테스트 실행 (pass 확인)**

Run: `cd backend && pytest tests/test_forge.py -v`
Expected: PASS (3 tests)

- [ ] **Step 6: `backend/app/api/__init__.py` 빈 파일**

```python
```

- [ ] **Step 7: `backend/app/api/forge.py` 작성**

```python
from fastapi import APIRouter, HTTPException
from .. import repo, forge, state_machine
from ..models import ForgeRequest, WeaponOut

router = APIRouter()


@router.post("/forge", response_model=WeaponOut)
async def post_forge(req: ForgeRequest):
    player = repo.load_player()
    try:
        state_machine.assert_phase(player["current_phase"], "forge_open")
    except state_machine.PhaseError as e:
        raise HTTPException(400, detail={"error": "wrong_phase", "current_phase": player["current_phase"]})

    try:
        weapon = await forge.craft(req.weapon_type, {m.material_id: m.qty for m in req.materials})
    except ValueError as e:
        raise HTTPException(400, detail={"error": "insufficient_materials", "message": str(e)})

    repo.update_player(current_phase=state_machine.next_phase("forge_open"))
    return weapon
```

- [ ] **Step 8: `backend/app/main.py` 수정 — forge 라우터 등록**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .api import forge as forge_api

app = FastAPI(title="Smith Tycoon API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(forge_api.router)


@app.get("/health")
def health():
    return {"ok": True}
```

- [ ] **Step 9: Commit**

```bash
git add backend/app/models.py backend/app/forge.py backend/app/api/ backend/app/main.py backend/tests/test_forge.py
git commit -m "feat(backend): forge module and POST /forge endpoint"
```

---

## Task 7: 협상 모듈 (판매) + API

**Files:**
- Create: `backend/app/negotiation.py`
- Create: `backend/app/api/negotiate.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_negotiation.py`
- Create: `backend/tests/fixtures/llm/negotiate_reject.json`
- Create: `backend/tests/fixtures/llm/negotiate_counter.json`

- [ ] **Step 1: 추가 픽스처 파일 생성**

`backend/tests/fixtures/llm/negotiate_reject.json`:
```json
{"decision": "reject", "message": "그 가격에는 사지 않겠소.", "counter_price": null}
```

`backend/tests/fixtures/llm/negotiate_counter.json`:
```json
{"decision": "counter", "message": "비싸오. 700에 어떻소?", "counter_price": 700}
```

- [ ] **Step 2: `backend/tests/test_negotiation.py` 작성 (실패 테스트 먼저)**

```python
import pytest
from app.negotiation import clamp_price, market_price


def test_clamp_price_lower_bound():
    assert clamp_price(10, base=1000) == 100   # 0.1배 하한


def test_clamp_price_upper_bound():
    assert clamp_price(999999, base=1000) == 5000  # 5배 상한


def test_clamp_price_passthrough():
    assert clamp_price(1500, base=1000) == 1500


def test_market_price_uses_materials_and_rarity():
    weapon = {"rarity": 50, "sharpness": 50, "materials_used": [
        {"category": "일반", "qty": 2}, {"category": "특수", "qty": 1}
    ]}
    # 일반(50*2=100) + 특수(50*1*5=250) + rarity 보너스 = 어쨌든 양수
    price = market_price(weapon)
    assert price > 0
```

- [ ] **Step 3: 테스트 실행 (fail)**

Run: `cd backend && pytest tests/test_negotiation.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 4: `backend/app/negotiation.py` 작성**

```python
from __future__ import annotations
from typing import Any
from . import repo, state_machine
from .llm.client import complete_json

CATEGORY_BASE = {"일반": 50, "이상한": 5, "특수": 250, "전설": 1500}


def market_price(weapon: dict[str, Any]) -> int:
    mat_value = sum(
        CATEGORY_BASE.get(m["category"], 50) * m.get("qty", 1)
        for m in weapon["materials_used"]
    )
    rarity_mult = 1 + weapon["rarity"] / 100
    sharp_mult = 1 + weapon["sharpness"] / 200
    return max(10, int(mat_value * rarity_mult * sharp_mult))


def clamp_price(price: int, base: int) -> int:
    return max(int(base * 0.1), min(int(base * 5.0), price))


async def step_sell(weapon_id: int, hero_id: int, price_offered: int,
                    player_message: str, neg_id: int | None) -> dict[str, Any]:
    weapon = repo.get_weapon(weapon_id)
    hero = repo.get_hero(hero_id)
    base = market_price(weapon)
    safe_price = clamp_price(price_offered, base)

    if neg_id is None:
        player = repo.load_player()
        neg = repo.insert_negotiation({
            "day": player["current_day"], "phase": player["current_phase"],
            "kind": "sell", "counterparty_id": hero_id, "weapon_id": weapon_id,
            "rounds": [], "outcome": "open",
        })
        neg_id = neg["id"]
        prior_rounds: list[dict[str, Any]] = []
    else:
        neg = repo.get_negotiation(neg_id)
        prior_rounds = neg["rounds"]

    fixture_name = "negotiate_accept"  # 픽스처 모드의 기본; 실제 LLM은 prompt 결과 사용
    llm = await complete_json("negotiate_sell", fixture_name,
                              hero=hero, weapon=weapon,
                              market_price=base,
                              prior_rounds=prior_rounds,
                              player_message=player_message,
                              price_offered=safe_price)

    decision = llm["decision"]
    counter = llm.get("counter_price")
    if counter is not None:
        counter = clamp_price(int(counter), base)

    new_rounds = prior_rounds + [
        {"role": "player", "message": player_message, "price": safe_price},
        {"role": "hero", "message": llm["message"], "price": counter},
    ]
    update: dict[str, Any] = {"rounds": new_rounds}
    if decision == "accept":
        update["outcome"] = "accepted"
        update["agreed_price"] = safe_price
    elif decision == "reject":
        update["outcome"] = "rejected"
    repo.update_negotiation(neg_id, **update)

    return {
        "negotiation_id": neg_id,
        "decision": decision,
        "counter_price": counter,
        "message": llm["message"],
    }


def finalize_sale(neg_id: int) -> None:
    neg = repo.get_negotiation(neg_id)
    if neg["outcome"] != "accepted":
        raise ValueError("negotiation not accepted")
    player = repo.load_player()
    repo.transfer_weapon_to_hero(neg["weapon_id"], neg["counterparty_id"])
    repo.update_player(gold=player["gold"] + neg["agreed_price"],
                       reputation=player["reputation"] + 1,
                       current_phase=state_machine.next_phase(player["current_phase"]))
    hero = repo.get_hero(neg["counterparty_id"])
    weapon = repo.get_weapon(neg["weapon_id"])
    new_history = (hero["history"] or []) + [
        {"weapon": weapon["name"], "price": neg["agreed_price"], "battle": None}
    ]
    repo.update_hero(neg["counterparty_id"], affinity=hero["affinity"] + 5,
                     history=new_history[-5:])
```

- [ ] **Step 5: 테스트 실행 (pass)**

Run: `cd backend && pytest tests/test_negotiation.py -v`
Expected: PASS (4 tests)

- [ ] **Step 6: `backend/app/api/negotiate.py` 작성**

```python
from fastapi import APIRouter, HTTPException
from .. import repo, negotiation, state_machine
from ..models import NegotiateRequest, NegotiateResponse, FinalizeRequest

router = APIRouter()


@router.post("/negotiate", response_model=NegotiateResponse)
async def post_negotiate(req: NegotiateRequest):
    player = repo.load_player()
    try:
        state_machine.assert_phase(player["current_phase"], "hero_negotiate")
    except state_machine.PhaseError:
        raise HTTPException(400, detail={"error": "wrong_phase",
                                          "current_phase": player["current_phase"]})

    # slice: 매번 새 협상 (round 누적은 negotiation_id가 응답에 있으니 클라이언트가 전달).
    # 단순화를 위해 idempotency_key 키 매칭은 MVP 외.
    weapon = repo.get_weapon(req.weapon_id)
    if weapon["owner"] != "player":
        raise HTTPException(400, detail={"error": "weapon_not_owned"})

    # 현재 phase에 매칭되는 hero를 찾기 위해 가장 최근의 alive hero를 사용 (slice 단순화)
    heroes = repo.list_alive_heroes() if hasattr(repo, "list_alive_heroes") else []
    if not heroes:
        raise HTTPException(400, detail={"error": "no_hero_present"})
    hero_id = heroes[0]["id"]

    result = await negotiation.step_sell(req.weapon_id, hero_id, req.price_offered,
                                         req.player_message, neg_id=None)
    return result


@router.post("/negotiate/finalize")
def post_finalize(req: FinalizeRequest):
    try:
        negotiation.finalize_sale(req.negotiation_id)
    except ValueError as e:
        raise HTTPException(400, detail={"error": "cannot_finalize", "message": str(e)})
    player = repo.load_player()
    return {"ok": True, "next_phase": player["current_phase"]}
```

- [ ] **Step 7: `backend/app/repo.py`에 `list_alive_heroes` 추가**

`backend/app/repo.py` 맨 아래에 추가:

```python
def list_alive_heroes() -> list[dict[str, Any]]:
    return _client().table("heroes").select("*").eq("status", "alive").execute().data
```

- [ ] **Step 8: `backend/app/main.py` 수정 — negotiate 라우터 등록**

기존 main.py의 import와 include_router에 추가:

```python
from .api import forge as forge_api, negotiate as negotiate_api
...
app.include_router(forge_api.router)
app.include_router(negotiate_api.router)
```

- [ ] **Step 9: Commit**

```bash
git add backend/app/negotiation.py backend/app/api/negotiate.py backend/app/repo.py backend/app/main.py backend/tests/test_negotiation.py backend/tests/fixtures/llm/negotiate_*.json
git commit -m "feat(backend): sell negotiation module and POST /negotiate endpoints"
```

---

## Task 8: combat 모듈 + API

**Files:**
- Create: `backend/app/combat.py`
- Create: `backend/app/api/battle.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_combat.py`

- [ ] **Step 1: `backend/tests/test_combat.py` 작성 (실패 테스트 먼저)**

```python
import pytest
from app.combat import apply_outcomes


def test_apply_outcomes_survived_killed_increases_rep():
    delta = apply_outcomes({"hero": "survived", "weapon": "preserved", "demon": "killed"})
    assert delta["reputation"] >= 2  # 생존 +1, 마왕 처치 +1


def test_apply_outcomes_died_destroyed_decreases_rep():
    delta = apply_outcomes({"hero": "died", "weapon": "destroyed", "demon": "survived"})
    assert delta["reputation"] < 0


def test_apply_outcomes_neutral_outcomes_no_change():
    delta = apply_outcomes({"hero": "injured", "weapon": "preserved", "demon": "survived"})
    assert delta["reputation"] == 0
```

- [ ] **Step 2: 테스트 실행 (fail)**

Run: `cd backend && pytest tests/test_combat.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: `backend/app/combat.py` 작성**

```python
from __future__ import annotations
import random
from typing import Any
from . import repo, state_machine
from .llm.client import complete_json

DEMONS = [
    {"type": "고블린",   "attribute": "흙",   "difficulty_range": (1, 10)},
    {"type": "지옥개",   "attribute": "불",   "difficulty_range": (3, 12)},
    {"type": "작은 영혼","attribute": "물",   "difficulty_range": (1, 8)},
    {"type": "임프",     "attribute": "불",   "difficulty_range": (5, 15)},
]


def roll_demon(seed: int | None = None) -> dict[str, Any]:
    rng = random.Random(seed)
    base = rng.choice(DEMONS)
    lo, hi = base["difficulty_range"]
    return {"type": base["type"], "attribute": base["attribute"],
            "difficulty": rng.randint(lo, hi)}


def apply_outcomes(outcomes: dict[str, str]) -> dict[str, int]:
    """결과 코드 → 평판 변화 등 델타."""
    rep = 0
    if outcomes["hero"] == "survived":
        rep += 1
    elif outcomes["hero"] == "died":
        rep -= 2
    if outcomes["weapon"] == "destroyed":
        rep -= 1
    if outcomes["demon"] == "killed":
        rep += 1
    elif outcomes["demon"] == "fled":
        rep += 0  # 소폭 ↑이지만 slice에서는 0
    return {"reputation": rep}


async def run_battle(hero_id: int, weapon_id: int | None) -> dict[str, Any]:
    hero = repo.get_hero(hero_id)
    weapon = repo.get_weapon(weapon_id) if weapon_id else None
    demon = roll_demon()
    llm = await complete_json("battle", "battle_basic",
                              hero=hero, weapon=weapon, demon=demon)
    outcomes = llm["outcomes"]
    delta = apply_outcomes(outcomes)

    player = repo.load_player()
    repo.update_player(reputation=player["reputation"] + delta["reputation"],
                       current_phase=state_machine.next_phase(player["current_phase"]))

    # hero 상태 반영
    if outcomes["hero"] == "died":
        repo.update_hero(hero_id, status="dead")

    repo.insert_battle({
        "day": player["current_day"],
        "hero_id": hero_id,
        "weapon_id": weapon_id,
        "demon": demon,
        "script_text": llm["script"],
        "outcomes": outcomes,
    })

    return {"script": llm["script"], "outcomes": outcomes,
            "next_phase": repo.load_player()["current_phase"]}
```

- [ ] **Step 4: 테스트 실행 (pass)**

Run: `cd backend && pytest tests/test_combat.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: `backend/app/api/battle.py` 작성**

```python
from fastapi import APIRouter, HTTPException
from .. import repo, combat, state_machine
from ..models import BattleResponse

router = APIRouter()


@router.post("/battle", response_model=BattleResponse)
async def post_battle():
    player = repo.load_player()
    try:
        state_machine.assert_phase(player["current_phase"], "hero_battle")
    except state_machine.PhaseError:
        raise HTTPException(400, detail={"error": "wrong_phase",
                                          "current_phase": player["current_phase"]})

    heroes = repo.list_alive_heroes()
    if not heroes:
        raise HTTPException(400, detail={"error": "no_hero_present"})
    hero = heroes[0]

    # slice: 가장 최근 sold 무기를 그 용사가 들고 있다고 가정
    sold = repo.list_sold_weapons() if hasattr(repo, "list_sold_weapons") else []
    weapon_id = sold[-1]["id"] if sold else None
    return await combat.run_battle(hero["id"], weapon_id)
```

- [ ] **Step 6: `backend/app/repo.py`에 `list_sold_weapons` 추가**

```python
def list_sold_weapons() -> list[dict[str, Any]]:
    return _client().table("weapons").select("*").eq("owner", "sold").order("id").execute().data
```

- [ ] **Step 7: `backend/app/main.py` 수정 — battle 라우터 등록**

```python
from .api import forge as forge_api, negotiate as negotiate_api, battle as battle_api
...
app.include_router(forge_api.router)
app.include_router(negotiate_api.router)
app.include_router(battle_api.router)
```

- [ ] **Step 8: Commit**

```bash
git add backend/app/combat.py backend/app/api/battle.py backend/app/repo.py backend/app/main.py backend/tests/test_combat.py
git commit -m "feat(backend): combat module and POST /battle endpoint"
```

---

## Task 9: state 조회 + game/reset 엔드포인트

**Files:**
- Create: `backend/app/api/state.py`
- Create: `backend/app/api/game.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: `backend/app/api/state.py` 작성**

```python
from fastapi import APIRouter
from .. import repo

router = APIRouter()


@router.get("/state")
def get_state():
    player = repo.load_player()
    inventory = repo.load_inventory()
    weapons = repo.load_player_weapons()
    heroes = repo.list_alive_heroes()
    return {
        "player": player,
        "inventory": inventory,
        "weapons": weapons,
        "hero": heroes[0] if heroes else None,
    }
```

- [ ] **Step 2: `backend/app/api/game.py` 작성**

```python
import random
from fastapi import APIRouter
from .. import repo

router = APIRouter()


JOBS = ["검사", "법사", "궁수", "성문 문지기", "거렁뱅이", "청소년", "군인"]
NAMES = ["라엘", "다리우스", "에리카", "조나스", "미라", "카엘", "노바"]


@router.post("/game/reset")
def post_reset():
    repo.reset_game()
    rng = random.Random()
    repo.insert_hero({
        "name": rng.choice(NAMES),
        "job": rng.choice(JOBS),
        "str": rng.randint(5, 15),
        "mag": rng.randint(2, 12),
        "gold": rng.randint(500, 2000),
        "mood": rng.choice(["여유로움", "초조함", "들떠있음", "지친 듯"]),
        "personality_tags": rng.sample(["호탕", "깐깐", "소심", "허세", "검소"], k=2),
    })
    return {"ok": True}
```

- [ ] **Step 3: `backend/app/main.py` 수정 — state, game 라우터 등록**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .api import forge as forge_api, negotiate as negotiate_api, battle as battle_api, state as state_api, game as game_api

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


@app.get("/health")
def health():
    return {"ok": True}
```

- [ ] **Step 4: 수동 통합 검증**

Run: `cd backend && uvicorn app.main:app --reload --port 8000`

다른 터미널에서 (Supabase env 채운 상태로):
```
curl -X POST http://localhost:8000/game/reset
curl http://localhost:8000/state
```
Expected: `state` 응답에 player(gold 5000), inventory 7개 항목, weapons 빈 배열, hero 1명 포함.

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/state.py backend/app/api/game.py backend/app/main.py
git commit -m "feat(backend): GET /state and POST /game/reset endpoints"
```

---

## Task 10: 프론트엔드 스캐폴드 + API 클라이언트

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/index.html`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/styles.css`
- Create: `frontend/src/types.ts`
- Create: `frontend/src/api.ts`

- [ ] **Step 1: `frontend/package.json`**

```json
{
  "name": "smith-tycoon-frontend",
  "private": true,
  "version": "0.0.1",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1"
  },
  "devDependencies": {
    "@types/react": "^18.3.12",
    "@types/react-dom": "^18.3.1",
    "@vitejs/plugin-react": "^4.3.3",
    "typescript": "^5.6.3",
    "vite": "^5.4.10"
  }
}
```

- [ ] **Step 2: `frontend/vite.config.ts`**

```typescript
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: "http://localhost:8000", changeOrigin: true, rewrite: (p) => p.replace(/^\/api/, "") },
    },
  },
});
```

- [ ] **Step 3: `frontend/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "jsx": "react-jsx",
    "strict": true,
    "noImplicitAny": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "isolatedModules": true,
    "resolveJsonModule": true
  },
  "include": ["src"]
}
```

- [ ] **Step 4: `frontend/index.html`**

```html
<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>대장장이 Tycoon</title>
</head>
<body>
  <div id="root"></div>
  <script type="module" src="/src/main.tsx"></script>
</body>
</html>
```

- [ ] **Step 5: `frontend/src/types.ts`**

```typescript
export interface Material {
  material_id: number;
  qty: number;
  name: string;
  category: string;
  attribute: string | null;
  base_price: number;
}

export interface Weapon {
  id: number;
  name: string;
  type: string;
  rarity: number;
  sharpness: number;
  attribute: string | null;
  skill: string;
  str_req: number;
  mag_req: number;
}

export interface Hero {
  id: number;
  name: string;
  job: string;
  str: number;
  mag: number;
  gold: number;
  mood: string;
  personality_tags: string[];
  affinity: number;
}

export interface Player {
  id: number;
  gold: number;
  reputation: number;
  current_day: number;
  current_phase: string;
}

export interface StateResponse {
  player: Player;
  inventory: Material[];
  weapons: Weapon[];
  hero: Hero | null;
}

export interface NegotiateResponse {
  negotiation_id: number;
  decision: "accept" | "reject" | "counter";
  counter_price: number | null;
  message: string;
}

export interface BattleResponse {
  script: string;
  outcomes: { hero: string; weapon: string; demon: string };
  next_phase: string;
}
```

- [ ] **Step 6: `frontend/src/api.ts`**

```typescript
import type { StateResponse, Weapon, NegotiateResponse, BattleResponse } from "./types";

const BASE = "/api";

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const r = await fetch(`${BASE}${path}`, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!r.ok) {
    const detail = await r.json().catch(() => ({}));
    throw Object.assign(new Error("api_error"), { detail, status: r.status });
  }
  return r.json();
}

export const api = {
  getState: () => request<StateResponse>("GET", "/state"),
  resetGame: () => request<{ ok: true }>("POST", "/game/reset"),
  forge: (weapon_type: string, materials: { material_id: number; qty: number }[]) =>
    request<Weapon>("POST", "/forge", { weapon_type, materials }),
  negotiate: (weapon_id: number, price_offered: number, player_message: string) =>
    request<NegotiateResponse>("POST", "/negotiate", { weapon_id, price_offered, player_message }),
  finalize: (negotiation_id: number) =>
    request<{ ok: true; next_phase: string }>("POST", "/negotiate/finalize", { negotiation_id }),
  battle: () => request<BattleResponse>("POST", "/battle"),
};
```

- [ ] **Step 7: `frontend/src/styles.css`**

```css
:root { font-family: system-ui, sans-serif; color-scheme: light dark; }
body { margin: 0; }
.app { display: grid; grid-template-columns: 280px 1fr; min-height: 100vh; }
.side { padding: 16px; border-right: 1px solid #ccc; }
.main { padding: 16px; }
.btn { padding: 8px 16px; cursor: pointer; }
.btn[disabled] { opacity: 0.5; cursor: not-allowed; }
.chat { display: flex; flex-direction: column; gap: 8px; max-height: 400px; overflow-y: auto; }
.msg { padding: 8px; border-radius: 6px; }
.msg.player { background: #cfe6ff; align-self: flex-end; }
.msg.hero { background: #efefef; align-self: flex-start; }
.material-row { display: flex; gap: 8px; align-items: center; padding: 4px 0; }
```

- [ ] **Step 8: `frontend/src/main.tsx`**

```typescript
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode><App /></StrictMode>
);
```

- [ ] **Step 9: `frontend/src/App.tsx` (최소 — 다음 task에서 채움)**

```typescript
import { useEffect, useState } from "react";
import { api } from "./api";
import type { StateResponse } from "./types";

export default function App() {
  const [state, setState] = useState<StateResponse | null>(null);

  const refresh = async () => setState(await api.getState());

  useEffect(() => { refresh().catch(() => setState(null)); }, []);

  if (!state) {
    return (
      <div style={{ padding: 24 }}>
        <button className="btn" onClick={async () => { await api.resetGame(); await refresh(); }}>
          새 게임 시작
        </button>
      </div>
    );
  }

  return (
    <div className="app">
      <div className="side">
        <h3>플레이어</h3>
        <p>금화: {state.player.gold}</p>
        <p>평판: {state.player.reputation}</p>
        <p>Phase: {state.player.current_phase}</p>
        <button className="btn" onClick={async () => { await api.resetGame(); await refresh(); }}>
          새 게임
        </button>
      </div>
      <div className="main">
        <pre>{JSON.stringify(state, null, 2)}</pre>
      </div>
    </div>
  );
}
```

- [ ] **Step 10: 의존성 설치 + 개발 서버 띄우기**

Run: `cd frontend && npm install`
Run: `npm run dev`

브라우저로 `http://localhost:5173` 접속. "새 게임 시작" 클릭 → state JSON이 보여야 함.

- [ ] **Step 11: Commit**

```bash
git add frontend/
git commit -m "feat(frontend): Vite + React scaffold and API client"
```

---

## Task 11: SidePanel·ForgePanel·DayRouter

**Files:**
- Create: `frontend/src/components/SidePanel.tsx`
- Create: `frontend/src/components/ForgePanel.tsx`
- Create: `frontend/src/components/DayRouter.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: `frontend/src/components/SidePanel.tsx`**

```typescript
import type { StateResponse } from "../types";

export function SidePanel({ state, onReset }: { state: StateResponse; onReset: () => void }) {
  return (
    <div className="side">
      <h3>플레이어</h3>
      <p>금화: {state.player.gold}</p>
      <p>평판: {state.player.reputation}</p>
      <p>Phase: <code>{state.player.current_phase}</code></p>

      <h4>인벤토리</h4>
      <ul>
        {state.inventory.map((m) => (
          <li key={m.material_id}>{m.name} × {m.qty} <small>({m.category})</small></li>
        ))}
      </ul>

      <h4>진열장</h4>
      {state.weapons.length === 0 ? <p><em>(없음)</em></p> : (
        <ul>
          {state.weapons.map((w) => (
            <li key={w.id}>{w.name} ({w.type})</li>
          ))}
        </ul>
      )}

      <button className="btn" onClick={onReset} style={{ marginTop: 16 }}>새 게임</button>
    </div>
  );
}
```

- [ ] **Step 2: `frontend/src/components/ForgePanel.tsx`**

```typescript
import { useState } from "react";
import { api } from "../api";
import type { Material } from "../types";

const WEAPON_TYPES = ["한손검", "양손검", "한손둔기", "양손둔기", "마법지팡이", "방패", "단도", "표창", "총"];

export function ForgePanel({ inventory, onDone }: { inventory: Material[]; onDone: () => void }) {
  const [picks, setPicks] = useState<Record<number, number>>({});
  const [type, setType] = useState(WEAPON_TYPES[0]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const change = (mid: number, delta: number) => {
    setPicks((p) => {
      const cur = (p[mid] ?? 0) + delta;
      const max = inventory.find((m) => m.material_id === mid)?.qty ?? 0;
      const next = Math.max(0, Math.min(max, cur));
      const out = { ...p };
      if (next === 0) delete out[mid]; else out[mid] = next;
      return out;
    });
  };

  const submit = async () => {
    setBusy(true); setErr(null);
    try {
      const materials = Object.entries(picks).map(([k, v]) => ({ material_id: Number(k), qty: v }));
      if (!materials.length) throw new Error("재료를 1개 이상 선택하세요");
      await api.forge(type, materials);
      onDone();
    } catch (e: unknown) {
      setErr((e as Error).message);
    } finally { setBusy(false); }
  };

  return (
    <div>
      <h2>제작</h2>
      <div>
        무기 종류:
        <select value={type} onChange={(e) => setType(e.target.value)}>
          {WEAPON_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
      </div>

      <h4>재료 선택</h4>
      {inventory.map((m) => (
        <div key={m.material_id} className="material-row">
          <span style={{ flex: 1 }}>{m.name} <small>({m.category}, 보유 {m.qty})</small></span>
          <button className="btn" onClick={() => change(m.material_id, -1)}>−</button>
          <span style={{ width: 24, textAlign: "center" }}>{picks[m.material_id] ?? 0}</span>
          <button className="btn" onClick={() => change(m.material_id, +1)}>+</button>
        </div>
      ))}

      <button className="btn" onClick={submit} disabled={busy} style={{ marginTop: 16 }}>
        {busy ? "제작 중..." : "제작하기"}
      </button>
      {err && <p style={{ color: "red" }}>{err}</p>}
    </div>
  );
}
```

- [ ] **Step 3: `frontend/src/components/DayRouter.tsx`**

```typescript
import type { StateResponse } from "../types";
import { ForgePanel } from "./ForgePanel";
import { NegotiationChat } from "./NegotiationChat";
import { BattleResult } from "./BattleResult";

export function DayRouter({ state, refresh }: { state: StateResponse; refresh: () => void }) {
  const phase = state.player.current_phase;
  if (phase === "forge_open") {
    return <ForgePanel inventory={state.inventory} onDone={refresh} />;
  }
  if (phase === "hero_negotiate") {
    if (!state.hero || state.weapons.length === 0) {
      return <p>준비 안 됨 (용사 또는 무기 없음).</p>;
    }
    return <NegotiationChat hero={state.hero} weapon={state.weapons[0]} onDone={refresh} />;
  }
  if (phase === "hero_battle") {
    return <BattleResult onDone={refresh} />;
  }
  return (
    <div>
      <h2>슬라이스 종료</h2>
      <p>한 번의 vertical slice가 끝났습니다. 새 게임으로 다시 시작할 수 있습니다.</p>
    </div>
  );
}
```

- [ ] **Step 4: `frontend/src/App.tsx` 갱신**

```typescript
import { useEffect, useState } from "react";
import { api } from "./api";
import type { StateResponse } from "./types";
import { SidePanel } from "./components/SidePanel";
import { DayRouter } from "./components/DayRouter";

export default function App() {
  const [state, setState] = useState<StateResponse | null>(null);

  const refresh = async () => setState(await api.getState());
  const reset = async () => { await api.resetGame(); await refresh(); };

  useEffect(() => { refresh().catch(() => setState(null)); }, []);

  if (!state) {
    return (
      <div style={{ padding: 24 }}>
        <button className="btn" onClick={reset}>새 게임 시작</button>
      </div>
    );
  }

  return (
    <div className="app">
      <SidePanel state={state} onReset={reset} />
      <div className="main">
        <DayRouter state={state} refresh={refresh} />
      </div>
    </div>
  );
}
```

- [ ] **Step 5: NegotiationChat·BattleResult 스텁 (Task 12에서 채움)**

`frontend/src/components/NegotiationChat.tsx`:
```typescript
import type { Hero, Weapon } from "../types";
export function NegotiationChat(_: { hero: Hero; weapon: Weapon; onDone: () => void }) {
  return <p>NegotiationChat (Task 12에서 구현)</p>;
}
```

`frontend/src/components/BattleResult.tsx`:
```typescript
export function BattleResult(_: { onDone: () => void }) {
  return <p>BattleResult (Task 13에서 구현)</p>;
}
```

- [ ] **Step 6: 타입 체크 + 수동 확인**

Run: `cd frontend && npx tsc --noEmit`
Expected: 에러 없음.

브라우저에서 새 게임 → ForgePanel이 보이고 재료 선택 후 "제작하기"가 동작해야 함 (phase가 `hero_negotiate`로 바뀜).

- [ ] **Step 7: Commit**

```bash
git add frontend/src/
git commit -m "feat(frontend): SidePanel, ForgePanel, DayRouter wiring"
```

---

## Task 12: NegotiationChat 컴포넌트

**Files:**
- Modify: `frontend/src/components/NegotiationChat.tsx`

- [ ] **Step 1: `frontend/src/components/NegotiationChat.tsx` 작성**

```typescript
import { useState } from "react";
import { api } from "../api";
import type { Hero, Weapon, NegotiateResponse } from "../types";

interface ChatMsg { role: "player" | "hero"; message: string; price?: number | null }

export function NegotiationChat({ hero, weapon, onDone }: { hero: Hero; weapon: Weapon; onDone: () => void }) {
  const [msgs, setMsgs] = useState<ChatMsg[]>([]);
  const [price, setPrice] = useState<number>(500);
  const [text, setText] = useState<string>("");
  const [last, setLast] = useState<NegotiateResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const send = async () => {
    setBusy(true); setErr(null);
    try {
      const res = await api.negotiate(weapon.id, price, text);
      setMsgs((m) => [
        ...m,
        { role: "player", message: text, price },
        { role: "hero", message: res.message, price: res.counter_price },
      ]);
      setLast(res);
      setText("");
      if (res.counter_price) setPrice(res.counter_price);
    } catch (e: unknown) {
      setErr((e as Error).message);
    } finally { setBusy(false); }
  };

  const accept = async () => {
    if (!last) return;
    setBusy(true);
    try { await api.finalize(last.negotiation_id); onDone(); }
    catch (e: unknown) { setErr((e as Error).message); }
    finally { setBusy(false); }
  };

  return (
    <div>
      <h2>협상 — {hero.name} ({hero.job})</h2>
      <p>판매 대상 무기: <strong>{weapon.name}</strong> ({weapon.type}, 희귀도 {weapon.rarity}, 예리도 {weapon.sharpness})</p>
      <p><small>용사 기분: {hero.mood} / 성격: {hero.personality_tags.join(", ")} / 보유 금화: {hero.gold}</small></p>

      <div className="chat">
        {msgs.map((m, i) => (
          <div key={i} className={`msg ${m.role}`}>
            <strong>{m.role === "player" ? "나" : hero.name}:</strong> {m.message}
            {m.price != null && <em> ({m.price} 골드)</em>}
          </div>
        ))}
      </div>

      {last?.decision === "accept" ? (
        <div style={{ marginTop: 16 }}>
          <p>용사가 수락했습니다. 거래를 확정하시겠습니까?</p>
          <button className="btn" onClick={accept} disabled={busy}>확정</button>
        </div>
      ) : last?.decision === "reject" ? (
        <div style={{ marginTop: 16 }}>
          <p>거래가 결렬되었습니다.</p>
          <button className="btn" onClick={onDone}>다음으로</button>
        </div>
      ) : (
        <div style={{ marginTop: 16 }}>
          <div>
            <label>제시 가격:
              <input type="number" value={price} onChange={(e) => setPrice(Number(e.target.value))} />
            </label>
          </div>
          <textarea rows={3} style={{ width: "100%" }} value={text} onChange={(e) => setText(e.target.value)} placeholder="용사에게 한마디" />
          <button className="btn" onClick={send} disabled={busy || !text.trim()}>{busy ? "..." : "제안하기"}</button>
        </div>
      )}
      {err && <p style={{ color: "red" }}>{err}</p>}
    </div>
  );
}
```

- [ ] **Step 2: 수동 검증**

브라우저: 새 게임 → 제작 → 협상 화면에서 가격·메시지 입력 → 응답이 채팅에 표시. accept 시 확정 버튼이 보이고 확정 후 phase가 `hero_battle`로 바뀜.

(LLM이 항상 accept를 반환하지 않을 수 있음 — counter나 reject도 정상 동작 확인.)

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/NegotiationChat.tsx
git commit -m "feat(frontend): NegotiationChat with chat UI and finalize"
```

---

## Task 13: BattleResult 컴포넌트

**Files:**
- Modify: `frontend/src/components/BattleResult.tsx`

- [ ] **Step 1: `frontend/src/components/BattleResult.tsx` 작성**

```typescript
import { useEffect, useState } from "react";
import { api } from "../api";
import type { BattleResponse } from "../types";

export function BattleResult({ onDone }: { onDone: () => void }) {
  const [result, setResult] = useState<BattleResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api.battle().then(setResult).catch((e) => setErr(e.message));
  }, []);

  if (err) return <p style={{ color: "red" }}>전투 실패: {err}</p>;
  if (!result) return <p>전투 중...</p>;

  return (
    <div>
      <h2>전투 결과</h2>
      <p style={{ whiteSpace: "pre-wrap" }}>{result.script}</p>
      <ul>
        <li>용사: <strong>{result.outcomes.hero}</strong></li>
        <li>무기: <strong>{result.outcomes.weapon}</strong></li>
        <li>마왕군: <strong>{result.outcomes.demon}</strong></li>
      </ul>
      <button className="btn" onClick={onDone}>다음으로</button>
    </div>
  );
}
```

- [ ] **Step 2: 수동 검증 — 골든 패스 끝까지**

브라우저:
1. 새 게임
2. ForgePanel에서 재료 2~3개 선택 + 무기 종류 → 제작
3. NegotiationChat에서 가격 제시·대화 → accept면 확정
4. BattleResult에 스크립트와 결과 코드 표시 → 다음으로
5. "슬라이스 종료" 화면

각 단계에서 사이드 패널의 금화·평판·phase가 변하는지 확인.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/BattleResult.tsx
git commit -m "feat(frontend): BattleResult component completing vertical slice"
```

---

## Task 14: 통합 골든 패스 픽스처 테스트

**Files:**
- Create: `backend/tests/test_integration_slice.py`

- [ ] **Step 1: `backend/tests/test_integration_slice.py` 작성**

```python
import pytest
from unittest.mock import patch, MagicMock
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
```

- [ ] **Step 2: 테스트 실행**

Run: `cd backend && pytest tests/test_integration_slice.py -v`
Expected: PASS

- [ ] **Step 3: 전체 테스트 스위트 실행**

Run: `cd backend && pytest -v`
Expected: 모든 테스트 PASS

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_integration_slice.py
git commit -m "test(backend): integration test for full slice golden path"
```

---

## Task 15: 골든 패스 수동 검증 체크리스트

**Files:**
- Create: `docs/superpowers/plans/2026-05-26-mvp-plan1-checklist.md`

- [ ] **Step 1: 체크리스트 문서 작성**

`docs/superpowers/plans/2026-05-26-mvp-plan1-checklist.md`:

```markdown
# Plan 1 수동 검증 체크리스트

실제 LLM API 키로 한 번, 픽스처 모드로 한 번 검증.

## 사전
- [ ] Supabase env 채워짐 (.env)
- [ ] LLM env 채워짐
- [ ] `backend/migrations/001_initial.sql` 실행 완료
- [ ] `uvicorn app.main:app --port 8000` 동작
- [ ] `npm run dev` (frontend) 동작

## 골든 패스 (실제 LLM)
- [ ] http://localhost:5173 → "새 게임 시작"
- [ ] SidePanel에 인벤토리 7종, 금화 5000, 평판 0
- [ ] 재료 2~3개 선택 + 양손검 → "제작하기"
- [ ] SidePanel 진열장에 새 무기 1개. phase가 `hero_negotiate`로
- [ ] NegotiationChat에 용사 정보 표시
- [ ] 가격 1000, "튼튼한 검이오" 입력 → 제안
- [ ] 채팅에 용사 응답이 나타남 (LLM이 생성한 한국어 대사)
- [ ] decision이 accept면 확정 → phase가 `hero_battle`
- [ ] decision이 counter면 카운터 가격 받고 재제안
- [ ] decision이 reject면 다음으로
- [ ] BattleResult에 LLM이 생성한 한국어 뉴스 단락 표시
- [ ] outcomes 코드 3가지 표시
- [ ] "다음으로" → "슬라이스 종료" 화면
- [ ] SidePanel 금화·평판 변화 확인

## 에러 경로
- [ ] 재료 0개 상태에서 제작 시도 → 토스트 (재료 부족)
- [ ] phase 우회 (직접 /battle 호출) → 400
- [ ] LLM 모델명을 잘못된 값으로 → 에러 토스트, 게임 계속 가능 (폴백)

## 정성 점검 (LLM 품질)
- [ ] 협상 대사가 용사 성격에 어울리는가
- [ ] 전투 스크립트가 무기와 적을 모두 언급하는가
- [ ] 같은 시드의 동일 입력에 대해 응답이 너무 균질하지 않은가
```

- [ ] **Step 2: 수동으로 체크리스트 실행 + 결과 기록**

문서를 채워가며 실제 LLM 호출로 한 번 플레이. 발견된 LLM 응답 품질 이슈는 `docs/llm-eval/2026-05-26.md`에 기록.

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/plans/2026-05-26-mvp-plan1-checklist.md
git commit -m "docs: Plan 1 manual golden path checklist"
```

---

## 완료 조건 (Definition of Done)

- 모든 단위·통합 테스트 PASS (`pytest -v` 14+ 테스트)
- 프론트 타입 체크 PASS (`tsc --noEmit`)
- 골든 패스 수동 검증 체크리스트 전부 통과 (실제 LLM)
- 모든 커밋이 main으로 푸시됨
