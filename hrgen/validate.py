"""Validation of the EXPORTED files (what a stranger would receive).

Two kinds of checks:
  structural  must always pass (keys, formats, arithmetic, lifecycle, ...)
  rule        business rules that the injected anomalies deliberately break: the set of
              violating records must equal exactly the labelled ground-truth records.
"""
import hashlib
import json
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

from .business_calendar import add_business_minutes, business_minutes_between
from .config import REFERENCE_DATE, SCALES
from .export import COLUMNS, FKS, GROUND_TRUTH_TABLES, PK, TABLE_ORDER, UNIQUE
from .rules import (ALLOWED_TRANSITIONS, SLA_TARGET_MINUTES, audience_allowed,
                    find_effective_version)
from .sla import paused_minutes

QUEUES = {"GENERAL", "BENEFITS", "LEAVE", "PAYROLL", "IT_OPS", "ER_CONFIDENTIAL", "HR_LEAD"}
PRIORITIES = {"P1", "P2", "P3"}
STATUSES = {"new", "assigned", "pending_employee", "in_progress", "escalated", "resolved", "closed"}
ISSUE_TYPES = {"OBSOLETE_CITATION", "SENSITIVE_MISROUTED", "SLA_BUSINESS_HOURS_ERROR",
               "UNSUPPORTED_CLAIM"}

ENUMS = {
    ("employee", "role"): {"employee", "candidate", "manager", "hr_partner", "hr_er_specialist",
                           "it_ops_partner", "admin"},
    ("employee", "employment_type"): {"full_time", "part_time", "contract", "intern"},
    ("employee", "status"): {"active", "on_leave", "exited"},
    ("category", "default_queue"): QUEUES,
    ("category", "default_priority"): PRIORITIES,
    ("policy_document", "audience"): {"all", "employee", "manager", "candidate"},
    ("knowledge_article", "status"): {"published", "draft", "archived"},
    ("ticket", "priority"): PRIORITIES,
    ("assignment", "queue"): QUEUES,
    ("ticket_status_event", "to_status"): STATUSES,
    ("ticket_status_event", "from_status"): STATUSES | {""},
    ("message", "sender_role"): {"employee", "hr_agent", "hr_er_specialist", "it_ops_partner",
                                 "hr_lead", "system"},
    ("message", "message_type"): {"employee_question", "clarification_request", "employee_reply",
                                  "hr_answer", "resolution_note", "follow_up"},
    ("sla", "priority"): PRIORITIES,
    ("resolution", "resolution_code"): {"answered", "policy_clarified", "referred",
                                        "escalated_resolved", "no_response"},
    ("ground_truth", "issue_type"): ISSUE_TYPES,
}
BOOLEANS = {("category", "is_sensitive"), ("ticket", "is_sensitive"), ("ticket", "is_ambiguous"),
            ("ticket", "missing_context"), ("sla", "first_response_met"),
            ("sla", "resolution_met"), ("expected_decisions", "needs_clarification")}
OPTIONAL_BOOLEANS = {("sla", "resolution_met")}
DATETIME_COLS = {
    "knowledge_article": ["published_at"], "ticket": ["created_at"], "assignment": ["assigned_at"],
    "ticket_status_event": ["event_at"], "message": ["sent_at"],
    "sla": ["first_response_due", "resolution_due", "first_responded_at"],
    "resolution": ["resolved_at"],
}
DATE_COLS = {"employee": ["hire_date"], "policy_version": ["effective_from", "effective_to"]}
OPTIONAL_DATES = {("policy_version", "effective_to")}
INT_COLS = {"policy_version": ["version_no"],
            "sla": ["paused_minutes", "business_minutes_to_first_response"],
            "resolution": ["business_minutes_to_resolve"]}
OPTIONAL_FK = {("employee", "manager_id"), ("message_citation", "kb_id"),
               ("resolution", "cited_version_id")}
ENTITY_KEY = {"message_citation": ("message_citation", "message_id"),
              "assignment": ("assignment", "assignment_id"),
              "sla": ("sla", "sla_id"), "message": ("message", "message_id")}
LABEL_COLUMNS = {"issue_type", "issue_id", "is_anomaly", "anomaly", "label",
                 "expected_value", "observed_value"}


class _Report:
    """Collects check results."""

    def __init__(self) -> None:
        self.checks: list[dict] = []

    def structural(self, name: str, problems: list, ok_text: str) -> None:
        problems = list(problems)
        detail = ok_text if not problems else (
            f"{len(problems)} problem(s), e.g. " + "; ".join(str(p) for p in problems[:3]))
        self.checks.append({"name": name, "kind": "structural", "ok": not problems, "detail": detail})

    def rule(self, name: str, found, expected) -> None:
        found, expected = set(found), set(expected)
        self.checks.append({
            "name": name, "kind": "rule", "ok": found == expected,
            "found": sorted(found), "expected": sorted(expected),
            "detail": (f"{len(found)} violation(s); {len(expected)} labelled in ground truth; "
                       f"{len(found - expected)} unexplained, {len(expected - found)} not detected"),
        })

    def last_ok(self) -> bool:
        return self.checks[-1]["ok"]


def _read(path: Path) -> list[dict]:
    """CSV -> list of dicts; every value is a string and empty cells stay ''."""
    return pd.read_csv(path, dtype=str, keep_default_na=False).to_dict("records")


def _group(rows: list[dict], key: str = "ticket_id") -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        out[r[key]].append(r)
    return dict(out)


def _iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def _facts(version: dict) -> str:
    rules = json.loads(version["key_rules"])
    return "; ".join(f"{k.replace('_', ' ')} is {v}" for k, v in sorted(rules.items()))


def _sequence_problems(label: str, groups: dict, prefix: str, width: int, id_col: str) -> list:
    problems = []
    for tid, rows in groups.items():
        want = [f"{prefix}-{tid}-{n:0{width}d}" for n in range(1, len(rows) + 1)]
        if [r[id_col] for r in rows] != want:
            problems.append(f"{label} ids not 1..n for {tid}")
    return problems


def run_checks(rep: _Report, tables: dict, truth: dict, scale) -> None:
    every = {**tables, **truth}
    names = TABLE_ORDER + GROUND_TRUTH_TABLES

    # ---------------- structure: schema, keys, duplicates ----------------
    rep.structural("Schema: columns match the data dictionary",
                   [f"{n}: columns differ" for n in names
                    if every[n] and list(every[n][0]) != COLUMNS[n]],
                   f"{len(names)} tables have the expected columns")
    if not rep.last_ok():
        return

    problems = []
    for n in names:
        seen = set()
        for r in every[n]:
            key = tuple(r[c] for c in PK[n])
            if "" in key:
                problems.append(f"{n}: empty primary key")
            elif key in seen:
                problems.append(f"{n}: duplicate key {key}")
            seen.add(key)
    rep.structural("Primary keys are unique and non-empty", problems,
                   f"{sum(len(every[n]) for n in names)} rows in {len(names)} tables")

    problems = []
    for n, cols in UNIQUE.items():
        for c in cols:
            vals = [r[c] for r in tables[n]]
            if len(vals) != len(set(vals)):
                problems.append(f"{n}.{c} is not unique")
    rep.structural("Unique columns (email, one SLA and one resolution per ticket)", problems,
                   "email, sla.ticket_id and resolution.ticket_id are unique")

    problems = []
    for n in names:
        rows = [tuple(r.values()) for r in every[n]]
        if len(rows) != len(set(rows)):
            problems.append(f"{n}: duplicate rows")
    keys = [(t["employee_id"], t["category_id"], t["subject"], t["created_at"])
            for t in tables["ticket"]]
    if len(keys) != len(set(keys)):
        problems.append("duplicate tickets (same employee, category, subject and time)")
    rep.structural("No duplicate rows or duplicate tickets", problems, "no duplicates found")

    # ---------------- formats ----------------
    problems = []
    for n, cols in DATETIME_COLS.items():
        for r in every[n]:
            for c in cols:
                try:
                    datetime.fromisoformat(r[c])
                except ValueError:
                    problems.append(f"{n}.{c}={r[c]!r}")
    for n, cols in DATE_COLS.items():
        for r in every[n]:
            for c in cols:
                if r[c] == "" and (n, c) in OPTIONAL_DATES:
                    continue
                try:
                    date.fromisoformat(r[c])
                except ValueError:
                    problems.append(f"{n}.{c}={r[c]!r}")
    for n, cols in INT_COLS.items():
        for r in every[n]:
            for c in cols:
                try:
                    int(r[c])
                except ValueError:
                    problems.append(f"{n}.{c}={r[c]!r}")
    rep.structural("Formats: dates, timestamps and integers parse", problems,
                   "all date, timestamp and integer columns parse")
    if not rep.last_ok():
        return

    problems = []
    for (n, c), allowed in ENUMS.items():
        bad = sorted({r[c] for r in every[n]} - allowed)
        if bad:
            problems.append(f"{n}.{c}: {bad}")
    for n, c in sorted(BOOLEANS):
        allowed = {"true", "false"} | ({""} if (n, c) in OPTIONAL_BOOLEANS else set())
        bad = sorted({r[c] for r in every[n]} - allowed)
        if bad:
            problems.append(f"{n}.{c}: {bad}")
    rep.structural("Enums and booleans only use allowed values", problems,
                   f"{len(ENUMS)} enum columns and {len(BOOLEANS)} boolean columns are valid")

    # ---------------- completeness and foreign keys ----------------
    ticket = {t["ticket_id"]: t for t in tables["ticket"]}
    employee = {e["employee_id"]: e for e in tables["employee"]}
    sla = {s["ticket_id"]: s for s in tables["sla"]}
    res = {r["ticket_id"]: r for r in tables["resolution"]}
    msgs = _group(tables["message"])
    events = _group(tables["ticket_status_event"])
    asg = _group(tables["assignment"])
    problems = []
    for label, group in (("sla", sla), ("resolution", res), ("messages", msgs),
                         ("status events", events), ("assignments", asg)):
        if set(group) != set(ticket):
            problems.append(f"{label} do not cover exactly the tickets")
    rep.structural("Completeness: every ticket has SLA, resolution, messages, events, assignment",
                   problems, f"all {len(ticket)} tickets are fully covered")
    if not rep.last_ok():
        return

    problems = []
    for n, fks in FKS.items():
        for col, parent, pcol in fks:
            parent_ids = {r[pcol] for r in tables[parent]}
            for r in tables[n]:
                v = r[col]
                if v == "":
                    if (n, col) not in OPTIONAL_FK:
                        problems.append(f"{n}.{col} is empty")
                elif v not in parent_ids:
                    problems.append(f"{n}.{col}={v} has no parent in {parent}")
    problems += [f"employee {e['employee_id']} is their own manager"
                 for e in tables["employee"] if e["manager_id"] == e["employee_id"]]
    for n in GROUND_TRUTH_TABLES:
        problems += [f"{n}.ticket_id={r['ticket_id']} is not a ticket"
                     for r in truth[n] if r["ticket_id"] not in ticket]
    for g in truth["ground_truth"]:
        table, col = ENTITY_KEY[g["entity"]]
        if g["record_id"] not in {r[col] for r in tables[table]}:
            problems.append(f"ground_truth {g['issue_id']}: {g['record_id']} not in {table}")
    rep.structural("Foreign keys exist (data and ground truth)", problems,
                   f"{sum(len(v) for v in FKS.values())} foreign-key columns all resolve")
    if not rep.last_ok():
        return

    # ---------------- counts, versions, ids ----------------
    want = {"department": scale.departments, "employee": scale.employees, "category": 6,
            "policy_document": scale.policy_documents, "knowledge_article": scale.knowledge_articles,
            "ticket": scale.tickets, "message": scale.messages, "sla": scale.tickets,
            "resolution": scale.tickets}
    problems = [f"{n}: {len(tables[n])} rows, expected {c}" for n, c in want.items()
                if len(tables[n]) != c]
    linked = {b["kb_id"] for b in tables["kb_policy_version"]}
    if linked != {a["kb_id"] for a in tables["knowledge_article"]}:
        problems.append("some knowledge article has no policy-version link")
    rep.structural(f"Row counts match the '{scale.name}' scale", problems,
                   f"{scale.tickets} tickets, {scale.messages} messages, "
                   f"{scale.knowledge_articles} articles")

    problems = []
    by_pol = _group(tables["policy_version"], "policy_id")
    if set(by_pol) != {p["policy_id"] for p in tables["policy_document"]}:
        problems.append("a policy has no version")
    for pid, vs in by_pol.items():
        vs = sorted(vs, key=lambda v: int(v["version_no"]))
        if [int(v["version_no"]) for v in vs] != list(range(1, len(vs) + 1)):
            problems.append(f"{pid}: version numbers not 1..n")
        if [v["version_id"] for v in vs] != [f"VER-{pid}-{n:02d}" for n in range(1, len(vs) + 1)]:
            problems.append(f"{pid}: version ids do not follow the format")
        if [v["effective_to"] == "" for v in vs] != [False] * (len(vs) - 1) + [True]:
            problems.append(f"{pid}: exactly the latest version must be current")
        for a, b in zip(vs, vs[1:]):
            if a["effective_to"] and (date.fromisoformat(b["effective_from"])
                                      - date.fromisoformat(a["effective_to"])) != timedelta(days=1):
                problems.append(f"{pid}: versions {a['version_no']}/{b['version_no']} overlap or leave a gap")
        problems += [f"{v['version_id']}: effective_from is not before effective_to" for v in vs
                     if v["effective_to"] and v["effective_from"] >= v["effective_to"]]
    rep.structural("Policy versions: no overlaps, one current version per policy", problems,
                   f"{len(by_pol)} policies have consecutive, non-overlapping versions")

    problems = (_sequence_problems("message", msgs, "MSG", 3, "message_id")
                + _sequence_problems("event", events, "EVT", 2, "event_id")
                + _sequence_problems("assignment", asg, "ASG", 2, "assignment_id"))
    rep.structural("Ids: message, event and assignment sequences are 1..n per ticket "
                   "(no duplicate ticket/sequence pairs)", problems, "all sequences are gap-free")

    # ---------------- date order ----------------
    problems = []
    for tid, rows in msgs.items():
        times = [r["sent_at"] for r in rows]
        if any(b <= a for a, b in zip(times, times[1:])):
            problems.append(f"{tid}: message times do not strictly increase")
        if rows[0]["message_type"] != "employee_question":
            problems.append(f"{tid}: first message is not the question")
    for tid, rows in events.items():
        times = [r["event_at"] for r in rows]
        if any(b < a for a, b in zip(times, times[1:])):
            problems.append(f"{tid}: event times go backwards")
    rep.structural("Date order: message and event times increase within a ticket", problems,
                   "all timelines are in order")

    problems = []
    for tid, t in ticket.items():
        created = t["created_at"]
        if not (created < sla[tid]["first_responded_at"] <= res[tid]["resolved_at"]):
            problems.append(f"{tid}: created < first response <= resolved violated")
        if created[:10] > REFERENCE_DATE:
            problems.append(f"{tid}: created after the reference date")
        if employee[t["employee_id"]]["hire_date"] > created[:10]:
            problems.append(f"{tid}: raised before the employee was hired")
        if min(a["assigned_at"] for a in asg[tid]) < created:
            problems.append(f"{tid}: assigned before it was created")
    rep.structural("Date order: created < first response <= resolved; hired before ticket",
                   problems, "all tickets are consistent")

    # ---------------- derived values (SLA arithmetic) ----------------
    first_hr: dict[str, str] = {}
    for m in tables["message"]:
        if m["sender_role"] != "employee" and m["ticket_id"] not in first_hr:
            first_hr[m["ticket_id"]] = m["sent_at"]
    due_by_sla: dict[str, str] = {}
    bad_due: set[str] = set()
    problems = []
    for tid, t in ticket.items():
        created = datetime.fromisoformat(t["created_at"])
        s, r = sla[tid], res[tid]
        first_target, res_target = SLA_TARGET_MINUTES[t["priority"]]
        paused = paused_minutes(events[tid])
        first_due = add_business_minutes(created, first_target)
        res_due = add_business_minutes(created, res_target + paused)
        first_at = datetime.fromisoformat(s["first_responded_at"])
        resolved_at = datetime.fromisoformat(r["resolved_at"])
        no_resp = r["resolution_code"] == "no_response"
        expected = {
            "priority": t["priority"],
            "paused_minutes": str(paused),
            "first_response_due": _iso(first_due),
            "first_responded_at": first_hr[tid],
            "business_minutes_to_first_response": str(business_minutes_between(created, first_at)),
            "first_response_met": "true" if first_at <= first_due else "false",
            "resolution_met": "" if no_resp else ("true" if resolved_at <= res_due else "false"),
        }
        problems += [f"{s['sla_id']}.{col}" for col, w in expected.items() if s[col] != w]
        if r["business_minutes_to_resolve"] != str(business_minutes_between(created, resolved_at)):
            problems.append(f"{r['resolution_id']}.business_minutes_to_resolve")
        due_by_sla[s["sla_id"]] = _iso(res_due)
        if s["resolution_due"] != _iso(res_due):
            bad_due.add(s["sla_id"])        # judged by the rule check below
    rep.structural("Arithmetic: SLA fields, pauses, flags and resolution times recompute",
                   problems, "every derived SLA/resolution value recomputes (resolution_due is a rule check)")

    # ---------------- lifecycle ----------------
    problems = []
    for tid, rows in events.items():
        if rows[0]["from_status"] != "" or rows[0]["to_status"] != "new":
            problems.append(f"{tid}: first event is not (none)->new")
        for prev, cur in zip(rows, rows[1:]):
            if cur["from_status"] != prev["to_status"]:
                problems.append(f"{tid}: chain broken at {cur['event_id']}")
            if (cur["from_status"], cur["to_status"]) not in ALLOWED_TRANSITIONS:
                problems.append(f"{tid}: illegal transition {cur['from_status']}->{cur['to_status']}")
        if rows[-1]["to_status"] != "closed":
            problems.append(f"{tid}: not closed")
        if tid not in res:
            problems.append(f"{tid}: closed without a resolution")
    rep.structural("Lifecycle: only allowed transitions; every closed ticket has a resolution",
                   problems, f"{len(tables['ticket_status_event'])} events follow the lifecycle")

    problems = []
    for tid, r in res.items():
        evs = events[tid]
        resolved = [e for e in evs if e["to_status"] == "resolved"]
        if r["resolution_code"] == "no_response":
            if resolved or r["resolved_at"] != evs[-1]["event_at"] or r["cited_version_id"] != "":
                problems.append(f"{tid}: inconsistent no_response resolution")
        elif len(resolved) != 1 or r["resolved_at"] != resolved[0]["event_at"] or not r["cited_version_id"]:
            problems.append(f"{tid}: resolution does not match its resolved event")
    rep.structural("Resolution rows match the final status events", problems,
                   "resolved_at, code and citation agree with the events")

    problems = []
    for tid in ticket:
        esc = [e for e in events[tid] if e["to_status"] == "escalated"]
        lead = [a for a in asg[tid] if a["queue"] == "HR_LEAD"]
        if len(esc) != len(lead) or len(asg[tid]) != 1 + len(esc):
            problems.append(f"{tid}: escalation events and HR_LEAD assignments differ")
        elif esc and lead[0]["assigned_at"] != esc[0]["event_at"]:
            problems.append(f"{tid}: escalation and assignment times differ")
    rep.structural("Escalations: each has one HR_LEAD assignment at the same time", problems,
                   "escalation events and assignments agree")

    # ---------------- citations ----------------
    msg = {m["message_id"]: m for m in tables["message"]}
    cit = {c["message_id"]: c for c in tables["message_citation"]}
    bridge = {(b["kb_id"], b["version_id"]) for b in tables["kb_policy_version"]}
    version = {v["version_id"]: v for v in tables["policy_version"]}
    by_policy = {pid: [{**v, "effective_to": v["effective_to"] or None} for v in vs]
                 for pid, vs in by_pol.items()}

    def in_force(version_id: str, day: str):
        return find_effective_version(by_policy[version[version_id]["policy_id"]], day)

    answers = {m["message_id"] for m in tables["message"] if m["message_type"] == "hr_answer"}
    problems = []
    if answers != set(cit) or len(cit) != len(tables["message_citation"]):
        problems.append("each hr_answer needs exactly one citation and nothing else may be cited")
    for c in tables["message_citation"]:
        if not c["snippet"]:
            problems.append(f"{c['message_id']}: empty snippet")
        if c["kb_id"] and (c["kb_id"], c["version_id"]) not in bridge:
            problems.append(f"{c['message_id']}: kb article does not link to the cited version")
    rep.structural("Citations: one per hr_answer, valid snippet and knowledge-article link",
                   problems, f"{len(cit)} answers each have one citation")

    # ---------------- ground truth and answer key ----------------
    asg_by_id = {a["assignment_id"]: a for a in tables["assignment"]}
    sla_by_id = {s["sla_id"]: s for s in tables["sla"]}
    problems = []
    for g in truth["ground_truth"]:
        kind, rec, tid = g["issue_type"], g["record_id"], g["ticket_id"]
        if kind == "OBSOLETE_CITATION":
            c, m = cit.get(rec), msg.get(rec)
            right = in_force(c["version_id"], ticket[tid]["created_at"][:10]) if c else None
            if (not c or not m or m["ticket_id"] != tid or c["version_id"] != g["observed_value"]
                    or right is None or right["version_id"] != g["expected_value"]
                    or right["version_id"] == c["version_id"]):
                problems.append(g["issue_id"])
        elif kind == "SENSITIVE_MISROUTED":
            a = asg_by_id.get(rec)
            if (not a or a["ticket_id"] != tid or a["queue"] != g["observed_value"]
                    or g["expected_value"] != "ER_CONFIDENTIAL" or not ticket[tid]["is_sensitive"] == "true"):
                problems.append(g["issue_id"])
        elif kind == "SLA_BUSINESS_HOURS_ERROR":
            s = sla_by_id.get(rec)
            if (not s or s["ticket_id"] != tid or s["resolution_due"] != g["observed_value"]
                    or due_by_sla[rec] != g["expected_value"] or g["observed_value"] == g["expected_value"]):
                problems.append(g["issue_id"])
        elif kind == "UNSUPPORTED_CLAIM":
            m = msg.get(rec)
            if not m or m["ticket_id"] != tid or not m["body"].endswith(g["observed_value"]):
                problems.append(g["issue_id"])
    rep.structural("Ground-truth rows describe what is really in the data", problems,
                   f"{len(truth['ground_truth'])} labelled anomalies verified against the tables")

    problems = []
    for d in truth["expected_decisions"]:
        tid, t = d["ticket_id"], ticket[d["ticket_id"]]
        unclear = "true" if "true" in (t["is_ambiguous"], t["missing_context"]) else "false"
        if d["needs_clarification"] != unclear:
            problems.append(f"{tid}: needs_clarification")
        if t["is_sensitive"] == "true" and d["expected_queue"] != "ER_CONFIDENTIAL":
            problems.append(f"{tid}: sensitive ticket expects {d['expected_queue']}")
        v = d["expected_version_id"]
        if v and (in_force(v, t["created_at"][:10]) or {}).get("version_id") != v:
            problems.append(f"{tid}: expected version was not in force")
    if len(truth["expected_decisions"]) != len(ticket):
        problems.append("expected_decisions must cover every ticket")
    rep.structural("Answer key (expected_decisions) is correct and covers every ticket", problems,
                   f"{len(ticket)} expected decisions verified")

    # ---------------- rule checks: violations must equal the labelled anomalies ----------------
    def labelled(kind: str, field: str = "record_id") -> set:
        return {g[field] for g in truth["ground_truth"] if g["issue_type"] == kind}

    found = set()
    for c in tables["message_citation"]:
        t = ticket[msg[c["message_id"]]["ticket_id"]]
        right = in_force(c["version_id"], t["created_at"][:10])
        if right is None or right["version_id"] != c["version_id"]:
            found.add(c["message_id"])
    rep.rule("Rule: answer cites the policy version in force on the ticket date",
             found, labelled("OBSOLETE_CITATION"))

    found = {tid for tid, t in ticket.items()
             if t["is_sensitive"] == "true" and asg[tid][0]["queue"] != "ER_CONFIDENTIAL"}
    rep.rule("Rule: sensitive tickets are first routed to ER_CONFIDENTIAL",
             found, labelled("SENSITIVE_MISROUTED", "ticket_id"))

    rep.rule("Rule: SLA due times use business hours", bad_due, labelled("SLA_BUSINESS_HOURS_ERROR"))

    found = set()
    for c in tables["message_citation"]:
        v = version[c["version_id"]]
        if c["snippet"] != _facts(v) or not msg[c["message_id"]]["body"].endswith(c["snippet"] + "."):
            found.add(c["message_id"])
    rep.rule("Rule: answers state only facts from the cited version's key_rules",
             found, labelled("UNSUPPORTED_CLAIM"))

    found = set()
    for tid, t in ticket.items():
        if "true" in (t["is_ambiguous"], t["missing_context"]):
            types = [m["message_type"] for m in msgs[tid]]
            if "clarification_request" not in types or (
                    "hr_answer" in types
                    and types.index("hr_answer") < types.index("clarification_request")):
                found.add(tid)
    rep.rule("Rule: ambiguous or missing-context tickets get a clarification first", found, set())

    role = {e["employee_id"]: e["role"] for e in tables["employee"]}
    found = {tid for tid, t in ticket.items() if t["is_sensitive"] == "true"
             and any(role[a["assignee_id"]] == "manager" for a in asg[tid])}
    rep.rule("Rule: managers are never assigned to sensitive tickets", found, set())

    audience = {p["policy_id"]: p["audience"] for p in tables["policy_document"]}
    found = set()
    for c in tables["message_citation"]:
        raiser = employee[ticket[msg[c["message_id"]]["ticket_id"]]["employee_id"]]["role"]
        if not audience_allowed(audience[version[c["version_id"]]["policy_id"]], raiser):
            found.add(c["message_id"])
    rep.rule("Rule: citations respect the policy audience", found, set())


def _manifest_checks(rep: _Report, out: Path, manifest: dict, tables: dict, truth: dict) -> None:
    problems = []
    for rel, info in manifest["files"].items():
        path = out / rel
        if not path.exists():
            problems.append(f"missing {rel}")
        elif hashlib.sha256(path.read_bytes()).hexdigest() != info["sha256"]:
            problems.append(f"checksum mismatch {rel}")
    rep.structural("Manifest: every listed file exists and its SHA-256 matches", problems,
                   f"{len(manifest['files'])} files match their checksums")
    problems = [f"{n}: manifest says {manifest['row_counts'][n]}, file has {len(tables[n])}"
                for n in TABLE_ORDER if manifest["row_counts"][n] != len(tables[n])]
    problems += [f"{n}: manifest says {manifest['ground_truth_row_counts'][n]}, file has {len(truth[n])}"
                 for n in GROUND_TRUTH_TABLES
                 if manifest["ground_truth_row_counts"][n] != len(truth[n])]
    rep.structural("Manifest: row counts match the CSV files", problems, "all row counts match")


def _separation_checks(rep: _Report, out: Path, tables: dict) -> None:
    problems = [f"{n} has column {c}" for n in TABLE_ORDER for c in COLUMNS[n] if c in LABEL_COLUMNS]
    problems += [f"{n}.csv is in the data folder" for n in GROUND_TRUTH_TABLES
                 if (out / f"{n}.csv").exists()]
    if "issue_type" in (out / "seed.sql").read_text(encoding="utf-8"):
        problems.append("seed.sql contains ground-truth labels")
    rep.structural("Ground-truth separation: no labels in data tables or the SQL seed", problems,
                   "labels live only in ground_truth/")


def validate_dir(out: Path) -> tuple[list[dict], bool]:
    """Validate one exported folder. Returns (checks, all_ok)."""
    out = Path(out)
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    tables = {n: _read(out / f"{n}.csv") for n in TABLE_ORDER}
    truth = {n: _read(out / "ground_truth" / f"{n}.csv") for n in GROUND_TRUTH_TABLES}
    rep = _Report()
    _manifest_checks(rep, out, manifest, tables, truth)
    run_checks(rep, tables, truth, SCALES[manifest["scale"]])
    _separation_checks(rep, out, tables)
    return rep.checks, all(c["ok"] for c in rep.checks)


def write_summary(out: Path, checks: list[dict]) -> str:
    """Write validation_summary.md (no timestamps, so it is reproducible too)."""
    out = Path(out)
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    ok = all(c["ok"] for c in checks)
    failed = sum(1 for c in checks if not c["ok"])
    cell = lambda s: str(s).replace("|", "/")          # keep the Markdown tables intact
    status = lambda c: "PASS" if c["ok"] else "FAIL"
    lines = [
        "# Validation summary", "",
        f"- Scale: `{manifest['scale']}`  |  seed: `{manifest['seed']}`",
        f"- Overall: **{'PASS' if ok else 'FAIL'}** ({len(checks)} checks, {failed} failed)", "",
        "## Structural checks (must all pass)", "",
        "| # | Check | Result | Detail |", "|---|---|---|---|",
    ]
    for n, c in enumerate([c for c in checks if c["kind"] == "structural"], start=1):
        lines.append(f"| {n} | {cell(c['name'])} | {status(c)} | {cell(c['detail'])} |")
    lines += [
        "", "## Rule checks (must fail exactly on the labelled ground-truth records)", "",
        "A rule check PASSES when the records that break the rule are exactly the records "
        "labelled in `ground_truth/ground_truth.csv`. A rule with no anomaly type must have "
        "zero violations.", "",
        "| Rule | Violations found | Labelled in ground truth | Result |", "|---|---|---|---|",
    ]
    for c in [c for c in checks if c["kind"] == "rule"]:
        lines.append(f"| {cell(c['name'])} | {len(c['found'])} | {len(c['expected'])} | {status(c)} |")
    text = "\n".join(lines) + "\n"
    (out / "validation_summary.md").write_bytes(text.encode("utf-8"))
    return text
