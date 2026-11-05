PROMPTS_ADD = """
## Build log by stage (2026-11-04 to 2026-11-05)

Primary AI tool: Claude (claude.ai). Additional assistance: ChatGPT.

Disclosure: The chat tool does not provide a per-prompt export, so the prompts below are recorded as short summaries of what was asked at each stage, not word-for-word text. The first entry in this file holds the original planning prompt.

1. Setup and skeleton: follow the build guide, create the repo, venv and starter files. Fixed an unsaved-paste ImportError and a GitHub 403 caused by the wrong saved account.

2. Docs: draft data_dictionary.md and assumptions.md from my table design.

3. Business calendar and pytest tests (Friday 17:00 + 120 min = Monday 10:30).

4. Master data module and tests.

5. Tickets, routing rules and status events, with tests.

6. Messages and citations (first draft rejected as flawed; rewritten with one counter per ticket).

7. Derived SLA and resolution tables plus escalation rules.

8. Edge-case injection, ground truth and answer key.

9. Metrics and export (CSV, JSON, SQL seed, manifest with SHA-256).

10. Asked what "tune P1 delays" meant, then asked for the full modified messages.py.

11. Validation, validation summary and reproducibility script.

12. README, AI usage notes and final checks (this finalisation script).

Additional ChatGPT assistance: explanations, troubleshooting guidance, and review of final validation and reproducibility results.

What I checked myself each stage: ran pytest, ran both scales, compared counts with expectations, and committed only after tests passed.
"""

