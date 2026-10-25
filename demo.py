"""Team demo: evaluator-only fixture walkthrough, not a reviewer or sandbox."""

import marimo

__generated_with = "0.25.2"
app = marimo.App(width="full", app_title="Code review evaluation · fixture explorer")


@app.cell
def _():
    import json

    import marimo as mo

    import validate_fixtures as fixture_validator
    from demo_support.explorer import file_inventory, line_counts, read_snapshot_text, render_diff
    from demo_support.rendering import source_block
    from reference_checks.query_overrides import CASE_IDS, PROBES, check_contract, load_builder

    # Anchor reads to this project, not the shell's working directory.
    root = fixture_validator.SCHEMAS.resolve().parent

    return (
        CASE_IDS,
        PROBES,
        check_contract,
        file_inventory,
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
    # Fixture explorer

    Evaluator-only. Never share this notebook with a reviewer.
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
    _paths = [_item["path"] for _item in inventory]
    file_selector = mo.ui.dropdown(
        options=_paths, value=_paths[0] if _paths else None,
        allow_select_none=False, disabled=not _paths,
        label="File", full_width=True,
    )
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
        mo.accordion({"Files": mo.ui.table(
            inventory, selection=None, pagination=False, show_download=False,
        )}),
        file_selector,
        mo.hstack([diff_layout, full_context], align="center"),
    ])
    return diff_layout, file_selector, full_context, inventory


@app.cell
def _(case_dir, file_selector, mo, public, read_snapshot_text):
    mo.stop(file_selector.value is None, mo.md("This fixture has no snapshot files."))
    before_text = read_snapshot_text(case_dir, public, "base", file_selector.value)
    after_text = read_snapshot_text(case_dir, public, "head", file_selector.value)
    return after_text, before_text


@app.cell
def _(
    after_text,
    before_text,
    diff_layout,
    file_selector,
    full_context,
    inventory,
    json,
    line_counts,
    mo,
    public,
    render_diff,
    source_block,
):
    _added, _removed = line_counts(before_text, after_text)
    _status = next(_item["status"] for _item in inventory if _item["path"] == file_selector.value)
    _snapshot_view = mo.vstack([
        mo.md(f"**{file_selector.value}** · {_status} · **+{_added} / −{_removed} lines**"),
        mo.Html(render_diff(
            before_text, after_text, file_selector.value,
            layout="split" if diff_layout.value == "Side by side" else "unified",
            full_context=full_context.value,
        )),
        mo.md("Green: added · red: removed · amber: changed characters."),
    ])
    _diff = public["change"]["diff"]
    _supplied_diff = (
        source_block(_diff["artifact"]["content"])
        if _diff["status"] == "available" and _diff["artifact"]["content"]
        else mo.md("The supplied diff is available but empty.") if _diff["status"] == "available"
        else mo.md(f"Diff unavailable: {_diff['reason']}")
    )
    _inline = [
        mo.vstack([mo.md(f"**{_entry['path']} · {_entry['snapshot_id']}**"), source_block(_entry["content"])])
        for _entry in public["context_manifest"]
        if _entry["delivery"] == "initial" and _entry["availability"] == "available"
    ]
    _manifest_rows = [
        {"Snapshot": _entry["snapshot_id"], "Path": _entry["path"],
         "Delivery": _entry["delivery"], "Availability": _entry["availability"]}
        for _entry in public["context_manifest"]
    ]
    mo.ui.tabs({
        "Changes": _snapshot_view,
        "Request": mo.md(public["change"]["description"]),
        "Base": source_block(before_text) if before_text is not None else mo.md("File absent from base."),
        "Head": source_block(after_text) if after_text is not None else mo.md("File absent from head."),
        "Supplied patch": _supplied_diff,
        "Reviewer context": mo.vstack(_inline) if _inline else mo.md("No inline files."),
        "Access manifest": mo.ui.table(_manifest_rows, selection=None, pagination=False, show_download=False),
        "JSON": source_block(json.dumps(public, indent=2)),
    })
    return


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
        **({"Checkpoint history (not replayed)": source_block(json.dumps(prefix, indent=2))}
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
                "Non-findings": source_block(json.dumps(_expectations["non_findings"], indent=2)),
                "Private rubric and provenance": source_block(json.dumps(private_notes, indent=2)),
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

    Three format examples and one authored defect/fix pair are not five independent
    scenarios. Annotation review, licensing approval, and a frozen corpus are pending.
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
