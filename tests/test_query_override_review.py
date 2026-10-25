"""Offline integrity checks for recorded preflight evidence, never live model calls."""

import json
import unittest
from pathlib import Path

from validate_fixtures import check_schema, sha256

ROOT = Path(__file__).resolve().parents[1]
RECORD = ROOT / "reviews/query-overrides/round-01"
PROMPT_PREFIX = "Review the following code-change request.\n\n"


class QueryOverrideReviewRecordTests(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads((RECORD / "manifest.json").read_text())

    def test_exact_system_prompt_and_raw_responses_are_hash_bound(self):
        system = self.manifest["system_prompt"]
        self.assertEqual(sha256((RECORD / system["path"]).read_bytes()), system["sha256"])
        for case in self.manifest["cases"]:
            with self.subTest(case=case["case_id"]):
                self.assertEqual(
                    sha256((RECORD / case["response_artifact"]).read_bytes()),
                    case["response_sha256"],
                )
                self.assertEqual(case["status"], "completed")
                self.assertEqual(case["exit_code"], 0)

    def test_blinded_prompts_contain_only_the_bound_reviewer_request(self):
        for case in self.manifest["cases"]:
            with self.subTest(case=case["case_id"]):
                raw = (RECORD / case["prompt_artifact"]).read_bytes()
                self.assertEqual(sha256(raw), case["prompt_sha256"])
                self.assertTrue(raw.startswith(PROMPT_PREFIX.encode()))
                request = raw[len(PROMPT_PREFIX.encode()):]
                self.assertEqual(sha256(request), case["input_sha256"])
                public = json.loads(request)
                check_schema("reviewer-input", public)
                self.assertEqual(public["case_id"], case["case_id"])
                self.assertEqual(public["tools"], [])
                # A recorded review cannot silently follow edits to an immutable case revision.
                current = (ROOT / "fixtures" / case["case_id"] / "reviewer/input.json").read_bytes()
                if json.loads(current)["revision"] == public["revision"]:
                    self.assertEqual(sha256(current), case["input_sha256"])

    def test_automated_review_does_not_claim_human_approval_or_budget_enforcement(self):
        self.assertFalse(self.manifest["readiness"]["frozen"])
        self.assertEqual(self.manifest["readiness"]["independent_human_annotation"], "pending")
        self.assertEqual(self.manifest["readiness"]["redistribution_licensing"], "pending")
        self.assertIsNone(self.manifest["independent_human_signoff"])
        self.assertIsNone(self.manifest["licensing_signoff"])
        self.assertFalse(self.manifest["execution"]["enforces_fixture_budgets"])
        self.assertIsNone(self.manifest["execution"]["model_tokens"])
        self.assertIsNone(self.manifest["execution"]["cost"])


if __name__ == "__main__":
    unittest.main()
