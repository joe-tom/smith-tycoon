# 전리품 · chitchat · 인내심 — 설계 (2차 배치)

작성일: 2026-05-28
관련 피드백: `docs/feedback/0527.txt` 항목 #4, #5, #6
선행: 1차 배치 (비동기 전투 + 가변 하루 길이)

## 배경

1차 배치로 `returning_hero` 슬롯과 호감도 시스템(±100)이 자리잡았다. 2차는 그 위에 세 가지를 얹는다.

- **#4 재방문 전리품 거래**: 출정에서 돌아온 용사가 적에게서 얻은 재료를 대장장이에게 판다. 사주면 호감도 ↑.
- **#5 chitchat**: 호감도 ≥ 0인 용사와 잡담. 한 문단의 LLM narration이 `heroes.lore`에 누적. 향후 도감 시스템의 입구.
- **#6 인내심 스탯**: 영웅·상인에 인내심을 추가. LLM 페르소나로 시작값 계산, 라운드별 감소, 0 이하면 협상 자동 종료.

셋 다 returning_hero 슬롯 안에서 일어나고 호감도 시스템을 공유하므로 한 묶음으로 설계한다.

## 합의된 결정

1. **메뉴식 슬롯 UX**: 슬롯 진입 시 [무기 판매 / 강화 / 전리품 매수 / 잡담 / 보내기] 메뉴. 액션 후 메뉴로 복귀, "보내기"로만 슬롯 종료. 단 무기 판매 accept는 dispatch와 함께 즉시 슬롯 종료.
2. **chitchat 게이트**: `affinity ≥ 0`. 신규 용사는 affinity=0으로 시작하므로 첫 방문부터 가능. 비호감(<0)으로 떨어진 용사만 잠긴다.
3. **chitchat은 정보 저장만**, 호감도 변화 없음. lore는 JSONB 구조로 저장(향후 도감 확장).
4. **전리품 풀**: 보스 시그니처 + 일반 몹 난이도 기반 하이브리드.
5. **전리품 거래는 새 함수** `step_buy_loot` — step_buy 변형, 호감도 가중 시작가, 매수 시 호감도 +5.
6. **인내심**: 숫자 0-100, 페르소나 기반 시작값 결정, 라운드 -10, ≤30 어조 변화, ≤0 자동 종료.
7. **부상 시 무기**: 같이 destroyed 처리 (1차 보류 사항 정리). 수리 시스템은 yagni.

## 데이터 모델 (마이그레이션 011)

### heroes 컬럼 추가
- `lore JSONB NOT NULL DEFAULT '[]'::jsonb` — chitchat 누적 (`[{day, text, tags?}]`, 최대 20개)
- `loot_pending JSONB NOT NULL DEFAULT '[]'::jsonb` — 다음 방문에 가져올 전리품 (`[{material_id, qty, asking_price}]`)

### negotiations 컬럼 추가
- `patience_start INT`
- `patience_current INT`

인내심은 협상 진행 중에만 의미가 있으므로 `heroes` / `merchants_today`에 별도 컬럼을 두지 않는다. 시작값은 협상 시작 시점에 페르소나/시드에서 계산해 `negotiations.patience_start`에 박는다.

## 슬롯 흐름

```
visitor slot (new_hero | returning_hero) 진입
  │
  ├─ returning_hero면 회고 narration (기존 ReturningHeroPanel 로직)
  │
  ▼
[메뉴]
 ① 무기 판매 (인벤토리 무기 있음)     → NegotiationChat → accept 시 dispatch + slot advance
 ② 무기 강화 (용사가 무기 들고 있음)  → EnhanceNegotiation → accept 시 dispatch + slot advance
 ③ 전리품 매수 (loot_pending 있음)    → LootNegotiation → accept 시 inventory 추가 + 메뉴 복귀
 ④ 잡담 (affinity ≥ 0)               → ChitchatPanel → lore 추가 + 메뉴 복귀
 ⑤ 보내기                            → /visitor/current/{return,skip} → slot advance
```

merchant 슬롯은 기존 MerchantPanel 그대로 (인내심만 추가).

## 인내심 메커니즘

### 시작값 계산 (협상 시작 시 1회)

**영웅**:
```python
base = 50
deltas = {"호탕": +20, "깐깐": -20, "검소": 0, "소심": -10, "허세": -10}
start = base + sum(deltas.get(tag, 0) for tag in hero.personality_tags)
patience_start = max(10, min(90, start))
```

**상인**: 시드 기반 균등 `[30, 70]`. 시드 = `(player_id*1_000_003 + day*31 + merchant_id*7 + 19) & 0xFFFFFFFF`.

`negotiations.patience_start`와 `.patience_current`에 저장.

### 라운드별 감소
- 매 라운드 (player 한 줄 + 상대 한 줄 = 1쌍) `patience_current -= 10`.
- 가격이 직전 라운드 대비 상대에게 유리하게 양보 (상인은 ↓ / 영웅은 ↑) → 감소 -5만.

### 임계값 효과
| 인내심 | 효과 |
|---|---|
| > 30 | 정상. LLM 프롬프트 `patience_level=high` |
| 1–30 | `patience_level=low` → 짜증·재촉 어조 안내 (서버 메커니즘은 동일) |
| ≤ 0 | 자동 reject. day_event `patience_exhausted` 기록. 평판 -1, 호감도 -1. 슬롯은 메뉴 복귀(advance 안 함). |

### LLM 프롬프트
`patience_current`, `patience_level` 둘 다 전달. 어조 가이드만, 결정은 서버.

### UI
협상 화면 상단에 게이지 (high=초록 / mid=노랑 / low=빨강).

## chitchat 메커니즘

### 엔드포인트
`POST /visitor/current/chitchat` body: `{player_message?: string}`

### 서버 처리
1. 슬롯 검증 (hero kind, affinity ≥ 0).
2. LLM 호출:
   - 프롬프트 `chitchat.j2` (신규)
   - 변수: hero 정보, recent_lore (최근 3개), player_message, recent_history (전투 기록 최근 3개)
   - 응답: `{lore_text: "..."}` (한 문단 3~5문장)
3. `heroes.lore`에 `{day, text}` append. 20개 초과 시 오래된 것 drop.
4. 호감도 변화 없음.
5. 응답 반환, 슬롯 advance 안 함.

### 미래 확장 (out of scope)
lore entry에 `tags: [{kind:"enemy"|"location", id:"..."}]` 같은 구조화 필드 추가 가능 (도감 시스템).

## 전리품 시스템

### `loot_table.py` (신규)

```python
BOSS_LOOT = {
    "surt": [{"category": "전설", "name_hint": "화염정수", "qty": 1}],
    # ... 각 보스마다
}

def roll_loot(demon: dict, seed: int) -> list[{"material_id": int, "qty": int}]:
    """결정성. 사망 케이스에선 호출되지 않는다."""
```

**규칙**:
| 난이도 | 일반 | 이상한 | 특수 |
|---|---|---|---|
| 1–3 | 1–2개 | — | — |
| 4–6 | 2–3개 | 30% 1개 | — |
| 7–9 | 2–3개 | — | 40% 1개 |
| 보스 | BOSS_LOOT 확정 + 일반 2–3개 | | |

시드 = `outcome_seed + 17` (dispatch와 동일 시드 패밀리). 각 카테고리 내 material 선택은 `repo.list_materials_by_category(category)` 후 시드로 굴림.

### dispatch_async_battle 통합

`combat.dispatch_async_battle` 안에서 outcome 결정 직후 (`hero != "died"`이고 demon == "killed" 케이스만 — 죽은 용사는 전리품 못 가져옴, 도망친 적은 떨굴 게 없음):
```python
if outcome["hero"] != "died" and outcome["demon"] == "killed":
    loot = loot_table.roll_loot(demon, seed + 17)
    hero.loot_pending += loot  # 누적
    repo.update_hero(hero_id, loot_pending=hero.loot_pending)
    outcome_json["loot"] = loot  # 회고 narration용
```

## 전리품 매수 협상 (`step_buy_loot`)

### 가격 책정
시작가 = `Σ(material.base_price × qty) × multiplier`, `multiplier = 1.2 - (affinity / 200)` (호감도 100이면 0.7×, -100이면 1.7×).

### 협상 메커니즘
step_buy와 동일:
- 한 라운드 최대 양보 5%
- 카운터 하한 = 시작가의 70%
- 플레이어가 카운터 이상 → 자동 accept
- 인내심 라운드 감소 + ≤0 자동 종료

### accept 후처리 (`finalize_buy_loot`)
- 플레이어 골드 차감
- `loot_pending` 재료 → `inventory` add
- `loot_pending` 비움
- **호감도 +5**
- day_event `loot_sale` 기록
- 슬롯 advance 안 함 (메뉴 복귀)

### reject 후처리
- `loot_pending` 유지 (다음 방문 시 다시 제시 가능)
- 호감도 변화 없음

### 엔드포인트
- `POST /loot/negotiate`
- `POST /loot/player_accept`
- `POST /loot/player_reject`
- `POST /loot/finalize`

## 프론트엔드 변화

### 신규 컴포넌트
- `HeroVisitorPanel` — 메뉴식. new_hero/returning_hero 양쪽 처리. 회고 narration도 흡수.
- `LootNegotiation` — NegotiationChat 패턴, 시작 시 loot 목록 표시.
- `ChitchatPanel` — textarea(선택) + "이야기 듣기" 버튼, 응답 표시, lore 누적 펼침.

### 변경
- `VisitorRouter`: hero 종류는 `HeroVisitorPanel`로 일원화.
- `NegotiationChat`, `MerchantPanel`, `EnhanceNegotiation`: 인내심 게이지 상단에 추가.
- `ReturningHeroPanel` 폐기.

### 타입 추가 (`types.ts`)
- `Hero`에 `lore?: LoreEntry[]`, `loot_pending?: LootItem[]`, `patience?: number`
- `Negotiation`에 `patience_current?, patience_start?`
- `LootItem`, `LoreEntry`

### API 래퍼 (`api.ts`)
- `chitchat(message?)`
- `lootNegotiate(...)`, `lootPlayerAccept(id)`, `lootPlayerReject(id)`, `lootFinalize(id)`

## 테스트

신규:
- `test_loot_table.py`: 결정성, 보스 시그니처 포함 여부, 난이도별 풀
- `test_dispatch_loot_integration.py`: dispatch 후 loot_pending 채워짐(생존+demon_killed 케이스만)
- `test_step_buy_loot.py`: 가격 공식, 양보율, 인내심, accept 시 inventory/affinity/loot_pending 처리
- `test_chitchat.py`: affinity 게이트, lore append, 20개 cap
- `test_patience.py`: 시작값(페르소나/상인), 라운드 감소, ≤0 자동 reject

기존 보완:
- `test_negotiation.py`: 인내심 통합 — 라운드 감소, 자동 종료 케이스
- `test_combat.py` (dispatch): 사망 케이스에선 loot_pending 변화 없음

## 마이그레이션 (`011_loot_chitchat_patience.sql`)

```sql
ALTER TABLE heroes
  ADD COLUMN IF NOT EXISTS lore JSONB NOT NULL DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS loot_pending JSONB NOT NULL DEFAULT '[]'::jsonb;

ALTER TABLE negotiations
  ADD COLUMN IF NOT EXISTS patience_start INT,
  ADD COLUMN IF NOT EXISTS patience_current INT;
```

## 롤아웃 순서

1. 마이그레이션 011 + FakeRepo 확장 (lore/loot_pending/patience 필드)
2. `loot_table.py` + 테스트
3. `dispatch_async_battle`에 loot roll + hero.loot_pending 갱신 통합
4. 인내심 모듈 (시작값 계산, 라운드 감소) + `negotiations.patience_*` 통합 + 테스트
5. `step_sell`/`step_buy`에 인내심 적용 + 자동 종료
6. `step_buy_loot` + `finalize_buy_loot` + 엔드포인트
7. chitchat 엔드포인트 + LLM 프롬프트 + 픽스처
8. 프론트 `HeroVisitorPanel` (큰 변경 — 회고+메뉴 통합)
9. `LootNegotiation`, `ChitchatPanel`, 인내심 게이지
10. 회귀 + 브라우저 검증

## 후속: 인내심 기반 양보폭 U곡선 (2026-05-28 추가)

### 문제
현재 모든 협상의 1라운드 양보폭이 직전가의 **5% 고정**이라 양측이 합의에 도달하기까지 라운드가 많이 들고, 인내심 상태가 가격에 영향을 주지 않아 게이지가 장식에 가깝다.

### 규칙
`patience.concession_multiplier(patience: int) -> float`를 도입한다.

```
distance = abs(patience - 50)         # 0..50
multiplier = 1.0 + min(distance, 50) / 25   # 1.0..3.0
```

- patience=50 → 1.0× (현재와 동일)
- patience=75 or 25 → 2.0× (10%)
- patience=100 or 1 → 3.0× (15%)

**해석**: 인내심이 가득한 NPC는 기분이 좋아 후하게 양보하고, 거의 탈진한 NPC는 빨리 끝내려고 후하게 양보한다. 중간 구간(40~60)이 가장 빡빡하다.

### 적용 지점 (4곳)
1. `negotiation.py:155` `step_sell` — `max_raise = int(previous * 0.05 * mult)`
2. `negotiation.py:408` `step_buy` — `max_drop = int(previous * 0.05 * mult)`
3. `negotiation.py:814` `step_buy_loot` — `previous - int(previous * 0.05 * mult)`
4. `step_enhance` — **현재 5% cap 없음**. 동일하게 `0.05 * mult` cap을 신규로 추가해 4가지 협상을 통일한다.

`mult`는 라운드 진입 시점의 `patience_current`로 계산. `0.05 * mult * previous` 결과는 `int()`로 내림.

### 범위 밖 (이번 후속에서 OUT)
- 시작 인내심 값, 라운드 감소량(5/10), exhausted 종료 로직 — 변경 없음
- floor (선호 가중 60/80%, 상인 70/80%) — 변경 없음, 양보폭만 늘어남
- LLM 메시지 톤 — 그대로 (숫자만 변경)

### 테스트
- `tests/test_patience.py`: `concession_multiplier` 단위 (5케이스: 0/25/50/75/100)
- `tests/test_negotiation.py`: 각 step_*에 patience=50 / patience=100 / patience=10 케이스
- 회귀: 기존 patience 없는 (None) 케이스 → 50 폴백으로 1.0× 유지

## 범위 밖 (명시적 OUT)

- 무기 수리/반환 흐름 (Q8: 부상 시 destroyed로 단순화)
- 도감 UI (lore 저장만, 열람은 별도 배치)
- 미션 NPC/세금관/상인조합장 (3차)
- 상인 재료 진행도 (피드백 #3, 4차)
- 무기 칭호 (피드백 #8, 4차)
