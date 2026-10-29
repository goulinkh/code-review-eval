# All-fixture Pi / OpenRouter comparison

Updated: 2026-10-25T23:03:10.510192+00:00

**8/70 attempts finished · 5 models · 14 authored fixtures · one repetition.**

Same Pi 1.1.0 harness and fixture inputs across models. No spending ceiling was requested.
**Execution and review delivery are not review-quality scores. Human adjudication is pending; no quality winner is declared.**

| Model | Finished / planned | Completed reviews | Failed / invalid / timed out | Median agent time (s) | Known billed USD | Unknown billing |
|---|---:|---:|---:|---:|---:|---:|
| `qwen/qwen3-30b-a3b-instruct-2507` | 2/14 | 0 | 2 | unknown | 0.000000000 | 2 |
| `mistralai/mistral-small-3.2-24b-instruct` | 2/14 | 0 | 2 | unknown | 0.000000000 | 2 |
| `meta-llama/llama-3.3-70b-instruct` | 2/14 | 0 | 2 | unknown | 0.000000000 | 2 |
| `meta-llama/llama-4-maverick` | 1/14 | 0 | 1 | unknown | 0.000000000 | 1 |
| `deepseek/deepseek-chat-v3-0324` | 1/14 | 0 | 1 | unknown | 0.000000000 | 1 |

## Fixture coverage

Delivery means a completed, valid review artifact, not a correct finding. Missing/running attempts remain pending, never fabricated zero-quality scores.

| Fixture | `qwen3-30b-a3b-instruct-2507` | `mistral-small-3.2-24b-instruct` | `llama-3.3-70b-instruct` | `llama-4-maverick` | `deepseek-chat-v3-0324` |
|---|---|---|---|---|---|
| case-0004 | failed | failed | failed | failed | failed |
| case-0005 | failed | failed | failed | not started | not started |
| case-0006 | not started | not started | not started | not started | not started |
| case-0007 | not started | not started | not started | not started | not started |
| case-0008 | not started | not started | not started | not started | not started |
| case-0009 | not started | not started | not started | not started | not started |
| case-0010 | not started | not started | not started | not started | not started |
| case-0011 | not started | not started | not started | not started | not started |
| case-0012 | not started | not started | not started | not started | not started |
| case-0013 | not started | not started | not started | not started | not started |
| case-0014 | not started | not started | not started | not started | not started |
| case-0015 | not started | not started | not started | not started | not started |
| case-0016 | not started | not started | not started | not started | not started |
| case-0017 | not started | not started | not started | not started | not started |

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
| `qwen/qwen3-30b-a3b-instruct-2507` | case-0004 | failed | pending |
| `mistralai/mistral-small-3.2-24b-instruct` | case-0004 | failed | pending |
| `meta-llama/llama-3.3-70b-instruct` | case-0004 | failed | pending |
| `meta-llama/llama-4-maverick` | case-0004 | failed | pending |
| `deepseek/deepseek-chat-v3-0324` | case-0004 | failed | pending |
| `qwen/qwen3-30b-a3b-instruct-2507` | case-0005 | failed | pending |
| `mistralai/mistral-small-3.2-24b-instruct` | case-0005 | failed | pending |
| `meta-llama/llama-3.3-70b-instruct` | case-0005 | failed | pending |
| `meta-llama/llama-4-maverick` | case-0005 | not started | pending |
| `deepseek/deepseek-chat-v3-0324` | case-0005 | not started | pending |
| `qwen/qwen3-30b-a3b-instruct-2507` | case-0006 | not started | pending |
| `mistralai/mistral-small-3.2-24b-instruct` | case-0006 | not started | pending |
| `meta-llama/llama-3.3-70b-instruct` | case-0006 | not started | pending |
| `meta-llama/llama-4-maverick` | case-0006 | not started | pending |
| `deepseek/deepseek-chat-v3-0324` | case-0006 | not started | pending |
| `qwen/qwen3-30b-a3b-instruct-2507` | case-0007 | not started | pending |
| `mistralai/mistral-small-3.2-24b-instruct` | case-0007 | not started | pending |
| `meta-llama/llama-3.3-70b-instruct` | case-0007 | not started | pending |
| `meta-llama/llama-4-maverick` | case-0007 | not started | pending |
| `deepseek/deepseek-chat-v3-0324` | case-0007 | not started | pending |
| `qwen/qwen3-30b-a3b-instruct-2507` | case-0008 | not started | pending |
| `mistralai/mistral-small-3.2-24b-instruct` | case-0008 | not started | pending |
| `meta-llama/llama-3.3-70b-instruct` | case-0008 | not started | pending |
| `meta-llama/llama-4-maverick` | case-0008 | not started | pending |
| `deepseek/deepseek-chat-v3-0324` | case-0008 | not started | pending |
| `qwen/qwen3-30b-a3b-instruct-2507` | case-0009 | not started | pending |
| `mistralai/mistral-small-3.2-24b-instruct` | case-0009 | not started | pending |
| `meta-llama/llama-3.3-70b-instruct` | case-0009 | not started | pending |
| `meta-llama/llama-4-maverick` | case-0009 | not started | pending |
| `deepseek/deepseek-chat-v3-0324` | case-0009 | not started | pending |
| `qwen/qwen3-30b-a3b-instruct-2507` | case-0010 | not started | pending |
| `mistralai/mistral-small-3.2-24b-instruct` | case-0010 | not started | pending |
| `meta-llama/llama-3.3-70b-instruct` | case-0010 | not started | pending |
| `meta-llama/llama-4-maverick` | case-0010 | not started | pending |
| `deepseek/deepseek-chat-v3-0324` | case-0010 | not started | pending |
| `qwen/qwen3-30b-a3b-instruct-2507` | case-0011 | not started | pending |
| `mistralai/mistral-small-3.2-24b-instruct` | case-0011 | not started | pending |
| `meta-llama/llama-3.3-70b-instruct` | case-0011 | not started | pending |
| `meta-llama/llama-4-maverick` | case-0011 | not started | pending |
| `deepseek/deepseek-chat-v3-0324` | case-0011 | not started | pending |
| `qwen/qwen3-30b-a3b-instruct-2507` | case-0012 | not started | pending |
| `mistralai/mistral-small-3.2-24b-instruct` | case-0012 | not started | pending |
| `meta-llama/llama-3.3-70b-instruct` | case-0012 | not started | pending |
| `meta-llama/llama-4-maverick` | case-0012 | not started | pending |
| `deepseek/deepseek-chat-v3-0324` | case-0012 | not started | pending |
| `qwen/qwen3-30b-a3b-instruct-2507` | case-0013 | not started | pending |
| `mistralai/mistral-small-3.2-24b-instruct` | case-0013 | not started | pending |
| `meta-llama/llama-3.3-70b-instruct` | case-0013 | not started | pending |
| `meta-llama/llama-4-maverick` | case-0013 | not started | pending |
| `deepseek/deepseek-chat-v3-0324` | case-0013 | not started | pending |
| `qwen/qwen3-30b-a3b-instruct-2507` | case-0014 | not started | pending |
| `mistralai/mistral-small-3.2-24b-instruct` | case-0014 | not started | pending |
| `meta-llama/llama-3.3-70b-instruct` | case-0014 | not started | pending |
| `meta-llama/llama-4-maverick` | case-0014 | not started | pending |
| `deepseek/deepseek-chat-v3-0324` | case-0014 | not started | pending |
| `qwen/qwen3-30b-a3b-instruct-2507` | case-0015 | not started | pending |
| `mistralai/mistral-small-3.2-24b-instruct` | case-0015 | not started | pending |
| `meta-llama/llama-3.3-70b-instruct` | case-0015 | not started | pending |
| `meta-llama/llama-4-maverick` | case-0015 | not started | pending |
| `deepseek/deepseek-chat-v3-0324` | case-0015 | not started | pending |
| `qwen/qwen3-30b-a3b-instruct-2507` | case-0016 | not started | pending |
| `mistralai/mistral-small-3.2-24b-instruct` | case-0016 | not started | pending |
| `meta-llama/llama-3.3-70b-instruct` | case-0016 | not started | pending |
| `meta-llama/llama-4-maverick` | case-0016 | not started | pending |
| `deepseek/deepseek-chat-v3-0324` | case-0016 | not started | pending |
| `qwen/qwen3-30b-a3b-instruct-2507` | case-0017 | not started | pending |
| `mistralai/mistral-small-3.2-24b-instruct` | case-0017 | not started | pending |
| `meta-llama/llama-3.3-70b-instruct` | case-0017 | not started | pending |
| `meta-llama/llama-4-maverick` | case-0017 | not started | pending |
| `deepseek/deepseek-chat-v3-0324` | case-0017 | not started | pending |
