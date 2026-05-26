# 대장장이 Tycoon (Smith Tycoon)

LLM 기반 NPC 시뮬레이션이 들어간 대장간 운영 타이쿤 프로토타입. 플레이어는 대장장이가 되어 100일 동안 무기를 제작·판매하며 용사를 마왕군과 싸우게 한다. 협상 대사·전투 묘사·별명 부여는 LLM이 생성하고, 결과 코드(생존/사망 등)는 결정론 룰이 정한다.

> **상태**: MVP에서 풀 100일 게임까지 확장 완료. 시그니처 기법·전설 무기 등재·일부 엔딩(누적 수익 1억 등)은 미구현.

---

## 목차

- [게임 한눈에 보기](#게임-한눈에-보기)
- [기술 스택](#기술-스택)
- [디렉토리 구조](#디렉토리-구조)
- [로컬 셋업](#로컬-셋업)
- [실행](#실행)
- [테스트](#테스트)
- [데이터베이스 / 마이그레이션](#데이터베이스--마이그레이션)
- [LLM 호출 정책](#llm-호출-정책)
- [멀티 플레이어 모델](#멀티-플레이어-모델)
- [게임 시스템 상세](#게임-시스템-상세)
- [API 개요](#api-개요)
- [개발 워크플로우 (superpowers)](#개발-워크플로우-superpowers)
- [향후 작업](#향후-작업)

---

## 게임 한눈에 보기

- **장르**: 대장간 운영 타이쿤 + LLM NPC 시뮬레이션
- **플레이 시간**: 최대 100일 (게임 내 일수)
- **하루 루프**: 제작 → 용사1 협상 → 용사1 전투 → 상인 협상 → 용사2 협상 → 용사2 전투 → 제작(2회차) → 용사3 협상 → 용사3 전투 → 하루 요약
- **승리 조건 (구현된 것)**:
  - 🏆 **마왕 토벌** — 최종보스 수르트 처치 즉시 종료
  - 🌒 **외로운 마왕** — 100일 도달 + 중간보스 7명 전원 처치 + 수르트 미처치
- **패배 조건 (구현된 것)**:
  - 🔥 **다 쓰러져가는 대장간은 불타야 해** — 100일 도달 + 중간보스 1–6명 처치 + 수르트 미처치
  - 💤 **정년 퇴직** — 100일 도달 + 중간보스 전원 미처치 + 수르트 미처치
  - 💀 **이기지도 못할 거면서 왜 싸웠어?** — 누적 용사 사망 ≥ 200
  - ⚔️ **우리나라 청년들은 너 때문에 죽은 거야** — 누적 무기 파괴 ≥ 200

---

## 기술 스택

### Backend
- **Python 3.12+**
- **FastAPI** — REST API
- **Supabase (Postgres)** — 데이터 저장. `supabase-py` SDK 사용
- **Pydantic v2** — 모델/설정
- **Pytest + pytest-asyncio** — 144개 자동화 테스트

### Frontend
- **React 18 + TypeScript**
- **Vite 5** — 개발 서버 + 빌드. dev에서 `/api` → `localhost:8000` 프록시
- 외부 UI 라이브러리 없음. 일반 CSS + 인라인 스타일

### LLM
- OpenAI 호환 엔드포인트 사용 (기본 `gpt-4o-mini`)
- 테스트에서는 **fixture 모드**로 실제 호출 없이 미리 저장된 JSON 응답 사용

### Infra
- Supabase 클라우드 인스턴스 (프로젝트 id `lgxjxkiyychicfzwbirp`)
- 마이그레이션 8개 (`backend/migrations/`) — Supabase MCP 또는 Supabase Studio로 적용

---

## 디렉토리 구조

```
.
├── architecture.md              # 게임 설계 문서 (룰북)
├── README.md
├── backend/
│   ├── app/
│   │   ├── api/                 # FastAPI 라우터 (forge, negotiate, battle, merchant, enhance, day, state, game)
│   │   ├── llm/                 # LLM 클라이언트 + 프롬프트 템플릿
│   │   │   ├── client.py
│   │   │   └── prompts/
│   │   ├── auth.py              # X-Player-Nickname 헤더 → player_id 의존성
│   │   ├── bosses.py            # 7대 죄악 + 수르트 정의
│   │   ├── combat.py            # 50종 적, 100일 난이도 곡선, 5행 상성, decide_outcomes
│   │   ├── endgame.py           # 엔딩 detector (post_battle / day_100)
│   │   ├── forge.py             # craft — 재료 → 무기, 효율 소비
│   │   ├── hero_registry.py     # 용사 풀, today_heroes 결정론 시드
│   │   ├── merchant.py          # 상인 일일 인벤토리 생성
│   │   ├── negotiation.py       # 매도/매수/강화 협상 LLM 흐름
│   │   ├── nickname.py          # 별명 부여 조건/LLM
│   │   ├── affinity.py          # 호감도 delta / 가격 ceiling
│   │   ├── day_summary.py       # 하루 통계 집계
│   │   ├── state_machine.py     # phase 전이 (MAX_DAY=100)
│   │   ├── enhancement.py       # 무기 강화 roll
│   │   ├── repo.py              # Supabase 데이터 접근
│   │   ├── models.py            # Pydantic 요청/응답 모델
│   │   └── config.py
│   ├── migrations/              # 001 → 008 SQL
│   ├── seed/materials.json      # 60종 재료 카탈로그
│   ├── tests/
│   │   ├── fixtures/llm/        # LLM 응답 픽스처
│   │   └── test_*.py            # 17개 테스트 모듈, 144개 케이스
│   ├── pyproject.toml
│   └── .venv/
├── frontend/
│   ├── src/
│   │   ├── api.ts               # fetch 래퍼 + X-Player-Nickname 헤더 자동 부착
│   │   ├── auth.ts              # localStorage 닉네임 get/set/clear
│   │   ├── App.tsx              # 닉네임 게이트
│   │   ├── endings.ts           # 6 엔딩 메타 (title/flavor)
│   │   ├── types.ts
│   │   ├── components/
│   │   │   ├── Login.tsx
│   │   │   ├── DayRouter.tsx
│   │   │   ├── SidePanel.tsx
│   │   │   ├── ForgePanel.tsx
│   │   │   ├── NegotiationChat.tsx
│   │   │   ├── EnhanceNegotiation.tsx
│   │   │   ├── BattleResult.tsx
│   │   │   ├── MerchantPanel.tsx
│   │   │   ├── MerchantNegotiation.tsx
│   │   │   ├── DaySummary.tsx
│   │   │   └── GameOver.tsx
│   │   └── styles.css
│   ├── package.json
│   ├── tsconfig.json
│   └── vite.config.ts
└── docs/superpowers/            # spec/plan 문서 (개발 프로세스 산출물)
    ├── specs/
    └── plans/
```

---

## 로컬 셋업

### 1. 사전 요구사항

- Python 3.12 이상
- Node.js 20 이상 + npm
- Supabase 프로젝트 (또는 본 프로젝트의 클라우드 인스턴스 접근 권한)
- OpenAI 호환 LLM 엔드포인트 (개발 중엔 fixture 모드로 우회 가능)

### 2. 환경 변수

`backend/.env` 파일 생성:

```
SUPABASE_URL=https://<project>.supabase.co
SUPABASE_SERVICE_KEY=<service_role_key>
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=<openai_or_compatible_key>
LLM_MODEL=gpt-4o-mini
# 픽스처 모드 (테스트/개발) — 실제 LLM 호출 없이 미리 저장된 JSON 사용
# LLM_FIXTURE_DIR=tests/fixtures/llm
```

`pytest`는 conftest가 `LLM_FIXTURE_DIR`을 자동으로 fixture 디렉토리로 설정하므로 별도 작업 불필요. 실 게임 플레이 시에는 `LLM_API_KEY`가 필요.

### 3. 백엔드 설치

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 4. 프론트엔드 설치

```bash
cd frontend
npm install
```

### 5. 데이터베이스 적용

`backend/migrations/`의 001 → 008을 순서대로 Supabase에 적용. Supabase Dashboard의 SQL Editor에서 붙여넣어 실행하거나, Supabase CLI:

```bash
supabase db push --linked
```

또는 본 저장소가 사용 중인 Supabase MCP 서버를 통해서 `apply_migration` 호출.

`materials` 시드는 별도 적용 필요:

```bash
# Supabase SQL Editor에서
-- seed/materials.json의 60개 row를 materials 테이블에 insert
```

(편의를 위한 일회용 시드 스크립트는 없음. JSON을 `INSERT INTO materials VALUES (...)`로 변환해 실행.)

---

## 실행

### 백엔드 (FastAPI)

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

- http://localhost:8000/docs — Swagger UI
- http://localhost:8000/openapi.json — OpenAPI 스펙

### 프론트엔드 (Vite)

```bash
cd frontend
npm run dev
```

- http://localhost:5173 — 게임 UI
- Vite의 `/api` 프록시가 자동으로 백엔드(`localhost:8000`)로 포워딩

### 빌드 (정적 배포용)

```bash
cd frontend
npm run build
# → frontend/dist/
```

---

## 테스트

### 백엔드

```bash
cd backend
source .venv/bin/activate
python -m pytest -q             # 144 tests
python -m pytest tests/test_bosses.py -v   # 특정 모듈
python -m pytest -k boss -v     # 키워드 매칭
```

테스트는 **실제 Supabase에 닿지 않는다**. 각 통합 테스트는 `FakeRepo`(in-memory)를 `unittest.mock.patch`로 주입해서 사용. LLM은 픽스처 응답으로 대체. 따라서 `.env` 없이도 통과.

### 프론트엔드

```bash
cd frontend
npx tsc --noEmit                # 타입 체크
```

E2E/visual 자동 테스트는 없음. 라이브 동작 확인은 dev server에서 수동.

---

## 데이터베이스 / 마이그레이션

마이그레이션은 idempotent하지 않으므로 한 번씩 차례대로 적용. 누적 변경:

| # | 파일 | 내용 |
|---|---|---|
| 001 | `001_initial.sql` | players, weapons, materials, inventory, heroes, negotiations, battles 테이블 |
| 002 | `002_daily_loop.sql` | day_events, merchants_today 추가 |
| 003 | `003_meta.sql` | negotiations.finalized (멱등성) |
| 004 | `004_effort.sql` | players.effort (0–100) |
| 005 | `005_multi_player.sql` | players.nickname (unique) + 전 데이터 wipe |
| 006 | `006_players_id_identity.sql` | players.id에 generated always as identity |
| 007 | `007_heroes_player_id.sql` | heroes.player_id 컬럼 (멀티 플레이어 진작에 빠진 부분 보완) |
| 008 | `008_endgame.sql` | players.heroes_died_total, weapons_destroyed_total, ending_kind |

### 주요 테이블 요약

- **`players`** — 닉네임 단위 세이브. gold, reputation, craft_power, effort, current_day, current_phase, 누적 카운터, ending_kind.
- **`materials`** — 60종 재료 카탈로그 (전역, 플레이어 무관).
- **`inventory`** — 플레이어별 재료 보유 (composite PK).
- **`weapons`** — 제작·매도·강화된 무기. attribute, rarity, sharpness, materials_used (jsonb), enhancement_level.
- **`heroes`** — 용사 인스턴스. affinity, history, nickname, held_weapon_id, return_day.
- **`negotiations`** — 협상 라운드 기록.
- **`battles`** — 전투 결과 + 적 정보.
- **`day_events`** — 하루 안의 모든 이벤트 (forge / sale / buy / battle / boss_kill / surt_kill / nickname / skip / reject / hero_roster).
- **`merchants_today`** — 일일 상인 인벤토리 캐시.

---

## LLM 호출 정책

LLM이 결과를 결정하지 않는다. **서버가 결정론 룰로 결과 코드를 정하고, LLM은 그 결과에 살을 붙이는 텍스트만 생성**한다.

| 호출 지점 | 입력 | 출력 | 결정론 보장 |
|---|---|---|---|
| 무기 이름 | 재료 리스트 | 이름 1개 | 이름이 게임 룰에 영향 없음 |
| 무기 스킬 | 재료 + 희귀도/예리도 | 스킬 텍스트 | 텍스트만, 효과 X |
| 협상 라운드 | 용사/무기/이전 라운드 + 시세·호감도 | 응답 + decision(accept/reject/counter) | 가격은 서버가 clamp, decision도 서버가 재검증 |
| 전투 묘사 | 용사/무기/적/이미 결정된 결과 코드 | 뉴스 스크립트 | 결과 코드는 LLM 이전에 결정됨 |
| 별명 | 용사 + 최근 처치한 적 종류 | 후보 3개 → 랜덤 1개 | — |

전투의 outcomes(`hero/weapon/demon`)는 `combat.decide_outcomes`가 정한다. LLM이 다른 outcomes를 같이 반환해도 서버가 무시한다 (`combat.py:105` 주석).

---

## 멀티 플레이어 모델

각 플레이어는 **닉네임 하나로 구분되는 독립 세이브**를 가진다. 비밀번호·인증 없음 — 프로토타입 수준.

- 프론트엔드: 첫 접속 시 닉네임 입력 → localStorage 저장
- 모든 API 요청에 `X-Player-Nickname` 헤더 자동 부착
- 백엔드 `auth.current_player` 의존성이 헤더를 검증(트림, 1–20자, 대소문자 구분)하고 player row를 조회·자동 생성
- 닉네임 충돌 시 같은 row 재사용 (같은 사람이라고 가정)
- `/game/reset`은 호출한 닉네임의 세이브만 초기화

NPC 시드는 `(player_id, day)` 결정론:
- `hero_registry.heroes_for_today(player_id, day)`: `seed = (player_id * 1_000_003 + day * 31 + slot * 7) & 0xFFFFFFFF`
- `merchant.generate_today(player_id, day)`: `seed = (player_id * 1_000_003 + day * 31 + 7) & 0xFFFFFFFF`

→ 같은 플레이어 + 같은 날 = 같은 용사·상인. 다른 플레이어는 다른 풀.

---

## 게임 시스템 상세

### 재료 (60종)

- **일반 25종** — 금속(철, 강철, 청동, 백금...), 목재(나뭇가지, 대나무, 흑단...), 광물(점토, 화강암, 모래...), 액체(빙정수, 산호...), 기타(천, 왁스).
- **이상한 15종** — 머리카락, 손톱조각, 깨진 거울, 곰팡이 핀 빵 등 일상 잡동사니. 매우 저렴.
- **특수 12종** — 루비, 미스릴, 오리하르콘, 천공석 등 보석·희귀 금속.
- **전설 8종** — 드래곤의 깃털, 신의 눈물, 세계수의 잎 등 신화적 아이템.

각 재료는 5행 속성(금/바람/흙/물/불) 또는 null. 분포는 60종 중 금 12 / 바람 10 / 흙 8 / 불 8 / 물 9 / null 13.

**시작 인벤토리**: 매번 일반 4종 × 3개 + 이상한 2종 × 2개를 카탈로그에서 랜덤 추출. 닉네임마다, `/game/reset`마다 다름.

### 노력 (effort)

플레이어 스태미나. 최대 100, 시작 50.

| 동작 | 노력 변화 |
|---|---|
| 일반 재료 1개 제작 소비 | −6/개 |
| 이상한 재료 1개 제작 소비 | −3/개 |
| 특수 재료 1개 제작 소비 | −10/개 |
| 전설 재료 1개 제작 소비 | −20/개 |
| 시세 ≥130%로 판매 finalize | +10 |
| 시세 ≥200%로 판매 finalize | +20 |

**부족 페널티** (소비량 > 보유 노력 시):
- 부족량 1–10 → 결과물 예리도·희귀도 ×0.7
- 부족량 >10 → ×0.3

자연 회복 없음. 비싸게 팔아서 회복하는 게 사실상 유일한 자원 순환.

### 협상

**매도** (플레이어 → 용사):
- 라운드 1: 플레이어가 가격 제시
- LLM이 accept / counter / reject 판단. counter면 라운드 반복.
- 가격은 서버가 시세 대비 0.1× ~ 5×로 clamp.
- 용사의 카운터는 시간이 갈수록 단조 비감소 (자기 의향가 후퇴 금지).
- 호감도 ≥ +50: 시세 +10%까지 자동 수락.
- 호감도 ≤ −50: 첫 라운드부터 즉시 거절 ("당신과는 거래하지 않겠소"), 평판 변화 없음.

**매수** (플레이어 → 상인):
- 라운드 1: 선택 재료/무기 묶음 → 상인이 total 제시
- 협상 이후 거절 시 평판 −1 (즉시 거절은 예외)

**강화** (재방문한 용사가 보유 무기를 강화 의뢰):
- 무기 1개 + 인벤토리 재료 1–3개 + 협상한 비용 골드
- 카테고리별 예리도/희귀도 Δ (일반 +1–3, 특수 +3–7, 전설 +7–15 등)
- 매번 성공, 폭만 랜덤

### 호감도

거래·전투마다 −100 ~ +100 누적. 트리거:
- 적정가 거래 (시세 ±10%): +5
- 후한 거래 (시세 −10% 미만): +10
- 바가지 (시세 +20% 초과): −10
- 무기 파괴: −5
- (연속 생존 + 마왕 처치 + 호감도 ≥20 → 별명 부여 트리거)

### 적 (50종) + 5행 상성

5단계 티어 + day별 난이도 곡선으로 등장 풀이 자연스럽게 변함.

| 티어 | 난이도 mid | 종수 | 예시 |
|---|---|---|---|
| T1 잡몹 | ~7 | 15 | 고블린, 슬라임, 박쥐, 좀비, 스켈레톤 |
| T2 중하 | ~20 | 12 | 늑대인간, 인큐버스, 진흙 골렘 |
| T3 중급 | ~37 | 10 | 서큐버스, 가고일, 와이번 새끼 |
| T4 상급 | ~58 | 8 | 와이번, 케르베로스, 미노타우로스 |
| T5 거인 | ~82 | 5 | 빙룡, 화염 거인, 강철 골렘왕 |

**100일 난이도 곡선** (`combat.difficulty_range`):
- Day 1–5: MVP 곡선 (1,10) ~ (20,40)
- Day 6–99: (20,40) → (75,95) 선형 보간
- Day 100+: (75,95) 캡

**5행 사이클**: `금 → 바람 → 흙 → 물 → 불 → 금` (각 원소가 다음을 억제). 무기가 적을 억제하면 `power × 1.3`, 역이면 `× 0.7`. BattleResult UI에 "상성 우위 +30%" / "상성 열세 −30%" 라벨로 표시.

### 보스 (8명)

7대 죄악(중간보스) + 수르트(최종보스). 일반 적 슬롯에서 확률적으로 등장.

| 순서 | 이름 | 죄악 | 속성 | 난이도 |
|---|---|---|---|---|
| 1 | 벨페고르 | 나태 | 흙 | 70 |
| 2 | 벨제붑 | 폭식 | 바람 | 75 |
| 3 | 맘몬 | 탐욕 | 금 | 78 |
| 4 | 레비아탄 | 질투 | 물 | 82 |
| 5 | 아스모데우스 | 색욕 | 불 | 85 |
| 6 | 사탄 | 분노 | 불 | 90 |
| 7 | 루시퍼 | 교만 | 금 | 95 |
| F | 수르트 | — | 불 | 110 |

**등장 확률 (전투당)**:
- Day < 40: 0%
- Day 40–59: 5%
- Day 60–79: 10%
- Day 80–89: 25%
- Day 90+: 100%
- Day 100+: 무조건 수르트

**선택 규칙**: 살아있는 중간보스 중 가장 약한 (낮은 난이도) 하나. 7명 다 처치되면 다음 보스 슬롯은 수르트.

처치 시: 평판 +10 보너스, `day_events`에 `boss_kill` 기록(수르트는 추가로 `surt_kill`).

### 엔딩 6종

`combat.run_battle` 끝과 `api/day.post_next_day` 진입 시점에서 검사. 첫 매치 즉시 게임 종료.

| 우선순위 | id | 트리거 | 결과 |
|---|---|---|---|
| 1 | `surt_killed` | 수르트 처치 | 🏆 승리 |
| 2 | `youth_blood` | heroes_died_total ≥ 200 | 💀 패배 |
| 3 | `weapons_broken` | weapons_destroyed_total ≥ 200 | ⚔️ 패배 |
| 4 | `lonely_demon` | day == 100 + 중간보스 7명 처치 + 수르트 alive | 🌒 승리 |
| 5 | `forge_burns` | day == 100 + 중간보스 1–6명 처치 + 수르트 alive | 🔥 패배 |
| 6 | `retirement` | day == 100 + 중간보스 0명 + 수르트 alive | 💤 패배 |

GameOver 화면에 엔딩 제목/플레이버 + 최종 통계(Day, 골드, 평판, 보스 처치 수, 사망 용사, 파괴 무기) + "새 게임" 버튼.

---

## API 개요

전 엔드포인트는 헤더 `X-Player-Nickname: <닉네임>` 필수 (없으면 422).

| Method | Path | 설명 |
|---|---|---|
| GET | `/state` | 플레이어, 인벤토리, 진열장, 현재 hero/merchant, boss_kill_count |
| POST | `/game/reset` | 닉네임 세이브 초기화 |
| POST | `/forge` | 무기 제작 (재료 → 무기) |
| POST | `/forge/skip` | 제작 phase 종료 |
| POST | `/negotiate` | 매도 협상 라운드 |
| POST | `/negotiate/finalize` | 매도 합의 확정 |
| POST | `/negotiate/player_accept` | 용사 카운터를 플레이어가 수락 |
| POST | `/negotiate/player_reject` | 플레이어가 거절 |
| POST | `/negotiate/skip` | 협상 건너뛰기 (평판 −1) |
| POST | `/battle` | 전투 실행 (script + outcomes + demon + weapon) |
| POST | `/merchant/negotiate` | 상인 매수 협상 |
| POST | `/merchant/negotiate/finalize` | 매수 확정 |
| POST | `/merchant/skip` | 상인 단계 건너뛰기 |
| POST | `/enhance/negotiate` | 강화 협상 |
| POST | `/enhance/finalize` | 강화 확정 |
| POST | `/enhance/skip` | 강화 안 함 |
| GET | `/day/summary` | 하루 통계 |
| POST | `/day/next` | 다음 날 진행 (day==100이면 엔딩 검사) |

Swagger UI(`/docs`)에서 즉시 시도 가능. 헤더는 Swagger의 Authorize에서 안 지원되므로 `curl`로:

```bash
curl -s -H "X-Player-Nickname: Test" http://localhost:8000/state | jq
```

---

## 개발 워크플로우 (superpowers)

본 프로젝트는 [Anthropic Claude Code](https://docs.claude.com/en/docs/claude-code)의 **superpowers** 스킬셋으로 개발됐다. 모든 큰 변경은:

1. **brainstorming** — 사용자와 1문 1답 + 옵션 카드로 설계 확정
2. **spec** — `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md` 작성·커밋
3. **plan** — `docs/superpowers/plans/YYYY-MM-DD-<topic>.md`에 TDD 단계별 구현 플랜
4. **subagent-driven execution** — task마다 새 서브에이전트가 RED→GREEN→COMMIT
5. **PR + 머지**

산출물 위치:

```
docs/superpowers/
├── specs/
│   ├── 2026-05-26-smith-tycoon-mvp-design.md
│   ├── 2026-05-26-mvp-plan2-design.md
│   ├── 2026-05-26-mvp-plan3-design.md
│   ├── 2026-05-26-multi-player-design.md
│   ├── 2026-05-26-bosses-and-attribute-design.md
│   └── 2026-05-26-endgame-design.md
└── plans/
    └── (대응되는 implementation plan들)
```

merged된 PR 히스토리:
- **PR #1** — 멀티 플레이어 (닉네임 기반 독립 세이브)
- **PR #2** — 보스(7대 죄악 + 수르트) + 5행 상성
- **PR #3** — 엔딩 시스템 (6종)

각 PR은 commit history와 spec/plan 문서로 추적 가능.

---

## 향후 작업

architecture.md `§13`, `§14`에 정의되어 있지만 미구현:

- **시그니처 기법** — 동일 (주재료 카테고리 + 속성) 패턴 10회 누적 시 패시브 해금. 최대 3개.
- **전설 무기 등재** — 보스 처치한 무기·5회 연속 생존 무기·최종보스 유효타 무기를 영구 등재. 명예의 전당 UI.
- **나머지 4개 엔딩** — 누적 수익 1억 (현재 `gold`만 있고 누적 추적 X), 한 용사 20회 연속 생존, 50일 이후 연속 20일 무기 파괴 0, 100일 항전.
- **보스 한정 전리품 / LLM 톤 차별화**
- **NewGame+ / 명예의 전당 / 점수 비교**

기타 개선 후보:
- gh CLI 설치 가정 없이 PR 머지 자동화
- E2E 테스트 (Playwright)
- 시드 데이터 자동 적용 스크립트
- 실시간 동기화(여러 탭에서 같은 닉네임)
- 닉네임 정책 강화 (욕설 필터, 길이 외 검증)

---

## 라이선스 / 기여

내부 프로토타입 — 외부 기여 정책 없음. 코드 변경은 위 superpowers 워크플로우를 따른다.
