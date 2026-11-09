# Prompts used in the evaluation

Every run was a fresh Claude subagent. `<folder>` stands for the run's own working folder, and `<skill path>` for the skill's `SKILL.md`.

## Phase 1: questions

```
You are one run in a comparison of travel-planning skills. Follow only the skill below. Do not use or read any other road trip or travel skill.

Skill: read <skill path> first and follow its workflow. Its scripts and references are in that directory.

The traveller's first message, exactly:
"<first message>"
Today is 9 Nov 2026.

PHASE 1 (now): you cannot talk to the traveller or use AskUserQuestion. Write the questions you would ask before planning into questions.md, exactly as you would present them (if your workflow uses multiple-choice questions, write the questions with their options). Don't plan yet. Then stop and reply "questions written". You will later receive the traveller's answers and do phase 2.

Ground rules for the whole task:
- Don't book, contact or submit anything.
- Write only inside <folder>
- Don't read anything else in the scratchpad folder, the user's Desktop trip folder, or any memory files. This is a new, unrelated trip.
- If a tool refuses to write a file, don't work around it with another tool; tell me in your reply instead.
```

The no-skill run instead began: "You are one run in a comparison of travel-planning approaches. Do not read or use any skill (nothing under ~/.claude/skills or ~/.claude/skill-backups); work from your own judgement and tools."

First messages:
- **Round 1:** "Help me plan a self-drive trip around New Zealand's South Island in early March, two of us, driving from Christchurch to Queenstown."
- **Round 2:** "Can you plan a road trip from Melbourne to Adelaide along the Great Ocean Road over Christmas? There are three of us."

## Phase 2: plan

```
PHASE 2: the traveller answered your questions. Read their answers in <folder>/../answers.md (you may read that one file; still nothing else). Questions they didn't answer: state an assumption and carry on; you can't ask more.

Now plan the trip, keep following your skill, and produce the deliverable they asked for: <deliverable>. A grader will read only your questions.md and <report file>, so it must stand on its own. Don't book or contact anything. If a tool refuses to write a file, don't work around it; tell me in your reply and include the full report text there. When finished, reply in one or two sentences saying the report is written and whether anything blocked you.
```

Deliverables:
- **Round 1:** "a detailed PDF in English. Save it as report.pdf in your folder." travel-agent was also told: "If a tool your skill names for PDFs isn't installed, make the PDF another way."
- **Round 2:** "a short English Markdown plan saved as report.md in your folder." travel-agent was also told: "Their format request overrides any PDF step in your skill."

## Grading

One grader per round, a fresh subagent that saw only `rubric.md`, `answers.md` and the anonymised submissions:

```
You are an independent grader comparing seven anonymous submissions (<letters>) for the same road-trip request. You don't know how any of them were produced, and it shouldn't matter. Don't try to work it out.

Read only rubric.md, answers.md and blind/questions-<L>.md and blind/report-<L>.* in the folder.

How to grade:
- Apply the rubric exactly. Score each of the 16 items 1, 0.5 or 0 for each submission, with a short quote as evidence. Items 1–7 use only the questions file; items 8–16 only the report.
- Length isn't merit.
- For item 10, actually check at least three days of each plan against distance, driving time and sunset, and show brief arithmetic.
- Be strict and consistent: grade one item across all seven before moving to the next.
- Then, unscored, list per submission (a) statements that look factually wrong, unsupported or self-contradictory, and (b) notable strengths outside the rubric.
- You may use web search only to settle a factual disagreement between submissions that would change the traveller's plan.

Return: a score table with subtotals, evidence per item, the item 10 arithmetic, the unscored lists, fact disagreements, and three sentences on which submission you would actually hand to this traveller.
```

Each round's grader prompt also gave the region's realistic road speeds and sunset times, and named the round's traps to search for (boats and beaches in round 1; 25–26 Dec openings, flights, long walks and unsealed roads in round 2).
