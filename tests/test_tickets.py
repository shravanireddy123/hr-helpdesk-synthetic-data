import random
from datetime import date

import pytest
from faker import Faker

from hrgen.business_calendar import is_business_day
from hrgen.config import SCALES
from hrgen.master_data import build_master_data
from hrgen.rules import ALLOWED_TRANSITIONS, is_sensitive, priority_for, route_queue
from hrgen.tickets import build_tickets


def build(scale_name, seed=20261022):
    rng = random.Random(seed)
    fake = Faker("en_IN")
    fake.seed_instance(seed)
    master = build_master_data(rng, fake, SCALES[scale_name])
    return master, build_tickets(rng, master["employee"], SCALES[scale_name])


@pytest.fixture(scope="module", params=["starter", "full"])
def built(request):
    return request.param, *build(request.param)


# ---- pure rule tests -------------------------------------------------------
def test_er_category_is_sensitive_and_routed_to_er():
    s = is_sensitive("CAT-ER", "I need to discuss something confidential")
    assert s and route_queue("CAT-ER", "anything", s) == "ER_CONFIDENTIAL"


def test_keyword_makes_non_er_ticket_sensitive():
    assert is_sensitive("CAT-LEAVE", "Medical leave certificate requirement")
    assert not is_sensitive("CAT-LEAVE", "Sick leave balance for this year")


def test_onboarding_it_issue_goes_to_it_ops():
    assert route_queue("CAT-ONBOARDING", "Laptop not delivered before joining date", False) == "IT_OPS"
    assert route_queue("CAT-ONBOARDING", "Background verification status", False) == "GENERAL"


def test_default_queues():
    assert route_queue("CAT-LEAVE", "x", False) == "LEAVE"
    assert route_queue("CAT-BENEFITS", "x", False) == "BENEFITS"
    assert route_queue("CAT-PAYROLL", "x", False) == "PAYROLL"
    assert route_queue("CAT-GENERAL", "x", False) == "GENERAL"


def test_priority_rules():
    assert priority_for("CAT-ER", True) == "P1"
    assert priority_for("CAT-LEAVE", True) == "P1"
    assert priority_for("CAT-PAYROLL", False) == "P2"
    assert priority_for("CAT-LEAVE", False) == "P3"


# ---- generated-data tests --------------------------------------------------
def test_counts(built):
    name, _, t = built
    n = SCALES[name].tickets
    assert len(t["ticket"]) == n
    assert len(t["assignment"]) == n
    assert len(t["ticket_status_event"]) == 2 * n


def test_sensitive_tickets_route_to_er(built):
    _, master, t = built
    role = {e["employee_id"]: e["role"] for e in master["employee"]}
    first = {a["ticket_id"]: a for a in t["assignment"]}
    for tk in t["ticket"]:
        a = first[tk["ticket_id"]]
        if tk["is_sensitive"]:
            assert a["queue"] == "ER_CONFIDENTIAL"
            assert role[a["assignee_id"]] == "hr_er_specialist"
            assert tk["priority"] == "P1"
        else:
            assert a["queue"] != "ER_CONFIDENTIAL"


def test_ids_and_time_order(built):
    _, _, t = built
    tickets = t["ticket"]
    assert [x["ticket_id"] for x in tickets] == sorted(x["ticket_id"] for x in tickets)
    created = [x["created_at"] for x in tickets]
    assert created == sorted(created)
    assert all(c.startswith("2026-") for c in created)
    working = sum(1 for c in created
                  if is_business_day(date.fromisoformat(c[:10])) and 9 <= int(c[11:13]) < 19)
    assert working / len(created) > 0.75


def test_raisers_are_valid(built):
    _, master, t = built
    emp = {e["employee_id"]: e for e in master["employee"]}
    for tk in t["ticket"]:
        e = emp[tk["employee_id"]]
        assert e["status"] != "exited"
        assert e["hire_date"] <= tk["created_at"][:10]
        if e["role"] == "candidate":
            assert tk["category_id"] == "CAT-ONBOARDING"


def test_flag_mix_is_roughly_right(built):
    _, _, t = built
    n = len(t["ticket"])
    amb = sum(x["is_ambiguous"] for x in t["ticket"]) / n
    mis = sum(x["missing_context"] for x in t["ticket"]) / n
    er = sum(x["category_id"] == "CAT-ER" for x in t["ticket"]) / n
    assert abs(amb - 0.12) < 0.05 and abs(mis - 0.08) < 0.05 and abs(er - 0.06) < 0.03
    assert not any(x["is_ambiguous"] and x["missing_context"] for x in t["ticket"])


def test_events_follow_lifecycle(built):
    _, _, t = built
    for ev in t["ticket_status_event"]:
        assert (ev["from_status"], ev["to_status"]) in ALLOWED_TRANSITIONS


def test_same_seed_gives_identical_tickets():
    assert build("starter")[1] == build("starter")[1]