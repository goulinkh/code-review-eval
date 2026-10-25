"""Benchmark-only normalization, reports and human adjudication (not execution)."""

from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path, PurePosixPath

import mlflow
from mlflow.entities import AssessmentSource

from validate_fixtures import FixtureError, check_schema, sha256, strict_json

VERSION = "1.0.0"


def save_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


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


def human_template(case_id: str, review: dict | None, review_hash: str | None) -> dict:
    return {
        "schema_version": VERSION, "case_id": case_id, "review_sha256": review_hash,
        "adjudicator": None,
        "findings": [{"finding_id": f["id"], "verdict": "unresolved", "reference_id": None,
                      "duplicate_of": None, "reason": ""} for f in (review or {}).get("findings", [])],
        "case_verdicts": {key: {"verdict": "unresolved", "reason": ""}
                          for key in ("context_handling", "instruction_handling")},
    }


def validate_human(human: dict, template: dict, private: dict) -> None:
    """Reject ambiguous matches; never infer a semantic judgment from review text."""
    def require(ok, message):
        if not ok:
            raise FixtureError(f"adjudication: {message}")

    require(isinstance(human, dict) and human.keys() == template.keys(), "unexpected fields")
    for key in ("schema_version", "case_id", "review_sha256"):
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
    rows = human["findings"] if completed else []
    counts = Counter(row["verdict"] for row in rows)
    matched = {row["reference_id"] for row in rows if row["verdict"] == "valid" and row["reference_id"]}
    pending = not human["adjudicator"] or counts["unresolved"] > 0 or any(
        r["verdict"] == "unresolved" for r in human["case_verdicts"].values())
    return {
        "status": ("pending" if pending else "adjudicated") if completed else "not_applicable",
        "provisional": bool(pending) if completed else False,
        "matched_reference_ids": sorted(matched),
        "unmatched_reference_ids": sorted(references - matched),
        "missed_reference_ids": sorted(references - matched) if not completed or not pending else [],
        "finding_counts": {key: counts[key] for key in ("valid", "invalid", "duplicate", "unresolved")},
        "defect_recall": ratio(len(matched), len(references)),
        "finding_precision": ratio(counts["valid"], counts["valid"] + counts["invalid"]),
        "adjudication_coverage": ratio(counts["valid"] + counts["invalid"],
                                       counts["valid"] + counts["invalid"] + counts["unresolved"]),
        "case_verdicts": human["case_verdicts"] if completed else None,
    }


def write_reports(output: Path, manifest: dict, reports: list[dict]) -> None:
    counts = dict(Counter(r["status"] for r in reports))
    save_json(output / "report.json", {
        "schema_version": VERSION, "execution_counts": counts, "cases": reports,
        "context_boundary": manifest.get("context_boundary"),
        "budget_enforcement": manifest.get("budget_enforcement"),
    })
    lines = ["# Evaluation report", "", "Harness demonstration; not a frozen or independently verified corpus.",
             "Finding quality requires human adjudication. Pending recall is only a lower bound.",
             "Unknown token/cost metadata is not zero. No overall quality score.", "",
             manifest.get("context_boundary", ""), manifest.get("budget_enforcement", ""), "",
             f"MLflow run: `{manifest['mlflow_run_id']}`", "",
             "| Case | Execution | Findings | Quality | Recall | Precision |",
             "|---|---|---:|---|---|---|"]
    def formatted(metric):
        return (f"{metric['numerator']}/{metric['denominator']}" if metric["denominator"] else "N/A")
    for report in reports:
        q = report["quality"]
        case_id = report["case_id"]
        save_json(output / case_id / "report.json", report)
        lines.append(f"| [{case_id}]({case_id}/report.json) | {report['status']} | "
                     f"{report['finding_count']} | {q['status']} | {formatted(q['defect_recall'])} | "
                     f"{formatted(q['finding_precision'])} |")
    (output / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def export_trace(case_dir: Path, trace_id: str) -> None:
    mlflow.flush_trace_async_logging()
    trace = mlflow.get_trace(trace_id)
    if trace is None:
        raise RuntimeError("MLflow did not retain the case trace")
    save_json(case_dir / "trace.json", trace.to_dict())


def adjudicate(output: Path) -> list[dict]:
    manifest = load_json(output / "manifest.json")
    bundle = load_json(output / "report.json")
    reports = bundle["cases"]
    # Validate every judgment and binding before logging any human assessments.
    prepared = []
    for report in reports:
        case_dir = output / report["case_id"]
        for filename, key in (("request.json", "input_sha256"), ("reference.json", "reference_sha256")):
            if sha256((case_dir / filename).read_bytes()) != report[key]:
                raise FixtureError(f"retained {filename} changed")
        review = load_json(case_dir / "review.json") if report["review_sha256"] else None
        if review is not None and sha256((case_dir / "review.json").read_bytes()) != report["review_sha256"]:
            raise FixtureError("retained review changed")
        private = load_json(case_dir / "reference.json")
        human = load_json(case_dir / "adjudication.json")
        template = human_template(report["case_id"], review, report["review_sha256"])
        validate_human(human, template, private)
        prepared.append((report, private, human))
    mlflow.set_tracking_uri(manifest["tracking_uri"])
    for report, private, human in prepared:
        report["quality"] = quality(report, private, human)
        case_dir = output / report["case_id"]
        if human["adjudicator"] and report["status"] == "completed":
            # One assessment per signed form revision. Re-importing unchanged forms is idempotent.
            digest = sha256((case_dir / "adjudication.json").read_bytes())
            trace = mlflow.get_trace(report["trace_id"])
            if trace is None:
                raise RuntimeError("case trace unavailable")
            if not any((a.metadata or {}).get("adjudication_sha256") == digest for a in trace.info.assessments):
                mlflow.log_feedback(
                    trace_id=report["trace_id"], name="human_adjudication", value=json.dumps(human, sort_keys=True),
                    source=AssessmentSource(source_type="HUMAN", source_id=human["adjudicator"]),
                    rationale="Manual finding and behavior judgments; see retained adjudication form.",
                    metadata={"adjudication_sha256": digest, "grading_version": "human-1.0.0"},
                )
            export_trace(case_dir, report["trace_id"])
    write_reports(output, manifest, reports)
    return reports
