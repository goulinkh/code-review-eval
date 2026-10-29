"""Saved model comparisons are display data, never a reason to run a model."""

import copy
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from demo_support.results import (
    discover_reports,
    load_pilot_comparison,
    pilot_model_rows,
    pilot_repetition_rows,
)
from validate_fixtures import FixtureError

ROOT = Path(__file__).resolve().parents[1]


def comparison():
    def model(name):
        return {
            "model_id": name,
            "attempted": 2,
            "finished": 2,
            "execution_counts": {"completed": 1, "invalid_output": 1},
            "latency_ms": {"min": 100, "median": 150, "max": 200},
            "known_billed_cost_usd": 0.001,
            "unknown_billed_cost_invocations": 0,
            "usage": {
                "input_tokens": {"known_total": 1000, "unknown_invocations": 0},
                "output_tokens": {"known_total": 100, "unknown_invocations": 0},
            },
            "quality": {"status": "pending", "recall": None, "precision": None,
                        "corrected_case_false_alarm_cases": None},
            "variation_by_case": {
                "case-0004": {"status_by_repetition": {"1": "completed"},
                              "finding_counts": [2], "distinct_normalized_review_hashes": 1},
                "case-0005": {"status_by_repetition": {"1": "invalid_output"},
                              "finding_counts": [None], "distinct_normalized_review_hashes": 0},
            },
        }
    return {"models": [model("qwen/example"), model("mistral/example")],
            "planned_invocations": 12, "ledger_entries": 4,
            "ranking": None, "ranking_status": "pending human adjudication"}


class PilotResultTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / "experiments/pilot/comparison.json"
        self.path.parent.mkdir(parents=True)
        self.bundle = comparison()
        self.path.write_text(json.dumps(self.bundle))

    def test_discovery_prefers_real_experiments_without_reading_results(self):
        newer = self.root / "experiments/pilot-z/comparison.json"
        newer.parent.mkdir()
        newer.write_text("not even JSON; discovery must not read it")
        demo = self.root / "runs/demo/visuals.json"
        demo.parent.mkdir(parents=True)
        demo.write_text("not read either")
        with patch.object(Path, "read_text", side_effect=AssertionError("read report")), patch.object(
                Path, "read_bytes", side_effect=AssertionError("read report")):
            reports = discover_reports(self.root)
        self.assertEqual(reports, ["experiments/pilot-z/comparison.json",
                                  "experiments/pilot/comparison.json", "runs/demo/visuals.json"])

    def test_loader_is_project_confined_and_does_not_follow_evidence(self):
        self.assertEqual(load_pilot_comparison(self.path, self.root), self.bundle)
        with self.assertRaisesRegex(FixtureError, "inside this project"):
            load_pilot_comparison("../outside.json", self.root)
        escape = self.root / "experiments/escape/comparison.json"
        escape.parent.mkdir()
        escape.symlink_to(self.root.parent / "outside.json")
        self.assertNotIn("experiments/escape/comparison.json", discover_reports(self.root))
        with self.assertRaisesRegex(FixtureError, "inside this project"):
            load_pilot_comparison(escape, self.root)

    def test_invalid_summaries_and_duplicate_keys_are_rejected(self):
        mutations = [
            lambda b: b.update(models=[]),
            lambda b: b["models"].append(copy.deepcopy(b["models"][0])),
            lambda b: b["models"][0].update(finished=3),
            lambda b: b["models"][0].update(known_billed_cost_usd=float("inf")),
            lambda b: b["models"][0]["quality"].update(precision={"value": 1.5}),
        ]
        for mutate in mutations:
            bad = copy.deepcopy(self.bundle)
            mutate(bad)
            self.path.write_text(json.dumps(bad))
            with self.subTest(mutation=mutate), self.assertRaises(FixtureError):
                load_pilot_comparison(self.path, self.root)
        self.path.write_text('{"models":[],"models":[]}')
        with self.assertRaisesRegex(FixtureError, "duplicate JSON key"):
            load_pilot_comparison(self.path, self.root)

    def test_pending_quality_is_not_zero_and_source_model_order_is_preserved(self):
        rows = pilot_model_rows(self.bundle)
        self.assertEqual([r["Model"] for r in rows], ["qwen/example", "mistral/example"])
        self.assertEqual(rows[0]["Finished / attempted"], "2/2")
        self.assertEqual(rows[0]["Completed"], 1)
        self.assertEqual(rows[0]["Failed / invalid / timed out"], 1)
        for row in rows:
            self.assertEqual(row["Recall"], "Pending")
            self.assertEqual(row["Precision"], "Pending")
            self.assertEqual(row["Corrected-case false alarms"], "Pending")
            self.assertNotIn("Rank", row)
        repetitions = pilot_repetition_rows(self.bundle)
        self.assertEqual(len(repetitions), 4)
        self.assertEqual(repetitions[1]["Finding counts (not scores)"], "[null]")

    def test_unknown_telemetry_and_unstarted_models_do_not_appear_free(self):
        model = self.bundle["models"][0]
        model["unknown_billed_cost_invocations"] = 2
        model["known_billed_cost_usd"] = 0
        model["usage"]["input_tokens"].update(known_total=None, unknown_invocations=2)
        model["usage"]["output_tokens"].update(known_total=None, runtime_zero_without_provider_response=2)
        self.path.write_text(json.dumps(self.bundle))
        self.assertEqual(load_pilot_comparison(self.path, self.root), self.bundle)
        row = pilot_model_rows(self.bundle)[0]
        self.assertEqual(row["OpenRouter billed subtotal"], "Unknown")
        self.assertEqual(row["Input tokens"], "Unknown")
        self.assertEqual(row["Output tokens"], "Unknown")
        model.update(attempted=0, finished=0, execution_counts={}, latency_ms=None)
        row = pilot_model_rows(self.bundle)[0]
        self.assertEqual(row["OpenRouter billed subtotal"], "Not finished")
        self.assertEqual(row["Median latency (ms)"], "Unknown")

    def test_only_reported_adjudicated_quality_is_formatted_as_a_score(self):
        self.bundle["models"][0]["quality"] = {
            "status": "adjudicated", "recall": {"value": 1},
            "precision": {"value": 0.5},
            "corrected_case_false_alarm_cases": {"count": 1, "adjudicated_completed_cases": 3},
        }
        row = pilot_model_rows(self.bundle)[0]
        self.assertEqual((row["Recall"], row["Precision"]), ("100.0%", "50.0%"))
        self.assertEqual(row["Corrected-case false alarms"], "1/3")


@unittest.skipUnless(importlib.util.find_spec("marimo"), "install the demo dependency group")
class PilotNotebookTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from demo import app
        cls.app = app

    def test_real_comparison_is_selected_but_not_read_without_opt_in(self):
        reports = ["experiments/pilot/comparison.json", "runs/demo/visuals.json"]
        with patch("demo_support.results.discover_reports", return_value=reports), patch(
                "demo_support.results.load_pilot_comparison", side_effect=AssertionError("loaded by default")):
            _, definitions = self.app.run()
        self.assertEqual(definitions["report_selector"].value, reports[0])
        self.assertEqual(definitions["results_path"].value, reports[0])
        self.assertIsNone(definitions["pilot_comparison"])
        self.assertIsNone(definitions["visual_results"])
        self.assertIsNone(definitions["results_error"])

    def test_opt_in_shows_model_comparison_and_main_report_without_execution(self):
        bundle = comparison()
        with patch("demo_support.results.load_pilot_comparison", return_value=bundle) as loader, patch(
                "demo_support.results.load_report_text", return_value="# Saved model comparison") as text, patch(
                "reference_checks.query_overrides.load_builder", side_effect=AssertionError("executed snapshot")):
            _, definitions = self.app.run(defs={
                "load_results": SimpleNamespace(value=True),
                "results_path": SimpleNamespace(value="experiments/pilot/comparison.json"),
            })
        loader.assert_called_once_with("experiments/pilot/comparison.json", ROOT)
        text.assert_called_once_with(ROOT / "experiments/pilot/comparison.md", ROOT)
        self.assertEqual(definitions["pilot_comparison"], bundle)
        self.assertIsNone(definitions["visual_results"])
        self.assertIsNone(definitions["results_error"])
        self.assertIsNone(definitions["private_notes"])
        self.assertIsNone(definitions["probe_failures"])
        self.assertIn("pending human adjudication", definitions["results_view"].text)
        self.assertIn("comparison.md", definitions["results_view"].text)

    def test_pilot_load_error_does_not_hide_the_fixture_explorer(self):
        with patch("demo_support.results.load_pilot_comparison", side_effect=FixtureError("invalid model summary")):
            _, definitions = self.app.run(defs={
                "load_results": SimpleNamespace(value=True),
                "results_path": SimpleNamespace(value="experiments/pilot/comparison.json"),
            })
        self.assertIn("invalid model summary", definitions["results_error"])
        self.assertIsNone(definitions["pilot_comparison"])
        self.assertEqual(definitions["public"]["case_id"], "case-0004")


if __name__ == "__main__":
    unittest.main()
