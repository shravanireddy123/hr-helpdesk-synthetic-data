# HR Helpdesk Synthetic Data Generator

**Submission deadline:** Friday, 6 November 2026, 5:18:42 PM IST (target finish: 11:18 AM IST)

A Python command-line program that generates a believable, fully synthetic history of an HR helpdesk: employees raise tickets, HR answers from versioned policies, sensitive cases go to a confidential queue, and every ticket has business-hours SLAs. It validates its own output, injects four labelled edge cases, exports CSV/JSON/SQL, and proves that two runs with the same seed are identical.

## 1. Problem understanding
Employees raise HR questions as tickets. HR answers using official policies, and policies change over time, so a good answer cites the version in force on the ticket date. Sensitive cases (harassment, grievance, medical) must go to a confidential queue. Every ticket has SLA deadlines measured in business hours, and vague questions get a clarification request first. The program builds a dataset of this workflow so an HR assistant could later be tested against it.

## 2. Quick start (Windows PowerShell)
```powershell
git clone https://github.com/shravanireddy123/hr-helpdesk-synthetic-data.git
cd hr-helpdesk-synthetic-data
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m hrgen --scale starter
python -m hrgen --scale full
python scripts\check_reproducibility.py
python -m pytest -q
```
Python 3.12. Each run writes to `output/<scale>/`, validates what it wrote, and exits with an error if any check fails.

## 3. Output
Per scale folder (`output/starter`, `output/full`): one CSV and one JSON per table, `seed.sql`, `metrics.json`, `manifest.json` (row counts and SHA-256 per file), `validation_summary.md`, and `ground_truth/` (answer key, kept separate).

| Table | Starter | Full |
|---|---|---|
| department | 8 | 12 |
| employee | 200 | 1,200 |
| category | 6 | 6 |
| policy_document | 12 | 40 |
| policy_version | 33 | 105 |
| knowledge_article | 30 | 150 |
| kb_policy_version | 41 | 199 |
| ticket | 500 | 5,000 |
| assignment | 519 | 5,125 |
| ticket_status_event | 2,590 | 25,943 |
| message | 2,000 | 20,000 |
| message_citation | 481 | 4,854 |
| sla | 500 | 5,000 |
| resolution | 500 | 5,000 |
| ground_truth | 30 | 283 |

## 4. Data model
14 tables: the 11 required entities plus `kb_policy_version` and `message_citation` (bridge tables for many-to-many links) and `ticket_status_event` (append-only history). Full field list: [docs/data_dictionary.md](docs/data_dictionary.md). Master tables are generated first, then tickets, messages, SLAs and anomalies.

## 5. Business rules (all in code)
- **Sensitivity:** Employee Relations category, or subject mentions harassment, grievance, misconduct or medical.
- **Routing:** sensitive goes to ER_CONFIDENTIAL (ER specialist, never a manager); onboarding laptop/access goes to IT_OPS; benefits, leave and payroll have their own queues; else GENERAL.
- **Priority:** sensitive P1, payroll P2, others P3.
- **SLA (business hours Mon-Fri 09:30-18:00 IST, minus holidays):** P1 4h/16h, P2 8h/24h, P3 16h/40h (first response / resolution). The clock pauses while waiting for the employee.
- **Clarification:** ambiguous or missing-context tickets get a clarification request first; about 85% reply, the rest close as `no_response`.
- **Citation:** the answer cites the policy version in force on the ticket date, for an allowed audience.
- **Escalation:** P1 untouched for 2 business hours, or first-response breach, creates an `escalated` event and an HR_LEAD assignment.
- **Supported claims:** answers state only facts from the cited version's `key_rules`.

## 6. Edge cases and ground truth
After all valid data exists, about 2% of eligible tickets per type (minimum 3, one anomaly per ticket) are corrupted and labelled in `output/<scale>/ground_truth/`:

| Issue type | Injection | Starter | Full |
|---|---|---|---|
| OBSOLETE_CITATION | Answer rewritten on an older version of the same policy | 8 | 82 |
| SENSITIVE_MISROUTED | First assignment of a sensitive ticket put in GENERAL | 3 | 10 |
| SLA_BUSINESS_HOURS_ERROR | `resolution_due` computed with plain calendar time | 10 | 98 |
| UNSUPPORTED_CLAIM | One invented sentence appended to an answer | 9 | 93 |

No data table contains a label column, and `seed.sql` excludes ground truth. `expected_decisions.csv` is the answer key per ticket, computed from the clean data.

## 7. Validation and verification
`validation_summary.md` (in each output folder) lists 30 checks: 23 structural (keys, foreign keys, enums, formats, date order, SLA arithmetic, lifecycle, duplicates, manifest checksums, separation) and 7 rule checks. A rule check passes only when the records violating the rule are exactly the records labelled in ground truth.

| Acceptance criterion | How it is proven |
|---|---|
| Answers cite effective sources | Rule check re-finds the effective version for every answer; violations equal the OBSOLETE_CITATION rows |
| Sensitive cases route correctly | Rule check: every sensitive first assignment is ER_CONFIDENTIAL except the SENSITIVE_MISROUTED rows |
| Ambiguity triggers clarification | Rule check: zero tickets lack a clarification request before the answer |
| SLA metrics are reproducible | SLA fields recomputed from events and messages match stored values (except the labelled SLA errors); two runs give identical checksums |

Tests: 107 pytest tests (calendar, master data, tickets, messages, SLA, anomalies, export/metrics, validation), including tests that deliberately break data and confirm validation catches it.

**Manual spot check** (five tickets traced across tickets, messages, assignments, events and ground truth in `output/starter`):
- Normal ticket `TKT-2026-000001` (Leave, P3): routed to the LEAVE queue; messages run employee_question, hr_answer, follow_up, resolution_note; events run new, assigned, in_progress, resolved, closed; no ground-truth row.
- Ambiguous ticket `TKT-2026-000003` (Payroll, P2): the HR clarification_request is the first reply; the employee never answered, so events end pending_employee then closed (the no_response path), with no answer or citation.
- Sensitive ticket `TKT-2026-000012` (P1): category is Leave but it is sensitive (keyword rule), so its first assignment is ER_CONFIDENTIAL; it was also escalated to HR_LEAD.
- Escalated ticket `TKT-2026-000069` (Payroll, P2): events run in_progress, escalated, in_progress; a second assignment in HR_LEAD was created; the ticket was then resolved and closed.
- Anomaly ticket `TKT-2026-000128` (Employee Relations, P1): ground truth labels it SENSITIVE_MISROUTED (expected ER_CONFIDENTIAL, observed GENERAL), and its only assignment is indeed GENERAL.

## 8. Reproducibility
Seed `20261022`. `python scripts\check_reproducibility.py` runs each scale twice in separate processes and compares the SHA-256 of every file. Result: **IDENTICAL** ([reproducibility_report.md](reproducibility_report.md)). Determinism rules: one seeded `random.Random`, seeded Faker, no `datetime.now()` (fixed reference date 2026-10-31), sorted output.

## 9. Metrics (full scale, from `metrics.json`)
First-response SLA met: P1 100% / P2 92.04% / P3 100%. Resolution SLA met: 100% at all priorities. Business hours to resolve: median 11.72, p90 23.1. Clarification rate 19.7%, reply rate 85.18%, escalation rate 2.5%. Citation accuracy 98.31% and sensitive-routing accuracy 98.07%, both below 100% only because of the labelled anomalies.

## 10. Key decisions and trade-offs
- **CLI, not a web app:** the brief rewards correct data, rules and documentation.
- **150 articles on 40 policies with 1-4 versions each:** so superseded versions exist and "the version in force" is meaningful.
- **SLA clock pauses while waiting for the employee:** the delay is not HR's fault.
- **Status is derived from events, never stored:** history is append-only.
- **Anomalies injected last, into copies:** valid data cannot be affected by the corruption.
- **P1 agent delays cut to a quarter:** the first version gave 15.56% P1 attainment at starter scale, which was unrealistic for urgent cases.

## 11. Assumptions
See [docs/assumptions.md](docs/assumptions.md).

## 12. Limitations and next steps
- Message text is template-based English; no real language variety or NLP.
- SLA attainment is high by design (100% for P1 and for resolution); only P2 first response produces breaches. A noisier delay model would be more realistic.
- About 10% of tickets are sensitive, above the 6% Employee Relations share, because the keyword rule also catches "medical leave" tickets.
- Clarification reply rate is 78.89% at starter scale (small sample) and 85.18% at full scale.
- One fixed holiday list; no time zones other than IST.
- Next steps: more varied delay and no-reply models, multi-language messages, an HTML metrics summary.

## 13. Data provenance
All data is synthetic, generated with Faker (MIT) and Python's seeded `random`. No external datasets. See [docs/source_manifest.md](docs/source_manifest.md).

## 14. AI usage
See [ai_prompts/](ai_prompts/): every prompt sent, plus `AI_USAGE.md`.