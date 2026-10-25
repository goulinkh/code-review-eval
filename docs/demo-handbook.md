# Demo extension handbook

Use this guide when adding fixtures, views, or checks to the marimo demo.
Keep the notebook focused on exploration; explanations belong here or in the
project docs. Commands below run from `code-review-eval/`.

## Where changes belong

| Change | Location |
|---|---|
| Controls, tabs, labels, and display wiring | [`demo.py`](../demo.py) |
| Snapshot reads, file inventory, diff rendering, and scoped styles | [`demo_support/explorer.py`](../demo_support/explorer.py) |
| Marimo-specific display helpers | [`demo_support/rendering.py`](../demo_support/rendering.py) |
| Notebook behavior and opt-in checks | [`tests/test_demo.py`](../tests/test_demo.py) |
| Pure-Python diff and integrity tests | [`tests/test_fixture_explorer.py`](../tests/test_fixture_explorer.py) |
| Trusted executable author checks | [`reference_checks/`](../reference_checks/) |
| Demo dependencies and default dark theme | [`pyproject.toml`](../pyproject.toml) |
| Fixture authoring rules | [Fixture format](fixture-format.md) and [`schemas/`](../schemas/) |

## Keep the default view small

Show the selected fixture, file, and diff first. Put long requests and source
in tabs; put budgets, provenance, and background in collapsed panels. Use short
labels instead of numbered presentation sections. Keep the notebook usable in
dark mode, with both diff layouts and full context.

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
   `tests/test_demo.py` currently expects five fixtures; the default selection
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

Keep notebook-only helpers in `demo_support/`, not in the evaluator modules.
`demo.py` contains the notebook cells and reactive wiring. Put snapshot and diff
logic in `demo_support/explorer.py`, without a marimo dependency, and UI helpers
in `demo_support/rendering.py`. Reuse `read_snapshot_text()` for hash-checked
snapshot reads and `source_block()` for escaped source display. Escape filenames
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

For a future results panel, use retained evaluation artifacts rather than
invoking a reviewer during notebook startup. Keep synthetic
recordings, contract probes, and actual reviewer results clearly labelled.
Preserve pending human adjudication, unsupported cases, unknown telemetry, and
provisional reference labels. Inspect raw output for sensitive text before
showing it. Run artifacts and private references remain evaluator-only.

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
