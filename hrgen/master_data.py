"""Master (reference) data for the HR helpdesk generator.

Order matters: parents are generated before children, so every foreign key
points at a row that already exists. All randomness comes from the `rng`
passed in; Faker is seeded once in __main__. Dates are ISO strings and
empty values are None (becomes blank in CSV, null in JSON/SQL).
"""
import json
import re
from datetime import date, datetime, time, timedelta
from random import Random

from . import ids
from .config import Scale

CITIES = ["Hyderabad", "Bengaluru", "Pune", "Chennai", "Mumbai", "Delhi"]

# Department number N -> name (DEPT-00N). The first six matter for routing.
DEPARTMENT_NAMES = [
    "HR Operations", "Employee Relations", "Payroll and Compensation",
    "Benefits Administration", "IT Operations", "Finance", "Engineering",
    "Sales", "Marketing", "Legal and Compliance", "Facilities", "Customer Support",
]
DEPT_HR_OPS, DEPT_ER, DEPT_PAYROLL, DEPT_BENEFITS, DEPT_IT = 1, 2, 3, 4, 5

# Staff roles live in fixed departments; everyone else is spread randomly.
ROLE_DEPT = {
    "hr_partner": DEPT_HR_OPS, "admin": DEPT_HR_OPS,
    "hr_er_specialist": DEPT_ER, "it_ops_partner": DEPT_IT,
}

CATEGORIES = [
    # category_id, name, default_queue, is_sensitive, default_priority
    ("CAT-LEAVE", "Leave", "LEAVE", False, "P3"),
    ("CAT-BENEFITS", "Benefits", "BENEFITS", False, "P3"),
    ("CAT-PAYROLL", "Payroll", "PAYROLL", False, "P2"),
    ("CAT-ONBOARDING", "Onboarding", "GENERAL", False, "P3"),
    ("CAT-ER", "Employee Relations", "ER_CONFIDENTIAL", True, "P1"),
    ("CAT-GENERAL", "General HR", "GENERAL", False, "P3"),
]

# Which department owns policies of each category.
CATEGORY_OWNER_DEPT = {
    "CAT-LEAVE": DEPT_HR_OPS, "CAT-BENEFITS": DEPT_BENEFITS,
    "CAT-PAYROLL": DEPT_PAYROLL, "CAT-ONBOARDING": DEPT_HR_OPS,
    "CAT-ER": DEPT_ER, "CAT-GENERAL": DEPT_HR_OPS,
}

# (title, category_id, audience, {rule: [value in v1, v2, v3, v4]}).
# Version k uses the k-th value, so consecutive versions always differ.
# The first 12 entries cover every category (used by the starter scale).
POLICY_CATALOG = [
    ("Annual Leave Policy", "CAT-LEAVE", "employee",
     {"annual_leave_days": [18, 20, 22, 24], "carry_forward_days": [5, 6, 8, 10]}),
    ("Sick Leave Policy", "CAT-LEAVE", "employee",
     {"sick_leave_days": [8, 10, 12, 14], "medical_certificate_after_days": [4, 3, 3, 2]}),
    ("Maternity Leave Policy", "CAT-LEAVE", "employee",
     {"maternity_leave_weeks": [12, 18, 24, 26], "notice_period_days": [30, 45, 60, 75]}),
    ("Group Health Insurance Policy", "CAT-BENEFITS", "employee",
     {"sum_insured_inr": [300000, 400000, 500000, 700000], "dependents_covered": [2, 3, 4, 5]}),
    ("Provident Fund Contribution Policy", "CAT-BENEFITS", "employee",
     {"vpf_max_percent": [20, 25, 30, 35]}),
    ("Salary Payment Schedule", "CAT-PAYROLL", "employee",
     {"salary_credit_day": [30, 28, 26, 25]}),
    ("Expense Reimbursement Policy", "CAT-PAYROLL", "employee",
     {"claim_window_days": [30, 45, 60, 90], "receipt_required_above_inr": [500, 1000, 1500, 2000]}),
    ("Tax Declaration and TDS Policy", "CAT-PAYROLL", "employee",
     {"proof_submission_window_days": [15, 20, 25, 30]}),
    ("New Joiner Onboarding Checklist", "CAT-ONBOARDING", "all",
     {"joining_formalities_days": [10, 7, 5, 3]}),
    ("IT Equipment and Access Provisioning", "CAT-ONBOARDING", "all",
     {"laptop_delivery_days": [7, 5, 3, 2], "access_setup_hours": [72, 48, 36, 24]}),
    ("Anti-Harassment and POSH Policy", "CAT-ER", "all",
     {"complaint_ack_days": [7, 5, 3, 2], "inquiry_completion_days": [120, 100, 90, 75]}),
    ("Work From Home Policy", "CAT-GENERAL", "employee",
     {"wfh_days_per_week": [1, 2, 3, 4]}),
    # ---- remaining 28 (full scale only) ----
    ("Paternity Leave Policy", "CAT-LEAVE", "employee", {"paternity_leave_days": [5, 10, 12, 15]}),
    ("Leave Encashment Policy", "CAT-LEAVE", "employee", {"max_encashable_days": [10, 12, 15, 18]}),
    ("Compensatory Off Policy", "CAT-LEAVE", "employee", {"comp_off_validity_days": [30, 45, 60, 90]}),
    ("Bereavement Leave Policy", "CAT-LEAVE", "employee", {"bereavement_leave_days": [2, 3, 4, 5]}),
    ("Unpaid Leave and Sabbatical Policy", "CAT-LEAVE", "employee",
     {"sabbatical_max_months": [3, 4, 6, 9], "min_service_years": [5, 4, 3, 2]}),
    ("Public and Optional Holiday Policy", "CAT-LEAVE", "all",
     {"optional_holidays_per_year": [1, 2, 3, 4]}),
    ("Gratuity Policy", "CAT-BENEFITS", "employee", {"gratuity_days_per_year": [15, 16, 18, 20]}),
    ("Wellness Allowance Policy", "CAT-BENEFITS", "employee",
     {"wellness_allowance_inr_per_year": [6000, 9000, 12000, 15000]}),
    ("Meal Card Benefit", "CAT-BENEFITS", "employee", {"meal_card_inr_per_month": [1500, 2000, 2200, 2500]}),
    ("Learning and Development Reimbursement", "CAT-BENEFITS", "employee",
     {"annual_learning_budget_inr": [20000, 30000, 40000, 50000]}),
    ("Relocation Assistance Policy", "CAT-BENEFITS", "employee",
     {"relocation_lumpsum_inr": [25000, 35000, 50000, 60000]}),
    ("Employee Assistance Programme", "CAT-BENEFITS", "all",
     {"counselling_sessions_per_year": [4, 6, 8, 10]}),
    ("Overtime and Shift Allowance Policy", "CAT-PAYROLL", "employee",
     {"night_shift_allowance_inr_per_day": [300, 400, 500, 600]}),
    ("Salary Advance Policy", "CAT-PAYROLL", "employee",
     {"max_advance_percent_of_salary": [25, 50, 60, 75]}),
    ("Bonus and Incentive Payout Policy", "CAT-PAYROLL", "employee",
     {"bonus_payout_after_close_days": [60, 45, 30, 21]}),
    ("Payslip and Form 16 Access", "CAT-PAYROLL", "employee",
     {"payslip_available_by_day": [7, 5, 3, 2]}),
    ("Full and Final Settlement Policy", "CAT-PAYROLL", "employee",
     {"fnf_settlement_days": [60, 50, 45, 30]}),
    ("Background Verification Policy", "CAT-ONBOARDING", "candidate",
     {"bgv_turnaround_days": [21, 15, 10, 7]}),
    ("Probation and Confirmation Policy", "CAT-ONBOARDING", "employee",
     {"probation_review_days": [90, 75, 60, 45]}),
    ("Offer Letter and Documentation Policy", "CAT-ONBOARDING", "candidate",
     {"document_submission_days": [15, 10, 7, 5]}),
    ("Buddy and Induction Programme", "CAT-ONBOARDING", "all", {"induction_days": [1, 2, 3, 5]}),
    ("Grievance Redressal Policy", "CAT-ER", "all", {"grievance_ack_days": [7, 5, 3, 2]}),
    ("Code of Conduct and Disciplinary Policy", "CAT-ER", "all",
     {"disciplinary_notice_days": [3, 5, 7, 10]}),
    ("Whistleblower Protection Policy", "CAT-ER", "all", {"whistleblower_ack_days": [10, 7, 5, 3]}),
    ("Medical Accommodation Policy", "CAT-ER", "all", {"accommodation_review_days": [14, 10, 7, 5]}),
    ("Employee Referral Programme", "CAT-GENERAL", "employee",
     {"referral_bonus_inr": [10000, 15000, 20000, 25000]}),
    ("Dress Code and Office Conduct", "CAT-GENERAL", "all", {"casual_days_per_week": [1, 2, 3, 5]}),
    ("Office Access and Visitor Policy", "CAT-GENERAL", "all",
     {"visitor_pre_registration_hours": [24, 12, 8, 4]}),
]


def make_departments(rng: Random, scale: Scale) -> list[dict]:
    """Departments DEPT-001..; names come from a fixed list, locations are random."""
    assert 6 <= scale.departments <= len(DEPARTMENT_NAMES)
    return [
        {"department_id": ids.department_id(n),
         "name": DEPARTMENT_NAMES[n - 1],
         "location": rng.choice(CITIES)}
        for n in range(1, scale.departments + 1)
    ]


def make_employees(rng: Random, fake, scale: Scale) -> list[dict]:
    """Employees of every role. Faker supplies names; rng supplies everything else."""
    total = scale.employees
    # Fixed number of staff/special roles, the rest are plain employees.
    plan = {
        "admin": 2,
        "candidate": max(3, total // 25),
        "hr_er_specialist": max(3, total // 100),
        "hr_partner": max(6, total // 30),
        "it_ops_partner": max(3, total // 100),
        "manager": max(5, total // 10),
    }
    roles: list[str] = []
    for role in sorted(plan):                 # sorted -> same order every run
        roles.extend([role] * plan[role])
    roles.extend(["employee"] * (total - len(roles)))
    rng.shuffle(roles)

    hire_base = date(2015, 1, 1)
    hire_span = (date(2025, 12, 31) - hire_base).days
    rows: list[dict] = []
    for n, role in enumerate(roles, start=1):
        first, last = fake.first_name(), fake.last_name()
        slug = re.sub(r"[^a-z]", "", first.lower()) + "." + re.sub(r"[^a-z]", "", last.lower())
        dept_no = ROLE_DEPT.get(role) or rng.randint(1, scale.departments)
        if role == "candidate":
            # For candidates hire_date = offer-acceptance date (late 2025).
            hire = date(2025, 11, 1) + timedelta(days=rng.randint(0, 60))
        else:
            hire = hire_base + timedelta(days=rng.randint(0, hire_span))
        if role == "employee":
            emp_type = rng.choices(["full_time", "part_time", "contract", "intern"],
                                   weights=[82, 5, 9, 4])[0]
            status = rng.choices(["active", "on_leave", "exited"], weights=[95, 3, 2])[0]
        else:
            emp_type, status = "full_time", "active"
        rows.append({
            "employee_id": ids.employee_id(n),
            "full_name": f"{first} {last}",
            "email": f"{slug}.{n}@hrdemo.example",   # id inside -> always unique
            "department_id": ids.department_id(dept_no),
            "manager_id": None,
            "role": role,
            "employment_type": emp_type,
            "location": rng.choice(CITIES),
            "hire_date": hire.isoformat(),
            "status": status,
        })

    # Second pass: managers need existing employees to point at.
    managers = [r for r in rows if r["role"] == "manager"]
    for idx, mgr in enumerate(managers):
        # First manager is the top; later ones report to an EARLIER manager (no cycles).
        mgr["manager_id"] = None if idx == 0 else rng.choice(managers[:idx])["employee_id"]
    for r in rows:
        if r["role"] == "manager":
            continue
        same_dept = [m for m in managers if m["department_id"] == r["department_id"]]
        r["manager_id"] = rng.choice(same_dept or managers)["employee_id"]
    return rows


def make_categories() -> list[dict]:
    """The six fixed ticket categories (no randomness)."""
    return [
        {"category_id": cid, "name": name, "default_queue": queue,
         "is_sensitive": sens, "default_priority": prio}
        for cid, name, queue, sens, prio in CATEGORIES
    ]


def make_policy_documents(scale: Scale) -> list[dict]:
    """The first scale.policy_documents entries of the fixed catalog."""
    assert scale.policy_documents <= len(POLICY_CATALOG)
    rows = []
    for n, (title, cat, audience, _rules) in enumerate(POLICY_CATALOG[: scale.policy_documents], start=1):
        rows.append({
            "policy_id": ids.policy_id(n),
            "title": title,
            "category_id": cat,
            "audience": audience,
            "owner_department_id": ids.department_id(CATEGORY_OWNER_DEPT[cat]),
        })
    return rows


def make_policy_versions(rng: Random, docs: list[dict]) -> list[dict]:
    """1-4 versions per policy with non-overlapping dates.

    effective_to is the INCLUSIVE last day (day before the next version starts);
    only the latest version has it empty. Change dates are multiples of 30 days
    after 2025-07-01, so every version lasts at least 30 days.
    """
    change_start = date(2025, 7, 1)
    slots = (date(2026, 9, 30) - change_start).days // 30   # 15 possible change dates
    rows: list[dict] = []
    for n, doc in enumerate(docs, start=1):
        title, _cat, _aud, spec = POLICY_CATALOG[n - 1]
        count = rng.choices([1, 2, 3, 4], weights=[15, 35, 30, 20])[0]
        first_from = date(2024, 1, 1) + timedelta(days=rng.randint(0, 300))
        change_slots = sorted(rng.sample(range(slots), count - 1))
        starts = [first_from] + [change_start + timedelta(days=30 * s) for s in change_slots]
        for v in range(count):
            key_rules = {rule: values[v] for rule, values in spec.items()}
            effective_to = starts[v + 1] - timedelta(days=1) if v + 1 < count else None
            facts = ", ".join(f"{k.replace('_', ' ')} = {val}" for k, val in sorted(key_rules.items()))
            rows.append({
                "version_id": ids.version_id(doc["policy_id"], v + 1),
                "policy_id": doc["policy_id"],
                "version_no": v + 1,
                "effective_from": starts[v].isoformat(),
                "effective_to": effective_to.isoformat() if effective_to else None,
                "key_rules": json.dumps(key_rules, sort_keys=True),
                "summary": f"{title}, version {v + 1}: {facts}.",
            })
    return rows


def make_knowledge_articles(rng: Random, docs: list[dict], versions: list[dict],
                            count: int) -> tuple[list[dict], list[dict]]:
    """Knowledge articles plus the kb_policy_version bridge rows.

    Articles cycle through the policies (so every policy gets coverage). Each
    article links to the policy's latest version and, 30% of the time, to one
    older version too (a deliberately stale link).
    """
    by_policy: dict[str, list[dict]] = {}
    for v in versions:                       # versions are already in id order
        by_policy.setdefault(v["policy_id"], []).append(v)
    title_styles = ["How the {t} works", "FAQ: {t}", "{t}: quick guide",
                    "Understanding the {t}", "{t}: eligibility and rules"]

    articles: list[dict] = []
    bridge: list[dict] = []
    for n in range(1, count + 1):
        doc = docs[(n - 1) % len(docs)]
        vers = by_policy[doc["policy_id"]]
        latest = vers[-1]
        linked = [latest]
        if len(vers) > 1 and rng.random() < 0.3:
            linked.append(rng.choice(vers[:-1]))
        # Published shortly after the latest linked version took effect.
        published = datetime.combine(
            date.fromisoformat(latest["effective_from"]) + timedelta(days=rng.randint(0, 20)),
            time(rng.randint(9, 17), rng.randint(0, 59)),
        )
        kb = ids.kb_id(n)
        articles.append({
            "kb_id": kb,
            "title": rng.choice(title_styles).format(t=doc["title"]),
            "category_id": doc["category_id"],
            "body": f"This article explains the {doc['title']}. {latest['summary']}",
            "status": rng.choices(["published", "archived", "draft"], weights=[85, 10, 5])[0],
            "published_at": published.isoformat(timespec="seconds"),
        })
        for v in sorted(linked, key=lambda x: x["version_id"]):
            bridge.append({"kb_id": kb, "version_id": v["version_id"]})
    return articles, bridge


def build_master_data(rng: Random, fake, scale: Scale) -> dict[str, list[dict]]:
    """Generate all master tables, parents first. Keys are the table names."""
    departments = make_departments(rng, scale)
    employees = make_employees(rng, fake, scale)
    categories = make_categories()
    policies = make_policy_documents(scale)
    versions = make_policy_versions(rng, policies)
    articles, bridge = make_knowledge_articles(rng, policies, versions, scale.knowledge_articles)
    return {
        "department": departments,
        "employee": employees,
        "category": categories,
        "policy_document": policies,
        "policy_version": versions,
        "knowledge_article": articles,
        "kb_policy_version": bridge,
    }