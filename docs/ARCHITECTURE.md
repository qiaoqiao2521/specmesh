# Architecture

SPEC.md defines the continuity standard. templates/ supplies minimal entry and task-file examples.
README.md is the public introduction; PROJECT.md records this repository's intent and priorities.

scripts/map_v0.py derives a deterministic, budgeted graph from code/Git and reviewed memory.
.specmesh/context.md configures experimental inputs; .specmesh/memory/ supplies asserted claims;
.specmesh/repo-areas.v0.yaml declares reviewed responsibility anchors. .specmesh/cache/ is rebuildable
output and is never authoritative or tracked. Area ambiguity or pending rebind suppresses scoped
memory; malformed authoritative declarations fail loudly.

`scripts/build_architecture.py` adds an optional human view over the same Map. Each project owns
reviewed module labels, responsibilities, paths, explicit relationships and check commands in
`architecture/architecture.json`; `architecture/explorer.html` is the reusable offline viewer.
The builder validates current paths, symbols and area gates, optionally executes declared checks,
and writes disposable HTML/JSON under `dist/architecture/`. Check evidence binds the actual Git
revision, dirty content and build definitions. It never writes project memory, infers business
relationships or treats an absent check as passed. Explicit downstream impact is a review
candidate set, not proof of behavioral failure. See [Architecture Explorer](ARCHITECTURE-EXPLORER.md).

CI stores static snapshots as Actions artifacts. Adopting private projects pin the public tool
revision and keep their own model/results in their repository. No hosted service, public Pages
deployment or change to the released independent runtime is required.

External viewers and agent runners may consume these files through independent interfaces.
No CM, History or Orca integration is required for development, acceptance or release. Markdown adoption
installs SPEC.md as the user's standard and uses templates only where a controlled project's actual
needs justify them. The optional machine profile runs independently as a bounded subprocess;
Markdown adoption does not require it.

## Read Next
- [Normative standard](../SPEC.md)
- [Experimental configuration and commands](../.specmesh/context.md)
- [Decisions](DECISIONS.md)
- [Release plan](../plans/release-alignment/task_plan.md)

## Codekit integration (v1.2.0)

See [CODEKIT-INTEGRATION](CODEKIT-INTEGRATION.md) for the new module boundary, public invocation and limits. This local implementation does not establish deployment acceptance.

`specmesh_port/service.py` owns progressive selection, structural findings and proposal generation.
`snapshot.py` owns descriptor-anchored observations and content/identity revalidation, including
missing files. `git_reader.py` owns bounded, filter-free Git plumbing with transport denial.
`__main__.py` exposes a capability descriptor and read-only request/result JSON. Contracts stay
inside this independent package; host adapters mirror and validate them. No module imports CM or
History Viewer. Assertions, derived references and externally verified results remain distinct.

The released 1.3.0 runtime adds project_state.py for finite, source-bound declaration extraction and
handoff.py for caller-scoped dirty retention and full live-material comparison. A handoff never
grants execution authority. The service keeps these reads inside one descriptor snapshot and
requires trusted task/files at consumption. See the interface document for explicit bounds.

scripts/build_release.py creates a deterministic allowlisted archive with source/file identities;
scripts/smoke_release.py validates an unpacked package in a fresh Python process and disposable Git
fixture. Those local distribution checks do not constitute S3 fresh-Agent acceptance.

The distribution includes scripts/verify_install.py for declared-file hash checks, not signature
verification. Versioned runtime directories can be switched without altering project memory or
the normative standard link. Release/installation acceptance is recorded in the bounded-delivery plan.
