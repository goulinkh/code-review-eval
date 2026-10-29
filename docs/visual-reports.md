# Visualization report format 1.0.0

`visuals.json` is an evaluator-only, chart-friendly secondary report. It is emitted
beside `report.md` and `report.json` by `run`, `adjudicate`, and `compare`. It
projects existing judgments; it does not grade findings, alter expectations,
create MLflow assessments, or supply a model ranking. Fixture contracts are
unchanged. The closed [JSON Schema](../schemas/visual-report.schema.json) uses
Draft 2020-12; unsupported versions fail rather than being silently converted.

## Use in the notebook

```sh
uv sync --locked --group demo
# Backfill the retained demonstration; no Docker, models or MLflow access.
uv run python run_eval.py export-visuals \
  runs/adjudication-demo-recorded runs/adjudication-demo-pending-pair \
  --output runs/adjudication-demo-comparison
uv run --locked --group demo marimo run demo.py
```

Use **Model comparison** at the top of the notebook. The report dropdown lists
real experiment comparisons before generic run sidecars. Choose the desired
`visuals.json` and enable **Load selected report**. For the simulated grading demo,
select `runs/adjudication-demo-comparison/visuals.json` explicitly rather than
mistaking it for a live-model experiment.

Separate tabs display quality with uncertainty intervals, execution statuses,
latency, cost, underlying tables/evidence paths, and raw `visuals.json`. Sibling
`report.md` and `report.json` appear in their own tabs when present; missing
primary reports do not prevent viewing the sidecar. Reports cover the selected
bundle, independently of the fixture dropdown. Rows remain in input-run order,
not score order. No charting dependency or network is required.
The notebook reads no result files until enabled and never follows evidence
links to load private references. It confines selected files, including symlink
targets, to this project. It displays an error for missing/invalid reports.

The [demonstrated tables](../runs/adjudication-demo-comparison/visuals.json) contain
two recorded runs, four cases and 112 metric rows. Practice judgments are visibly
labelled **SIMULATION**, not human approval. Pending defects remain distinct from
confirmed misses. The [static chart preview](../runs/adjudication-demo-comparison/visual-preview.html)
shows the same offline SVG renderers used by the notebook.

`export-visuals` accepts one or more compatible **run directories** and writes
only `<output>/visuals.json`; the output directory may already exist. It validates
retained bindings and refuses unimported approved judgments. It neither changes
forms nor logs assessments. It can refresh/backfill old artifacts without
rerunning Harbor or contacting MLflow. It refreshes only the sidecar: to refresh
both a comparison's primary reports and its tables after grading, use `compare`
with a fresh output directory.

## Real pilot model comparisons

The same notebook can load the existing `experiments/*/comparison.json` format.
This is the pilot summarizer's model-level report, not a `visuals.json` sidecar
and not a new fixture contract. The **Models** tab shows finished/attempted
invocations, valid review delivery, failures, median latency, known billing,
usage, and available adjudicated quality. **Repetitions** preserves case-level
variation; **comparison.md** displays the main report. Models stay in source
order, without an inferred ranking.

The dropdown selects a real pilot by default when one exists, but reads no
results until explicitly enabled. **Reload saved report** only rereads retained
files; it cannot make a stale summary current by itself. Refresh this pilot from
existing run artifacts with:

```sh
uv run python experiments/openrouter-pilot-20261025T221002Z/summarize.py
```

Then reload it in the notebook. This does not rerun models or approve judgments.
The summary can legitimately remain incomplete while invocations are still
running. Pending recall/precision are displayed as **Pending**, not zero; unknown
cost/token usage is not treated as free. The pilot covers its selected fixture
pair, not every fixture subsequently added to the corpus.

## Three tidy tables

The envelope contains `format: "code-review-eval.visuals"`, `schema_version`,
`grading_version`, `evaluator_only: true`, `ranking: null`, interpretation `notes`,
and three arrays of flat rows:

| Table | Key | Contents |
|---|---|---|
| `runs` | `run_key` | Name, agent, model, MLflow run ID, quality basis, pending cases, expected/reported case counts, completion flag, report URI |
| `cases` | `(run_key, case_id)` | Revision, execution/adjudication/annotation status, approval source, input/reference/review/imported-adjudication hashes, trace ID, evidence URIs |
| `metrics` | `(run_key, case_id, domain, metric)` | Numeric value, unit, ratio counts, uncertainty bounds, known/total telemetry coverage |

`run_key` is a bundle-local join key (`run-001`, etc.), not a rank or a global ID.
Use `mlflow_run_id` for the native run identity. A metric's `case_id: null` denotes
an aggregate run metric; non-null rows describe an individual case. Join tables
on their keys rather than parsing names or review text. Evidence URIs are URL-
escaped and relative to the sidecar's directory. Relocate it with the run tree
if those links need to keep working. They are data, not executable commands.

Every metric has the same columns:

```json
{
  "run_key": "run-002", "case_id": null,
  "domain": "quality", "metric": "defect_recall", "unit": "ratio",
  "value": 0.0, "numerator": 0, "denominator": 1,
  "lower": 0.0, "upper": 1.0, "known_count": null, "total_count": null
}
```

This example means recall is **pending over 0–100%**, not a confirmed miss.

### Metric names and interpretation

- **Quality ratios:** `defect_recall`, `finding_precision`, `finding_coverage`,
  `case_coverage`, `corrected_false_alarm_rate`. Run recall/precision include
  `lower`/`upper` bounds. Case-level coverage is `adjudication_coverage`.
- **Quality counts:** `matched_defects`, `confirmed_misses`, `pending_defects`,
  `pending_cases`, `valid_novel_findings`, `valid_findings`, `invalid_findings`,
  `duplicate_findings`, `unresolved_findings`, `corrected_false_alarm_findings`,
  `corrected_pending_cases`, `corrected_valid_novel_findings`. Corrected-case
  counts/ratios are run-level; novel valid findings are not false alarms.
- **Execution:** `completion`, `delivery_recall_lower_bound`, `completed`,
  `failed`, `timed_out`, `invalid_output`, `unreported_cases`,
  `unavailable_defects`, `corrected_unavailable_cases`. Execution-unavailable
  defects do not appear as human-confirmed quality misses. In-progress exports
  explicitly report expected versus reported cases and `complete: false`;
  aggregate ratios at that point cover only observed results.
- **Latency:** `mean_ms` per run and `agent_ms` per case, unit `ms`.
- **Cost:** `known_total_usd` per run and `usd` per case, unit `USD`. A known
  subtotal with partial telemetry is **not** the run's complete cost.

Units are `ratio` (0–1), `count`, `ms`, or `USD`. Ratios retain integer numerator
and denominator. A zero denominator yields `value: null` (N/A), never a perfect
score. Counts/telemetry use null ratio fields. Unknown telemetry stays `null`,
not zero; `known_count` / `total_count` records how much was measured. Bounds
are null when not provided, not an implicit zero-width confidence interval.
These are adjudication uncertainty bounds, not statistical confidence intervals.

Quality, execution reliability, latency, and cost are never merged into one
score. Recorded latency measures submission rather than original inference.
`approval_source` stays `human`, `simulation`, or null; the export cannot turn a
practice judgment into human approval. Annotation status remains independent.
The export deliberately omits review prose, code, private explanations, operator
identifiers, reasons, and raw exceptions. Counts/statuses still contain private
evaluation information: neither notebook nor export is reviewer input.

## Other consumers

These arrays can be passed directly to a dataframe/chart library, without
scraping Markdown or flattening nested metric objects:

```python
import json
import pandas as pd  # optional consumer, not a new evaluator dependency

bundle = json.loads(open("runs/comparison/visuals.json").read())
runs = pd.DataFrame(bundle["runs"])
metrics = pd.DataFrame(bundle["metrics"])
recall = metrics.query("case_id.isna() and domain == 'quality' and metric == 'defect_recall'")
recall = recall.merge(runs, on="run_key", validate="many_to_one")
# Plot value with lower/upper; show quality_basis and pending_cases prominently.
# Never replace missing telemetry with zero or rank pending/simulated results.
```

Use `demo_support.results.load_visuals()` for schema, ratio, join-key, finite
number, and coverage checks before displaying an artifact in this repository.
The export is a retained snapshot; it is not a live connection to the latest
forms or MLflow backend. See [runner usage](runner.md) for grading denominators.
