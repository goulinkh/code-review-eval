"""Offline loading and dependency-free SVG views of evaluator result tables."""

from __future__ import annotations

from html import escape
import json
import math
from pathlib import Path

from validate_fixtures import FixtureError, strict_json
from visual_reporting import validate_visual_report


def _result_path(path: str | Path, root: Path) -> Path:
    root = root.resolve()
    path = (root / path).resolve()
    if not path.is_relative_to(root):
        raise FixtureError("result path must stay inside this project (including symlink targets)")
    return path


def load_report_text(path: str | Path, root: Path) -> str:
    """Read a retained report, never its linked evidence, within the project."""
    return _result_path(path, root).read_text(encoding="utf-8")


def load_visuals(path: str | Path, root: Path) -> dict:
    bundle = strict_json(_result_path(path, root).read_bytes())
    validate_visual_report(bundle)
    return bundle


def discover_reports(root: Path) -> list[str]:
    """List retained reports without reading results, labels, or evidence."""
    root = root.resolve()
    reports = []
    for collection, pattern in (("experiments", "*/comparison.json"), ("runs", "**/visuals.json")):
        for path in sorted((root / collection).glob(pattern), reverse=True):
            try:
                resolved = _result_path(path, root)
            except FixtureError:
                continue
            if resolved.is_file():
                reports.append(path.relative_to(root).as_posix())
    return reports


def load_pilot_comparison(path: str | Path, root: Path) -> dict:
    """Read the pilot's existing model summary, not a visuals.json sidecar."""
    bundle = strict_json(_result_path(path, root).read_bytes())

    def require(condition):
        if not condition:
            raise FixtureError("pilot comparison: invalid model summary")

    def count(value):
        return type(value) is int and value >= 0

    def number(value):
        return type(value) in (int, float) and math.isfinite(value) and value >= 0

    require(isinstance(bundle, dict))
    require(count(bundle.get("planned_invocations")) and count(bundle.get("ledger_entries")))
    require(isinstance(bundle.get("models"), list) and bool(bundle["models"]))
    seen = set()
    for model in bundle["models"]:
        require(isinstance(model, dict))
        name = model.get("model_id")
        require(isinstance(name, str) and bool(name) and name not in seen)
        seen.add(name)
        require(count(model.get("attempted")) and count(model.get("finished")))
        require(model["finished"] <= model["attempted"])
        counts = model.get("execution_counts")
        require(isinstance(counts, dict) and all(isinstance(k, str) and count(v) for k, v in counts.items()))
        require(sum(counts.values()) <= model["attempted"])
        require(number(model.get("known_billed_cost_usd")))
        require(count(model.get("unknown_billed_cost_invocations")))
        latency = model.get("latency_ms")
        require(latency is None or isinstance(latency, dict))
        if latency is not None:
            require(all(number(latency.get(key)) for key in ("min", "median", "max")))
            require(latency["min"] <= latency["median"] <= latency["max"])
        usage = model.get("usage")
        require(isinstance(usage, dict))
        for key in ("input_tokens", "output_tokens"):
            item = usage.get(key)
            require(isinstance(item, dict))
            require("known_total" in item and (item["known_total"] is None or number(item["known_total"])))
            require(count(item.get("unknown_invocations")))
            require(count(item.get("runtime_zero_without_provider_response", 0)))
        quality = model.get("quality")
        require(isinstance(quality, dict) and quality.get("status") in ("pending", "adjudicated"))
        for key in ("recall", "precision"):
            metric = quality.get(key)
            require(metric is None or isinstance(metric, dict))
            if metric is not None:
                value = metric.get("value")
                require(value is None or (number(value) and value <= 1))
        false_alarms = quality.get("corrected_case_false_alarm_cases")
        require(false_alarms is None or isinstance(false_alarms, dict))
        if false_alarms is not None:
            require(count(false_alarms.get("count")) and count(false_alarms.get("adjudicated_completed_cases")))
            require(false_alarms["count"] <= false_alarms["adjudicated_completed_cases"])
        variations = model.get("variation_by_case", {})
        require(isinstance(variations, dict))
        for case_id, variation in variations.items():
            require(isinstance(case_id, str) and isinstance(variation, dict))
            require(isinstance(variation.get("status_by_repetition"), dict))
            require(isinstance(variation.get("finding_counts"), list))
            require(count(variation.get("distinct_normalized_review_hashes")))
    return bundle


def pilot_model_rows(bundle: dict) -> list[dict]:
    """Preserve model order and pending/unknown values; never invent a ranking."""
    def quality_value(quality, name):
        if quality["status"] != "adjudicated":
            return "Pending"
        metric = quality.get(name)
        return f"{metric['value']:.1%}" if metric and metric.get("value") is not None else "N/A"

    def tokens(model, name):
        item = model["usage"][name]
        if not model["finished"]:
            return "Not finished"
        unknown = item["unknown_invocations"]
        placeholders = item.get("runtime_zero_without_provider_response", 0)
        if item["known_total"] is None or unknown >= model["finished"] or placeholders >= model["finished"]:
            return "Unknown"
        suffix = f"; {unknown} unknown" if unknown else ""
        if placeholders:
            suffix += f"; {placeholders} unverified zeros"
        return f"{item['known_total']:g} known{suffix}"

    rows = []
    for model in bundle["models"]:
        quality = model["quality"]
        unknown_cost = model["unknown_billed_cost_invocations"]
        cost = ("Not finished" if not model["finished"] else
                "Unknown" if unknown_cost >= model["finished"] else
                f"${model['known_billed_cost_usd']:.9f} known" +
                (f"; {unknown_cost} unknown" if unknown_cost else ""))
        false_alarms = quality.get("corrected_case_false_alarm_cases")
        false_alarm_text = "Pending"
        if quality["status"] == "adjudicated":
            false_alarm_text = (f"{false_alarms['count']}/{false_alarms['adjudicated_completed_cases']}"
                                if false_alarms and false_alarms["adjudicated_completed_cases"] else "N/A")
        rows.append({
            "Model": model["model_id"],
            "Finished / attempted": f"{model['finished']}/{model['attempted']}",
            "Completed": model["execution_counts"].get("completed", 0),
            "Failed / invalid / timed out": sum(v for k, v in model["execution_counts"].items() if k != "completed"),
            "Median latency (ms)": model["latency_ms"]["median"] if model["latency_ms"] is not None else "Unknown",
            "OpenRouter billed subtotal": cost,
            "Input tokens": tokens(model, "input_tokens"),
            "Output tokens": tokens(model, "output_tokens"),
            "Quality": quality["status"],
            "Recall": quality_value(quality, "recall"),
            "Precision": quality_value(quality, "precision"),
            "Corrected-case false alarms": false_alarm_text,
        })
    return rows


def pilot_repetition_rows(bundle: dict) -> list[dict]:
    return [
        {"Model": model["model_id"], "Case": case_id,
         "Status by repetition": json.dumps(variation["status_by_repetition"], sort_keys=True),
         "Finding counts (not scores)": json.dumps(variation["finding_counts"]),
         "Distinct normalized reviews": variation["distinct_normalized_review_hashes"]}
        for model in bundle["models"]
        for case_id, variation in model.get("variation_by_case", {}).items()
    ]


def _metric(bundle, run_key, domain, metric):
    for row in bundle["metrics"]:
        if (row["run_key"], row["case_id"], row["domain"], row["metric"]) == (run_key, None, domain, metric):
            return row
    raise FixtureError(f"visual report: missing run metric {domain}/{metric}")


def _label(run, y):
    raw_name = f"{run['name']} · {run['agent']} / {run['model']}"
    name, short_name = escape(raw_name), escape(raw_name[:85])
    basis = escape(f"{run['quality_basis']} · pending cases: {run['pending_cases']}")
    return (f'<text x="8" y="{y + 15}" font-size="12"><title>{name}</title>{short_name}</text>'
            f'<text x="8" y="{y + 32}" font-size="10">{basis}</text>')


def _svg(title, rows, body):
    title = escape(title)
    return (f'<figure style="overflow-x:auto;margin:12px 0"><figcaption>{title}</figcaption>'
            f'<svg xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{title}" '
            f'viewBox="0 0 1200 {max(1, rows) * 52 + 12}" style="min-width:900px;width:100%;fill:currentColor">'
            f'<title>{title}</title>{body}</svg></figure>')


def metric_chart(bundle: dict, domain: str, metric: str, title: str) -> str:
    rows = [(run, _metric(bundle, run["run_key"], domain, metric)) for run in bundle["runs"]]
    if len({row["unit"] for _, row in rows}) > 1:
        raise FixtureError("visual report: chart cannot mix units")
    ratio = bool(rows and rows[0][1]["unit"] == "ratio")
    maximum = 1 if ratio else max([row["value"] or 0 for _, row in rows] + [1e-12])
    body = []
    for index, (run, row) in enumerate(rows):
        y = index * 52 + 4
        body.append(_label(run, y))
        value = row["value"]
        if value is None:
            label = "N/A" if row["unit"] == "ratio" else "unknown"
        else:
            label = f"{value:.1%} ({row['numerator']}/{row['denominator']})" if ratio else f"{value:g} {row['unit']}"
            body.append(f'<rect x="560" y="{y + 5}" width="{value / maximum * 370:.3f}" height="18" fill="#3b82f6" opacity="0.65"/>')
        if row["lower"] is not None:
            left, right = 560 + row["lower"] * 370, 560 + row["upper"] * 370
            body.append(f'<path d="M {left:.3f} {y + 27} H {right:.3f} M {left:.3f} {y + 23} V {y + 31} M {right:.3f} {y + 23} V {y + 31}" stroke="currentColor" fill="none"/>')
            label += f"; range {row['lower']:.0%}–{row['upper']:.0%}"
        if row["known_count"] is not None:
            label += f"; known {row['known_count']}/{row['total_count']}"
        body.append(f'<text x="945" y="{y + 19}" font-size="11">{escape(label)}</text>')
    return _svg(title, len(rows), "".join(body))


def count_chart(bundle: dict, domain: str, series: list[tuple[str, str, str]], title: str) -> str:
    rows = [(run, [_metric(bundle, run["run_key"], domain, name)["value"] for name, _, _ in series])
            for run in bundle["runs"]]
    if any(value is None for _, values in rows for value in values):
        raise FixtureError("visual report: count charts require known counts")
    maximum = max([sum(values) for _, values in rows] + [1])
    body = []
    for index, (run, values) in enumerate(rows):
        y, left = index * 52 + 4, 560.0
        body.append(_label(run, y))
        for value, (_, name, color) in zip(values, series):
            width = value / maximum * 370
            body.append(f'<rect x="{left:.3f}" y="{y + 5}" width="{width:.3f}" height="18" fill="{color}"><title>{escape(name)}: {value:g}</title></rect>')
            left += width
        label = "; ".join(f"{name}: {value:g}" for value, (_, name, _) in zip(values, series))
        body.append(f'<text x="560" y="{y + 39}" font-size="10">{escape(label)}</text>')
    legend = " · ".join(f'<span style="color:{color}">{escape(name)}</span>' for _, name, color in series)
    return f"<div>{legend}</div>" + _svg(title, len(rows), "".join(body))


def result_views(bundle: dict) -> dict[str, str]:
    """No rankings, approvals, artifact reads, JavaScript or model calls."""
    validate_visual_report(bundle)
    return {
        "Quality": "".join([
            metric_chart(bundle, "quality", "defect_recall", "Defect recall — bounds include pending defects"),
            metric_chart(bundle, "quality", "finding_precision", "Resolved distinct finding precision — pending uncertainty shown"),
            metric_chart(bundle, "quality", "case_coverage", "Case adjudication coverage (includes empty reviews)"),
            count_chart(bundle, "quality", [
                ("matched_defects", "matched", "#16a34a"), ("confirmed_misses", "missed", "#ef4444"),
                ("pending_defects", "pending", "#f59e0b"),
            ], "Defect judgments — pending is not missed"),
            metric_chart(bundle, "quality", "corrected_false_alarm_rate", "Corrected-case false alarms — lower bound while pending"),
        ]),
        "Execution": count_chart(bundle, "execution", [
            ("completed", "completed", "#16a34a"), ("failed", "failed", "#ef4444"),
            ("timed_out", "timed out", "#f59e0b"), ("invalid_output", "invalid output", "#a855f7"),
        ], "Execution status — not a quality score") + metric_chart(
            bundle, "execution", "unavailable_defects", "Defects unavailable due to execution — not confirmed misses"),
        "Latency": metric_chart(bundle, "latency", "mean_ms", "Mean agent latency — recordings measure submission, not original inference"),
        "Cost": metric_chart(bundle, "cost", "known_total_usd", "Known cost subtotal — missing telemetry is unknown, not zero"),
    }
