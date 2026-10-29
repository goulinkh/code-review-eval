"""Benchmark-only normalization, reports and human adjudication (not execution)."""

from __future__ import annotations

import json
import math
import os
import tempfile
from collections import Counter
from pathlib import Path, PurePosixPath
from urllib.parse import quote

import mlflow
from mlflow.entities import AssessmentSource

from validate_fixtures import FixtureError, check_schema, sha256, strict_json
from visual_reporting import visual_report

VERSION = "1.0.0"
GRADING_VERSION = "human-1.1.0"


def save_json(path: Path, value) -> None:
    """Atomic replacement: an interrupted prompt/import must not truncate progress."""
    content = json.dumps(value, indent=2, allow_nan=False) + "\n"
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
            stream.close()
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)


def load_json(path: Path):
    return strict_json(path.read_bytes())


def normalize(raw: bytes) -> dict:
    review = strict_json(raw)
    check_schema("review", review)
    result = {
        "schema_version": VERSION,
        "summary": review.get("summary"),
        "recommendation": review.get("recommendation", "not_provided"),
        "usage": {key: review.get("usage", {}).get(key)
                  for key in ("input_tokens", "output_tokens", "cost_usd")},
        "normalization_notes": review.get("normalization_notes", []),
        "findings": [],
    }
    cost = result["usage"]["cost_usd"]
    if cost is not None and not math.isfinite(cost):
        raise FixtureError("nonfinite cost")
    for index, finding in enumerate(review["findings"], 1):
        result["findings"].append({
            "id": f"f-{index:03d}", "text": finding["text"],
            **{key: finding.get(key) for key in ("path", "side", "lines", "severity")},
        })
    return result


def location_checks(review: dict, public: dict, fixture: Path) -> list[str]:
    errors = []
    for finding in review["findings"]:
        path, side, lines = (finding[key] for key in ("path", "side", "lines"))
        problem = None
        if path is None:
            if lines is not None or side is not None:
                problem = "location_without_path"
        elif (PurePosixPath(path).as_posix() != path or path.startswith("/")
              or ".." in PurePosixPath(path).parts or "\\" in path):
            problem = "noncanonical_path"
        else:
            candidates = [item for name, snapshot in public["snapshots"].items()
                          if side is None or name == side
                          for item in snapshot["files"] if item["path"] == path]
            if not candidates:
                problem = "path_not_in_snapshot"
            elif lines is not None:
                lengths = [len((fixture / "environment/blobs" / item["sha256"])
                               .read_text(encoding="utf-8").splitlines()) for item in candidates]
                if lines["start"] > lines["end"] or not any(lines["end"] <= n for n in lengths):
                    problem = "line_range_out_of_bounds"
        if problem:
            errors.append(f"{finding['id']}: {problem}")
    return errors


def human_template(case_id: str, review: dict | None, review_hash: str | None,
                   input_hash: str | None = None, reference_hash: str | None = None) -> dict:
    return {
        "schema_version": VERSION, "case_id": case_id, "review_sha256": review_hash,
        "input_sha256": input_hash, "reference_sha256": reference_hash,
        "adjudicator": None, "approval": None,
        "empty_review": {"verdict": "unresolved", "reason": ""},
        "findings": [{"finding_id": f["id"], "verdict": "unresolved", "reference_id": None,
                      "duplicate_of": None, "reason": ""} for f in (review or {}).get("findings", [])],
        "case_verdicts": {key: {"verdict": "unresolved", "reason": ""}
                          for key in ("context_handling", "instruction_handling")},
    }


def judgment_digest(human: dict) -> str:
    return sha256(json.dumps({k: v for k, v in human.items() if k != "approval"},
                             sort_keys=True, allow_nan=False).encode())


def approve_form(human: dict, source: str) -> None:
    """Called only after explicit operator confirmation; simulations never become HUMAN."""
    human["approval"] = {"source": source, "judgments_sha256": judgment_digest(human)}


def validate_human(human: dict, template: dict, private: dict) -> None:
    """Reject ambiguous matches; never infer a semantic judgment from review text."""
    def require(ok, message):
        if not ok:
            raise FixtureError(f"adjudication: {message}")

    require(isinstance(human, dict) and human.keys() == template.keys(), "unexpected fields")
    for key in ("schema_version", "case_id", "review_sha256", "input_sha256", "reference_sha256"):
        require(human[key] == template[key], f"stale or mismatched {key}")
    require(human["adjudicator"] is None or
            isinstance(human["adjudicator"], str) and bool(human["adjudicator"].strip()), "adjudicator required")
    rows = human["findings"]
    require(isinstance(rows, list), "findings must be a list")
    expected_ids = [f["finding_id"] for f in template["findings"]]
    require(len(rows) == len(expected_ids), "one judgment per finding required")
    require(all(isinstance(r, dict) and r.keys() == {
        "finding_id", "verdict", "reference_id", "duplicate_of", "reason"} for r in rows), "finding fields")
    require([r["finding_id"] for r in rows] == expected_ids, "finding IDs/order changed")
    reference_ids = {f["id"] for f in private["expectations"]["required_findings"]}
    matched = set()
    by_id = {r["finding_id"]: r for r in rows}
    for row in rows:
        verdict, ref, duplicate = row["verdict"], row["reference_id"], row["duplicate_of"]
        require(verdict in ("valid", "invalid", "duplicate", "unresolved"), "unknown finding verdict")
        require(isinstance(row["reason"], str), "reason must be text")
        if verdict != "unresolved":
            require(bool(human["adjudicator"]) and bool(row["reason"].strip()), "resolved judgments need human and reason")
        if ref is not None:
            require(isinstance(ref, str) and verdict == "valid" and ref in reference_ids,
                    "only valid findings can match known references")
            require(ref not in matched, "reference matched more than once")
            matched.add(ref)
        if verdict == "duplicate":
            require(isinstance(duplicate, str) and duplicate in by_id and duplicate != row["finding_id"]
                    and by_id[duplicate]["verdict"] in ("valid", "invalid"), "duplicate needs distinct resolved target")
        else:
            require(duplicate is None, "only duplicates may set duplicate_of")
    empty = human["empty_review"]
    require(isinstance(empty, dict) and empty.keys() == {"verdict", "reason"}, "empty review fields")
    require(empty["verdict"] in ("approved", "unresolved") and isinstance(empty["reason"], str), "empty review verdict")
    if empty["verdict"] == "approved":
        require(not rows and bool(human["adjudicator"]) and bool(empty["reason"].strip()),
                "empty approval requires an empty review, operator and reason")
    approval = human["approval"]
    if approval is not None:
        require(isinstance(approval, dict) and approval.keys() == {"source", "judgments_sha256"}, "approval fields")
        require(approval["source"] in ("human", "simulation") and bool(human["adjudicator"]), "approval source/operator")
        require(approval["judgments_sha256"] == judgment_digest(human), "stale approval; confirm the changed form again")
    verdicts = human["case_verdicts"]
    require(isinstance(verdicts, dict) and verdicts.keys() == template["case_verdicts"].keys(), "case verdict fields")
    for row in verdicts.values():
        require(isinstance(row, dict) and row.keys() == {"verdict", "reason"}, "case verdict fields")
        require(row["verdict"] in ("pass", "fail", "unresolved", "not_applicable"), "unknown case verdict")
        require(isinstance(row["reason"], str), "reason must be text")
        if row["verdict"] != "unresolved":
            require(bool(human["adjudicator"]) and bool(row["reason"].strip()), "case judgments need human and reason")


def ratio(numerator: int, denominator: int) -> dict:
    return {"numerator": numerator, "denominator": denominator,
            "value": numerator / denominator if denominator else None}


def quality(report: dict, private: dict, human: dict) -> dict:
    references = {f["id"] for f in private["expectations"]["required_findings"]}
    completed = report["status"] == "completed"
    approval = human["approval"]
    approved = bool(approval and approval["judgments_sha256"] == judgment_digest(human))
    rows = human["findings"] if completed else []
    counts = Counter(row["verdict"] if approved else "unresolved" for row in rows)
    matched = {row["reference_id"] for row in rows
               if approved and row["verdict"] == "valid" and row["reference_id"]}
    findings_done = approved and not counts["unresolved"] and (
        bool(rows) or human["empty_review"]["verdict"] == "approved")
    pending = not findings_done or any(r["verdict"] == "unresolved" for r in human["case_verdicts"].values())
    return {
        "status": ("pending" if pending else "adjudicated") if completed else "not_applicable",
        "approval_source": approval["source"] if approved and completed else None,
        "provisional": bool(pending) if completed else False,
        "matched_reference_ids": sorted(matched),
        "unmatched_reference_ids": sorted(references - matched),
        "missed_reference_ids": sorted(references - matched) if completed and findings_done else [],
        "pending_reference_ids": sorted(references - matched) if completed and not findings_done else [],
        "execution_unavailable_reference_ids": sorted(references) if not completed else [],
        "valid_novel_findings": sum(approved and r["verdict"] == "valid" and r["reference_id"] is None for r in rows),
        "finding_counts": {key: counts[key] for key in ("valid", "invalid", "duplicate", "unresolved")},
        "defect_recall": ratio(len(matched), len(references) if completed else 0),
        "finding_precision": ratio(counts["valid"], counts["valid"] + counts["invalid"]),
        "adjudication_coverage": ratio(sum(counts[k] for k in ("valid", "invalid", "duplicate")), sum(counts.values())),
        "findings_complete": bool(completed and findings_done),
        "case_verdicts": human["case_verdicts"] if completed and approved else None,
    }


def aggregate(reports: list[dict]) -> dict:
    """Micro counts, with unknown truth and unavailable execution kept explicit."""
    qualities = [r["quality"] for r in reports]
    def total(key):
        return sum(len(q[key]) for q in qualities)
    counts = Counter()
    for q in qualities:
        counts.update(q["finding_counts"])
    matched, missed, pending, unavailable = (total(k) for k in (
        "matched_reference_ids", "missed_reference_ids", "pending_reference_ids", "execution_unavailable_reference_ids"))
    completed = [r for r in reports if r["status"] == "completed"]
    clean = [r for r in completed if r["labels"]["change_outcome"] == "clean"]
    latencies = [r["latency_ms"] for r in reports if r["latency_ms"] is not None]
    costs = [r["usage"]["cost_usd"] for r in reports if r["usage"]["cost_usd"] is not None]
    simulation = any(q["approval_source"] == "simulation" for q in qualities)
    confirmed = any(q["approval_source"] == "human" for q in qualities)
    return {
        "quality": {
            "basis": ("SIMULATION — not human approval" if simulation else
                      "human-confirmed judgments only" if confirmed else "pending — no confirmed judgments"),
            "defect_recall": ratio(matched, matched + missed + pending),
            "recall_bounds": {"lower": ratio(matched, matched + missed + pending),
                              "upper": ratio(matched + pending, matched + missed + pending)},
            "finding_precision": ratio(counts["valid"], counts["valid"] + counts["invalid"]),
            "precision_bounds": {"lower": ratio(counts["valid"], counts["valid"] + counts["invalid"] + counts["unresolved"]),
                                 "upper": ratio(counts["valid"] + counts["unresolved"], counts["valid"] + counts["invalid"] + counts["unresolved"])},
            "matched_defects": matched, "confirmed_misses": missed, "pending_defects": pending,
            "valid_novel_findings": sum(q["valid_novel_findings"] for q in qualities),
            "finding_counts": dict(counts),
            "finding_coverage": ratio(sum(counts[k] for k in ("valid", "invalid", "duplicate")), sum(counts.values())),
            "case_coverage": ratio(sum(q["status"] == "adjudicated" for q in qualities), len(completed)),
            "pending_cases": sum(q["status"] == "pending" for q in qualities),
            "corrected_case_false_alarms": {
                "invalid_findings": sum(r["quality"]["finding_counts"]["invalid"] for r in clean),
                "affected_cases": ratio(sum(r["quality"]["finding_counts"]["invalid"] > 0 for r in clean), len(clean)),
                "pending_cases": sum(not r["quality"]["findings_complete"] for r in clean),
                "execution_unavailable_cases": sum(r["status"] != "completed" and r["labels"]["change_outcome"] == "clean" for r in reports),
                "valid_novel_findings": sum(r["quality"]["valid_novel_findings"] for r in clean),
            },
        },
        "execution": {"counts": dict(Counter(r["status"] for r in reports)),
                      "completion": ratio(len(completed), len(reports)),
                      "unavailable_defects": unavailable,
                      "delivery_recall_lower_bound": ratio(matched, matched + missed + pending + unavailable)},
        "latency": {"mean_ms": sum(latencies) / len(latencies) if latencies else None,
                    "known_cases": len(latencies), "total_cases": len(reports)},
        "cost": {"known_total_usd": sum(costs) if costs else None,
                 "known_cases": len(costs), "total_cases": len(reports)},
        "ranking": None,
        "ranking_note": "Descriptive only: no confident ranking from pending judgments, simulation, or this provisional corpus.",
    }


def formatted(metric: dict) -> str:
    return f"{metric['numerator']}/{metric['denominator']}" if metric["denominator"] else "N/A"


REPORT_NOTES = """Harness demonstration; not a frozen or independently verified corpus. No overall score or confident ranking.
Recall excludes execution-unavailable cases; delivery recall includes them separately.
Pending defects are not confirmed misses. Recall is a lower bound until adjudication is complete.
Precision is over resolved distinct findings only; duplicates and unresolved findings are shown separately.
Empty denominators are N/A. Corrected-case false alarms count approved invalid findings, not all unmatched findings; affected-case rates are lower bounds while pending.
Practice scores are simulations, NOT human confirmation. Fixture reference checks are not reviewer-quality scores.
Unknown cost is not zero. Recorded latency is Harbor submission time, not original inference latency.
"""


def summary_lines(summary: dict) -> list[str]:
    q, e = summary["quality"], summary["execution"]
    false = q["corrected_case_false_alarms"]
    return [f"Quality basis: **{q['basis']}**", "",
            f"- Defect recall: **{formatted(q['defect_recall'])}**; bounds {formatted(q['recall_bounds']['lower'])}–{formatted(q['recall_bounds']['upper'])}.",
            f"- Finding precision (resolved distinct): **{formatted(q['finding_precision'])}**; bounds {formatted(q['precision_bounds']['lower'])}–{formatted(q['precision_bounds']['upper'])}.",
            f"- Matched: {q['matched_defects']}; confirmed misses: {q['confirmed_misses']}; pending defects: {q['pending_defects']}; novel valid: {q['valid_novel_findings']}.",
            f"- Findings: {q['finding_counts']}; finding coverage {formatted(q['finding_coverage'])}; case coverage {formatted(q['case_coverage'])}; pending cases {q['pending_cases']}.",
            f"- Corrected-case false alarms: {false['invalid_findings']} invalid findings; affected cases {formatted(false['affected_cases'])}; pending cases {false['pending_cases']}; execution unavailable {false['execution_unavailable_cases']}; valid novel {false['valid_novel_findings']}.",
            "", "Execution reliability (not quality): " + str(e["counts"]),
            f"- Completed {formatted(e['completion'])}; execution-unavailable defects {e['unavailable_defects']}; delivery recall lower bound {formatted(e['delivery_recall_lower_bound'])}.",
            f"- Latency (separate): {summary['latency']}", f"- Cost (separate): {summary['cost']}", ""]


def case_lines(reports: list[dict], prefix: str = "") -> list[str]:
    lines = ["| Case / evidence | Execution | Quality / source | Recall | Precision | Miss / pending / unavailable |",
             "|---|---|---|---|---|---|"]
    for report in reports:
        q, case_id = report["quality"], report["case_id"]
        base = f"{prefix}{case_id}"
        review = f"[review]({base}/review.json)" if report["review_sha256"] else f"[raw]({base}/review-output.bin)" if report["raw_sha256"] else "no review"
        links = f"[{case_id}]({base}/report.json) {review} [request]({base}/request.json) [reference]({base}/reference.json) [trace]({base}/trace.json) [form]({base}/adjudication.json)"
        lines.append(f"| {links} | {report['status']} | {q['status']} / {q['approval_source'] or 'none'} | "
                     f"{formatted(q['defect_recall'])} | {formatted(q['finding_precision'])} | "
                     f"{len(q['missed_reference_ids'])} / {len(q['pending_reference_ids'])} / {len(q['execution_unavailable_reference_ids'])} |")
    return lines


def write_reports(output: Path, manifest: dict, reports: list[dict]) -> None:
    summary = aggregate(reports)
    save_json(output / "report.json", {
        "schema_version": VERSION, "execution_counts": summary["execution"]["counts"], "cases": reports,
        "aggregate": summary, "grading_version": GRADING_VERSION,
        "context_boundary": manifest.get("context_boundary"),
        "budget_enforcement": manifest.get("budget_enforcement"),
    })
    save_json(output / "visuals.json", visual_report([
        {"output": output, "manifest": manifest, "cases": reports, "aggregate": summary},
    ], output, grading_version=GRADING_VERSION, notes=REPORT_NOTES))
    for report in reports:
        save_json(output / report["case_id"] / "report.json", report)
    lines = ["# Evaluation report", "", REPORT_NOTES, manifest.get("context_boundary", ""),
             manifest.get("budget_enforcement", ""), "", f"MLflow run: `{manifest['mlflow_run_id']}`", "",
             *summary_lines(summary), *case_lines(reports)]
    (output / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def export_trace(case_dir: Path, trace_id: str) -> None:
    mlflow.flush_trace_async_logging()
    trace = mlflow.get_trace(trace_id)
    if trace is None:
        raise RuntimeError("MLflow did not retain the case trace")
    save_json(case_dir / "trace.json", trace.to_dict())


def form_digest(human: dict) -> str:
    return sha256(json.dumps(human, sort_keys=True, allow_nan=False).encode())


def load_run(output: Path) -> tuple[dict, list[tuple]]:
    """Validate the entire retained bundle before grading, importing, or comparing."""
    manifest = load_json(output / "manifest.json")
    reports = load_json(output / "report.json")["cases"]
    pins = {r["case_id"]: r for r in manifest["cases"]}
    if (len(pins) != len(manifest["cases"]) or len(pins) != len(reports)
            or {r["case_id"] for r in reports} != set(pins)):
        raise FixtureError("run is incomplete or has duplicate case reports")
    prepared = []
    for report in reports:
        case_dir = output / report["case_id"]
        for filename, key in (("request.json", "input_sha256"), ("reference.json", "reference_sha256"),
                              ("review.json", "review_sha256"), ("review-output.bin", "raw_sha256")):
            if key in pins[report["case_id"]] and pins[report["case_id"]][key] != report[key]:
                raise FixtureError(f"manifest/report binding differs: {key}")
            if report[key] is not None and sha256((case_dir / filename).read_bytes()) != report[key]:
                raise FixtureError(f"retained {filename.removesuffix('.json') if filename == 'review.json' else filename} changed")
        review = load_json(case_dir / "review.json") if report["review_sha256"] else None
        private = load_json(case_dir / "reference.json")
        if private["input_sha256"] != report["input_sha256"]:
            raise FixtureError("reference/input binding differs")
        if any(report[key] != private[key] for key in ("case_id", "labels", "dataset")):
            raise FixtureError("report/reference metadata differs")
        human = load_json(case_dir / "adjudication.json")
        template = human_template(report["case_id"], review, report["review_sha256"],
                                  report["input_sha256"], report["reference_sha256"])
        # Upgrade pre-approval forms as DRAFTS, preserving all prior judgments. A name
        # on a legacy form is not explicit human approval, including for empty reviews.
        legacy_keys = set(template) - {"input_sha256", "reference_sha256", "approval", "empty_review"}
        if isinstance(human, dict) and set(human) == legacy_keys:
            human = {**template, **human}
        validate_human(human, template, private)
        prepared.append((report, private, human, template))
    return manifest, prepared


def form_snapshots(output: Path) -> dict[Path, bytes]:
    return {path: path.read_bytes() for path in output.glob("case-*/adjudication.json")}


def adjudicate(output: Path) -> list[dict]:
    # Validate every judgment and binding before logging any human assessments.
    originals = form_snapshots(output)
    manifest, prepared = load_run(output)
    for path, raw in originals.items():
        if path.read_bytes() != raw:
            raise FixtureError("adjudication changed during import; retry")
    mlflow.set_tracking_uri(manifest["tracking_uri"])
    for report, private, human, _ in prepared:
        report["quality"] = quality(report, private, human)
        case_dir = output / report["case_id"]
        path = case_dir / "adjudication.json"
        if path.read_bytes() != originals[path]:
            raise FixtureError("adjudication changed during import; retry")
        if strict_json(originals[path]) != human:  # Persist only legacy migration, not unchanged forms.
            save_json(path, human)
        digest = form_digest(human)
        approval = human["approval"]
        if approval and approval["source"] == "human" and report["status"] == "completed":
            # Only explicitly attested human forms can produce HUMAN feedback.
            trace = mlflow.get_trace(report["trace_id"])
            if trace is None:
                raise RuntimeError("case trace unavailable")
            if not any((a.metadata or {}).get("adjudication_sha256") == digest for a in trace.info.assessments):
                mlflow.log_feedback(
                    trace_id=report["trace_id"], name="human_adjudication", value=json.dumps(human, sort_keys=True),
                    source=AssessmentSource(source_type="HUMAN", source_id=human["adjudicator"]),
                    rationale="Explicitly confirmed human judgments; see hash-bound retained form.",
                    metadata={"adjudication_sha256": digest, "grading_version": GRADING_VERSION},
                )
            export_trace(case_dir, report["trace_id"])
        report["imported_adjudication_sha256"] = digest
    reports = [r[0] for r in prepared]
    write_reports(output, manifest, reports)
    return reports


def report_entries(outputs: list[Path]) -> list[dict]:
    """Validate comparable imported results without MLflow access or changing judgments."""
    outputs = [p.resolve() for p in outputs]
    if not outputs or len(set(outputs)) != len(outputs):
        raise FixtureError("comparison requires distinct run directories")
    entries, signature = [], None
    for output in outputs:
        manifest, prepared = load_run(output)
        current = sorted((r["case_id"], r["revision"], r["input_sha256"], r["reference_sha256"])
                         for r, _, _, _ in prepared)
        current = (manifest["instruction_sha256"], current)
        if signature is not None and signature != current:
            raise FixtureError("incompatible corpus or instruction hashes; rerun/rescore the same cases")
        signature = current
        reports = []
        for report, private, human, _ in prepared:
            imported = report.get("imported_adjudication_sha256")
            if imported != form_digest(human) and (imported is not None or human["approval"] is not None):
                raise FixtureError(f"unimported judgments in {output.name}; run adjudicate first")
            report["quality"] = quality(report, private, human)
            reports.append(report)
        entries.append({"output": output, "manifest": manifest, "cases": reports, "aggregate": aggregate(reports)})
    return entries


def export_visuals(outputs: list[Path], destination: Path) -> dict:
    """Backfill only the sidecar for retained runs; no execution or feedback import."""
    bundle = visual_report(report_entries(outputs), destination, grading_version=GRADING_VERSION, notes=REPORT_NOTES)
    destination.mkdir(parents=True, exist_ok=True)
    save_json(destination / "visuals.json", bundle)
    return bundle


def compare(outputs: list[Path], destination: Path) -> dict:
    """Compare the same immutable corpus; never silently compare different case subsets."""
    if any(destination.resolve().is_relative_to(p.resolve()) for p in outputs):
        raise FixtureError("comparison output must be outside input runs")
    entries = report_entries(outputs)
    runs = []
    lines = ["# Reviewer comparison", "", REPORT_NOTES]
    for entry in entries:
        output, manifest, reports, summary = (entry[k] for k in ("output", "manifest", "cases", "aggregate"))
        runs.append({"output": str(output), "reviewer": manifest["reviewer"],
                     "mlflow_run_id": manifest["mlflow_run_id"], "aggregate": summary})
        relative = Path(os.path.relpath(output, destination)).as_posix()
        # Paths are URL-quoted so evidence links survive spaces in output names.
        prefix = quote(relative, safe="/.-") + "/"
        lines.extend(["", f"## {output.name}", "", f"Reviewer: `{json.dumps(manifest['reviewer'])}`", "",
                      f"[Run report]({prefix}report.md) · MLflow `{manifest['mlflow_run_id']}`", "",
                      manifest.get("context_boundary", ""), manifest.get("budget_enforcement", ""), "",
                      *summary_lines(summary), *case_lines(reports, prefix)])
    table = ["## At a glance", "", "Quality (resolved distinct precision; recall is a lower bound while pending):", "",
             "| Run | Reviewer / model | Basis | Recall | Precision | Missed / pending defects | Case coverage | Corrected false alarms |",
             "|---|---|---|---|---|---|---|---|"]
    execution = ["", "Execution, latency and cost (separate from quality):", "",
                 "| Run | Completion | Unavailable defects | Mean latency ms (known cases) | Known cost USD (known cases) |",
                 "|---|---|---|---|---|"]
    for run in runs:
        summary = run["aggregate"]
        q, e = summary["quality"], summary["execution"]
        name = Path(run["output"]).name
        reviewer = run["reviewer"]
        table.append(f"| {name} | {reviewer['agent']} / {reviewer['model']} | {q['basis']} | "
                     f"{formatted(q['defect_recall'])} | {formatted(q['finding_precision'])} | "
                     f"{q['confirmed_misses']} / {q['pending_defects']} | {formatted(q['case_coverage'])} | "
                     f"{q['corrected_case_false_alarms']['invalid_findings']} |")
        latency, cost = summary["latency"], summary["cost"]
        execution.append(f"| {name} | {formatted(e['completion'])} | {e['unavailable_defects']} | "
                         f"{latency['mean_ms'] if latency['mean_ms'] is not None else 'unknown'} ({latency['known_cases']}/{latency['total_cases']}) | "
                         f"{cost['known_total_usd'] if cost['known_total_usd'] is not None else 'unknown'} ({cost['known_cases']}/{cost['total_cases']}) |")
    lines[3:3] = table + execution
    bundle = {"schema_version": VERSION, "grading_version": GRADING_VERSION, "runs": runs, "ranking": None,
              "ranking_note": "No confident ranking: inspect coverage, bounds, execution gaps and corpus limitations."}
    destination.mkdir(parents=True, exist_ok=False)
    save_json(destination / "report.json", bundle)
    save_json(destination / "visuals.json", visual_report(entries, destination,
              grading_version=GRADING_VERSION, notes=REPORT_NOTES))
    (destination / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return bundle
