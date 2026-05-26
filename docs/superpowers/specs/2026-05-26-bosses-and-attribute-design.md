# 보스 + 5행 상성 — 설계

> Plan 4 — 마왕군 7대 죄악 중간보스 + 최종보스 수르트, 5행 속성 상성 데미지 보정.

## 1. 결정 요약

| 결정 | 값 |
|---|---|
| 보스 등장 방식 | 일반 적과 같은 슬롯. roll_demon이 확률적으로 보스 반환 |
| 등장 확률 (전투당) | day<40: 0%, 40–59: 5%, 60–79: 10%, 80–89: 25%, 90–99: 100%, 100+: 100% |
| 보스 선택 | 약 → 강 순서 고정. 가장 약한 alive mid-boss |
| 수르트 등장 트리거 | day≥100 또는 mid-boss 7명 전원 처치 |
| 게임 승리 | 수르트 처치 (지금은 기록만, 엔딩 UI는 다음 플랜) |
| 5행 공식 | 무기가 적 억제: power ×1.3 / 역억제: ×0.7 / 그 외: ×1.0 |
| 보스 정의 저장 | 코드 상수 (`bosses.py`), DB 테이블 신규 X |
| 처치 이력 | `day_events.kind='boss_kill'` payload `{boss_id, boss_name, ...}` |

## 2. 보스 정의

```
MID_BOSSES = [
  {"boss_id": "belphegor",  "name": "벨페고르",    "sin": "나태", "attribute": "흙",   "difficulty": 70},
  {"boss_id": "beelzebub",  "name": "벨제붑",      "sin": "폭식", "attribute": "바람", "difficulty": 75},
  {"boss_id": "mammon",     "name": "맘몬",        "sin": "탐욕", "attribute": "금",   "difficulty": 78},
  {"boss_id": "leviathan",  "name": "레비아탄",    "sin": "질투", "attribute": "물",   "difficulty": 82},
  {"boss_id": "asmodeus",   "name": "아스모데우스","sin": "색욕", "attribute": "불",   "difficulty": 85},
  {"boss_id": "satan",      "name": "사탄",        "sin": "분노", "attribute": "불",   "difficulty": 90},
  {"boss_id": "lucifer",    "name": "루시퍼",      "sin": "교만", "attribute": "금",   "difficulty": 95},
]

FINAL_BOSS = {"boss_id": "surt", "name": "수르트", "sin": None, "attribute": "불", "difficulty": 110}
```

정렬 순서가 곧 약→강 등장 순서. `weakest_alive(defeated_ids)`는 이 리스트에서 defeated_ids에 없는 첫 번째 항목 반환.

## 3. 등장 확률·선택 로직

```python
def boss_spawn_chance(day: int) -> float:
    if day < 40: return 0.0
    if day < 60: return 0.05
    if day < 80: return 0.10
    if day < 90: return 0.25
    return 1.0  # 90+ 항상

def roll_demon(day, defeated_boss_ids, seed=None):
    rng = random.Random(seed)
    surt_dead = "surt" in defeated_boss_ids
    alive_mid = [b for b in MID_BOSSES if b["boss_id"] not in defeated_boss_ids]

    # day 100+ → 수르트 무조건 (아직 살아있으면)
    if day >= 100 and not surt_dead:
        return _to_demon_dict(FINAL_BOSS, is_boss=True)

    # 모든 mid-boss 처치 → 수르트 조기 등장
    if not alive_mid and not surt_dead:
        return _to_demon_dict(FINAL_BOSS, is_boss=True)

    # 확률적 mid-boss 스폰
    if alive_mid and rng.random() < boss_spawn_chance(day):
        return _to_demon_dict(alive_mid[0], is_boss=True)

    # 일반 적 (기존 로직)
    return _roll_regular_demon(day, rng)
```

`_to_demon_dict`은 boss 또는 regular demon dict를 동일 형태 (`{type, attribute, difficulty, is_boss?, boss_id?, sin?}`)로 변환.

## 4. 5행 상성

architecture.md §3.4 사이클: `금 → 바람 → 흙 → 물 → 불 → 금`.

```python
CYCLE_NEXT = {"금": "바람", "바람": "흙", "흙": "물", "물": "불", "불": "금"}

def attribute_bonus(weapon_attr, demon_attr) -> float:
    if not weapon_attr or not demon_attr:
        return 1.0
    if CYCLE_NEXT.get(weapon_attr) == demon_attr: return 1.3   # 무기가 적 억제
    if CYCLE_NEXT.get(demon_attr) == weapon_attr: return 0.7   # 적이 무기 억제
    return 1.0
```

`decide_outcomes`의 power 계산 직후 곱함:
```python
power = hero_power(hero, weapon)
power *= attribute_bonus(weapon.get("attribute") if weapon else None, demon["attribute"])
```

맨손(weapon=None)은 weapon_attr=None → bonus 1.0.

## 5. 보스 처치 효과

`combat.run_battle` 내 outcomes 처리 직후:

```python
if outcomes["demon"] == "killed" and demon.get("is_boss"):
    repo.insert_day_event(pid, day=player["current_day"], phase=player["current_phase"],
                          kind="boss_kill",
                          payload={"boss_id": demon["boss_id"], "boss_name": demon["type"],
                                   "sin": demon.get("sin"), "battle_id": battle_row["id"]})
    # 일반 적 처치 평판(+1)이 이미 apply_outcomes에서 계산됨. 보스 보너스 +10을 추가.
    delta["reputation"] += 10
```

수르트 처치 시에는 `kind='boss_kill'` 외에 `kind='surt_kill'` 이벤트도 별도 기록 (다음 플랜의 엔딩 시스템이 이걸 찾아 게임 종료 트리거). payload는 동일 정보 + `final: True`.

## 6. 파일 구조

**신규**
- `backend/app/bosses.py` — 상수 + 헬퍼 (`weakest_alive`, `find_boss_by_id`, `is_boss`)
- `backend/tests/test_bosses.py`
- `backend/tests/test_attribute_bonus.py`
- `backend/tests/test_boss_spawn.py`

**수정**
- `backend/app/combat.py` — `attribute_bonus`, `boss_spawn_chance`, `roll_demon` 시그니처 확장, `decide_outcomes`에서 5행 적용, `run_battle`에서 보스 처치 이벤트·보너스 평판
- `backend/app/repo.py` — `list_defeated_boss_ids(player_id) -> set[str]` 신규
- `backend/app/day_summary.py` — `summarize_events`에 boss_kill 카운트, 한글 포맷 추가
- `frontend/src/types.ts` — `Demon`에 `is_boss?`, `boss_id?`, `sin?` 추가
- `frontend/src/components/BattleResult.tsx`: demon 표시에 보스면 ⚜ + 빨강 강조
- `frontend/src/components/DaySummary.tsx`: boss_kill 한글 포맷

## 7. 테스트

신규 단위:
- `test_bosses.py`: 약→강 정렬 검증, weakest_alive 동작 (∅ / 1명 / 7명 처치 케이스), find_boss_by_id
- `test_attribute_bonus.py`: 5×5 매트릭스 + null + 무기 없음 케이스
- `test_boss_spawn.py`:
  - `boss_spawn_chance` 경계 day들 (39/40/59/60/79/80/89/90/99/100)
  - `roll_demon`: day<40 → 항상 일반, day=100 → 수르트, defeated={7 mid} → 수르트, defeated={surt+7} → 일반, 보스 선택 시 alive 중 가장 약한 것

통합:
- `test_integration_day.py`에 Day 100 시나리오 추가 (수르트 등장 → 처치 → day_events에 'surt_kill' 기록)

기존:
- `test_combat.py::test_roll_demon_day_difficulty_range`는 day 1–5라 영향 없음

## 8. 범위 외

- 승리·패배 엔딩 UI (수르트 처치 후 게임 종료 화면)
- 전설 무기 등재 (보스 처치 시 그 무기 등재)
- 보스 한정 전리품·골드 보상
- 보스 LLM 대사 톤 차별화 (현재 fixture는 그대로 사용)
