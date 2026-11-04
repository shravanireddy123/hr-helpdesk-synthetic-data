import json
import random
from datetime import datetime

import pytest
from faker import Faker

from hrgen.config import SCALES
from hrgen.master_data import build_master_data
from hrgen.messages import build_messages
from hrgen.rules import ALLOWED_TRANSITIONS, audience_allowed
from hrgen.tickets import build_tickets


def build(scale_name, seed=20261022):
    scale = SCALES[scale_name]
    rng = random.Random(seed)
    fake = Faker("en_IN")
    fake.seed_instance(seed)
    master = build_master_data(rng, fake, scale)
    tix = build_tickets(rng, master["employee"], scale)
    both = {**master, **tix}
    msg = build_messages(rng, both, both, scale)
    events = sorted(tix["ticket_status_event"] + msg["new_events"], key=lambda e: e["event_id"])
    return master, tix, msg, events


@pytest.fixture(scope="module", params=["starter", "full"])
def built(request):
    return request.param, *build(request.param)


def by_ticket(rows):
    out = {}
    for r in rows:
        out.setdefault(r["ticket_id"], []).append(r)
    return out


def test_message_total_is_exact(built):
    name, _, _, msg, _ = built
    assert len(msg["message"]) == SCALES[name].messages


def test_message_ids_sequential_per_ticket(built):
    _, _, tix, msg, _ = built
    groups = by_ticket(msg["message"])
    assert set(groups) == {t["ticket_id"] for t in tix["ticket"]}
    for tid, rows in groups.items():
        assert [m["message_id"] for m in rows] == [f"MSG-{tid}-{n:03d}" for n in range(1, len(rows) + 1)]


def test_message_times_strictly_increase(built):
    _, _, _, msg, _ = built
    for rows in by_ticket(msg["message"]).values():
        times = [m["sent_at"] for m in rows]
        assert all(a < b for a, b in zip(times, times[1:]))


def test_clarification_flow_for_unclear_tickets(built):
    _, _, tix, msg, _ = built
    groups = by_ticket(msg["message"])
    for t in tix["ticket"]:
        types = [m["message_type"] for m in groups[t["ticket_id"]]]
        if t["is_ambiguous"] or t["missing_context"]:
            assert types[:2] == ["employee_question", "clarification_request"]
            if "hr_answer" in types:
                assert types[2] == "employee_reply"
                assert types.index("hr_answer") == 3
            else:
                assert types == ["employee_question", "clarification_request"]
        else:
            assert "clarification_request" not in types
            assert types[:2] == ["employee_question", "hr_answer"]


def test_every_answered_ticket_ends_with_resolution_note(built):
    _, _, _, msg, _ = built
    for rows in by_ticket(msg["message"]).values():
        types = [m["message_type"] for m in rows]
        if "hr_answer" in types:
            assert types[-1] == "resolution_note"
            assert types.count("resolution_note") == 1


def test_citations_are_correct(built):
    _, master, _, msg, _ = built
    ver = {v["version_id"]: v for v in master["policy_version"]}
    pol = {p["policy_id"]: p for p in master["policy_document"]}
    emp = {e["employee_id"]: e for e in master["employee"]}
    tickets = {t["ticket_id"]: t for t in _tickets(built)}
    answers = {m["message_id"]: m for m in msg["message"] if m["message_type"] == "hr_answer"}
    cites = {c["message_id"]: c for c in msg["message_citation"]}
    assert set(cites) == set(answers)                     # exactly one citation per answer
    for mid, c in cites.items():
        t = tickets[answers[mid]["ticket_id"]]
        v = ver[c["version_id"]]
        day = t["created_at"][:10]
        assert v["effective_from"] <= day and (v["effective_to"] is None or v["effective_to"] >= day)
        assert audience_allowed(pol[v["policy_id"]]["audience"], emp[t["employee_id"]]["role"])
        for k, val in json.loads(v["key_rules"]).items():  # claims are supported by key_rules
            assert f"{k.replace('_', ' ')} is {val}" in c["snippet"]
        assert c["snippet"] in answers[mid]["body"]


def _tickets(built):
    return built[2]["ticket"]


def test_event_chain_is_valid(built):
    _, _, tix, _, events = built
    ids_ = [e["event_id"] for e in events]
    assert len(ids_) == len(set(ids_))
    for tid, rows in by_ticket(events).items():
        assert rows[0]["from_status"] is None and rows[0]["to_status"] == "new"
        for prev, cur in zip(rows, rows[1:]):
            assert cur["from_status"] == prev["to_status"]
            assert (cur["from_status"], cur["to_status"]) in ALLOWED_TRANSITIONS
            assert datetime.fromisoformat(cur["event_at"]) >= datetime.fromisoformat(prev["event_at"])
        assert rows[-1]["to_status"] == "closed"           # every ticket is finished
    assert set(by_ticket(events)) == {t["ticket_id"] for t in tix["ticket"]}


def test_same_seed_gives_identical_messages():
    a, b = build("starter"), build("starter")
    assert a[2] == b[2] and a[3] == b[3]
