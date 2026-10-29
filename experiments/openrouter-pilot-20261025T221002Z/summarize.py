"""Summarize retained pilot evidence; never supply semantic judgments or a ranking."""

from collections import Counter
import hashlib
import json
from pathlib import Path
import statistics

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def read(path):
    return json.loads(path.read_bytes())


def save(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def spread(values):
    return ({"min": min(values), "median": statistics.median(values),
             "max": max(values), "population_stdev": statistics.pstdev(values)}
            if values else None)


def main():
    manifest = read(HERE / "manifest.json")
    output = ROOT / manifest["output_root"]
    ledger = read(output / "ledger.json")
    rows = []
    inventory = []
    for attempt in ledger:
        directory = output / attempt["id"]
        path = directory / attempt["case_id"]
        report_path = path / "report.json"
        report = read(report_path) if report_path.exists() else None
        abort_markers = 0
        for session in directory.glob("harbor/*/agent/pi/sessions/*.jsonl"):
            for line in session.read_text().splitlines():
                message = json.loads(line).get("message", {})
                if (message.get("role") == "assistant"
                        and message.get("errorMessage") == "This operation was aborted"
                        and not message.get("responseId")):
                    abort_markers += 1
        rows.append({"attempt": attempt, "report": report, "path": path,
                     "zero_usage_abort_markers": abort_markers})
        if directory.exists():
            inventory += [{"path": f.relative_to(ROOT).as_posix(),
                           "sha256": hashlib.sha256(f.read_bytes()).hexdigest()}
                          for f in sorted(directory.rglob("*")) if f.is_file()]
    summaries = []
    for model in manifest["models"]:
        selected = [r for r in rows if r["attempt"]["model_id"] == model]
        reports = [r["report"] for r in selected if r["report"]]
        finished = [r for r in selected if r["attempt"].get("finished_at")]
        usage = {key: {"known_total": sum(r["usage"][key] for r in reports if r["usage"][key] is not None),
                       "unknown_invocations": sum(r["usage"][key] is None for r in reports) + len(finished) - len(reports)}
                 for key in ("input_tokens", "cached_input_tokens", "output_tokens", "cost_usd")}
        identified_costs = [r["attempt"]["accounting"]["billed_cost_usd"] for r in finished]
        billed = [r["attempt"]["accounting"]["billed_cost_usd"] if not r["zero_usage_abort_markers"] else None
                  for r in finished]
        human_done = any(r["status"] == "completed" for r in reports) and all(
            r["status"] != "completed" or
            (r["quality"]["status"] == "adjudicated" and r["quality"].get("approval_source") == "human")
            for r in reports)
        # Do not turn the lower bounds in unsigned forms into quality scores.
        q = {"status": "pending", "recall": None, "precision": None,
             "corrected_case_false_alarm_cases": None, "ranking": None}
        if human_done and len(reports) == 6:
            matched = sum(len(r["quality"]["matched_reference_ids"]) for r in reports)
            required = sum(len(read(row["path"] / "reference.json")["expectations"]["required_findings"])
                           for row in selected)
            valid = sum(r["quality"]["finding_counts"]["valid"] for r in reports)
            invalid = sum(r["quality"]["finding_counts"]["invalid"] for r in reports)
            corrected = [r for r in reports if r["case_id"] == "case-0005" and r["status"] == "completed"]
            q.update(status="adjudicated", recall={"matched": matched, "required_including_execution_failures": required,
                     "value": matched / required if required else None},
                     precision={"valid": valid, "invalid": invalid,
                                "value": valid / (valid + invalid) if valid + invalid else None},
                     corrected_case_false_alarm_cases={"count": sum(r["quality"]["finding_counts"]["invalid"] > 0 for r in corrected),
                                                       "adjudicated_completed_cases": len(corrected)})
        unavailable = sum(not r["attempt"].get("accounting", {}).get("router_generations")
                          and r["report"] and not r["report"]["usage"]["input_tokens"]
                          for r in finished)
        for key in ("input_tokens", "cached_input_tokens", "output_tokens"):
            usage[key]["runtime_zero_without_provider_response"] = unavailable
            usage[key]["unknown_invocations"] += unavailable
            if reports and unavailable == len(reports):
                usage[key]["known_total"] = None
        if reports and all(r["usage"]["cost_usd"] is None for r in reports):
            usage["cost_usd"]["known_total"] = None
        summaries.append({
            "model_id": model, "attempted": len(selected), "finished": len(finished),
            "execution_counts": dict(Counter(r["status"] for r in reports)),
            "failure_reasons": dict(Counter(r["error"] for r in reports if r["error"])),
            "latency_ms": spread([r["latency_ms"] for r in reports if r["latency_ms"] is not None]),
            "usage": usage,
            "known_billed_cost_usd": sum(c for c in identified_costs if c is not None),
            "missing_generation_billing_invocations": sum(c is None for c in identified_costs),
            "abort_marker_invocations": sum(bool(r["zero_usage_abort_markers"]) for r in finished),
            "unknown_billed_cost_invocations": sum(c is None for c in billed),
            "billed_cost_usd_total": sum(billed) if billed and all(c is not None for c in billed) else None,
            "quality": q,
            "variation_by_case": {case: {
                "status_by_repetition": {str(r["attempt"]["repetition"]): r["report"]["status"] if r["report"] else "running"
                                         for r in selected if r["attempt"]["case_id"] == case},
                "finding_counts": [r["report"]["finding_count"] for r in selected
                                   if r["attempt"]["case_id"] == case and r["report"]],
                "token_usage": {key: spread([r["report"]["usage"][key] for r in selected
                    if r["attempt"]["case_id"] == case and r["report"] and r["report"]["usage"][key] is not None
                    and r["attempt"].get("accounting", {}).get("router_generations")])
                    for key in ("input_tokens", "output_tokens")},
                "distinct_normalized_review_hashes": len({r["report"]["review_sha256"] for r in selected
                    if r["attempt"]["case_id"] == case and r["report"] and r["report"]["review_sha256"]}),
                "latency_ms": spread([r["report"]["latency_ms"] for r in selected
                    if r["attempt"]["case_id"] == case and r["report"] and r["report"]["latency_ms"] is not None]),
                "quality_variation": "pending human adjudication" if q["status"] == "pending" else
                    [r["report"]["quality"] for r in selected if r["attempt"]["case_id"] == case and r["report"]],
            } for case in ("case-0004", "case-0005")},
        })
    save(HERE / "comparison.json", {"models": summaries, "ranking": None,
        "ranking_status": "pending human adjudication; no artifact_present ranking",
        "planned_invocations": 18, "ledger_entries": len(ledger)})
    save(HERE / "artifact-index.json", inventory)
    # Links are rooted at the repository in the helper above; make them relative
    # to this experiment directory for portable Markdown rendering.
    def evidence(path, label):
        import os
        return f"[{label}]({Path(os.path.relpath(path, HERE)).as_posix()})"
    lines = ["# OpenRouter / Pi small pilot", "", "**Quality and ranking: pending human adjudication. No winner declared.**", "",
        "One authored defect/fix pair, three repetitions per model. Labels and licensing/independent annotation remain provisional.",
        "All attempts and failures are retained. Native `artifact_present` is not a quality score.", "",
        "## Execution", "", "| Model | Finished / planned | Completed | Failed / invalid / timeout | Latency ms min / median / max | Input / output tokens (known) | Router billed USD (known) | Incomplete-cost cases |",
        "|---|---:|---:|---:|---|---:|---:|---:|"]
    for s in summaries:
        counts = s["execution_counts"]; latency = s["latency_ms"]
        timing = " / ".join(str(latency[k]) for k in ("min", "median", "max")) if latency else "unknown"
        cost_text = f"{s['known_billed_cost_usd']:.9f}" if not s['unknown_billed_cost_invocations'] else f"unknown total ({s['known_billed_cost_usd']:.9f} known)"
        input_text = s['usage']['input_tokens']['known_total']
        output_text = s['usage']['output_tokens']['known_total']
        tokens_text = f"{input_text} / {output_text}" if input_text is not None else "unknown"
        lines.append(f"| `{s['model_id']}` | {s['finished']}/6 | {counts.get('completed',0)} | "
            f"{sum(v for k,v in counts.items() if k!='completed')} | {timing} | "
            f"{tokens_text} | {cost_text} | {s['unknown_billed_cost_invocations']} |")
    total = sum(s["known_billed_cost_usd"] for s in summaries)
    lines += ["", f"Known OpenRouter generation charges: **US${total:.9f}**, against a US$2 pilot budget.",
        "Unknown cost, if present, is not zero. Per-case Pi/Harbor estimates are separately retained in comparison.json and case reports. Runtime zero token counts without a provider response are placeholders, not verified provider usage; their counts are recorded separately.",
        "GPT-4o-mini was advertised publicly but rejected under the unchanged account ZDR/guardrail policy. No account settings or key permissions were changed, and no model was substituted. Qwen's first authenticated response contained no usable text/tool calls and submitted no artifact; that failure was retained.",
        "Seven cases lack generation billing metadata (six policy rejections and one timeout). Seven other cases contain zero-usage, no-response-ID abort markers after the one-turn limit. These markers are not evidence of another completed turn, a retry, or zero additional billing. Conservatively, 14 full-case totals are incomplete; known identified-generation charges are still included above. The original finish-time ledger is retained unchanged.",
        "The final audit reserves another $0.10 for each incomplete case, in addition to all known charges: $1.402744041 booked against $2. The original pre-call whole-matrix reserve was $1.80. Neither amount guarantees final provider billing.",
        "Latency is Harbor agent-execution time, excluding image/setup/verifier; provider latency/timing and full invocation timestamps are in the ledger.",
        "", "## Catalog and common conditions", "",
        "| Catalog model ID | Advertised input USD / million tokens | Output USD / million tokens |",
        "|---|---:|---:|"]
    for m in read(HERE / "selected-catalog.json")["models"]:
        c = m["catalog"]
        lines.append(f"| `{c['id']}` | {float(c['pricing']['prompt'])*1e6:g} | {float(c['pricing']['completion'])*1e6:g} |")
    lines += ["", "Prices were queried live; raw catalog prices are USD/token. Endpoint-specific rates and availability are retained in selected-catalog.json.",
        "Pi 1.1.0, Harbor 0.25.0, same pinned Docker image, existing exact prompts and case-0004/0005 inputs; fresh sessions, sequential execution, no case retries or model substitutions.",
        "Native write-only tool selection; one model turn, max_tokens=1024, temperature=0, top_p=1, thinking off, common 32768-token context limit. Compaction, warming and Pi retries disabled; fixture agent timeout 30 seconds and reported combined token check 4096.",
        "", "**Limits:** native-agent tool restrictions and budget enforcement are incomplete. This is not an enforced no-tools baseline. The submission tool conflicts with the fixture's nominal zero-tool budget; no tool-compliance score is claimed. Wall timeout/resources are enforced; spend/whole-episode caps are not. The $0.10 next-case reserve is a conservative launch gate, not a guaranteed billing cap.",
        "Model tokenizers, upstream routing/prices and latency differ. Exact provider and generation IDs are in the ledger. Harbor resolves Node 22 and Pi dependencies during setup. Reporting-only concurrent changes were pinned after preflight and are disclosed in manifest.json; reviewer-facing settings did not change.",
        "", "## Quality", "",
        "Adjudicated recall, precision and corrected-case false alarms are **pending**, including empty reviews. No evaluated model judges itself; no agent-written form is HUMAN approval.",
        "Once every completed case is human-confirmed, summarize.py computes reference recall over all three defective attempts (execution failures stay in the denominator), distinct-finding precision, and false-alarm cases over adjudicated completed corrected cases. Failed corrected cases stay execution failures, not clean reviews. Zero denominators are N/A. The existing grader also reports execution-unavailable references separately.",
        "Any eventual winner may be described only as **best on this small pilot**.",
        "", "| Model | Adjudicated recall | Adjudicated precision | Corrected-case false alarms |", "|---|---|---|---|"]
    for s in summaries:
        q = s["quality"]
        def metric(value):
            return str(value) if q["status"] == "adjudicated" else "pending"
        lines.append(f"| `{s['model_id']}` | {metric(q['recall'])} | {metric(q['precision'])} | {metric(q['corrected_case_false_alarm_cases'])} |")
    lines += [
        "", "Qwen's empty Pi responses could reflect upstream/adapter compatibility rather than review quality; without a retained raw transport stream the cause is unresolved. Endpoint rejection and timeout are likewise execution outcomes, not semantic judgments.",
        "", "## Repetition variation", "",
        "Finding counts and byte differences below are descriptive, not quality judgments. Null means no normalized review, not zero findings.",
        "", "| Model | Case | Findings across repetitions | Distinct normalized reviews | Status by repetition |", "|---|---|---|---:|---|"]
    for s in summaries:
        for case, v in s["variation_by_case"].items():
            lines.append(f"| `{s['model_id']}` | {case} | {json.dumps(v['finding_counts'])} | {v['distinct_normalized_review_hashes']} | {json.dumps(v['status_by_repetition'])} |")
    lines += ["", "Full per-case latency distributions (including population standard deviation), execution differences and usage are in comparison.json. Quality variation remains pending.",
        "", "## Individual evidence", "", "All links are evaluator-only. Start the local MLflow UI with `uv run mlflow ui --backend-store-uri sqlite:///$(pwd)/mlflow.db` from the repository root. Trace JSON exports remain readable without a running UI.",
        "", "| Invocation | Status / reason | Review | Judgment | MLflow trace |", "|---|---|---|---|---|"]
    worksheet = ["# Human grading worksheet — PRIVATE", "", "No suggested judgments have been supplied. Keep model outputs and private rubrics away from reviewers.",
        "Use the same rubric and evidence standard for all 18 attempts. Match required defects by meaning/evidence, allow valid novel issues, and distinguish duplicates from false allegations. Empty reviews need explicit inspection/sign-off. Context/instruction handling is graded separately; native tool restrictions are not an enforced no-tools baseline.",
        "", "For each completed invocation, run its `grade` command below in an interactive human terminal. Enter only your own decisions and confirm with HUMAN; then run its `adjudicate` command. Do not use --practice as real approval. Unfinished forms remain pending. Failed execution is unavailable, never an empty clean approval.",
        "", "| Invocation | Execution | Findings to inspect | Review / rubric / form |", "|---|---|---|---|"]
    grading_commands = []
    for row in rows:
        a, r, path = row["attempt"], row["report"], row["path"]
        if not r:
            continue
        review = evidence(path / "review.json", "review") if (path / "review.json").exists() else "not submitted"
        form = evidence(path / "adjudication.json", "form")
        trace = evidence(path / "trace.json", r["trace_id"])
        lines.append(f"| {a['id']} | {r['status']} / {r['error'] or '—'} | {review} | {form} | {trace} |")
        findings = read(path / "review.json")["findings"] if (path / "review.json").exists() else []
        worksheet.append(f"| {a['id']} | {r['status']} | {', '.join(f['id'] for f in findings) or ('explicit empty review' if r['status']=='completed' else 'unavailable')} | {review} / {evidence(path/'reference.json','rubric')} / {form} |")
        if r["status"] == "completed":
            d = path.parent.relative_to(ROOT).as_posix()
            grading_commands += ["", f"### {a['id']}", "", "```sh", f"uv run python run_eval.py grade {d}", f"uv run python run_eval.py adjudicate {d}", "```"]
    lines += ["", "## Reproduce and grade", "",
        "See [manifest.json](manifest.json), [human worksheet](grading-worksheet.md), [artifact hashes](artifact-index.json), and " + evidence(output / "ledger.json", "usage/billing ledger") + ".",
        "The manifest pins all public/private fixture bytes, schemas, evaluator source, Pi options and image inputs. No credential values are retained. Do not rerun into the original output directories."]
    (HERE / "comparison.md").write_text("\n".join(lines) + "\n")
    (HERE / "grading-worksheet.md").write_text("\n".join(worksheet + grading_commands) + "\n")
    print("Finished", sum(s["finished"] for s in summaries), "/ 18; known billing USD", total)


if __name__ == "__main__":
    main()
