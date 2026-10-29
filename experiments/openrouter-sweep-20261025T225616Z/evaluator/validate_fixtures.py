"""Offline structural/integrity validation, not execution, isolation, or grading."""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
from graphlib import CycleError, TopologicalSorter
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

SCHEMAS = Path(__file__).parent / "schemas"
COUNTERS = ("tool_calls", "shell_invocations", "repository_read_attempts", "returned_bytes")


class FixtureError(ValueError):
    """An invalid fixture, with a diagnostic suitable for the CLI."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise FixtureError(message)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def strict_json(data: bytes):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, f"duplicate JSON key: {key}")
            result[key] = value
        return result

    def invalid_constant(value):
        raise FixtureError(f"non-JSON numeric constant: {value}")

    return json.loads(data, object_pairs_hook=pairs, parse_constant=invalid_constant)


def read_artifact(root: Path, relative: str) -> bytes:
    path = root / relative
    require(path.resolve().is_relative_to(root), f"artifact escapes fixture: {relative}")
    require(not any(p.is_symlink() for p in (path, *path.parents) if p != root and root in p.parents),
            f"symlink artifact: {relative}")
    return path.read_bytes()


def schema_validators() -> dict[str, Draft202012Validator]:
    schemas = [strict_json(path.read_bytes()) for path in sorted(SCHEMAS.glob("*.schema.json"))]
    registry = Registry().with_resources((s["$id"], Resource.from_contents(s)) for s in schemas)
    result = {}
    for schema in schemas:
        Draft202012Validator.check_schema(schema)
        result[schema["$id"].split(":")[-2]] = Draft202012Validator(schema, registry=registry)
    return result


VALIDATORS = schema_validators()


def check_schema(name: str, value) -> None:
    error = next(VALIDATORS[name].iter_errors(value), None)
    if error:
        location = "/".join(map(str, error.absolute_path)) or "<root>"
        raise FixtureError(f"{name}/{location}: {error.message}")


def generated_diff(snapshots: dict[str, dict[str, str]]) -> str:
    base, head = snapshots["base"], snapshots["head"]
    return "".join(
        "".join(difflib.unified_diff(
            base.get(path, "").splitlines(keepends=True),
            head.get(path, "").splitlines(keepends=True),
            fromfile=f"a/{path}" if path in base else "/dev/null",
            tofile=f"b/{path}" if path in head else "/dev/null",
            n=3,
        ))
        for path in sorted(base.keys() | head.keys())
    )


def validate_fixture(directory: Path | str) -> tuple[dict, dict]:
    root = Path(directory).resolve()
    raw = read_artifact(root, "reviewer/input.json")
    public = strict_json(raw)
    private = strict_json(read_artifact(root, "private/expectations.json"))
    check_schema("reviewer-input", public)
    check_schema("expectations", private)
    for key in ("case_id", "revision", "schema_version"):
        require(public[key] == private[key], f"public/private {key} mismatch")
    require(private["input_sha256"] == sha256(raw), "input_sha256 mismatch")

    # Source bytes live outside reviewer/ even when the manifest is public.
    snapshots, by_id = {}, {}
    for side, snapshot in public["snapshots"].items():
        files = {}
        for item in snapshot["files"]:
            path = item["path"]
            require(path not in files, f"duplicate snapshot path: {side}/{path}")
            content = read_artifact(root, f"environment/blobs/{item['sha256']}")
            require(sha256(content) == item["sha256"], f"blob hash mismatch: {side}/{path}")
            text = content.decode("utf-8")
            require(not text or text.endswith("\n"), f"text blob must end with newline: {path}")
            require("\x00" not in text, f"binary blob not supported: {path}")
            files[path] = text
        sid = snapshot["id"]
        require(sid not in ("base", "head"), "snapshot ID conflicts with a branch alias")
        require(sid not in by_id or by_id[sid] == files, f"conflicting snapshot id: {sid}")
        by_id[sid] = files
        snapshots[side] = files

    diff = public["change"]["diff"]
    if diff["status"] == "available":
        artifact = diff["artifact"]
        require(sha256(artifact["content"].encode()) == artifact["sha256"], "diff hash mismatch")
        require(artifact["content"] == generated_diff(snapshots), "diff disagrees with snapshots")

    manifest = {}
    initial_evidence = set()
    for entry in public["context_manifest"]:
        key = (public["repository"], entry["snapshot_id"], entry["path"])
        require(key not in manifest, f"duplicate context entry: {key}")
        manifest[key] = entry
        require(entry["snapshot_id"] in by_id, f"unknown context snapshot: {key}")
        files = by_id[entry["snapshot_id"]]
        if entry["availability"] == "available":
            require(entry["path"] in files, f"available context file absent: {key}")
            if entry["delivery"] == "initial":
                require(entry["content"] == files[entry["path"]], f"initial context mismatch: {key}")
                initial_evidence.add(key)
        elif entry["availability"] == "missing":
            require(entry["path"] not in files, f"missing context file exists: {key}")

    tools = {tool["name"]: tool for tool in public["tools"]}
    require(len(tools) == len(public["tools"]), "duplicate tool name")
    start = public["start"]
    continuation = start["mode"] == "continuation"
    allowed = {"input.json", "prefix.json"} if continuation else {"input.json"}
    require({p.name for p in (root / "reviewer").iterdir()} == allowed,
            "unexpected or missing reviewer artifact (possible private-data exposure)")
    observed = dict.fromkeys(COUNTERS, 0)
    longest_call_ms = 0
    prefix_evidence = set()
    if continuation:
        require(start["snapshots"] == {side: s["id"] for side, s in public["snapshots"].items()},
                "checkpoint snapshot mismatch")
        prefix_raw = read_artifact(root, "reviewer/prefix.json")
        require(sha256(prefix_raw) == start["prefix"]["sha256"], "prefix hash mismatch")
        prefix = strict_json(prefix_raw)
        check_schema("atif-prefix", prefix)
        seen_calls = set()
        revisions = {side: s["id"] for side, s in public["snapshots"].items()}
        revisions.update({sid: sid for sid in by_id})
        for index, step in enumerate(prefix["steps"], 1):
            require(step["step_id"] == index, "ATIF step IDs must be sequential from 1")
            calls = step.get("tool_calls", [])
            call_ids = [call["tool_call_id"] for call in calls]
            require(len(set(call_ids)) == len(call_ids) and not seen_calls.intersection(call_ids),
                    "duplicate ATIF tool_call_id")
            seen_calls.update(call_ids)
            results = step.get("observation", {}).get("results", [])
            result_ids = [result["source_call_id"] for result in results]
            require(len(result_ids) == len(call_ids) and set(result_ids) == set(call_ids),
                    "each ATIF call requires exactly one result on the same step")
            results_by_id = {result["source_call_id"]: result for result in results}
            for call in calls:
                require(call["function_name"] in tools, "prefix invokes undeclared tool")
                tool = tools[call["function_name"]]
                result = results_by_id[call["tool_call_id"]]
                meta = result["extra"]["code_review_eval"]
                longest_call_ms = max(longest_call_ms, meta["duration_ms"])
                if meta["status"] == "completed":
                    require(meta["exit_code"] == 0, "completed call must have exit code 0")
                elif meta["status"] == "failed":
                    require(meta["exit_code"] is not None and meta["exit_code"] != 0,
                            "failed call must have a nonzero exit code")
                observed["tool_calls"] += 1
                observed["shell_invocations"] += tool["kind"] == "shell"
                observed["returned_bytes"] += len(result["content"].encode()) + len(meta["stderr"].encode())
                for read in meta["repository_reads"]:
                    observed["repository_read_attempts"] += 1
                    require("repository.read" in tool["operations"], "repository read capability not declared")
                    expected_sid = revisions.get(read["requested_revision"]) if read["repository"] == public["repository"] else None
                    require(read["resolved_snapshot_id"] == expected_sid, "read revision/snapshot mismatch")
                    key = (read["repository"], expected_sid, read["path"])
                    entry = manifest.get(key)
                    if read["status"] == "completed":
                        require(entry is not None and entry["availability"] == "available",
                                "successful prefix read is not available in manifest")
                        content = by_id[expected_sid][read["path"]]
                        require(read["returned_bytes"] == len(content.encode()) and
                                read["content_sha256"] == sha256(content.encode()),
                                "successful read does not match immutable snapshot bytes")
                        require(content in result["content"], "successful whole-file evidence absent from output")
                        prefix_evidence.add(key)
                    elif read["status"] in ("missing", "error", "blocked"):
                        require(read["returned_bytes"] == 0 and read["content_sha256"] is None,
                                "failed reads must not claim successful file content")
                    if entry is not None and entry["availability"] in ("missing", "error"):
                        require(read["status"] == entry["availability"], "read disagrees with declared unavailable response")
                        require(entry["error_message"] in result["content"] + meta["stderr"],
                                "declared read error missing from visible output")

    budgets = public["budgets"]
    require(budgets["inherited"]["wall_time_ms"] >= longest_call_ms,
            "inherited wall time cannot be shorter than a recorded call")
    for key, whole in budgets["whole_path"].items():
        inherited, remaining = budgets["inherited"][key], budgets["remaining"][key]
        if not continuation:
            require(inherited == 0, f"fresh inherited {key} must be zero")
        if key in observed:
            require(inherited == observed[key], f"inherited {key} disagrees with prefix")
        if whole is None:
            require(remaining is None, f"uncapped {key} must have null remaining limit")
        else:
            require(inherited is not None and remaining is not None and
                    whole >= inherited and remaining == whole - inherited,
                    f"infeasible remaining budget: {key}")

    expectations = private["expectations"]
    require((expectations["continuation"] is not None) == continuation,
            "continuation expectations must agree with start mode")
    require(private["labels"]["change_outcome"] != "clean" or not expectations["required_findings"],
            "clean case cannot have required defects")
    require((private["provenance"]["kind"] == "derived") == bool(private["provenance"]["sources"]),
            "derived provenance needs sources; original provenance must not claim them")
    ids = [item["id"] for name in ("required_findings", "non_findings") for item in expectations[name]]
    for finding in expectations["required_findings"]:
        for location in finding["locations"]:
            files = snapshots[location["side"]]
            require(location["path"] in files, "finding location absent from selected snapshot")
            lines = location["lines"]
            if lines is not None:
                require(lines["start"] <= lines["end"] <= len(files[location["path"]].splitlines()),
                        "invalid finding line range")

    requirements = expectations["retrieval"]["requirements"]
    if public["protocol"]["name"] == "fixed-context":
        require(not requirements, "fixed-context cases cannot require repository retrieval")
    for requirement in requirements:
        ids.append(requirement["id"])
        sources = {(s["repository"], s["snapshot_id"], s["path"]) for s in requirement["acceptable_sources"]}
        for key in sources:
            require(key in manifest and manifest[key]["availability"] == "available",
                    "required evidence source unavailable in context manifest")
        inherited_evidence = initial_evidence | prefix_evidence
        needs_read = requirement["evidence_origin"] == "new-suffix" or not sources.intersection(inherited_evidence)
        if needs_read:
            remaining = budgets["remaining"]
            minimum_bytes = min(len(by_id[sid][path].encode()) for _, sid, path in sources)
            has_read_tool = any(
                "repository.read" in tool["operations"] and
                (tool["kind"] != "shell" or remaining["shell_invocations"] > 0)
                for tool in tools.values()
            )
            require(has_read_tool and remaining["tool_calls"] > 0 and
                    remaining["repository_read_attempts"] > 0 and
                    remaining["returned_bytes"] >= minimum_bytes and remaining["wall_time_ms"] > 0,
                    "remaining budget cannot obtain required evidence")

    if continuation:
        rest = expectations["continuation"]
        ids.extend(action["id"] for action in rest["required_remaining_actions"])
        order_ids = {r["id"] for r in requirements} | {a["id"] for a in rest["required_remaining_actions"]} | {"final_review"}
        graph = {}
        for edge in rest["essential_order"]:
            require(edge["before"] in order_ids and edge["after"] in order_ids, "unknown ordering constraint id")
            graph.setdefault(edge["after"], set()).add(edge["before"])
        try:
            tuple(TopologicalSorter(graph).static_order())
        except CycleError as exc:
            raise FixtureError("cyclic continuation ordering constraints") from exc
    require("final_review" not in ids and len(ids) == len(set(ids)), "expectation IDs must be unique and not reserved")
    return public, private


def validate_dataset(directories) -> int:
    cases, groups = {}, {}
    count = 0
    for directory in directories:
        public, private = validate_fixture(directory)
        case_id = public["case_id"]
        require(case_id not in cases, f"duplicate case_id: {case_id}")
        cases[case_id] = private
        dataset = private["dataset"]
        group = (dataset["id"], dataset["version"], dataset["group_id"])
        require(group not in groups or groups[group] == dataset["partition"], "scenario group crosses dataset partitions")
        groups[group] = dataset["partition"]
        count += 1
    for private in cases.values():
        dataset = private["dataset"]
        for relation in dataset["related_cases"]:
            other = cases.get(relation["case_id"])
            if other is not None:
                require(all(dataset[key] == other["dataset"][key] for key in ("id", "version", "partition", "group_id")),
                        "related cases must share dataset version, group, and partition")
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixtures", type=Path, nargs="+", help="fixture directories (validate together to check partitions)")
    args = parser.parse_args()
    try:
        count = validate_dataset(args.fixtures)
    except (FixtureError, OSError, UnicodeError, json.JSONDecodeError) as exc:
        parser.exit(1, f"Invalid fixture: {exc}\n")
    print(f"Validated {count} fixture(s). No reviewer was executed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
