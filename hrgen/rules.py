"""Pure business rules for the HR helpdesk (no randomness, no tables).

Every function takes plain values and returns plain values, so each rule can be
unit-tested on its own and reused by later stages (SLA, escalation, validation).
"""

SENSITIVE_KEYWORDS = ("harassment", "grievance", "misconduct", "medical")
IT_KEYWORDS = ("laptop", "access", "vpn", "email account")

# Category -> default queue (onboarding is refined by routing below).
QUEUE_FOR_CATEGORY = {
    "CAT-LEAVE": "LEAVE",
    "CAT-BENEFITS": "BENEFITS",
    "CAT-PAYROLL": "PAYROLL",
    "CAT-ONBOARDING": "GENERAL",
    "CAT-ER": "ER_CONFIDENTIAL",
    "CAT-GENERAL": "GENERAL",
}

# Queue -> role of the employee who may be assigned. "HR lead" = hr_partner.
ASSIGNEE_ROLE_FOR_QUEUE = {
    "GENERAL": "hr_partner",
    "BENEFITS": "hr_partner",
    "LEAVE": "hr_partner",
    "PAYROLL": "hr_partner",
    "IT_OPS": "it_ops_partner",
    "ER_CONFIDENTIAL": "hr_er_specialist",
    "HR_LEAD": "hr_partner",
}

# Priority -> (first response, resolution) targets in BUSINESS MINUTES.
SLA_TARGET_MINUTES = {
    "P1": (4 * 60, 16 * 60),
    "P2": (8 * 60, 24 * 60),
    "P3": (16 * 60, 40 * 60),
}

# Allowed (from_status, to_status) pairs. (None, "new") is the first event.
ALLOWED_TRANSITIONS = {
    (None, "new"),
    ("new", "assigned"),
    ("assigned", "pending_employee"),
    ("assigned", "in_progress"),
    ("pending_employee", "in_progress"),
    ("pending_employee", "closed"),
    ("in_progress", "escalated"),
    ("escalated", "in_progress"),
    ("in_progress", "resolved"),
    ("resolved", "closed"),
}


def is_sensitive(category_id: str, subject: str) -> bool:
    """Sensitive if the category is Employee Relations or the subject has a keyword."""
    text = subject.lower()
    return category_id == "CAT-ER" or any(k in text for k in SENSITIVE_KEYWORDS)


def route_queue(category_id: str, subject: str, sensitive: bool) -> str:
    """Pick the queue: sensitive first, then onboarding IT issues, then by category."""
    if sensitive:
        return "ER_CONFIDENTIAL"
    if category_id == "CAT-ONBOARDING" and any(k in subject.lower() for k in IT_KEYWORDS):
        return "IT_OPS"
    return QUEUE_FOR_CATEGORY[category_id]


def assignee_role(queue: str) -> str:
    """Role an assignee must have for a queue."""
    return ASSIGNEE_ROLE_FOR_QUEUE[queue]


def priority_for(category_id: str, sensitive: bool) -> str:
    """Sensitive -> P1, payroll -> P2, everything else -> P3."""
    if sensitive:
        return "P1"
    if category_id == "CAT-PAYROLL":
        return "P2"
    return "P3"
def find_effective_version(versions: list[dict], on_date: str) -> dict | None:
    """The policy version in force on `on_date` (YYYY-MM-DD string).

    `versions` are all versions of ONE policy. effective_to is the inclusive
    last day; an empty value means the version is still current.
    """
    for v in versions:
        if v["effective_from"] <= on_date and (v["effective_to"] is None or v["effective_to"] >= on_date):
            return v
    return None


def audience_allowed(policy_audience: str, employee_role: str) -> bool:
    """Candidates only see policies for 'all' or 'candidate'; others see 'all', 'employee', 'manager'."""
    if employee_role == "candidate":
        return policy_audience in ("all", "candidate")
    return policy_audience in ("all", "employee", "manager")