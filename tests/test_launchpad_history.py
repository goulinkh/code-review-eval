"""Explicit trusted author checks, not model reviews or independent approval."""

from copy import deepcopy
import sys
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from reference_checks.launchpad_history import (
    ISSUE_PROBES,
    MODULES,
    FakeSink,
    check_case,
    check_issue_links,
    check_metrics,
    load_project,
)
from validate_fixtures import validate_dataset, validate_fixture

ROOT = Path(__file__).resolve().parents[1]
ISSUE_FAILURES = {
    "forge-trailing-slash", "code-trailing-slash", "trailing-query-fragment",
    "trailing-leading-zeroes",
}
METRIC_FAILURES = {"deleted-package", "deleted-bundle", "deleted-hyphenated-prefix"}


class LaunchpadHistoryTests(unittest.TestCase):
    def test_additions_validate_with_the_existing_inventory(self):
        cases = sorted((ROOT / "fixtures").glob("case-*"))
        self.assertTrue(set(MODULES).issubset({p.name for p in cases}))
        self.assertEqual(validate_dataset(cases), len(cases))

    def test_fresh_inline_inputs_preserve_budgets_and_private_boundary(self):
        template, _ = validate_fixture(ROOT / "fixtures/case-0004")
        groups = set()
        for case in MODULES:
            public, private = validate_fixture(ROOT / "fixtures" / case)
            with self.subTest(case=case):
                self.assertEqual(public["protocol"], {"name": "fixed-context", "version": "1.0.0"})
                self.assertEqual(public["start"], {"mode": "fresh"})
                self.assertEqual(public["budgets"], template["budgets"])
                self.assertEqual(public["tools"], [])
                self.assertIsNone(private["expectations"]["continuation"])
                self.assertEqual(private["expectations"]["retrieval"]["requirements"], [])
                self.assertEqual(private["expectations"]["retrieval"]["soft_budget"], {
                    "repository_read_attempts": 0, "returned_bytes": 0, "repeated_reads": 0,
                })
                head_paths = {f["path"] for f in public["snapshots"]["head"]["files"]}
                self.assertEqual({c["path"] for c in public["context_manifest"]}, head_paths)
                for entry in public["context_manifest"]:
                    self.assertEqual((entry["delivery"], entry["availability"]), ("initial", "available"))
                    self.assertIn("content", entry)
                self.assertEqual({p.name for p in (ROOT / "fixtures" / case / "reviewer").iterdir()}, {"input.json"})
                self.assertEqual(private["dataset"]["version"], "0.3.0")
                self.assertEqual(private["dataset"]["partition"], "development")
                self.assertEqual(private["dataset"]["related_cases"], [])
                groups.add(private["dataset"]["group_id"])
                self.assertEqual(private["labels"]["change_outcome"], "defective")
                self.assertEqual(private["expectations"]["context"]["condition"], "self-contained")
                self.assertEqual(len(private["expectations"]["required_findings"]), 1)
                self.assertEqual(private["provenance"]["verification"]["status"], "pending")
                self.assertEqual(private["provenance"]["licence"], "NOASSERTION")
                source = private["provenance"]["sources"][0]
                for key in ("fix_revision", "parent_revision"):
                    self.assertRegex(source[key], r"^[0-9a-f]{40}$")
                self.assertEqual(source["repository"], "https://git.launchpad.net/launchpad")
                self.assertEqual(source["synthesis"], "faithful-reduction")
        self.assertEqual(groups, {"scenario-06", "scenario-07"})

    def test_issue_head_rejects_only_the_supported_trailing_slash_probes(self):
        report = check_case("case-0016")
        self.assertEqual(report.total, 16)
        self.assertEqual(set(report.failures), ISSUE_FAILURES)
        for detail in report.failures.values():
            self.assertTrue(detail.startswith("expected ("), detail)
            self.assertTrue(detail.endswith("got None"), detail)
        self.assertEqual(check_case("case-0016", "base").failures, {})

    def test_metric_head_fails_only_by_the_specific_deleted_build_dereference(self):
        report = check_case("case-0017")
        self.assertEqual(report.total, 8)
        self.assertEqual(set(report.failures), METRIC_FAILURES)
        self.assertEqual(set(report.failures.values()), {
            "deleted build dereferenced as None.kind before metric emission",
        })
        self.assertEqual(check_case("case-0017", "base").failures, {})

    def test_unchanged_issue_spellings_and_invalid_shapes_match_the_base(self):
        base = load_project("case-0016", "base")["issue_links"].parse_issue_url
        head = load_project("case-0016")["issue_links"].parse_issue_url
        checked = 0
        for name, link, expected in ISSUE_PROBES:
            if name not in ISSUE_FAILURES:
                checked += 1
                self.assertEqual(head(link), base(link))
                self.assertEqual(head(link), expected)
        self.assertEqual(checked, 12)

    def test_live_and_manual_metric_behavior_is_unchanged(self):
        base = load_project("case-0017", "base")
        head = load_project("case-0017")
        for kind in (None, "PACKAGE", "BUNDLE", "IMAGE"):
            for seconds in (0, 0.25, 1.25):
                calls = []
                for project in (base, head):
                    record = project["records"]
                    upload = (record.UserUpload("manual") if kind is None else
                              record.BuildUpload(f"batch-with-hyphens-{kind}-7", record.Build(kind)))
                    before = deepcopy(upload)
                    sink = FakeSink()
                    project["metrics"].record_duration(upload, seconds, sink)
                    self.assertEqual(upload, before)
                    self.assertEqual(len(sink.calls), 1)
                    self.assertEqual(sink.calls[0], ("upload_duration", seconds * 1000, {"type": kind or "manual"}))
                    calls.append(sink.calls)
                self.assertEqual(*calls)

    def test_deleted_build_control_uses_surviving_metadata_without_recreation(self):
        project = load_project("case-0017", "base")
        record = project["records"]
        upload = record.BuildUpload("queue-retry-BUNDLE-8", None)
        sink = FakeSink()
        project["metrics"].record_duration(upload, 0, sink)
        self.assertIsNone(upload.build)
        self.assertEqual(sink.calls, [("upload_duration", 0, {"type": "BUNDLE"})])

    def test_unrelated_errors_are_not_counted_as_intended_defects(self):
        with self.assertRaisesRegex(RuntimeError, "unrelated"):
            check_issue_links(lambda link: (_ for _ in ()).throw(RuntimeError("unrelated")))
        project = load_project("case-0017")
        for error in (RuntimeError("unrelated"), AttributeError("wrong attribute", name="other", obj=None)):
            with patch.object(project["metrics"], "record_duration", side_effect=error):
                with self.assertRaises(type(error)):
                    check_metrics(project)
        # Even a fabricated matching error from a broken provider/wrapper does
        # not establish a dereference in the authored metrics module.
        original = project["metrics"].record_duration

        def broken_wrapper(upload, seconds, sink):
            if isinstance(upload, project["records"].BuildUpload) and upload.build is None:
                raise AttributeError("fake", name="kind", obj=None)
            return original(upload, seconds, sink)

        with patch.object(project["metrics"], "record_duration", side_effect=broken_wrapper):
            with self.assertRaisesRegex(AttributeError, "fake"):
                check_metrics(project)

    def test_syntax_and_dependency_failures_propagate(self):
        for source, error in (("def broken(:\n", SyntaxError),
                              ("import nonexistent_history_fixture_dependency\n", ModuleNotFoundError)):
            with patch.object(Path, "read_text", return_value=source):
                with self.assertRaises(error):
                    load_project("case-0016")

    def test_loader_restores_local_imports_and_refuses_unknown_inputs(self):
        before = {name: sys.modules.get(name) for name in ("issue_links", "records", "metrics")}
        for case in MODULES:
            load_project(case)
        self.assertEqual(before, {name: sys.modules.get(name) for name in before})
        for case, side in (("case-9999", "head"), ("case-0016", "../private")):
            with self.assertRaises(ValueError):
                load_project(case, side)

    def test_entire_expanded_inventory_exports_only_public_requests(self):
        from run_eval import REQUEST_MARKER, prepare
        cases = sorted((ROOT / "fixtures").glob("case-*"))
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "prepared"
            prepare(cases, output)  # No Job/agent/container/model execution.
            for case in cases:
                task = output / "tasks" / case.name
                self.assertEqual({p.relative_to(task).as_posix() for p in task.rglob("*") if p.is_file()}, {
                    "instruction.md", "task.toml", "environment/Dockerfile", "tests/test.sh",
                })
                request = (case / "reviewer/input.json").read_text()
                self.assertEqual((task / "instruction.md").read_text().split(REQUEST_MARKER, 1)[1], request)
                for artifact in task.rglob("*"):
                    if artifact.is_file():
                        for private_term in ("required_findings", "discoverable_because", "fix_revision", "NOASSERTION"):
                            self.assertNotIn(private_term, artifact.read_text())


if __name__ == "__main__":
    unittest.main()
