import random
from fastapi import APIRouter
from .. import repo

router = APIRouter()


JOBS = ["검사", "법사", "궁수", "성문 문지기", "거렁뱅이", "청소년", "군인"]


@router.post("/game/reset")
def post_reset():
    repo.reset_game()
    rng = random.Random()
    repo.insert_hero({
        "name": str(rng.randint(1, 1000)),
        "job": rng.choice(JOBS),
        "str": rng.randint(5, 15),
        "mag": rng.randint(2, 12),
        "gold": rng.randint(500, 2000),
        "mood": rng.choice(["여유로움", "초조함", "들떠있음", "지친 듯"]),
        "personality_tags": rng.sample(["호탕", "깐깐", "소심", "허세", "검소"], k=2),
    })
    return {"ok": True}
