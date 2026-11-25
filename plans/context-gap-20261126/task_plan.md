# Context-gap recovery alignment

## Goal

Sync SpecMesh with the user's approved TraceMesh context-gap workflow: retrieve
only missing evidence that changes the next action, then resume the existing task.

## Context

Baseline: `44689b942d9ee14f75f12711356680a9ccadc13b` on `main`.
The user approved implementation and SpecMesh synchronization on 2026-11-26.
SpecMesh already provides progressive files, Map v0, an independent handoff and
an optional exact-bound historical-material reader. Reuse them.

## Requirements

- Sufficient current context means no additional retrieval.
- A gap names the missing fact, blocked action, scoped query/source, required
  evidence/revision and next action.
- Current project files/code precede historical explanations; repeated queries
  with unchanged scope/source revision reuse their results.
- Preserve missing, failed, stale, conflicting and incomplete evidence; summaries
  or aborted fragments cannot become verified facts or execution authority.
- Planning files, SpecMesh authority/index and TraceMesh history remain separate.

## Non-goals

No runtime state machine, database, service, mandatory hook, extra task-file type,
machine-interface change, release replacement, user-machine installation or
automatic history-to-memory promotion.

## Plan

- [x] Read existing standard, templates, retrieval and source binding behavior.
- [x] Clarify the standard and mirror the minimal rule in default templates.
- [x] Connect the rule to the existing retrieval workflow and progressive indexes.
- [x] Verify existing unit/native contract tests and rebuild/check Map inputs.
- [x] Review changes and record exact verification and delivery scope.

The SpecMesh agent owns this checkout; the parent owns TraceMesh and remote
delivery. Precise TraceMesh commands follow the implemented CLI, not a proposed
interface. Stop expansion when these rules and compatibility checks are covered.

## Success

Normative rules and templates agree, progressive links resolve, existing source
binding/runtime compatibility checks pass, and verification distinguishes source
delivery from installation and live-history effectiveness.

## Status

Source alignment and local verification complete; remote delivery is owned by
the parent task. See progress for precise acceptance and exclusions.
