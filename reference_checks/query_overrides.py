"""Evaluator-only checks for two trusted, authored fixtures; not a sandbox.

Validation still never executes snapshots. This explicit reference command does.
Run from the repository root with python -m reference_checks.query_overrides CASE.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from validate_fixtures import validate_fixture

ROOT = Path(__file__).resolve().parents[1]
CASE_IDS = ("case-0004", "case-0005")
PROJECT_PATH = "src/request_url.py"
URL_PREFIX = "https://catalogue.example.test:8443/items%2Ffeatured;list"


@dataclass(frozen=True)
class Probe:
    name: str
    query: str
    overrides: dict[str, str | None] | None
    expected: dict[str, list[str]]


# Literal expected multimaps, independent of the fixture's pair-filter algorithm.
# Cross-key order/escaping may normalize; order within untouched repeated keys may not.
PROBES = (
    Probe("existing-single", "sort=old", {"sort": "new"}, {"sort": ["new"]}),
    Probe(
        "existing-repeated", "sort=old&sort=older&tag=a&tag=b",
        {"sort": "new"}, {"sort": ["new"], "tag": ["a", "b"]},
    ),
    Probe("empty-override", "sort=old", {"sort": ""}, {"sort": [""]}),
    Probe(
        "encoded-key", "s%6Frt=old&sort=older&tag=a",
        {"sort": "new"}, {"sort": ["new"], "tag": ["a"]},
    ),
    Probe(
        "several-overrides", "sort=old&page=1&tag=a&tag=b&keep=",
        {"sort": "new", "page": "2", "keep": None, "missing": None},
        {"sort": ["new"], "page": ["2"], "tag": ["a", "b"], "keep": [""]},
    ),
    Probe(
        "case-sensitive-keys", "SORT=upper&sort=old",
        {"sort": "new"}, {"SORT": ["upper"], "sort": ["new"]},
    ),
    Probe(
        "no-overrides", "sort=old&tag=a&tag=&tag=b", None,
        {"sort": ["old"], "tag": ["a", "", "b"]},
    ),
    Probe(
        "empty-overrides", "sort=old&tag=a&tag=b", {},
        {"sort": ["old"], "tag": ["a", "b"]},
    ),
    Probe(
        "new-key", "tag=a&tag=b", {"sort": "new"},
        {"tag": ["a", "b"], "sort": ["new"]},
    ),
    Probe(
        "none-existing", "sort=old&sort=older", {"sort": None},
        {"sort": ["old", "older"]},
    ),
    Probe("none-missing", "tag=a", {"sort": None}, {"tag": ["a"]}),
    Probe(
        "blank-unrelated", "tag=&tag=b&keep=", {"sort": "new"},
        {"tag": ["", "b"], "keep": [""], "sort": ["new"]},
    ),
    Probe(
        "encoding-values", "tag=x", {"filter name": "red & blue/雪+%"},
        {"tag": ["x"], "filter name": ["red & blue/雪+%"]},
    ),
    Probe("empty-query", "", {"sort": "new"}, {"sort": ["new"]}),
)


def load_builder(case_id: str, side: str = "head") -> Callable[..., str]:
    """Execute only a named author-owned snapshot after integrity validation."""
    if case_id not in CASE_IDS or side not in ("base", "head"):
        raise ValueError("Only the authored query-override pair is supported")
    directory = ROOT / "fixtures" / case_id
    public, _ = validate_fixture(directory)
    item = next(f for f in public["snapshots"][side]["files"] if f["path"] == PROJECT_PATH)
    source = (directory / "environment/blobs" / item["sha256"]).read_text(encoding="utf-8")
    namespace = {"__name__": "fixture_request_url"}
    exec(compile(source, f"{case_id}/{side}/{PROJECT_PATH}", "exec"), namespace)
    return namespace["request_url"]


def check_contract(builder: Callable[..., str]) -> dict[str, str]:
    """Return semantic mismatches; exceptions propagate and are never a defect pass."""
    failures = {}
    for probe in PROBES:
        link = f"{URL_PREFIX}?{probe.query}#page-2"
        overrides = None if probe.overrides is None else dict(probe.overrides)
        before = None if overrides is None else dict(overrides)
        result = builder(link, overrides)
        original, built = urlsplit(link), urlsplit(result)
        actual = parse_qs(built.query, keep_blank_values=True)
        problems = []
        if actual != probe.expected:
            problems.append(f"expected query {probe.expected!r}, got {actual!r}")
        if built._replace(query="") != original._replace(query=""):
            problems.append("changed URL components outside the query")
        if overrides != before:
            problems.append("mutated the override mapping")
        if problems:
            failures[probe.name] = "; ".join(problems)
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case_id", choices=CASE_IDS)
    args = parser.parse_args()
    failures = check_contract(load_builder(args.case_id))
    for name, detail in failures.items():
        print(f"FAIL {name}: {detail}")
    print(f"{args.case_id}: {len(PROBES) - len(failures)}/{len(PROBES)} contract probes passed.")
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(main())
