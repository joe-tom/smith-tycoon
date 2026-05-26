# 멀티 플레이어 (독립 싱글 세이브) — 설계

> 닉네임 기반 다중 세이브. 각 플레이어는 자신만의 골드/노력/인벤토리/용사/마왕군을 가짐. 인증·과금·실시간 동기화 없음. 프로토타입 수준.

## 1. 결정 요약

| 결정 | 값 |
|---|---|
| 멀티 의미 | 각자 독립 싱글플레이 세이브 |
| 인증 | 닉네임만 (비밀번호 없음) |
| 세션 전달 | HTTP 헤더 `X-Player-Nickname` + 프론트 localStorage |
| NPC 시드 | `hash((player_id, day))` — 플레이어마다 다른 용사·상인 |
| 기존 데이터 | 마이그레이션 시 전부 와이프 |
| `/game/reset` 범위 | 호출한 닉네임의 세이브만 |

## 2. DB

### 2.1 마이그레이션 005
- 모든 게임 테이블(`day_events`, `merchants_today`, `battles`, `negotiations`, `heroes`, `weapons`, `inventory`, `players`) row 삭제. `materials`는 보존.
- `players` 테이블에 컬럼 추가:
  ```sql
  alter table players add column nickname text unique not null;
  ```
- 기존 `players.id`는 그대로 PK(auto-increment bigint). 닉네임은 식별자, FK는 `player_id`.

## 3. 백엔드

### 3.1 신규 모듈 `app/auth.py`
```python
def current_player(x_player_nickname: str = Header(...)) -> dict:
    nickname = x_player_nickname.strip()
    if not nickname or len(nickname) > 20:
        raise HTTPException(400, detail={"error": "invalid_nickname"})
    return repo.get_or_create_player_by_nickname(nickname)
```
- 닉네임 검증: 트림 후 1–20자. **대소문자 구분** (`Bob`과 `bob`은 다른 계정). 그 이상 정책은 두지 않음.

### 3.2 repo 리팩토링
- 상수 `PLAYER_ID` 제거.
- 플레이어 스코프 함수는 모두 첫 인자로 `player_id: int` 받음:
  ```
  load_player, update_player, load_inventory, load_player_weapons,
  insert_weapon, deduct_materials, insert_hero, list_alive_heroes,
  list_alive_heroes_ready, insert_negotiation, insert_battle,
  get_merchant_today, insert_merchant_today, add_inventory,
  insert_day_event, list_day_events, list_sold_weapons,
  count_consecutive_survives, reset_game
  ```
- 단건 ID 기반 함수는 그대로(`get_weapon`, `get_hero`, `get_negotiation`, `update_negotiation`, `update_hero`, `update_weapon`, `transfer_weapon_to_hero`). 프로토타입이라 권한 검증은 생략.
- 신규: `get_or_create_player_by_nickname(nickname) -> dict`. 신규 row일 경우 시작 상태(gold 0, effort 50, day 1, phase forge_open, 초기 인벤토리 시드)까지 한 번에 처리.

### 3.3 호출 계층
- `api/*.py` 모든 엔드포인트가 `player = Depends(current_player)` 주입받음.
- 도메인 모듈(`forge`, `negotiation`, `combat`, `day_summary`, `merchant`, `nickname`, `hero_registry`)은 더 이상 `repo.load_player()`를 직접 호출하지 않고, 호출자(API)에서 받은 `player` dict를 인자로 받음.

### 3.4 NPC 시드 변경
- 파이썬 내장 `hash()`는 `PYTHONHASHSEED` 영향을 받아 프로세스마다 다름 → 결정론적 시드는 안정적 계산을 써야 함.
- `hero_registry.heroes_for_today(player_id, day, count=3)`:
  ```python
  seed = (player_id * 1_000_003 + day) & 0xFFFFFFFF
  ```
- `merchant.generate_today(player_id, day)`: 충돌 회피용 오프셋만 다르게.
  ```python
  seed = (player_id * 1_000_003 + day * 31 + 7) & 0xFFFFFFFF
  ```

### 3.5 `reset_game(player_id)` 동작
- 해당 player_id의 row만 삭제(테이블 순서: `day_events`, `merchants_today`, `battles`, `negotiations`, `heroes`, `weapons`, `inventory`).
- `players` row는 유지하고 초기 상태로 update.
- 시작 인벤토리 재시드.
- `materials`는 건드리지 않음.

## 4. 프론트엔드

### 4.1 신규 `src/auth.ts`
- `getNickname() / setNickname(name) / clearNickname()` (localStorage 키 `smith-tycoon:nickname`).

### 4.2 `src/api.ts` 수정
- 모든 fetch가 `X-Player-Nickname` 헤더 자동 부착. 닉네임이 없으면 throw해서 호출 측이 로그인 화면을 띄움.

### 4.3 `App.tsx`
- 닉네임 없음 → `<Login />`.
- 닉네임 있음 → 기존 게임 화면.

### 4.4 신규 `Login.tsx`
- 닉네임 input (1–20자, 트림). 입장 클릭 → `setNickname(name)` → `GET /state` 호출 → 성공 시 메인 화면 전환.

### 4.5 `SidePanel`
- "새 게임" 버튼은 그대로 (`/game/reset`).
- "로그아웃" 버튼 추가: `clearNickname()` → Login 화면.

## 5. 테스트 전략

### 5.1 신규 단위 테스트
- `test_auth.py`: 헤더 없음/빈 닉네임/21자 닉네임 → 400. 정상 닉네임 → 자동 생성. 같은 닉네임 재호출 → 동일 player_id.
- `test_repo_multi.py`: 두 player가 서로의 inventory/weapons/heroes/day_events를 못 봄.
- `test_hero_registry_multi.py`: 같은 day, 다른 player_id → 다른 용사. 같은 player+day → 동일.

### 5.2 기존 테스트 마이그레이션
- `conftest.py`에 fixture `test_player(nickname='test') -> dict` 추가.
- 영향받은 모든 테스트가 fixture 받아 player_id 전달하도록 점진적 수정 (파일 단위로 RED→GREEN).
- 최종적으로 기존 76 + 신규 ~10 테스트 모두 통과.

## 6. 변경 면적 정리

**신규 파일**
- `app/auth.py`
- `migrations/005_multi_player.sql`
- `frontend/src/auth.ts`
- `frontend/src/components/Login.tsx`
- `tests/test_auth.py`, `tests/test_repo_multi.py`, `tests/test_hero_registry_multi.py`

**큰 변경**
- `app/repo.py` (거의 전 함수)
- `app/api/*.py` (모든 엔드포인트에 `Depends(current_player)`)
- `app/{forge,negotiation,combat,day_summary,merchant,nickname,hero_registry}.py` (player_id 전파)
- 기존 76개 테스트 (fixture 적용)

**작은 변경**
- `frontend/src/{App.tsx, api.ts, components/SidePanel.tsx, types.ts}`

## 7. 범위 외 (Plan 5+)

- 비밀번호·OAuth 인증
- 플레이어 간 상호작용(리더보드·관전·거래)
- 동시성/실시간(여러 탭에서 같은 닉네임 동시 조작)
- 권한 검증(다른 player의 weapon_id를 직접 조회·갱신 가능). 프로토타입이라 의도적으로 생략.
