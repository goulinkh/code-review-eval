# Code review evaluation

A standalone Git repository with versioned fixtures and a thin benchmark layer
on [Harbor](https://github.com/harbor-framework/harbor). Harbor runs Pi, OpenCode,
and future custom agents in sandboxed environments. This layer exports tasks,
captures MLflow lifecycle traces, retains reviews, and produces per-case reports.
Finding quality is human-adjudicated; no model judge is included.

## Standards first

- **JSON Schema Draft 2020-12** validates the fixture documents.
- **Harbor ATIF-v1.7** represents continuation conversations, real tool calls,
  and associated observations. We define a deliberately restricted text-only
  profile, not a new conversation format.
- Snapshot manifests, remaining-budget accounting, and semantic review labels
  are benchmark-specific extensions. These are **not Harbor tasks**.

See [the format](docs/fixture-format.md),
[the standards index](docs/standards.md), and
[the standards comparison and pinned sources](docs/standards/fixture-interoperability.md).
Agents should start with [AGENTS.md](AGENTS.md) for task-specific loading and validation.

## Validate

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/). Evaluation runs also
require Docker with Compose; fixture validation and unit tests do not.

```sh
uv sync --locked
uv run python validate_fixtures.py examples/* fixtures/*
uv run python -m unittest discover -s tests -v
```

Alternatively install the dependency from `pyproject.toml` in your own virtual
environment and run the same Python commands without `uv run`.

## Run an evaluation

```sh
uv run python run_eval.py run fixtures/* \
  --recorded recorded_reviews/smoke --output runs/recorded-smoke
```

Open `runs/recorded-smoke/report.md`; quality remains pending until a human edits
its per-case `adjudication.json` forms and runs:

```sh
uv run python run_eval.py adjudicate runs/recorded-smoke
uv run mlflow ui --backend-store-uri "sqlite:///$(pwd)/mlflow.db"
```

Use `--agent pi --model provider/model` or `--agent opencode --model provider/model`
for Harbor's built-in integrations, or `--agent my_module:MyAgent` for a custom
Harbor agent. See [runner usage](docs/runner.md) for human matching, retained
artifacts, and capability/budget limitations. Only fresh fixed-context fixtures
are exported; native agents retain their tools, so this is not a controlled
no-tools baseline.

## Team demo (marimo)

The evaluator-only [`demo.py`](demo.py) notebook provides an interactive,
offline walkthrough and visual fixture explorer. Choose a case and file to
browse line-numbered **side-by-side or unified diffs**, with additions,
deletions, and character-level changes highlighted. Toggle full context, inspect
the base/head source, or switch tabs to the supplied patch, initial reviewer
context, access manifest, and raw request. The reconstructed snapshot view is
evaluator-only; it does not enlarge the reviewer's allowed context.

From this repository's root (`code-review-eval/`):

```sh
uv sync --locked --group demo
uv run --locked --group demo marimo run demo.py
```

Use `marimo edit demo.py` instead of `marimo run demo.py` to edit the
notebook. Marimo is optional; core validation needs only the normal dependencies.
After setup, no model, API key, live service, or network access is needed.
For future additions, see the [demo extension handbook](docs/demo-handbook.md).

Suggested five-minute presentation:

1. Explain the `reviewer/`, `environment/`, and `private/` boundary.
2. Inspect the default `fixtures/case-0004` request and visual file diff.
   Try both diff layouts and the reviewer-context tabs. Ask the team what finding
   they would report before revealing the reference.
3. Reveal the private rubric, then run the trusted defect/fix pair: the existing
   author checker reports **8/14** probes passed for `case-0004` and **14/14**
   for `case-0005`. These are contract probes, not reviewer/model scores.
4. Select `examples/case-0003` and inspect the historical ATIF prefix and
   inherited/remaining budgets. Historical commands are displayed, never replayed.
5. Validate all five artifacts together and close with the pending work:
   independent annotation/licensing review, a frozen corpus, an isolated
   tool-enabled runner, and broader evaluation coverage.

Snapshot execution is opt-in and restricted to the existing two trusted authored
cases; it is not sandboxed. Structural validation does not execute snapshots.
The notebook and any exports are evaluator-only presentation material, **never
reviewer context**. Labels remain provisional; this is one authored pair, not
broad corpus coverage or an independently verified clean dataset.

Notebook checks and a static export of the default view:

```sh
uv run --locked --group demo marimo check --strict demo.py
uv run --locked --group demo python -m unittest discover -s tests -v
uv run --locked --group demo marimo export html demo.py --no-include-code -o /tmp/code-review-eval-demo.html
```

The HTML export is a noninteractive fallback: it shows the default view, without
revealed labels or probe/validation results. Run the live notebook to switch
cases, files, diff layouts, and full context. Notebook tests are skipped when
marimo is not installed; the pure-Python diff renderer is tested with core dependencies.

## Layout and trust boundary

```text
schemas/                      # versioned contracts; resolved offline
examples/<neutral-case-id>/
fixtures/<neutral-case-id>/    # same per-case layout
  reviewer/input.json         # ONLY reviewer-visible request data
  reviewer/prefix.json        # ATIF historical input; continuation only
  environment/blobs/<sha256>  # runner-owned UTF-8 snapshot content
  private/expectations.json   # labels, provenance, partitions, grading rubric
```

**Never expose the whole fixture directory to a reviewer.** Fixed-context
adapters receive the reviewer documents and inline initial context only.
A future tool-enabled integration must serve declared whole-file reads through
an enforced boundary. The current layer exports only public input into native
Harbor tasks; Harbor owns Docker isolation. Never mount the original fixture
checkout or evaluator output into an agent environment.

The three examples show a fresh defective/corrected pair and a continuation
of the defective case after a completed file read. They are format examples,
not an independently reviewed or frozen evaluation corpus. Category labels,
case relationships, expected paths, and reproducer outcomes stay private.

The independent Python query-override pair lives in `fixtures/case-0004`
(defective) and `case-0005` (corrected), with private labels and provenance.
Run `uv run python -m reference_checks.query_overrides <case-id>`: `case-0004`
exits 1 (six failing probes); `case-0005` exits 0 (14/14 pass).
[Raw blinded preflight records](reviews/query-overrides/round-01/manifest.json)
remain evaluator-only; independent annotation and licensing approval are pending.

The design follows the parent project's
[`code-review-eval-scope.md`](../code-review-eval-scope.md) and
[`code-review-eval-categories.md`](../code-review-eval-categories.md).
The repository remains usable independently; those documents are design
inputs, not runtime dependencies.

No production reviewer or live code-hosting write integration is configured.
Model calls are opt-in; the recorded Harbor agent runs without model access.
