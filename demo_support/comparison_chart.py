"""Offline line charts for retained pilot results, without judging review quality."""

from html import escape
import math
from pathlib import Path

from demo_support.results import load_report_text
from validate_fixtures import FixtureError, strict_json

COLORS = ("#60a5fa", "#f59e0b", "#34d399", "#c084fc", "#fb7185", "#22d3ee")
DASHES = ("", "10 4", "3 5", "12 4 3 4")
FINISHED = {"completed", "failed", "timed_out", "invalid_output"}


def load_chart_data(path: str | Path, root: Path) -> dict:
    """Read only the selected, project-confined report; never follow evidence."""
    bundle = strict_json(load_report_text(path, root).encode("utf-8"))
    if not isinstance(bundle, dict) or not isinstance(bundle.get("models"), list):
        raise FixtureError("comparison chart needs a saved model summary")
    for model in bundle["models"]:
        if (not isinstance(model, dict) or not isinstance(model.get("model_id"), str)
                or not isinstance(model.get("variation_by_case"), dict)):
            raise FixtureError("comparison chart needs per-model case results")
        for case in model["variation_by_case"].values():
            if not isinstance(case, dict) or not isinstance(case.get("status_by_repetition"), dict):
                raise FixtureError("comparison chart needs repetition statuses")
            if any(not isinstance(k, str) or not isinstance(v, str)
                   for k, v in case["status_by_repetition"].items()):
                raise FixtureError("comparison chart has invalid repetition statuses")
    return bundle


def model_line_chart(bundle: dict, metric: str = "delivery") -> str:
    """One color/line per model. Missing observations create gaps, never zeroes."""
    models = bundle["models"]
    cases = sorted({case for model in models for case in model["variation_by_case"]})
    if metric == "delivery":
        labels = cases
        title = "Review delivery by fixture"
        y_label, x_label, unit = "Completed reviews (%)", "Fixture", "%"
        series = []
        for model in models:
            values = []
            for case in labels:
                statuses = list(model["variation_by_case"].get(case, {}).get(
                    "status_by_repetition", {}).values())
                values.append(100 * statuses.count("completed") / len(statuses)
                              if statuses and all(s in FINISHED for s in statuses) else None)
            series.append((model["model_id"], values))
        maximum = 100
        note = ("Successful review submission, NOT defect-detection quality. "
                "Invalid, blocked, and timed-out attempts are not completed reviews. "
                "Not-yet-run fixtures are gaps, not zeroes. "
                "Lines can overlap when models have identical delivery rates.")
    elif metric == "latency":
        labels = cases
        title = "Agent latency by fixture"
        y_label, x_label, unit = "Median agent time (seconds)", "Fixture", " s"
        series = []
        for model in models:
            values = []
            for case in cases:
                timing = model["variation_by_case"].get(case, {}).get("latency_ms")
                value = timing.get("median") if isinstance(timing, dict) else None
                values.append(value / 1000 if type(value) in (int, float)
                              and math.isfinite(value) and value >= 0 else None)
            series.append((model["model_id"], values))
        maximum = max([value for _, values in series for value in values if value is not None] + [1]) * 1.15
        note = ("Includes failed or provider-blocked attempts: a fast failure is NOT a better review. "
                "Missing latency is not plotted. Review-quality grading remains separate.")
    else:
        raise ValueError("Unknown comparison chart metric")
    if not labels:
        return "<p>No retained observations are available for this chart.</p>"

    width, height = 1080, 390
    left, right, top, bottom = 80, 1035, 30, 315
    x = lambda index: (left + (right - left) / 2 if len(labels) == 1 else
                       left + index * (right - left) / (len(labels) - 1))
    y = lambda value: bottom - value / maximum * (bottom - top)
    body = []
    for tick in range(6):
        value = maximum * tick / 5
        position = y(value)
        body.append(
            f'<path d="M {left} {position:.2f} H {right}" stroke="currentColor" opacity="0.15"/>'
            f'<text x="{left - 12}" y="{position + 4:.2f}" text-anchor="end" font-size="12">{value:.3g}</text>'
        )
    for index, label in enumerate(labels):
        body.append(f'<text x="{x(index):.2f}" y="{bottom + 25}" text-anchor="middle" font-size="12">{escape(label)}</text>')
    body.extend([
        f'<text x="{(left + right) / 2}" y="{height - 16}" text-anchor="middle" font-size="13">{x_label}</text>',
        f'<text transform="translate(20 {(top + bottom) / 2}) rotate(-90)" text-anchor="middle" font-size="13">{y_label}</text>',
    ])
    legend = []
    for index, (name, values) in enumerate(series):
        color = COLORS[index % len(COLORS)]
        dash = DASHES[index % len(DASHES)]
        safe_name = escape(name, quote=True)
        legend.append(
            f'<span style="display:inline-flex;align-items:center;gap:6px">'
            f'<svg width="40" height="14" aria-hidden="true"><path d="M 0 7 H 40" '
            f'stroke="{color}" stroke-width="3" stroke-dasharray="{dash}"/></svg>{safe_name}</span>'
        )
        segments, segment = [], []
        for point, value in enumerate(values):
            if value is None:
                if segment:
                    segments.append(segment)
                segment = []
            else:
                segment.append((point, value))
        if segment:
            segments.append(segment)
        for segment in segments:
            points = " ".join(f"{x(point):.2f},{y(value):.2f}" for point, value in segment)
            body.append(
                f'<polyline data-model="{safe_name}" points="{points}" fill="none" '
                f'stroke="{color}" stroke-width="3" stroke-dasharray="{dash}">'
                f'<title>{safe_name}</title></polyline>'
            )
            for point, value in segment:
                px, py = x(point), y(value)
                tooltip = escape(f"{name} · {labels[point]}: {value:.3g}{unit}")
                if index % 3 == 0:
                    marker = f'<circle cx="{px:.2f}" cy="{py:.2f}" r="6"'
                elif index % 3 == 1:
                    marker = f'<rect x="{px - 4:.2f}" y="{py - 4:.2f}" width="8" height="8"'
                else:
                    marker = f'<polygon points="{px:.2f},{py - 7:.2f} {px - 6:.2f},{py + 4:.2f} {px + 6:.2f},{py + 4:.2f}"'
                body.append(f'{marker} fill="none" stroke="{color}" stroke-width="2"><title>{tooltip}</title>'
                            + ("</circle>" if index % 3 == 0 else "</rect>" if index % 3 == 1 else "</polygon>"))
    return (
        f'<figure style="margin:12px 0"><figcaption style="font-weight:600">{title}</figcaption>'
        f'<div style="display:flex;flex-wrap:wrap;gap:12px;margin:12px 0;font-size:12px">{"".join(legend)}</div>'
        f'<div style="overflow-x:auto"><svg xmlns="http://www.w3.org/2000/svg" role="img" '
        f'aria-label="{title}" viewBox="0 0 {width} {height}" '
        f'style="width:100%;min-width:640px;fill:currentColor">{"".join(body)}</svg></div>'
        f'<figcaption style="font-size:12px;opacity:0.8">{escape(note)}</figcaption></figure>'
    )
