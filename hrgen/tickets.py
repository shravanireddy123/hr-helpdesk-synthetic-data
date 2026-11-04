"""Tickets, first assignments and the first status events.

Randomness comes only from the `rng` passed in. Messages, SLAs and anomalies
are added by later stages.
"""
from datetime import date, datetime, time, timedelta
from random import Random

from . import ids
from .business_calendar import is_business_day
from .config import Scale
from .rules import assignee_role, is_sensitive, priority_for, route_queue

START_DATE = date(2026, 1, 5)
END_DATE = date(2026, 10, 15)

CATEGORY_MIX = [
    ("CAT-LEAVE", 30), ("CAT-BENEFITS", 22), ("CAT-PAYROLL", 22),
    ("CAT-ONBOARDING", 16), ("CAT-ER", 6), ("CAT-GENERAL", 4),
]

SUBJECTS = {
    "normal": {
        "CAT-LEAVE": ["How many annual leave days do I have left?",
                      "Carry forward of unused leave to next year",
                      "Maternity leave eligibility and notice period",
                      "Sick leave balance for this year",
                      "Applying for compensatory off",
                      "Medical leave certificate requirement"],
        "CAT-BENEFITS": ["Adding a dependent to group health insurance",
                         "Provident fund VPF contribution change",
                         "Claiming my wellness allowance",
                         "Meal card top-up not received",
                         "Learning budget reimbursement process"],
        "CAT-PAYROLL": ["My salary was short this month",
                        "Reimbursement claim still pending",
                        "Tax declaration proof submission deadline",
                        "Payslip for last month not available",
                        "Bonus payout date query"],
        "CAT-ONBOARDING": ["Laptop not delivered before joining date",
                           "Access to email account not working",
                           "VPN access request for new joiner",
                           "Documents needed for joining formalities",
                           "Background verification status",
                           "Induction schedule for first week"],
        "CAT-ER": ["Harassment complaint about a colleague",
                   "Grievance about my appraisal rating",
                   "Misconduct report involving my team",
                   "Request for medical accommodation at work"],
        "CAT-GENERAL": ["Work from home days allowed per week",
                        "Employee referral bonus query",
                        "Dress code for client days",
                        "Visitor registration for the office"],
    },
    "ambiguous": {
        "CAT-LEAVE": ["Question about my leave"],
        "CAT-BENEFITS": ["Need help with my benefits"],
        "CAT-PAYROLL": ["Something is wrong with my pay"],
        "CAT-ONBOARDING": ["Need help with joining"],
        "CAT-ER": ["I need to discuss something confidential"],
        "CAT-GENERAL": ["Need clarification on a policy"],
    },
    "missing": {
        "CAT-LEAVE": ["Leave not showing correctly"],
        "CAT-BENEFITS": ["My claim was rejected"],
        "CAT-PAYROLL": ["Deduction in my salary"],
        "CAT-ONBOARDING": ["My documents were not accepted"],
        "CAT-ER": ["I want to report an incident"],
        "CAT-GENERAL": ["My request was not approved"],
    },
}


def random_created_at(rng: Random) -> datetime:
    """Random 2026 timestamp, clustered on business days and 09:00-19:00."""
    span = (END_DATE - START_DATE).days
    while True:
        day = START_DATE + timedelta(days=rng.randint(0, span))
        # 92% of tickets must fall on a business day; retry otherwise.
        if rng.random() < 0.92 and not is_business_day(day):
            continue
        break
    if rng.random() < 0.9:
        seconds = rng.randint(9 * 3600, 19 * 3600 - 1)   # working hours
    else:
        seconds = rng.randint(0, 24 * 3600 - 1)          # any time
    return datetime.combine(day, time()) + timedelta(seconds=seconds)


def build_tickets(rng: Random, employees: list[dict], scale: Scale) -> dict[str, list[dict]]:
    """Create tickets, first assignments and the first two status events each."""
    raisers = [e for e in employees if e["role"] in ("employee", "manager")
               and e["status"] != "exited"]
    candidates = [e for e in employees if e["role"] == "candidate"]
    staff: dict[str, list[dict]] = {}
    for e in employees:                      # employees are already in id order
        staff.setdefault(e["role"], []).append(e)
    admin_id = staff["admin"][0]["employee_id"]
    cat_ids = [c for c, _ in CATEGORY_MIX]
    cat_weights = [w for _, w in CATEGORY_MIX]

    # 1) Draft every ticket, 2) sort by time, 3) number them.
    drafts = []
    for _ in range(scale.tickets):
        cat = rng.choices(cat_ids, weights=cat_weights)[0]
        roll = rng.random()
        kind = "ambiguous" if roll < 0.12 else "missing" if roll < 0.20 else "normal"
        subject = rng.choice(SUBJECTS[kind][cat])
        created = random_created_at(rng)
        pool = candidates if (cat == "CAT-ONBOARDING" and rng.random() < 0.15) else raisers
        drafts.append({"cat": cat, "kind": kind, "subject": subject,
                       "created": created, "employee": rng.choice(pool)["employee_id"]})
    drafts.sort(key=lambda d: d["created"])   # stable sort: ties keep draft order

    tickets, assignments, events = [], [], []
    for n, d in enumerate(drafts, start=1):
        tid = ids.ticket_id(n)
        sensitive = is_sensitive(d["cat"], d["subject"])
        queue = route_queue(d["cat"], d["subject"], sensitive)
        assignee = rng.choice(staff[assignee_role(queue)])["employee_id"]
        assigned_at = d["created"] + timedelta(minutes=rng.randint(1, 10))
        tickets.append({
            "ticket_id": tid,
            "employee_id": d["employee"],
            "category_id": d["cat"],
            "subject": d["subject"],
            "created_at": d["created"].isoformat(timespec="seconds"),
            "priority": priority_for(d["cat"], sensitive),
            "is_sensitive": sensitive,
            "is_ambiguous": d["kind"] == "ambiguous",
            "missing_context": d["kind"] == "missing",
        })
        assignments.append({
            "assignment_id": f"ASG-{tid}-01",
            "ticket_id": tid,
            "queue": queue,
            "assignee_id": assignee,
            "assigned_at": assigned_at.isoformat(timespec="seconds"),
            "reason": f"initial routing to {queue}",
        })
        events.append({"event_id": f"EVT-{tid}-01", "ticket_id": tid, "from_status": None,
                       "to_status": "new", "event_at": d["created"].isoformat(timespec="seconds"),
                       "actor_id": d["employee"]})
        events.append({"event_id": f"EVT-{tid}-02", "ticket_id": tid, "from_status": "new",
                       "to_status": "assigned", "event_at": assigned_at.isoformat(timespec="seconds"),
                       "actor_id": admin_id})
    return {"ticket": tickets, "assignment": assignments, "ticket_status_event": events}