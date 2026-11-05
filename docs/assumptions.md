# Assumptions and Design Decisions

## Scope and scale
- 14 tables: the 11 required entities + `kb_policy_version`, `message_citation`, `ticket_status_event`.
- Two scales from the same code: starter (500 tickets) and full (5,000 tickets, 150 KB articles, 20,000 messages).
- "150 policy articles" is read as 150 KnowledgeArticles built on 40 PolicyDocuments with 1-4 versions each, so superseded versions exist.
- All data is synthetic (Faker `en_IN` + seeded `random.Random`). No real people or external datasets.

## Time
- Fixed reference date 2026-10-31 (never the system clock). Seed 20261022.
- All timestamps are naive IST, ISO 8601 `YYYY-MM-DDTHH:MM:SS`. Dates are `YYYY-MM-DD`.
- Tickets are created between 2026-01-05 and 2026-10-15 so most can complete before the reference date; any ticket still unresolved at the reference date stays open.
- Business hours: Mon-Fri 09:30-18:00 IST (8.5 h/day), minus a fixed 2026 holiday list defined in `business_calendar.py` (fixed-date holidays: 26 Jan, 1 May, 15 Aug, 2 Oct, 25 Dec, plus moveable festivals to verify against an official calendar).
- The SLA clock pauses while status is `pending_employee`.

## Roles and queues
- Employee roles: employee, candidate, manager, hr_partner, hr_er_specialist, it_ops_partner, admin.
- Queues: GENERAL, BENEFITS, LEAVE, PAYROLL, IT_OPS, ER_CONFIDENTIAL, HR_LEAD.
- Managers are never assigned to sensitive tickets.

## Business rules
- **Sensitivity:** category EMPLOYEE_RELATIONS, or subject mentions harassment, grievance, misconduct or medical -> `is_sensitive = true`.
- **Routing:** sensitive -> ER_CONFIDENTIAL (assignee role hr_er_specialist); onboarding access/laptop -> IT_OPS; benefits/leave/payroll -> own queue; else GENERAL.
- **Priority:** sensitive P1; payroll P2; everything else P3.
- **SLA (business hours):** P1 4h first response / 16h resolution; P2 8h / 24h; P3 16h / 40h.
- **Clarification:** ambiguous or missing-context tickets get a `clarification_request` first; ~85% of employees reply; the rest close as `no_response` after 5 business days.
- **Citation:** the answer cites the PolicyVersion with `effective_from <= ticket.created_at` and (`effective_to` empty or later), for a policy whose audience matches the employee.
- **Escalation:** first-response SLA breached, or P1 untouched for 2 business hours -> `escalated` event + new Assignment to an HR lead.
- **Supported claims:** answer text may only state facts present in the cited version's `key_rules`.
- Ticket mix: leave 30%, benefits 22%, payroll 22%, onboarding 16%, employee relations 6%, general 4%; ~12% ambiguous, ~8% missing context.

## Derived values (never random)
Current ticket status (latest event), SLA due times, paused minutes, breach flags, resolution times, all metrics.

## Edge cases
About 2% of eligible tickets per type are corrupted AFTER valid data is built: OBSOLETE_CITATION, SENSITIVE_MISROUTED, SLA_BUSINESS_HOURS_ERROR, UNSUPPORTED_CLAIM. Labels live only in `ground_truth/`; no data table has an issue_type or label column.

## Simplifications (limitations)
- English-only, template-based message text; no real NLP.
- One assignee at a time per ticket; reassignment history kept in Assignment.
- Holiday list is a single fixed 2026 list.
Candidates’ hire_date is their offer-acceptance date (Nov to Dec 2025). The ticket step must skip exited employees as ticket raisers.
“HR lead” means an hr_partner employee.
## Added during the build
- Candidates' `hire_date` is their offer-acceptance date; `exited` employees never raise tickets. "HR lead" means an `hr_partner`.
- Each ticket starts with two events: (none)->new by the employee, and new->assigned by an admin account acting as the routing system. Ambiguous and missing-context are mutually exclusive.
- About 10% of tickets are sensitive: the ER category (6%) plus keyword matches such as "medical leave".
- Resolution rows are derived from the final events. Follow-up messages are spread over answered tickets so message totals match the scale exactly.
- Escalation is recorded when a ticket first enters `in_progress`. P1 trigger: no HR message within 2 business hours. P2/P3 trigger: first-response SLA breach. The escalation Assignment goes to the `HR_LEAD` queue, to a different `hr_partner`. Tickets closed as `no_response` never escalate.
- The SLA pause starts at the clarification request (which is also the first response), so first-response due times are never adjusted. `resolution_met` is empty for `no_response` tickets.
- Resolution code priority: no_response, escalated_resolved, referred (sensitive), policy_clarified (ambiguous or missing context), answered.
- P1 agent delay ranges are cut to a quarter, so P1 first-response attainment is 100%. SLA attainment is high by design; P2 first response is the main source of breaches.
- Anomalies are injected after all valid data exists: about 2% of eligible tickets per type (minimum 3), at most one per ticket. The eligible pool differs by type, so counts differ (OBSOLETE_CITATION is 82 at full scale).
- Export conventions: CSV uses true/false and empty for NULL; JSON uses booleans and null; SQL stores booleans as 0/1. Files are sorted by primary key, UTF-8, `\n` line endings. The manifest records the command without `--out`.
- Validation reads the exported CSVs. Structural checks must pass. Rule checks must fail exactly on the labelled ground-truth records. `validation_summary.md` is written into each output folder and is not listed in the manifest.