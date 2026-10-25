# Fixture format 1.0.0

## Contract and versioning

The schemas use JSON Schema Draft 2020-12. Every object is closed except real
implementation-specific tool arguments and the small environment-variable
allowlist. References use versioned URNs resolved from `schemas/` offline; a
validator must not fetch remote schemas. Unknown fields and versions fail.

| Document | Audience | Schema |
|---|---|---|
| `reviewer/input.json` | Reviewer/adapter | `reviewer-input.schema.json` |
| `reviewer/prefix.json` | Reviewer/adapter, continuation only | `atif-prefix.schema.json` |
| `private/expectations.json` | Evaluator/grader only | `expectations.schema.json` |
| `environment/blobs/<sha256>` | Evaluator's fixture-backed read service | Raw UTF-8 bytes |

An adapter consumes the reviewer input, not a combined fixture object with a
`private` field to remember to remove. Never pass labels, expected paths,
category hints, provenance, dataset partitions, grader instructions, private
reproducers, or the parent checkout to the reviewer. IDs match `case-[0-9]{4,}`;
revision and snapshot names should also be neutral. Closed schemas reduce
accidental exposure; they cannot detect answer leakage or credentials in
free text. Authors must inspect all reviewer-visible content.

`schema_version` versions the format; `protocol.version` versions execution
semantics. `case_id` plus `revision` names immutable case content. Private
`dataset.id/version` identifies an immutable comparison corpus, including its
labels and rubric. Breaking changes require a new schema/protocol version.
Label corrections require a dataset revision and rescoring all reviewers.

## Snapshots and changes

A fixture owns its before/after trees. `snapshots.base/head` each provide an
opaque immutable `id` and complete inventory of canonical project-relative
paths and SHA-256 content digests. No Git commit or hosted repository is
required. IDs are scoped to the fixture revision, not global Git hashes; they
must not collide with the reserved branch labels `base` and `head`.

The single `repository` is a fixture alias. Requests for branch labels `base`
and `head`, or for the exact snapshot ID, resolve locally to those inventories.
There is no live branch resolution. Multi-repository fixtures are deferred.

Blobs are stored under `environment/blobs/<lowercase SHA-256>`. Hash exact raw
bytes, without newline conversion. Version 1 supports UTF-8 text files that
are empty or end in a newline; binary files and symlink artifacts are rejected.
Do not execute snapshot contents as part of validation. Renames are represented
as deletion/addition; coordinates remain ordinary base/head file coordinates.

An available diff has `format: "unified"` and an inline `{content, sha256}`
artifact. Generate the canonical diff using `generated_diff()` in
`validate_fixtures.py`: sorted paths, three context lines, `a/` and `b/` names,
`/dev/null` for absent files. The validator compares it to the snapshot bytes.
An unavailable diff instead has `status: "unavailable"` and a reason; it is
not interchangeable with an available but empty diff.

The input hash in private expectations covers the **exact bytes** of
`reviewer/input.json`. The continuation input additionally pins the exact
prefix file hash. JSON formatting changes therefore require updating hashes;
no bespoke JSON canonicalization or implied Git identity is involved.

## Accessible context and capabilities

`context_manifest` enumerates material the reviewer may access. Each entry
names a snapshot, path, delivery mode, and availability:

- `initial` + `available`: inline `content`, checked against its snapshot.
- `tool` + `available`: no inline content; serve the whole file through the
  declared read boundary, only when requested.
- `missing` or `error`: no content; a prescribed `error_message` and nonzero
  `exit_code`. Missing files must actually be absent from the snapshot. A read
  error can deny access to an existing file.

The snapshot inventory is not an access grant. Unlisted requests must be
blocked or explicitly fail; they cannot successfully return repository data.
All reviewer-visible initial content is inline. The adapter must not mount
`environment/` wholesale, even for tool-enabled cases.

`fixed-context` has no tools and only initial context. `tool-enabled` declares
real tool names, their kind (`shell` or `repository-read`), and permitted
operations (`repository.read`, `discovery`). A shell tool is not permission to
execute arbitrary commands. A future runner must isolate access to these
operations, deny network/credentials/host-project access, and report any
observation gap. This schema validator does not enforce that boundary.

`content_capture: "approved-fixture-content"` explicitly approves full source
and supplied dialogue capture for this fixture only. It does not authorize
capturing host environment dumps, credentials, or raw transport exceptions.

## Fresh and continuation mode

Fresh input has `start: {"mode": "fresh"}` and no prefix file. Its inherited
usage is zero. Continuation input instead declares:

- `checkpoint_id` and `prefix: {file: "prefix.json", sha256: ...}`;
- the exact base/head IDs at the checkpoint;
- the pinned environment and currently permitted tools;
- inherited usage and explicit remaining limits.

`environment` currently describes a read-only fixture workspace with
`cwd: "."`, a `LANG`/`LC_ALL`/`TZ` variable allowlist, and `runtime_state: null`.
No hidden files, proprietary agent memory, private model reasoning, or
in-flight operations are implicit in the checkpoint. If more state is needed,
this protocol cannot faithfully represent that checkpoint: report unsupported.
A transcript is not a runtime-state snapshot.

The ATIF profile is defined in
[the fixture interoperability standards](standards/fixture-interoperability.md).
Its ordered steps preserve system/user/agent dialogue. Each agent tool call retains its ID,
actual tool name, and arguments. Exactly one result on that same step retains
the visible stdout (`content`) and namespaced execution metadata:

```json
{
  "source_call_id": "call-01",
  "content": "def allowed(used, limit):\n    return used <= limit\n",
  "extra": {
    "code_review_eval": {
      "status": "completed",
      "exit_code": 0,
      "stderr": "",
      "duration_ms": 10,
      "repository_reads": []
    }
  }
}
```

The example above illustrates a tool result's shape only; actual repository
reads must populate `repository_reads`. One shell invocation may record zero,
one, or multiple reads. For `lp`, keep the actual shell command in the call
arguments; do not invent an agent tool called `read_file`.

Read events record operation, repository, requested revision, resolved immutable
snapshot ID (or `null` for unknown), canonical path, completion status,
returned file bytes, and content hash (`null` when unavailable). Only a
`completed` whole-file read matching the correct repository/snapshot/path
counts as evidence. Missing, error, incomplete, and blocked attempts are not
successful retrieval. Stdout and stderr still preserve their actual results.
No range reads, filtered-output reconstruction, or speculative tool calls.

Resume only after all supplied calls have results, at a reviewer decision
boundary. Restore the declared state **without executing historical calls**.
Keep the prefix as a hashed, labelled input artifact; trace the generated
suffix separately. Mark historical ATIF steps `is_copied_context: true`; they
are not newly executed spans. An adapter unable to preserve the messages,
call/result associations, or environment must report unsupported continuation,
not silently start fresh or summarize the history.

## Hard budgets and inherited usage

`budgets` contains complete `whole_path`, `inherited`, and `remaining` maps.
All count/size/time values are nonnegative integers. Zero prohibits additional
usage; it is not a default or an unspecified limit.

| Dimension | Unit/accounting |
|---|---|
| `tool_calls` | Agent-facing calls, including failures, retries, and discovery |
| `shell_invocations` | Actual shell tool calls, separate from nested repository reads |
| `repository_read_attempts` | Each observed whole-file attempt, including failures/repeats; discovery is not a read |
| `returned_bytes` | UTF-8 stdout plus stderr visible in tool results, counted once per result, not again per nested read |
| `wall_time_ms` | Whole-path elapsed execution time; inherited duration is declared, not a sum of possibly parallel calls |
| `model_tokens` | Optional hard combined input/output-token cap; `null` cap means no provider-token cap, and `null` inherited usage means unknown |

For every finite cap: `remaining = whole_path - inherited >= 0`. For a null
cap, remaining is also null. Unknown inherited token usage cannot support a
finite whole-path token cap. Fresh inherited token usage is zero even when
uncapped. Missing cost/token telemetry is unknown, never zero by inference.
Token usage and wall time cannot be reconstructed from text-only ATIF history;
the checkpoint author declares them. Inherited elapsed time must at least
cover the longest recorded call, without summing possibly parallel calls. The
other inherited counters are checked against supplied calls, outputs, and read
events.

Only the newly generated suffix consumes remaining limits. Report fixed-prefix
usage, suffix usage, and combined totals separately. Do not reset budgets on
resume. Grade continuation efficiency against the remaining limits and private
suffix soft budget, not the cost or mistakes of the supplied prefix.

Hard limits are public and must eventually be enforced by the runner. Private
retrieval `soft_budget` values measure efficiency (read attempts, returned
bytes, repeated successful reads), not permission to exceed hard limits.
A blocked attempt is an observable budget/safety event, not a successful clean
review. This repository validates budgets; it does not enforce execution.

## Private labels and expected remainder

Private expectations bind to the input hash and record:

- dataset version, partition, scenario group, and related cases;
- languages, primary/secondary concerns, and defective/clean/undetermined status;
- original/derived provenance, permission/licence, source fix/parent hashes and
  paths, synthesis changes, and independent-verification status;
- required defects with explanation, severity/rationale, defensible base/head
  locations (inclusive 1-based lines, or `null` for a file-level finding),
  evidence, and why the allowed context makes them discoverable;
- specific incorrect allegations to avoid, context limitations, and resistance
  to instructions embedded in reviewed material;
- required retrieval evidence, alternative paths, and soft exploration limits;
- continuation-only required remaining actions, forbidden actions, essential
  ordering, and acceptable alternative behavior; fresh cases use `null`;
- final-review behavior, not exact wording or a mandatory approval vote.

Each retrieval requirement accepts any one `acceptable_sources` entry; use
separate requirements when both caller and callee are necessary.
`available-evidence` accepts relevant initial or prefix evidence, so no redundant
read is needed. `new-suffix` explicitly requires a new successful read and
must be justified by an outstanding uncertainty, not used to force repetition.
Do not require context-dependent findings in a diff-only case that cannot
establish them. Fixed-context cases have no retrieval requirements or tool-use
score. Check content quality and evidence acquisition separately.

Continuation `required_remaining_actions` describe observable suffix behavior,
not an exact transcript. `essential_order` references action/retrieval IDs or
reserved `final_review`; cycles and unknown IDs fail validation. Prefix
mistakes are not new reviewer failures; preserving a mistaken claim in the
final review can be. Grade only new actions and the final artifact.

An unmatched finding is not automatically false. Semantic matching, novel
findings, discoverability, and experimental relevance need the frozen rubric
and human adjudication. The validator is not a semantic judge. `pending`
verification examples must not be reported as independently verified clean
cases or final corpus coverage.

## Pre-run validation and limits

`validate_fixtures.py` checks schemas, raw hashes, blob/diff consistency,
canonical paths, snapshot agreement, call/result consistency, checkpoint mode,
inherited counters, remaining-cap arithmetic, and obvious required-evidence
budget infeasibility. It rejects symlink artifacts and unexpected files in
`reviewer/`. Validate related cases together to check partition/group integrity;
references outside the selected subset are not checked for completeness.

It does not prove arbitrary natural-language expectations, full multi-step
budget feasibility, provenance permission, absence of free-text leakage, or
sandbox safety. A frozen dataset needs independent annotation review and an
immutable run manifest in addition to these checks. Fresh and continuation
results remain separate in reports; related pairs, adversarial variants, and
checkpoints must stay in the same partition.

## Deferred work

No reviewer output schema, adapters, execution runner, grader, live posting,
CLI sandbox, or tracing backend is implemented here. The initial fixed-context
protocol can use these contracts without building a review loop.

REPL execution is a post-initial protocol. It will need a real sandbox,
versioned interpreter/semantics, session identity, hashed restorable runtime
state (definitions, variables, loaded code and seeds), experiment budgets,
execution observations, and private discriminating-probe requirements. The
current `runtime_state: null` does **not** claim to restore such a session.
Do not add invented ATIF top-level fields or fake runtime state; version the
fixture/profile extension when that milestone is designed.
