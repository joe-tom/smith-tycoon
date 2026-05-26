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


def test_summarize_events_empty():
    s = summarize_events([])
    assert s == {"forges": 0, "sales": 0, "buys": 0, "battles": 0,
                 "heroes_survived": 0, "heroes_injured": 0, "heroes_died": 0,
                 "rep_delta": 0, "gold_delta": 0}
