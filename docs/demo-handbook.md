# Demo extension handbook

Use this guide when adding fixtures, views, or checks to the marimo demo.
Keep the notebook focused on exploration; explanations belong here or in the
project docs. Commands below run from `code-review-eval/`.

## Where changes belong

| Change | Location |
|---|---|
| Controls, tabs, labels, and display wiring | [`demo.py`](../demo.py) |
| Snapshot reads, file inventory, diff rendering, and scoped styles | [`demo_support/explorer.py`](../demo_support/explorer.py) |
| Shared syntax highlighting and light/dark palettes | [`demo_support/syntax.py`](../demo_support/syntax.py) |
| Nested snapshot tree, viewer layout, and active-file styling | [`demo_support/file_tree.py`](../demo_support/file_tree.py) |
| Marimo-specific display helpers | [`demo_support/rendering.py`](../demo_support/rendering.py) |
| Retained result loading and SVG charts | [`demo_support/results.py`](../demo_support/results.py) |
| Visualization export contract | [Visualization reports](visual-reports.md) and [`../visual_reporting.py`](../visual_reporting.py) |
| Notebook behavior and opt-in checks | [`tests/test_demo.py`](../tests/test_demo.py) |
| Tree hierarchy, selection callbacks, and escaped names | [`tests/test_file_tree.py`](../tests/test_file_tree.py) |
| Pure-Python diff and integrity tests | [`tests/test_fixture_explorer.py`](../tests/test_fixture_explorer.py) |
| Trusted executable author checks | [`reference_checks/`](../reference_checks/) |
| Demo dependencies and default dark theme | [`pyproject.toml`](../pyproject.toml) |
| Fixture authoring rules | [Fixture format](fixture-format.md) and [`schemas/`](../schemas/) |

## Keep the default view small

Put the model-comparison selector before the fixture explorer. After explicit
loading, show the real pilot's per-model summary first; keep raw reports and
repetition detail in tabs. Put long fixture requests and source in tabs, with
budgets, provenance, and background in collapsed panels. Use short labels and
keep the notebook usable in dark mode, with both diff layouts and full context. Long code lines wrap within
their diff column without changing source line numbers. Nest the collapsible file
tree immediately beside the viewer, not in a notebook-wide sidebar. Use the
notebook's neutral theme colors for filenames, status badges, and selection.
The tree uses only the snapshot inventory, never the local filesystem.

Opening the notebook or changing a selection should not launch a model, execute
snapshot code, write artifacts, or load private labels. Require an explicit
control for those actions. Preserve the offline default.

This is an **evaluator-only** explorer. Snapshot browsing may show more than a
reviewer is allowed to retrieve. Neither a hidden panel nor a directory named
`private/` provides isolation; never supply the notebook, exports, handbook,
or an entire fixture directory to a reviewer.

## Add a fixture

1. Follow the [fixture format](fixture-format.md), relevant
   [schemas](../schemas/), and [interoperability rules](standards/fixture-interoperability.md).
   Use `examples/` for format illustrations and `fixtures/` for authored cases,
   with neutral `case-NNNN` identifiers.
2. Supply `reviewer/input.json`, private expectations, and content-addressed
   snapshot blobs. Add `reviewer/prefix.json` only for a continuation. Generate
   the canonical patch with `generated_diff()` in `validate_fixtures.py` and
   bind hashes to exact artifact bytes. Follow the contract's revision rules;
   do not silently change an immutable case or its labels.
3. Validate related cases together, then open the explorer. It discovers
   `*/reviewer/input.json` under both collections automatically; no registration
   list is needed. File options come from the selected snapshot inventories.
4. Update count-dependent tests and prose when the collection changes.
   Fixture tests discover the current inventory; the default fixture selection
   is `fixtures/case-0004`. Keep provisional labels and related scenarios
   distinct from independently verified corpus coverage.

Discovery grants no execution permission. Adding a fixture must not add it to
an executable checker automatically. Checkpoints are displayed, never replayed.

## Add a view or control

Edit with:

```sh
uv sync --locked --group demo
uv run --locked --group demo marimo edit demo.py
```

Prefer another entry in the existing `mo.ui.tabs` or `mo.accordion` mapping over
a new always-visible section. For example, a public snapshot-ID tab can use:

```python
"Snapshot IDs": source_block(json.dumps(
    {side: snapshot["id"] for side, snapshot in public["snapshots"].items()},
    indent=2,
)),
```

Keep marimo's reactive wiring explicit: define each exported name in one cell,
accept dependencies as cell arguments, and return names used downstream. Use
`_`-prefixed names for cell-local intermediates. Create a widget in one cell
and read its `.value` in a dependent cell.

Tree leaf buttons share `mo.state` for the selected path. Recreate that state
when the fixture inventory changes, defaulting to its first (changed-first)
entry. Keep tree construction and diff controls independent of the selected
path; update the active-row style separately. `file_tree_layout()` nests the
existing tree control and viewer without cloning the buttons. Do not replace
the virtual tree with `mo.ui.file_browser`, which would
browse evaluator-owned files rather than snapshot paths.

Keep notebook-only helpers in `demo_support/`, not in the evaluator modules.
`demo.py` contains the notebook cells and reactive wiring. Put snapshot and diff
logic in `demo_support/explorer.py`, without a marimo dependency, and UI helpers
in `demo_support/rendering.py`. Reuse `read_snapshot_text()` for hash-checked
snapshot reads and `source_block(content, path=...)` for escaped, syntax-highlighted
source display. For structured text without a filename, pass `language="json"`
or `language="diff"`; unknown filenames fall back to plain text. Escape filenames
as well as content in new HTML. Preserve these distinctions:

- An absent file (`None`) versus a present empty file (`""`).
- Added, deleted, modified, and unchanged files.
- The reviewer-supplied patch versus a reconstructed snapshot diff.
- An unavailable patch versus an available but empty patch.
- Unknown usage versus zero usage; uncapped limits versus finite limits.

Load private expectations only after the reference-label control is enabled.
Do not mix labels, provenance, or grading hints into reviewer-facing views.

## Add checks or evaluation results

Keep executable checks behind a run button, with a short description of what
will execute. The current pair checker accepts only trusted `case-0004` and
`case-0005` snapshots after validation. Do not turn it into an executor for the
fixture dropdown. Add a separate trusted checker and tests for a new family;
report parse/runtime failures as errors, not reproduced defects.

The **Model comparison** section at the top discovers retained reports without
reading their contents. It lists `experiments/*/comparison.json` before run
`visuals.json` sidecars. Enable **Load selected report** to read the chosen
artifact; **Reload saved report** rereads it without executing anything.

Pilot comparisons show the existing model-level execution, latency, billing,
usage, and quality summary, with repetition detail and sibling `comparison.md`.
The default is a real pilot when available, not the simulated grading demo.
Pending quality remains pending. The loader does not create a winner or grade
findings. Regenerate stale experiment summaries separately from saved run data.

Generic sidecars retain their charts and sibling `report.md` / `report.json` tabs.
Reports cover the chosen bundle, not the fixture dropdown. See [the formats and
refresh commands](visual-reports.md). Keep evaluator transforms in
`visual_reporting.py` and notebook-only discovery/loading/presentation in
`demo_support/results.py`. Neither view should invoke a reviewer, create
judgments, contact MLflow, or follow links into private references.

Keep synthetic recordings, contract probes, and actual reviewer results clearly
labelled. Charts must retain pending uncertainty, execution-unavailable defects,
simulation sources, and unknown telemetry. Never sort into a model ranking or
fill missing cost with zero. Display domains separately, escape all labels,
and preserve the no-result-reads default. Run artifacts remain evaluator-only.

Adding a display panel does not add execution support or create a sandbox.
Keep unsupported protocols explicit rather than silently starting fresh or
replaying historical calls.

## Validate and preview

```sh
uv sync --locked --group demo
uv run --locked --group demo python validate_fixtures.py examples/* fixtures/*
uv run --locked --group demo python -m unittest discover -s tests -v
uv run --locked --group demo marimo check --strict demo.py
uv run --locked --group demo marimo export html demo.py --no-include-code --force -o /tmp/code-review-eval-demo.html
```

Add pure renderer tests for diff changes and headless `app.run()` tests for
notebook behavior. Cover the initial view, changed selections, and explicit
opt-ins. When overriding definitions with `app.run(defs=...)`, supply **all**
exported names from each overridden cell; existing tests show this pattern.
Notebook tests skip without marimo, so use the `demo` dependency group to run
them. Core diff tests do not need marimo.

For live preview, stop any server already using the port, then run:

```sh
uv run --locked --group demo marimo run demo.py --headless --watch --host 127.0.0.1 --port 2718
```

Open <http://localhost:2718>. Check every fixture, both diff layouts, full
context, reference-label reveal, and continuation history. Confirm that the
default view stays compact and performs no snapshot execution or private-label
reads. Test added/deleted, empty, and unchanged files when changing the renderer.
The static export has no Python backend; use the live notebook to test reactive
controls. Treat both live and exported views as evaluator-only.
