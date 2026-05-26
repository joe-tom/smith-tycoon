# 엔딩 시스템 — 설계

> Plan 5 — 6종 엔딩 (승리 2 / 패배 4) + GameOver UI. 수르트 처치, 100일 도달, 누적 사망·파괴 카운터를 트리거로 사용.

## 1. 결정 요약

| 결정 | 값 |
|---|---|
| 엔딩 개수 | 6 (승리 2 + 패배 4) |
| 트리거 시점 | 전투 직후 + day/next 시 (current_day == 100) |
| 누적 카운터 저장 | `players` 테이블 컬럼 (`heroes_died_total`, `weapons_destroyed_total`) |
| 종료 상태 | `players.ending_kind` (NULL = 진행 중), `current_phase='game_over'` |
| 우선순위 | 첫 매치 즉시 종료 (아래 §2 표 순서) |
| UI 요소 | 제목 + 플레이버 텍스트 + 최종 통계 + 새 게임 버튼 |

## 2. 엔딩 정의 + 우선순위

전투 직후 검사 순서:

| 우선순위 | id | 제목 | 트리거 | 결과 |
|---|---|---|---|---|
| 1 | `surt_killed` | 🏆 마왕 토벌 | 수르트 처치 (`"surt" in defeated_boss_ids`) | 승리 |
| 2 | `youth_blood` | 💀 이기지도 못할 거면서 왜 싸웠어? | `heroes_died_total >= 200` | 패배 |
| 3 | `weapons_broken` | ⚔️ 우리나라 청년들은 너 때문에 죽은 거야 | `weapons_destroyed_total >= 200` | 패배 |

day/next에서 current_day == 100일 때 검사 순서 (surt 아직 살아있을 때):

| 우선순위 | id | 제목 | 트리거 | 결과 |
|---|---|---|---|---|
| 4 | `lonely_demon` | 🌒 외로운 마왕 | 중간보스 7명 전원 처치 | 승리 |
| 5 | `forge_burns` | 🔥 다 쓰러져가는 대장간은 불타야 해 | 중간보스 1–6명 처치 | 패배 |
| 6 | `retirement` | 💤 정년 퇴직 | 중간보스 0명 처치 | 패배 |

플레이버 텍스트는 코드 상수로 저장 (LLM 비호출).

## 3. DB 마이그레이션 008

```sql
alter table players
  add column heroes_died_total       int  not null default 0,
  add column weapons_destroyed_total int  not null default 0,
  add column ending_kind             text;
```

기존 row(있다면)는 default로 자동 채워짐.

## 4. 백엔드

### 4.1 신규 모듈 `app/endgame.py`

상수:
```python
MID_BOSS_IDS = {"belphegor","beelzebub","mammon","leviathan","asmodeus","satan","lucifer"}

ENDINGS: list[dict] = [
    {"id": "surt_killed",    "title": "🏆 마왕 토벌",          "won": True,
     "flavor": "수르트의 화염이 사그라들었다. 7대 죄악도 함께 무너졌고, 인간 세계는 다시 빛을 찾았다. 당신의 망치는 전설이 되었다."},
    {"id": "lonely_demon",   "title": "🌒 외로운 마왕",        "won": True,
     "flavor": "7대 죄악은 모두 무너졌지만 수르트는 끝내 모습을 드러내지 않았다. 100일의 항전은 끝나고, 세상은 마왕 하나만 남긴 채 평온해졌다."},
    {"id": "forge_burns",    "title": "🔥 다 쓰러져가는 대장간은 불타야 해", "won": False,
     "flavor": "100일이 지났지만 수르트는 건재하다. 절반의 죄악을 베어낸 당신의 무기들은 영광스럽지만, 정작 마왕은 닿지 못한 곳에 있다. 대장간 문을 닫을 시간이다."},
    {"id": "retirement",     "title": "💤 정년 퇴직",          "won": False,
     "flavor": "100일 동안 망치질만 했다. 단 한 명의 죄악도 무너뜨리지 못했고 수르트는 더더욱. 당신은 평범한 대장장이로 늙어간다."},
    {"id": "youth_blood",    "title": "💀 이기지도 못할 거면서 왜 싸웠어?", "won": False,
     "flavor": "200명의 용사가 당신 손에서 무기를 받았고, 200명이 돌아오지 못했다. 마을 입구마다 곡소리가 그치지 않는다."},
    {"id": "weapons_broken", "title": "⚔️ 우리나라 청년들은 너 때문에 죽은 거야", "won": False,
     "flavor": "당신이 만든 무기 200개가 마왕군 앞에서 부러졌다. 살아 돌아온 용사들의 손에는 부러진 자루만 남았고, 그들의 분노는 당신을 향한다."},
]
```

함수:
```python
def detect_post_battle(player: dict, defeated_boss_ids: set[str]) -> str | None:
    if "surt" in defeated_boss_ids:
        return "surt_killed"
    if player.get("heroes_died_total", 0) >= 200:
        return "youth_blood"
    if player.get("weapons_destroyed_total", 0) >= 200:
        return "weapons_broken"
    return None

def detect_day_100(player: dict, defeated_boss_ids: set[str]) -> str | None:
    if "surt" in defeated_boss_ids:
        return None
    mid_dead = len(defeated_boss_ids & MID_BOSS_IDS)
    if mid_dead == 7: return "lonely_demon"
    if mid_dead >= 1: return "forge_burns"
    return "retirement"

def apply_ending(player_id: int, ending_id: str) -> None:
    from . import repo
    repo.update_player(player_id, ending_kind=ending_id, current_phase="game_over")
```

### 4.2 `combat.run_battle` 수정

`apply_outcomes(outcomes)` 결과로 누적 카운터 증가 + ending 체크.

```python
delta = apply_outcomes(outcomes)
if outcomes["demon"] == "killed" and demon.get("is_boss"):
    delta["reputation"] += 10

extra = {}
if outcomes["hero"] == "died":
    extra["heroes_died_total"] = player["heroes_died_total"] + 1
if outcomes["weapon"] == "destroyed":
    extra["weapons_destroyed_total"] = player["weapons_destroyed_total"] + 1

repo.update_player(pid,
    reputation=player["reputation"] + delta["reputation"],
    current_phase=state_machine.next_phase(player["current_phase"]),
    **extra)
```

전투 끝(battle row + day_event 기록 후, boss_kill 이벤트 기록 후) 에서 ending 검사:

```python
post_player = repo.load_player(pid)
ending = endgame.detect_post_battle(
    post_player, repo.list_defeated_boss_ids(pid)
)
if ending:
    endgame.apply_ending(pid, ending)
    return {"script": script, "outcomes": outcomes, "demon": demon,
            "next_phase": "game_over"}
```

(기존 return 값에서 next_phase만 'game_over'로 바뀜.)

### 4.3 `api/day.py post_next_day` 수정

```python
def post_next_day(player: dict = Depends(current_player)):
    if player["current_phase"] != "day_summary":
        raise HTTPException(400, detail={"error": "wrong_phase", ...})
    if player["current_day"] == 100:
        defeated = repo.list_defeated_boss_ids(player["id"])
        ending = endgame.detect_day_100(player, defeated)
        if ending:
            endgame.apply_ending(player["id"], ending)
            return {"ok": True, "ending": ending,
                    "current_day": 100, "current_phase": "game_over"}
    # 기존 advance 로직
    state_machine.advance_to_next_day(player)
    repo.update_player(player["id"],
                       current_day=player["current_day"],
                       current_phase=player["current_phase"])
    return {"ok": True, "current_day": player["current_day"],
            "current_phase": player["current_phase"]}
```

### 4.4 `api/state.py` 응답에 boss_kill_count 추가

```python
boss_kill_count = len(repo.list_defeated_boss_ids(player["id"]))
return {..., "boss_kill_count": boss_kill_count}
```

## 5. 프론트엔드

### 5.1 신규 `frontend/src/endings.ts`

```typescript
// 백엔드 endgame.ENDINGS와 동일한 한글 문구를 그대로 사용.
// id 키만 동기화 유지.
export const ENDINGS: Record<string, { title: string; won: boolean; flavor: string }> = {
  surt_killed:    { title: "🏆 마왕 토벌",       won: true,
    flavor: "수르트의 화염이 사그라들었다. 7대 죄악도 함께 무너졌고, 인간 세계는 다시 빛을 찾았다. 당신의 망치는 전설이 되었다." },
  lonely_demon:   { title: "🌒 외로운 마왕",     won: true,
    flavor: "7대 죄악은 모두 무너졌지만 수르트는 끝내 모습을 드러내지 않았다. 100일의 항전은 끝나고, 세상은 마왕 하나만 남긴 채 평온해졌다." },
  forge_burns:    { title: "🔥 다 쓰러져가는 대장간은 불타야 해", won: false,
    flavor: "100일이 지났지만 수르트는 건재하다. 절반의 죄악을 베어낸 당신의 무기들은 영광스럽지만, 정작 마왕은 닿지 못한 곳에 있다. 대장간 문을 닫을 시간이다." },
  retirement:     { title: "💤 정년 퇴직",       won: false,
    flavor: "100일 동안 망치질만 했다. 단 한 명의 죄악도 무너뜨리지 못했고 수르트는 더더욱. 당신은 평범한 대장장이로 늙어간다." },
  youth_blood:    { title: "💀 이기지도 못할 거면서 왜 싸웠어?", won: false,
    flavor: "200명의 용사가 당신 손에서 무기를 받았고, 200명이 돌아오지 못했다. 마을 입구마다 곡소리가 그치지 않는다." },
  weapons_broken: { title: "⚔️ 우리나라 청년들은 너 때문에 죽은 거야", won: false,
    flavor: "당신이 만든 무기 200개가 마왕군 앞에서 부러졌다. 살아 돌아온 용사들의 손에는 부러진 자루만 남았고, 그들의 분노는 당신을 향한다." },
};
```

(백엔드 `endgame.ENDINGS`와 별개. id로만 동기화.)

### 5.2 타입 확장 (`types.ts`)

```typescript
export interface Player {
  // 기존
  heroes_died_total: number;
  weapons_destroyed_total: number;
  ending_kind: string | null;
}

export interface StateResponse {
  // 기존
  boss_kill_count: number;
}
```

### 5.3 `GameOver.tsx` 재작성

```tsx
import type { StateResponse } from "../types";
import { ENDINGS } from "../endings";

export function GameOver({ state, onReset }: { state: StateResponse; onReset: () => void }) {
  if (!state.player) return null;
  const kind = state.player.ending_kind;
  const meta = kind ? ENDINGS[kind] : null;
  return (
    <div style={{ padding: 24 }}>
      <h2>{meta?.title ?? "게임 종료"}</h2>
      <p style={{ whiteSpace: "pre-wrap", color: meta?.won ? "#080" : "#a30" }}>
        {meta?.flavor ?? ""}
      </p>
      <div style={{ marginTop: 16, padding: 12, background: "#f5f5f5" }}>
        <p>Day {state.player.current_day} / 100</p>
        <p>골드 {state.player.gold.toLocaleString()} · 평판 {state.player.reputation}</p>
        <p>처치한 보스: {state.boss_kill_count}명</p>
        <p>사망한 용사: {state.player.heroes_died_total}명</p>
        <p>파괴된 무기: {state.player.weapons_destroyed_total}개</p>
      </div>
      <button className="btn" onClick={onReset} style={{ marginTop: 16 }}>새 게임</button>
    </div>
  );
}
```

### 5.4 `DayRouter.tsx`

이미 `phase === "game_over"` 분기 존재. GameOver 호출 시 state 전달하도록만 수정:

```tsx
if (phase === "game_over") return <GameOver state={state} onReset={onReset} />;
```

## 6. 테스트

### 6.1 단위 (`backend/tests/test_endgame.py`)

- `detect_post_battle`:
  - surt 포함 → `"surt_killed"`
  - heroes_died_total=200 → `"youth_blood"`
  - weapons_destroyed_total=200 → `"weapons_broken"`
  - surt 포함 + 두 카운터 모두 200 → `"surt_killed"` (우선)
  - 모든 조건 불충족 → `None`
- `detect_day_100`:
  - surt 포함 → `None`
  - 7 mid + surt alive → `"lonely_demon"`
  - 3 mid + surt alive → `"forge_burns"`
  - 0 mid + surt alive → `"retirement"`

### 6.2 통합 (`test_integration_meta.py`)

- Surt 처치 후 player.ending_kind='surt_killed', current_phase='game_over' 확인.
- 약한 용사 vs 강한 적으로 hero died → heroes_died_total +1 확인.
- (선택) day 100 + 7 mid defeated 상태에서 day/next → ending='lonely_demon'.

### 6.3 FakeRepo 갱신

- `self.player`에 `heroes_died_total: 0, weapons_destroyed_total: 0, ending_kind: None` 필드 추가.
- `update_player`은 이미 `**f`로 받아 `self.player.update(f)` 하므로 추가 변경 불필요.

## 7. 파일 구조

**신규**
- `backend/migrations/008_endgame.sql`
- `backend/app/endgame.py`
- `backend/tests/test_endgame.py`
- `frontend/src/endings.ts`

**수정**
- `backend/app/combat.py` — counters + post-battle ending check
- `backend/app/api/day.py` — day 100 ending check
- `backend/app/api/state.py` — boss_kill_count 응답
- `backend/tests/test_integration_day.py`, `test_integration_meta.py` — FakeRepo 필드
- `frontend/src/types.ts` — Player + StateResponse
- `frontend/src/components/GameOver.tsx` — 재작성
- `frontend/src/components/DayRouter.tsx` — state prop 전달

## 8. 범위 외

- 나머지 4개 엔딩 (누적 수익 1억, 연속 20회 생존, 50일+ 연속 20일 무기 파괴 0, 100일 항전)
- 엔딩 LLM 플레이버 생성
- 명예의 전당 / 점수표
- NewGame+
- ending 발생 후 다른 phase 진입 차단 강화 (state_machine 변경) — 현재는 phase=game_over로 두면 모든 다른 API가 wrong_phase로 거부함 (이미 자연스럽게 작동)
