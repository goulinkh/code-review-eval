"""Team demo: evaluator-only fixture walkthrough, not a reviewer or sandbox."""

import marimo

__generated_with = "0.25.2"
app = marimo.App(
    width="full",
    app_title="Code review evaluation · model comparisons",
    css_file="demo_support/file_tree.css",
)


@app.cell
def _():
    import json

    import marimo as mo

    import validate_fixtures as fixture_validator
    from demo_support.explorer import file_inventory, line_counts, read_snapshot_text, render_diff
    from demo_support.file_tree import (
        file_tree as build_file_tree,
        file_tree_layout,
        file_tree_selection_style,
    )
    from demo_support.rendering import source_block
    from reference_checks.query_overrides import CASE_IDS, PROBES, check_contract, load_builder

    # Anchor reads to this project, not the shell's working directory.
    root = fixture_validator.SCHEMAS.resolve().parent

    return (
        CASE_IDS,
        PROBES,
        build_file_tree,
        check_contract,
        file_inventory,
        file_tree_layout,
        file_tree_selection_style,
        fixture_validator,
        json,
        line_counts,
        load_builder,
        mo,
        read_snapshot_text,
        render_diff,
        root,
        source_block,
    )


@app.cell
def _(mo):
    mo.md(r"""
    # Code review evaluation

    Compare saved model results below, then explore their fixtures. Evaluator-only; never share with a reviewer.
    """)
    return


@app.cell
def _(mo, root):
    from demo_support.results import discover_reports as _discover_reports

    _reports = _discover_reports(root)
    _options = _reports or ["runs/adjudication-demo-comparison/visuals.json"]
    report_selector = mo.ui.dropdown(
        options=_options,
        value=next((_path for _path in _options if "/openrouter-sweep-" in _path), _options[0]),
        allow_select_none=False,
        label="Saved comparison or run · full-fixture sweep first", full_width=True,
    )
    return (report_selector,)


@app.cell
def _(mo):
    refresh_results = mo.ui.refresh(
        options=["10s", "30s"], default_interval="10s", label="Reload saved report",
    )
    return (refresh_results,)


@app.cell
def _(mo, refresh_results, report_selector):
    results_path = mo.ui.text(
        value=report_selector.value, label="Report path (project-relative)", full_width=True,
    )
    load_results = mo.ui.checkbox(label="Load selected report", value=False)
    mo.vstack([
        mo.md("## Model comparison"),
        report_selector,
        mo.hstack([load_results, refresh_results], justify="start", align="center"),
        mo.accordion({"Advanced: report path": results_path}),
        mo.md(
            "Full-fixture model sweeps are selected before older pilots and demonstrations. Enable loading to see "
            "the selected comparison. While loaded, results refresh every 10 seconds. Refresh reads saved results only; it does not run models, "
            "grade reviews, regenerate reports, or contact MLflow. Evaluator-only."
        ),
    ])
    return load_results, results_path


@app.cell
def _(load_results, mo, refresh_results, results_path, root):
    comparison_chart_view = None
    _refresh = refresh_results.value
    if load_results.value and results_path.value.rsplit("/", 1)[-1] == "comparison.json":
        from demo_support.comparison_chart import load_chart_data as _chart_data, model_line_chart as _line_chart
        from validate_fixtures import FixtureError as _ChartError

        try:
            _data = _chart_data(results_path.value, root)
            comparison_chart_view = mo.vstack([
                mo.md("### Models side by side · one line per model"),
                mo.ui.tabs({
                    "Agent latency": mo.Html(_line_chart(_data, "latency")),
                    "Review delivery": mo.Html(_line_chart(_data, "delivery")),
                }),
                mo.md("Hover over a point for its value. Colors identify models across both charts. "
                      "These show execution results, not pending review-quality scores."),
            ])
        except (OSError, ValueError, _ChartError) as _error:
            comparison_chart_view = mo.callout(
                mo.plain_text("Saved comparison chart unavailable: " + str(_error)), kind="warn",
            )
    comparison_chart_view
    return (comparison_chart_view,)


@app.cell
def _(json, load_results, mo, refresh_results, results_path, root, source_block):
    visual_results = None
    pilot_comparison = None
    results_error = None
    results_view = None
    _refresh = refresh_results.value
    if load_results.value:
        from demo_support.results import (
            load_pilot_comparison as _load_pilot,
            load_report_text as _load_report,
            load_visuals as _load_visuals,
            pilot_model_rows as _model_rows,
            pilot_repetition_rows as _repetition_rows,
            result_views as _result_views,
        )
        from validate_fixtures import FixtureError as _FixtureError

        try:
            _pilot = results_path.value.rsplit("/", 1)[-1] == "comparison.json"
            if _pilot:
                pilot_comparison = _load_pilot(results_path.value, root)
                _models = pilot_comparison["models"]
                _finished = sum(_model["finished"] for _model in _models)
                _completed = sum(_model["execution_counts"].get("completed", 0) for _model in _models)
                _planned = pilot_comparison["planned_invocations"]
                _pending = any(_model["quality"]["status"] != "adjudicated" for _model in _models)
                _known_cost = sum(_model["known_billed_cost_usd"] for _model in _models)
                _message = (
                    "Review quality is pending human adjudication; no winning model can be declared."
                    if _pending else
                    "Adjudicated results for this small pilot only, not a general model ranking."
                )
                if _finished < _planned:
                    _message += (
                        f" This saved snapshot has {_finished}/{_planned} finished invocations. "
                        "Other attempts may still be running or the summary may need refreshing."
                    )
                _tabs = {
                    "Models": mo.vstack([
                        mo.hstack([
                            mo.stat(str(len(_models)), label="Models", bordered=True),
                            mo.stat(f"{_finished}/{_planned}", label="Finished / planned", bordered=True),
                            mo.stat(str(_completed), label="Completed reviews (not quality)", bordered=True),
                            mo.stat(f"${_known_cost:.6f}", label="Known billed subtotal", bordered=True),
                        ], widths="equal"),
                        mo.callout(_message, kind="warn"),
                        mo.ui.table(_model_rows(pilot_comparison), selection=None,
                                    pagination=False, show_download=False),
                    ]),
                    "Repetitions": mo.ui.table(
                        _repetition_rows(pilot_comparison), selection=None, show_download=False,
                    ),
                    "comparison.json": source_block(
                        json.dumps(pilot_comparison, indent=2), language="json",
                    ),
                }
                _report_names = ("comparison.md",)
                _notes = (
                    "This is the retained OpenRouter/Pi pilot comparison, grouped by model. "
                    "Quality requires human adjudication; pending values are not zero scores. "
                    "Failures are not clean reviews, and unknown usage or cost is not free. "
                    "Reload rereads this snapshot. To regenerate it from saved run results, "
                    "run the experiment's summarize.py separately; no model calls are needed."
                )
            else:
                visual_results = _load_visuals(results_path.value, root)
                _tabs = {_name: mo.Html(_html) for _name, _html in _result_views(visual_results).items()}
                _tabs.update({
                    "Runs": mo.ui.table(visual_results["runs"], selection=None, show_download=False),
                    "Cases / evidence": mo.ui.table(visual_results["cases"], selection=None, show_download=False),
                    "Metric tables": mo.ui.table(visual_results["metrics"], selection=None, show_download=False),
                    "visuals.json": source_block(json.dumps(visual_results, indent=2), language="json"),
                })
                _incomplete = any(not _run["complete"] for _run in visual_results["runs"])
                _message = (
                    "Evaluator-only. Descriptive results, not a model ranking. "
                    "Simulations are NOT human approval; pending judgments are NOT misses. "
                    + ("Execution is incomplete: not every selected case has a report." if _incomplete else "")
                )
                _tabs = {"Interpretation": mo.callout(_message, kind="warn"), **_tabs}
                _report_names = ("report.md", "report.json")
                _notes = visual_results["notes"]
        except (OSError, ValueError, _FixtureError) as _error:
            results_error = str(_error)
            results_view = None
            if results_path.value.rsplit("/", 1)[-1] == "comparison.json":
                try:
                    _saved_report = _load_report(
                        (root / results_path.value).with_name("comparison.md"), root,
                    )
                except (OSError, ValueError, _FixtureError):
                    pass
                else:
                    results_view = mo.vstack([
                        mo.md(_saved_report),
                        mo.accordion({
                            "Optional JSON summary diagnostics": mo.plain_text(results_error),
                        }),
                    ])
            if results_view is None:
                results_view = mo.callout(
                    mo.plain_text("Cannot load evaluation report: " + results_error), kind="warn",
                )
        else:
            for _name in _report_names:
                try:
                    _report_text = _load_report((root / results_path.value).with_name(_name), root)
                except (OSError, ValueError, _FixtureError) as _error:
                    _tabs[_name] = mo.callout(
                        mo.plain_text(f"Cannot load {_name}: {_error}"), kind="warn",
                    )
                else:
                    _tabs[_name] = (
                        mo.md(_report_text) if _name.endswith(".md")
                        else source_block(_report_text, language="json")
                    )
            results_view = mo.vstack([
                mo.ui.tabs(_tabs),
                mo.accordion({"Metric interpretation": mo.plain_text(_notes)}),
            ])
    results_view
    return pilot_comparison, results_error, results_view, visual_results


@app.cell
def _(mo):
    mo.md(r"""
    ## Fixture explorer
    """)
    return


@app.cell
def _(mo, root):
    case_selector = mo.ui.dropdown(
        options=[
            str(_path.parent.parent.relative_to(root))
            for _collection in ("examples", "fixtures")
            for _path in sorted((root / _collection).glob("*/reviewer/input.json"))
        ],
        value="fixtures/case-0004",
        allow_select_none=False,
        label="Fixture",
        full_width=True,
    )
    case_selector
    return (case_selector,)


@app.cell
def _(case_selector, fixture_validator, json, root):
    case_dir = root / case_selector.value
    public = json.loads((case_dir / "reviewer/input.json").read_text(encoding="utf-8"))
    fixture_validator.check_schema("reviewer-input", public)
    return case_dir, public


@app.cell
def _(file_inventory, mo, public):
    inventory = file_inventory(public)
    get_selected_file, set_selected_file = mo.state(inventory[0]["path"] if inventory else None)
    return get_selected_file, inventory, set_selected_file


@app.cell
def _(build_file_tree, inventory, set_selected_file):
    file_tree = build_file_tree(inventory, set_selected_file)
    return (file_tree,)


@app.cell
def _(get_selected_file):
    selected_file = get_selected_file()
    return (selected_file,)


@app.cell
def _(inventory, mo, public):
    diff_layout = mo.ui.radio(
        options=["Side by side", "Unified"], value="Side by side",
        label="View", inline=True,
    )
    full_context = mo.ui.checkbox(label="Full context", value=False)
    mo.vstack([
        mo.hstack([
            mo.stat(public["case_id"], label=f"Revision {public['revision']}", bordered=True),
            mo.stat(public["protocol"]["name"], label="Protocol", bordered=True),
            mo.stat(public["start"]["mode"], label="Start mode", bordered=True),
            mo.stat(str(sum(_item["status"] != "unchanged" for _item in inventory)),
                    label=f"Changed files / {len(inventory)} total", bordered=True),
        ], widths="equal"),
        mo.hstack([diff_layout, full_context], align="center"),
    ])
    return diff_layout, full_context


@app.cell
def _(case_dir, public, read_snapshot_text, selected_file):
    before_text = after_text = None
    if selected_file is not None:
        before_text = read_snapshot_text(case_dir, public, "base", selected_file)
        after_text = read_snapshot_text(case_dir, public, "head", selected_file)
    return after_text, before_text


@app.cell
def _(
    after_text,
    before_text,
    diff_layout,
    file_tree,
    file_tree_layout,
    file_tree_selection_style,
    full_context,
    inventory,
    json,
    line_counts,
    mo,
    public,
    render_diff,
    selected_file,
    source_block,
):
    mo.stop(selected_file is None, mo.md("This fixture has no snapshot files."))
    _added, _removed = line_counts(before_text, after_text)
    _status = next(_item["status"] for _item in inventory if _item["path"] == selected_file)
    _snapshot_view = mo.vstack([
        mo.md(f"**{selected_file}** · {_status} · **+{_added} / −{_removed} lines**"),
        mo.Html(render_diff(
            before_text, after_text, selected_file,
            layout="split" if diff_layout.value == "Side by side" else "unified",
            full_context=full_context.value,
        )),
    ])
    _diff = public["change"]["diff"]
    _supplied_diff = (
        source_block(_diff["artifact"]["content"], language="diff")
        if _diff["status"] == "available" and _diff["artifact"]["content"]
        else mo.md("The supplied diff is available but empty.") if _diff["status"] == "available"
        else mo.md(f"Diff unavailable: {_diff['reason']}")
    )
    _inline = [
        mo.vstack([mo.md(f"**{_entry['path']} · {_entry['snapshot_id']}**"), source_block(_entry["content"], path=_entry["path"])])
        for _entry in public["context_manifest"]
        if _entry["delivery"] == "initial" and _entry["availability"] == "available"
    ]
    _manifest_rows = [
        {"Snapshot": _entry["snapshot_id"], "Path": _entry["path"],
         "Delivery": _entry["delivery"], "Availability": _entry["availability"]}
        for _entry in public["context_manifest"]
    ]
    _tabs = mo.ui.tabs({
        "Changes": _snapshot_view,
        "Request": mo.md(public["change"]["description"]),
        "Base": source_block(before_text, path=selected_file) if before_text is not None else mo.md("File absent from base."),
        "Head": source_block(after_text, path=selected_file) if after_text is not None else mo.md("File absent from head."),
        "Supplied patch": _supplied_diff,
        "Reviewer context": mo.vstack(_inline) if _inline else mo.md("No inline files."),
        "Access manifest": mo.ui.table(_manifest_rows, selection=None, pagination=False, show_download=False),
        "JSON": source_block(json.dumps(public, indent=2), language="json"),
    })
    explorer_view = mo.vstack([
        file_tree_selection_style(inventory, selected_file),
        file_tree_layout(file_tree, _tabs),
    ])
    explorer_view
    return (explorer_view,)


@app.cell
def _(case_dir, json, mo, public, source_block):
    _budget_rows = [
        {
            "Dimension": _dimension,
            "Whole path": "not capped" if _whole is None else str(_whole),
            "Inherited": "unknown" if public["budgets"]["inherited"][_dimension] is None
            else str(public["budgets"]["inherited"][_dimension]),
            "Remaining": "not capped" if public["budgets"]["remaining"][_dimension] is None
            else str(public["budgets"]["remaining"][_dimension]),
        }
        for _dimension, _whole in public["budgets"]["whole_path"].items()
    ]
    prefix = None
    if public["start"]["mode"] == "continuation":
        # Display supplied history only. Never replay its commands.
        prefix = json.loads((case_dir / "reviewer/prefix.json").read_text(encoding="utf-8"))
    mo.accordion({
        "Budgets": mo.vstack([
            mo.ui.table(_budget_rows, selection=None, pagination=False, show_download=False),
            mo.md("Zero prohibits further usage; unknown is not zero. Only new actions consume the remaining budget."),
        ]),
        **({"Checkpoint history (not replayed)": source_block(json.dumps(prefix, indent=2), language="json")}
           if prefix is not None else {}),
    })
    return (prefix,)


@app.cell
def _(mo, public):
    reveal_labels = mo.ui.checkbox(
        label=f"Show reference labels · {public['case_id']}", value=False,
    )
    reveal_labels
    return (reveal_labels,)


@app.cell
def _(case_dir, fixture_validator, json, mo, reveal_labels, source_block):
    private_notes = None
    _view = None
    if reveal_labels.value:
        _, private_notes = fixture_validator.validate_fixture(case_dir)
        _expectations = private_notes["expectations"]
        _findings = _expectations["required_findings"]
        _view = mo.vstack([
            mo.callout(
                f"Reference: {private_notes['labels']['change_outcome']} · "
                f"independent verification: {private_notes['provenance']['verification']['status']}. "
                "Author labels remain provisional.",
                kind="warn",
            ),
            mo.vstack([
                mo.md(f"**{_finding['severity']} · {_finding['id']}**\n\n{_finding['explanation']}")
                for _finding in _findings
            ]) if _findings else mo.md(
                "No required defects under this contract; this is not proof of correctness."
            ),
            mo.accordion({
                "Non-findings": source_block(json.dumps(_expectations["non_findings"], indent=2), language="json"),
                "Private rubric and provenance": source_block(json.dumps(private_notes, indent=2), language="json"),
            }),
        ])
    _view
    return (private_notes,)


@app.cell
def _(mo):
    run_probes = mo.ui.run_button(label="Run pair probes")
    mo.hstack([
        run_probes,
        mo.md("Executes trusted case-0004/0005 snapshots without a sandbox."),
    ], align="center", justify="start")
    return (run_probes,)


@app.cell
def _(CASE_IDS, PROBES, check_contract, load_builder, mo, run_probes, source_block):
    probe_failures = None
    _probe_view = None
    if run_probes.value:
        # Deliberately independent of the explorer's case selector.
        probe_failures = {_case: check_contract(load_builder(_case)) for _case in CASE_IDS}
        _probe_view = mo.vstack([
            mo.hstack([
                mo.stat(f"{len(PROBES) - len(probe_failures[_case])}/{len(PROBES)}",
                        label=f"{_case} · contract probes passed", bordered=True)
                for _case in CASE_IDS
            ], widths="equal"),
            mo.ui.table([
                {"Probe": _probe.name, **{
                    _case: "FAIL" if _probe.name in probe_failures[_case] else "PASS"
                    for _case in CASE_IDS
                }}
                for _probe in PROBES
            ], selection=None, pagination=False, show_download=False),
            mo.accordion({
                f"{_case} · mismatch evidence": source_block(
                    "\n".join(f"{_name}: {_detail}" for _name, _detail in probe_failures[_case].items())
                    or "No contract mismatches."
                ) for _case in CASE_IDS
            }),
            mo.md("Contract probes, not reviewer scores or independent annotation review."),
        ])
    _probe_view
    return (probe_failures,)


@app.cell
def _(mo):
    run_validation = mo.ui.run_button(
        label="Validate fixtures", tooltip="Check artifact structure and integrity without executing snapshots.",
    )
    run_validation
    return (run_validation,)


@app.cell
def _(fixture_validator, mo, root, run_validation):
    validated_count = None
    _validation_view = None
    if run_validation.value:
        _directories = [
            _path.parent.parent
            for _collection in ("examples", "fixtures")
            for _path in sorted((root / _collection).glob("*/reviewer/input.json"))
        ]
        validated_count = fixture_validator.validate_dataset(_directories)
        _validation_view = mo.callout(
            f"Validated {validated_count} fixtures. Structure and integrity only; no snapshot code executed.",
            kind="success",
        )
    _validation_view
    return (validated_count,)


@app.cell
def _(mo):
    mo.accordion({"About this demo": mo.md(r"""
    `reviewer/` holds reviewer input, `environment/` holds runner-owned snapshots,
    and `private/` holds evaluator labels. Snapshot browsing checks hashes and
    never executes source. It grants no extra reviewer access; hiding a panel
    is not isolation. Never give a reviewer this notebook or a fixture directory.

    Fixture artifacts and continuation variants are not independent review scenarios.
    See the corpus documentation for authored coverage. Annotation review, licensing
    approval, and a frozen corpus are pending.
    This notebook does not evaluate a reviewer. Match findings by mechanism, trigger,
    and consequence; novel findings need human adjudication.

    Pair probes use the same 14 checks: six collision probes and eight controls.
    Runtime errors are errors, not successful reproductions. Validation checks
    schemas, hashes, diffs, snapshots, call/result links, counters, budgets, and
    partition relationships; it does not establish correctness, licensing permission,
    absence of answer leakage, or sandbox safety.

    No model or network is needed after setup. See `README.md`,
    `docs/fixture-format.md`, and evaluator-only `docs/query-overrides.md`.
    """)})
    return


if __name__ == "__main__":
    app.run()
