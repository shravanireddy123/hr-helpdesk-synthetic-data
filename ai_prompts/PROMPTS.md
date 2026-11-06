PROMPTS.md
Claude
Primary AI tool: Claude (claude.ai).

Disclosure: The chat tool does not provide a per-prompt export, so
the entries below are reconstructed summaries of what I asked at each
stage, not the exact original wording. 
1. Can you follow the project build guide and help me create the
   repository, Python virtual environment and required starter files?
   Please guide me step by step.
2. Can you help me create data_dictionary.md and assumptions.md
   based on my project tables? Please explain what information should
   be included.
3. Can you help me implement a business calendar module in Python and
   write pytest test cases? Please verify that adding 120 business
   minutes to Friday at 5 PM gives Monday at 10:30 AM.
4. Can you create the master data generation module and its test cases?
   Please make sure the generated data is realistic and consistent.
5. Can you help me generate HR tickets with routing rules and status
   events? Please also create test cases to verify the ticket workflow.
6. Can you implement ticket messages and policy citations? Please make
   sure message IDs and counters are handled correctly for each ticket.
7. What does tuning P1 agent delays mean? Can you explain it and
   provide the complete updated messages.py file?
8. Can you help me implement validation checks and generate a
   validation summary? I also need a script to check whether repeated
   runs produce identical output.
9. Can you help me prepare the README, AI usage documentation and final
   project verification steps before submission.
At each stage, I ran pytest, tested both dataset sizes, checked the
generated counts and validation results, and committed my changes after
the tests passed.
ChatGPT
Additional AI tool: ChatGPT (GPT-6).

Disclosure: The following prompts are reconstructed in a natural
question-and-answer style based on the project work and available
conversation history. They are not exact word-for-word transcripts of
the original conversations.
1. Can you help me fix the issue where I am unable to open the project
   file in VS Code?
2. How can I check and change my Git username and email? I am facing an
   issue with my commit author name.
3. I am getting errors while pushing my project to GitHub. Can you
   explain why this happens and guide me to fix it?
4. How can I run all the pytest test cases? Please explain the output
   and help me understand any failures.
5. Can you explain the validation summary? What do structural checks,
   foreign keys, row counts and ground-truth verification mean?
6. How can I check whether the starter and full datasets are generated
   identically every time? Please explain the checksum comparison.
7. What does tuning P1 agent delays mean? Can you explain why it is
   needed and help me understand the changes in messages.py?
8. Can you guide me in preparing README.md, AI_USAGE.md and
   PROMPTS.md for my final project submission?
9. I have an issue with the author name in my previous Git commits. Can
   you guide me on how to correct it without losing my project changes?
10. How can I check Git reflog and recover missing commits? Please
    explain the steps carefully.
11. Can you guide me through checking my project folders, generated
    datasets, pytest results and validation summaries before submission?
12. How can I confirm that all my changes are pushed to GitHub and that
    my working tree is clean?

I also ran pytest and reviewed the results, generated both starter and
full datasets, compared row counts with expected counts, reviewed
validation and ground-truth checks, checked reproducibility, followed
Git commands, reviewed commit history, and confirmed that the working
tree was clean and the project was pushed successfully.