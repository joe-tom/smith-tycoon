class PhaseError(Exception):
    pass


PHASES = ["forge_open", "hero_negotiate", "hero_battle", "done"]
INITIAL_PHASE = PHASES[0]


def next_phase(current: str) -> str:
    if current not in PHASES:
        raise PhaseError(f"unknown phase: {current}")
    idx = PHASES.index(current)
    if idx + 1 >= len(PHASES):
        raise PhaseError(f"no phase after {current}")
    return PHASES[idx + 1]


def assert_phase(current: str, expected: str) -> None:
    if current != expected:
        raise PhaseError(f"expected phase {expected}, got {current}")
