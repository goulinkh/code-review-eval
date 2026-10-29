# All-fixture Pi / OpenRouter comparison

Updated: 2026-10-25T23:17:40.166680+00:00

**70/70 attempts finished · 5 models · 14 authored fixtures · one repetition.**

Same Pi 1.1.0 harness and fixture inputs across models. No spending ceiling was requested.
**Execution and review delivery are not review-quality scores. Human adjudication is pending; no quality winner is declared.**

| Model | Finished / planned | Completed reviews | Failed / invalid / timed out | Median agent time (s) | Known billed USD | Unknown billing |
|---|---:|---:|---:|---:|---:|---:|
| `qwen/qwen3-30b-a3b-instruct-2507` | 14/14 | 0 | 14 | 12.67 | 0.003942990 | 0 |
| `mistralai/mistral-small-3.2-24b-instruct` | 14/14 | 13 | 1 | 10.98 | 0.003617273 | 0 |
| `meta-llama/llama-3.3-70b-instruct` | 14/14 | 14 | 0 | 4.16 | 0.006034765 | 0 |
| `meta-llama/llama-4-maverick` | 14/14 | 0 | 14 | 30.03 | 0.000000000 | 14 |
| `deepseek/deepseek-chat-v3-0324` | 14/14 | 9 | 5 | 9.42 | 0.010066750 | 1 |

## Fixture coverage

Delivery means a completed, valid review artifact, not a correct finding. Missing/running attempts remain pending, never fabricated zero-quality scores.

| Fixture | `qwen3-30b-a3b-instruct-2507` | `mistral-small-3.2-24b-instruct` | `llama-3.3-70b-instruct` | `llama-4-maverick` | `deepseek-chat-v3-0324` |
|---|---|---|---|---|---|
| case-0004 | invalid_output | completed | completed | timed_out | invalid_output |
| case-0005 | invalid_output | completed | completed | timed_out | completed |
| case-0006 | invalid_output | completed | completed | timed_out | completed |
| case-0007 | invalid_output | completed | completed | timed_out | completed |
| case-0008 | invalid_output | completed | completed | timed_out | completed |
| case-0009 | invalid_output | completed | completed | timed_out | completed |
| case-0010 | invalid_output | completed | completed | timed_out | invalid_output |
| case-0011 | invalid_output | completed | completed | timed_out | invalid_output |
| case-0012 | invalid_output | completed | completed | timed_out | completed |
| case-0013 | invalid_output | completed | completed | timed_out | completed |
| case-0014 | invalid_output | completed | completed | timed_out | completed |
| case-0015 | invalid_output | invalid_output | completed | timed_out | completed |
| case-0016 | invalid_output | completed | completed | timed_out | invalid_output |
| case-0017 | invalid_output | completed | completed | failed | failed |

## Conditions and limitations

- Uses all authored fixtures, not the illustrative continuation examples. Each case is fresh fixed-context.
- Pi 1.1.0, thinking off, one model turn, write-only artifact submission, temperature 0, top_p 1, 1,024 maximum output tokens, common 32,768 context window. These retain the original pilot's reviewer-facing settings.
- The one-turn artifact protocol can expose model/tool integration failures. A missing artifact is not proof the model cannot identify defects.
- Fixture wall-time and reported token limits remain in place. Native tool and total token/spend limits are not fully enforced. Artifact-writing access is not a controlled zero-tool baseline.
- Frozen input/evaluator snapshots are retained outside reviewer sandboxes. Harbor owns every actual agent/container invocation.
- Failures and unavailable routes are retained without retries or model substitutions. Old pilot results are not mixed into this experiment.
- Billing metadata is best-effort. Known subtotals omit unknown charges; unknown is not free. Latency includes failed/blocked attempts and excludes container setup.
- No machine-generated judgments are marked HUMAN. Use the retained adjudication forms for subsequent human grading.

## Per-attempt evidence

| Model | Fixture | Execution | Review / report |
|---|---|---|---|
| `qwen/qwen3-30b-a3b-instruct-2507` | case-0004 | invalid_output | [report](../../runs/openrouter-sweep-20261025T230226Z/001-case-0004-model-1/case-0004/report.json) |
| `mistralai/mistral-small-3.2-24b-instruct` | case-0004 | completed | [report](../../runs/openrouter-sweep-20261025T230226Z/002-case-0004-model-2/case-0004/report.json) / [review](../../runs/openrouter-sweep-20261025T230226Z/002-case-0004-model-2/case-0004/review.json) |
| `meta-llama/llama-3.3-70b-instruct` | case-0004 | completed | [report](../../runs/openrouter-sweep-20261025T230226Z/003-case-0004-model-3/case-0004/report.json) / [review](../../runs/openrouter-sweep-20261025T230226Z/003-case-0004-model-3/case-0004/review.json) |
| `meta-llama/llama-4-maverick` | case-0004 | timed_out | [report](../../runs/openrouter-sweep-20261025T230226Z/004-case-0004-model-4/case-0004/report.json) |
| `deepseek/deepseek-chat-v3-0324` | case-0004 | invalid_output | [report](../../runs/openrouter-sweep-20261025T230226Z/005-case-0004-model-5/case-0004/report.json) |
| `qwen/qwen3-30b-a3b-instruct-2507` | case-0005 | invalid_output | [report](../../runs/openrouter-sweep-20261025T230226Z/006-case-0005-model-1/case-0005/report.json) |
| `mistralai/mistral-small-3.2-24b-instruct` | case-0005 | completed | [report](../../runs/openrouter-sweep-20261025T230226Z/007-case-0005-model-2/case-0005/report.json) / [review](../../runs/openrouter-sweep-20261025T230226Z/007-case-0005-model-2/case-0005/review.json) |
| `meta-llama/llama-3.3-70b-instruct` | case-0005 | completed | [report](../../runs/openrouter-sweep-20261025T230226Z/008-case-0005-model-3/case-0005/report.json) / [review](../../runs/openrouter-sweep-20261025T230226Z/008-case-0005-model-3/case-0005/review.json) |
| `meta-llama/llama-4-maverick` | case-0005 | timed_out | [report](../../runs/openrouter-sweep-20261025T230226Z/009-case-0005-model-4/case-0005/report.json) |
| `deepseek/deepseek-chat-v3-0324` | case-0005 | completed | [report](../../runs/openrouter-sweep-20261025T230226Z/010-case-0005-model-5/case-0005/report.json) / [review](../../runs/openrouter-sweep-20261025T230226Z/010-case-0005-model-5/case-0005/review.json) |
| `qwen/qwen3-30b-a3b-instruct-2507` | case-0006 | invalid_output | [report](../../runs/openrouter-sweep-20261025T230226Z/011-case-0006-model-1/case-0006/report.json) |
| `mistralai/mistral-small-3.2-24b-instruct` | case-0006 | completed | [report](../../runs/openrouter-sweep-20261025T230226Z/012-case-0006-model-2/case-0006/report.json) / [review](../../runs/openrouter-sweep-20261025T230226Z/012-case-0006-model-2/case-0006/review.json) |
| `meta-llama/llama-3.3-70b-instruct` | case-0006 | completed | [report](../../runs/openrouter-sweep-20261025T230226Z/013-case-0006-model-3/case-0006/report.json) / [review](../../runs/openrouter-sweep-20261025T230226Z/013-case-0006-model-3/case-0006/review.json) |
| `meta-llama/llama-4-maverick` | case-0006 | timed_out | [report](../../runs/openrouter-sweep-20261025T230226Z/014-case-0006-model-4/case-0006/report.json) |
| `deepseek/deepseek-chat-v3-0324` | case-0006 | completed | [report](../../runs/openrouter-sweep-20261025T230226Z/015-case-0006-model-5/case-0006/report.json) / [review](../../runs/openrouter-sweep-20261025T230226Z/015-case-0006-model-5/case-0006/review.json) |
| `qwen/qwen3-30b-a3b-instruct-2507` | case-0007 | invalid_output | [report](../../runs/openrouter-sweep-20261025T230226Z/016-case-0007-model-1/case-0007/report.json) |
| `mistralai/mistral-small-3.2-24b-instruct` | case-0007 | completed | [report](../../runs/openrouter-sweep-20261025T230226Z/017-case-0007-model-2/case-0007/report.json) / [review](../../runs/openrouter-sweep-20261025T230226Z/017-case-0007-model-2/case-0007/review.json) |
| `meta-llama/llama-3.3-70b-instruct` | case-0007 | completed | [report](../../runs/openrouter-sweep-20261025T230226Z/018-case-0007-model-3/case-0007/report.json) / [review](../../runs/openrouter-sweep-20261025T230226Z/018-case-0007-model-3/case-0007/review.json) |
| `meta-llama/llama-4-maverick` | case-0007 | timed_out | [report](../../runs/openrouter-sweep-20261025T230226Z/019-case-0007-model-4/case-0007/report.json) |
| `deepseek/deepseek-chat-v3-0324` | case-0007 | completed | [report](../../runs/openrouter-sweep-20261025T230226Z/020-case-0007-model-5/case-0007/report.json) / [review](../../runs/openrouter-sweep-20261025T230226Z/020-case-0007-model-5/case-0007/review.json) |
| `qwen/qwen3-30b-a3b-instruct-2507` | case-0008 | invalid_output | [report](../../runs/openrouter-sweep-20261025T230226Z/021-case-0008-model-1/case-0008/report.json) |
| `mistralai/mistral-small-3.2-24b-instruct` | case-0008 | completed | [report](../../runs/openrouter-sweep-20261025T230226Z/022-case-0008-model-2/case-0008/report.json) / [review](../../runs/openrouter-sweep-20261025T230226Z/022-case-0008-model-2/case-0008/review.json) |
| `meta-llama/llama-3.3-70b-instruct` | case-0008 | completed | [report](../../runs/openrouter-sweep-20261025T230226Z/023-case-0008-model-3/case-0008/report.json) / [review](../../runs/openrouter-sweep-20261025T230226Z/023-case-0008-model-3/case-0008/review.json) |
| `meta-llama/llama-4-maverick` | case-0008 | timed_out | [report](../../runs/openrouter-sweep-20261025T230226Z/024-case-0008-model-4/case-0008/report.json) |
| `deepseek/deepseek-chat-v3-0324` | case-0008 | completed | [report](../../runs/openrouter-sweep-20261025T230226Z/025-case-0008-model-5/case-0008/report.json) / [review](../../runs/openrouter-sweep-20261025T230226Z/025-case-0008-model-5/case-0008/review.json) |
| `qwen/qwen3-30b-a3b-instruct-2507` | case-0009 | invalid_output | [report](../../runs/openrouter-sweep-20261025T230226Z/026-case-0009-model-1/case-0009/report.json) |
| `mistralai/mistral-small-3.2-24b-instruct` | case-0009 | completed | [report](../../runs/openrouter-sweep-20261025T230226Z/027-case-0009-model-2/case-0009/report.json) / [review](../../runs/openrouter-sweep-20261025T230226Z/027-case-0009-model-2/case-0009/review.json) |
| `meta-llama/llama-3.3-70b-instruct` | case-0009 | completed | [report](../../runs/openrouter-sweep-20261025T230226Z/028-case-0009-model-3/case-0009/report.json) / [review](../../runs/openrouter-sweep-20261025T230226Z/028-case-0009-model-3/case-0009/review.json) |
| `meta-llama/llama-4-maverick` | case-0009 | timed_out | [report](../../runs/openrouter-sweep-20261025T230226Z/029-case-0009-model-4/case-0009/report.json) |
| `deepseek/deepseek-chat-v3-0324` | case-0009 | completed | [report](../../runs/openrouter-sweep-20261025T230226Z/030-case-0009-model-5/case-0009/report.json) / [review](../../runs/openrouter-sweep-20261025T230226Z/030-case-0009-model-5/case-0009/review.json) |
| `qwen/qwen3-30b-a3b-instruct-2507` | case-0010 | invalid_output | [report](../../runs/openrouter-sweep-20261025T230226Z/031-case-0010-model-1/case-0010/report.json) |
| `mistralai/mistral-small-3.2-24b-instruct` | case-0010 | completed | [report](../../runs/openrouter-sweep-20261025T230226Z/032-case-0010-model-2/case-0010/report.json) / [review](../../runs/openrouter-sweep-20261025T230226Z/032-case-0010-model-2/case-0010/review.json) |
| `meta-llama/llama-3.3-70b-instruct` | case-0010 | completed | [report](../../runs/openrouter-sweep-20261025T230226Z/033-case-0010-model-3/case-0010/report.json) / [review](../../runs/openrouter-sweep-20261025T230226Z/033-case-0010-model-3/case-0010/review.json) |
| `meta-llama/llama-4-maverick` | case-0010 | timed_out | [report](../../runs/openrouter-sweep-20261025T230226Z/034-case-0010-model-4/case-0010/report.json) |
| `deepseek/deepseek-chat-v3-0324` | case-0010 | invalid_output | [report](../../runs/openrouter-sweep-20261025T230226Z/035-case-0010-model-5/case-0010/report.json) |
| `qwen/qwen3-30b-a3b-instruct-2507` | case-0011 | invalid_output | [report](../../runs/openrouter-sweep-20261025T230226Z/036-case-0011-model-1/case-0011/report.json) |
| `mistralai/mistral-small-3.2-24b-instruct` | case-0011 | completed | [report](../../runs/openrouter-sweep-20261025T230226Z/037-case-0011-model-2/case-0011/report.json) / [review](../../runs/openrouter-sweep-20261025T230226Z/037-case-0011-model-2/case-0011/review.json) |
| `meta-llama/llama-3.3-70b-instruct` | case-0011 | completed | [report](../../runs/openrouter-sweep-20261025T230226Z/038-case-0011-model-3/case-0011/report.json) / [review](../../runs/openrouter-sweep-20261025T230226Z/038-case-0011-model-3/case-0011/review.json) |
| `meta-llama/llama-4-maverick` | case-0011 | timed_out | [report](../../runs/openrouter-sweep-20261025T230226Z/039-case-0011-model-4/case-0011/report.json) |
| `deepseek/deepseek-chat-v3-0324` | case-0011 | invalid_output | [report](../../runs/openrouter-sweep-20261025T230226Z/040-case-0011-model-5/case-0011/report.json) |
| `qwen/qwen3-30b-a3b-instruct-2507` | case-0012 | invalid_output | [report](../../runs/openrouter-sweep-20261025T230226Z/041-case-0012-model-1/case-0012/report.json) |
| `mistralai/mistral-small-3.2-24b-instruct` | case-0012 | completed | [report](../../runs/openrouter-sweep-20261025T230226Z/042-case-0012-model-2/case-0012/report.json) / [review](../../runs/openrouter-sweep-20261025T230226Z/042-case-0012-model-2/case-0012/review.json) |
| `meta-llama/llama-3.3-70b-instruct` | case-0012 | completed | [report](../../runs/openrouter-sweep-20261025T230226Z/043-case-0012-model-3/case-0012/report.json) / [review](../../runs/openrouter-sweep-20261025T230226Z/043-case-0012-model-3/case-0012/review.json) |
| `meta-llama/llama-4-maverick` | case-0012 | timed_out | [report](../../runs/openrouter-sweep-20261025T230226Z/044-case-0012-model-4/case-0012/report.json) |
| `deepseek/deepseek-chat-v3-0324` | case-0012 | completed | [report](../../runs/openrouter-sweep-20261025T230226Z/045-case-0012-model-5/case-0012/report.json) / [review](../../runs/openrouter-sweep-20261025T230226Z/045-case-0012-model-5/case-0012/review.json) |
| `qwen/qwen3-30b-a3b-instruct-2507` | case-0013 | invalid_output | [report](../../runs/openrouter-sweep-20261025T230226Z/046-case-0013-model-1/case-0013/report.json) |
| `mistralai/mistral-small-3.2-24b-instruct` | case-0013 | completed | [report](../../runs/openrouter-sweep-20261025T230226Z/047-case-0013-model-2/case-0013/report.json) / [review](../../runs/openrouter-sweep-20261025T230226Z/047-case-0013-model-2/case-0013/review.json) |
| `meta-llama/llama-3.3-70b-instruct` | case-0013 | completed | [report](../../runs/openrouter-sweep-20261025T230226Z/048-case-0013-model-3/case-0013/report.json) / [review](../../runs/openrouter-sweep-20261025T230226Z/048-case-0013-model-3/case-0013/review.json) |
| `meta-llama/llama-4-maverick` | case-0013 | timed_out | [report](../../runs/openrouter-sweep-20261025T230226Z/049-case-0013-model-4/case-0013/report.json) |
| `deepseek/deepseek-chat-v3-0324` | case-0013 | completed | [report](../../runs/openrouter-sweep-20261025T230226Z/050-case-0013-model-5/case-0013/report.json) / [review](../../runs/openrouter-sweep-20261025T230226Z/050-case-0013-model-5/case-0013/review.json) |
| `qwen/qwen3-30b-a3b-instruct-2507` | case-0014 | invalid_output | [report](../../runs/openrouter-sweep-20261025T230226Z/051-case-0014-model-1/case-0014/report.json) |
| `mistralai/mistral-small-3.2-24b-instruct` | case-0014 | completed | [report](../../runs/openrouter-sweep-20261025T230226Z/052-case-0014-model-2/case-0014/report.json) / [review](../../runs/openrouter-sweep-20261025T230226Z/052-case-0014-model-2/case-0014/review.json) |
| `meta-llama/llama-3.3-70b-instruct` | case-0014 | completed | [report](../../runs/openrouter-sweep-20261025T230226Z/053-case-0014-model-3/case-0014/report.json) / [review](../../runs/openrouter-sweep-20261025T230226Z/053-case-0014-model-3/case-0014/review.json) |
| `meta-llama/llama-4-maverick` | case-0014 | timed_out | [report](../../runs/openrouter-sweep-20261025T230226Z/054-case-0014-model-4/case-0014/report.json) |
| `deepseek/deepseek-chat-v3-0324` | case-0014 | completed | [report](../../runs/openrouter-sweep-20261025T230226Z/055-case-0014-model-5/case-0014/report.json) / [review](../../runs/openrouter-sweep-20261025T230226Z/055-case-0014-model-5/case-0014/review.json) |
| `qwen/qwen3-30b-a3b-instruct-2507` | case-0015 | invalid_output | [report](../../runs/openrouter-sweep-20261025T230226Z/056-case-0015-model-1/case-0015/report.json) |
| `mistralai/mistral-small-3.2-24b-instruct` | case-0015 | invalid_output | [report](../../runs/openrouter-sweep-20261025T230226Z/057-case-0015-model-2/case-0015/report.json) |
| `meta-llama/llama-3.3-70b-instruct` | case-0015 | completed | [report](../../runs/openrouter-sweep-20261025T230226Z/058-case-0015-model-3/case-0015/report.json) / [review](../../runs/openrouter-sweep-20261025T230226Z/058-case-0015-model-3/case-0015/review.json) |
| `meta-llama/llama-4-maverick` | case-0015 | timed_out | [report](../../runs/openrouter-sweep-20261025T230226Z/059-case-0015-model-4/case-0015/report.json) |
| `deepseek/deepseek-chat-v3-0324` | case-0015 | completed | [report](../../runs/openrouter-sweep-20261025T230226Z/060-case-0015-model-5/case-0015/report.json) / [review](../../runs/openrouter-sweep-20261025T230226Z/060-case-0015-model-5/case-0015/review.json) |
| `qwen/qwen3-30b-a3b-instruct-2507` | case-0016 | invalid_output | [report](../../runs/openrouter-sweep-20261025T230226Z/061-case-0016-model-1/case-0016/report.json) |
| `mistralai/mistral-small-3.2-24b-instruct` | case-0016 | completed | [report](../../runs/openrouter-sweep-20261025T230226Z/062-case-0016-model-2/case-0016/report.json) / [review](../../runs/openrouter-sweep-20261025T230226Z/062-case-0016-model-2/case-0016/review.json) |
| `meta-llama/llama-3.3-70b-instruct` | case-0016 | completed | [report](../../runs/openrouter-sweep-20261025T230226Z/063-case-0016-model-3/case-0016/report.json) / [review](../../runs/openrouter-sweep-20261025T230226Z/063-case-0016-model-3/case-0016/review.json) |
| `meta-llama/llama-4-maverick` | case-0016 | timed_out | [report](../../runs/openrouter-sweep-20261025T230226Z/064-case-0016-model-4/case-0016/report.json) |
| `deepseek/deepseek-chat-v3-0324` | case-0016 | invalid_output | [report](../../runs/openrouter-sweep-20261025T230226Z/065-case-0016-model-5/case-0016/report.json) |
| `qwen/qwen3-30b-a3b-instruct-2507` | case-0017 | invalid_output | [report](../../runs/openrouter-sweep-20261025T230226Z/066-case-0017-model-1/case-0017/report.json) |
| `mistralai/mistral-small-3.2-24b-instruct` | case-0017 | completed | [report](../../runs/openrouter-sweep-20261025T230226Z/067-case-0017-model-2/case-0017/report.json) / [review](../../runs/openrouter-sweep-20261025T230226Z/067-case-0017-model-2/case-0017/review.json) |
| `meta-llama/llama-3.3-70b-instruct` | case-0017 | completed | [report](../../runs/openrouter-sweep-20261025T230226Z/068-case-0017-model-3/case-0017/report.json) / [review](../../runs/openrouter-sweep-20261025T230226Z/068-case-0017-model-3/case-0017/review.json) |
| `meta-llama/llama-4-maverick` | case-0017 | failed | pending |
| `deepseek/deepseek-chat-v3-0324` | case-0017 | failed | [report](../../runs/openrouter-sweep-20261025T230226Z/070-case-0017-model-5/case-0017/report.json) |
