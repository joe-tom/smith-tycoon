from __future__ import annotations
import json
import random
from pathlib import Path
from typing import Any

_MATERIALS_CATALOG: list[dict[str, Any]] | None = None


def _materials_catalog() -> list[dict[str, Any]]:
    global _MATERIALS_CATALOG
    if _MATERIALS_CATALOG is None:
        path = Path(__file__).parent.parent / "seed" / "materials.json"
        _MATERIALS_CATALOG = json.loads(path.read_text())
    return _MATERIALS_CATALOG


WEAPON_TYPES = ["한손검", "양손검", "한손둔기", "양손둔기", "마법지팡이", "방패", "단도", "표창", "총"]

# 등장 확률 가중치 (architecture.md §4 등장확률 컬럼 참고)
CATEGORY_WEIGHT = {"일반": 10.0, "이상한": 4.0, "특수": 1.5, "전설": 0.3}

# 수량 범위 (희소할수록 적게)
CATEGORY_QTY = {
    "일반":   (2, 5),   # 일반은 넉넉히
    "이상한": (1, 4),
    "특수":   (1, 2),
    "전설":   (1, 1),
}


def _weighted_sample(rng: random.Random, items: list[dict[str, Any]], k: int) -> list[dict[str, Any]]:
    """카테고리 가중치에 따라 비복원 추출."""
    picked: list[dict[str, Any]] = []
    pool = list(items)
    for _ in range(min(k, len(pool))):
        weights = [CATEGORY_WEIGHT.get(m["category"], 1.0) for m in pool]
        choice = rng.choices(pool, weights=weights, k=1)[0]
        picked.append(choice)
        pool.remove(choice)
    return picked


def generate_today(day: int, seed: int | None = None) -> dict[str, Any]:
    """day별 상인 인벤토리 — materials 4~6종 + weapon 1개. 희소도가 높은 재료는 드물고 적게."""
    rng = random.Random(seed if seed is not None else f"merchant-{day}")
    catalog = _materials_catalog()

    n_materials = rng.randint(4, 6)
    chosen = _weighted_sample(rng, catalog, n_materials)
    materials = []
    for m in chosen:
        lo, hi = CATEGORY_QTY.get(m["category"], (1, 3))
        qty = rng.randint(lo, hi)
        markup = 1.0 + rng.random() * 0.5
        materials.append({
            "material_id": m["id"], "name": m["name"], "category": m["category"],
            "attribute": m.get("attribute"), "base_price": m["base_price"],
            "qty": qty,
            "asking_price": int(m["base_price"] * qty * markup),
        })

    wt = rng.choice(WEAPON_TYPES)
    weapon = {
        "name": f"{wt} (상인 매물)",
        "type": wt,
        "rarity": 30,
        "sharpness": 30,
        "attribute": None,
        "skill": "표준품의 안정적인 효과를 가집니다.",
        "str_req": 5,
        "mag_req": 3,
        "asking_price": int(300 * (1.0 + rng.random() * 0.5)),
    }
    return {"materials": materials, "weapon": weapon}


def bundle_market_price(bundle: dict[str, Any]) -> int:
    total = sum(m["base_price"] * m.get("qty", 1) for m in bundle["materials"])
    if bundle.get("weapon"):
        total += bundle["weapon"]["asking_price"]
    return max(10, total)
