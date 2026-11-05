"""Derived metrics (no randomness), computed from the FINAL exported tables."""
import math
import statistics
from collections import Counter

from .rules import find_effective_version

PRIORITIES = ("P1", "P2", "P3")


def _pct(part: int, whole: int):
    """Percentage rounded to 2 decimals (None if there is nothing to divide by)."""
    return round(100 * part / whole, 2) if whole else None


def _percentile(values: list[float], p: int) -> float:
    """Nearest-rank percentile: the smallest value with at least p% of values at or below it."""
    ordered = sorted(values)
    return ordered[max(0, math.ceil(p / 100 * len(ordered)) - 1)]


def compute_metrics(tables: dict, truth: dict) -> dict:
    tickets = {t["ticket_id"]: t for t in tables["ticket"]}
    n_tickets = len(tickets)

    # SLA attainment by priority (using the stored flags).
    first_ok, res_ok = {}, {}
    for p in PRIORITIES:
        rows = [s for s in tables["sla"] if s["priority"] == p]
        first_ok[p] = _pct(sum(1 for s in rows if s["first_response_met"]), len(rows))
        judged = [s for s in rows if s["resolution_met"] is not None]   # no_response has no verdict
        res_ok[p] = _pct(sum(1 for s in judged if s["resolution_met"]), len(judged))

    # Business hours to resolve (tickets that were actually resolved).
    hours = [r["business_minutes_to_resolve"] / 60 for r in tables["resolution"]
             if r["resolution_code"] != "no_response"]

    # Clarification and escalation, per ticket.
    clarified = {m["ticket_id"] for m in tables["message"] if m["message_type"] == "clarification_request"}
    replied = {m["ticket_id"] for m in tables["message"] if m["message_type"] == "employee_reply"}
    escalated = {e["ticket_id"] for e in tables["ticket_status_event"] if e["to_status"] == "escalated"}

    # Citation accuracy: does each cited version match the one in force on the ticket date?
    by_policy: dict[str, list[dict]] = {}
    version = {}
    for v in tables["policy_version"]:
        by_policy.setdefault(v["policy_id"], []).append(v)
        version[v["version_id"]] = v
    msg_ticket = {m["message_id"]: m["ticket_id"] for m in tables["message"]}
    correct = 0
    for c in tables["message_citation"]:
        day = tickets[msg_ticket[c["message_id"]]]["created_at"][:10]
        right = find_effective_version(by_policy[version[c["version_id"]]["policy_id"]], day)
        correct += right is not None and right["version_id"] == c["version_id"]

    # Sensitive routing accuracy: first assignment must be ER_CONFIDENTIAL.
    first_queue = {a["ticket_id"]: a["queue"] for a in tables["assignment"]
                   if a["assignment_id"].endswith("-01")}
    sensitive = [tid for tid, t in tickets.items() if t["is_sensitive"]]
    routed = sum(1 for tid in sensitive if first_queue[tid] == "ER_CONFIDENTIAL")

    per_category = Counter(t["category_id"] for t in tickets.values())
    msgs_per_category = Counter(tickets[m["ticket_id"]]["category_id"] for m in tables["message"])
    anomalies = Counter(g["issue_type"] for g in truth["ground_truth"])

    return {
        "tickets_total": n_tickets,
        "messages_total": len(tables["message"]),
        "first_response_sla_attainment_pct": first_ok,
        "resolution_sla_attainment_pct": res_ok,
        "business_hours_to_resolve": {
            "median": round(statistics.median(hours), 2) if hours else None,
            "p90": round(_percentile(hours, 90), 2) if hours else None,
        },
        "clarification_rate_pct": _pct(len(clarified), n_tickets),
        "clarification_reply_rate_pct": _pct(len(clarified & replied), len(clarified)),
        "escalation_rate_pct": _pct(len(escalated), n_tickets),
        "citation_accuracy_pct": _pct(correct, len(tables["message_citation"])),
        "sensitive_routing_accuracy_pct": _pct(routed, len(sensitive)),
        "tickets_per_category": dict(sorted(per_category.items())),
        "messages_per_category": dict(sorted(msgs_per_category.items())),
        "anomaly_counts": dict(sorted(anomalies.items())),
    }


def format_metrics(m: dict) -> str:
    """A short human-readable table for the end of a run."""
    def line(label, value):
        return f"  {label:<40}{value}"
    fr, rs, bh = (m["first_response_sla_attainment_pct"], m["resolution_sla_attainment_pct"],
                  m["business_hours_to_resolve"])
    return "\n".join([
        "Metrics:",
        line("first-response SLA met %  P1/P2/P3", " / ".join(str(fr[p]) for p in PRIORITIES)),
        line("resolution SLA met %      P1/P2/P3", " / ".join(str(rs[p]) for p in PRIORITIES)),
        line("business hours to resolve (median, p90)", f"{bh['median']}, {bh['p90']}"),
        line("clarification rate %", m["clarification_rate_pct"]),
        line("clarification reply rate %", m["clarification_reply_rate_pct"]),
        line("escalation rate %", m["escalation_rate_pct"]),
        line("citation accuracy %", m["citation_accuracy_pct"]),
        line("sensitive routing accuracy %", m["sensitive_routing_accuracy_pct"]),
        line("anomalies", m["anomaly_counts"]),
    ])