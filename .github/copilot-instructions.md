# gstack Skill Loader

This repository uses gstack skills from:

- /Users/pavansai/gstack/.agents/skills/gstack

When the user invokes a slash command such as /review, /qa, /ship, /plan-ceo-review, or /investigate:

1. Read ~/gstack/.agents/skills/gstack/<skill-name>/SKILL.md first.
2. Execute that SKILL.md workflow fully.
3. Do not partially summarize or skip required steps.

## Workflow Order

Think -> Plan -> Build -> Review -> Test -> Ship -> Reflect

## Project Context

Project-specific coding conventions and commands live in [AGENTS.md](../AGENTS.md). Prefer that file for day-to-day implementation guidance.