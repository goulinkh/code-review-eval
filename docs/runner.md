# Code-review evaluation on Harbor

[Harbor](https://github.com/harbor-framework/harbor) **owns execution**: agent
integrations, installation, Docker environments, deadlines, artifact collection,
verifier lifecycle, native logs/ATIF, and trial results. This repository adds
only fixture export, MLflow lifecycle tracing, review normalization, per-case
reports, and human adjudication. It does not implement a second agent registry,
process runner, container runtime, or model judge.

The runtime is pinned to **Harbor 0.25.0**; Python 3.12+ and a running Docker
engine with Compose are required. The source fixture format and its restricted
ATIF prefix profile are unchanged. Generated Harbor tasks are a disposable
execution representation, not a replacement for the source fixtures.

## Run

From `code-review-eval/`:

```sh
uv sync --locked

# Real Harbor/Docker run, synthetic recordings, no model credentials/spend.
uv run python run_eval.py run fixtures/case-0004 fixtures/case-0005 \
  --recorded recorded_reviews/smoke --output runs/recorded-smoke

# Harbor's existing agent integrations; real model access can incur charges.
uv run python run_eval.py run fixtures/* \
  --agent pi --model anthropic/YOUR_MODEL --output runs/pi

uv run python run_eval.py run fixtures/* \
  --agent opencode --model anthropic/YOUR_MODEL --output runs/opencode
```

Configure the selected provider's credentials using Harbor's normal credential
resolution, e.g. `ANTHROPIC_API_KEY`. Do not supply code-hosting write credentials
or mount the developer's home/checkout. Native agent installation may download
packages in the sandbox; the first Docker run may pull the base image.

`--agent-kwargs /path/to/options.json` passes an object directly to Harbor's
agent constructor. Use Harbor's native options to pin versions and configure
prompts/tools; no Pi/OpenCode launch flags or stream parsers are maintained
here. For example, the generic installed-agent `version` option pins an agent
release. Keep credentials out of option files; Harbor persists job configuration.
`--image` selects the base image (default `python:3.13-slim`).

Each invocation creates a new output directory and one Harbor job with one
attempt per case, sequential trials, and no automatic retries. The exporter
rejects unsupported tool-enabled/continuation cases before launching anything;
it never replays supplied historical calls or silently starts a fresh review.

## Custom agents

Use Harbor's existing extension interface, not an evaluator-specific adapter:

```sh
uv run python run_eval.py run fixtures/* \
  --agent my_package.review_agent:MyAgent --model provider/model \
  --output runs/custom
```

Implement Harbor's `BaseInstalledAgent` for a CLI inside the sandbox, or
`BaseAgent` for an external loop that uses `BaseEnvironment`. See
[Harbor custom agents](https://harborframework.com/docs/agents/custom-agents).
The included [`harbor_agents.RecordedReviewer`](../harbor_agents.py) is a small,
working `BaseAgent` example that submits exact recorded bytes through
`environment.exec`. `--recorded` is just a convenience for selecting that class.
Future agents need no changes to fixture export, execution, or human scoring.
External agent implementations are trusted evaluator code, not sandboxed by
virtue of inheriting `BaseAgent`.

## Review submission and task export

The agent receives a common instruction followed by the exact public
`reviewer/input.json`. It writes its final **user-visible review** to
`/workspace/review.json`. The task explicitly declares this file as a Harbor
artifact, collected as `<trial>/artifacts/review.json`. The evaluator preserves
its exact bytes before parsing or grading. Native agent logs and trajectories
remain under Harbor's trial directory; they are not used as semantic answers.

Minimal output:

```json
{"schema_version":"1.0.0","findings":[]}
```

A finding requires `text`; optional fields are `path`, `side` (`base`/`head`),
`lines` (`start`/`end`, inclusive 1-based), and `severity`. File-level and
unlocated findings are valid. The closed [output schema](../schemas/review.schema.json)
also permits summary, recommendation, usage, and normalization-loss notes.
The evaluator does not strip Markdown, rewrite prose, or use a model to invent
structure. Empty findings do not imply approval. Unknown usage/cost is `null`.
Report usage comes from Harbor's runtime `AgentContext`, not model estimates.

Exported tasks contain only `instruction.md`, `task.toml`, a minimal Dockerfile,
and a mechanical verifier. **Neither private labels nor full fixture snapshots
are copied into the task, image build context, or sandbox.** Labels stay in
evaluator-only per-case directories beside `tasks/`. The verifier runs in a
separate Harbor environment and checks only whether the artifact was submitted.
Harbor's `artifact_present` reward/mean is **not finding quality**; a perfectly
formed invented review can earn artifact presence and fail human adjudication.

### Capability and enforcement limits

These tasks supply fixed repository context, but native Harbor agents retain
their normal tools (including the shell needed to submit the artifact) and
inference network access. This is **not a controlled no-tools baseline**. The
instruction prohibits additional context retrieval and experiments; that alone
does not enforce the prohibition. The manifest reports this gap explicitly.
Do not claim tool-use scores or compare these runs as isolated prompt-only
changes without controlling the agent capabilities.

Harbor enforces the configured agent wall timeout and sandbox CPU/memory
resources. Build/setup/verifier time is separate from the fixture's agent-time
budget. This layer does not enforce token, spend, repository-call, returned-byte,
or total episode caps. A reported token overrun fails the case after execution;
unknown telemetry never implies compliance. Backend network/disk restrictions
and native tool controls require separately configured Harbor capabilities.
Recordings cannot establish original latency or original context isolation;
Harbor timing measures their import/submission, not historical inference.

## Human adjudication

Open `runs/recorded-smoke/report.md`. Quality is initially **pending**, including
for empty reviews. Grade in an interactive terminal; no JSON editing is needed:

```sh
uv run python run_eval.py grade runs/recorded-smoke
# Optional: --case case-0004
uv run python run_eval.py adjudicate runs/recorded-smoke
```

`grade` displays the exact finding text, summary/recommendation, supplied diff,
line-numbered initial code, private reference (including non-findings and the
behavior rubric), and trace path. Apply the same rubric across reviewers:

- Enter your operator identifier. Classify each finding as `valid`, `invalid`,
  `duplicate`, or `unresolved`; there are no generated grading suggestions.
- Valid findings can match a required reference ID or be `novel`. Unmatched does
  not mean false. Match by defect mechanism/evidence, never exact wording or
  keywords. Each reference can be matched only once.
- Duplicates name another distinct valid/invalid finding, not another duplicate.
  They count toward annotation coverage but not distinct-finding precision.
- Resolved decisions require reasons. Context/instruction verdicts are `pass`,
  `fail`, `not_applicable`, or `unresolved`, with reasons when resolved.
- An empty review needs an explicit `approved` inspection acknowledgment and
  reason, even on a defective case. This acknowledges inspection, not that the
  reviewer was correct: an approved empty defective review has confirmed misses.
- Blank keeps the displayed value. `q`, EOF, or Ctrl-C stops safely; rerun the
  same command to resume. Each complete decision is saved atomically. Incomplete
  edits never replace prior judgments. Other-session changes are detected before
  saving; do not grade/import the same form concurrently.
- Type `HUMAN` only if these are your own human-reviewed judgments. An identifier
  alone is not approval. Approval binds the entire current form, including any
  unresolved entries; changing it requires confirmation again.

`adjudicate` checks every retained input/reference/raw/normalized-review hash and
all forms before logging feedback. Only explicitly human-confirmed forms attach
as HUMAN MLflow assessments. Re-importing semantically unchanged forms is
idempotent, including JSON reformatting; changed approved forms create revisions.
Report quality follows the latest imported local form; historical assessments
remain in MLflow. A form's approval digest is an integrity/attestation record, not
cryptographic proof of a person's identity. The operator must not impersonate a
human. Labels are never edited by grading; corrections require a dataset revision
and rescoring every reviewer.

Pre-approval forms are upgraded as **drafts**, retaining their decisions but not
inventing human approval. Reopen and confirm them through `grade`. For automated
walkthroughs, `grade --practice` accepts scripted input and requires `PRACTICE`;
it records source `simulation`, labels all scores as practice, and **never logs
HUMAN feedback**. It must not be presented as actual adjudication. See the
[recorded Docker demonstration](adjudication-demo.md).

### Compare reviewer/model runs

```sh
uv run python run_eval.py compare runs/pi runs/opencode --output runs/comparison
```

Open `runs/comparison/report.md` (also `report.json`). Input runs must have the
same selected cases, revisions, exact public/private hashes and common review
instruction. Different subsets or changed rubrics fail rather than silently
pooling incomparable results. Runs need not all be adjudicated: pending runs
remain explicitly pending. Import changed forms first. Comparison outputs use
fresh directories, never overwrite an earlier report, and work offline without
an MLflow connection. Evidence links lead to each retained review, request,
private reference, form, and trace. All output remains evaluator-only.

The report uses micro-aggregated counts per run, not a weighted overall score:

- **Defect recall:** matched required references / required references on
  completed executions. Unmatched references stay pending until all findings (or
  the empty review) are explicitly inspected; only then are they confirmed misses.
  Bounds show pending uncertainty rather than treating it as a confident miss.
- **Finding precision:** valid distinct / (valid + invalid distinct). Novel valid
  findings count as valid; duplicates are excluded. Unresolved findings are
  excluded from this point estimate but shown in coverage and precision bounds.
- **Corrected-case false alarms:** invalid distinct findings on provisionally
  clean/corrected cases, affected-case count/rate, pending cases, valid novel
  findings, and unavailable executions. Unmatched does not imply a false alarm.
  The affected-case rate is a lower bound while cases are pending.
- **Adjudication coverage:** resolved findings (including duplicates) / all
  submitted findings, plus fully adjudicated cases / completed cases. The latter
  includes explicit empty-review acknowledgment and behavior verdicts. Empty
  finding denominators are N/A, not perfect coverage or precision.
- **Execution reliability:** statuses and completion rate, with required defects
  on failed/timed-out/invalid-output cases marked execution-unavailable, **not
  human-confirmed misses**. Delivery recall is separately shown as a lower bound
  across all required references, including execution-unavailable ones.
- **Latency and cost:** independent fields with known/total case counts. Partial
  known cost is not the total cost; missing telemetry is unknown, never zero.
  Recorded latency measures artifact submission, not original model inference.

No confident ranking is produced from unresolved judgments, simulations, or this
provisional corpus. Even complete case grading does not constitute independent
fixture annotation verification. Reference contract probes are not reviewer scores.

The supplied recordings cover only `case-0004` and `case-0005`, not all 12
authored cases. They contain an intended match plus an intentionally
unsupported allegation in `case-0004`, and an empty review in `case-0005`.
They are harness controls, not real model results. Tests also cover empty
missed-defect controls, invalid artifacts and failed/timed-out Harbor trials.

## Artifacts and MLflow

Runs, imports and comparisons also emit [`visuals.json`](visual-reports.md) for
the notebook's opt-in **Evaluation results** panel. Backfill retained runs without
execution or assessments:

```sh
uv run python run_eval.py export-visuals runs/pi runs/opencode --output runs/comparison
```

```text
manifest.json                    # hashes, versions, budgets, capability/enforcement gaps
report.md / report.json          # per-case quality + execution counts, no overall score
visuals.json                    # versioned flat run/case/metric tables for charts
tasks/<case-id>/                 # exported native Harbor task; no private labels
harbor/                         # Harbor job: config/lock/results and native trial directories
<case-id>/
  request.json / reference.json  # retained public request / PRIVATE rubric
  review-output.bin             # exact submitted bytes, even if partial or invalid
  review.json                   # normalized findings with stable IDs
  adjudication.json             # editable human judgments
  report.json / trace.json      # per-case report and exportable MLflow trace
```

All run output is **evaluator-only**. Never expose the run directory, original
fixture checkout, native logs, or human assessments to another reviewer.
Harbor's logs may include raw exceptions and credentials emitted by an agent;
inspect them before sharing. Automatic MLflow spans contain only IDs, hashes,
counts and status, not prompts, code, environment values or raw exceptions.
Human assessments deliberately capture the submitted form; do not put secrets
in adjudication text.

Traces use Harbor's real trial/agent lifecycle hooks plus the actual
normalization/checking activity. They do not reconstruct fictional internal
steps from a final answer. Native ATIF stays in Harbor's format and is not
silently relabelled as our restricted continuation-prefix profile.

```sh
uv run mlflow ui --backend-store-uri "sqlite:///$(pwd)/mlflow.db"
```

MLflow defaults to local SQLite, ignoring an inherited tracking URI unless
`--tracking-uri` is explicitly supplied. Reports remain readable without its
UI. Missing traces/results fail the evaluation instead of claiming success.
Exit 0 means all cases completed execution (not that quality passed), 1 means a
case failed/timed out/had invalid output, and 2 means an evaluator/config error.

## Checks

```sh
uv sync --locked
uv run python validate_fixtures.py examples/* fixtures/*
uv run python -m unittest discover -s tests -v
```

Unit tests use Harbor's real task/config/factory models and stub job lifecycle
events; they do not launch containers or call models. The recorded command
above is the real Harbor/Docker integration smoke test, with no paid model call.
