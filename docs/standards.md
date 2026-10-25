# Standards index

This is the entry point for agents working on this repository. Select standards
by the operation being performed; do not load every document by default.
Standards constrain an authorized task; they do not grant permission to commit,
push, publish, or release.

## Select by task

| Task | Read | Authority |
|---|---|---|
| Create/rename a branch; prepare a commit, merge proposal, or release | [Git standards](standards/git.md), relevant rules below | Repository development policy |
| Change fixture schemas, validation, adapters, or continuation handling | [Fixture interoperability](standards/fixture-interoperability.md) and [fixture contract](fixture-format.md) | Pinned standards/profile and execution semantics |
| Author or update fixture artifacts | [Fixture contract](fixture-format.md) and the relevant schema in [`../schemas/`](../schemas/) | Format requirements and machine-enforced structure |
| Understand schema relationships | [Schema ERD](schema-erd.md) | Explanatory reference, not a replacement for schemas |

For fixture work, use JSON Schema Draft 2020-12 and the restricted Harbor
ATIF-v1.7 profile. The [interoperability document](standards/fixture-interoperability.md)
retains the exact upstream pin, prior-art comparison, and profile constraints.
Snapshot manifests, budgets, and semantic labels are benchmark-specific;
these fixtures are not Harbor tasks.

## Git rule lookup

Rule IDs are stable references for agents and review findings. `MUST` denotes
a requirement; `SHOULD` denotes a default with justified exceptions.

| Rule ID | Level | Load when |
|---|---|---|
| [`cs:git.branch.name`](standards/git.md#csgitbranchname) | MUST | Creating or renaming a branch |
| [`cs:git.commit.message`](standards/git.md#csgitcommitmessage) | MUST | Preparing a commit that will land on main |
| [`cs:git.commit.scope`](standards/git.md#csgitcommitscope) | SHOULD | Choosing a commit scope |
| [`cs:git.merge-proposal.description`](standards/git.md#csgitmerge-proposaldescription) | MUST | Writing or updating a merge proposal |
| [`cs:git.tag.versioning`](standards/git.md#csgittagversioning) | MUST | Creating a release tag or configuring version tooling |
| [`cs:git.commit.context`](standards/git.md#csgitcommitcontext) | SHOULD | Preparing a commit with a coding harness |

The former ID `cs.git.commit.context` is an alias for
`cs:git.commit.context`; use the latter in new references.

## Apply and maintain standards

1. Load the relevant document before changing the affected artifact.
2. Apply rules only when their applicability condition is met. Examples are
   illustrative, not exhaustive lists of accepted values.
3. Run the listed checks when applicable. State which checks ran; do not
   claim compliance based only on an example or a syntax check.
4. Report violations with a rule ID (or fixture-contract section), artifact,
   evidence, and suggested correction. Distinguish requirements from guidance.
5. Keep each rule in its canonical document. This index routes agents; do not
   duplicate requirements here. Keep IDs stable and retain aliases for renames.

Schemas define machine-enforced structure; the fixture contract also defines
semantics that schemas alone cannot enforce. Report inconsistencies between
them instead of choosing whichever permits a change. Respect higher-priority
agent instructions and surface any conflict with these standards.

[Repository agent instructions](../AGENTS.md) cover the validation commands and
evaluation trust boundary. The former [`git.md`](git.md) path remains a
compatibility link to the canonical Git standards.
