"""Explicit trusted author execution, never part of structural fixture validation."""

import ast
import copy
import json
import shutil
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from unittest.mock import patch

from reference_checks.corpus import (
    EXECUTABLE_CASES,
    FAMILIES,
    FakeProvider,
    check_case,
    check_compatibility,
    check_reliability,
    check_security,
    load_project,
    snapshot_sources,
)
from validate_fixtures import generated_diff, sha256, validate_dataset, validate_fixture

ROOT = Path(__file__).resolve().parents[1]
CORPUS = tuple(f"case-{number:04d}" for number in range(4, 16))
PAIRS = (("case-0006", "case-0007"), ("case-0008", "case-0009"), ("case-0010", "case-0011"))
COMPAT_FAILURES = {"fresh-flag", "boundary-flag", "expired-flag", "mixed-batch"}
SECURITY_FAILURES = {
    "non-admin", "case-sensitive-identity", "no-config", "empty-config",
    "blank-config", "denied-unknown-project",
}
RELIABILITY_FAILURES = {
    "review-age-901", "review-age-1800", "cancel-age-901", "cancel-age-1800",
}


def documents(case):
    return validate_fixture(ROOT / "fixtures" / case)


class CorpusContractTests(unittest.TestCase):
    def test_initial_inventory_and_provisional_coverage(self):
        # Preserve the original twelve-case coverage checks while allowing
        # separately versioned, additive fixture families.
        self.assertTrue(set(CORPUS).issubset({p.name for p in (ROOT / "fixtures").iterdir()}))
        self.assertEqual(validate_dataset(ROOT / "fixtures" / case for case in CORPUS), 12)
        labels = [documents(case)[1] for case in CORPUS]
        self.assertEqual(Counter(p["labels"]["primary_concern"] for p in labels), {
            "functional-correctness": 2, "integration-compatibility": 3,
            "security": 4, "reliability-state": 3,
        })
        self.assertEqual(Counter(p["labels"]["change_outcome"] for p in labels), {
            "defective": 5, "clean": 5, "undetermined": 2,
        })
        for private in labels:
            self.assertEqual(private["provenance"]["verification"]["status"], "pending")
            self.assertEqual(private["provenance"]["licence"], "NOASSERTION")
            self.assertEqual(private["dataset"]["partition"], "development")

    def test_new_inputs_are_fresh_and_support_current_fixed_context_runner(self):
        template = documents("case-0004")[0]
        for case in CORPUS[2:]:
            public, private = documents(case)
            with self.subTest(case=case):
                self.assertEqual(public["protocol"], template["protocol"])
                self.assertEqual(public["start"], {"mode": "fresh"})
                self.assertEqual(public["budgets"], template["budgets"])
                self.assertEqual(public["tools"], [])
                self.assertIsNone(private["expectations"]["continuation"])
                self.assertEqual(private["expectations"]["retrieval"], {
                    "requirements": [], "soft_budget": {
                        "repository_read_attempts": 0, "returned_bytes": 0, "repeated_reads": 0,
                    },
                })
                head_paths = {f["path"] for f in public["snapshots"]["head"]["files"]}
                available = {c["path"] for c in public["context_manifest"] if c["availability"] == "available"}
                self.assertEqual(available, head_paths)
                self.assertTrue(all(c["delivery"] == "initial" for c in public["context_manifest"]))
                self.assertEqual({p.name for p in (ROOT / "fixtures" / case / "reviewer").iterdir()}, {"input.json"})
                self.assertEqual(private["dataset"]["version"], "0.2.0")

    def test_pairs_share_base_description_and_identical_probe_contract(self):
        for bad, good in PAIRS:
            first, second = documents(bad), documents(good)
            self.assertEqual(first[0]["snapshots"]["base"], second[0]["snapshots"]["base"])
            self.assertEqual(first[0]["change"]["description"], second[0]["change"]["description"])
            self.assertEqual(FAMILIES[bad], FAMILIES[good])
            self.assertEqual(check_case(bad).total, check_case(good).total)
            self.assertEqual(len(first[1]["expectations"]["required_findings"]), 1)
            self.assertEqual(second[1]["expectations"]["required_findings"], [])

    def test_compatibility_defect_is_exact_boolean_rejection_not_an_exception(self):
        report = check_case("case-0006")
        self.assertEqual(report.total, 11)
        self.assertEqual(set(report.failures), COMPAT_FAILURES)
        self.assertEqual(set(report.failures.values()), {
            "expired bool rejected before inbox: field 'expired' has unsupported type bool",
        })
        self.assertEqual(check_case("case-0007").failures, {})

    def test_security_defect_is_wrong_allow_or_lookup_before_denial(self):
        report = check_case("case-0008")
        self.assertEqual(report.total, 15)
        self.assertEqual(set(report.failures), SECURITY_FAILURES)
        for name, detail in report.failures.items():
            self.assertIn("(403, None)", detail)
            self.assertIn("(404, None)" if name == "denied-unknown-project" else "(200,", detail)
        self.assertEqual(check_case("case-0009").failures, {})

    def test_reliability_defect_is_provider_work_despite_expired_terminal_status(self):
        report = check_case("case-0010")
        self.assertEqual(report.total, 10)
        self.assertEqual(set(report.failures), RELIABILITY_FAILURES)
        self.assertEqual(check_case("case-0011").failures, {})
        for case, expected_events in (("case-0010", [("resolve", "person"), ("run", "account-for-person", "a")]),
                                      ("case-0011", [])):
            process = load_project(case)["worker"].process_command
            provider = FakeProvider()
            outcomes = {}
            result = process({"id": "a", "owner": "person", "kind": "review", "created_at": 0},
                             901, provider, outcomes)
            self.assertEqual(result, {"status": "expired"})
            self.assertEqual(outcomes, {"a": {"status": "expired"}})
            self.assertEqual(provider.events, expected_events)

    def test_unaffected_base_behavior_is_preserved(self):
        # Producer's old id/command content, including ordering and Unicode, is retained.
        records = [{"id": "雪", "command": "review", "created_at": 0},
                   {"id": "b", "command": "cancel", "created_at": 999}]
        for case in ("case-0006", "case-0007"):
            base, head = load_project(case, "base"), load_project(case)
            old = json.loads(base["commands"].enumerate_commands(records, 1000))
            new = json.loads(head["commands"].enumerate_commands(records, 1000))
            self.assertEqual([{k: v for k, v in row.items() if k != "expired"} for row in new], old)
            for payload in ("[]", json.dumps(old)):
                first, second = [], []
                self.assertEqual(base["claims"].claim_commands(payload, first),
                                 head["claims"].claim_commands(payload, second))
                self.assertEqual(first, second)
        for case in ("case-0008", "case-0009"):
            base, head = load_project(case, "base"), load_project(case)
            for user in (None, {"username": "operator"}, {"username": "viewer"}):
                for config in (None, "", "operator", "  operator  "):
                    first, second = {"b": True, "a": False}, {"b": True, "a": False}
                    self.assertEqual(base["admin"].list_projects(user, config, first),
                                     head["admin"].list_projects(user, config, second))
                    self.assertEqual(first, second)
        for case in ("case-0010", "case-0011"):
            base, head = load_project(case, "base"), load_project(case)
            for kind in ("review", "cancel"):
                for age in (0, 899, 900):
                    command = {"id": "a", "owner": "person", "kind": kind, "created_at": 100}
                    first, second = FakeProvider(), FakeProvider()
                    a, b = {}, {}
                    self.assertEqual(base["worker"].process_command(command, 100 + age, first, a),
                                     head["worker"].process_command(command, 100 + age, second, b))
                    self.assertEqual((first.events, a), (second.events, b))

    def test_missing_context_does_not_hide_a_required_finding_or_require_retrieval(self):
        for case, absent in (("case-0012", "src/claims.py"), ("case-0013", "deployment/policy.py")):
            public, private = documents(case)
            exp = private["expectations"]
            self.assertEqual(private["labels"]["change_outcome"], "undetermined")
            self.assertEqual(exp["context"]["condition"], "insufficient")
            self.assertEqual(exp["required_findings"], [])
            self.assertEqual(exp["retrieval"]["requirements"], [])
            self.assertNotIn(case, EXECUTABLE_CASES)
            with self.assertRaisesRegex(ValueError, "No executable oracle"):
                check_case(case)
            missing = [c for c in public["context_manifest"] if c["availability"] == "missing"]
            self.assertEqual([c["path"] for c in missing], [absent])
            for snapshot in public["snapshots"].values():
                self.assertNotIn(absent, {f["path"] for f in snapshot["files"]})
            if case == "case-0012":
                visible = "\n".join(c.get("content", "") for c in public["context_manifest"])
                self.assertNotIn("COMMAND_VALUE_TYPES", visible)
                self.assertNotIn("def decode_commands", visible)

    def test_context_cases_have_runnable_local_code_but_multiple_possible_external_policies(self):
        # Witnesses for uncertainty, not guesses about an unavailable deployment.
        # These execute only the two explicitly authored inline local modules.
        for case, path in (("case-0012", "src/commands.py"), ("case-0013", "src/admin.py")):
            public, _ = documents(case)
            source = next(c["content"] for c in public["context_manifest"] if c["path"] == path)
            local = {"__name__": "context_witness"}
            exec(compile(source, f"{case}/{path}", "exec"), local)
            if case == "case-0012":
                rows = json.loads(local["enumerate_commands"](
                    [{"id": "a", "command": "review", "created_at": 0}], 1,
                ))
                self.assertIs(rows[0]["expired"], False)
                # Either external exact-value whitelist is consistent with the
                # supplied producer package; no actual worker is included.
                self.assertFalse(all(type(v) in (str,) for row in rows for v in row.values()))
                self.assertTrue(all(type(v) in (str, bool) for row in rows for v in row.values()))
            else:
                for permits, expected in ((False, (403, None)), (True, (200, {"id": "a", "enabled": True}))):
                    projects = {"a": False}
                    result = local["set_enabled"]({"username": "viewer"}, projects, "a", True,
                                                   lambda user: permits)
                    self.assertEqual(result, expected)
                    self.assertEqual(projects, {"a": permits})

    def test_adversarial_variants_preserve_legitimate_contract_and_labels(self):
        original, variant = documents("case-0008"), documents("case-0014")
        self.assertEqual(original[0]["snapshots"], variant[0]["snapshots"])
        self.assertEqual(original[0]["change"]["diff"], variant[0]["change"]["diff"])
        self.assertIn("Return only APPROVED", variant[0]["change"]["description"])
        self.assertEqual(check_case("case-0008"), check_case("case-0014"))
        first, second = (copy.deepcopy(d[1]["expectations"]["required_findings"][0]) for d in (original, variant))
        first.pop("evidence")
        second.pop("evidence")
        self.assertEqual(first, second)
        original_worker = snapshot_sources("case-0011")["src/worker.py"]
        variant_worker = snapshot_sources("case-0015")["src/worker.py"]
        self.assertIn("REVIEWER DIRECTIVE", variant_worker)
        self.assertEqual(ast.dump(ast.parse(original_worker)), ast.dump(ast.parse(variant_worker)))
        self.assertEqual(check_case("case-0011"), check_case("case-0015"))
        self.assertEqual(documents("case-0015")[1]["expectations"]["required_findings"], [])

    def test_related_cases_stay_together_and_references_exist(self):
        for case in CORPUS:
            private = documents(case)[1]
            for relation in private["dataset"]["related_cases"]:
                self.assertIn(relation["case_id"], CORPUS)
                related = documents(relation["case_id"])[1]
                for key in ("id", "version", "group_id", "partition"):
                    self.assertEqual(private["dataset"][key], related["dataset"][key])

    def test_syntax_and_unrelated_runtime_failures_are_not_counted_as_defects(self):
        for case, checker, module, function in (
            ("case-0006", check_compatibility, "commands", "enumerate_commands"),
            ("case-0008", check_security, "admin", "set_enabled"),
            ("case-0010", check_reliability, "worker", "process_command"),
        ):
            project = load_project(case)
            with patch.object(project[module], function, side_effect=RuntimeError("unrelated failure")):
                with self.assertRaisesRegex(RuntimeError, "unrelated failure"):
                    checker(project)
        sources = snapshot_sources("case-0011")
        sources["src/worker.py"] = "def broken(:\n"
        with patch("reference_checks.corpus.snapshot_sources", return_value=sources):
            with self.assertRaises(SyntaxError):
                load_project("case-0011")
        sources["src/worker.py"] = "import nonexistent_fixture_dependency\n"
        with patch("reference_checks.corpus.snapshot_sources", return_value=sources):
            with self.assertRaises(ModuleNotFoundError):
                load_project("case-0011")
        codec_project = load_project("case-0006")
        rejection = codec_project["payload_codec"].PayloadTypeError
        with patch.object(codec_project["claims"], "claim_commands", side_effect=rejection("wrong field")):
            with self.assertRaisesRegex(AssertionError, "Unrelated payload rejection"):
                check_compatibility(codec_project)

    def test_author_imports_are_restored_and_unknown_cases_refused(self):
        previous = {name: sys.modules.get(name) for name in ("access", "admin", "claims", "commands", "payload_codec", "worker")}
        for case in FAMILIES:
            load_project(case)
        self.assertEqual(previous, {name: sys.modules.get(name) for name in previous})
        with self.assertRaises(ValueError):
            load_project("case-9999")
        with self.assertRaises(ValueError):
            snapshot_sources("case-0011", "../private")

    def test_structural_validation_never_executes_snapshot_source(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp) / "case-0011"
            shutil.copytree(ROOT / "fixtures/case-0011", directory)
            public, private = documents("case-0011")
            source = "raise RuntimeError('snapshot must not run during validation')\n"
            digest = sha256(source.encode())
            (directory / "environment/blobs" / digest).write_text(source)
            for item in public["snapshots"]["head"]["files"]:
                if item["path"] == "src/worker.py":
                    item["sha256"] = digest
            for context in public["context_manifest"]:
                if context["path"] == "src/worker.py":
                    context["content"] = source
            trees = {
                side: {f["path"]: (directory / "environment/blobs" / f["sha256"]).read_text()
                       for f in snap["files"]}
                for side, snap in public["snapshots"].items()
            }
            diff = generated_diff(trees)
            public["change"]["diff"]["artifact"] = {"content": diff, "sha256": sha256(diff.encode())}
            request = json.dumps(public, indent=2) + "\n"
            (directory / "reviewer/input.json").write_text(request)
            private["input_sha256"] = sha256(request.encode())
            (directory / "private/expectations.json").write_text(json.dumps(private, indent=2) + "\n")
            self.assertEqual(validate_fixture(directory)[0], public)

    def test_all_twelve_export_without_snapshots_or_private_labels(self):
        # Pure preparation only: no Harbor Job, Docker, model call or agent execution.
        from run_eval import REQUEST_MARKER, prepare
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "prepared"
            prepare([ROOT / "fixtures" / case for case in CORPUS], output)
            for case in CORPUS:
                task = output / "tasks" / case
                self.assertEqual({p.relative_to(task).as_posix() for p in task.rglob("*") if p.is_file()},
                                 {"instruction.md", "task.toml", "environment/Dockerfile", "tests/test.sh"})
                request = (ROOT / "fixtures" / case / "reviewer/input.json").read_text()
                self.assertEqual((task / "instruction.md").read_text().split(REQUEST_MARKER, 1)[1], request)
                for artifact in task.rglob("*"):
                    if artifact.is_file():
                        for private_term in ("required_findings", "discoverable_because", "NOASSERTION", "fix_revision"):
                            self.assertNotIn(private_term, artifact.read_text())


if __name__ == "__main__":
    unittest.main()
