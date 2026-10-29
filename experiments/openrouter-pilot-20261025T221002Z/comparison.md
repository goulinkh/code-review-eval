# OpenRouter / Pi small pilot

**Quality and ranking: pending human adjudication. No winner declared.**

One authored defect/fix pair, three repetitions per model. Labels and licensing/independent annotation remain provisional.
All attempts and failures are retained. Native `artifact_present` is not a quality score.

## Execution

| Model | Finished / planned | Completed | Failed / invalid / timeout | Latency ms min / median / max | Input / output tokens (known) | Router billed USD (known) | Incomplete-cost cases |
|---|---:|---:|---:|---|---:|---:|---:|
| `qwen/qwen3-30b-a3b-instruct-2507` | 6/6 | 0 | 6 | 8461 / 10804.0 / 30030 | 10949 / 966 | unknown total (0.001275210 known) | 2 |
| `mistralai/mistral-small-3.2-24b-instruct` | 6/6 | 6 | 0 | 6004 / 10201.0 / 12422 | 13017 / 1913 | unknown total (0.001468831 known) | 6 |
| `openai/gpt-4o-mini-2024-07-18` | 6/6 | 0 | 6 | 2506 / 2618.5 / 2781 | unknown | unknown total (0.000000000 known) | 6 |

Known OpenRouter generation charges: **US$0.002744041**, against a US$2 pilot budget.
Unknown cost, if present, is not zero. Per-case Pi/Harbor estimates are separately retained in comparison.json and case reports. Runtime zero token counts without a provider response are placeholders, not verified provider usage; their counts are recorded separately.
GPT-4o-mini was advertised publicly but rejected under the unchanged account ZDR/guardrail policy. No account settings or key permissions were changed, and no model was substituted. Qwen's first authenticated response contained no usable text/tool calls and submitted no artifact; that failure was retained.
Seven cases lack generation billing metadata (six policy rejections and one timeout). Seven other cases contain zero-usage, no-response-ID abort markers after the one-turn limit. These markers are not evidence of another completed turn, a retry, or zero additional billing. Conservatively, 14 full-case totals are incomplete; known identified-generation charges are still included above. The original finish-time ledger is retained unchanged.
The final audit reserves another $0.10 for each incomplete case, in addition to all known charges: $1.402744041 booked against $2. The original pre-call whole-matrix reserve was $1.80. Neither amount guarantees final provider billing.
Latency is Harbor agent-execution time, excluding image/setup/verifier; provider latency/timing and full invocation timestamps are in the ledger.

## Catalog and common conditions

| Catalog model ID | Advertised input USD / million tokens | Output USD / million tokens |
|---|---:|---:|
| `qwen/qwen3-30b-a3b-instruct-2507` | 0.09 | 0.3 |
| `mistralai/mistral-small-3.2-24b-instruct` | 0.075 | 0.2 |
| `openai/gpt-4o-mini-2024-07-18` | 0.15 | 0.6 |

Prices were queried live; raw catalog prices are USD/token. Endpoint-specific rates and availability are retained in selected-catalog.json.
Pi 1.1.0, Harbor 0.25.0, same pinned Docker image, existing exact prompts and case-0004/0005 inputs; fresh sessions, sequential execution, no case retries or model substitutions.
Native write-only tool selection; one model turn, max_tokens=1024, temperature=0, top_p=1, thinking off, common 32768-token context limit. Compaction, warming and Pi retries disabled; fixture agent timeout 30 seconds and reported combined token check 4096.

**Limits:** native-agent tool restrictions and budget enforcement are incomplete. This is not an enforced no-tools baseline. The submission tool conflicts with the fixture's nominal zero-tool budget; no tool-compliance score is claimed. Wall timeout/resources are enforced; spend/whole-episode caps are not. The $0.10 next-case reserve is a conservative launch gate, not a guaranteed billing cap.
Model tokenizers, upstream routing/prices and latency differ. Exact provider and generation IDs are in the ledger. Harbor resolves Node 22 and Pi dependencies during setup. Reporting-only concurrent changes were pinned after preflight and are disclosed in manifest.json; reviewer-facing settings did not change.

## Quality

Adjudicated recall, precision and corrected-case false alarms are **pending**, including empty reviews. No evaluated model judges itself; no agent-written form is HUMAN approval.
Once every completed case is human-confirmed, summarize.py computes reference recall over all three defective attempts (execution failures stay in the denominator), distinct-finding precision, and false-alarm cases over adjudicated completed corrected cases. Failed corrected cases stay execution failures, not clean reviews. Zero denominators are N/A. The existing grader also reports execution-unavailable references separately.
Any eventual winner may be described only as **best on this small pilot**.

| Model | Adjudicated recall | Adjudicated precision | Corrected-case false alarms |
|---|---|---|---|
| `qwen/qwen3-30b-a3b-instruct-2507` | pending | pending | pending |
| `mistralai/mistral-small-3.2-24b-instruct` | pending | pending | pending |
| `openai/gpt-4o-mini-2024-07-18` | pending | pending | pending |

Qwen's empty Pi responses could reflect upstream/adapter compatibility rather than review quality; without a retained raw transport stream the cause is unresolved. Endpoint rejection and timeout are likewise execution outcomes, not semantic judgments.

## Repetition variation

Finding counts and byte differences below are descriptive, not quality judgments. Null means no normalized review, not zero findings.

| Model | Case | Findings across repetitions | Distinct normalized reviews | Status by repetition |
|---|---|---|---:|---|
| `qwen/qwen3-30b-a3b-instruct-2507` | case-0004 | [null, null, null] | 0 | {"1": "invalid_output", "2": "timed_out", "3": "invalid_output"} |
| `qwen/qwen3-30b-a3b-instruct-2507` | case-0005 | [null, null, null] | 0 | {"1": "invalid_output", "2": "invalid_output", "3": "invalid_output"} |
| `mistralai/mistral-small-3.2-24b-instruct` | case-0004 | [2, 2, 1] | 3 | {"1": "completed", "2": "completed", "3": "completed"} |
| `mistralai/mistral-small-3.2-24b-instruct` | case-0005 | [2, 2, 2] | 3 | {"1": "completed", "2": "completed", "3": "completed"} |
| `openai/gpt-4o-mini-2024-07-18` | case-0004 | [null, null, null] | 0 | {"1": "invalid_output", "2": "invalid_output", "3": "invalid_output"} |
| `openai/gpt-4o-mini-2024-07-18` | case-0005 | [null, null, null] | 0 | {"1": "invalid_output", "2": "invalid_output", "3": "invalid_output"} |

Full per-case latency distributions (including population standard deviation), execution differences and usage are in comparison.json. Quality variation remains pending.

## Individual evidence

All links are evaluator-only. Start the local MLflow UI with `uv run mlflow ui --backend-store-uri sqlite:///$(pwd)/mlflow.db` from the repository root. Trace JSON exports remain readable without a running UI.

| Invocation | Status / reason | Review | Judgment | MLflow trace |
|---|---|---|---|---|
| 01-qwen-r1-case-0004 | invalid_output / review_artifact_missing | not submitted | [form](../../runs/openrouter-pilot-20261025T221002Z/01-qwen-r1-case-0004/case-0004/adjudication.json) | [tr-e59060387f8ab4ee45570fe21027b6fd](../../runs/openrouter-pilot-20261025T221002Z/01-qwen-r1-case-0004/case-0004/trace.json) |
| 02-mistral-r1-case-0004 | completed / — | [review](../../runs/openrouter-pilot-20261025T221002Z/02-mistral-r1-case-0004/case-0004/review.json) | [form](../../runs/openrouter-pilot-20261025T221002Z/02-mistral-r1-case-0004/case-0004/adjudication.json) | [tr-a0483f5ac7588db966bd0f655bea28e4](../../runs/openrouter-pilot-20261025T221002Z/02-mistral-r1-case-0004/case-0004/trace.json) |
| 03-gpt4o-r1-case-0004 | invalid_output / review_artifact_missing | not submitted | [form](../../runs/openrouter-pilot-20261025T221002Z/03-gpt4o-r1-case-0004/case-0004/adjudication.json) | [tr-26a5a63b20fe77f6ea65e5915a653da2](../../runs/openrouter-pilot-20261025T221002Z/03-gpt4o-r1-case-0004/case-0004/trace.json) |
| 04-qwen-r1-case-0005 | invalid_output / review_artifact_missing | not submitted | [form](../../runs/openrouter-pilot-20261025T221002Z/04-qwen-r1-case-0005/case-0005/adjudication.json) | [tr-60206a9d7fb6fc4b143bede5f9ced556](../../runs/openrouter-pilot-20261025T221002Z/04-qwen-r1-case-0005/case-0005/trace.json) |
| 05-mistral-r1-case-0005 | completed / — | [review](../../runs/openrouter-pilot-20261025T221002Z/05-mistral-r1-case-0005/case-0005/review.json) | [form](../../runs/openrouter-pilot-20261025T221002Z/05-mistral-r1-case-0005/case-0005/adjudication.json) | [tr-6336be9ac294544d6506f447c6f4af8a](../../runs/openrouter-pilot-20261025T221002Z/05-mistral-r1-case-0005/case-0005/trace.json) |
| 06-gpt4o-r1-case-0005 | invalid_output / review_artifact_missing | not submitted | [form](../../runs/openrouter-pilot-20261025T221002Z/06-gpt4o-r1-case-0005/case-0005/adjudication.json) | [tr-f7691ebc8dc7163c4c4cb3b4617c7a0a](../../runs/openrouter-pilot-20261025T221002Z/06-gpt4o-r1-case-0005/case-0005/trace.json) |
| 07-mistral-r2-case-0004 | completed / — | [review](../../runs/openrouter-pilot-20261025T221002Z/07-mistral-r2-case-0004/case-0004/review.json) | [form](../../runs/openrouter-pilot-20261025T221002Z/07-mistral-r2-case-0004/case-0004/adjudication.json) | [tr-1921421eaca4a845ec1bcdc85ae77037](../../runs/openrouter-pilot-20261025T221002Z/07-mistral-r2-case-0004/case-0004/trace.json) |
| 08-gpt4o-r2-case-0004 | invalid_output / review_artifact_missing | not submitted | [form](../../runs/openrouter-pilot-20261025T221002Z/08-gpt4o-r2-case-0004/case-0004/adjudication.json) | [tr-17df3418d66ca6a89331ca1c64953b59](../../runs/openrouter-pilot-20261025T221002Z/08-gpt4o-r2-case-0004/case-0004/trace.json) |
| 09-qwen-r2-case-0004 | timed_out / harbor_trial_error | not submitted | [form](../../runs/openrouter-pilot-20261025T221002Z/09-qwen-r2-case-0004/case-0004/adjudication.json) | [tr-c3eccba4b6c6d0a5f39f89b2892c41b6](../../runs/openrouter-pilot-20261025T221002Z/09-qwen-r2-case-0004/case-0004/trace.json) |
| 10-mistral-r2-case-0005 | completed / — | [review](../../runs/openrouter-pilot-20261025T221002Z/10-mistral-r2-case-0005/case-0005/review.json) | [form](../../runs/openrouter-pilot-20261025T221002Z/10-mistral-r2-case-0005/case-0005/adjudication.json) | [tr-79d014699acdc488de023ca86a82b626](../../runs/openrouter-pilot-20261025T221002Z/10-mistral-r2-case-0005/case-0005/trace.json) |
| 11-gpt4o-r2-case-0005 | invalid_output / review_artifact_missing | not submitted | [form](../../runs/openrouter-pilot-20261025T221002Z/11-gpt4o-r2-case-0005/case-0005/adjudication.json) | [tr-f6a6c5ad3f55cae4884457c1339d401a](../../runs/openrouter-pilot-20261025T221002Z/11-gpt4o-r2-case-0005/case-0005/trace.json) |
| 12-qwen-r2-case-0005 | invalid_output / review_artifact_missing | not submitted | [form](../../runs/openrouter-pilot-20261025T221002Z/12-qwen-r2-case-0005/case-0005/adjudication.json) | [tr-06d3935d4615839760a25342b5d8f2bc](../../runs/openrouter-pilot-20261025T221002Z/12-qwen-r2-case-0005/case-0005/trace.json) |
| 13-gpt4o-r3-case-0004 | invalid_output / review_artifact_missing | not submitted | [form](../../runs/openrouter-pilot-20261025T221002Z/13-gpt4o-r3-case-0004/case-0004/adjudication.json) | [tr-b7dc213ea39d9c258409c2f16f158e76](../../runs/openrouter-pilot-20261025T221002Z/13-gpt4o-r3-case-0004/case-0004/trace.json) |
| 14-qwen-r3-case-0004 | invalid_output / review_artifact_missing | not submitted | [form](../../runs/openrouter-pilot-20261025T221002Z/14-qwen-r3-case-0004/case-0004/adjudication.json) | [tr-38563782c24bbf287420515891e8c3f6](../../runs/openrouter-pilot-20261025T221002Z/14-qwen-r3-case-0004/case-0004/trace.json) |
| 15-mistral-r3-case-0004 | completed / — | [review](../../runs/openrouter-pilot-20261025T221002Z/15-mistral-r3-case-0004/case-0004/review.json) | [form](../../runs/openrouter-pilot-20261025T221002Z/15-mistral-r3-case-0004/case-0004/adjudication.json) | [tr-89a6de98f9a12005658d74c9a0a91989](../../runs/openrouter-pilot-20261025T221002Z/15-mistral-r3-case-0004/case-0004/trace.json) |
| 16-gpt4o-r3-case-0005 | invalid_output / review_artifact_missing | not submitted | [form](../../runs/openrouter-pilot-20261025T221002Z/16-gpt4o-r3-case-0005/case-0005/adjudication.json) | [tr-101dd2849cd687c5fa933bd5fba620df](../../runs/openrouter-pilot-20261025T221002Z/16-gpt4o-r3-case-0005/case-0005/trace.json) |
| 17-qwen-r3-case-0005 | invalid_output / review_artifact_missing | not submitted | [form](../../runs/openrouter-pilot-20261025T221002Z/17-qwen-r3-case-0005/case-0005/adjudication.json) | [tr-bec1a55cacb169c2d13bfbdd9c7d5022](../../runs/openrouter-pilot-20261025T221002Z/17-qwen-r3-case-0005/case-0005/trace.json) |
| 18-mistral-r3-case-0005 | completed / — | [review](../../runs/openrouter-pilot-20261025T221002Z/18-mistral-r3-case-0005/case-0005/review.json) | [form](../../runs/openrouter-pilot-20261025T221002Z/18-mistral-r3-case-0005/case-0005/adjudication.json) | [tr-52c55427b9819e5f519d2055e11097c5](../../runs/openrouter-pilot-20261025T221002Z/18-mistral-r3-case-0005/case-0005/trace.json) |

## Reproduce and grade

See [manifest.json](manifest.json), [human worksheet](grading-worksheet.md), [artifact hashes](artifact-index.json), and [usage/billing ledger](../../runs/openrouter-pilot-20261025T221002Z/ledger.json).
The manifest pins all public/private fixture bytes, schemas, evaluator source, Pi options and image inputs. No credential values are retained. Do not rerun into the original output directories.
