import random
from datetime import datetime

import pytest
from faker import Faker

from hrgen.business_calendar import add_business_minutes, business_minutes_between
from hrgen.config import SCALES
from hrgen.master_data import build_master_data
from hrgen.messages import build_messages
from hrgen.rules import ALLOWED_TRANSITIONS, SLA_TARGET_MINUTES
from hrgen.sla import P1_UNTOUCHED_MINUTES, build_sla
from hrgen.tickets import build_tickets


def build(scale_name, seed=20261022):
    scale = SCALES[scale_name]
    rng = random.Random(seed)
    fake = Faker("en_IN")
    fake.seed_instance(seed)
    master = build_master_data(rng, fake, scale)
    tix = build_tickets(rng, master["employee"], scale)
    tables = {**master, **tix}
    msg = build_messages(rng, tables, tables, scale)
    tables["message"] = msg["message"]
    tables["message_citation"] = msg["message_citation"]
    tables["ticket_status_event"] = sorted(
        tables["ticket_status_event"] + msg["new_events"], key=lambda e: e["event_id"])
    tables.update(build_sla(tables))
    return tables


@pytest.fixture(scope="module", params=["starter", "full"])
def built(request):
    return request.param, build(request.param)


def group(rows, key="ticket_id"):
    out = {}
    for r in rows:
        out.setdefault(r[key], []).append(r)
    return out


def dt(s):
    return datetime.fromisoformat(s)


def test_one_sla_and_resolution_per_ticket(built):
    _, t = built
    ids_ = {x["ticket_id"] for x in t["ticket"]}
    assert {s["ticket_id"] for s in t["sla"]} == ids_ and len(t["sla"]) == len(ids_)
    assert {r["ticket_id"] for r in t["resolution"]} == ids_ and len(t["resolution"]) == len(ids_)


def test_sla_values_recompute(built):
    _, t = built
    tickets = {x["ticket_id"]: x for x in t["ticket"]}
    for s in t["sla"]:
        tk = tickets[s["ticket_id"]]
        created = dt(tk["created_at"])
        first_t, res_t = SLA_TARGET_MINUTES[tk["priority"]]
        assert s["priority"] == tk["priority"]
        assert dt(s["first_response_due"]) == add_business_minutes(created, first_t)
        assert dt(s["resolution_due"]) == add_business_minutes(created, res_t + s["paused_minutes"])
        assert s["business_minutes_to_first_response"] == business_minutes_between(
            created, dt(s["first_responded_at"]))
        assert s["first_response_met"] == (dt(s["first_responded_at"]) <= dt(s["first_response_due"]))


def test_paused_minutes_and_no_response(built):
    _, t = built
    msgs = group(t["message"])
    res = {r["ticket_id"]: r for r in t["resolution"]}
    for s in t["sla"]:
        tid = s["ticket_id"]
        types = [m["message_type"] for m in msgs[tid]]
        if "clarification_request" not in types:
            assert s["paused_minutes"] == 0
        else:
            assert s["paused_minutes"] > 0
        if res[tid]["resolution_code"] == "no_response":
            assert s["paused_minutes"] == 5 * 510
            assert s["resolution_met"] is None
            assert res[tid]["cited_version_id"] is None
            assert len(types) == 2
        else:
            assert isinstance(s["resolution_met"], bool)


def test_escalation_rule_applied_exactly(built):
    _, t = built
    tickets = {x["ticket_id"]: x for x in t["ticket"]}
    sla = {s["ticket_id"]: s for s in t["sla"]}
    events = group(t["ticket_status_event"])
    escalated = {tid for tid, rows in events.items() if any(e["to_status"] == "escalated" for e in rows)}
    assert 0 < len(escalated) < len(tickets)
    for tid, rows in events.items():
        reached = any(e["to_status"] == "in_progress" for e in rows)
        tk = tickets[tid]
        created = dt(tk["created_at"])
        if tk["priority"] == "P1":
            trigger = add_business_minutes(created, P1_UNTOUCHED_MINUTES)
        else:
            trigger = dt(sla[tid]["first_response_due"])
        should = reached and dt(sla[tid]["first_responded_at"]) > trigger
        assert (tid in escalated) == should, tid


def test_escalation_creates_hr_lead_assignment(built):
    _, t = built
    role = {e["employee_id"]: e["role"] for e in t["employee"]}
    asg = group(t["assignment"])
    events = group(t["ticket_status_event"])
    for tid, rows in asg.items():
        esc = [e for e in events[tid] if e["to_status"] == "escalated"]
        if esc:
            assert len(rows) == 2 and len(esc) == 1
            second = rows[1]
            assert second["assignment_id"] == f"ASG-{tid}-02" and second["queue"] == "HR_LEAD"
            assert second["assigned_at"] == esc[0]["event_at"]
            assert second["assignee_id"] != rows[0]["assignee_id"]
            assert role[second["assignee_id"]] == "hr_partner"
        else:
            assert len(rows) == 1


def test_event_chain_after_escalation(built):
    _, t = built
    for tid, rows in group(t["ticket_status_event"]).items():
        assert [e["event_id"] for e in rows] == [f"EVT-{tid}-{n:02d}" for n in range(1, len(rows) + 1)]
        assert rows[0]["from_status"] is None and rows[0]["to_status"] == "new"
        assert rows[-1]["to_status"] == "closed"
        for prev, cur in zip(rows, rows[1:]):
            assert cur["from_status"] == prev["to_status"]
            assert (cur["from_status"], cur["to_status"]) in ALLOWED_TRANSITIONS
            assert dt(cur["event_at"]) >= dt(prev["event_at"])


def test_resolution_rows(built):
    _, t = built
    tickets = {x["ticket_id"]: x for x in t["ticket"]}
    sla = {s["ticket_id"]: s for s in t["sla"]}
    cites = {c["message_id"]: c["version_id"] for c in t["message_citation"]}
    answers = {m["ticket_id"]: m["message_id"] for m in t["message"] if m["message_type"] == "hr_answer"}
    for r in t["resolution"]:
        tid = r["ticket_id"]
        created = dt(tickets[tid]["created_at"])
        assert dt(r["resolved_at"]) >= created
        assert r["business_minutes_to_resolve"] == business_minutes_between(created, dt(r["resolved_at"]))
        if tid in answers:
            assert r["cited_version_id"] == cites[answers[tid]]
        if r["resolution_code"] != "no_response":
            assert sla[tid]["resolution_met"] == (dt(r["resolved_at"]) <= dt(sla[tid]["resolution_due"]))


def test_same_seed_gives_identical_sla():
    a, b = build("starter"), build("starter")
    for name in ("sla", "resolution", "assignment", "ticket_status_event"):
        assert a[name] == b[name]