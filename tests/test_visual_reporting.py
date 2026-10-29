"""Pure projections of synthetic judgments; no human assessments or reviewer calls."""

import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import unquote

from demo_support.results import load_visuals, result_views
from review_reporting import (
    GRADING_VERSION, REPORT_NOTES, aggregate, approve_form, compare, export_visuals,
    form_digest, human_template, load_json, normalize, quality, save_json, write_reports,
)
from validate_fixtures import FixtureError
from visual_reporting import validate_visual_report, visual_report

ROOT = Path(__file__).resolve().parents[1]


def entry(output, *, pending=False, failed=False):
    reports, forms, privates = [], [], []
    for case_id in ("case-0004", "case-0005"):
        private = load_json(ROOT / "fixtures" / case_id / "private/expectations.json")
        review = normalize(json.dumps({"schema_version": "1.0.0", "findings": [
            {"text": "SECRET review text"}, {"text": "SECRET second finding"}
        ] if case_id == "case-0004" else []}).encode())
        report = {
            "case_id": case_id, "revision": "1", "labels": private["labels"], "dataset": private["dataset"],
            "annotation_verification": private["provenance"]["verification"],
            "input_sha256": private["input_sha256"], "reference_sha256": "a" * 64,
            "review_sha256": "b" * 64, "raw_sha256": "c" * 64, "trace_id": "test-only-" + case_id,
            "status": "timed_out" if failed and case_id == "case-0004" else "completed",
            "finding_count": len(review["findings"]), "latency_ms": 120 if case_id == "case-0004" else None,
            "usage": {"cost_usd": 0.25 if case_id == "case-0004" else None},
        }
        form = human_template(case_id, review, report["review_sha256"], report["input_sha256"], report["reference_sha256"])
        if not pending:
            form["adjudicator"] = "synthetic-test-operator"
            for row in form["case_verdicts"].values():
                row.update(verdict="pass", reason="SECRET reason, not exported")
            if review["findings"]:
                form["findings"][0].update(verdict="valid", reference_id="finding-01", reason="SECRET evidence")
                form["findings"][1].update(verdict="invalid", reason="SECRET evidence")
            else:
                form["empty_review"] = {"verdict": "approved", "reason": "SECRET inspection"}
            approve_form(form, "simulation")
            report["imported_adjudication_sha256"] = form_digest(form)
        report["quality"] = quality(report, private, form)
        reports.append(report)
        forms.append(form)
        privates.append(private)
    manifest = {"reviewer": {"agent": "recorded", "model": "unknown"}, "mlflow_run_id": "test-only",
                "instruction_sha256": "shared", "cases": [{"case_id": r["case_id"]} for r in reports]}
    return {"output": output, "manifest": manifest, "cases": reports, "aggregate": aggregate(reports)}, forms, privates


class VisualReportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.first, self.forms, self.privates = entry(self.root / "first run")
        self.second, _, _ = entry(self.root / "pending run", pending=True)
        self.destination = self.root / "comparison"
        self.bundle = self.build([self.first, self.second])

    def build(self, entries):
        return visual_report(entries, self.destination, grading_version=GRADING_VERSION, notes=REPORT_NOTES)

    def metric(self, name, domain="quality", run_key="run-001", case_id=None):
        return next(r for r in self.bundle["metrics"] if
                    (r["run_key"], r["case_id"], r["domain"], r["metric"]) == (run_key, case_id, domain, name))

    def test_flat_tables_have_unique_join_keys_numeric_ratios_and_evidence_bindings(self):
        validate_visual_report(self.bundle)
        self.assertEqual(len(self.bundle["runs"]), 2)
        self.assertEqual(len(self.bundle["cases"]), 4)
        self.assertEqual(self.metric("defect_recall")["value"], 1)
        precision = self.metric("finding_precision")
        self.assertEqual((precision["numerator"], precision["denominator"], precision["value"]), (1, 2, 0.5))
        self.assertIn("SIMULATION", self.bundle["runs"][0]["quality_basis"])
        self.assertIsNone(self.bundle["ranking"])
        case = self.bundle["cases"][0]
        self.assertEqual(case["reference_sha256"], "a" * 64)
        self.assertEqual(case["approval_source"], "simulation")
        self.assertEqual(case["adjudication_sha256"], form_digest(self.forms[0]))
        self.assertEqual(case["annotation_status"], "pending")
        self.assertEqual(unquote(case["reference_uri"]), "../first run/case-0004/reference.json")
        self.assertEqual(case["trace_id"], "test-only-case-0004")
        serialized = json.dumps(self.bundle)
        self.assertNotIn("SECRET", serialized)
        self.assertNotIn("required_findings", serialized)

    def test_pending_intervals_are_not_confirmed_misses_or_rankings(self):
        self.assertEqual(self.metric("confirmed_misses", run_key="run-002")["value"], 0)
        self.assertEqual(self.metric("pending_defects", run_key="run-002")["value"], 1)
        recall = self.metric("defect_recall", run_key="run-002")
        self.assertEqual((recall["lower"], recall["upper"]), (0, 1))
        self.assertEqual(self.metric("case_coverage", run_key="run-002")["value"], 0)

    def test_unknown_and_partial_telemetry_keep_known_total_coverage(self):
        latency = self.metric("mean_ms", "latency")
        self.assertEqual((latency["value"], latency["known_count"], latency["total_count"]), (120, 1, 2))
        cost = self.metric("known_total_usd", "cost")
        self.assertEqual((cost["value"], cost["known_count"], cost["total_count"]), (0.25, 1, 2))
        unknown = self.metric("usd", "cost", case_id="case-0005")
        self.assertIsNone(unknown["value"])
        self.assertEqual(unknown["known_count"], 0)
        for report in self.first["cases"]:
            report["usage"]["cost_usd"] = None
        self.first["aggregate"] = aggregate(self.first["cases"])
        self.bundle = self.build([self.first])
        self.assertIsNone(self.metric("known_total_usd", "cost")["value"])
        self.assertIn("unknown", result_views(self.bundle)["Cost"])

    def test_empty_denominators_are_null_not_perfect_scores(self):
        precision = self.metric("finding_precision", case_id="case-0005")
        self.assertEqual(precision["denominator"], 0)
        self.assertIsNone(precision["value"])
        self.assertEqual(self.metric("case_coverage")["value"], 1)

    def test_execution_failure_stays_out_of_confirmed_quality_misses(self):
        failed, _, _ = entry(self.root / "failed", failed=True)
        self.bundle = self.build([failed])
        self.assertEqual(self.metric("timed_out", "execution")["value"], 1)
        self.assertEqual(self.metric("unavailable_defects", "execution")["value"], 1)
        self.assertEqual(self.metric("confirmed_misses")["value"], 0)
        self.assertIsNone(self.metric("defect_recall")["value"])
        failed["cases"][0].update(review_sha256=None, raw_sha256=None)
        self.assertIsNone(self.build([failed])["cases"][0]["review_uri"])

    def test_partial_execution_is_explicit(self):
        self.first["cases"] = self.first["cases"][:1]
        self.first["aggregate"] = aggregate(self.first["cases"])
        self.bundle = self.build([self.first])
        run = self.bundle["runs"][0]
        self.assertEqual((run["reported_cases"], run["expected_cases"], run["complete"]), (1, 2, False))
        self.assertEqual(self.metric("unreported_cases", "execution")["value"], 1)

    def test_schema_and_semantic_validation_fail_closed(self):
        mutations = [
            lambda b: b.update(schema_version="2.0.0"),
            lambda b: b.update(ranking=["run-001"]),
            lambda b: b["runs"].append(copy.deepcopy(b["runs"][0])),
            lambda b: b["cases"][0].update(run_key="absent"),
            lambda b: b["metrics"].append(copy.deepcopy(b["metrics"][0])),
            lambda b: b["metrics"][0].update(value=0.3),
            lambda b: b["metrics"][0].update(lower=1, upper=0),
            lambda b: b["metrics"][0].update(value=float("inf")),
            lambda b: b["metrics"][0].update(known_count=2, total_count=1),
            lambda b: b["runs"][0].update(complete=False),
        ]
        for mutate in mutations:
            bad = copy.deepcopy(self.bundle)
            mutate(bad)
            with self.subTest(mutation=mutate), self.assertRaises(FixtureError):
                validate_visual_report(bad)

    def test_loader_is_offline_confined_and_does_not_read_linked_private_artifacts(self):
        self.destination.mkdir()
        path = self.destination / "visuals.json"
        save_json(path, self.bundle)
        self.assertEqual(load_visuals(path, self.root), self.bundle)
        with self.assertRaisesRegex(FixtureError, "inside this project"):
            load_visuals("../outside.json", self.root)
        (self.root / "escape.json").symlink_to(Path(self.root.parent) / "outside.json")
        with self.assertRaisesRegex(FixtureError, "inside this project"):
            load_visuals("escape.json", self.root)
        path.write_text('{"format":"x","format":"y"}')
        with self.assertRaisesRegex(FixtureError, "duplicate JSON key"):
            load_visuals(path, self.root)

    def test_renderer_escapes_labels_and_keeps_four_domains_separate(self):
        self.bundle["runs"][0]["agent"] = '<script>alert("x")</script>'
        views = result_views(self.bundle)
        self.assertEqual(set(views), {"Quality", "Execution", "Latency", "Cost"})
        text = "".join(views.values())
        self.assertNotIn("<script>", text)
        self.assertIn("&lt;script&gt;", text)
        self.assertIn('role="img"', text)
        self.assertIn("not confirmed misses", views["Execution"])
        self.assertIn("SIMULATION", views["Quality"])
        self.assertIn("range 0%–100%", views["Quality"])
        self.assertIn("subtotal", views["Cost"])

    def test_single_run_writer_emits_sidecar_without_changing_original_quality(self):
        output = self.first["output"]
        for report in self.first["cases"]:
            (output / report["case_id"]).mkdir(parents=True)
        original = copy.deepcopy(self.first["cases"])
        write_reports(output, self.first["manifest"], self.first["cases"])
        self.assertEqual(original, self.first["cases"])
        loaded = load_visuals(output / "visuals.json", self.root)
        self.assertEqual(len(loaded["runs"]), 1)
        self.assertTrue((output / "report.md").is_file())
        self.assertEqual(load_json(output / "report.json")["cases"], original)

    def prepared(self):
        return self.first["manifest"], list(zip(self.first["cases"], self.privates, self.forms, self.forms))

    def test_compare_and_backfill_emit_the_same_tables_without_assessments(self):
        with patch("review_reporting.load_run", return_value=self.prepared()), patch("review_reporting.mlflow.log_feedback") as feedback:
            compare([self.first["output"]], self.destination)
            original = (self.destination / "report.json").read_bytes()
            exported = load_json(self.destination / "visuals.json")
            self.assertEqual(export_visuals([self.first["output"]], self.destination), exported)
            self.assertEqual((self.destination / "report.json").read_bytes(), original)
            feedback.assert_not_called()

    def test_backfill_rejects_unimported_judgments(self):
        self.first["cases"][0].pop("imported_adjudication_sha256")
        with patch("review_reporting.load_run", return_value=self.prepared()):
            with self.assertRaisesRegex(FixtureError, "unimported"):
                export_visuals([self.first["output"]], self.destination)
        self.assertFalse(self.destination.exists())


@unittest.skipUnless(importlib.util.find_spec("marimo"), "install the demo dependency group")
class VisualNotebookTests(unittest.TestCase):
    def test_results_are_opt_in_and_load_failures_are_displayed(self):
        from demo import app
        with patch("demo_support.results.load_visuals", side_effect=AssertionError("default loaded results")):
            _, definitions = app.run()
        self.assertIsNone(definitions["visual_results"])
        self.assertIsNone(definitions["results_error"])
        _, definitions = app.run(defs={
            "load_results": SimpleNamespace(value=True),
            "results_path": SimpleNamespace(value="../outside.json"),
        })
        self.assertIsNone(definitions["visual_results"])
        self.assertIn("inside this project", definitions["results_error"])

    def test_opt_in_displays_retained_results_without_execution_or_private_reads(self):
        from demo import app
        first, _, _ = entry(ROOT / "runs/test-only")
        bundle = visual_report([first], ROOT / "runs", grading_version=GRADING_VERSION, notes=REPORT_NOTES)
        with patch("demo_support.results.load_visuals", return_value=bundle) as loader, patch(
                "reference_checks.query_overrides.load_builder", side_effect=AssertionError("snapshot executed")):
            _, definitions = app.run(defs={
                "load_results": SimpleNamespace(value=True),
                "results_path": SimpleNamespace(value="runs/test-only/visuals.json"),
            })
        loader.assert_called_once_with("runs/test-only/visuals.json", ROOT)
        self.assertEqual(definitions["visual_results"], bundle)
        self.assertIsNone(definitions["results_error"])
        self.assertIsNone(definitions["private_notes"])
        self.assertIsNone(definitions["probe_failures"])


if __name__ == "__main__":
    unittest.main()
