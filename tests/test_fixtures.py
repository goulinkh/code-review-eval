import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from validate_fixtures import (
    VALIDATORS,
    FixtureError,
    check_schema,
    sha256,
    strict_json,
    validate_dataset,
    validate_fixture,
)

ROOT = Path(__file__).resolve().parents[1]


class FixtureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        shutil.copytree(ROOT / "examples", self.root / "examples")
        self.case = self.root / "examples/case-0003"
        self.public = self.load("reviewer/input.json")
        self.private = self.load("private/expectations.json")
        self.prefix = self.load("reviewer/prefix.json")

    def load(self, path):
        return json.loads((self.case / path).read_text())

    def write(self, path, value):
        (self.case / path).write_text(json.dumps(value, indent=2) + "\n")

    def save(self):
        self.write("reviewer/prefix.json", self.prefix)
        self.public["start"]["prefix"]["sha256"] = sha256((self.case / "reviewer/prefix.json").read_bytes())
        self.write("reviewer/input.json", self.public)
        self.private["input_sha256"] = sha256((self.case / "reviewer/input.json").read_bytes())
        self.write("private/expectations.json", self.private)

    def invalid(self, message):
        self.save()
        with self.assertRaisesRegex(FixtureError, message):
            validate_fixture(self.case)

    def result(self):
        return self.prefix["steps"][1]["observation"]["results"][0]

    def read(self):
        return self.result()["extra"]["code_review_eval"]["repository_reads"][0]

    def test_all_examples_validate_offline(self):
        self.assertEqual(validate_dataset(sorted((self.root / "examples").iterdir())), 3)
        self.assertEqual(set(VALIDATORS), {
            "common", "atif-prefix", "expectations", "review", "reviewer-input", "visual-report",
        })

    def test_closed_reviewer_schema_rejects_private_labels(self):
        self.public["expectations"] = self.private["expectations"]
        self.invalid("Additional properties")

    def test_private_artifact_cannot_be_added_to_reviewer_directory(self):
        self.write("reviewer/expectations.json", self.private)
        self.invalid("unexpected or missing reviewer artifact")

    def test_prefix_hash_is_checked(self):
        path = self.case / "reviewer/prefix.json"
        path.write_bytes(path.read_bytes() + b" ")
        with self.assertRaisesRegex(FixtureError, "prefix hash mismatch"):
            validate_fixture(self.case)

    def test_input_is_bound_to_private_expectations(self):
        self.private["input_sha256"] = "0" * 64
        self.write("private/expectations.json", self.private)
        with self.assertRaisesRegex(FixtureError, "input_sha256 mismatch"):
            validate_fixture(self.case)

    def test_private_and_public_identifiers_must_agree(self):
        self.private["case_id"] = "case-9999"
        self.invalid("case_id mismatch")

    def test_reasoning_is_not_checkpoint_data(self):
        self.prefix["steps"][1]["reasoning_content"] = "private reasoning"
        self.invalid("Additional properties")

    def test_native_roles_are_not_invented_atif_roles(self):
        self.prefix["steps"][1]["source"] = "assistant"
        self.invalid("atif-prefix")

    def test_in_flight_checkpoint_is_rejected(self):
        del self.prefix["steps"][1]["observation"]
        self.invalid("atif-prefix")

    def test_call_and_result_associations_are_preserved(self):
        self.result()["source_call_id"] = "call-other"
        self.invalid("exactly one result")

    def test_duplicate_result_is_rejected(self):
        self.prefix["steps"][1]["observation"]["results"].append(copy.deepcopy(self.result()))
        self.invalid("exactly one result")

    def test_call_ids_are_globally_unique(self):
        duplicate = copy.deepcopy(self.prefix["steps"][1])
        duplicate["step_id"] = 3
        self.prefix["steps"].append(duplicate)
        self.invalid("duplicate ATIF tool_call_id")

    def test_step_ids_are_sequential(self):
        self.prefix["steps"][1]["step_id"] = 4
        self.invalid("sequential")

    def test_historical_steps_are_marked_copied(self):
        self.prefix["steps"][0]["is_copied_context"] = False
        self.invalid("atif-prefix")

    def test_checkpoint_snapshots_are_pinned(self):
        self.public["start"]["snapshots"]["head"] = "s-other"
        self.invalid("checkpoint snapshot mismatch")

    def test_read_snapshot_must_match_requested_revision(self):
        self.read()["resolved_snapshot_id"] = "s-01"
        self.invalid("revision/snapshot mismatch")

    def test_read_bytes_must_match_snapshot(self):
        self.read()["content_sha256"] = "0" * 64
        self.invalid("immutable snapshot bytes")

    def test_read_content_must_have_been_visible(self):
        self.result()["content"] = "an invented summary"
        self.invalid("evidence absent from output")

    def test_success_requires_available_manifest_entry(self):
        self.public["context_manifest"] = []
        self.invalid("not available in manifest")

    def test_declared_tool_is_required(self):
        self.public["tools"][0]["name"] = "another-tool"
        self.invalid("undeclared tool")

    def test_whole_path_budget_does_not_reset(self):
        self.public["budgets"]["remaining"]["tool_calls"] = 1
        self.invalid("infeasible remaining budget")

    def test_negative_remaining_budget_is_rejected(self):
        self.public["budgets"]["remaining"]["returned_bytes"] = -1
        self.invalid("reviewer-input")

    def test_inherited_usage_must_match_history(self):
        self.public["budgets"]["inherited"]["repository_read_attempts"] = 0
        self.invalid("inherited repository_read_attempts")

    def test_inherited_elapsed_time_cannot_exclude_recorded_calls(self):
        self.public["budgets"]["inherited"]["wall_time_ms"] = 0
        self.public["budgets"]["remaining"]["wall_time_ms"] = 30000
        self.invalid("inherited wall time")

    def test_fresh_usage_is_not_inherited(self):
        case = self.root / "examples/case-0001"
        path = case / "reviewer/input.json"
        public = json.loads(path.read_text())
        public["budgets"]["inherited"]["wall_time_ms"] = 1
        public["budgets"]["remaining"]["wall_time_ms"] -= 1
        path.write_text(json.dumps(public) + "\n")
        private_path = case / "private/expectations.json"
        private = json.loads(private_path.read_text())
        private["input_sha256"] = sha256(path.read_bytes())
        private_path.write_text(json.dumps(private) + "\n")
        with self.assertRaisesRegex(FixtureError, "fresh inherited"):
            validate_fixture(case)

    def test_unsupported_runtime_state_is_not_silently_accepted(self):
        self.public["environment"]["runtime_state"] = {"session": "unrestorable"}
        self.invalid("reviewer-input")

    def test_unknown_tokens_cannot_satisfy_a_finite_cap(self):
        self.public["budgets"]["whole_path"]["model_tokens"] = 500
        self.public["budgets"]["remaining"]["model_tokens"] = 500
        self.invalid("infeasible remaining budget: model_tokens")

    def test_failed_read_consumes_attempts_and_visible_output_bytes(self):
        error = "File not found"
        self.public["context_manifest"][0].update(path="src/absent.py", availability="missing", error_message=error, exit_code=1)
        result = self.result()
        result["content"] = ""
        meta = result["extra"]["code_review_eval"]
        meta.update(status="failed", exit_code=1, stderr=error)
        self.read().update(path="src/absent.py", status="missing", returned_bytes=0, content_sha256=None)
        for key in ("whole_path", "inherited"):
            self.public["budgets"][key]["returned_bytes"] = len(error.encode())
        self.save()
        validate_fixture(self.case)

    def test_one_shell_can_contain_two_read_attempts(self):
        arguments = self.prefix["steps"][1]["tool_calls"][0]["arguments"]
        arguments["command"] += "; " + arguments["command"]
        result = self.result()
        meta = result["extra"]["code_review_eval"]
        meta["repository_reads"].append(copy.deepcopy(self.read()))
        result["content"] *= 2
        for key in ("whole_path", "inherited"):
            self.public["budgets"][key]["repository_read_attempts"] = 2
            self.public["budgets"][key]["returned_bytes"] *= 2
        self.save()
        validate_fixture(self.case)

    def test_successful_result_requires_success_exit_status(self):
        self.result()["extra"]["code_review_eval"]["exit_code"] = 1
        self.invalid("exit code 0")

    def test_diff_must_agree_with_owned_snapshots(self):
        artifact = self.public["change"]["diff"]["artifact"]
        artifact["content"] = ""
        artifact["sha256"] = sha256(b"")
        self.invalid("diff disagrees with snapshots")

    def test_source_blob_integrity(self):
        digest = self.public["snapshots"]["head"]["files"][0]["sha256"]
        (self.case / f"environment/blobs/{digest}").write_text("tampered\n")
        self.invalid("blob hash mismatch")

    def test_artifact_symlinks_are_rejected(self):
        path = self.case / "reviewer/prefix.json"
        copy_path = self.case / "prefix-copy.json"
        path.rename(copy_path)
        path.symlink_to(copy_path)
        with self.assertRaisesRegex(FixtureError, "symlink artifact"):
            validate_fixture(self.case)

    def test_context_paths_are_canonical(self):
        for path in ("../private/expectations.json", "/etc/passwd", "src/../private", "src//quota.py", "src\\quota.py", "src/./quota.py", "src/", "src\nquota.py"):
            with self.subTest(path=path), self.assertRaises(FixtureError):
                check_schema("reviewer-input", {
                    **self.public,
                    "context_manifest": [{**self.public["context_manifest"][0], "path": path}],
                })

    def test_required_suffix_evidence_must_fit_remaining_budget(self):
        self.private["expectations"]["retrieval"]["requirements"] = [{
            "id": "read-next", "acceptable_sources": [{"repository": "fixture-project", "snapshot_id": "s-02", "path": "src/quota.py"}],
            "evidence_origin": "new-suffix", "rationale": "A new successful read is explicitly required.",
        }]
        self.invalid("cannot obtain required evidence")

    def test_prefix_evidence_does_not_need_a_redundant_call(self):
        self.private["expectations"]["retrieval"]["requirements"] = [{
            "id": "read-existing", "acceptable_sources": [{"repository": "fixture-project", "snapshot_id": "s-02", "path": "src/quota.py"}],
            "evidence_origin": "available-evidence", "rationale": "Previously returned whole-file evidence is sufficient.",
        }]
        self.save()
        validate_fixture(self.case)

    def test_continuation_expectations_are_required(self):
        self.private["expectations"]["continuation"] = None
        self.invalid("must agree with start mode")

    def test_ordering_constraints_cannot_cycle(self):
        self.private["expectations"]["continuation"]["essential_order"] = [
            {"before": "finish-review", "after": "final_review"},
            {"before": "final_review", "after": "finish-review"},
        ]
        self.invalid("cyclic")

    def test_finding_ranges_use_real_snapshot_coordinates(self):
        self.private["expectations"]["required_findings"][0]["locations"][0]["lines"]["end"] = 100
        self.invalid("invalid finding line range")

    def test_file_level_findings_are_valid(self):
        self.private["expectations"]["required_findings"][0]["locations"][0]["lines"] = None
        self.save()
        validate_fixture(self.case)

    def test_related_checkpoints_cannot_cross_partitions(self):
        self.private["dataset"]["partition"] = "held-out"
        self.save()
        with self.assertRaisesRegex(FixtureError, "crosses dataset partitions"):
            validate_dataset(sorted((self.root / "examples").iterdir()))

    def test_unknown_diff_is_not_an_empty_diff(self):
        self.public["change"]["diff"] = {"status": "unavailable", "reason": "Diff intentionally withheld for a limited-context case."}
        self.private["expectations"]["required_findings"] = []
        self.private["expectations"]["context"]["condition"] = "insufficient"
        self.save()
        validate_fixture(self.case)

    def test_fixed_context_does_not_allow_tools(self):
        self.public["protocol"]["name"] = "fixed-context"
        self.invalid("reviewer-input")

    def test_strict_json_rejects_duplicate_keys_and_nan(self):
        for content in (b'{"x": 1, "x": 2}', b'{"value": NaN}', b'{"value": Infinity}'):
            with self.subTest(content=content), self.assertRaises(FixtureError):
                strict_json(content)


if __name__ == "__main__":
    unittest.main()
