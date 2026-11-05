# Validation summary

- Scale: `full`  |  seed: `20261022`
- Overall: **PASS** (30 checks, 0 failed)

## Structural checks (must all pass)

| # | Check | Result | Detail |
|---|---|---|---|
| 1 | Manifest: every listed file exists and its SHA-256 matches | PASS | 34 files match their checksums |
| 2 | Manifest: row counts match the CSV files | PASS | all row counts match |
| 3 | Schema: columns match the data dictionary | PASS | 16 tables have the expected columns |
| 4 | Primary keys are unique and non-empty | PASS | 77917 rows in 16 tables |
| 5 | Unique columns (email, one SLA and one resolution per ticket) | PASS | email, sla.ticket_id and resolution.ticket_id are unique |
| 6 | No duplicate rows or duplicate tickets | PASS | no duplicates found |
| 7 | Formats: dates, timestamps and integers parse | PASS | all date, timestamp and integer columns parse |
| 8 | Enums and booleans only use allowed values | PASS | 16 enum columns and 7 boolean columns are valid |
| 9 | Completeness: every ticket has SLA, resolution, messages, events, assignment | PASS | all 5000 tickets are fully covered |
| 10 | Foreign keys exist (data and ground truth) | PASS | 22 foreign-key columns all resolve |
| 11 | Row counts match the 'full' scale | PASS | 5000 tickets, 20000 messages, 150 articles |
| 12 | Policy versions: no overlaps, one current version per policy | PASS | 40 policies have consecutive, non-overlapping versions |
| 13 | Ids: message, event and assignment sequences are 1..n per ticket (no duplicate ticket/sequence pairs) | PASS | all sequences are gap-free |
| 14 | Date order: message and event times increase within a ticket | PASS | all timelines are in order |
| 15 | Date order: created < first response <= resolved; hired before ticket | PASS | all tickets are consistent |
| 16 | Arithmetic: SLA fields, pauses, flags and resolution times recompute | PASS | every derived SLA/resolution value recomputes (resolution_due is a rule check) |
| 17 | Lifecycle: only allowed transitions; every closed ticket has a resolution | PASS | 25943 events follow the lifecycle |
| 18 | Resolution rows match the final status events | PASS | resolved_at, code and citation agree with the events |
| 19 | Escalations: each has one HR_LEAD assignment at the same time | PASS | escalation events and assignments agree |
| 20 | Citations: one per hr_answer, valid snippet and knowledge-article link | PASS | 4854 answers each have one citation |
| 21 | Ground-truth rows describe what is really in the data | PASS | 283 labelled anomalies verified against the tables |
| 22 | Answer key (expected_decisions) is correct and covers every ticket | PASS | 5000 expected decisions verified |
| 23 | Ground-truth separation: no labels in data tables or the SQL seed | PASS | labels live only in ground_truth/ |

## Rule checks (must fail exactly on the labelled ground-truth records)

A rule check PASSES when the records that break the rule are exactly the records labelled in `ground_truth/ground_truth.csv`. A rule with no anomaly type must have zero violations.

| Rule | Violations found | Labelled in ground truth | Result |
|---|---|---|---|
| Rule: answer cites the policy version in force on the ticket date | 82 | 82 | PASS |
| Rule: sensitive tickets are first routed to ER_CONFIDENTIAL | 10 | 10 | PASS |
| Rule: SLA due times use business hours | 98 | 98 | PASS |
| Rule: answers state only facts from the cited version's key_rules | 93 | 93 | PASS |
| Rule: ambiguous or missing-context tickets get a clarification first | 0 | 0 | PASS |
| Rule: managers are never assigned to sensitive tickets | 0 | 0 | PASS |
| Rule: citations respect the policy audience | 0 | 0 | PASS |
