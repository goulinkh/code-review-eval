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
        self.assertEqual(definitions["selected_file"], "src/request_url.py")
        self.assertIn('class="fixture-file-tree"', definitions["file_tree"].text)
        viewer = definitions["explorer_view"].text
        self.assertLess(viewer.index('<nav class="fixture-file-tree"'), viewer.index("<marimo-tabs"))
        self.assertNotIn("marimo-sidebar", viewer)
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
        definitions = self.run_notebook()
        for layout in ("Side by side", "Unified"):
            with self.subTest(layout=layout):
                _, selected = self.app.run(defs={
                    "diff_layout": SimpleNamespace(value=layout),
                    "full_context": SimpleNamespace(value=True),
                    "selected_file": "src/request_url.py",
                })
                self.assertEqual(selected["before_text"], definitions["before_text"])
                self.assertEqual(selected["after_text"], definitions["after_text"])

    def test_selecting_each_tree_path_loads_the_matching_snapshots(self):
        from demo_support.explorer import read_snapshot_text

        definitions = self.run_notebook(case_selector="fixtures/case-0007")
        self.assertGreater(len(definitions["inventory"]), 1)
        for item in definitions["inventory"]:
            with self.subTest(path=item["path"]):
                _, selected = self.app.run(defs={
                    "case_selector": SimpleNamespace(value="fixtures/case-0007"),
                    "selected_file": item["path"],
                })
                for side, name in (("base", "before_text"), ("head", "after_text")):
                    expected = read_snapshot_text(selected["case_dir"], selected["public"], side, item["path"])
                    self.assertEqual(selected[name], expected)
                self.assertIsNone(selected["private_notes"])
                self.assertIsNone(selected["probe_failures"])

    def test_changing_fixture_resets_selection_to_its_first_inventory_path(self):
        for case in ("case-0004", "case-0007", "case-0005"):
            with self.subTest(case=case):
                definitions = self.run_notebook(case_selector=f"fixtures/{case}")
                self.assertEqual(definitions["selected_file"], definitions["inventory"][0]["path"])

    def test_empty_file_tree_does_not_attempt_snapshot_reads(self):
        with patch("demo_support.explorer.read_snapshot_text", side_effect=AssertionError("snapshot read")):
            _, definitions = self.app.run(defs={
                "inventory": [],
                "get_selected_file": lambda: None,
                "set_selected_file": lambda _: None,
            })
        self.assertIsNone(definitions["selected_file"])
        self.assertIsNone(definitions["before_text"])
        self.assertIsNone(definitions["after_text"])
        self.assertIn("No snapshot files.", definitions["file_tree"].text)

    def test_source_display_escapes_html(self):
        from demo_support.rendering import source_block

        html = source_block("<script>alert(1)</script>").text
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)

    def test_source_display_highlights_python_and_json_as_escaped_data(self):
        from demo_support.rendering import source_block

        python = source_block('def render():\n    return "<script>"\n', path="src/render.py").text
        self.assertIn('<span class="k">def</span>', python)
        self.assertIn('<span class="nf">render</span>', python)
        self.assertNotIn("<script>", python)
        self.assertIn("&lt;script&gt;", python)
        json = source_block('{"count": 42}', language="json").text
        self.assertIn('<span class="nt">&quot;count&quot;</span>', json)
        self.assertIn('<span class="mi">42</span>', json)

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
        expected_count = sum(
            1 for collection in ("examples", "fixtures")
            for _ in (ROOT / collection).glob("*/reviewer/input.json")
        )
        self.assertEqual(definitions["validated_count"], expected_count)
        self.assertIsNone(definitions["private_notes"])
        self.assertIsNone(definitions["probe_failures"])


if __name__ == "__main__":
    unittest.main()
