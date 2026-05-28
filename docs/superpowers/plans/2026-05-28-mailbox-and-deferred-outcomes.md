# 우편함 + 전투 효과 consume 시점 지연 — 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 비동기 전투의 평판/카운터/엔딩/보스이벤트/닉네임을 dispatch 시점에서 떼어 consume 시점(returning_hero advance 또는 death_mail ack)으로 옮기고, 사이드패널에 항상 보이는 "우편함"으로 미수령 출정 결과를 모아 보여준다.

**Problem:**
- 현재 `combat.dispatch_async_battle`이 평판/카운터/엔딩/이벤트를 즉시 적용 → 출정 직후 player 패널에 평판 변화가 보여 결과 스포일러
- 사망 편지(`DeathMailModal`)는 forge_open phase에만 노출돼서 day_summary나 visitor phase에선 안 보임 → 놓치면 다음 forge_open까지 모름

**Architecture:**
1. `pending_outcomes` 테이블에 `deferred_effects JSONB` 컬럼 추가 (migration 014)
2. `dispatch_async_battle`은 outcome 결정 + deferred_effects 작성만, 즉시 변경은 weapon DELETE + hero return_day 만
3. 새 `pending_outcomes.apply_deferred(player_id, outcome_id)`: 평판/카운터/엔딩 적용 + `battle_outcome` day_event 작성
4. consume 트리거 (둘 다 `apply_deferred` 호출 후 `consumed=true` 마킹):
   - `/visitor/current/return` (returning_hero slot 처리)
   - `/mail/{id}/ack` (death_mail 확인)
5. `/mail` GET 엔드포인트 신설: 미수령 pending_outcomes 모두 (kind 무관) 리스트
6. 프론트 `Mailbox` 컴포넌트: SidePanel에 항상 표시. 항목 클릭하면 recap + outcome 보여주고 "확인" 버튼

**Tech Stack:** Python 3.12 + FastAPI + Supabase + Pytest, React 18 + TS

**Spec context:** 기존 async-combat 스펙 (`docs/superpowers/specs/2026-05-28-async-combat-and-variable-day-design.md`)이 "결과 노출 금지 — 평판 변화도 묶어서 dispatch에만" 이라고 명시했으나 실제 코드는 평판을 즉시 적용. 본 계획이 그 의도를 완성한다.

---

## File Structure

**Backend — create**
- `backend/migrations/014_deferred_effects.sql`
- `backend/tests/test_apply_deferred.py`

**Backend — modify**
- `backend/app/combat.py` — `dispatch_async_battle`: 즉시 적용 제거, deferred_effects 작성
- `backend/app/pending_outcomes.py` — `apply_deferred` 함수 추가
- `backend/app/repo.py` — `update_pending_consumed_with_effects` 같은 헬퍼 (또는 기존 `mark_pending_consumed` + `update_pending` 조합)
- `backend/app/api/visitor.py` — `/visitor/current/return`에서 `apply_deferred` 호출
- `backend/app/api/mail.py` — GET `/mail` 엔드포인트 추가, `/mail/{id}/ack`에서 `apply_deferred` 호출
- `backend/app/day_summary.py` — `battle_outcome` 이벤트도 집계 (`dispatch`는 평판 0)
- `backend/app/endgame.py` — 호출 시점 변경 없음 (이미 player row 기준)
- `backend/tests/test_combat_async.py` — 평판/카운터 즉시 적용 안 함 확인
- `backend/tests/test_death_mail.py` — ack 후 평판 적용 확인

**Frontend — create**
- `frontend/src/components/Mailbox.tsx`

**Frontend — modify**
- `frontend/src/types.ts` — `MailEntry` 타입
- `frontend/src/api.ts` — `mailList()` 래퍼
- `frontend/src/components/SidePanel.tsx` — Mailbox 마운트
- `frontend/src/components/DaySummary.tsx` — `battle_outcome` 케이스 추가; `dispatch`에서 rep_delta 제거
- `frontend/src/components/DeathMailModal.tsx` — 기존 동작 유지하되 Mailbox와 중복 OK (forge_open 자동 팝업 + 우편함 영구 노출)

---

### Task 1: 마이그레이션 014 — deferred_effects 컬럼

**Files:**
- Create: `backend/migrations/014_deferred_effects.sql`

```sql
ALTER TABLE pending_outcomes
  ADD COLUMN IF NOT EXISTS deferred_effects JSONB NOT NULL DEFAULT '{}'::jsonb;
```

Commit: `migrate: 014 add pending_outcomes.deferred_effects`

또한 Supabase MCP `apply_migration`으로 원격 적용.

---

### Task 2: FakeRepo + repo 헬퍼

- `tests/fake_repo.py`: `pending_outcomes` insert/update에서 `deferred_effects` 보존
- `backend/app/repo.py`: 기존 `update_pending_resolve_day` 옆에 `update_pending_consumed(outcome_id, applied_effects: dict | None = None)` 추가 (consumed=true + 선택적으로 effects 갱신)
- 또는 단순화: `update_pending(outcome_id, **fields)` 범용 헬퍼

Commit: `repo: support deferred_effects on pending_outcomes`

---

### Task 3: `combat.dispatch_async_battle` 즉시 적용 제거

`backend/app/combat.py:231-340` 전면 수정:

```python
# 변경 후 핵심
deferred = {
    "rep_delta": delta["reputation"],
    "hero_died": outcomes["hero"] == "died",
    "weapon_destroyed": outcomes.get("weapon") == "destroyed",
    "boss_kill": (
        {"boss_id": demon["boss_id"], "name": demon["type"], "sin": demon.get("sin")}
        if outcomes["demon"] == "killed" and demon.get("is_boss") else None
    ),
    "nickname": picked_nickname_or_None,  # nickname 결정도 미리 해두지만 hero update는 deferred
}
saved = repo.insert_pending_outcome({
    ...기존 필드...,
    "deferred_effects": deferred,
})
# 즉시 적용 — weapon DELETE, hero return_day 세팅 (pending_outcomes.dispatch_hero에 이미 있음)
# 제거 — repo.update_player(reputation=..., heroes_died_total=..., weapons_destroyed_total=...)
# 제거 — repo.insert_day_event(kind="boss_kill", ...)
# 제거 — endgame.detect_post_battle + apply_ending
# 제거 — nickname update_hero(nickname=...) + insert_day_event(kind="nickname",...)
# 유지 — dispatch 이벤트 (단 payload에서 rep_delta 제거)
repo.insert_day_event(pid, day=..., phase=..., kind="dispatch",
                      payload={"battle_id": battle_row["id"], "hero_id": hero_id})
```

테스트 (`backend/tests/test_combat_async.py`):
- `dispatch_async_battle` 직후 `player.reputation` 변동 없음
- `player.heroes_died_total` 변동 없음
- `pending_outcomes[-1]["deferred_effects"]["rep_delta"]` 적절히 세팅
- `day_events` 중 `dispatch` 1개, `boss_kill` 0개 (consume 전)

Commit: `feat(combat): defer rep/counters/events to consume time via deferred_effects`

---

### Task 4: `apply_deferred` 함수

`backend/app/pending_outcomes.py`:

```python
def apply_deferred(player: dict, outcome_id: int) -> dict | None:
    """consume 시점에 호출. deferred_effects를 player에 반영하고 day_event 작성.
    이미 consumed면 no-op. 반환: 적용된 ending 또는 None.
    """
    p = repo.get_pending(outcome_id)
    if not p or p["consumed"]:
        return None
    eff = p.get("deferred_effects") or {}
    pid = player["id"]
    player_now = repo.load_player(pid)

    extra = {"reputation": player_now["reputation"] + int(eff.get("rep_delta", 0))}
    if eff.get("hero_died"):
        extra["heroes_died_total"] = int(player_now.get("heroes_died_total", 0)) + 1
    if eff.get("weapon_destroyed"):
        extra["weapons_destroyed_total"] = int(player_now.get("weapons_destroyed_total", 0)) + 1
    repo.update_player(pid, **extra)

    # battle_outcome 이벤트
    repo.insert_day_event(pid, day=player_now["current_day"],
                          phase=player_now["current_phase"], kind="battle_outcome",
                          payload={"hero_id": p["hero_id"],
                                   "rep_delta": int(eff.get("rep_delta", 0)),
                                   "outcome": p["outcome_json"]})

    # boss_kill 이벤트
    if eff.get("boss_kill"):
        bk = eff["boss_kill"]
        repo.insert_day_event(pid, day=player_now["current_day"],
                              phase=player_now["current_phase"], kind="boss_kill",
                              payload={"boss_id": bk["boss_id"], "boss_name": bk["name"],
                                       "sin": bk.get("sin")})
        # boss row insert? — 기존 combat.py에 있던 로직 옮길 것

    # nickname
    if eff.get("nickname"):
        repo.update_hero(p["hero_id"], nickname=eff["nickname"])
        repo.insert_day_event(pid, day=player_now["current_day"],
                              phase=player_now["current_phase"], kind="nickname",
                              payload={"hero_id": p["hero_id"], "nickname": eff["nickname"]})

    repo.mark_pending_consumed(outcome_id)

    # 엔딩 감지 — consume 후 시점
    post = repo.load_player(pid)
    ending = endgame.detect_post_battle(post, repo.list_defeated_boss_ids(pid))
    if ending:
        endgame.apply_ending(pid, ending)
    return ending
```

테스트 (`backend/tests/test_apply_deferred.py`):
- consume 직후 평판/카운터 정확히 변동
- 두 번 호출해도 멱등 (consumed=True 후 no-op)
- boss_kill effect 시 day_events에 boss_kill 생김
- ending 조건 충족하면 ending 반환

Commit: `feat(pending-outcomes): apply_deferred — consume 시 effects/events 적용`

---

### Task 5: visitor `/current/return` 에서 `apply_deferred` 호출

`backend/app/api/visitor.py`의 `finish_returning_hero`:

```python
@router.post("/current/return")
def finish_returning_hero(player=Depends(current_player)):
    slot = _current_slot(player)
    if slot["kind"] != "returning_hero":
        raise HTTPException(409, "current slot is not returning_hero")
    ending = pending_outcomes.apply_deferred(player, slot["outcome_id"])
    if ending:
        return {"ok": True, "ending": ending}
    _advance_and_save(player)
    return {"ok": True}
```

테스트: 기존 `test_visitor_endpoints.py`에 평판 변동 검증 추가.

Commit: `feat(api): visitor/current/return triggers apply_deferred`

---

### Task 6: `/mail/{id}/ack` 에서 `apply_deferred` 호출

`backend/app/api/mail.py` 수정 + 새 GET `/mail` 엔드포인트:

```python
@router.get("/mail")
def list_mail(player=Depends(current_player)):
    pid = player["id"]
    pending = repo.list_all_pending_unconsumed(pid)  # 새 repo 함수
    return {
        "mail": [
            {"id": p["id"], "kind": p["kind"], "hero_id": p["hero_id"],
             "depart_day": p["depart_day"], "resolve_day": p["resolve_day"],
             "outcome": p["outcome_json"], "weapon_snapshot": p["weapon_snapshot"],
             "deferred_effects": p.get("deferred_effects") or {}}
            for p in pending
        ],
    }


@router.post("/mail/{outcome_id}/ack")
def ack(outcome_id: int, player=Depends(current_player)):
    p = repo.get_pending(outcome_id)
    if not p or p["player_id"] != player["id"]:
        raise HTTPException(404, "mail not found")
    pending_outcomes.apply_deferred(player, outcome_id)
    return {"ok": True}
```

`repo.list_all_pending_unconsumed(player_id)`: `consumed=false AND resolve_day <= current_day`.

Commit: `feat(api): GET /mail list + ack triggers apply_deferred`

---

### Task 7: day_summary `battle_outcome` 집계

`backend/app/day_summary.py`:
- `kind == "dispatch"`: 평판 변동 0 처리 (그냥 카운터만)
- `kind == "battle_outcome"` 추가: `s["rep_delta"] += rep_delta`, `s["rep_breakdown"]["battle"] += rep_delta`, `s["battles"] += 1` (혹은 새 카테고리)

기존 dispatch에서 rep_delta를 읽던 코드 제거.

테스트: 기존 day_summary 테스트에 `battle_outcome` 이벤트 케이스 추가.

Commit: `feat(day-summary): aggregate battle_outcome instead of dispatch rep_delta`

---

### Task 8: 프론트 — `Mailbox` 컴포넌트

`frontend/src/components/Mailbox.tsx`:
- `useEffect`로 `/mail` 폴링 (또는 state refresh 시 동기 호출)
- 항목 리스트 표시: 용사명/출정일/예정 귀환일/kind 아이콘
- 클릭 → expand: outcome 요약 ("토벌 성공" / "사망"), 무기 스냅샷, recap (있으면), 평판 변화
- "확인" 버튼 → `POST /mail/{id}/ack` → state refresh

types.ts `MailEntry` 추가.

`SidePanel.tsx`에 마운트 (항상 보이는 패널).

`DeathMailModal`은 그대로 유지 (forge_open 자동 팝업) — 우편함은 그 외 시점 + 이력 확인용.

Commit: `feat(frontend): Mailbox in side panel — phase-independent pending outcomes view`

---

### Task 9: dispatch 이벤트 포매터 + DaySummary 로그 업데이트

`frontend/src/components/DaySummary.tsx`:
- `case "dispatch"`: "출정: 용사 #N 떠남" (rep 표시 제거)
- `case "battle_outcome"`: "결과 확인: 용사 #N — outcome.hero (평판 ±N)"

Commit: `feat(frontend): event log dispatch/battle_outcome separation`

---

### Task 10: 회귀 + UI 수동 확인

1. `pytest -q` 전부 PASS
2. `npx tsc --noEmit` 깨끗
3. UI 시나리오:
   - 용사 출정 → 평판 즉시 안 변하는지
   - 우편함에 "용사 #N (귀환 예정 day Y)" 표시되는지
   - 귀환일 도달 후 returning_hero 슬롯 처리 → 평판 변동 + battle_outcome 이벤트 로그
   - 사망 케이스 → 우편함에 빨간 아이콘, 확인 시 평판 적용

---

## 마이그레이션 적용 순서

1. 코드 머지 전: Supabase MCP로 014 적용
2. 코드 머지
3. 기존 데이터: 이미 `dispatch` 시점에 평판이 반영된 pending_outcome들은 deferred_effects가 비어있음 → consume해도 평판 0 적용 (이중 적용 방지). 깔끔하게 가려면 014 적용 전 모든 player 데이터 리셋 권장 (or migration 014에서 기존 pending_outcomes를 consumed=true로 마킹).

---

## 범위 밖 (이번 계획에서 OUT)

- 우편함 알림 배지(미수령 N개) — 다음 패스
- 우편함 정렬/필터(귀환일순/사망만) — 단순 리스트로 시작
- 평판 즉시 적용이 필요한 다른 액션 (skip, reject) — 변경 없음 (즉시 적용 유지)
- combat.py 외 동기 전투 잔존 코드 정리 (현재 `run_battle`는 이미 dead, 점진 정리)
