"""무기 강화 — 현재 스탯 × 1.4 cap, 재료 품질이 cap 내 roll 폭을 결정."""
from __future__ import annotations
import random
from typing import Any

# 카테고리별 품질 점수 (1개당). 합이 1.0에 도달하면 cap 가까이 roll.
QUALITY: dict[str, float] = {
    "일반": 0.1,
    "이상한": 0.25,
    "특수": 0.5,
    "전설": 1.0,
}

# 한 라운드 강화 cap = 현재 스탯의 40% 증가 (= 1.4배). 단 너무 작은 스탯은 최소 3까지는 허용.
ENHANCE_PCT = 0.4
MIN_DELTA_FLOOR = 3
QUALITY_FLOOR = 0.2  # 아무 재료라도 최소 이 비율은 보장


def quality_score(materials: list[dict[str, Any]]) -> float:
    total = sum(QUALITY.get(m.get("category", ""), 0.05) * int(m.get("qty", 1))
                for m in materials)
    return max(QUALITY_FLOOR, min(1.0, total))


def _max_delta(current: int) -> int:
    return max(MIN_DELTA_FLOOR, int(current * ENHANCE_PCT))


def roll_delta(weapon: dict[str, Any], materials: list[dict[str, Any]],
               seed: int | None = None) -> dict[str, int]:
    rng = random.Random(seed)
    score = quality_score(materials)
    cur_sharp = int(weapon.get("sharpness", 0))
    cur_rarity = int(weapon.get("rarity", 0))
    max_d_sharp = _max_delta(cur_sharp)
    max_d_rarity = _max_delta(cur_rarity)
    low_pct, high_pct = score * 0.3, score
    return {
        "sharpness": rng.randint(int(max_d_sharp * low_pct), int(max_d_sharp * high_pct)),
        "rarity":    rng.randint(int(max_d_rarity * low_pct), int(max_d_rarity * high_pct)),
    }


def apply_to_weapon(weapon: dict[str, Any], delta: dict[str, int],
                    used_materials: list[dict[str, Any]]) -> dict[str, Any]:
    new = dict(weapon)
    new["sharpness"] = min(100, int(weapon.get("sharpness", 0)) + delta["sharpness"])
    new["rarity"] = min(100, int(weapon.get("rarity", 0)) + delta["rarity"])
    new["enhancement_level"] = int(weapon.get("enhancement_level", 0)) + 1
    existing = list(weapon.get("materials_used") or [])
    existing.append({
        "action": "enhance",
        "materials": used_materials,
        "delta": delta,
    })
    new["materials_used"] = existing
    return new


def bundle_estimate(weapon: dict[str, Any], materials: list[dict[str, Any]]) -> int:
    """기대 강화 가치 추정 — 시장가 anchor 계산용."""
    score = quality_score(materials)
    cur_sharp = int(weapon.get("sharpness", 0))
    cur_rarity = int(weapon.get("rarity", 0))
    exp_sharp = _max_delta(cur_sharp) * score * 0.65   # roll 평균 ≈ score×0.65
    exp_rarity = _max_delta(cur_rarity) * score * 0.65
    return max(50, int(exp_sharp * 30 + exp_rarity * 60))
