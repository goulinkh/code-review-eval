"""Replay this frozen pilot through run_eval.py; no agent loop or execution adapter.

Run one invocation first, inspect it, then explicitly approve the preflight in
manifest.json before requesting the remaining matrix. Outputs are never reused.
"""

import argparse
import asyncio
from contextlib import redirect_stderr, redirect_stdout
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def read(path):
    return json.loads(path.read_bytes())


def save(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def account(directory):
    """Preserve Harbor usage and, when available, read-only router billing data."""
    report_path = directory / "report.json"
    reports = read(report_path)["cases"] if report_path.exists() else []
    responses = []
    session_ids = []
    for path in directory.glob("harbor/*/agent/pi/sessions/*.jsonl"):
        for line in path.read_text().splitlines():
            event = json.loads(line)
            if event.get("type") == "session":
                session_ids.append(event["id"])
            message = event.get("message", {})
            if message.get("role") != "assistant" or not message.get("responseId"):
                continue
            response_id = message["responseId"]
            req = urllib.request.Request(
                "https://openrouter.ai/api/v1/generation?id=" + response_id,
                headers={"Authorization": "Bearer " + os.environ["OPENROUTER_API_KEY"]},
            )
            try:
                with urllib.request.urlopen(req, timeout=30) as response:
                    data = json.load(response)["data"]
                fields = ("id", "model", "provider_name", "total_cost", "tokens_prompt",
                          "tokens_completion", "native_tokens_prompt", "native_tokens_completion",
                          "native_tokens_reasoning", "generation_time", "latency", "finish_reason",
                          "is_byok", "created_at")
                responses.append({k: data.get(k) for k in fields})
            except (urllib.error.URLError, ValueError, KeyError):
                responses.append({"id": response_id, "total_cost": None,
                                  "metadata_status": "unavailable"})
    known = bool(responses) and all(r.get("total_cost") is not None for r in responses)
    return {
        "reports": [{k: r[k] for k in ("case_id", "status", "error", "latency_ms", "usage", "trace_id")}
                    for r in reports],
        "session_ids": session_ids,
        "router_generations": responses,
        "billed_cost_usd": sum(r["total_cost"] for r in responses) if known else None,
        "runtime_cost_kind": "Pi catalog-derived estimate, not a billing guarantee",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="Fresh matrix root")
    parser.add_argument("--count", type=int, default=1, help="Number of not-yet-attempted invocations")
    args = parser.parse_args()
    os.chdir(ROOT)
    load_dotenv(ROOT / ".env", override=True)
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise SystemExit("OPENROUTER_API_KEY is missing")
    # Load the existing evaluator once so concurrent reporting-only checkout
    # edits cannot change implementations between the remaining invocations.
    sys.path.insert(0, str(ROOT))
    import run_eval as evaluator
    manifest = read(HERE / "manifest.json")
    for filename, expected in manifest["file_sha256"].items():
        if digest(ROOT / filename) != expected:
            raise SystemExit("Pinned input/configuration changed: " + filename)
    image = subprocess.check_output(
        ["docker", "image", "inspect", manifest["image"]["tag"], "--format", "{{.Id}}"], text=True,
    ).strip()
    if image != manifest["image"]["id"]:
        raise SystemExit("Image changed; do not mix conditions")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    ledger_path = output / "ledger.json"
    ledger = read(ledger_path) if ledger_path.exists() else []
    if any(row.get("finished_at") is None for row in ledger):
        raise SystemExit("An interrupted invocation needs accounting; never silently retry")
    for _ in range(args.count):
        if len(ledger) == len(manifest["invocations"]):
            break
        if ledger and not manifest["preflight"]["approved_for_matrix"] and args.count != 1:
            raise SystemExit("Preflight is not approved: only one next planned invocation is allowed")
        for filename, expected in manifest["file_sha256"].items():
            if filename in ("run_eval.py", "review_reporting.py", "pyproject.toml", "uv.lock"):
                continue  # Loaded implementation/environment, not re-imported or re-synced.
            if digest(ROOT / filename) != expected:
                raise SystemExit("Pinned input/configuration changed: " + filename)
        # Unknown billing is reserved at the conservative per-invocation amount,
        # never treated as zero. This gates launches; it cannot cap provider billing.
        booked = sum(row["accounting"]["billed_cost_usd"]
                     if row["accounting"]["billed_cost_usd"] is not None
                     else manifest["budget"]["per_invocation_reserve_usd"] for row in ledger)
        reserve = manifest["budget"]["per_invocation_reserve_usd"]
        if booked + reserve > manifest["budget"]["usd"]:
            raise SystemExit("Budget gate: stopping before the next invocation")
        invocation = manifest["invocations"][len(ledger)]
        directory = output / invocation["id"]
        if directory.exists():
            raise SystemExit("Refusing to reuse an output directory")
        command = [sys.executable, "run_eval.py", "run", "fixtures/" + invocation["case_id"],
                   "--agent", "pi", "--model", "openrouter/" + invocation["model_id"],
                   "--agent-kwargs", str(HERE / "agent-kwargs.json"),
                   "--image", manifest["image"]["tag"], "--output", str(directory)]
        row = {**invocation,
               "phase": "matrix" if manifest["preflight"]["approved_for_matrix"] else "preflight",
               "execution_api": "existing run_eval.run (same CLI core, loaded once)",
               "harness_sha256": {name: manifest["file_sha256"][name]
                                  for name in ("run_eval.py", "review_reporting.py")},
               "started_at": datetime.now(timezone.utc).isoformat(),
               "finished_at": None, "budget_before_usd": booked, "reserved_usd": reserve,
               "command": command[1:]}
        ledger.append(row)
        save(ledger_path, ledger)  # Retain attempts even if the evaluator crashes.
        log_path = output / (invocation["id"] + ".log")
        with log_path.open("w") as log, redirect_stdout(log), redirect_stderr(log):
            try:
                reports = asyncio.run(evaluator.run(
                    [ROOT / "fixtures" / invocation["case_id"]], directory,
                    agent="pi", model="openrouter/" + invocation["model_id"],
                    agent_kwargs=read(HERE / "agent-kwargs.json"),
                    image=manifest["image"]["tag"],
                    tracking_uri=f"sqlite:///{ROOT / 'mlflow.db'}",
                ))
                returncode = int(any(r["status"] != "completed" for r in reports))
            except Exception as exc:
                print("Evaluator error type:", type(exc).__name__)
                returncode = 2
        row.update(finished_at=datetime.now(timezone.utc).isoformat(), returncode=returncode,
                   accounting=account(directory))
        save(ledger_path, ledger)
        # Refuse to publish artifacts if the credential appears anywhere in them.
        for path in output.rglob("*"):
            if path.is_file() and key.encode() in path.read_bytes():
                raise SystemExit("Secret scan failed; quarantine evaluator outputs")
        print(invocation["id"], "exit", returncode,
              "billed_usd", row["accounting"]["billed_cost_usd"], flush=True)
        if returncode == 2:
            raise SystemExit("Evaluator error retained; investigate before continuing")


if __name__ == "__main__":
    main()
