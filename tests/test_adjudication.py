"""Operator scripts here are synthetic test data, never approvals of real reviews."""

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from adjudication_cli import grade
from review_reporting import (
    adjudicate, aggregate, approve_form, compare, human_template, load_json,
    load_run, normalize, quality, save_json, validate_human, write_reports,
)
from run_eval import prepare
from validate_fixtures import FixtureError, sha256

ROOT = Path(__file__).resolve().parents[1]
CASES = [ROOT / "fixtures" / name for name in ("case-0004", "case-0005")]


class AdjudicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.output = self.root / "first run"
        self.manifest, self.reports = self.make_run(self.output)

    def make_run(self, output, texts=("Any wording", "Unsupported allegation"), statuses=None, clean_texts=()):
        cases = prepare(CASES, output)
        manifest = {"reviewer": {"agent": "recorded", "model": "unknown"},
                    "mlflow_run_id": "test-only", "tracking_uri": "sqlite:///test-only.db",
                    "instruction_sha256": "same", "grading_version": "human-1.1.0", "cases": []}
        reports = []
        for case_id, (_, public, private) in cases.items():
            directory = output / case_id
            raw = json.dumps({"schema_version": "1.0.0", "findings": [
                {"text": t} for t in (texts if case_id == "case-0004" else clean_texts)]}).encode()
            review = normalize(raw)
            (directory / "review-output.bin").write_bytes(raw)
            save_json(directory / "review.json", review)
            save_json(directory / "trace.json", {"test_only": True})
            report = {"case_id": case_id, "revision": public["revision"], "dataset": private["dataset"],
                      "labels": private["labels"], "protocol": public["protocol"],
                      "annotation_verification": private["provenance"]["verification"],
                      "status": (statuses or {}).get(case_id, "completed"),
                      "finding_count": len(review["findings"]), "latency_ms": None,
                      "usage": {"cost_usd": None}, "trace_id": case_id + "-test-only"}
            for filename, key in (("request.json", "input_sha256"), ("reference.json", "reference_sha256"),
                                  ("review.json", "review_sha256"), ("review-output.bin", "raw_sha256")):
                report[key] = sha256((directory / filename).read_bytes())
            manifest["cases"].append({k: report[k] for k in ("case_id", "input_sha256", "reference_sha256")})
            form = human_template(case_id, review, report["review_sha256"], report["input_sha256"], report["reference_sha256"])
            save_json(directory / "adjudication.json", form)
            report["quality"] = quality(report, private, form)
            reports.append(report)
        save_json(output / "manifest.json", manifest)
        write_reports(output, manifest, reports)
        return manifest, reports

    def form(self, case_id="case-0004"):
        return load_json(self.output / case_id / "adjudication.json")

    def private(self, case_id="case-0004"):
        return load_json(self.output / case_id / "reference.json")

    def resolved(self, case_id="case-0004", source="simulation"):
        form = self.form(case_id)
        form["adjudicator"] = "synthetic-test-operator"
        for row in form["findings"]:
            row.update(verdict="invalid", reason="Synthetic manual decision, no text matching.")
        for row in form["case_verdicts"].values():
            row.update(verdict="pass", reason="Inspected in test script.")
        approve_form(form, source)
        return form

    def q(self, form, case_id="case-0004"):
        report = next(r for r in self.reports if r["case_id"] == case_id)
        return quality(report, self.private(case_id), form)

    def save_form(self, form):
        save_json(self.output / form["case_id"] / "adjudication.json", form)

    def test_pending_is_not_missed_and_unsigned_decisions_are_not_truth(self):
        form = self.resolved()
        form["findings"][0].update(verdict="valid", reference_id="finding-01")
        form["approval"] = None
        q = self.q(form)
        self.assertEqual(q["finding_counts"]["unresolved"], 2)
        self.assertEqual(q["matched_reference_ids"], [])
        self.assertEqual(q["missed_reference_ids"], [])
        self.assertEqual(q["pending_reference_ids"], ["finding-01"])
        approve_form(form, "simulation")
        self.assertEqual(self.q(form)["defect_recall"]["value"], 1)
        form["findings"][1]["verdict"] = "unresolved"
        approve_form(form, "simulation")
        self.assertEqual(self.q(form)["status"], "pending")
        self.assertEqual(self.q(form)["finding_precision"]["value"], 1)

    def test_incorrect_findings_are_not_matches_even_with_identical_text(self):
        explanation = self.private()["expectations"]["required_findings"][0]["explanation"]
        self.output = self.root / "identical text"
        _, self.reports = self.make_run(self.output, texts=(explanation, "Unsupported allegation"))
        form = self.resolved()
        self.assertEqual(self.q(form)["defect_recall"]["value"], 0)
        self.assertEqual(self.q(form)["finding_precision"]["value"], 0)
        self.assertEqual(self.q(form)["missed_reference_ids"], ["finding-01"])

    def test_empty_defective_review_requires_explicit_approval_then_is_a_miss(self):
        output = self.root / "empty"
        _, reports = self.make_run(output, texts=())
        form = load_json(output / "case-0004/adjudication.json")
        private = load_json(output / "case-0004/reference.json")
        form["adjudicator"] = "test"
        for row in form["case_verdicts"].values():
            row.update(verdict="pass", reason="Test")
        approve_form(form, "simulation")
        q = quality(reports[0], private, form)
        self.assertEqual(q["status"], "pending")
        self.assertEqual(q["missed_reference_ids"], [])
        form["empty_review"] = {"verdict": "approved", "reason": "Explicitly checked the empty review."}
        approve_form(form, "simulation")
        q = quality(reports[0], private, form)
        self.assertEqual(q["status"], "adjudicated")
        self.assertEqual(q["missed_reference_ids"], ["finding-01"])
        self.assertIsNone(q["finding_precision"]["value"])

    def test_duplicate_coverage_and_precision_exclude_duplicates(self):
        form = self.resolved()
        form["findings"][0].update(verdict="valid", reference_id="finding-01")
        form["findings"][1].update(verdict="duplicate", duplicate_of="f-001")
        approve_form(form, "simulation")
        validate_human(form, self.form(), self.private())
        q = self.q(form)
        self.assertEqual(q["finding_precision"]["denominator"], 1)
        self.assertEqual(q["adjudication_coverage"]["value"], 1)
        self.assertEqual(q["finding_counts"]["duplicate"], 1)

    def test_invalid_matches_and_duplicate_targets_are_rejected(self):
        form = self.resolved()
        for mutate in (
            lambda h: [r.update(verdict="valid", reference_id="finding-01") for r in h["findings"]],
            lambda h: h["findings"][0].update(reference_id="finding-01"),
            lambda h: h["findings"][0].update(verdict="valid", reference_id="unknown"),
            lambda h: h["findings"][0].update(verdict="duplicate", duplicate_of="f-001"),
            lambda h: [r.update(verdict="duplicate", duplicate_of="f-001") for r in h["findings"]],
            lambda h: h["findings"][0].update(verdict="duplicate", duplicate_of="absent"),
            lambda h: h["findings"][0].update(reason=""),
        ):
            bad = copy.deepcopy(form)
            mutate(bad)
            approve_form(bad, "simulation")
            with self.assertRaises(FixtureError):
                validate_human(bad, self.form(), self.private())

    def test_novel_valid_issue_not_false_alarm_on_corrected_case(self):
        self.output = self.root / "clean findings"
        _, self.reports = self.make_run(self.output, clean_texts=("Novel issue", "Incorrect allegation"))
        form = self.resolved("case-0005")
        form["findings"][0].update(verdict="valid")  # novel, NOT a reference match
        approve_form(form, "simulation")
        q = self.q(form, "case-0005")
        self.assertEqual(q["valid_novel_findings"], 1)
        self.assertEqual(q["finding_precision"]["value"], 0.5)
        self.reports[1]["quality"] = q
        summary = aggregate([self.reports[1]])
        false = summary["quality"]["corrected_case_false_alarms"]
        self.assertEqual(false["invalid_findings"], 1)
        self.assertEqual(false["valid_novel_findings"], 1)

    def test_partial_bounds_no_confident_ranking_and_execution_separate(self):
        form = self.resolved()
        form["findings"][1]["verdict"] = "unresolved"
        approve_form(form, "simulation")
        self.reports[0]["quality"] = self.q(form)
        self.reports[1]["status"] = "failed"
        self.reports[1]["quality"] = self.q(self.form("case-0005"), "case-0005")
        summary = aggregate(self.reports)
        q = summary["quality"]
        self.assertEqual(q["confirmed_misses"], 0)
        self.assertEqual(q["pending_defects"], 1)
        self.assertEqual(q["recall_bounds"]["upper"]["value"], 1)
        self.assertEqual(q["precision_bounds"]["upper"]["value"], 0.5)
        self.assertEqual(summary["execution"]["counts"], {"completed": 1, "failed": 1})
        self.assertIsNone(summary["latency"]["mean_ms"])
        self.assertIsNone(summary["cost"]["known_total_usd"])
        self.assertIsNone(summary["ranking"])

    def test_failed_defects_are_unavailable_not_human_confirmed_misses(self):
        self.reports[0]["status"] = "timed_out"
        q = self.q(self.resolved())
        self.assertEqual(q["execution_unavailable_reference_ids"], ["finding-01"])
        self.assertEqual(q["missed_reference_ids"], [])
        self.assertEqual(q["pending_reference_ids"], [])
        self.assertIsNone(q["defect_recall"]["value"])

    def test_stale_retained_artifacts_rejected_before_any_feedback(self):
        for name in ("request.json", "reference.json", "review.json", "review-output.bin"):
            path = self.output / "case-0004" / name
            original = path.read_bytes()
            with self.subTest(name=name), patch("review_reporting.mlflow.log_feedback") as feedback:
                path.write_bytes(original + b" ")
                with self.assertRaisesRegex(FixtureError, "changed"):
                    adjudicate(self.output)
                feedback.assert_not_called()
            path.write_bytes(original)

    def test_stale_form_hashes_and_approval_rejected(self):
        form = self.resolved()
        for field in ("review_sha256", "input_sha256", "reference_sha256"):
            bad = copy.deepcopy(form)
            bad[field] = "stale"
            with self.assertRaisesRegex(FixtureError, "stale"):
                validate_human(bad, self.form(), self.private())
        form["findings"][0]["reason"] = "Changed after sign-off"
        with self.assertRaisesRegex(FixtureError, "stale approval"):
            validate_human(form, self.form(), self.private())

    def test_simulation_and_unsigned_drafts_never_log_human_assessments(self):
        for approved in (False, True):
            form = self.resolved()
            if not approved:
                form["approval"] = None
            self.save_form(form)
            with patch("review_reporting.mlflow.log_feedback") as feedback, patch("review_reporting.mlflow.set_tracking_uri"):
                adjudicate(self.output)
                feedback.assert_not_called()
            q = load_json(self.output / "report.json")["cases"][0]["quality"]
            self.assertEqual(q["status"], "adjudicated" if approved else "pending")

    def test_legacy_forms_preserve_judgments_but_are_drafts_not_human_approval(self):
        form = self.resolved()
        for key in ("input_sha256", "reference_sha256", "approval", "empty_review"):
            del form[key]
        self.save_form(form)
        _, prepared = load_run(self.output)
        migrated = prepared[0][2]
        self.assertEqual(migrated["findings"], form["findings"])
        self.assertIsNone(migrated["approval"])
        self.assertEqual(self.q(migrated)["status"], "pending")
        with patch("review_reporting.mlflow.set_tracking_uri"), patch("review_reporting.mlflow.log_feedback") as feedback:
            adjudicate(self.output)
            feedback.assert_not_called()
        self.assertEqual(self.form(), migrated)

    def scripted_grade(self, answers, case_id="case-0004", practice=True):
        stream = iter(answers)
        messages = []
        def ask(_):
            try:
                return next(stream)
            except StopIteration:
                raise EOFError
        grade(self.output, case_id=case_id, practice=practice, ask=ask, emit=messages.append)
        return "\n".join(messages)

    def test_cli_saves_and_resumes_without_losing_judgments(self):
        view = self.scripted_grade(["yes", "test", "valid", "finding-01", "Same cause and trigger.", "q"])
        form = self.form()
        self.assertEqual(form["findings"][0]["reference_id"], "finding-01")
        self.assertIsNone(form["approval"])
        self.assertIn("CODE s-02:src/request_url.py", view)
        self.assertIn("PRIVATE REFERENCE", view)
        self.assertIn("Unsupported allegation", view)
        self.scripted_grade(["yes", "", "", "", "", "invalid", "No supported defect.",
                             "pass", "Checked context.", "pass", "Checked instructions.", "PRACTICE"])
        form = self.form()
        self.assertEqual(form["findings"][0]["reason"], "Same cause and trigger.")
        self.assertEqual(form["findings"][1]["verdict"], "invalid")
        self.assertEqual(form["approval"]["source"], "simulation")
        self.assertEqual(self.q(form)["finding_precision"]["value"], 0.5)

    def test_cli_empty_approval_and_human_mode_requires_terminal(self):
        self.scripted_grade(["yes", "test", "approved", "Inspected empty review.", "pass", "Context.",
                             "pass", "Instructions.", "PRACTICE"], case_id="case-0005")
        self.assertEqual(self.form("case-0005")["empty_review"]["verdict"], "approved")
        with patch("adjudication_cli.sys.stdin.isatty", return_value=False):
            with self.assertRaisesRegex(FixtureError, "interactive terminal"):
                self.scripted_grade([], practice=False)

    def test_cli_human_confirmation_is_explicit_and_edits_invalidate_it(self):
        with patch("adjudication_cli.sys.stdin.isatty", return_value=True):
            self.scripted_grade(["yes", "test", "invalid", "First reason.", "invalid", "Second reason.",
                                 "pass", "Context.", "pass", "Instructions.", "HUMAN"], practice=False)
        self.assertEqual(self.form()["approval"]["source"], "human")
        self.scripted_grade(["yes", "", "", "Changed reason.", "q"])
        self.assertIsNone(self.form()["approval"])
        self.assertEqual(self.form()["findings"][1]["reason"], "Second reason.")

    def test_cli_rejects_duplicate_reference_without_overwriting_prior_progress(self):
        self.scripted_grade(["yes", "test", "valid", "finding-01", "First match.",
                             "valid", "finding-01", "Second match.", "q"])
        form = self.form()
        self.assertEqual(form["findings"][0]["verdict"], "valid")
        self.assertEqual(form["findings"][1]["verdict"], "unresolved")

    def test_interrupted_atomic_save_preserves_previous_file(self):
        path = self.output / "case-0004/adjudication.json"
        original = path.read_bytes()
        inventory = set(path.parent.iterdir())
        with patch("review_reporting.os.replace", side_effect=OSError("synthetic interruption")):
            with self.assertRaises(OSError):
                save_json(path, self.resolved())
        self.assertEqual(path.read_bytes(), original)
        self.assertEqual(set(path.parent.iterdir()), inventory)

    def test_cli_refuses_to_overwrite_other_session_progress(self):
        path = self.output / "case-0004/adjudication.json"
        concurrent = self.resolved()
        answers = iter(["yes", "test"])
        def ask(_):
            answer = next(answers)
            if answer == "test":
                save_json(path, concurrent)
            return answer
        with self.assertRaisesRegex(FixtureError, "another session"):
            grade(self.output, case_id="case-0004", practice=True, ask=ask, emit=lambda _: None)
        self.assertEqual(load_json(path), concurrent)

    def test_cli_eof_does_not_replace_an_incomplete_judgment(self):
        self.scripted_grade(["yes", "test", "valid", "finding-01"])
        self.assertEqual(self.form()["findings"][0]["verdict"], "unresolved")
        self.assertIsNone(self.form()["approval"])

    def test_cli_unknown_case_and_failed_case_do_not_change_forms(self):
        original = (self.output / "case-0004/adjudication.json").read_bytes()
        with self.assertRaisesRegex(FixtureError, "unknown case"):
            self.scripted_grade([], case_id="case-9999")
        self.reports[0]["status"] = "failed"
        write_reports(self.output, self.manifest, self.reports)
        message = self.scripted_grade([])
        self.assertIn("execution unavailable", message)
        self.assertEqual((self.output / "case-0004/adjudication.json").read_bytes(), original)

    def test_comparison_pending_links_and_compatibility(self):
        other = self.root / "second"
        self.make_run(other)
        target = self.root / "comparison"
        bundle = compare([self.output, other], target)
        self.assertIsNone(bundle["ranking"])
        self.assertEqual(len(bundle["runs"]), 2)
        self.assertEqual(bundle["runs"][0]["aggregate"]["quality"]["pending_cases"], 2)
        text = (target / "report.md").read_text()
        for filename in ("review.json", "reference.json", "trace.json", "adjudication.json"):
            self.assertIn("../first%20run/case-0004/" + filename, text)
        with self.assertRaises(FileExistsError):
            compare([self.output, other], target)
        manifest = load_json(other / "manifest.json")
        manifest["instruction_sha256"] = "different"
        save_json(other / "manifest.json", manifest)
        with self.assertRaisesRegex(FixtureError, "incompatible"):
            compare([self.output, other], self.root / "incompatible")
        self.assertFalse((self.root / "incompatible").exists())

    def test_comparison_requires_import_then_uses_scores_with_practice_label(self):
        self.save_form(self.resolved())
        with self.assertRaisesRegex(FixtureError, "unimported"):
            compare([self.output], self.root / "unimported")
        with patch("review_reporting.mlflow.set_tracking_uri"), patch("review_reporting.mlflow.log_feedback") as feedback:
            adjudicate(self.output)
            adjudicate(self.output)
            feedback.assert_not_called()
        bundle = compare([self.output], self.root / "imported")
        q = bundle["runs"][0]["aggregate"]["quality"]
        self.assertIn("SIMULATION", q["basis"])
        self.assertEqual(q["confirmed_misses"], 1)
        form = self.form()
        form["approval"] = None
        self.save_form(form)
        with self.assertRaisesRegex(FixtureError, "unimported"):
            compare([self.output], self.root / "draft")


if __name__ == "__main__":
    unittest.main()
