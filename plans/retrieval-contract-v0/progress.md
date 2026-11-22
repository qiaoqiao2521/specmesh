# Progress
Implemented the optional read-only command, source-specific status handling, and negative tests. See [usage](../../docs/RETRIEVAL-CONTRACT.md) for direct reproduction. Live cross-source user-data validation remains separate from fixture validation.

## 2026-11-22 — Native compressed-case material identity

User authorized direct `main` delivery. Added the case-expansion/material-export workflow and an optional native contract regression, without changing the production retrieval validator, command exit semantics or runtime dependencies.

- With AgentTraceMesh's pre-fix exporter, the actual CLI contract failed exactly on the compression/materials `store_id` mismatch (7 passed, 1 failed).
- With the corrected exporter, all eight retrieval tests passed. The binding uses the original case evidence identity, preserves hidden message slots and later corrections, and returns only context locators with `live_verified=false`.
- Full SpecMesh regression with `AGENTTRACEMESH_CHECKOUT` explicitly supplied: **125 tests passed** (Python 3.12.14, `TZ=UTC`, 11.617s). Without the explicit checkout, the native contract is skipped and the independent runtime remains usable.
- Existing legacy `local` material packets retain their original exact bindings. Mixed namespaces remain rejected; the actual pre-fix exported packet from the preceding integration verification still matched its original binding.
- Independent review found no remaining P1/P2 issue; `git diff --check` passed.

The corresponding exporter fix is [AgentTraceMesh b9e1e73](https://github.com/qiaoqiao2521/AgentTraceMesh/commit/b9e1e739f64de8ce6918a96c2eebb436064723bc). Source delivery uses a fast-forward update of `main` and remote-head readback; no service, installation or private-history rollout is implied.
