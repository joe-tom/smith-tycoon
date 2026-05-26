from app.day_summary import summarize_events


def test_summarize_events_counts_kinds():
    events = [
        {"kind": "forge",  "payload": {"name": "검A"}},
        {"kind": "sale",   "payload": {"price": 1000}},
        {"kind": "battle", "payload": {"outcomes": {"hero": "survived"}, "rep_delta": 2}},
        {"kind": "battle", "payload": {"outcomes": {"hero": "injured"},  "rep_delta": 0}},
        {"kind": "buy",    "payload": {"price": 800}},
    ]
    s = summarize_events(events)
    assert s["forges"] == 1
    assert s["sales"] == 1
    assert s["buys"] == 1
    assert s["battles"] == 2
    assert s["heroes_survived"] == 1
    assert s["heroes_injured"] == 1
    assert s["heroes_died"] == 0
    # rep_delta: 전투 2 + 판매 1 + 구매 1 = 4
    assert s["rep_delta"] == 4
    assert s["rep_breakdown"]["battle"] == 2
    assert s["rep_breakdown"]["sale"] == 1
    assert s["rep_breakdown"]["buy"] == 1


def test_summarize_events_skip_and_reject_penalty():
    events = [
        {"kind": "skip",   "payload": {"rep_delta": -1}},
        {"kind": "reject", "payload": {"rep_delta": -1}},
    ]
    s = summarize_events(events)
    assert s["rep_delta"] == -2
    assert s["rep_breakdown"]["skip"] == -1
    assert s["rep_breakdown"]["reject"] == -1


def test_summarize_events_empty():
    s = summarize_events([])
    assert s["forges"] == 0
    assert s["sales"] == 0
    assert s["rep_delta"] == 0
    assert s["gold_delta"] == 0
    assert s["rep_breakdown"] == {"battle": 0, "sale": 0, "buy": 0, "skip": 0, "reject": 0}
