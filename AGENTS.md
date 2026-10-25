# Agent instructions

These instructions apply to repository development. Standards describe how to
perform an operation, not permission to perform it. Do not create or push commits
unless the user explicitly requests it. Do not create or use Git worktrees.

## Load the relevant standards

Start with [the standards index](docs/standards.md), then read only the documents
and rules applicable to the task:

- Branches, commits, merge proposals, releases: [Git standards](docs/standards/git.md).
- Schemas, validation, or continuation behavior: [fixture interoperability](docs/standards/fixture-interoperability.md)
  and [the fixture contract](docs/fixture-format.md).
- Fixture artifacts: the relevant schema in `schemas/`, plus the fixture contract.

Cite stable rule IDs when explaining Git compliance or reporting a violation.
If a standard conflicts with the requested change or an authoritative contract,
report the conflict rather than silently changing policy.

## Preserve the evaluation boundary

Never expose an entire fixture directory to a reviewer. Reviewer-facing data
belongs in `reviewer/`; `private/` labels are evaluator-only and `environment/`
is runner-owned. Repository-development instructions and standards are not
additional reviewer input. Do not execute historical tool calls from prefixes.
See the fixture contract for the complete access and continuation rules.

## Validate changes

From the repository root:

```sh
uv sync --locked
uv run python validate_fixtures.py examples/* fixtures/*
uv run python -m unittest discover -s tests -v
```

Report which checks ran and any that could not run. The thin Harbor integration
is documented in [runner usage](docs/runner.md). Unit tests use stub lifecycle
events, never paid model calls. Harbor owns agent execution and sandbox lifecycle;
do not introduce a parallel agent registry, process runner, or container runtime.
