"""Run an all-fixture Pi/OpenRouter sweep using the existing Harbor evaluator."""

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import statistics
import subprocess
import sys
import threading
import urllib.request

from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUTPUT = ROOT / "runs" / HERE.name
MODELS = [
    "qwen/qwen3-30b-a3b-instruct-2507",
    "mistralai/mistral-small-3.2-24b-instruct",
    "meta-llama/llama-3.3-70b-instruct",
    "meta-llama/llama-4-maverick",
    "deepseek/deepseek-chat-v3-0324",
]
LOCK = threading.Lock()


def now():
    return datetime.now(timezone.utc).isoformat()


def read(path):
    return json.loads(path.read_bytes())


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    temporary.replace(path)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def spread(values):
    return ({"min": min(values), "median": statistics.median(values), "max": max(values),
             "population_stdev": statistics.pstdev(values)} if values else None)


def summarize(manifest, ledger):
    models = []
    for model in manifest["models"]:
        selected = [row for row in ledger if row["model_id"] == model]
        finished = [row for row in selected if row.get("finished_at")]
        reports = []
        for row in finished:
            path = OUTPUT / row["id"] / row["case_id"] / "report.json"
            report = read(path) if path.is_file() else None
            reports.append((row, report))
        counts = Counter(row["status"] for row in finished)
        usage = {}
        for key in ("input_tokens", "cached_input_tokens", "output_tokens", "cost_usd"):
            values = [report["usage"].get(key) if report else None for _, report in reports]
            known = [value for value in values if value is not None]
            usage[key] = {"known_total": sum(known) if known else None,
                          "unknown_invocations": sum(value is None for value in values)}
        billed = [row.get("accounting", {}).get("billed_cost_usd") for row in finished]
        variations = {}
        for case in manifest["cases"]:
            pairs = [(row, report) for row, report in reports if row["case_id"] == case]
            running = [row for row in selected if row["case_id"] == case and row.get("started_at") and not row.get("finished_at")]
            statuses = {"1": pairs[0][0]["status"]} if pairs else ({"1": "running"} if running else {})
            variations[case] = {
                "status_by_repetition": statuses,
                "finding_counts": [report["finding_count"] if report else None for _, report in pairs],
                "distinct_normalized_review_hashes": len({report["review_sha256"] for _, report in pairs if report and report.get("review_sha256")}),
                "latency_ms": spread([report["latency_ms"] for _, report in pairs if report and report.get("latency_ms") is not None]),
                "quality_variation": "pending human adjudication",
            }
        models.append({
            "model_id": model, "attempted": sum(bool(row.get("started_at")) for row in selected),
            "finished": len(finished), "execution_counts": dict(counts),
            "failure_reasons": dict(Counter(row["error"] for row in finished if row.get("error"))),
            "latency_ms": spread([report["latency_ms"] for _, report in reports if report and report.get("latency_ms") is not None]),
            "usage": usage, "known_billed_cost_usd": sum(value for value in billed if value is not None),
            "unknown_billed_cost_invocations": sum(value is None for value in billed),
            "quality": {"status": "pending", "recall": None, "precision": None,
                        "corrected_case_false_alarm_cases": None, "ranking": None},
            "variation_by_case": variations,
        })
    bundle = {"models": models, "ranking": None, "ranking_status": "pending human adjudication",
              "planned_invocations": len(ledger), "ledger_entries": sum(bool(row.get("started_at")) for row in ledger),
              "updated_at": now(), "fixture_count": len(manifest["cases"]), "repetitions": 1}
    save(HERE / "comparison.json", bundle)
    lines = ["# All-fixture Pi / OpenRouter comparison", "",
             f"Updated: {bundle['updated_at']}", "",
             f"**{sum(model['finished'] for model in models)}/{len(ledger)} attempts finished · {len(models)} models · {len(manifest['cases'])} authored fixtures · one repetition.**", "",
             "Same Pi 1.1.0 harness and fixture inputs across models. No spending ceiling was requested.",
             "**Execution and review delivery are not review-quality scores. Human adjudication is pending; no quality winner is declared.**", "",
             "| Model | Finished / planned | Completed reviews | Failed / invalid / timed out | Median agent time (s) | Known billed USD | Unknown billing |",
             "|---|---:|---:|---:|---:|---:|---:|"]
    for model in models:
        latency = model["latency_ms"]
        median = f"{latency['median']/1000:.2f}" if latency else "unknown"
        lines.append(f"| `{model['model_id']}` | {model['finished']}/{len(manifest['cases'])} | {model['execution_counts'].get('completed',0)} | {sum(v for k,v in model['execution_counts'].items() if k!='completed')} | {median} | {model['known_billed_cost_usd']:.9f} | {model['unknown_billed_cost_invocations']} |")
    lines += ["", "## Fixture coverage", "",
              "Delivery means a completed, valid review artifact, not a correct finding. Missing/running attempts remain pending, never fabricated zero-quality scores.", "",
              "| Fixture | " + " | ".join(f"`{m.split('/')[-1]}`" for m in manifest["models"]) + " |",
              "|---|" + "---|" * len(models)]
    for case in manifest["cases"]:
        states = [model["variation_by_case"][case]["status_by_repetition"].get("1", "not started") for model in models]
        lines.append("| " + case + " | " + " | ".join(states) + " |")
    lines += ["", "## Conditions and limitations", "",
              "- Uses all authored fixtures, not the illustrative continuation examples. Each case is fresh fixed-context.",
              "- Pi 1.1.0, thinking off, one model turn, write-only artifact submission, temperature 0, top_p 1, 1,024 maximum output tokens, common 32,768 context window. These retain the original pilot's reviewer-facing settings.",
              "- The one-turn artifact protocol can expose model/tool integration failures. A missing artifact is not proof the model cannot identify defects.",
              "- Fixture wall-time and reported token limits remain in place. Native tool and total token/spend limits are not fully enforced. Artifact-writing access is not a controlled zero-tool baseline.",
              "- Frozen input/evaluator snapshots are retained outside reviewer sandboxes. Harbor owns every actual agent/container invocation.",
              "- Failures and unavailable routes are retained without retries or model substitutions. Old pilot results are not mixed into this experiment.",
              "- Billing metadata is best-effort. Known subtotals omit unknown charges; unknown is not free. Latency includes failed/blocked attempts and excludes container setup.",
              "- No machine-generated judgments are marked HUMAN. Use the retained adjudication forms for subsequent human grading.", "",
              "## Per-attempt evidence", "", "| Model | Fixture | Execution | Review / report |", "|---|---|---|---|"]
    import os as paths
    for row in ledger:
        directory = OUTPUT / row["id"] / row["case_id"]
        relative = Path(paths.path.relpath(directory, HERE)).as_posix()
        status = row.get("status", "running" if row.get("started_at") else "not started")
        link = f"[report]({relative}/report.json)" if (directory / "report.json").is_file() else "pending"
        if (directory / "review.json").is_file():
            link += f" / [review]({relative}/review.json)"
        lines.append(f"| `{row['model_id']}` | {row['case_id']} | {status} | {link} |")
    target = HERE / "comparison.md"
    temporary = target.with_suffix(".md.tmp")
    temporary.write_text("\n".join(lines) + "\n")
    temporary.replace(target)
    save(OUTPUT / "ledger.json", ledger)


def prepare():
    if (HERE / "manifest.json").exists():
        raise SystemExit("This experiment already exists; use --report-only to refresh saved results")
    load_dotenv(ROOT / ".env", override=True)
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise SystemExit("OPENROUTER_API_KEY is missing")
    req = urllib.request.Request("https://openrouter.ai/api/v1/models/user", headers={"Authorization": "Bearer " + key})
    with urllib.request.urlopen(req, timeout=30) as response:
        catalog = {model["id"]: model for model in json.load(response)["data"]}
    selected = [catalog[name] for name in MODELS]
    if any("tools" not in model.get("supported_parameters", []) for model in selected):
        raise SystemExit("A selected model does not advertise tool support")
    image_dir = HERE / "image"
    image_dir.mkdir()
    old = ROOT / "experiments/openrouter-pilot-20261025T221002Z"
    shutil.copy2(old / "settings.json", image_dir / "settings.json")
    definitions = []
    for model in selected:
        pricing = model["pricing"]
        definitions.append({"id": model["id"], "name": model.get("name", model["id"]),
                            "reasoning": False, "input": ["text"],
                            "cost": {"input": float(pricing["prompt"]) * 1e6,
                                     "output": float(pricing["completion"]) * 1e6,
                                     "cacheRead": 0, "cacheWrite": 0},
                            "contextWindow": 32768, "maxTokens": 1024,
                            "samplingParams": {"temperature": 0, "top_p": 1},
                            "compat": {"maxTokensField": "max_tokens"}})
    save(image_dir / "models.json", {"providers": {"openrouter": {
        "baseUrl": "https://openrouter.ai/api/v1", "api": "openai-completions",
        "apiKey": "$OPENROUTER_API_KEY", "models": definitions}}})
    save(HERE / "selected-catalog.json", {"retrieved_at": now(), "models": selected})
    save(HERE / "agent-kwargs.json", {"version": "1.1.0", "reasoning_effort": "off", "max_turns": 1})
    cached_npm = """#!/bin/sh
if [ "$#" -eq 4 ] && [ "$1" = "install" ] && { [ "$2" = "-g" ] || [ "$2" = "--global" ]; } && [ "$3" = "--ignore-scripts" ] && [ "$4" = "@earendil-works/pi-coding-agent@1.1.0" ]; then
    package="$(dirname "$0")/../lib/node_modules/@earendil-works/pi-coding-agent/package.json"
    if node -e 'if(require(process.argv[1]).version !== "1.1.0") process.exit(1)' "$package"; then
        echo "Using the preinstalled, version-verified Pi 1.1.0 package"
        exit 0
    fi
fi
exec "$(dirname "$0")/npm-real" "$@"
"""
    (image_dir / "npm-cached").write_text(cached_npm)
    dockerfile = ('FROM code-review-sweep:20261025t225616z\n'
                  'COPY npm-cached /tmp/npm-cached\n'
                  'RUN for npm in /root/.nvm/versions/node/*/bin/npm; do mv "$npm" "$npm-real"; cp /tmp/npm-cached "$npm"; chmod +x "$npm"; done\n'
                  'COPY settings.json models.json /root/.pi/agent/\nWORKDIR /workspace\n')
    (image_dir / "Dockerfile").write_text(dockerfile)
    image = "code-review-sweep:" + HERE.name.rsplit("-", 1)[-1].lower()
    print("Preparing cached Pi image", image, flush=True)
    with (HERE / "image-build.log").open("w") as log:
        subprocess.run(["docker", "build", "-t", image, str(image_dir)], stdout=log, stderr=log, check=True)
    image_id = subprocess.check_output(["docker", "image", "inspect", image, "--format", "{{.Id}}"], text=True).strip()
    frozen = HERE / "evaluator"
    frozen.mkdir()
    for name in ("run_eval.py", "review_reporting.py", "visual_reporting.py", "harbor_agents.py", "validate_fixtures.py", "adjudication_cli.py"):
        if (ROOT / name).is_file():
            shutil.copy2(ROOT / name, frozen / name)
    shutil.copytree(ROOT / "schemas", frozen / "schemas")
    cases = []
    for case in sorted((ROOT / "fixtures").glob("*/reviewer/input.json")):
        public = read(case)
        if public["protocol"]["name"] != "fixed-context" or public["start"]["mode"] != "fresh":
            raise SystemExit("Unsupported authored fixture; do not silently omit: " + public["case_id"])
        case_id = public["case_id"]
        shutil.copytree(case.parent.parent, frozen / "fixtures" / case_id)
        cases.append(case_id)
    OUTPUT.mkdir(parents=True)
    (OUTPUT / "tracking").mkdir()
    manifest = {"created_at": now(), "models": MODELS, "cases": cases, "repetitions": 1,
                "agent": "pi", "pi_version": "1.1.0", "harbor_version": "0.25.0",
                "image": {"tag": image, "id": image_id}, "workers": 8,
                "spending_ceiling_usd": None, "output_root": OUTPUT.relative_to(ROOT).as_posix(),
                "source_sha256": {p.name: sha(p) for p in frozen.glob("*.py")},
                "input_sha256": {case: sha(frozen / "fixtures" / case / "reviewer/input.json") for case in cases},
                "quality": "pending human adjudication", "no_retries": True}
    save(HERE / "manifest.json", manifest)
    ledger = [{"id": f"{index:03d}-{case}-model-{model_index+1}", "model_id": model,
               "case_id": case, "repetition": 1, "started_at": None, "finished_at": None}
              for index, (case, model_index, model) in enumerate(
                  ((case, i, model) for case in cases for i, model in enumerate(MODELS)), 1)]
    summarize(manifest, ledger)
    return manifest, ledger


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-only", action="store_true")
    args = parser.parse_args()
    if args.report_only:
        summarize(read(HERE / "manifest.json"), read(OUTPUT / "ledger.json"))
        return
    manifest, ledger = prepare()
    spec = importlib.util.spec_from_file_location("pilot_accounting", ROOT / "experiments/openrouter-pilot-20261025T221002Z/replay.py")
    accounting = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(accounting)
    key = os.environ["OPENROUTER_API_KEY"]
    environment = os.environ.copy()
    environment.update(MLFLOW_DISABLE_TELEMETRY="true", MLFLOW_DISABLE_AGENT_HINT="1")

    def execute(row):
        directory = OUTPUT / row["id"]
        with LOCK:
            row["started_at"] = now()
            summarize(manifest, ledger)
        command = [sys.executable, str(HERE / "evaluator/run_eval.py"), "run",
                   str(HERE / "evaluator/fixtures" / row["case_id"]),
                   "--agent", "pi", "--model", "openrouter/" + row["model_id"],
                   "--agent-kwargs", str(HERE / "agent-kwargs.json"),
                   "--image", manifest["image"]["tag"], "--output", str(directory),
                   "--tracking-uri", "sqlite:///" + str(OUTPUT / "tracking" / (row["id"] + ".db"))]
        try:
            with (OUTPUT / (row["id"] + ".log")).open("w") as log:
                process = subprocess.run(command, cwd=ROOT, env=environment, stdout=log, stderr=log, timeout=300)
            case_report = directory / row["case_id"] / "report.json"
            report = read(case_report) if case_report.is_file() else None
            status = report["status"] if report else "failed"
            error = report.get("error") if report else "runner_exit_" + str(process.returncode)
            bill = accounting.account(directory)
            for path in directory.rglob("*"):
                if path.is_file() and key.encode() in path.read_bytes():
                    raise RuntimeError("credential_detected_in_output")
        except Exception as exc:
            status, error, bill = "failed", type(exc).__name__, {"billed_cost_usd": None}
        with LOCK:
            row.update(finished_at=now(), status=status, error=error, accounting=bill)
            summarize(manifest, ledger)
            done = sum(bool(item.get("finished_at")) for item in ledger)
            print(f"{done}/{len(ledger)} {row['case_id']} {row['model_id']} {status}", flush=True)

    with ThreadPoolExecutor(max_workers=manifest["workers"]) as pool:
        futures = [pool.submit(execute, row) for row in ledger]
        for future in as_completed(futures):
            future.result()
    with LOCK:
        summarize(manifest, ledger)
    print("Finished:", HERE / "comparison.md", flush=True)


if __name__ == "__main__":
    main()
