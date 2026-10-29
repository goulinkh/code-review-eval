"""Opt-in checks for two trusted, independently authored Launchpad reductions.

NOT a sandbox or reviewer grader. Structural fixture validation never invokes
this module or executes snapshot source. No source repository/service is needed.
Run: uv run python -m reference_checks.launchpad_history CASE [--side base|head]
The base is a corrected control; each head deliberately reintroduces one bug.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from pathlib import Path
import sys
from types import ModuleType
from unittest.mock import patch

from reference_checks.corpus import Report
from validate_fixtures import validate_fixture

ROOT = Path(__file__).resolve().parents[1]
MODULES = {
    "case-0016": ("issue_links",),
    "case-0017": ("records", "metrics"),
}


def load_project(case_id: str, side: str = "head") -> dict[str, ModuleType]:
    """Integrity-check then execute only explicitly named trusted author modules.

    Unexpected syntax/import/runtime failures propagate. Temporary module names
    support local imports without putting a fixture directory on sys.path.
    """
    if case_id not in MODULES or side not in ("base", "head"):
        raise ValueError("Only the named history fixtures and base/head are supported")
    directory = ROOT / "fixtures" / case_id
    public, _ = validate_fixture(directory)
    files = {item["path"]: item["sha256"] for item in public["snapshots"][side]["files"]}
    modules = {}
    with patch.dict(sys.modules):
        for name in MODULES[case_id]:
            module = ModuleType(name)
            module.__file__ = f"{case_id}/{side}/src/{name}.py"
            sys.modules[name] = module
            source = (directory / "environment/blobs" / files[f"src/{name}.py"]).read_text(encoding="utf-8")
            exec(compile(source, module.__file__, "exec"), module.__dict__)
            modules[name] = module
    return modules


# Literal expected outputs, independent of regex construction and URL parsing.
ISSUE_PROBES = (
    ("forge-plain", "https://forge.example.test/org/repo/issues/42",
     ("https://forge.example.test/org/repo/issues", "42")),
    ("forge-trailing-slash", "https://forge.example.test/org/repo/issues/42/",
     ("https://forge.example.test/org/repo/issues", "42")),
    ("code-plain", "https://code.example.test/team/project/issues/17",
     ("https://code.example.test/team/project/issues", "17")),
    ("code-trailing-slash", "https://code.example.test/team/project/issues/17/",
     ("https://code.example.test/team/project/issues", "17")),
    ("query-fragment", "https://forge.example.test/org/repo/issues/42?view=full#note",
     ("https://forge.example.test/org/repo/issues", "42")),
    ("trailing-query-fragment", "https://forge.example.test/org/repo/issues/42/?view=full#note",
     ("https://forge.example.test/org/repo/issues", "42")),
    ("leading-zeroes", "https://code.example.test/team/project/issues/00017",
     ("https://code.example.test/team/project/issues", "00017")),
    ("trailing-leading-zeroes", "https://code.example.test/team/project/issues/00017/",
     ("https://code.example.test/team/project/issues", "00017")),
    ("http", "http://forge.example.test/org/repo/issues/42",
     ("http://forge.example.test/org/repo/issues", "42")),
    ("unsupported-host", "https://other.example.test/org/repo/issues/42", None),
    ("unsupported-scheme", "ftp://forge.example.test/org/repo/issues/42", None),
    ("non-numeric", "https://forge.example.test/org/repo/issues/topic/", None),
    ("missing-number", "https://forge.example.test/org/repo/issues/", None),
    ("extra-tail", "https://forge.example.test/org/repo/issues/42/comments", None),
    ("double-slash", "https://code.example.test/team/project/issues/17//", None),
    ("missing-repository", "https://code.example.test/team/issues/17", None),
)


def check_issue_links(parser) -> Report:
    """Exceptions are never counted as the intended URL rejection."""
    failures = {}
    for name, link, expected in ISSUE_PROBES:
        actual = parser(link)
        if actual != expected:
            failures[name] = f"expected {expected!r}, got {actual!r}"
    return Report(len(ISSUE_PROBES), failures)


class FakeSink:
    """A local event log, not a metrics connection."""

    def __init__(self):
        self.calls = []

    def timing(self, name, milliseconds, labels):
        self.calls.append((name, milliseconds, dict(labels)))


# name, leaf, live kind (None = deleted), seconds, expected type, literal ms
BUILD_PROBES = (
    ("live-package", "queued-PACKAGE-1", "PACKAGE", 0.25, "PACKAGE", 250.0),
    ("live-bundle", "queued-BUNDLE-2", "BUNDLE", 0.5, "BUNDLE", 500.0),
    ("live-image", "queued-IMAGE-3", "IMAGE", 2.0, "IMAGE", 2000.0),
    ("deleted-package", "queued-PACKAGE-4", None, 0.25, "PACKAGE", 250.0),
    ("deleted-bundle", "queued-BUNDLE-5", None, 0.5, "BUNDLE", 500.0),
    ("deleted-hyphenated-prefix", "retry-batch-queued-IMAGE-6", None, 1.25, "IMAGE", 1250.0),
)


def check_metrics(project: dict[str, ModuleType]) -> Report:
    records, metrics = project["records"], project["metrics"]
    cases = [
        ("manual", records.UserUpload("manual-file"), 1.25, "manual", 1250.0),
        ("manual-zero", records.UserUpload("manual-file"), 0.0, "manual", 0.0),
    ]
    cases.extend(
        (name, records.BuildUpload(leaf, None if kind is None else records.Build(kind)), seconds, expected_type, milliseconds)
        for name, leaf, kind, seconds, expected_type, milliseconds in BUILD_PROBES
    )
    failures = {}
    for name, upload, seconds, kind, milliseconds in cases:
        sink = FakeSink()
        before = deepcopy(upload)
        try:
            metrics.record_duration(upload, seconds, sink)
        except AttributeError as exc:
            # The missing-build dereference IS this fixture's defect. Do not
            # count an arbitrary AttributeError (or a failing fake) as evidence.
            if not (isinstance(upload, records.BuildUpload) and upload.build is None
                    and exc.obj is None and exc.name == "kind"):
                raise
            origin = exc.__traceback__
            while origin.tb_next is not None:
                origin = origin.tb_next
            if origin.tb_frame.f_code.co_filename != metrics.__file__:
                raise
            if sink.calls or upload != before:
                raise AssertionError("Intended dereference probe had unrelated side effects") from exc
            failures[name] = "deleted build dereferenced as None.kind before metric emission"
            continue
        expected = [("upload_duration", milliseconds, {"type": kind})]
        if sink.calls != expected or upload != before:
            failures[name] = f"expected calls {expected!r} and unchanged input, got {sink.calls!r}, {upload!r}"
    return Report(len(cases), failures)


def check_case(case_id: str, side: str = "head") -> Report:
    project = load_project(case_id, side)
    if case_id == "case-0016":
        return check_issue_links(project["issue_links"].parse_issue_url)
    return check_metrics(project)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case_id", choices=MODULES)
    parser.add_argument("--side", choices=("base", "head"), default="head")
    args = parser.parse_args()
    report = check_case(args.case_id, args.side)
    for name, detail in report.failures.items():
        print(f"FAIL {name}: {detail}")
    print(f"{args.case_id}/{args.side}: {report.total - len(report.failures)}/{report.total} contract probes passed.")
    return int(bool(report.failures))


if __name__ == "__main__":
    raise SystemExit(main())
