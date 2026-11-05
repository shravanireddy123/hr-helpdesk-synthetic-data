import copy
import json
import random
from datetime import datetime, timedelta

import pytest
from faker import Faker

from hrgen.anomalies import inject_anomalies
from hrgen.business_calendar import add_business_minutes
from hrgen.config import SCALES
from hrgen.master_data import build_master_data
from hrgen.messages import build_messages
from hrgen.rules import SLA_TARGET_MINUTES, find_effective_version
from hrgen.sla import build_sla
from hrgen.tickets import build_tickets

TYPES = {"OBSOLETE_CITATION", "SENSITIVE_MISROUTED", "SLA_BUSINESS_HOURS_ERROR", "UNSUPPORTED_CLAIM"}
GT_COLUMNS = ["issue_id", "issue_type", "entity", "record_id", "ticket_id",
              "expected_value", "observed_value", "rule_reference"]
LABEL_COLUMNS = {"issue_type", "issue_id", "is_anomaly", "anomaly", "label"}


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
    clean = copy.deepcopy(tables)
    anom = inject_anomalies(rng, tables)
    return tables, clean, anom


@pytest.fixture(scope="module", params=["starter", "full"])
def built(request):
    return request.param, *build(request.param)


def by_type(anom):
    out = {}
    for g in anom["ground_truth"]:
        out.setdefault(g["issue_type"], []).append(g)
    return out


def changed(before, after, key):
    b = {r[key]: r for r in before}
    a = {r[key]: r for r in after}
    assert b.keys() == a.keys()
    return {k for k in a if a[k] != b[k]}


def facts(version):
    return "; ".join(f"{k.replace('_', ' ')} is {v}"
                     for k, v in sorted(json.loads(version["key_rules"]).items()))


def test_each_type_present_and_small(built):
    _, _, clean, anom = built
    groups = by_type(anom)
    assert set(groups) == TYPES
    for rows in groups.values():
        assert 3 <= len(rows) <= 0.05 * len(clean["ticket"])


def test_ground_truth_shape(built):
    _, _, clean, anom = built
    gt = anom["ground_truth"]
    assert all(list(g) == GT_COLUMNS for g in gt)
    assert [g["issue_id"] for g in gt] == [f"ISS-{n:04d}" for n in range(1, len(gt) + 1)]
    tickets = [g["ticket_id"] for g in gt]
    assert len(tickets) == len(set(tickets))                      # one anomaly per ticket
    assert set(tickets) <= {t["ticket_id"] for t in clean["ticket"]}


def test_no_label_columns_in_data_tables(built):
    _, _, _, anom = built
    for name in ("message", "message_citation", "assignment", "sla", "resolution"):
        assert not (set(anom[name][0]) & LABEL_COLUMNS), name


def test_inputs_are_not_modified(built):
    _, original, clean, _ = built
    assert original == clean


def test_only_labelled_records_changed(built):
    _, _, clean, anom = built
    g = by_type(anom)
    obs = {x["record_id"] for x in g["OBSOLETE_CITATION"]}
    obs_tickets = {x["ticket_id"] for x in g["OBSOLETE_CITATION"]}
    unsup = {x["record_id"] for x in g["UNSUPPORTED_CLAIM"]}
    assert changed(clean["message"], anom["message"], "message_id") == obs | unsup
    assert changed(clean["message_citation"], anom["message_citation"], "message_id") == obs
    assert changed(clean["assignment"], anom["assignment"], "assignment_id") == \
        {x["record_id"] for x in g["SENSITIVE_MISROUTED"]}
    assert changed(clean["sla"], anom["sla"], "sla_id") == \
        {x["record_id"] for x in g["SLA_BUSINESS_HOURS_ERROR"]}
    assert changed(clean["resolution"], anom["resolution"], "resolution_id") == \
        {f"RES-{t}" for t in obs_tickets}


def test_obsolete_citations(built):
    _, _, clean, anom = built
    ver = {v["version_id"]: v for v in clean["policy_version"]}
    by_pol = {}
    for v in clean["policy_version"]:
        by_pol.setdefault(v["policy_id"], []).append(v)
    tickets = {t["ticket_id"]: t for t in clean["ticket"]}
    msg = {m["message_id"]: m for m in anom["message"]}
    cit = {c["message_id"]: c for c in anom["message_citation"]}
    res = {r["ticket_id"]: r for r in anom["resolution"]}
    for g in by_type(anom)["OBSOLETE_CITATION"]:
        day = tickets[g["ticket_id"]]["created_at"][:10]
        right, old = ver[g["expected_value"]], ver[g["observed_value"]]
        assert right["policy_id"] == old["policy_id"] and old["version_no"] < right["version_no"]
        assert find_effective_version(by_pol[right["policy_id"]], day)["version_id"] == right["version_id"]
        assert old["effective_to"] < day                              # really superseded
        c = cit[g["record_id"]]
        assert c["version_id"] == old["version_id"] and c["snippet"] == facts(old)
        assert c["snippet"] in msg[g["record_id"]]["body"]
        assert res[g["ticket_id"]]["cited_version_id"] == old["version_id"]
    # every citation that disagrees with the version in force is a labelled row
    msg_ticket = {m["message_id"]: m["ticket_id"] for m in anom["message"]}
    mismatched = set()
    for c in anom["message_citation"]:
        v = ver[c["version_id"]]
        day = tickets[msg_ticket[c["message_id"]]]["created_at"][:10]
        if find_effective_version(by_pol[v["policy_id"]], day)["version_id"] != c["version_id"]:
            mismatched.add(c["message_id"])
    assert mismatched == {x["record_id"] for x in by_type(anom)["OBSOLETE_CITATION"]}


def test_sensitive_misrouted(built):
    _, _, clean, anom = built
    tickets = {t["ticket_id"]: t for t in clean["ticket"]}
    first = {a["ticket_id"]: a for a in anom["assignment"] if a["assignment_id"].endswith("-01")}
    decisions = {d["ticket_id"]: d for d in anom["expected_decisions"]}
    rows = by_type(anom)["SENSITIVE_MISROUTED"]
    wrong = {tid for tid, t in tickets.items()
             if t["is_sensitive"] and first[tid]["queue"] != "ER_CONFIDENTIAL"}
    assert wrong == {g["ticket_id"] for g in rows}
    for g in rows:
        assert tickets[g["ticket_id"]]["is_sensitive"]
        assert (g["expected_value"], g["observed_value"]) == ("ER_CONFIDENTIAL", "GENERAL")
        assert first[g["ticket_id"]]["queue"] == "GENERAL"
        assert decisions[g["ticket_id"]]["expected_queue"] == "ER_CONFIDENTIAL"


def test_sla_business_hours_error(built):
    _, _, clean, anom = built
    tickets = {t["ticket_id"]: t for t in clean["ticket"]}
    clean_sla = {s["sla_id"]: s for s in clean["sla"]}
    new_sla = {s["sla_id"]: s for s in anom["sla"]}

    def right_due(s):
        t = tickets[s["ticket_id"]]
        created = datetime.fromisoformat(t["created_at"])
        return created, SLA_TARGET_MINUTES[t["priority"]][1] + s["paused_minutes"]

    for g in by_type(anom)["SLA_BUSINESS_HOURS_ERROR"]:
        s = clean_sla[g["record_id"]]
        created, minutes = right_due(s)
        assert g["expected_value"] == s["resolution_due"] == \
            add_business_minutes(created, minutes).isoformat(timespec="seconds")
        assert g["observed_value"] == (created + timedelta(minutes=minutes)).isoformat(timespec="seconds")
        assert g["observed_value"] != g["expected_value"]
        assert new_sla[g["record_id"]]["resolution_due"] == g["observed_value"]
    mismatched = set()
    for s in anom["sla"]:
        created, minutes = right_due(s)
        if s["resolution_due"] != add_business_minutes(created, minutes).isoformat(timespec="seconds"):
            mismatched.add(s["sla_id"])
    assert mismatched == {g["record_id"] for g in by_type(anom)["SLA_BUSINESS_HOURS_ERROR"]}


def test_unsupported_claims(built):
    _, _, clean, anom = built
    clean_msg = {m["message_id"]: m for m in clean["message"]}
    new_msg = {m["message_id"]: m for m in anom["message"]}
    cit = {c["message_id"]: c for c in anom["message_citation"]}
    for g in by_type(anom)["UNSUPPORTED_CLAIM"]:
        mid, claim = g["record_id"], g["observed_value"]
        assert new_msg[mid]["message_type"] == "hr_answer"
        assert new_msg[mid]["body"] == clean_msg[mid]["body"] + " " + claim
        assert claim not in cit[mid]["snippet"]


def test_expected_decisions_are_the_answer_key(built):
    _, _, clean, anom = built
    dec = anom["expected_decisions"]
    assert [d["ticket_id"] for d in dec] == sorted(t["ticket_id"] for t in clean["ticket"])
    assert set(dec[0]) == {"ticket_id", "expected_queue", "expected_version_id", "needs_clarification"}
    tickets = {t["ticket_id"]: t for t in clean["ticket"]}
    ver = {v["version_id"]: v for v in clean["policy_version"]}
    by_pol = {}
    for v in clean["policy_version"]:
        by_pol.setdefault(v["policy_id"], []).append(v)
    first = {a["ticket_id"]: a for a in clean["assignment"] if a["assignment_id"].endswith("-01")}
    msg_ticket = {m["message_id"]: m["ticket_id"] for m in clean["message"]}
    cite = {msg_ticket[c["message_id"]]: c for c in clean["message_citation"]}
    for d in dec:
        tid, t = d["ticket_id"], tickets[d["ticket_id"]]
        assert d["expected_queue"] == first[tid]["queue"]
        assert d["needs_clarification"] == (t["is_ambiguous"] or t["missing_context"])
        if tid in cite:
            v = ver[d["expected_version_id"]]
            assert find_effective_version(by_pol[v["policy_id"]], t["created_at"][:10]) == v
        else:
            assert d["expected_version_id"] is None


def test_same_seed_gives_identical_anomalies():
    assert build("starter")[2] == build("starter")[2]