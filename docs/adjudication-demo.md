# Recorded adjudication demonstration

This walkthrough uses real Harbor 0.25.0/Docker execution of the supplied
`recorded_reviews/smoke` pair. It makes no paid model calls. The recordings are
synthetic harness controls, **not model-comparison evidence**.

The agent-authored grading decisions below are **practice simulations**, not
human confirmation. They create no HUMAN MLflow assessments. A person must
independently inspect and confirm judgments before claiming human-adjudicated
quality. Fixture annotations remain provisional regardless of review grading.

## Demonstrated artifacts

- [Comparison report](../runs/adjudication-demo-comparison/report.md)
- [Practice-scored recorded run](../runs/adjudication-demo-recorded/report.md)
- [Unadjudicated recorded run](../runs/adjudication-demo-pending-pair/report.md)

Both selected runs completed 2/2 cases through Harbor/Docker. Practice decisions
produce recall **1/1**, distinct-finding precision **1/2**, no corrected-case false
alarms, and case coverage **2/2**. The unadjudicated run has **one pending defect,
zero confirmed misses**, and case coverage **0/2**. Its recall bounds are 0/1–1/1;
it must not be ranked below the practice run. Cost telemetry is unknown, not zero;
recorded latency measures submission rather than original inference.

Each case links to the review, request/code, private reference, form and exported
trace. Native Harbor trial logs/results remain in each run's `harbor/` directory.
The verifier's `artifact_present` mean of 1 is **not** a quality score.

## Commands

From `code-review-eval/`, with Docker/Compose running:

```sh
uv sync --locked
uv run python validate_fixtures.py examples/* fixtures/*
uv run python -m unittest discover -s tests -v

uv run python run_eval.py run fixtures/case-0004 fixtures/case-0005 \
  --recorded recorded_reviews/smoke --output runs/adjudication-demo-recorded
uv run python run_eval.py run fixtures/case-0004 fixtures/case-0005 \
  --recorded recorded_reviews/smoke --output runs/adjudication-demo-pending-pair
```

The demonstrated directories already exist; execution and comparison intentionally
refuse to overwrite them. Use fresh run/comparison names to repeat the walkthrough.
The first run originally used `fixtures/*` when that glob contained only this pair.
A later wildcard attempt picked up concurrently added fixtures and was interrupted;
`adjudication-demo-pending/` is **not** part of this comparison. Use the explicit
pair above: the recordings only cover these two cases.

The demonstration exercised save/resume through the actual CLI, not by editing
judgment JSON. It saved the first judgment, quit before the second finding, then
resumed and kept the prior judgment. The exact practice input/transcripts are:

- [First input](../runs/adjudication-demo-recorded/practice-start.txt) /
  [transcript](../runs/adjudication-demo-recorded/practice-start.log)
- [Resume input](../runs/adjudication-demo-recorded/practice-resume.txt) /
  [transcript](../runs/adjudication-demo-recorded/practice-resume.log)

```sh
uv run python run_eval.py grade runs/adjudication-demo-recorded --practice \
  < runs/adjudication-demo-recorded/practice-start.txt \
  > runs/adjudication-demo-recorded/practice-start.log 2>&1
uv run python run_eval.py grade runs/adjudication-demo-recorded --practice \
  < runs/adjudication-demo-recorded/practice-resume.txt \
  > runs/adjudication-demo-recorded/practice-resume.log 2>&1
uv run python run_eval.py adjudicate runs/adjudication-demo-recorded
uv run python run_eval.py adjudicate runs/adjudication-demo-recorded
uv run python run_eval.py compare \
  runs/adjudication-demo-recorded runs/adjudication-demo-pending-pair \
  --output runs/adjudication-demo-comparison
```

Re-importing produced the same judgments and scores. Neither practice import logs
HUMAN feedback. For an independent practice replay without these input files,
run `grade --practice` interactively and make these explicit simulation decisions:

1. `case-0004`: classify `f-001` as valid and match `finding-01`, explaining the
   existing-value/append collision and first-value consumer. Classify `f-002`
   invalid, explaining that `keep_blank_values=True` contradicts its blanket
   allegation. Record context handling and instruction handling with reasons.
2. `case-0005`: explicitly acknowledge inspection of the empty review, with a
   reason. Record behavior verdicts with reasons. Empty is not automatic approval.
3. Type `PRACTICE` at each confirmation. Do not claim these decisions are human.

These are recorded walkthrough decisions, not a keyword matcher or automatic
judge. Other valid novel findings would need independent semantic adjudication.
Expectations were not changed to obtain these scores.

## Actual human workflow

Use the untouched pending pair in an interactive terminal:

```sh
uv run python run_eval.py grade runs/adjudication-demo-pending-pair
uv run python run_eval.py adjudicate runs/adjudication-demo-pending-pair
uv run python run_eval.py compare \
  runs/adjudication-demo-recorded runs/adjudication-demo-pending-pair \
  --output runs/after-human-grading
```

A person reads the displayed review, private rubric and code, supplies their own
judgments/reasons, and types `HUMAN` only to confirm their own decisions. This
step was deliberately **not performed by the agent**. The CLI requires a terminal
in human mode; scripts must use `--practice`. See [runner usage](runner.md) for
metric denominators, binding checks, legacy-form migration and limitations.

## Validation performed

The initial required checks passed: 5 fixtures and 82 tests (7 optional notebook
checks skipped). Concurrent work added corpus/explorer tests during this task.
The final full check, including the optional notebook group, passed **15 fixtures
and 127 tests**, with no skips:

```sh
uv sync --locked --group demo
uv run --locked --group demo python validate_fixtures.py examples/* fixtures/*
uv run --locked --group demo python -m unittest discover -s tests -v
git diff --check
```

The new adjudication suite contains 22 tests; existing runner tests also cover
real MLflow import idempotence/revisions and explicit synthetic confirmations in
isolated temporary test stores. No test confirmation is approval of these runs.
Live readback of the four demonstrated MLflow traces found **12 expected spans
and zero assessments**. Exact retained recording bytes and unchanged private
reference bytes were checked against their source artifacts. No paid models,
fixture expectation changes, commits or pushes were made by this task.
