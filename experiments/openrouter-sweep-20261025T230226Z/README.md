# All-fixture Pi/OpenRouter quick sweep

Start with [comparison.md](comparison.md). It is refreshed after every finished attempt and covers five models across all 14 authored fixtures, with one repetition: 70 planned model/fixture attempts. No spending ceiling was configured, as requested.

The reviewer is Harbor's existing Pi integration, pinned to Pi 1.1.0. Models were selected from the key-scoped OpenRouter catalog and retain the same common reviewer-facing settings. No credential value is stored in this experiment. The known policy-blocked GPT-4o route is not included.

## Notebook

Open http://localhost:2718/, select this experiment, and enable **Load selected report**. Use **Reload saved report** while the sweep runs. The line charts now use fixture IDs on the horizontal axis. Untested/running observations are gaps, not invented zero scores.

## Evidence and execution

- `manifest.json` records the models, case IDs, frozen source/input hashes, image identity, and absence of a spending ceiling.
- `image/` contains public Pi configuration and an idempotent npm installation fast path. It verifies the preinstalled Pi package is exactly 1.1.0; otherwise it delegates to the real npm command. This avoids repeating a slow global-package replacement without replacing the Harbor/Pi harness.
- `evaluator/` retains the evaluator implementation, schemas, and fixture inputs used in the experiment. This is evaluator-only; none of the private labels or full fixture snapshots are copied into reviewer containers.
- `../../runs/openrouter-sweep-20261025T230226Z/` retains per-attempt Harbor output, reviews, adjudication forms, MLflow exports, accounting, and the ledger. Per-attempt tracking stores are under its `tracking/` directory.
- `progress.log` records finished attempt counts and safe execution statuses.

The earlier `openrouter-sweep-20261025T225616Z` experiment was interrupted during repeated npm installation. Its setup failures and provenance remain retained separately; they are not mixed into this experiment's model results.

## Reporting only

To refresh from retained results without making any model calls:

```sh
uv run python experiments/openrouter-sweep-20261025T230226Z/run_sweep.py --report-only
```

Running the script without `--report-only` starts a paid experiment and refuses to overwrite an existing manifest/output set. It does not retry or silently substitute models.

Delivery, latency, and known billing are operational measurements, not semantic reviewer quality. Human adjudication remains pending, including for empty reviews. Known billing is a subtotal when generation metadata is unavailable. The existing fixture limits and native-agent capability gaps remain disclosed in the main report. No tests were run as part of this demo request.
