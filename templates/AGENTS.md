# Project Instructions

## Start Here

First read:

1. `PROJECT.md`

Then read only what the task requires:

- Architecture → `docs/ARCHITECTURE.md`
- Historical decisions → `docs/DECISIONS.md`
- Active work → `plans/<task>/`

Do not load unrelated documentation by default.

## Project Memory

Conversation history is not project memory.

Update `PROJECT.md` when confirmed user intent, priorities, constraints, or rejected directions change.

Update `docs/ARCHITECTURE.md` when durable knowledge about how the system works changes.

Update `docs/DECISIONS.md` when an important decision is made that future agents may otherwise revisit.

For substantial work, maintain:

- `task_plan.md`
- `findings.md`
- `progress.md`

## Development

Use the repository's existing development, testing, review, and validation mechanisms.

Before extending capabilities, check existing tools, plugins, official capabilities, and relevant community implementations in proportion to the task.

Prefer direct use, configuration, composition, or small patches; justify minimal adapters with verified gaps.

Do not introduce process or infrastructure unless the task actually requires it.

Useful partial automation is acceptable; workflow completeness is not a success criterion.

For delegation, state scope, ownership, dependencies, artifacts, verification and stop conditions in the existing plan.

Choose review depth by behavior risk and coupling; avoid fixed agent counts or review rounds for simple changes.

Before resolving conflicts, recover both intents and the common baseline; explain each choice and preserve ongoing work.

Reuse host hooks for deterministic checks; verify event fields, scope, and repeated triggers before relying on them.

Agents own contextual decisions and knowledge updates; hooks report or check specific events.

Do not silently reinterpret or weaken user requirements.

Before reporting completion, verify your own changes.

## Documentation

Keep documentation concise. Prefer links over duplicated explanations.

Code explains implementation. Documentation explains intent, structure, decisions, and current work.
