"""Offline checks of retained execution evidence, not quality adjudication."""

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import tarfile
from importlib.metadata import version

from dotenv import dotenv_values
import mlflow

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
from review_reporting import load_run  # noqa: E402


def read(path):
    return json.loads(path.read_bytes())


def main():
    manifest = read(HERE / "manifest.json")
    output = ROOT / manifest["output_root"]
    ledger = read(output / "ledger.json")
    assert len(ledger) == 18 and all(r["finished_at"] for r in ledger)
    assert Counter((r["model_id"], r["case_id"]) for r in ledger) == Counter({
        (m, c): 3 for m in manifest["models"] for c in ("case-0004", "case-0005")})
    sessions, trace_ids, system_hashes, source_drift = [], [], [], []
    native_errors, execution, turns, tools = Counter(), Counter(), 0, Counter()
    unobserved_requests = []
    abort_markers = []
    for filename, expected in manifest["file_sha256"].items():
        if hashlib.sha256((ROOT / filename).read_bytes()).hexdigest() != expected:
            source_drift.append(filename)
    # The remaining matrix used already-loaded implementations, not changing
    # checkout files. Validate those exact archived sources and installed core
    # versions; report concurrent display/reporting/lock edits explicitly.
    assert set(source_drift) <= {"run_eval.py", "review_reporting.py", "pyproject.toml", "uv.lock"}, source_drift
    with tarfile.open(HERE / "harness-source.tar.gz") as archive:
        for filename in ("run_eval.py", "review_reporting.py"):
            assert hashlib.sha256(archive.extractfile(filename).read()).hexdigest() == manifest["file_sha256"][filename]
    versions = read(HERE / "runtime-versions.json")
    for package in ("harbor", "mlflow", "jsonschema"):
        assert version(package) == versions[package], package
    for row in ledger:
        directory = output / row["id"]
        run_manifest, prepared = load_run(directory)
        assert run_manifest["instruction_sha256"] == manifest["instruction_sha256"]
        assert len(prepared) == 1
        report, private, human, _ = prepared[0]
        assert report["case_id"] == row["case_id"]
        assert report["agent"]["version"] == "1.1.0"
        assert report["agent"]["model_info"]["name"] == row["model_id"]
        assert human["approval"] is None and human["adjudicator"] is None
        assert all(f["verdict"] == "unresolved" for f in human["findings"])
        execution[report["status"]] += 1
        trace_ids.append(report["trace_id"])
        trace = read(directory / row["case_id"] / "trace.json")
        mlflow.set_tracking_uri(run_manifest["tracking_uri"])
        live_trace = mlflow.get_trace(report["trace_id"])
        assert live_trace is not None and not live_trace.info.assessments
        assert {s.name for s in live_trace.data.spans} == {
            "harbor_trial", "harbor_agent", "normalize_and_check"}
        session_files = list(directory.glob("harbor/*/agent/pi/sessions/*.jsonl"))
        assert len(session_files) == 1
        assistant_count = 0
        for line in session_files[0].read_text().splitlines():
            event = json.loads(line)
            if event.get("type") == "session":
                sessions.append(event["id"])
            message = event.get("message", {})
            if message.get("role") == "system":
                material = {k: message.get(k) for k in ("content", "sections", "toolsAdded")}
                system_hashes.append(hashlib.sha256(json.dumps(material, sort_keys=True).encode()).hexdigest())
                assert [t["name"] for t in message["toolsAdded"]] == ["write"]
            if message.get("role") == "assistant":
                if (message.get("errorMessage") == "This operation was aborted"
                        and not message.get("responseId") and not message["usage"]["totalTokens"]):
                    # Pi may append this after the native turn-limit extension
                    # aborts. It is not evidence of a second completed model turn
                    # or of zero additional provider billing.
                    abort_markers.append(row["id"])
                    continue
                assistant_count += 1
                assert message["usage"]["output"] <= 1024
                for block in message["content"]:
                    if block["type"] == "toolCall":
                        tools[block["name"]] += 1
                error = message.get("errorMessage", "")
                if "ZDR violation" in error:
                    native_errors["account_zdr_guardrail_rejection"] += 1
                elif error:
                    native_errors["other_native_error"] += 1
        assert assistant_count <= 1, (row["id"], assistant_count)
        if not assistant_count:
            assert report["status"] in ("timed_out", "failed"), row["id"]
            unobserved_requests.append(row["id"])
        turns += assistant_count
        expected_request = manifest["file_sha256"][f"fixtures/{row['case_id']}/reviewer/input.json"]
        assert report["input_sha256"] == expected_request
        artifact = directory / row["case_id"] / "review-output.bin"
        if report["status"] == "completed":
            assert artifact.is_file() and report["review_sha256"]
    assert len(set(sessions)) == 18 and len(set(trace_ids)) == 18
    assert len(set(system_hashes)) == 1, "Pi system prompt/tool definitions differ"
    key = dotenv_values(ROOT / ".env")["OPENROUTER_API_KEY"].encode()
    checked = 0
    for base in (output, HERE, ROOT / "mlruns"):
        for path in base.rglob("*"):
            if path.is_file():
                assert key not in path.read_bytes(), "Credential in retained output"
                checked += 1
    for path in ROOT.glob("mlflow.db*"):
        assert key not in path.read_bytes(), "Credential in MLflow database"
        checked += 1
    billed = [r["accounting"]["billed_cost_usd"] for r in ledger]
    known = sum(c for c in billed if c is not None)
    missing_generation_billing = sum(c is None for c in billed)
    incomplete = {r["id"] for r, c in zip(ledger, billed) if c is None} | set(abort_markers)
    unknown = len(incomplete)
    booked = known + unknown * manifest["budget"]["per_invocation_reserve_usd"]
    assert booked <= 2
    audit = {"checked_at": datetime.now(timezone.utc).isoformat(), "case_invocations": 18,
             "observed_native_model_responses_or_errors": turns,
             "request_outcome_unobserved_invocations": unobserved_requests,
             "zero_usage_no_response_id_abort_markers": abort_markers,
             "billing_scope": "Known response IDs only; no claim that abort markers prove zero additional billing.",
             "unique_sessions": len(set(sessions)),
             "unique_traces": len(set(trace_ids)), "common_system_and_tool_sha256": system_hashes[0],
             "execution_counts": dict(execution), "native_error_counts": dict(native_errors),
             "native_tool_calls": dict(tools), "secret_scan_files": checked,
             "secret_scan": "passed; no credential values retained", "human_approvals": 0,
             "frozen_core_source_verified": True, "concurrent_checkout_drift": source_drift,
             "known_billed_cost_usd": known, "unknown_billed_invocations": unknown,
             "missing_generation_billing_invocations": missing_generation_billing,
             "conservative_booked_usd": booked, "budget_is_guaranteed_cap": False,
             "quality": "pending human adjudication", "ranking": None}
    (HERE / "verification.json").write_text(json.dumps(audit, indent=2) + "\n")
    print(json.dumps(audit, indent=2))


if __name__ == "__main__":
    main()
