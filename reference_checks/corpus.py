"""Evaluator-only contract probes for explicitly named, trusted authored snapshots.

Opt-in snapshot execution, NOT a sandbox, reviewer score, or semantic grader.
Structural validation never imports this module or executes fixture source.
Run: uv run python -m reference_checks.corpus CASE_ID
The two insufficient-context cases deliberately have no executable defect oracle.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

from reference_checks import query_overrides
from validate_fixtures import validate_fixture

ROOT = Path(__file__).resolve().parents[1]
FAMILIES = {
    "case-0006": "compatibility", "case-0007": "compatibility",
    "case-0008": "security", "case-0009": "security",
    "case-0010": "reliability", "case-0011": "reliability",
    "case-0014": "security", "case-0015": "reliability",
}
EXECUTABLE_CASES = (*query_overrides.CASE_IDS, *FAMILIES)
MODULES = {
    "compatibility": ("payload_codec", "claims", "commands"),
    "security": ("access", "admin"),
    "reliability": ("worker",),
}


@dataclass(frozen=True)
class Report:
    total: int
    failures: dict[str, str]


def snapshot_sources(case_id: str, side: str = "head") -> dict[str, str]:
    """Integrity-check and read a known fixture; reading does not execute it."""
    if case_id not in EXECUTABLE_CASES or side not in ("base", "head"):
        raise ValueError("Only named executable author fixtures and base/head are supported")
    directory = ROOT / "fixtures" / case_id
    public, _ = validate_fixture(directory)
    return {
        item["path"]: (directory / "environment/blobs" / item["sha256"]).read_text(
            encoding="utf-8",
        )
        for item in public["snapshots"][side]["files"]
    }


def load_project(case_id: str, side: str = "head") -> dict[str, ModuleType]:
    """Execute only allowlisted author modules. Exceptions propagate, not defect passes.

    No checkout mount, sys.path insertion, subprocess, service, or retrieval.
    Temporary module entries support the miniature's ordinary local imports and
    are restored even on error. This is trusted author execution, not isolation.
    """
    if case_id not in FAMILIES:
        raise ValueError("Use query_overrides.load_builder for the existing pair")
    sources = snapshot_sources(case_id, side)
    modules = {}
    with patch.dict(sys.modules):
        for name in MODULES[FAMILIES[case_id]]:
            module = ModuleType(name)
            sys.modules[name] = module
            exec(compile(sources[f"src/{name}.py"], f"{case_id}/{side}/src/{name}.py", "exec"), module.__dict__)
            modules[name] = module
    return modules


def _difference(actual, expected) -> str | None:
    # JSON comparison distinguishes bool from int, unlike Python's True == 1.
    if json.dumps(actual, sort_keys=True) != json.dumps(expected, sort_keys=True):
        return f"expected {expected!r}, got {actual!r}"
    return None


def check_compatibility(project: dict[str, ModuleType]) -> Report:
    producer = project["commands"].enumerate_commands
    claim = project["claims"].claim_commands
    rejection = project["payload_codec"].PayloadTypeError
    # Literal wire expectations, not a reimplementation of the producer algorithm.
    cases = (
        ("empty-batch", [], 1000, []),
        ("fresh-flag", [{"id": "a", "command": "review", "created_at": 999}], 1000,
         [{"id": "a", "command": "review", "expired": False}]),
        ("boundary-flag", [{"id": "b", "command": "cancel", "created_at": 100}], 1000,
         [{"id": "b", "command": "cancel", "expired": False}]),
        ("expired-flag", [{"id": "c", "command": "review", "created_at": 99}], 1000,
         [{"id": "c", "command": "review", "expired": True}]),
        ("mixed-batch", [{"id": "雪", "command": "review", "created_at": 0},
                         {"id": "d", "command": "cancel", "created_at": 999}], 1000,
         [{"id": "雪", "command": "review", "expired": True},
          {"id": "d", "command": "cancel", "expired": False}]),
        ("legacy-batch", None, None, [{"id": "legacy", "command": "review"}]),
    )
    failures = {}
    for name, records, reference, expected in cases:
        before = None if records is None else [dict(row) for row in records]
        payload = json.dumps(expected) if records is None else producer(records, reference)
        wire_error = _difference(json.loads(payload), expected)
        if wire_error or records != before:
            failures[name] = wire_error or "mutated producer input"
            continue
        inbox = [{"id": "prior"}]
        try:
            count = claim(payload, inbox)
        except rejection as exc:
            # Only the intended exact decoder rejection is evidence of this bug.
            if str(exc) != "field 'expired' has unsupported type bool":
                raise AssertionError(f"Unrelated payload rejection: {exc}") from exc
            if inbox != [{"id": "prior"}]:
                raise AssertionError("Rejected batch partially modified inbox")
            failures[name] = "expired bool rejected before inbox: " + str(exc)
            continue
        problem = _difference((count, inbox), (len(expected), [{"id": "prior"}, *expected]))
        if problem:
            failures[name] = problem
    invalids = (("int", 1), ("float", 1.5), ("null", None), ("list", []), ("object", {}))
    for name, value in invalids:
        inbox = []
        try:
            claim(json.dumps([{"id": "a", "extra": value}]), inbox)
        except rejection:
            if inbox:
                failures[f"reject-{name}"] = "invalid batch partially modified inbox"
        else:
            failures[f"reject-{name}"] = "invalid field value accepted"
    return Report(len(cases) + len(invalids), failures)


def check_security(project: dict[str, ModuleType]) -> Report:
    update = project["admin"].set_enabled
    listing = project["admin"].list_projects
    admin, other = {"username": "operator"}, {"username": "viewer"}
    cases = (
        ("admin-enable", admin, "operator", "a", True, 200),
        ("admin-disable", admin, "operator", "b", False, 200),
        ("trimmed-config", admin, "  operator\t", "a", True, 200),
        ("unknown-project", admin, "operator", "absent", True, 404),
        ("anonymous", None, "operator", "a", True, 403),
        ("non-admin", other, "operator", "a", True, 403),
        ("case-sensitive-identity", {"username": "Operator"}, "operator", "a", True, 403),
        ("no-config", admin, None, "a", True, 403),
        ("empty-config", admin, "", "a", True, 403),
        ("blank-config", admin, " \t", "a", True, 403),
        ("denied-unknown-project", other, "operator", "absent", True, 403),
    )
    failures = {}
    for name, user, config, key, enabled, status in cases:
        projects = {"a": False, "b": True}
        before_user = None if user is None else dict(user)
        result = update(user, config, projects, key, enabled)
        expected_result = (status, {"id": key, "enabled": enabled} if status == 200 else None)
        expected_state = {"a": False, "b": True}
        if status == 200:
            expected_state[key] = enabled
        problem = _difference((result, projects, user), (expected_result, expected_state, before_user))
        if problem:
            failures[name] = problem
    lists = (
        ("listing-admin", admin, "operator", (200, ["a", "b"])),
        ("listing-non-admin", other, "operator", (403, None)),
        ("listing-unconfigured", admin, None, (403, None)),
        ("listing-anonymous", None, "operator", (403, None)),
    )
    for name, user, config, expected in lists:
        projects = {"b": True, "a": False}
        problem = _difference((listing(user, config, projects), projects),
                              (expected, {"a": False, "b": True}))
        if problem:
            failures[name] = problem
    return Report(len(cases) + len(lists), failures)


class FakeProvider:
    """Local event log; no payment, credentials, network, or external state."""

    def __init__(self):
        self.events = []

    def resolve_account(self, owner):
        self.events.append(("resolve", owner))
        return "account-for-" + owner

    def run(self, account, key):
        self.events.append(("run", account, key))

    def cancel(self, key):
        self.events.append(("cancel", key))


def check_reliability(project: dict[str, ModuleType]) -> Report:
    process = project["worker"].process_command
    failures = {}
    total = 0
    for kind in ("review", "cancel"):
        for age in (0, 899, 900, 901, 1800):
            total += 1
            name = f"{kind}-age-{age}"
            command = {"id": "a", "owner": "person", "kind": kind, "created_at": 100}
            original = dict(command)
            provider = FakeProvider()
            outcomes = {"prior": {"status": "completed"}}
            result = process(command, 100 + age, provider, outcomes)
            # Literal expected terminal state/events, independently of worker branches.
            if age in (901, 1800):
                expected, events = {"status": "expired"}, []
            elif kind == "cancel":
                expected, events = {"status": "cancelled"}, [("cancel", "a")]
            else:
                expected = {"status": "completed"}
                events = [("resolve", "person"), ("run", "account-for-person", "a")]
            expected_state = {"prior": {"status": "completed"}, "a": expected}
            problem = _difference((result, provider.events, outcomes, command),
                                  (expected, events, expected_state, original))
            if problem:
                failures[name] = problem
            # Replay at a later reference must not run again, even after fresh work ages.
            before_events = list(provider.events)
            replay = process(command, 10000, provider, outcomes)
            replay_problem = _difference((replay, provider.events, outcomes),
                                         (expected, before_events, expected_state))
            if replay_problem:
                failures[name] = (failures.get(name, "") + "; replay: " + replay_problem).lstrip("; ")
    return Report(total, failures)


CHECKERS = {
    "compatibility": check_compatibility,
    "security": check_security,
    "reliability": check_reliability,
}


def check_case(case_id: str, side: str = "head") -> Report:
    if case_id in query_overrides.CASE_IDS:
        return Report(len(query_overrides.PROBES), query_overrides.check_contract(
            query_overrides.load_builder(case_id, side),
        ))
    if case_id not in FAMILIES:
        raise ValueError("No executable oracle for unknown/insufficient-context cases")
    return CHECKERS[FAMILIES[case_id]](load_project(case_id, side))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case_id", choices=EXECUTABLE_CASES)
    args = parser.parse_args()
    report = check_case(args.case_id)
    for name, detail in report.failures.items():
        print(f"FAIL {name}: {detail}")
    print(f"{args.case_id}/head: {report.total - len(report.failures)}/{report.total} contract probes passed.")
    return int(bool(report.failures))


if __name__ == "__main__":
    raise SystemExit(main())
