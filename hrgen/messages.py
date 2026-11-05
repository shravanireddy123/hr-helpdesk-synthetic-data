"""Messages, citations and the later status events for every ticket.

Script per ticket (times strictly increase, all delays are BUSINESS minutes):
  normal:   question -> hr_answer -> [follow_ups] -> resolution_note
  unclear:  question -> clarification_request -> employee_reply -> hr_answer
            -> [follow_ups] -> resolution_note
  or, if the employee never replies: question -> clarification_request, then
            the ticket closes as no_response after 5 business days.
Follow-ups are added to answered tickets so the total hits scale.messages exactly.
P1 tickets get shorter agent delays before the first HR message (see _scaled).
"""
import json
from datetime import datetime, timedelta
from random import Random

from . import ids
from .business_calendar import add_business_minutes
from .config import Scale
from .rules import audience_allowed, find_effective_version

# Subject keyword -> policy title (first match wins); else fall back by category.
SUBJECT_POLICY = [
    ("annual leave", "Annual Leave Policy"), ("carry forward", "Annual Leave Policy"),
    ("maternity", "Maternity Leave Policy"), ("sick leave", "Sick Leave Policy"),
    ("medical leave", "Sick Leave Policy"), ("compensatory", "Compensatory Off Policy"),
    ("health insurance", "Group Health Insurance Policy"),
    ("provident", "Provident Fund Contribution Policy"),
    ("wellness", "Wellness Allowance Policy"), ("meal card", "Meal Card Benefit"),
    ("learning", "Learning and Development Reimbursement"),
    ("salary", "Salary Payment Schedule"), ("reimbursement", "Expense Reimbursement Policy"),
    ("tax", "Tax Declaration and TDS Policy"), ("payslip", "Payslip and Form 16 Access"),
    ("bonus", "Bonus and Incentive Payout Policy"),
    ("laptop", "IT Equipment and Access Provisioning"),
    ("access", "IT Equipment and Access Provisioning"),
    ("vpn", "IT Equipment and Access Provisioning"),
    ("joining formalities", "New Joiner Onboarding Checklist"),
    ("background verification", "Background Verification Policy"),
    ("induction", "Buddy and Induction Programme"),
    ("harassment", "Anti-Harassment and POSH Policy"), ("grievance", "Grievance Redressal Policy"),
    ("misconduct", "Code of Conduct and Disciplinary Policy"),
    ("medical accommodation", "Medical Accommodation Policy"),
    ("work from home", "Work From Home Policy"), ("referral", "Employee Referral Programme"),
    ("dress code", "Dress Code and Office Conduct"), ("visitor", "Office Access and Visitor Policy"),
]

QUEUE_SENDER_ROLE = {"ER_CONFIDENTIAL": "hr_er_specialist", "IT_OPS": "it_ops_partner"}
NO_REPLY_RATE = 0.15
BUSINESS_DAY_MINUTES = 510


def pick_policy(subject: str, category_id: str, role: str, policies: list[dict],
                by_title: dict[str, dict]) -> dict:
    """Policy a ticket's answer cites: by subject keyword, else first allowed in the category."""
    text = subject.lower()
    for keyword, title in SUBJECT_POLICY:
        pol = by_title.get(title)            # None if the title is not in this scale
        if keyword in text and pol and audience_allowed(pol["audience"], role):
            return pol
    for p in policies:
        if p["category_id"] == category_id and audience_allowed(p["audience"], role):
            return p
    return next(p for p in policies if audience_allowed(p["audience"], role))


def _iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def _delay(rng: Random, at: datetime, lo: int, hi: int) -> datetime:
    """`at` plus a random number of BUSINESS minutes in [lo, hi]."""
    return add_business_minutes(at, rng.randint(lo, hi))


def _scaled(t: dict, lo: int, hi: int) -> tuple[int, int]:
    """P1 tickets are handled faster: delay ranges are cut to a quarter."""
    return (max(1, lo // 4), max(2, hi // 4)) if t["priority"] == "P1" else (lo, hi)


class _Timeline:
    """Owns the message and event counters of ONE ticket, so IDs never collide."""

    def __init__(self, tid: str, messages: list, events: list):
        self.tid, self.messages, self.events = tid, messages, events
        self.msg_no = 0
        self.evt_no = 2          # events 01 (new) and 02 (assigned) come from tickets.py

    def msg(self, sender_id, sender_role, mtype, at, body) -> str:
        self.msg_no += 1
        mid = ids.message_id(self.tid, self.msg_no)
        self.messages.append({"message_id": mid, "ticket_id": self.tid, "sender_id": sender_id,
                              "sender_role": sender_role, "message_type": mtype,
                              "sent_at": _iso(at), "body": body})
        return mid

    def evt(self, from_status, to_status, at, actor_id) -> None:
        self.evt_no += 1
        self.events.append({"event_id": f"EVT-{self.tid}-{self.evt_no:02d}", "ticket_id": self.tid,
                            "from_status": from_status, "to_status": to_status,
                            "event_at": _iso(at), "actor_id": actor_id})


def build_messages(rng: Random, master: dict, tix: dict, scale: Scale) -> dict[str, list[dict]]:
    """Returns message, message_citation and new_events (events 03+; merge into ticket_status_event)."""
    emp = {e["employee_id"]: e for e in master["employee"]}
    policies = master["policy_document"]
    by_title = {p["title"]: p for p in policies}
    versions: dict[str, list[dict]] = {}
    for v in master["policy_version"]:
        versions.setdefault(v["policy_id"], []).append(v)
    kb_for_version: dict[str, str] = {}
    for b in master["kb_policy_version"]:
        kb_for_version.setdefault(b["version_id"], b["kb_id"])
    first_asg = {a["ticket_id"]: a for a in tix["assignment"]}
    admin_id = next(e["employee_id"] for e in master["employee"] if e["role"] == "admin")
    tickets = tix["ticket"]

    # ---- Pass 1: decide who never replies, so the scripted total is known up front.
    no_reply_plan: list[bool] = []
    scripted = 0
    for t in tickets:
        unclear = t["is_ambiguous"] or t["missing_context"]
        no_reply = unclear and rng.random() < NO_REPLY_RATE
        no_reply_plan.append(no_reply)
        scripted += 2 if no_reply else (5 if unclear else 3)

    # Spread the shortfall over answered tickets: everyone gets `base`, `rem` random ones get +1.
    answered = [i for i, nr in enumerate(no_reply_plan) if not nr]
    needed = scale.messages - scripted
    if needed < 0 or (needed > 0 and not answered):
        raise ValueError(f"cannot reach {scale.messages} messages (scripted {scripted})")
    extras = {i: 0 for i in answered}
    if answered:
        base, rem = divmod(needed, len(answered))
        for i in answered:
            extras[i] = base
        for k in rng.sample(range(len(answered)), rem):
            extras[answered[k]] += 1

    # ---- Pass 2: build each ticket's whole timeline in one go.
    messages: list[dict] = []
    citations: list[dict] = []
    new_events: list[dict] = []
    for i, t in enumerate(tickets):
        tid, employee_id = t["ticket_id"], t["employee_id"]
        created = datetime.fromisoformat(t["created_at"])
        asg = first_asg[tid]
        agent_id = asg["assignee_id"]
        agent_role = QUEUE_SENDER_ROLE.get(asg["queue"], "hr_agent")
        unclear = t["is_ambiguous"] or t["missing_context"]
        tl = _Timeline(tid, messages, new_events)

        tl.msg(employee_id, "employee", "employee_question", created + timedelta(minutes=1),
               f"{t['subject']}. Please help.")
        now = datetime.fromisoformat(asg["assigned_at"])

        if unclear:
            now = _delay(rng, now, *_scaled(t, 30, 300))          # P1: faster
            tl.msg(agent_id, agent_role, "clarification_request", now,
                   "Could you share more details, such as dates, amounts or the policy "
                   "you are asking about, so we can answer accurately?")
            tl.evt("assigned", "pending_employee", now, agent_id)
            if no_reply_plan[i]:
                close_at = add_business_minutes(now, 5 * BUSINESS_DAY_MINUTES)
                tl.evt("pending_employee", "closed", close_at, admin_id)
                continue                                  # no answer, no citation
            now = _delay(rng, now, 60, 1500)
            tl.msg(employee_id, "employee", "employee_reply", now,
                   "Here are the details you asked for. Thank you.")
            tl.evt("pending_employee", "in_progress", now, employee_id)
        else:
            now = _delay(rng, now, *_scaled(t, 20, 240))          # P1: faster
            tl.evt("assigned", "in_progress", now, agent_id)

        # The answer cites the version in force on the ticket's creation date.
        policy = pick_policy(t["subject"], t["category_id"], emp[employee_id]["role"],
                             policies, by_title)
        version = find_effective_version(versions[policy["policy_id"]], t["created_at"][:10])
        assert version is not None, f"no version in force for {policy['policy_id']}"
        facts = "; ".join(f"{k.replace('_', ' ')} is {v}"
                          for k, v in sorted(json.loads(version["key_rules"]).items()))
        intro = ("Thank you for reaching out. Your case is confidential and handled by the "
                 "Employee Relations team. " if t["is_sensitive"] else "")
        now = _delay(rng, now, *_scaled(t, 30, 360))              # P1: faster
        answer_id = tl.msg(agent_id, agent_role, "hr_answer", now,
                           f"{intro}Under the {policy['title']} (version {version['version_no']}): {facts}.")
        citations.append({"message_id": answer_id, "version_id": version["version_id"],
                          "kb_id": kb_for_version.get(version["version_id"]), "snippet": facts})

        # Follow-ups alternate employee / agent, then the resolution note closes the story.
        for j in range(extras[i]):
            now = _delay(rng, now, 30, 600)
            if j % 2 == 0:
                tl.msg(employee_id, "employee", "follow_up", now,
                       "Thanks. I have one more question about this.")
            else:
                tl.msg(agent_id, agent_role, "follow_up", now,
                       "Happy to help. Please see the policy details shared above.")
        now = _delay(rng, now, 15, 240)
        tl.msg(agent_id, agent_role, "resolution_note", now,
               "Marking this ticket resolved. Please reopen if you need anything else.")
        tl.evt("in_progress", "resolved", now, agent_id)
        now = _delay(rng, now, 60, 1020)
        tl.evt("resolved", "closed", now, admin_id)

    new_events.sort(key=lambda e: e["event_id"])
    return {"message": messages, "message_citation": citations, "new_events": new_events}