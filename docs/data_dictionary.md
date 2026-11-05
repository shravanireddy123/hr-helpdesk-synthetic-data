# Data Dictionary

Conventions: timestamps naive IST `YYYY-MM-DDTHH:MM:SS`; dates `YYYY-MM-DD`; empty = NULL; PK = primary key, FK = foreign key.

## Lifecycle
Statuses: `new, assigned, pending_employee, in_progress, escalated, resolved, closed`.
Allowed transitions: new->assigned; assigned->pending_employee; assigned->in_progress; pending_employee->in_progress; pending_employee->closed (no_response); in_progress->escalated; escalated->in_progress; in_progress->resolved; resolved->closed.
Current status = latest `ticket_status_event`; never stored on Ticket.

## Enums
- role: employee, candidate, manager, hr_partner, hr_er_specialist, it_ops_partner, admin
- employment_type: full_time, part_time, contract, intern
- employee status: active, on_leave, exited
- queue: GENERAL, BENEFITS, LEAVE, PAYROLL, IT_OPS, ER_CONFIDENTIAL, HR_LEAD
- priority: P1, P2, P3
- message_type: employee_question, clarification_request, employee_reply, hr_answer, resolution_note, follow_up
- sender_role: employee, hr_agent, hr_er_specialist, it_ops_partner, hr_lead, system
- resolution_code: answered, policy_clarified, referred, escalated_resolved, no_response
- article status: published, draft, archived
- audience: all, employee, manager, candidate

## Department (PK `department_id` DEPT-001)
| Field | Type | Req | Allowed / rule | Unique |
|---|---|---|---|---|
| department_id | string | Y | `DEPT-NNN` | Y |
| name | string | Y | non-empty | Y |
| location | string | Y | non-empty | N |

## Employee (PK `employee_id` EMP-000001)
| Field | Type | Req | Allowed / rule | Unique |
|---|---|---|---|---|
| employee_id | string | Y | `EMP-NNNNNN` | Y |
| full_name, email | string | Y | Faker; email unique | email Y |
| department_id | string | Y | FK Department | N |
| manager_id | string | N | FK Employee (self); not own ID | N |
| role | enum | Y | role list | N |
| employment_type | enum | Y | list above | N |
| location | string | Y | non-empty | N |
| hire_date | date | Y | <= reference date (for candidates: offer-acceptance date) | N |
| status | enum | Y | list above | N |

## Category (PK `category_id`)
| Field | Type | Req | Allowed / rule | Unique |
|---|---|---|---|---|
| category_id | string | Y | CAT-LEAVE, CAT-BENEFITS, CAT-PAYROLL, CAT-ONBOARDING, CAT-ER, CAT-GENERAL | Y |
| name | string | Y | non-empty | Y |
| default_queue | enum | Y | queue list | N |
| is_sensitive | bool | Y | true only for CAT-ER | N |
| default_priority | enum | Y | P1-P3 | N |

## PolicyDocument (PK `policy_id` POL-HR-2026-001)
| Field | Type | Req | Allowed / rule | Unique |
|---|---|---|---|---|
| policy_id | string | Y | `POL-HR-2026-NNN` | Y |
| title | string | Y | non-empty | Y |
| category_id | string | Y | FK Category | N |
| audience | enum | Y | audience list | N |
| owner_department_id | string | Y | FK Department | N |

## PolicyVersion (PK `version_id` VER-POL-HR-2026-001-01)
| Field | Type | Req | Allowed / rule | Unique |
|---|---|---|---|---|
| version_id | string | Y | `VER-<policy_id>-NN` | Y |
| policy_id | string | Y | FK PolicyDocument | N |
| version_no | int | Y | 1-4, consecutive per policy | N (unique with policy_id) |
| effective_from | date | Y | < effective_to | N |
| effective_to | date | N | empty only on the latest version; inclusive last day; no overlaps | N |
| key_rules | JSON string | Y | small dict of facts, differs between versions | N |
| summary | string | Y | non-empty | N |

## KnowledgeArticle (PK `kb_id` KB-000001)
| Field | Type | Req | Allowed / rule | Unique |
|---|---|---|---|---|
| kb_id | string | Y | `KB-NNNNNN` | Y |
| title, body | string | Y | non-empty | N |
| category_id | string | Y | FK Category | N |
| status | enum | Y | article status | N |
| published_at | datetime | Y | <= reference date | N |

## kb_policy_version (bridge; PK `kb_id` + `version_id`)
Both FK columns required; pair unique; each article links to at least one version.

## Ticket (PK `ticket_id` TKT-2026-000001)
| Field | Type | Req | Allowed / rule | Unique |
|---|---|---|---|---|
| ticket_id | string | Y | `TKT-2026-NNNNNN` | Y |
| employee_id | string | Y | FK Employee; hired before created_at | N |
| category_id | string | Y | FK Category | N |
| subject | string | Y | non-empty | N |
| created_at | datetime | Y | 2026, mostly weekday working hours | N |
| priority | enum | Y | P1-P3 per rule | N |
| is_sensitive, is_ambiguous, missing_context | bool | Y | true/false | N |

## Message (PK `message_id` MSG-TKT-2026-000001-001)
| Field | Type | Req | Allowed / rule | Unique |
|---|---|---|---|---|
| message_id | string | Y | `MSG-<ticket_id>-NNN`, sequence from 001 with no gaps | Y |
| ticket_id | string | Y | FK Ticket | N |
| sender_id | string | Y | FK Employee | N |
| sender_role | enum | Y | list above | N |
| message_type | enum | Y | list above | N |
| sent_at | datetime | Y | strictly increasing within a ticket | N |
| body | string | Y | non-empty | N |

## message_citation (bridge; PK `message_id` + `version_id`)
| Field | Type | Req | Rule |
|---|---|---|---|
| message_id | string | Y | FK Message; type hr_answer |
| version_id | string | Y | FK PolicyVersion |
| kb_id | string | N | FK KnowledgeArticle |
| snippet | string | Y | text drawn from the version's key_rules |

## Assignment (PK `assignment_id` ASG-TKT-2026-000001-01)
| Field | Type | Req | Rule |
|---|---|---|---|
| assignment_id | string | Y | `ASG-<ticket_id>-NN`, unique |
| ticket_id | string | Y | FK Ticket |
| queue | enum | Y | queue list |
| assignee_id | string | Y | FK Employee; never a manager if ticket is sensitive |
| assigned_at | datetime | Y | >= ticket.created_at |
| reason | string | Y | routing, escalation, etc. |

## SLA (PK `sla_id` SLA-TKT-2026-000001; 1:1 with Ticket)
| Field | Type | Req | Rule |
|---|---|---|---|
| sla_id, ticket_id | string | Y | ticket_id unique, FK Ticket |
| priority | enum | Y | equals ticket priority |
| first_response_due, resolution_due | datetime | Y | created_at + target business minutes (+ paused for resolution) |
| paused_minutes | int | Y | >= 0, business minutes in pending_employee |
| first_responded_at | datetime | Y | first HR message time |
| business_minutes_to_first_response | int | Y | derived |
| first_response_met | bool | Y | derived from timestamps |
| resolution_met | bool | N | derived; empty for no_response tickets |

## Resolution (PK `resolution_id` RES-TKT-2026-000001; 1 per Ticket)
| Field | Type | Req | Rule |
|---|---|---|---|
| resolution_id, ticket_id | string | Y | ticket_id unique, FK Ticket |
| resolved_at | datetime | Y | >= created_at |
| resolution_code | enum | Y | list above |
| cited_version_id | string | N | FK PolicyVersion; empty for no_response |
| business_minutes_to_resolve | int | Y | derived: business minutes from created_at to resolved_at |

## ticket_status_event (PK `event_id` EVT-TKT-2026-000001-01)
| Field | Type | Req | Rule |
|---|---|---|---|
| event_id | string | Y | `EVT-<ticket_id>-NN`, unique |
| ticket_id | string | Y | FK Ticket |
| from_status | enum | N | empty only for the first event |
| to_status | enum | Y | transition must be allowed |
| event_at | datetime | Y | non-decreasing per ticket |
| actor_id | string | Y | FK Employee |

## Ground truth (separate folder; never referenced by data tables)
`ground_truth.csv/json`: issue_id, issue_type, entity, record_id, ticket_id, expected_value, observed_value, rule_reference.
`expected_decisions.csv`: ticket_id, expected_queue, expected_version_id, needs_clarification.