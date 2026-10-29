# Checks

- `uv sync --locked`: passed before model execution.
- `uv run --no-sync python validate_fixtures.py examples/* fixtures/*`: passed,
  17 fixtures in the shared checkout. Only the unchanged original case-0004/0005
  pair was used in this experiment; other fixtures were added concurrently.
- `uv run --no-sync python -m unittest discover -s tests -v`: 172 tests passed.
  These tests use stubs, not paid models.
- `python -m py_compile experiments/openrouter-pilot-20261025T221002Z/*.py`:
  passed.
- `verify.py`: 18 retained invocations, 18 unique Pi sessions and MLflow traces,
  identical Pi system/tool declarations, Pi 1.1.0 throughout, no output beyond
  the configured 1,024 tokens, seven native write calls, zero HUMAN approvals.
  Raw failures, timeout and native abort markers are retained.
- Core installed versions remained Harbor 0.25.0, MLflow 3.17.2 and jsonschema
  4.26.0. The loaded evaluator source matches the archived snapshot. Concurrent
  reporting/CLI/lock drift is reported, not hidden or incorporated mid-matrix.
- Credential scan passed for experiment/run artifacts and local MLflow storage;
  `.env` is ignored by `.gitignore`. No credentials were printed or persisted in
  option files, manifests, traces or model fixtures.

See `verification.json` for machine-readable evidence, billing coverage and
limitations. Its pre-human-grading assertions intentionally stop passing after
real signed adjudication. No case invocations were retried and no failures dropped.
