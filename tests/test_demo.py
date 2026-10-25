"""Headless demo checks; the optional marimo dependency is not needed for core tests."""

import importlib.util
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(importlib.util.find_spec("marimo"), "install the demo dependency group")
class DemoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from demo import app

        cls.app = app

    def run_notebook(self, **overrides):
        _, definitions = self.app.run(defs={
            name: SimpleNamespace(value=value) for name, value in overrides.items()
        })
        return definitions

    def test_default_view_reads_snapshots_but_not_private_labels_or_executes_code(self):
        original_read_text, original_read_bytes = Path.read_text, Path.read_bytes

        def without_private(reader):
            def guarded(path, *args, **kwargs):
                if path.is_relative_to(ROOT) and "private" in path.parts:
                    self.fail(f"default view read a private artifact: {path}")
                return reader(path, *args, **kwargs)
            return guarded

        with (
            patch.object(Path, "read_text", without_private(original_read_text)),
            patch.object(Path, "read_bytes", without_private(original_read_bytes)),
            patch("reference_checks.query_overrides.load_builder", side_effect=AssertionError("snapshot executed")),
        ):
            definitions = self.run_notebook()
        self.assertEqual(definitions["public"]["case_id"], "case-0004")
        self.assertNotEqual(definitions["before_text"], definitions["after_text"])
        self.assertEqual(definitions["inventory"], [{"path": "src/request_url.py", "status": "modified"}])
        for name in ("private_notes", "probe_failures", "validated_count", "prefix"):
            self.assertIsNone(definitions[name], name)

    def test_every_case_can_be_explored_without_replaying_history(self):
        with patch("reference_checks.query_overrides.load_builder", side_effect=AssertionError("snapshot executed")):
            for collection in ("examples", "fixtures"):
                for path in sorted((ROOT / collection).glob("*/reviewer/input.json")):
                    case = str(path.parent.parent.relative_to(ROOT))
                    with self.subTest(case=case):
                        definitions = self.run_notebook(case_selector=case)
                        self.assertIsNone(definitions["private_notes"])
                        self.assertIsNone(definitions["probe_failures"])
                        if definitions["public"]["start"]["mode"] == "continuation":
                            self.assertEqual(definitions["prefix"]["schema_version"], "ATIF-v1.7")
                            self.assertEqual(definitions["public"]["budgets"]["remaining"]["repository_read_attempts"], 0)
                        else:
                            self.assertIsNone(definitions["prefix"])

    def test_both_diff_layouts_render_with_full_context(self):
        from demo_support.explorer import file_inventory

        definitions = self.run_notebook()
        for layout in ("Side by side", "Unified"):
            with self.subTest(layout=layout):
                _, selected = self.app.run(defs={
                    "diff_layout": SimpleNamespace(value=layout),
                    "full_context": SimpleNamespace(value=True),
                    "file_selector": SimpleNamespace(value="src/request_url.py"),
                    "inventory": file_inventory(definitions["public"]),
                })
                self.assertEqual(selected["before_text"], definitions["before_text"])
                self.assertEqual(selected["after_text"], definitions["after_text"])

    def test_source_display_escapes_html(self):
        from demo_support.rendering import source_block

        html = source_block("<script>alert(1)</script>").text
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)

    def test_reveal_loads_the_selected_private_reference(self):
        for case, outcome in (("case-0004", "defective"), ("case-0005", "clean")):
            with self.subTest(case=case):
                definitions = self.run_notebook(
                    case_selector=f"fixtures/{case}", reveal_labels=True,
                )
                private = definitions["private_notes"]
                self.assertEqual(private["case_id"], case)
                self.assertEqual(private["labels"]["change_outcome"], outcome)
                self.assertEqual(private["provenance"]["verification"]["status"], "pending")
                self.assertIsNone(definitions["probe_failures"])

    def test_probe_button_runs_only_the_trusted_pair_not_the_selected_case(self):
        definitions = self.run_notebook(
            case_selector="examples/case-0003", run_probes=True,
        )
        failures = definitions["probe_failures"]
        self.assertEqual(set(failures), {"case-0004", "case-0005"})
        self.assertEqual(set(failures["case-0004"]), {
            "existing-single", "existing-repeated", "empty-override",
            "encoded-key", "several-overrides", "case-sensitive-keys",
        })
        self.assertEqual(failures["case-0005"], {})

    def test_validation_button_validates_the_whole_dataset_without_execution(self):
        with patch("reference_checks.query_overrides.load_builder", side_effect=AssertionError("snapshot executed")):
            definitions = self.run_notebook(run_validation=True)
        self.assertEqual(definitions["validated_count"], 5)
        self.assertIsNone(definitions["private_notes"])
        self.assertIsNone(definitions["probe_failures"])


if __name__ == "__main__":
    unittest.main()
