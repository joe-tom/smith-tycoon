from app.day_summary import summarize_events


def test_summarize_events_counts_kinds():
    # 비동기 전투 도입 후 day_event 'battle'은 'dispatch'로 대체됨.
    # outcome은 재방문 전까지 비공개이므로 hero_* 카운터는 집계하지 않는다.
    events = [
        {"kind": "forge",    "payload": {"name": "검A"}},
        {"kind": "sale",     "payload": {"price": 1000}},
        {"kind": "dispatch", "payload": {"rep_delta": 2}},
        {"kind": "dispatch", "payload": {"rep_delta": 0}},
        {"kind": "buy",      "payload": {"price": 800}},
    ]
    s = summarize_events(events)
    assert s["forges"] == 1
    assert s["sales"] == 1
    assert s["buys"] == 1
    assert s["battles"] == 2  # dispatch count
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
