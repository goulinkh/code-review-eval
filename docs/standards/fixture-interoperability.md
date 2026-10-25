# Fixture interoperability standards

**Applies to:** changes to fixture schemas, validation, adapters, or continuation
handling. Read alongside [the fixture contract](../fixture-format.md); this
file defines the standards selection, upstream pin, and ATIF profile.

## Decision

Use [JSON Schema Draft 2020-12](https://json-schema.org/draft/2020-12)
for machine-readable contracts and Harbor's **Agent Trajectory Interchange
Format (ATIF)** for supplied conversations and tool history.

ATIF is an existing agent-evaluation interchange specification, not a universal
or ISO standard. Our checkpoint profile targets **ATIF-v1.7**, sufficient for
text-only tool calls and namespaced observation metadata. Upstream also
supports v1.8 (audio); no audio, images, subagents, model reasoning, or training
metrics are needed here. Do not accept other versions by silently relabelling
them.

Exploration used GitHub's `gh api` against:

| Project | Relevant contract | Decision |
|---|---|---|
| [Harbor](https://github.com/harbor-framework/harbor) | ATIF trajectories and isolated task/verifier layout | Reuse ATIF verbatim field names and its extension mechanism. Follow the separation principle, but do not claim task-format compatibility. |
| [Inspect AI](https://github.com/UKGovernmentBEIS/inspect_ai/blob/main/src/inspect_ai/dataset/_dataset.py) | `Sample(input, target, metadata, files, sandbox, checkpoint)` | Good future adapter target; not a reviewer-neutral on-disk fixture/checkpoint standard. |
| [SWE-bench](https://github.com/SWE-bench/SWE-bench/blob/main/docs/guides/datasets.md) | Repository/base-commit/problem plus solution and test patches | Oriented to repository-based repair, not benchmark-owned review changes or continuation grading. |

No inspected format covers the whole required contract unchanged. In
particular, ATIF records interaction evidence; it does not restore environment
state, define private semantic finding labels, or subtract checkpoint usage
from whole-path limits.

## Pinned ATIF reference

Harbor commit: `fdba28fc411e47e8765420a1a063b4918fce3def`.

- [RFC and version history](https://github.com/harbor-framework/harbor/blob/fdba28fc411e47e8765420a1a063b4918fce3def/rfcs/0001-trajectory-format.md)
- [Trajectory models](https://github.com/harbor-framework/harbor/tree/fdba28fc411e47e8765420a1a063b4918fce3def/src/harbor/models/trajectories)
- [ATIF introduction](https://github.com/harbor-framework/harbor/blob/fdba28fc411e47e8765420a1a063b4918fce3def/docs-mintlify/agents/atif.mdx)
- [Task layout](https://github.com/harbor-framework/harbor/blob/fdba28fc411e47e8765420a1a063b4918fce3def/docs-mintlify/tasks/overview.mdx)

The RFC/models at the pinned commit include v1.8; the introductory page still
calls v1.7 current. We deliberately pin the supported v1.7 subset rather than
following a moving default. Our independently written JSON Schema is a
**restrictive profile**, not the official or complete upstream schema.
All accepted prefixes must also be valid upstream ATIF-v1.7.

The continuation example was additionally checked with the pinned upstream
`Trajectory.model_validate_json` model. Upstream model files were loaded only
in a temporary directory; no Harbor source or runtime dependency is vendored.
The regular test suite remains offline and checks our stricter profile.

## Profile constraints and extensions

Preserve `schema_version`, `session_id`, `agent`, `steps`,
`step_id`, `source`, `message`, `tool_calls`, `tool_call_id`,
`function_name`, `arguments`, `observation.results`,
`source_call_id`, and `content`.

ATIF maps assistant messages to `source: "agent"`; tool results are
observations on that same step, not invented messages or dedicated repository
tools. For shell-based `lp`, keep the real shell tool name and exact command
arguments. Each result's `extra.code_review_eval` holds exit status, errors,
duration, and observed repository-read metadata. ATIF explicitly permits
custom observation-result metadata in `extra`.

The profile additionally requires sequential IDs, globally unique call IDs,
exactly one completed result per call on the same step, and
`is_copied_context: true` on every supplied step. This excludes partial,
multimodal, summarized, or in-flight checkpoints. Do not strip unsupported
content and claim a lossless import; report unsupported continuation instead.

Only public dialogue and tool evidence belong here. The profile prohibits
`reasoning_content`, arbitrary root/step metadata, evaluator labels, and
proprietary memory. Fixture extensions use closed schemas, not arbitrary
metadata bags. Tool arguments remain arbitrary JSON objects because tools
have implementation-specific signatures.
