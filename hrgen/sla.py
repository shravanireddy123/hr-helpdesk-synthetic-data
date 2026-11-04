"""SLA, Resolution and escalation. All values are DERIVED: no randomness here.

Inputs are the finished tables (tickets, assignments, events, messages, citations).
Outputs: sla, resolution, the full assignment list (with escalation rows) and the
full event list (with escalation events, renumbered per ticket).
"""
from datetime import datetime, timedelta

from .business_calendar import add_business_minutes, business_minutes_between
from .rules import SLA_TARGET_MINUTES

P1_UNTOUCHED_MINUTES = 120        # P1 with no HR message for 2 business hours -> escalate
ESCALATION_RETURN_MINUTES = 10    # business minutes until work resumes after escalation


def _dt(s: str) -> datetime:
    return datetime.fromisoformat(s)


def _iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def paused_minutes(events: list[dict]) -> int:
    """Business minutes spent in pending_employee (the SLA clock is paused there).

    A pause starts at the event that moves the ticket INTO pending_employee and
    ends at the very next event (reply -> in_progress, or no_response -> closed).
    """
    total = 0
    for prev, cur in zip(events, events[1:]):
        if prev["to_status"] == "pending_employee":
            total += business_minutes_between(_dt(prev["event_at"]), _dt(cur["event_at"]))
    return total


def build_sla(tables: dict) -> dict[str, list[dict]]:
    """Derive sla + resolution rows and add escalation events/assignments."""
    employees = tables["employee"]
    admin_id = min(e["employee_id"] for e in employees if e["role"] == "admin")
    hr_leads = sorted(e["employee_id"] for e in employees if e["role"] == "hr_partner")

    events_by: dict[str, list[dict]] = {}
    for e in tables["ticket_status_event"]:          # already sorted by event_id
        events_by.setdefault(e["ticket_id"], []).append(e)
    msgs_by: dict[str, list[dict]] = {}
    for m in tables["message"]:                      # already sorted by message_id
        msgs_by.setdefault(m["ticket_id"], []).append(m)
    msg_ticket = {m["message_id"]: m["ticket_id"] for m in tables["message"]}
    cited = {msg_ticket[c["message_id"]]: c["version_id"] for c in tables["message_citation"]}
    first_asg = {a["ticket_id"]: a for a in tables["assignment"]}

    sla_rows, res_rows, new_asg, all_events = [], [], [], []

    for t in tables["ticket"]:
        tid, prio = t["ticket_id"], t["priority"]
        created = _dt(t["created_at"])
        first_target, res_target = SLA_TARGET_MINUTES[prio]
        evs = events_by[tid]

        # ---- SLA formulas (business minutes) -------------------------------
        paused = paused_minutes(evs)
        first_due = add_business_minutes(created, first_target)
        res_due = add_business_minutes(created, res_target + paused)
        hr_msgs = [m for m in msgs_by[tid] if m["sender_role"] != "employee"]
        first_at = _dt(hr_msgs[0]["sent_at"])        # every ticket gets an HR message

        # ---- Resolution (from the final events) ----------------------------
        assert evs[-1]["to_status"] == "closed", tid
        resolved_evt = next((e for e in evs if e["to_status"] == "resolved"), None)
        no_response = resolved_evt is None           # closed straight from pending_employee
        resolved_at = _dt((resolved_evt or evs[-1])["event_at"])

        # ---- Escalation -----------------------------------------------------
        if prio == "P1":
            trigger = add_business_minutes(created, P1_UNTOUCHED_MINUTES)
            reason = "escalation: P1 ticket untouched for 2 business hours"
        else:
            trigger = first_due
            reason = "escalation: first-response SLA breached"
        in_prog = next((i for i, e in enumerate(evs) if e["to_status"] == "in_progress"), None)
        escalate = in_prog is not None and first_at > trigger

        ordered: list[dict] = []
        esc_at = None
        for i, e in enumerate(evs):
            ordered.append(dict(e))
            if escalate and i == in_prog:
                next_at = _dt(evs[i + 1]["event_at"])
                esc_at = max(trigger, _dt(e["event_at"]) + timedelta(minutes=1))
                assert esc_at <= next_at, tid
                back_at = min(add_business_minutes(esc_at, ESCALATION_RETURN_MINUTES), next_at)
                original = first_asg[tid]["assignee_id"]
                lead = [h for h in hr_leads if h != original]
                lead_id = lead[int(tid[-6:]) % len(lead)]
                ordered.append({"event_id": "", "ticket_id": tid, "from_status": "in_progress",
                                "to_status": "escalated", "event_at": _iso(esc_at),
                                "actor_id": admin_id})
                ordered.append({"event_id": "", "ticket_id": tid, "from_status": "escalated",
                                "to_status": "in_progress", "event_at": _iso(back_at),
                                "actor_id": lead_id})
                new_asg.append({"assignment_id": f"ASG-{tid}-02", "ticket_id": tid,
                                "queue": "HR_LEAD", "assignee_id": lead_id,
                                "assigned_at": _iso(esc_at), "reason": reason})
        for n, e in enumerate(ordered, start=1):     # renumber: -01, -02, ... in time order
            e["event_id"] = f"EVT-{tid}-{n:02d}"
        all_events.extend(ordered)

        # ---- Resolution code -------------------------------------------------
        if no_response:
            code = "no_response"
        elif escalate:
            code = "escalated_resolved"
        elif t["is_sensitive"]:
            code = "referred"
        elif t["is_ambiguous"] or t["missing_context"]:
            code = "policy_clarified"
        else:
            code = "answered"

        sla_rows.append({
            "sla_id": f"SLA-{tid}", "ticket_id": tid, "priority": prio,
            "first_response_due": _iso(first_due), "resolution_due": _iso(res_due),
            "paused_minutes": paused, "first_responded_at": _iso(first_at),
            "business_minutes_to_first_response": business_minutes_between(created, first_at),
            "first_response_met": first_at <= first_due,
            "resolution_met": None if no_response else resolved_at <= res_due,
        })
        res_rows.append({
            "resolution_id": f"RES-{tid}", "ticket_id": tid, "resolved_at": _iso(resolved_at),
            "resolution_code": code, "cited_version_id": cited.get(tid),
            "business_minutes_to_resolve": business_minutes_between(created, resolved_at),
        })

    return {
        "sla": sorted(sla_rows, key=lambda r: r["sla_id"]),
        "resolution": sorted(res_rows, key=lambda r: r["resolution_id"]),
        "assignment": sorted(tables["assignment"] + new_asg, key=lambda a: a["assignment_id"]),
        "ticket_status_event": sorted(all_events, key=lambda e: e["event_id"]),
    }