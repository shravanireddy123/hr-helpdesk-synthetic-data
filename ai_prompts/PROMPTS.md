# AI Prompt History

## Build Log by Stage (2026-11-04 to 2026-11-05)

Primary AI tool: Claude (claude.ai). Additional assistance: ChatGPT.

**Disclosure:** This file records summaries of the prompts and assistance used during development. These are not word-for-word transcripts of every conversation. Original prompt text is included only where available.

### Claude Prompts

1. **Setup and skeleton:** Follow the build guide, create the repository, virtual environment and starter files. Fixed an unsaved-paste ImportError and a GitHub 403 caused by the wrong saved account.

2. **Documentation:** Draft `data_dictionary.md` and `assumptions.md` based on my table design.

3. **Business calendar:** Create the business calendar module and pytest tests. Verify the calculation that Friday 17:00 + 120 business minutes = Monday 10:30.

4. **Master data:** Create the master data module and its tests.

5. **Tickets and routing:** Create tickets, routing rules and status events, along with tests.

6. **Messages and citations:** Create messages and citations. The first draft was rejected as flawed and rewritten to use one counter per ticket.

7. **SLA and resolution:** Create derived SLA and resolution tables, along with escalation rules.

8. **Anomalies:** Implement edge-case injection, ground truth and the answer key.

9. **Metrics and export:** Implement metrics and exports in CSV, JSON and SQL formats, including a manifest with SHA-256 checksums.

10. **P1 SLA tuning:** Explain what "tune P1 delays" means and provide the complete modified `messages.py` file.

11. **Validation and reproducibility:** Create validation checks, a validation summary and a reproducibility script.

12. **Final documentation:** Prepare the README, AI usage notes and final project checks.

### ChatGPT Assistance Log (2026-11-04 to 2026-11-05)

Additional AI tool: ChatGPT (GPT-6).

**Disclosure:** ChatGPT was used alongside Claude for explanations, troubleshooting, Git guidance and project review. The entries below summarize the assistance provided; they are not word-for-word prompt transcripts.

1. **Project understanding:** Explain the HR Helpdesk Synthetic Data Generator challenge, its requirements, deliverables and expected output.

2. **Git configuration:** Explain Git username and email configuration and help resolve commit author identity issues.

3. **GitHub push troubleshooting:** Help understand and resolve GitHub 403 errors, push rejections and remote synchronization problems.

4. **Project execution:** Explain terminal commands, Python virtual environment usage and how to run project commands in VS Code.

5. **Testing:** Help interpret pytest output, identify missing files and understand test failures.

6. **Dataset validation:** Explain validation results, structural checks, row counts, foreign keys and ground-truth verification.

7. **Reproducibility:** Help understand checksum comparisons and verify that starter and full datasets are generated identically across repeated runs.

8. **P1 SLA tuning:** Explain what tuning P1 agent delays means and help understand the required changes to `messages.py`.

9. **Documentation:** Explain how to prepare the README, `AI_USAGE.md` and `PROMPTS.md` for the final submission.

10. **Git author correction:** Guide the process of correcting the old commit author information while preserving the project history.

11. **Git recovery:** Help inspect Git reflog, unreachable commits and recovery branches to ensure no project commits were lost.

12. **Final GitHub verification:** Guide the safe history update using `git push --force-with-lease` and verify that the local and remote branches are synchronized.

13. **Submission review:** Help interpret reviewer feedback and identify the missing ChatGPT prompt documentation requirement.

### What I Checked Myself

- Ran pytest and reviewed the test results.
- Generated both starter and full datasets.
- Compared generated row counts with the expected counts.
- Reviewed validation results and ground-truth checks.
- Checked reproducibility results.
- Followed the suggested Git commands and reviewed terminal outputs.
- Verified the GitHub commit history.
- Checked that the working tree was clean and the project was pushed successfully.