import copy
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import mlflow
from harbor.agents.factory import AgentFactory
from harbor.agents.base import BaseAgent
from harbor.models.agent.context import AgentContext
from harbor.models.trial.config import AgentConfig
from harbor.models.trial.result import AgentInfo, TimingInfo

from harbor_agents import RecordedReviewer
from review_reporting import adjudicate, load_json, normalize, save_json, validate_human
from run_eval import REQUEST_MARKER, prepare, run
from validate_fixtures import FixtureError

ROOT = Path(__file__).resolve().parents[1]
CASES = [ROOT / "fixtures" / name for name in ("case-0004", "case-0005")]


def review(*texts):
    return {"schema_version": "1.0.0", "findings": [{"text": text} for text in texts]}


class HarborJobStub:
    """Exercise the public Harbor hook contract without Docker or model calls."""
    def __init__(self, output, outcomes=None):
        self.output = output
        self.callbacks = {}
        self.outcomes = outcomes or {}

    def on_trial_started(self, callback):
        self.callbacks["start"] = callback
        return self

    def on_agent_started(self, callback):
        self.callbacks["agent_start"] = callback
        return self

    def on_agent_ended(self, callback):
        self.callbacks["agent_end"] = callback
        return self

    def on_trial_ended(self, callback):
        self.callbacks["end"] = callback
        return self

    async def run(self):
        for task in sorted((self.output / "tasks").iterdir()):
            case_id = task.name
            raw, exception = self.outcomes.get(case_id, (json.dumps(review()).encode(), None))
            trial_name = f"{case_id}__test"
            trial_dir = self.output / "harbor" / trial_name
            (trial_dir / "artifacts").mkdir(parents=True)
            now = datetime.now(timezone.utc)
            context = AgentContext(n_input_tokens=10, n_output_tokens=5)
            result = SimpleNamespace(
                id=uuid4(), exception_info=exception,
                agent_info=AgentInfo(name="stub", version="1"),
                agent_execution=TimingInfo(started_at=now, finished_at=now + timedelta(milliseconds=20)),
                compute_token_cost_totals=lambda: (context.n_input_tokens, None, context.n_output_tokens, None),
            )
            event = SimpleNamespace(task_name=case_id, trial_name=trial_name, result=result, trial_id=result.id)
            await self.callbacks["start"](event)
            await self.callbacks["agent_start"](event)
            if raw is not None:
                (trial_dir / "artifacts/review.json").write_bytes(raw)
            await self.callbacks["agent_end"](event)
            await self.callbacks["end"](event)


class HarborLayerTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.tracking = tempfile.TemporaryDirectory()
        cls.uri = f"sqlite:///{Path(cls.tracking.name) / 'mlflow.db'}"

    @classmethod
    def tearDownClass(cls):
        mlflow.flush_trace_async_logging()
        cls.tracking.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.output = self.root / "run"

    async def execute(self, cases=CASES, outcomes=None):
        fake = HarborJobStub(self.output, outcomes)
        with patch("run_eval.Job.create", new=AsyncMock(return_value=fake)) as create:
            reports = await run(cases, self.output, agent="pi", model="provider/model",
                                tracking_uri=self.uri)
        config = create.call_args.args[0]
        self.assertEqual(config.agents[0].name, "pi")
        self.assertEqual(config.agents[0].model_name, "provider/model")
        self.assertEqual(config.n_attempts, 1)
        self.assertEqual(config.retry.max_retries, 0)
        self.assertEqual(str(config.environment.type.value), "docker")
        return reports

    def test_exported_native_tasks_never_contain_labels_or_snapshots(self):
        from harbor.models.task.task import Task
        prepare(CASES, self.output)
        for case in CASES:
            exported = self.output / "tasks" / case.name
            task = Task(exported)
            self.assertEqual(task.config.agent.timeout_sec, 30)
            self.assertEqual(task.config.verifier.environment_mode.value, "separate")
            self.assertEqual(task.config.artifacts[0].destination, "review.json")
            request = (case / "reviewer/input.json").read_text()
            self.assertEqual(task.instruction.split(REQUEST_MARKER, 1)[1], request)
            self.assertEqual(list((exported / "environment").iterdir()), [exported / "environment/Dockerfile"])
            for artifact in exported.rglob("*"):
                if artifact.is_file():
                    text = artifact.read_text()
                    for private_term in ("discoverable_because", "reference_checks", "required_findings", "NOASSERTION"):
                        self.assertNotIn(private_term, text)
            self.assertEqual((self.output / case.name / "reference.json").read_bytes(),
                             (case / "private/expectations.json").read_bytes())

    def test_harbor_owns_pi_opencode_and_future_agent_integration(self):
        for name in ("pi", "opencode", "harbor_agents:RecordedReviewer"):
            cls = AgentFactory.get_agent_class_from_config(AgentConfig(name=name))
            self.assertTrue(issubclass(cls, BaseAgent))
        self.assertEqual(AgentFactory.get_agent_class_from_config(
            AgentConfig(name="harbor_agents:RecordedReviewer")), RecordedReviewer)

    def test_unsupported_continuation_rejected_without_history_replay(self):
        with self.assertRaisesRegex(FixtureError, "unsupported fixture"):
            prepare([ROOT / "examples/case-0003"], self.output)
        self.assertFalse(self.output.exists())

    def test_validation_and_no_overwrite(self):
        with self.assertRaisesRegex(FixtureError, "duplicate case_id"):
            prepare([CASES[0], CASES[0]], self.output)
        prepare(CASES, self.output)
        with self.assertRaises(FileExistsError):
            prepare(CASES, self.output)

    async def test_per_case_artifacts_live_hook_traces_and_pending_quality(self):
        raw = json.dumps(review("Finding wording stays unchanged.")).encode()
        reports = await self.execute(outcomes={"case-0004": (raw, None)})
        self.assertEqual([r["status"] for r in reports], ["completed", "completed"])
        self.assertEqual([r["quality"]["status"] for r in reports], ["pending", "pending"])
        self.assertEqual(reports[0]["usage"]["input_tokens"], 10)
        self.assertIsNone(reports[0]["usage"]["cost_usd"])
        self.assertEqual(reports[0]["latency_ms"], 20)
        for report in reports:
            directory = self.output / report["case_id"]
            trace = load_json(directory / "trace.json")
            self.assertEqual({s["name"] for s in trace["data"]["spans"]},
                             {"harbor_trial", "harbor_agent", "normalize_and_check"})
            serialized = json.dumps(trace)
            self.assertNotIn("Finding wording", serialized)
            self.assertNotIn("discoverable_because", serialized)
        self.assertEqual((self.output / "case-0004/review-output.bin").read_bytes(), raw)
        manifest = load_json(self.output / "manifest.json")
        self.assertEqual(manifest["runner"], "harbor")
        self.assertEqual(manifest["harbor_version"], "0.25.0")
        self.assertIn("Not a controlled no-tools baseline", manifest["context_boundary"])

    async def test_failed_timeout_invalid_and_missing_output_are_not_clean_success(self):
        timeout = SimpleNamespace(exception_type="AgentTimeoutError", exception_message="SECRET")
        reports = await self.execute(outcomes={"case-0004": (b'{"partial":', timeout),
                                               "case-0005": (None, None)})
        self.assertEqual([r["status"] for r in reports], ["timed_out", "invalid_output"])
        self.assertEqual(reports[0]["quality"]["defect_recall"]["value"], 0)
        self.assertEqual(reports[1]["error"], "review_artifact_missing")
        self.assertNotIn("SECRET", (self.output / "case-0004/trace.json").read_text())
        self.assertEqual((self.output / "case-0004/review-output.bin").read_bytes(), b'{"partial":')

    async def test_invalid_json_and_bad_locations_are_invalid_output(self):
        located = review("Located finding")
        located["findings"][0].update(path="src/request_url.py", side="head", lines={"start": 999, "end": 1000})
        reports = await self.execute(outcomes={"case-0004": (b"not-json\xff", None),
                                               "case-0005": (json.dumps(located).encode(), None)})
        self.assertEqual([r["status"] for r in reports], ["invalid_output", "invalid_output"])
        self.assertEqual(reports[1]["checks"], ["f-001: line_range_out_of_bounds"])

    def signed_form(self, case_id):
        path = self.output / case_id / "adjudication.json"
        human = load_json(path)
        human["adjudicator"] = "test-human"
        for row in human["case_verdicts"].values():
            row.update(verdict="pass", reason="Manually inspected.")
        return path, human

    async def test_human_matching_novel_findings_precision_and_idempotent_assessments(self):
        await self.execute(outcomes={"case-0004": (json.dumps(review("Reference issue", "Invented issue")).encode(), None)})
        path, human = self.signed_form("case-0004")
        human["findings"][0].update(verdict="valid", reference_id="finding-01", reason="Same underlying defect.")
        human["findings"][1].update(verdict="invalid", reason="Unsupported allegation.")
        save_json(path, human)
        clean_path, clean = self.signed_form("case-0005")
        save_json(clean_path, clean)
        reports = adjudicate(self.output)
        self.assertEqual(reports[0]["quality"]["defect_recall"]["value"], 1)
        self.assertEqual(reports[0]["quality"]["finding_precision"]["value"], 0.5)
        self.assertEqual(reports[1]["quality"]["status"], "adjudicated")
        self.assertIsNone(reports[1]["quality"]["finding_precision"]["value"])
        trace_id = reports[0]["trace_id"]
        self.assertEqual(mlflow.get_trace(trace_id).info.assessments[0].source.source_type, "HUMAN")
        adjudicate(self.output)
        self.assertEqual(len(mlflow.get_trace(trace_id).info.assessments), 1)
        human["findings"][0]["reference_id"] = None  # A valid novel issue is not automatically false.
        save_json(path, human)
        reports = adjudicate(self.output)
        self.assertEqual(reports[0]["quality"]["defect_recall"]["value"], 0)
        self.assertEqual(reports[0]["quality"]["finding_precision"]["value"], 0.5)
        self.assertEqual(len(mlflow.get_trace(trace_id).info.assessments), 2)

    async def test_human_matches_are_one_to_one_and_hash_bound(self):
        await self.execute(CASES[:1], {"case-0004": (json.dumps(review("One", "Two")).encode(), None)})
        _, human = self.signed_form("case-0004")
        template = load_json(self.output / "case-0004/adjudication.json")
        private = load_json(self.output / "case-0004/reference.json")
        for mutation in (
            lambda h: h.update(review_sha256="stale"),
            lambda h: [row.update(verdict="valid", reference_id="finding-01", reason="Manual") for row in h["findings"]],
            lambda h: h["findings"][0].update(verdict="invalid"),
        ):
            bad = copy.deepcopy(human)
            mutation(bad)
            with self.assertRaises(FixtureError):
                validate_human(bad, template, private)
        human["findings"][0].update(verdict="valid", reference_id="finding-01", reason="Manual match.")
        human["findings"][1].update(verdict="duplicate", duplicate_of="f-001", reason="Same defect.")
        save_json(self.output / "case-0004/adjudication.json", human)
        q = adjudicate(self.output)[0]["quality"]
        self.assertEqual(q["finding_counts"]["duplicate"], 1)
        self.assertEqual(q["finding_precision"]["denominator"], 1)
        retained = self.output / "case-0004/review.json"
        retained.write_bytes(retained.read_bytes() + b" ")
        with self.assertRaisesRegex(FixtureError, "retained review changed"):
            adjudicate(self.output)

    async def test_recorded_agent_uses_harbor_environment_and_preserves_bytes(self):
        recordings = self.root / "recorded"
        recordings.mkdir()
        raw = b"deliberately invalid\xff"
        (recordings / "case-0004.json").write_bytes(raw)
        agent = RecordedReviewer(logs_dir=self.root / "logs", reviews_dir=str(recordings))
        env = SimpleNamespace(exec=AsyncMock(return_value=SimpleNamespace(return_code=0)))
        instruction = "Instructions" + REQUEST_MARKER + json.dumps({"case_id": "case-0004"})
        await agent.run(instruction, env, AgentContext())
        import base64
        self.assertIn(base64.b64encode(raw).decode(), env.exec.call_args.kwargs["command"])
        self.assertIn("/workspace/review.json", env.exec.call_args.kwargs["command"])

    def test_normalization_preserves_text_and_unknown_metadata(self):
        result = normalize(json.dumps(review("Original text")).encode())
        self.assertEqual(result["findings"][0]["text"], "Original text")
        self.assertEqual(result["recommendation"], "not_provided")
        self.assertIsNone(result["usage"]["cost_usd"])
        for raw in (b'{}', b'{"schema_version":"1.0.0","findings":[],"extra":1}',
                    b'{"schema_version":"1.0.0","findings":[],"findings":[]}'):
            with self.assertRaises(ValueError):
                normalize(raw)


if __name__ == "__main__":
    unittest.main()
