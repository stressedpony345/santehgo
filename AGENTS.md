# Santehgo agent workflow

## Mission

Move the project forward safely with minimal token use. Treat user statements as important evidence, not as infallible facts. Correct mistakes respectfully and continue with the safest reasonable interpretation whenever the intended outcome is clear.

## Decision discipline

- Verify claims against the repository, tests, runtime output, or authoritative documentation before relying on them.
- Distinguish facts, assumptions, and recommendations.
- If a user assumption conflicts with evidence, state the conflict briefly, explain the evidence, and use the evidence-based path.
- Do not agree merely to be agreeable. Challenge choices that create security, data-loss, deployment, or maintenance risk.
- Ask a question only when the missing answer would materially change the result or authorize a significant external effect. Otherwise make a reversible assumption, state it when material, and proceed.
- When several solutions work, prefer the smallest reversible change that matches the existing architecture.

## Token-efficient orchestration

- Do not spawn subagents for simple, sequential, or tightly coupled work.
- Delegate only when independent work can run in parallel or when noisy investigation would pollute the main context.
- Prefer one narrowly scoped subagent. Use two or three only when their responsibilities are genuinely independent.
- Never assign the same broad repository scan to multiple agents.
- Give each subagent exact scope, required evidence, output format, and stop condition.
- Ask subagents for concise findings and file references, not raw logs or long narratives.
- Reuse existing findings. Do not repeat exploration already completed by the main agent or another subagent.
- The main agent owns decisions, integration, edits, and the final response.
- Use one writer for overlapping files. Other agents should review read-only to avoid edit conflicts.

## When to delegate

Use `project-explorer` for focused codebase mapping when the relevant files or data flow are unknown.

Use `critical-reviewer` after a plan or implementation when assumptions, security, correctness, or operational risk need an independent challenge.

Use `test-reviewer` when behavior changes, regressions are plausible, or the correct verification scope is unclear.

For small fixes, the main agent should inspect, edit, and test without delegation.

## Project facts and verification

- Stack: Django 6.1, Python 3.13, PostgreSQL, Docker Compose, Nginx, and Playwright.
- Before changing models, inspect existing migrations and check migration drift.
- After Python or Django changes, run:
  - `python manage.py check`
  - `python manage.py makemigrations --check --dry-run`
  - `python manage.py test`
- After container or deployment changes, build the production Docker image.
- After UI changes, run the narrowest relevant Playwright checks; use the full browser suite for cross-browser or shared-layout changes.
- Never expose secrets, production credentials, private keys, or personal data.
- Do not bypass CI or deploy an untested revision.
- Keep production deployment gated on successful CI.

## Reporting

- Lead with the outcome.
- Report only material assumptions, changed files, verification performed, and remaining risks.
- Summarize command failures; do not paste large logs unless requested.
- If evidence is incomplete, say what is known, what is uncertain, and what safe next step was taken.
