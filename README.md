# Code review evaluation fixtures

A standalone Git repository inside the hackathon checkout. This first increment
defines fixture contracts, not a reviewer, runner, sandbox, or grader.

## Standards first

- **JSON Schema Draft 2020-12** validates the fixture documents.
- **Harbor ATIF-v1.7** represents continuation conversations, real tool calls,
  and associated observations. We define a deliberately restricted text-only
  profile, not a new conversation format.
- Snapshot manifests, remaining-budget accounting, and semantic review labels
  are benchmark-specific extensions. These are **not Harbor tasks**.

See [the format](docs/fixture-format.md),
[the standards index](docs/standards.md), and
[the standards comparison and pinned sources](docs/standards/fixture-interoperability.md).
Agents should start with [AGENTS.md](AGENTS.md) for task-specific loading and validation.

## Validate

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```sh
uv sync --locked
uv run python validate_fixtures.py examples/*
uv run python -m unittest discover -s tests -v
```

Alternatively install the dependency from `pyproject.toml` in your own virtual
environment and run the same Python commands without `uv run`.

## Layout and trust boundary

```text
schemas/                      # versioned contracts; resolved offline
examples/<neutral-case-id>/
  reviewer/input.json         # ONLY reviewer-visible request data
  reviewer/prefix.json        # ATIF historical input; continuation only
  environment/blobs/<sha256>  # runner-owned UTF-8 snapshot content
  private/expectations.json   # labels, provenance, partitions, grading rubric
```

**Never expose the whole fixture directory to a reviewer.** Fixed-context
adapters receive the reviewer documents and inline initial context only.
Tool-enabled adapters additionally serve declared whole-file reads from
`environment/` through an isolated read-only boundary. Merely naming a
directory `private/` is not isolation; this repository implements no sandbox.

The three examples show a fresh defective/corrected pair and a continuation
of the defective case after a completed file read. They are format examples,
not an independently reviewed or frozen evaluation corpus. Category labels,
case relationships, expected paths, and reproducer outcomes stay private.

The design follows the parent project's
[`code-review-eval-scope.md`](../code-review-eval-scope.md) and
[`code-review-eval-categories.md`](../code-review-eval-categories.md).
The repository remains usable independently; those documents are design
inputs, not runtime dependencies.

No commits, remote, live service access, or reviewer execution are configured.
