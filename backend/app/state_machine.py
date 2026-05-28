class PhaseError(Exception):
    pass


PHASES = ["forge_open", "visitor", "day_summary"]
INITIAL_PHASE = PHASES[0]
MAX_DAY = 100


def next_phase(current: str) -> str:
    if current == "day_summary":
        return "next_day"
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


def advance_visitor(player: dict) -> None:
    """visitor 슬롯 인덱스를 다음으로. 마지막이면 day_summary로 전이."""
    if player["current_phase"] != "visitor":
        raise PhaseError(f"advance_visitor requires phase=visitor, got {player['current_phase']}")
    schedule = player.get("day_schedule") or []
    new_idx = player.get("current_visitor_index", 0) + 1
    if new_idx >= len(schedule):
        player["current_phase"] = "day_summary"
    else:
        player["current_visitor_index"] = new_idx


def advance_to_next_day(player: dict) -> None:
    """player dict in-place 갱신. MAX_DAY 도달 시 game_over."""
    if player["current_day"] >= MAX_DAY:
        player["current_phase"] = "game_over"
    else:
        player["current_day"] += 1
        player["current_phase"] = "forge_open"
        player["current_visitor_index"] = 0
        player["day_schedule"] = []
