# OpenRouter / Pi pilot

Evaluator-only experiment, not reviewer input. Start with
[comparison.md](comparison.md), [manifest.json](manifest.json), and the
[human grading worksheet](grading-worksheet.md). Raw Harbor trials, reviews,
unsigned judgment forms, exported MLflow traces and billing metadata live in
`../../runs/openrouter-pilot-20261025T221002Z/` (Git-ignored, retained locally).

## What ran

The existing `run_eval.py` CLI and Harbor's built-in `pi` integration execute
all cases. `replay.py` only sequences the CLI's existing `run_eval.run` core,
gates the next launch, and reads OpenRouter generation metadata. It does not implement an agent loop, agent
registry, container runtime, prompt adapter or judge. `summarize.py` summarizes
retained evidence and prepares unsigned worksheets.

The pilot selects only `fixtures/case-0004` and `fixtures/case-0005`, regardless
of other fixtures subsequently added to this shared checkout. Original fixture,
prompt and schema hashes are pinned. Changes outside this experiment and the
`.env` ignore rule were made concurrently by others and are not this task's edits.
Concurrent reporting changes during preflight are explicitly recorded in the
manifest. A later source-hash gate stopped after invocation 04, before any new
request. The remaining calls load the existing evaluator core once so subsequent
checkout edits cannot change it mid-matrix; its exact source is archived in
`harness-source.tar.gz`. Reviewer-facing settings did not change. The first four
invocations used the CLI subprocess; remaining invocations use that same CLI
core in-process. All use Harbor's identical built-in Pi integration.

Three explicit, versioned model IDs were selected from the live OpenRouter
catalog. The selected catalog and endpoint responses, advertised prices, common
Pi configuration and exact image ID are retained. Catalog access and read-only
generation metadata queries do not invoke models. Provider availability can
change; replay must not silently substitute models.

The first Qwen attempt authenticated but submitted no artifact. The next
already-planned Mistral attempt was run alone and verified collection,
normalization, tracing and billing before the remaining matrix was launched.
Both attempts count in the 18; no failed case is retried or discarded.

## Reproduce execution (paid, separate budget required)

From the repository root, with a private `.env` containing
`OPENROUTER_API_KEY`:

```sh
uv sync --locked
# Use the original local image when available; replay checks its exact ID.
# Rebuilding later may change apt/Node/transitive dependencies and therefore
# requires a separately identified manifest/image revision, not mixing results.
docker build -t code-review-pilot:20261025T221002Z \
  experiments/openrouter-pilot-20261025T221002Z

# NEW output root, never the original run directory.
uv run python experiments/openrouter-pilot-20261025T221002Z/replay.py \
  --output runs/openrouter-pilot-REPLAY-UNIQUE --count 1
# Inspect authentication, artifacts, usage and MLflow trace before continuing.
uv run python experiments/openrouter-pilot-20261025T221002Z/replay.py \
  --output runs/openrouter-pilot-REPLAY-UNIQUE --count 17
```

The manifest records approval of infrastructure checks for the original pilot,
not human approval of review quality. A replay still needs its own first-case
inspection. A hash/image mismatch intentionally stops execution; use the
recorded revision or create a clearly separate experiment revision rather than
silently accepting drift. The image contains only public Pi configuration,
never a fixture checkout, private labels or credentials. Harbor owns sandbox
creation and agent installation.

`python-dotenv` loads `.env` with `override=True` inside the orchestrator.
This is necessary here because an inherited empty `OPENROUTER_API_KEY` masks
`uv --env-file`. Harbor's supported model connection resolver forwards the key
to Pi via execution environment variables. No key values appear in command
arguments, option files or manifests. No account settings or key permissions
were changed.

## Budget and limitations

Before any paid request, the maximum full common context and output allowance,
worst advertised selected endpoint rates and a 2x contingency estimated the
18-case matrix at US$0.1523712. The launch gate reserves US$0.10 for the next
invocation and for every finished invocation whose billing is unknown, against
US$2 total. Known OpenRouter `total_cost` replaces a reserve after each case in the original
finish-time ledger. Unknown billing is never zero. Pi catalog-derived costs remain
a separate, non-authoritative source. The final audit also conservatively reserves
for seven zero-usage/no-response-ID abort markers: they are not proof of another
completed turn, a retry, or zero additional billing. Thus full-case totals are
incomplete for 14 cases; US$0.002744041 in identified generation charges is known,
and US$1.402744041 is booked including conservative reserves. This is not a final
invoice or a guaranteed cap.

This is a conservative launch policy, **not a guaranteed billing cap**. Harbor
enforces agent wall time/resources, not full episode spend or token/tool caps.
One native `write` submission tool remains enabled despite the fixed-context
fixture's nominal zero-tool allowance. Tool restrictions are incomplete; this
is **not an enforced no-tools baseline**. One model turn and 1,024 output tokens
are configured consistently, Pi retries/compaction/warming are disabled, and
failures remain visible. Upstream routing and service behavior are not frozen.

## Human grading and refresh (no paid model calls)

Use the worksheet's interactive `run_eval.py grade` commands. Every finding,
reference match, duplicate, novel issue, empty review and behavior verdict must
come from the human grader. Only their explicit HUMAN attestation can authorize
HUMAN MLflow feedback. Do not ask an evaluated model to judge itself or import
agent suggestions as human approval.

After grading, run each corresponding `run_eval.py adjudicate` command, then:

```sh
uv run python experiments/openrouter-pilot-20261025T221002Z/summarize.py
```

Before grading, `uv run python experiments/openrouter-pilot-20261025T221002Z/verify.py`
checks the 18 retained attempts, unique sessions/traces, common Pi system/tool
configuration, output limits, unsigned forms, costs and absence of the credential
in output files/MLflow storage. Its no-approval assertion intentionally applies
only before human grading. See `verification.json` for the recorded check.

The original outputs remain the target of this summary command. All 18 bundles
were refreshed unsigned through the common final adjudication workflow; its
source is retained in `grading-source.tar.gz`. No HUMAN assessment was logged.
Final validation passed for 17 shared-checkout fixtures and 172 unit tests; this
experiment itself used only the original pair and authored no fixtures. Quality
and ranking stay pending until real adjudication is complete. Artifact presence is
never quality. Any eventual winner is only **best on this small pilot**.
