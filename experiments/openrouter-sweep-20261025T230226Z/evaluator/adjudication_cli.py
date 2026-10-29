"""Evaluator-only, resumable prompts over the existing adjudication forms."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

from review_reporting import (
    approve_form, form_snapshots, load_run, save_json, validate_human,
)
from validate_fixtures import FixtureError


class StopGrading(Exception):
    pass


def grade(output: Path, *, case_id: str | None = None, practice: bool = False,
          ask=input, emit=print) -> None:
    """No suggestions or semantic matching: every decision comes from the operator."""
    if not practice and not sys.stdin.isatty():
        raise FixtureError("human grading requires an interactive terminal; use --practice for simulations")
    originals = form_snapshots(output)
    _, prepared = load_run(output)
    if case_id and case_id not in {r[0]["case_id"] for r in prepared}:
        raise FixtureError(f"unknown case: {case_id}")

    def prompt(label, choices=None, default=""):
        while True:
            answer = ask(f"{label} [{default}] (q: save/quit): ").strip()
            if answer == "q":
                raise StopGrading
            if not answer:
                return default
            if choices is None or answer in choices:
                return answer
            emit("Choose: " + ", ".join(choices))

    def reason(default):
        while True:
            answer = prompt("Reason (evidence, not wording similarity)", default=default)
            if answer:
                return answer
            emit("A resolved judgment requires a reason.")

    emit("PRIVATE evaluator material. Never share this view with a reviewer.")
    emit("PRACTICE: no human approval or HUMAN assessments." if practice else
         "Human mode: only confirm judgments you personally reviewed; no agent suggestions count as approval.")
    try:
        for report, private, human, template in prepared:
            if case_id and report["case_id"] != case_id:
                continue
            if report["status"] != "completed":
                emit(f"{report['case_id']}: {report['status']}; execution unavailable, not a clean review.")
                continue
            directory = output / report["case_id"]
            path = directory / "adjudication.json"
            retained = originals[path]
            if path.read_bytes() != retained:
                raise FixtureError("adjudication changed in another session; restart to resume")

            def save(candidate):
                nonlocal human, retained
                candidate["approval"] = None
                validate_human(candidate, template, private)
                if path.read_bytes() != retained:
                    raise FixtureError("adjudication changed in another session; restart to resume")
                save_json(path, candidate)
                retained = path.read_bytes()
                human = candidate

            request = json.loads((directory / "request.json").read_text(encoding="utf-8"))
            review = json.loads((directory / "review.json").read_text(encoding="utf-8"))
            emit(f"\n=== {report['case_id']} === Execution: {report['status']}")
            emit("REVIEW: " + json.dumps(review, indent=2))
            emit("CHANGE: " + request["change"]["description"])
            diff = request["change"]["diff"]
            emit("DIFF:\n" + (diff["artifact"]["content"] if diff["status"] == "available" else "Unavailable"))
            for context in request["context_manifest"]:
                if "content" in context:
                    emit(f"CODE {context['snapshot_id']}:{context['path']}\n" + "\n".join(
                        f"{i:4}: {line}" for i, line in enumerate(context["content"].splitlines(), 1)))
            emit("PRIVATE REFERENCE (including non-findings and behavior rubric):\n" +
                 json.dumps(private["expectations"], indent=2))
            emit("Annotation verification: " + json.dumps(private["provenance"]["verification"]))
            emit(f"Trace: {directory / 'trace.json'}")
            if prompt("Grade this case? yes/skip", ("yes", "skip"), "skip") == "skip":
                continue
            actor = prompt("Operator identifier", default=human["adjudicator"] or "")
            if not actor:
                emit("No identifier; leaving case unchanged.")
                continue
            candidate = copy.deepcopy(human)
            candidate["adjudicator"] = actor
            if candidate["adjudicator"] != human["adjudicator"]:
                save(candidate)
            for index, finding in enumerate(review["findings"]):
                row = human["findings"][index]
                emit(f"\n{finding['id']}: {finding['text']}\nPrevious: {json.dumps(row)}")
                verdict = prompt("Verdict", ("valid", "invalid", "duplicate", "unresolved"), row["verdict"])
                updated = dict(row, verdict=verdict, reference_id=None, duplicate_of=None)
                if verdict == "valid":
                    references = [r["id"] for r in private["expectations"]["required_findings"]]
                    ref = prompt("Reference ID or novel", [*references, "novel"], row["reference_id"] or "novel")
                    updated["reference_id"] = None if ref == "novel" else ref
                if verdict == "duplicate":
                    targets = [r["finding_id"] for r in human["findings"]
                               if r["finding_id"] != row["finding_id"] and r["verdict"] in ("valid", "invalid")]
                    if not targets:
                        emit("Resolve the distinct target first; leaving this finding unchanged.")
                        continue
                    updated["duplicate_of"] = prompt("Duplicate of", targets, row["duplicate_of"] or targets[0])
                updated["reason"] = reason(row["reason"]) if verdict != "unresolved" else row["reason"]
                candidate = copy.deepcopy(human)
                candidate["findings"][index] = updated
                try:
                    save(candidate)
                except FixtureError as exc:
                    emit(str(exc) + "; previous judgment retained. Resume to change it.")
            if not review["findings"]:
                empty = human["empty_review"]
                verdict = prompt("Explicitly approve this EMPTY review as inspected?", ("approved", "unresolved"), empty["verdict"])
                candidate = copy.deepcopy(human)
                candidate["empty_review"] = {"verdict": verdict,
                    "reason": reason(empty["reason"]) if verdict == "approved" else empty["reason"]}
                save(candidate)
            for key in human["case_verdicts"]:
                row = human["case_verdicts"][key]
                verdict = prompt(key, ("pass", "fail", "not_applicable", "unresolved"), row["verdict"])
                candidate = copy.deepcopy(human)
                candidate["case_verdicts"][key] = {"verdict": verdict,
                    "reason": reason(row["reason"]) if verdict != "unresolved" else row["reason"]}
                save(candidate)
            token = "PRACTICE" if practice else "HUMAN"
            emit("Confirm the current form, including any unresolved entries. Changes invalidate this approval.")
            if prompt(f"Type {token} to attest these are {'simulation decisions, NOT human approval' if practice else 'your own human judgments'}") == token:
                candidate = copy.deepcopy(human)
                approve_form(candidate, "simulation" if practice else "human")
                validate_human(candidate, template, private)
                if path.read_bytes() != retained:
                    raise FixtureError("adjudication changed in another session; restart")
                save_json(path, candidate)
                emit("Confirmed. Run adjudicate to import and refresh reports.")
            else:
                emit("Draft saved; NOT approved or scored.")
    except (StopGrading, EOFError, KeyboardInterrupt):
        emit("\nProgress saved. Resume with the same grade command; unfinished edits were not applied.")
