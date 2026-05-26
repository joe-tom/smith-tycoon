class PhaseError(Exception):
    pass


PHASES = [
    "forge_open",
    "hero1_negotiate",
    "hero1_battle",
    "merchant_negotiate",
    "hero2_negotiate",
    "hero2_battle",
    "hero3_negotiate",
    "hero3_battle",
    "day_summary",
]
INITIAL_PHASE = PHASES[0]
MAX_DAY = 5


def next_phase(current: str) -> str:
    if current == "day_summary":
        return "next_day"   # sentinel — advance_to_next_day가 실제 처리
    if current == "game_over":
        raise PhaseError("no phase after game_over")
    if current not in PHASES:
        raise PhaseError(f"unknown phase: {current}")
    idx = PHASES.index(current)
    return PHASES[idx + 1]


def assert_phase(current: str, expected: str) -> None:
    if current != expected:
        raise PhaseError(f"expected phase {expected}, got {current}")


def assert_phase_in(current: str, expected: list[str]) -> None:
    if current not in expected:
        raise PhaseError(f"expected one of {expected}, got {current}")


def advance_to_next_day(player: dict) -> None:
    """player dict in-place 갱신. day=5에서 호출되면 game_over."""
    if player["current_day"] >= MAX_DAY:
        player["current_phase"] = "game_over"
    else:
        player["current_day"] += 1
        player["current_phase"] = "forge_open"
