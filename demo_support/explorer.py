"""Read-only, evaluator-side snapshot browsing and HTML diffs. Never executes code."""

from __future__ import annotations

import difflib
import re
from html import escape
from pathlib import Path

from validate_fixtures import read_artifact, require, sha256


def file_inventory(public: dict) -> list[dict[str, str]]:
    """Compare complete snapshot inventories, without treating them as access grants."""
    base, head = (
        {item["path"]: item["sha256"] for item in public["snapshots"][side]["files"]}
        for side in ("base", "head")
    )
    rows = []
    for path in sorted(base.keys() | head.keys()):
        status = (
            "added" if path not in base else
            "deleted" if path not in head else
            "modified" if base[path] != head[path] else "unchanged"
        )
        rows.append({"path": path, "status": status})
    return sorted(rows, key=lambda row: (row["status"] == "unchanged", row["path"]))


def read_snapshot_text(directory: Path, public: dict, side: str, path: str) -> str | None:
    """Read a named immutable blob, checking its hash; None means an absent file."""
    item = next((item for item in public["snapshots"][side]["files"] if item["path"] == path), None)
    if item is None:
        return None
    require(re.fullmatch(r"[0-9a-f]{64}", item["sha256"]) is not None, "invalid blob digest")
    raw = read_artifact(directory.resolve(), f"environment/blobs/{item['sha256']}")
    require(sha256(raw) == item["sha256"], f"blob hash mismatch: {side}/{path}")
    text = raw.decode("utf-8")
    require(not text or text.endswith("\n"), f"text blob must end with newline: {path}")
    require("\x00" not in text, f"binary blob not supported: {path}")
    return text


def line_counts(before: str | None, after: str | None) -> tuple[int, int]:
    """Count added and removed lines, counting replacements on both sides."""
    matcher = difflib.SequenceMatcher(None, (before or "").splitlines(), (after or "").splitlines(), autojunk=False)
    added = removed = 0
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag in ("insert", "replace"):
            added += j2 - j1
        if tag in ("delete", "replace"):
            removed += i2 - i1
    return added, removed


_STYLE = """
<style>
.fixture-diff { border: 1px solid #8885; border-radius: 8px; overflow: auto; max-height: 650px; }
.fixture-diff table { width: 100%; border-collapse: collapse; font: 13px/1.65 ui-monospace, monospace; }
.fixture-diff th { text-align: left; padding: 8px 12px; background: #8882; }
.fixture-diff td { padding: 0 6px; vertical-align: top; }
.fixture-diff .diff_header, .fixture-diff .line-number { color: #888; background: #8881; text-align: right; user-select: none; }
.fixture-diff .diff_next { background: #8882; font-size: 11px; }
.fixture-diff .diff_add, .fixture-diff .added { background: #22c55e30; }
.fixture-diff .diff_sub, .fixture-diff .removed { background: #ef444430; }
.fixture-diff .diff_chg { background: #eab30840; }
.fixture-diff .hunk { color: #60a5fa; background: #3b82f615; }
.fixture-diff .code { white-space: pre; width: 100%; }
.fixture-diff .empty-diff { padding: 16px; }
</style>
"""


def _unified_table(before: str | None, after: str | None, path: str, full_context: bool) -> str:
    base_lines, head_lines = (before or "").splitlines(keepends=True), (after or "").splitlines(keepends=True)
    patch = difflib.unified_diff(
        base_lines, head_lines,
        fromfile=f"a/{path}" if before is not None else "/dev/null",
        tofile=f"b/{path}" if after is not None else "/dev/null",
        n=max(len(base_lines), len(head_lines)) if full_context else 3,
    )
    rows = []
    old_line = new_line = 0
    for line in patch:
        if line.startswith(("--- ", "+++ ")) and not rows:
            continue
        if line.startswith("@@"):
            match = re.match(r"@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@", line)
            assert match is not None
            old_line, new_line = map(int, match.groups())
            rows.append(f'<tr class="hunk"><td colspan="3">{escape(line.rstrip(chr(10)))}</td></tr>')
            continue
        tag = line[:1]
        old_number = "" if tag == "+" else str(old_line)
        new_number = "" if tag == "-" else str(new_line)
        kind = "added" if tag == "+" else "removed" if tag == "-" else "context"
        rows.append(
            f'<tr class="{kind}"><td class="line-number">{old_number}</td>'
            f'<td class="line-number">{new_number}</td><td class="code">{escape(line.rstrip(chr(10)))}</td></tr>'
        )
        old_line += tag != "+"
        new_line += tag != "-"
    if not rows:
        return '<div class="empty-diff">No line changes. The file may be empty or unchanged.</div>'
    return '<table aria-label="Unified snapshot diff"><thead><tr><th>Base</th><th>Head</th><th>Change</th></tr></thead><tbody>' + "".join(rows) + "</tbody></table>"


def render_diff(before: str | None, after: str | None, path: str, *, layout: str = "split", full_context: bool = False) -> str:
    """Return escaped, line-numbered HTML; missing and empty files remain distinct."""
    if layout == "split":
        def heading(side, content):
            return escape(f"{side} · {path}" + (" (absent)" if content is None else " (empty)" if content == "" else ""))

        body = difflib.HtmlDiff(tabsize=4).make_table(
            (before or "").splitlines(), (after or "").splitlines(),
            fromdesc=heading("base", before), todesc=heading("head", after),
            context=not full_context, numlines=3,
        )
    elif layout == "unified":
        body = _unified_table(before, after, path, full_context)
    else:
        raise ValueError(f"Unknown diff layout: {layout}")
    return _STYLE + f'<div class="fixture-diff">{body}</div>'
