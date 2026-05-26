# MVP Plan 3 — 단골 메타 (호감도·회상·별명·강화) 설계 문서

작성일: 2026-05-26
선행: [Plan 2 spec](2026-05-26-mvp-plan2-design.md), [원본 설계](../../../architecture.md)

Plan 1·2로 일일 운영 루프가 동작하는 위에 **단골 용사 시스템**을 얹는다. 이미 누적되고 있는 `affinity`·`visit_count`·`held_weapon_id`·`history`가 실제 게임 효과로 활성화된다.

---

## 0. 목적 & 가설

핵심 가설:
- 재방문 용사가 "내 대장간의 단골" 같이 느껴지면 5일 게임이 단순 반복에서 누적 이야기로 바뀐다
- 무기 강화는 한 무기를 점점 키우는 작은 빌드 경험을 만든다
- 호감도 변화가 가격 협상을 다양화한다 (모든 거래가 같은 규칙이 아님)

비목표:
- 시그니처 기법, 전설 무기 등재 (Plan 4)
- 보스 전투, 5행 속성 상성, 승리·패배 엔딩 (Plan 4)

---

## 1. 스코프

### 1.1 포함

- **무기 강화 협상**: 재방문 용사가 보존 무기를 들고 오면 자동으로 강화 phase
- **호감도 가격 보정**: 호감도 구간별로 협상 합의 범위가 달라짐
- **프롬프트 회상**: 호감도 ≥20 용사의 거래 이력·별명을 협상 프롬프트에 주입
- **별명 부여**: 전투 결과 + 호감도 조건 충족 시 LLM이 별명 제안, 영구 적용

### 1.2 제외 (Plan 4+로 이월)

- 시그니처 기법 (재료 패턴 반복으로 패시브 해금)
- 전설 무기 등재 (조건 충족 무기를 명예의 전당에)
- 중간·최종 보스 전투
- 5행 속성 상성 데미지 계산
- 승리·패배 엔딩 조건 분기

---

## 2. phase 라우팅: 강화 vs 구매

state_machine PHASES는 Plan 2 그대로. 분기는 협상 phase 진입 시점에 결정:

```
hero{N}_negotiate 진입 →
  hero.held_weapon_id가 있으면:
    mode="enhance", state.hero.held_weapon = 그 무기 정보
    DayRouter → <EnhanceNegotiation>
  없으면:
    mode="sell" (Plan 2의 기존 흐름)
    DayRouter → <NegotiationChat>
```

state.py가 `mode` 필드를 응답에 포함. 백엔드는 한 가지 phase 이름(`hero{N}_negotiate`)을 유지하면서 두 모드를 라우팅.

---

## 3. 데이터 모델

기존 Plan 1·2 스키마가 이미 충분. 마이그레이션 003은 거의 비어 있음:

```sql
-- 003_meta.sql — Plan 3 (스키마 변경 없음, 문서용)
-- Plan 3는 기존 컬럼 재활용:
--   heroes.affinity, heroes.history, heroes.nickname, heroes.held_weapon_id
--   weapons.enhancement_level, weapons.materials_used (jsonb append)
--   negotiations.kind='enhance' (check constraint에 이미 포함)
```

(필요 시 인덱스나 추가 필드는 구현 중 추가.)

### 3.1 가격 보정 표 (architecture.md §12.3 기반)

| 호감도 구간 | 합의 가능 상한 (시세 대비) |
|---|---|
| ≥ +50 | 110% |
| +20 ~ +49 | 100% |
| -19 ~ +19 | 90% (기본) |
| -49 ~ -20 | 80% |
| ≤ -50 | 협상 자체 거부 (즉시 reject, 평판 변화 없음) |

`affinity.allowed_max_pct(affinity: int) -> float | "reject"` 함수가 이 표를 구현.

### 3.2 호감도 변화 규칙 (sale 시점)

| 트리거 | 호감도 Δ |
|---|---|
| 후한 거래 (agreed < 시세 × 0.9) | +10 |
| 적정가 거래 (시세 × 0.9 ~ 1.2) | +5 |
| 바가지 (agreed > 시세 × 1.2) | −10 |
| 강화 후 다음 전투에서 생존 | +10 |
| 구매한 무기가 다음 전투에서 파괴 | −5 |

기존 Plan 1·2의 단순 `+5 on sale`은 위 규칙으로 대체.

### 3.3 별명 부여 조건

다음 **모두** 충족하는 시점 (전투 직후):
- 이번 전투 결과: `hero == survived` AND `demon == killed`
- 이번 전투 포함 이 hero의 마지막 2개 이상 battles가 모두 (`survived` + `killed`) — 즉 이번 + 최소 1번의 직전 전투까지 연속 성공
- `hero.affinity ≥ 20`
- `hero.nickname is None` (이미 있으면 갱신 안 함)

조건 충족 시 LLM이 후보 3개 생성 → 서버가 랜덤 1개 픽 → `update_hero(nickname=...)`.

### 3.4 강화 결과 표 (architecture.md §11.3 그대로)

| 재료 카테고리 | 예리도 Δ | 희귀도 Δ |
|---|---|---|
| 일반 | +1 ~ +3 | +0 ~ +2 |
| 이상한 | +0 ~ +2 | +0 ~ +2 |
| 특수 | +3 ~ +7 | +2 ~ +5 |
| 전설 | +7 ~ +15 | +5 ~ +12 |

여러 재료 사용 시 Δ는 **합산**. `enhancement.roll_delta(materials: list) -> {sharp_delta, rarity_delta}` 가 구현.

무기에 적용:
- `sharpness = min(100, sharpness + sharp_delta)`
- `rarity = min(100, rarity + rarity_delta)`
- `enhancement_level += 1`
- `materials_used.append({"action": "enhance", "materials": [...], "delta": {...}})`

---

## 4. 모듈 구성

### 4.1 백엔드

| 모듈 | 책임 | 상태 |
|---|---|---|
| `affinity` (신규) | `delta_from_ratio`, `allowed_max_pct`, `apply_to_hero` | 신규 |
| `enhancement` (신규) | `roll_delta`, `apply_to_weapon`, `bundle_estimate` | 신규 |
| `nickname` (신규) | `should_award`, `award` (LLM 호출 + 픽) | 신규 |
| `negotiation` | step_sell 호감도·회상·가격 범위 반영. finalize_sale 호감도 갱신. step_enhance/finalize_enhance 신규 | 변경 |
| `combat` | 전투 후 nickname.should_award/award 호출. 무기 파괴 시 affinity −5 | 변경 |
| `repo` | `count_consecutive_survives(hero_id)`, `update_weapon(weapon_id, **fields)` | 변경 |
| `api/enhance.py` (신규) | `POST /enhance/negotiate`, `/finalize`, `/player_accept`, `/player_reject`, `/skip` | 신규 |
| `api/state.py` | hero에 `mode`, `held_weapon` 필드 | 변경 |
| `llm/prompts/negotiate_enhance.j2` (신규) | 강화 비용 협상 |  신규 |
| `llm/prompts/nickname.j2` (신규) | 별명 후보 3개 생성 |  신규 |
| `llm/prompts/negotiate_sell.j2` | 호감도/회상/가격 범위 변수 추가 | 변경 |
| `models.py` | `EnhanceNegotiateRequest` 등 추가 | 변경 |

### 4.2 프론트엔드

| 컴포넌트 | 책임 | 상태 |
|---|---|---|
| `<EnhanceNegotiation>` (신규) | 강화 재료 선택 + 비용 협상 채팅 | 신규 |
| `<DayRouter>` | hero.mode 분기 | 변경 |
| `<NegotiationChat>` | 호감도·별명·회상 라인 표시 | 변경 |
| `types.ts` | Hero에 `mode`, `held_weapon`, `nickname` (이미 있음) | 변경 |
| `api.ts` | `/enhance/*` wrapper | 변경 |

---

## 5. 데이터 플로우

### 5.1 매도 협상 + 호감도 (sell mode)

```
GET /state
  hero.mode = "sell" (held_weapon_id is null)
  hero.affinity = 28 (예시)
  hero.nickname = "단도의 신" (있는 경우)

POST /negotiate {weapon_id, price_offered, message}
  ↓
step_sell:
  base = market_price(weapon)
  affinity = hero["affinity"]
  max_pct = affinity.allowed_max_pct(affinity)
  
  if max_pct == "reject":
    # 호감도 ≤ -50
    insert_day_event(kind="reject", payload={by: "hero_blacklist"})
    return {decision: "reject", message: "당신과는 거래 안 하오."}
  
  ceiling = int(base * max_pct)
  safe_price = min(price_offered, hero.gold)   # 기존
  
  # 자동 수락: safe_price <= max_hero_counter (Plan 2) OR safe_price <= ceiling
  if safe_price <= ceiling and (
        not max_hero_counter or safe_price <= max_hero_counter):
    # 호감도 허용 범위 내, 즉시 수락 가능
    ... auto accept ...
  
  # 그 외 LLM 호출 — 프롬프트에 affinity, history (최근 5), nickname, preferences 주입
  ...
  
  # 서버 floor: 카운터는 적어도 시세 50%/70% 이상 (Plan 2)
  # 추가 ceiling: 카운터는 hero.gold 이하 (Plan 2)
  ...

POST /negotiate/finalize  (=accept)
  ↓
finalize_sale:
  ratio = agreed_price / base
  affinity_delta = affinity.delta_from_ratio(ratio)
  
  # 거래 처리 (Plan 1·2 기존)
  repo.transfer_weapon_to_hero(...)
  repo.update_player(gold +, reputation +1, current_phase advance)
  
  # 호감도 갱신
  history.append({weapon, agreed_price, ratio, battle: null})
  repo.update_hero(affinity += affinity_delta, history=history[-5:], held_weapon_id=weapon_id)
```

### 5.2 강화 협상 (enhance mode)

```
GET /state
  hero.mode = "enhance"
  hero.held_weapon = {id, name, sharpness 50, rarity 30, enhancement_level 0}

GET /state도 같은 hero를 반환하지만 mode가 다름

POST /enhance/negotiate {hero_id, selected_materials: [...], price_offered, message?, negotiation_id?}
  ↓
step_enhance:
  weapon = repo.get_weapon(hero.held_weapon_id)
  
  if neg_id is None:
    # 첫 라운드 — 재료 검증
    selected = validate_against_inventory(selected_materials)
    if not selected:
      raise ValueError("no_materials_selected")
    
    # 예상 가치 (LLM 첫 호가 기준)
    base_estimate = enhancement.bundle_estimate(weapon, selected)
    
    neg = repo.insert_negotiation(kind="enhance", weapon_id=weapon.id,
                                   counterparty_id=hero_id,
                                   materials={"selected": selected})
  else:
    neg = repo.get_negotiation(neg_id)
    base_estimate = enhancement.bundle_estimate(...)   # 동일 계산
  
  # 협상 핵심은 sell과 매우 비슷 — clamp_price, hero_gold cap, hero counter floor 등 동일
  llm = complete_json("negotiate_enhance", ..., weapon=weapon, 
                     materials=selected, base_estimate=base_estimate,
                     affinity=hero.affinity, history=hero.history, ...)
  ...

POST /enhance/finalize (=accept)
  ↓
finalize_enhance:
  if neg.outcome != "accepted": raise ValueError
  # 플레이어가 hero에게서 강화 비용을 받음 (gold 증가). 무기는 hero 소유 그대로.
  
  selected = neg["materials"]["selected"]
  sharp_d, rarity_d = enhancement.roll_delta(selected)
  
  # 무기 적용
  new_sharpness = min(100, weapon.sharpness + sharp_d)
  new_rarity = min(100, weapon.rarity + rarity_d)
  new_materials_used = weapon.materials_used + [{"action": "enhance", 
                                                  "materials": selected, 
                                                  "delta": {"sharpness": sharp_d, "rarity": rarity_d}}]
  repo.update_weapon(weapon.id, 
                     sharpness=new_sharpness, rarity=new_rarity,
                     enhancement_level=weapon.enhancement_level + 1,
                     materials_used=new_materials_used)
  
  # 재료 차감, 플레이어 보상, 호감도, 평판
  repo.deduct_materials({m.id: m.qty for m in selected})
  repo.update_player(gold + agreed_price, reputation + 1, current_phase advance)
  
  ratio = agreed_price / base_estimate
  affinity_delta = affinity.delta_from_ratio(ratio)
  repo.update_hero(hero_id, affinity += affinity_delta, 
                  history.append({"action": "enhance", "weapon": ..., "delta": ...}))
  
  # 무기는 여전히 hero가 보유 (held_weapon_id 그대로)
  
  insert_day_event(kind="enhance", payload={...})
```

### 5.3 별명 부여 (전투 직후)

```
combat.run_battle 마지막에:
  if outcomes["hero"] == "survived" and outcomes["demon"] == "killed":
    if nickname.should_award(hero, repo.count_consecutive_survives(hero_id)):
      await nickname.award(hero)
      # award 내부:
      #   candidates = LLM(prompt="nickname", hero=hero, recent_battles=...)
      #   picked = candidates["nicknames"][rng.randint(0, len-1)]
      #   repo.update_hero(hero_id, nickname=picked)
      #   repo.insert_day_event(kind="nickname", payload={hero_id, nickname})
```

별명 부여는 비치명적 — LLM 실패 시 skip하고 전투 결과는 정상 처리.

---

## 6. 에러 처리 & 엣지 케이스

| 상황 | 처리 |
|---|---|
| 호감도 ≤ -50인 hero와 협상 시도 | 첫 라운드 즉시 reject, 평판 변화 없음. `day_event` 기록 |
| 강화 phase인데 held_weapon_id 무효 (DB 비일관) | 500 + log warning. UI에서 새 게임 권장 |
| 강화 재료 0개 선택 | 400 + `no_materials_selected` |
| 강화 비용 협상 결렬 | 평판 -1, phase advance (sell reject와 동일) |
| 별명 LLM 호출 실패 | 별명 부여 skip. 전투 결과는 정상 |
| nickname JSON 파싱 실패 | 빈 후보 → award skip |
| affinity 값이 범위 벗어남 (-200 등) | 갱신 시 [-100, 100] clamp |

기존 처리는 Plan 1·2 그대로 유지.

---

## 7. 테스트 전략

### 7.1 단위 테스트

| 대상 | 검증 |
|---|---|
| `affinity.delta_from_ratio` | 후한·적정·바가지 경계 (0.89, 0.9, 1.1, 1.19, 1.2, 1.21) |
| `affinity.allowed_max_pct` | 표 모든 구간 (-100, -50, -20, 0, 20, 50, 100) |
| `enhancement.roll_delta` | 카테고리별 Δ 범위 (시드 30개씩) |
| `enhancement.apply_to_weapon` | sharp/rarity cap 100, enhancement_level +1, materials_used jsonb append |
| `nickname.should_award` | 조건 4개 진리표 |
| `repo.count_consecutive_survives` | battles 기록에서 hero_id 직전 연속 카운트 (생존이 끊기면 0부터) |
| `negotiation.step_sell` 회상 | LLM 차단·prompt 렌더 검증 — history·affinity·nickname 변수가 렌더된 prompt에 포함 |
| `affinity.delta_from_ratio` enhance 케이스 | (action 구분 시) |

### 7.2 LLM 픽스처

- `enhance_accept.json`, `enhance_counter.json`, `enhance_reject.json`
- `nickname_candidates.json`

### 7.3 통합 테스트

`test_integration_meta.py` 신규:
1. Day 1 hero1 무기 판매 (적정가) → 호감도 +5
2. Day 1 hero1 전투 생존 → return_day=4
3. Day 4 hero1 재방문, mode=enhance 확인
4. 강화 재료 선택 → 협상 → 합의 → 무기 Δ 적용 확인
5. Day 4 hero1 전투 생존 → 연속 2회 + 호감도 ≥20 + 마왕 처치 → 별명 부여 확인

기존 `test_integration_day.py`는 그대로 유지.

### 7.4 프론트엔드

자동 테스트 없음. tsc + 수동 체크리스트.

### 7.5 수동 검증

`docs/superpowers/plans/2026-05-26-mvp-plan3-checklist.md`:
- 강화 흐름 (일반/특수/전설 재료별 Δ 체감)
- 호감도 가격 보정 (후한 거래 누적 → 다음 방문에서 시세 110%까지 받는지)
- 별명 부여 시나리오
- 회상 대사 품질 (LLM이 history를 자연스럽게 인용?)

---

## 8. 디렉토리 변경

```
backend/
├── app/
│   ├── affinity.py            신규
│   ├── enhancement.py         신규
│   ├── nickname.py            신규
│   ├── negotiation.py         변경 (step_enhance, finalize_enhance, affinity 반영)
│   ├── combat.py              변경 (nickname 트리거)
│   ├── repo.py                변경 (count_consecutive_survives, update_weapon)
│   ├── api/
│   │   ├── enhance.py         신규
│   │   └── state.py           변경 (mode, held_weapon)
│   └── llm/prompts/
│       ├── negotiate_enhance.j2  신규
│       ├── nickname.j2           신규
│       └── negotiate_sell.j2     변경 (affinity·history·nickname 변수)
├── migrations/
│   └── 003_meta.sql           신규 (스키마 변경 없음, 문서 기록용)
└── tests/
    ├── test_affinity.py            신규
    ├── test_enhancement.py         신규
    ├── test_nickname.py            신규
    ├── test_negotiation.py         변경
    ├── test_integration_meta.py    신규
    └── fixtures/llm/
        ├── enhance_accept.json     신규
        ├── enhance_counter.json    신규
        ├── enhance_reject.json     신규
        └── nickname_candidates.json 신규

frontend/src/
├── api.ts                          변경 (/enhance/*)
├── types.ts                        변경 (mode, held_weapon)
└── components/
    ├── DayRouter.tsx               변경 (mode 분기)
    ├── NegotiationChat.tsx         변경 (호감도·별명·회상 표시)
    └── EnhanceNegotiation.tsx      신규

docs/superpowers/plans/
├── 2026-05-26-mvp-plan3-meta.md            (이후 작성될 plan)
└── 2026-05-26-mvp-plan3-checklist.md       신규
```

---

## 9. 열린 결정 (구현 시 정함)

- 호감도 ≤ -50 hero의 협상 거부 시점 — 첫 라운드 즉시 거부 vs 협상 진입 자체 차단(state.py에서 mode="blacklist")
- 별명 부여 후 LLM 프롬프트에서 어떻게 인용할지 (이름 대체 vs 추가)
- 강화 시 hero가 인벤토리 재료 가시성 — UI에 hero의 선호 재료 힌트도 줄지 (preferences에 추가?)
- 호감도가 음수일 때 가격 보정 외에 다른 페널티 (협상 라운드 추가, 시작가 강제 -10% 등)
