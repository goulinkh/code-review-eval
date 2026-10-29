# Launchpad history extension — evaluator-only

Two additional authored cases, `case-0016` and `case-0017`, extend the initial
12-case set to **14 authored cases** (17 artifacts with the format examples).
Do not expose this page, provenance or author checks to a reviewer.

Both are fresh fixed-context Python miniatures with complete inline supporting
context, owned snapshots and canonical generated diffs. Their public budgets
retain the existing policy. The runner and schemas are unchanged.

## Selected fixes and analysis

### Issue links with a trailing slash — `416322ad428`

The parent `parseGitHubURL` and `parseGitLabURL` expressions required the issue
number immediately before the end of the path. Consequently, `/issues/123/`
failed to match although `/issues/123` worked. The fix adds an optional final
slash without changing the extracted base URL or string id. The added
`GitHubWithTrailingSlash` and `GitLabWithTrailingSlash` scenarios expect exactly
the same extraction as the existing no-slash scenarios. Both implementation
versions and their surrounding tests were inspected, not just the commit title.

`case-0016` reduces this to one pure issue-link parser for two fictional hosts.
It retains Python, replaces the project service/registration machinery with a
return tuple, and explicitly limits the miniature's accepted URL syntax.
A change to the path expression rejects the supported trailing-slash spelling;
no network request, GitHub account or tracker registration is involved.

### Deleted build during metrics reporting — `fdab9af552b`

In the parent, `reportStatsdMetrics` checked for a `build` attribute and then
read `handler.build.job_type.name`. `BuildUploadHandler._getBuild` can return
None after deletion: the attribute exists without a live object. The fix uses
the handler type and the surviving queue leaf to recover the build type instead.
`testUploadStatsdMetricsBuildUploadDeletedBuild` queues an id that no longer
exists and expects one correctly labelled timing sample. Existing manual and
live-build tests cover the unaffected paths. These implementations, leaf parser
and tests were inspected locally; original Launchpad tests were not executed.

`case-0017` retains the nullable-build lifecycle and immutable queue metadata,
using frozen dataclasses and an injected event-recording sink. It simplifies
`job_type.name` to a direct `kind` string. Dereferencing `build.kind` fails for
None before the sample is emitted, while the leaf can still supply the type.
The fixture establishes a reporting exception and missing metric, **not** a
claim that upload publication is rolled back or data is lost.

## Review direction and coverage

Exactly **two review cases** were added, not two new defect/correction pairs.
Each owns a corrected **base** and a deliberately regressed **head**: the
historical fix direction is reversed so the review asks the model to detect
the original failure mechanism. This adaptation is recorded explicitly in
private provenance. Base execution provides a correction control under the
identical contract; it is not a separately evaluated clean review case and
must not increase the count of review-level paired fix-sensitivity controls.

| Case | Category | Context | Expected review behavior | Related cases | Author verification |
|---|---|---|---|---|---|
| `case-0016` | Functional correctness | Self-contained | Find rejection of valid issue links ending in one slash; explain the import failure | None; base is the correction control | Head 12/16, four intended rejections; base 16/16 |
| `case-0017` | Reliability/state | Self-contained | Find the deleted-build dereference and missing timing sample; use surviving metadata | None; base is the correction control | Head 5/8, three intended dereferences; base 8/8 |

Both cases use label version `0.3.0`, development partition, with distinct
scenario groups `scenario-06`/`scenario-07`. All earlier case bytes and label
versions are retained. As before, this additive inventory is not a newly frozen,
single-version comparison dataset. Labels and permission/licensing review are
**pending**, not independent human approval. New/unmatched review findings
require adjudication rather than automatic rejection.

## Private provenance and licensing

Each `private/expectations.json` records the full source fix and parent hashes,
implementation/test paths, observed mechanism, reduction decisions, reverse-fix
orientation and licensing observations. No original repository is required for
validation, author checks or reviewer execution.

The inspected Python headers specify AGPLv3; root `LICENSE` distributes Launchpad
source under AGPLv3 and separately restricts images/icons and trademarks. These
miniatures/checks were independently written without copying upstream source or
tests, graphics or branding. Their own redistribution licence and independent
permission review remain unresolved (`NOASSERTION`); no publication is approved.

## Explicit author checks

From `code-review-eval/`:

```sh
uv run python -m reference_checks.launchpad_history case-0016
# 12/16; exit 1 (the intended regression)
uv run python -m reference_checks.launchpad_history case-0016 --side base
# 16/16; exit 0
uv run python -m reference_checks.launchpad_history case-0017
# 5/8; exit 1 (the intended regression)
uv run python -m reference_checks.launchpad_history case-0017 --side base
# 8/8; exit 0
```

This command explicitly executes only the named trusted authored modules. It is
**not a sandbox**, reviewer run or semantic grader. Structural validation does
not execute source. The metrics checker recognizes only the expected None.kind
AttributeError in the authored metrics module, with an empty fake sink; syntax
errors, missing dependencies, unrelated exceptions and fabricated matching
errors from wrappers propagate instead. The URL regression is a wrong return
value, not an exception. Literal probe expectations also cover unaffected inputs.
Passing the corrected base probes does not prove that it has no other defects.

Unit tests in `tests/test_launchpad_history.py` assert the precise failure sets,
corrected base outcomes, unchanged behavior, no input mutation and the public
export boundary. Native Harbor preparation is tested for the entire expanded
inventory without launching an agent/container. The original twelve-case tests
continue to check their fixed initial coverage while permitting additive cases.

## Verification

Executed from `code-review-eval/`:

| Exact command | Result |
|---|---|
| `uv sync --locked` | Exit 0 |
| `uv run python validate_fixtures.py examples/* fixtures/*` | Exit 0; 17 fixtures validated, no reviewer executed |
| `uv run python -m unittest discover -s tests -p 'test_launchpad_history.py' -v` | Exit 0; 11 tests, OK |
| `uv run python -m unittest discover -s tests -v` | Exit 0; 141 tests in 39.730s, OK, no skips |
| `uv run python -m reference_checks.launchpad_history case-0016 --side head` | Exit 1 as intended; 12/16 probes |
| `uv run python -m reference_checks.launchpad_history case-0016 --side base` | Exit 0; 16/16 identical probes |
| `uv run python -m reference_checks.launchpad_history case-0017 --side head` | Exit 1 as intended; 5/8 probes |
| `uv run python -m reference_checks.launchpad_history case-0017 --side base` | Exit 0; 8/8 identical probes |

The full-suite count includes other tests added in the shared checkout. No model
calls, credentials, real services, commits or pushes were used for this extension.
