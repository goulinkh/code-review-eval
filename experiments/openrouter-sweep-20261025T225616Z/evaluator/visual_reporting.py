"""Read-only projection of evaluation results into chart-friendly, tidy tables."""

from __future__ import annotations

import math
import os
from collections import Counter
from pathlib import Path
from urllib.parse import quote

from validate_fixtures import FixtureError, check_schema

FORMAT = "code-review-eval.visuals"
VERSION = "1.0.0"


def visual_report(entries: list[dict], destination: Path, *, grading_version: str, notes: str) -> dict:
    """Project existing judgments/counts, never classify findings or create approvals."""
    bundle = {"format": FORMAT, "schema_version": VERSION, "grading_version": grading_version,
              "evaluator_only": True, "ranking": None, "notes": notes,
              "runs": [], "cases": [], "metrics": []}

    def metric(run_key, case_id, domain, name, *, value=None, unit="count", ratio=None,
               bounds=None, known_count=None, total_count=None):
        bundle["metrics"].append({
            "run_key": run_key, "case_id": case_id, "domain": domain, "metric": name,
            "unit": "ratio" if ratio is not None else unit,
            "value": ratio["value"] if ratio is not None else value,
            "numerator": ratio["numerator"] if ratio is not None else None,
            "denominator": ratio["denominator"] if ratio is not None else None,
            "lower": bounds["lower"]["value"] if bounds is not None else None,
            "upper": bounds["upper"]["value"] if bounds is not None else None,
            "known_count": known_count, "total_count": total_count,
        })

    for index, entry in enumerate(entries, 1):
        output, manifest, reports, summary = (entry[k] for k in ("output", "manifest", "cases", "aggregate"))
        output = Path(output)
        run_key = f"run-{index:03d}"
        prefix = Path(os.path.relpath(output, destination)).as_posix()
        def link(relative):
            return quote(f"{prefix}/{relative}", safe="/.-")
        q, execution = summary["quality"], summary["execution"]
        expected = len(manifest["cases"])
        bundle["runs"].append({
            "run_key": run_key, "name": output.name, "agent": manifest["reviewer"]["agent"],
            "model": manifest["reviewer"]["model"], "mlflow_run_id": manifest["mlflow_run_id"],
            "quality_basis": q["basis"], "pending_cases": q["pending_cases"],
            "expected_cases": expected, "reported_cases": len(reports), "complete": len(reports) == expected,
            "report_uri": link("report.md"),
        })
        for name in ("defect_recall", "finding_precision", "finding_coverage", "case_coverage"):
            bounds = q.get({"defect_recall": "recall_bounds", "finding_precision": "precision_bounds"}.get(name))
            metric(run_key, None, "quality", name, ratio=q[name], bounds=bounds)
        for name in ("matched_defects", "confirmed_misses", "pending_defects", "valid_novel_findings", "pending_cases"):
            metric(run_key, None, "quality", name, value=q[name])
        for name, value in q["finding_counts"].items():
            metric(run_key, None, "quality", f"{name}_findings", value=value)
        false = q["corrected_case_false_alarms"]
        metric(run_key, None, "quality", "corrected_false_alarm_rate", ratio=false["affected_cases"])
        for source, target in (("invalid_findings", "corrected_false_alarm_findings"),
                               ("pending_cases", "corrected_pending_cases"),
                               ("valid_novel_findings", "corrected_valid_novel_findings")):
            metric(run_key, None, "quality", target, value=false[source])
        metric(run_key, None, "execution", "corrected_unavailable_cases", value=false["execution_unavailable_cases"])
        metric(run_key, None, "execution", "completion", ratio=execution["completion"])
        metric(run_key, None, "execution", "delivery_recall_lower_bound", ratio=execution["delivery_recall_lower_bound"])
        metric(run_key, None, "execution", "unavailable_defects", value=execution["unavailable_defects"])
        metric(run_key, None, "execution", "unreported_cases", value=expected - len(reports))
        for status in ("completed", "failed", "timed_out", "invalid_output"):
            metric(run_key, None, "execution", status, value=execution["counts"].get(status, 0))
        for domain, name, unit in (("latency", "mean_ms", "ms"), ("cost", "known_total_usd", "USD")):
            telemetry = summary[domain]
            metric(run_key, None, domain, name, value=telemetry[name], unit=unit,
                   known_count=telemetry["known_cases"], total_count=telemetry["total_cases"])

        for report in reports:
            case_id, case_quality = report["case_id"], report["quality"]
            bundle["cases"].append({
                "run_key": run_key, "case_id": case_id, "revision": report["revision"],
                "execution_status": report["status"], "adjudication_status": case_quality["status"],
                "approval_source": case_quality["approval_source"],
                "annotation_status": report.get("annotation_verification", {}).get("status", "unknown"),
                "input_sha256": report["input_sha256"], "reference_sha256": report["reference_sha256"],
                "review_sha256": report["review_sha256"],
                "adjudication_sha256": report.get("imported_adjudication_sha256"),
                "trace_id": report["trace_id"],
                "report_uri": link(f"{case_id}/report.json"),
                "review_uri": link(f"{case_id}/review.json") if report["review_sha256"] else None,
                "raw_review_uri": link(f"{case_id}/review-output.bin") if report["raw_sha256"] else None,
                "request_uri": link(f"{case_id}/request.json"),
                "reference_uri": link(f"{case_id}/reference.json"),
                "trace_uri": link(f"{case_id}/trace.json"),
                "adjudication_uri": link(f"{case_id}/adjudication.json"),
            })
            for name in ("defect_recall", "finding_precision", "adjudication_coverage"):
                metric(run_key, case_id, "quality", name, ratio=case_quality[name])
            for source, target in (("matched_reference_ids", "matched_defects"),
                                   ("missed_reference_ids", "confirmed_misses"),
                                   ("pending_reference_ids", "pending_defects")):
                metric(run_key, case_id, "quality", target, value=len(case_quality[source]))
            for verdict, value in case_quality["finding_counts"].items():
                metric(run_key, case_id, "quality", f"{verdict}_findings", value=value)
            metric(run_key, case_id, "quality", "valid_novel_findings", value=case_quality["valid_novel_findings"])
            metric(run_key, case_id, "execution", "unavailable_defects",
                   value=len(case_quality["execution_unavailable_reference_ids"]))
            for domain, name, unit, value in (("latency", "agent_ms", "ms", report["latency_ms"]),
                                               ("cost", "usd", "USD", report["usage"]["cost_usd"])):
                metric(run_key, case_id, domain, name, value=value, unit=unit,
                       known_count=int(value is not None), total_count=1)
    validate_visual_report(bundle)
    return bundle


def validate_visual_report(bundle: dict) -> None:
    check_schema("visual-report", bundle)
    runs = {r["run_key"] for r in bundle["runs"]}
    cases = {(r["run_key"], r["case_id"]) for r in bundle["cases"]}
    if len(runs) != len(bundle["runs"]) or len(cases) != len(bundle["cases"]):
        raise FixtureError("visual report: duplicate run/case keys")
    if any(run_key not in runs for run_key, _ in cases):
        raise FixtureError("visual report: case references unknown run")
    case_counts = Counter(run_key for run_key, _ in cases)
    for run in bundle["runs"]:
        if (run["reported_cases"] != case_counts[run["run_key"]]
                or run["reported_cases"] > run["expected_cases"]
                or run["complete"] != (run["reported_cases"] == run["expected_cases"])
                or run["pending_cases"] > run["reported_cases"]):
            raise FixtureError("visual report: inconsistent run coverage")
    seen = set()
    for row in bundle["metrics"]:
        key = (row["run_key"], row["case_id"], row["domain"], row["metric"])
        if key in seen or row["run_key"] not in runs or (
                row["case_id"] is not None and key[:2] not in cases):
            raise FixtureError("visual report: duplicate metric or unknown run/case")
        seen.add(key)
        for field in ("value", "lower", "upper"):
            if row[field] is not None and not math.isfinite(row[field]):
                raise FixtureError("visual report: nonfinite metric")
        if row["unit"] == "ratio":
            numerator, denominator = row["numerator"], row["denominator"]
            if numerator is None or denominator is None or numerator > denominator:
                raise FixtureError("visual report: invalid ratio counts")
            expected = numerator / denominator if denominator else None
            if row["value"] != expected:
                raise FixtureError("visual report: ratio value/count mismatch")
        elif row["numerator"] is not None or row["denominator"] is not None:
            raise FixtureError("visual report: counts only allowed on ratios")
        if (row["lower"] is None) != (row["upper"] is None) or (
                row["lower"] is not None and not 0 <= row["lower"] <= row["upper"] <= 1):
            raise FixtureError("visual report: invalid uncertainty bounds")
        known, total = row["known_count"], row["total_count"]
        if (known is None) != (total is None) or (known is not None and known > total):
            raise FixtureError("visual report: invalid telemetry coverage")
