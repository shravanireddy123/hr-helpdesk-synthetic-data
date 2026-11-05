# AI usage

Primary AI tool: Claude (claude.ai).

Claude was used for planning, design, drafting Python modules and tests, debugging and documentation. The prompt log is in `PROMPTS.md`; it contains summaries of the prompts, not word-for-word transcripts.

## Where AI accelerated my work
- Drafting `data_dictionary.md` and `assumptions.md` from my table design.
- Drafting the modules: business calendar, master data, tickets, messages, SLA, anomalies, export and validation.
- Creating pytest tests for each module.
- Explaining errors: ImportError, GitHub 403, non-fast-forward rejection, a temporary GitHub server error.

## Where I relied heavily on AI
- The business-hours calendar algorithm and the per-ticket message timeline.
- The validation framework, including the rule that rule checks must fail exactly on the ground-truth records.
- The README draft, which I filled with my own run results and spot check.

## What I personally reviewed, changed or validated
- Ran the full test suite (final result: 107 passed).
- Generated both starter and full datasets and compared counts with expectations.
- Found that some pasted files were missing (`messages.py`, `test_tickets.py`) through pytest collection counts, and recreated them.
- Checked P1 first-response attainment (15.56%), decided to shorten P1 agent delays, and re-ran everything.
- Checked the sensitive-ticket share (about 10% vs the 6% category mix) and documented the reason.
- Ran the reproducibility script (IDENTICAL) and validation (PASS at both scales).
- Traced five tickets by hand across the tables (see README section 7).