"""Edge-case injection and ground truth.

Runs AFTER all valid data exists. It deep-copies the tables it may change, corrupts a small
labelled sample (disjoint tickets), and returns the corrupted tables plus:
  ground_truth       one row per injected anomaly (never referenced by data tables)
  expected_decisions the answer key per ticket, computed from the CLEAN data
"""
import copy
import json
from datetime import datetime, timedelta
from random import Random

from .rules import SLA_TARGET_MINUTES

ANOMALY_RATE = 0.02     # about 2% of the eligible tickets per issue type
MIN_PER_TYPE = 3        # floor, so small scales still contain every type

RULE_REFERENCE = {
    "OBSOLETE_CITATION": "Citation rule: cite the PolicyVersion in force on ticket.created_at",
    "SENSITIVE_MISROUTED": "Routing rule: sensitive tickets go to ER_CONFIDENTIAL",
    "SLA_BUSINESS_HOURS_ERROR": "SLA rule: due times use business hours (Mon-Fri 09:30-18:00 IST, minus holidays)",
    "UNSUPPORTED_CLAIM": "Supported-claims rule: answers state only facts present in the cited version's key_rules",
}

UNSUPPORTED_CLAIMS = [
    "Employees also receive 30 days of paid leave every year.",
    "All reimbursement claims are paid within 24 hours.",
    "Unused benefits are automatically converted to cash every March.",
    "Contract staff have exactly the same entitlement as permanent staff.",
    "This policy applies retroactively to the last five years.",
]

CHANGED_TABLES = ("message", "message_citation", "assignment", "sla", "resolution")


def _facts(version: dict) -> str:
    """Same wording that messages.py puts in an answer: 'rule name is value; ...'."""
    rules = json.loads(version["key_rules"])
    return "; ".join(f"{k.replace('_', ' ')} is {v}" for k, v in sorted(rules.items()))


def _count(pool_size: int) -> int:
    """About 2% of the pool, at least MIN_PER_TYPE, never more than the pool."""
    return min(pool_size, max(MIN_PER_TYPE, round(ANOMALY_RATE * pool_size)))


def _iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def inject_anomalies(rng: Random, tables: dict) -> dict:
    """Return corrupted copies of five tables + ground_truth + expected_decisions."""
    tickets = {t["ticket_id"]: t for t in tables["ticket"]}
    msg_ticket = {m["message_id"]: m["ticket_id"] for m in tables["message"]}

    # ---- Answer key, from the CLEAN data (before any corruption) ----------------
    clean_first = {a["ticket_id"]: a for a in tables["assignment"]
                   if a["assignment_id"].endswith("-01")}
    clean_cite = {msg_ticket[c["message_id"]]: c for c in tables["message_citation"]}
    expected_decisions = [{
        "ticket_id": tid,
        "expected_queue": clean_first[tid]["queue"],
        "expected_version_id": clean_cite[tid]["version_id"] if tid in clean_cite else None,
        "needs_clarification": tickets[tid]["is_ambiguous"] or tickets[tid]["missing_context"],
    } for tid in sorted(tickets)]

    # ---- Working copies (the inputs are never modified) --------------------------
    out = {name: copy.deepcopy(tables[name]) for name in CHANGED_TABLES}
    msg = {m["message_id"]: m for m in out["message"]}
    cit = {msg_ticket[c["message_id"]]: c for c in out["message_citation"]}
    asg = {a["assignment_id"]: a for a in out["assignment"]}
    sla = {s["ticket_id"]: s for s in out["sla"]}
    res = {r["ticket_id"]: r for r in out["resolution"]}
    ver = {v["version_id"]: v for v in tables["policy_version"]}
    by_policy: dict[str, list[dict]] = {}
    for v in tables["policy_version"]:
        by_policy.setdefault(v["policy_id"], []).append(v)
    kb_for: dict[str, str] = {}
    for b in tables["kb_policy_version"]:
        kb_for.setdefault(b["version_id"], b["kb_id"])

    used: set[str] = set()                 # tickets that already carry an anomaly
    found: list[tuple] = []                # (type, entity, record_id, ticket_id, expected, observed)

    # 1) OBSOLETE_CITATION: rewrite the answer on an older version of the same policy.
    pool = sorted(tid for tid, c in cit.items() if ver[c["version_id"]]["version_no"] > 1)
    for tid in sorted(rng.sample(pool, _count(len(pool)))):
        c = cit[tid]
        old = ver[c["version_id"]]
        new = rng.choice([v for v in by_policy[old["policy_id"]] if v["version_no"] < old["version_no"]])
        new_facts = _facts(new)
        m = msg[c["message_id"]]
        assert c["snippet"] in m["body"], tid
        m["body"] = (m["body"].replace(c["snippet"], new_facts)
                     .replace(f"(version {old['version_no']})", f"(version {new['version_no']})"))
        c["version_id"], c["kb_id"], c["snippet"] = new["version_id"], kb_for.get(new["version_id"]), new_facts
        res[tid]["cited_version_id"] = new["version_id"]
        used.add(tid)
        found.append(("OBSOLETE_CITATION", "message_citation", c["message_id"], tid,
                      old["version_id"], new["version_id"]))

    # 2) SENSITIVE_MISROUTED: first assignment of a sensitive ticket lands in GENERAL.
    pool = sorted(tid for tid, t in tickets.items() if t["is_sensitive"] and tid not in used
                  and clean_first[tid]["queue"] == "ER_CONFIDENTIAL")
    for tid in sorted(rng.sample(pool, _count(len(pool)))):
        a = asg[f"ASG-{tid}-01"]
        a["queue"], a["reason"] = "GENERAL", "initial routing to GENERAL"
        used.add(tid)
        found.append(("SENSITIVE_MISROUTED", "assignment", a["assignment_id"], tid,
                      "ER_CONFIDENTIAL", "GENERAL"))

    # 3) SLA_BUSINESS_HOURS_ERROR: resolution_due computed with plain calendar minutes.
    def calendar_due(tid: str) -> str:
        t = tickets[tid]
        created = datetime.fromisoformat(t["created_at"])
        minutes = SLA_TARGET_MINUTES[t["priority"]][1] + sla[tid]["paused_minutes"]
        return _iso(created + timedelta(minutes=minutes))

    # Only tickets where the wrong (calendar) time really differs from the correct one.
    pool = sorted(tid for tid in tickets
                  if tid not in used and calendar_due(tid) != sla[tid]["resolution_due"])
    for tid in sorted(rng.sample(pool, _count(len(pool)))):
        s = sla[tid]
        expected_due, wrong = s["resolution_due"], calendar_due(tid)
        s["resolution_due"] = wrong
        used.add(tid)
        found.append(("SLA_BUSINESS_HOURS_ERROR", "sla", s["sla_id"], tid, expected_due, wrong))

    # 4) UNSUPPORTED_CLAIM: an invented rule is appended to the answer text.
    pool = sorted(tid for tid in cit if tid not in used)
    for tid in sorted(rng.sample(pool, _count(len(pool)))):
        claim = rng.choice(UNSUPPORTED_CLAIMS)
        mid = cit[tid]["message_id"]
        assert claim not in cit[tid]["snippet"]
        msg[mid]["body"] += " " + claim
        used.add(tid)
        found.append(("UNSUPPORTED_CLAIM", "message", mid, tid,
                      f"only facts in key_rules of {cit[tid]['version_id']}", claim))

    ground_truth = [{
        "issue_id": f"ISS-{n:04d}", "issue_type": kind, "entity": entity, "record_id": record,
        "ticket_id": tid, "expected_value": expected, "observed_value": observed,
        "rule_reference": RULE_REFERENCE[kind],
    } for n, (kind, entity, record, tid, expected, observed) in enumerate(found, start=1)]

    out["ground_truth"] = ground_truth
    out["expected_decisions"] = expected_decisions
    return out