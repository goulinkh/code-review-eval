"""Pure-Python visual explorer checks: reads and diffs, never snapshot execution."""

import hashlib
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path

from demo_support.explorer import file_inventory, line_counts, read_snapshot_text, render_diff
from validate_fixtures import FixtureError


class CodeCells(HTMLParser):
    """Read displayed source independent of syntax spans or diff markers."""

    def __init__(self, html):
        super().__init__()
        self.cells = []
        self.parts = None
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        if tag == "td" and dict(attrs).get("class") == "code":
            self.parts = []

    def handle_endtag(self, tag):
        if tag == "td" and self.parts is not None:
            self.cells.append("".join(self.parts))
            self.parts = None

    def handle_data(self, data):
        if self.parts is not None:
            self.parts.append(data)


class FixtureExplorerTests(unittest.TestCase):
    def test_inventory_distinguishes_added_deleted_modified_and_unchanged(self):
        public = {"snapshots": {
            "base": {"files": [
                {"path": "same.py", "sha256": "same"},
                {"path": "old.py", "sha256": "old"},
                {"path": "edit.py", "sha256": "before"},
            ]},
            "head": {"files": [
                {"path": "same.py", "sha256": "same"},
                {"path": "new.py", "sha256": "new"},
                {"path": "edit.py", "sha256": "after"},
            ]},
        }}
        self.assertEqual(file_inventory(public), [
            {"path": "edit.py", "status": "modified"},
            {"path": "new.py", "status": "added"},
            {"path": "old.py", "status": "deleted"},
            {"path": "same.py", "status": "unchanged"},
        ])
        self.assertEqual(file_inventory({"snapshots": {"base": {"files": []}, "head": {"files": []}}}), [])

    def test_line_counts_include_insertions_deletions_and_both_sides_of_replacements(self):
        self.assertEqual(line_counts("keep\nold\n", "keep\nnew\nextra\n"), (2, 1))
        self.assertEqual(line_counts(None, "new\n"), (1, 0))
        self.assertEqual(line_counts("old\n", None), (0, 1))
        self.assertEqual(line_counts("same\n", "same\n"), (0, 0))
        self.assertEqual(line_counts(None, ""), (0, 0))

    def test_split_diff_has_line_numbers_highlights_and_escapes_source_and_path(self):
        html = render_diff("safe\n<script>old</script>\n", "safe\n<script>new</script>\n", "<img src=x>")
        self.assertRegex(html, r'class="diff_header" id="from\d+_2">2</td>')
        self.assertIn('class="diff_chg"', html)
        self.assertNotIn("<script>", html)
        self.assertNotIn("<img src=x>", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("&lt;img src=x&gt;", html)

    def test_unified_diff_has_correct_line_numbers_and_colored_rows(self):
        html = render_diff("same\nold\n", "same\nnew\n", "src/file.py", layout="unified")
        self.assertIn('class="removed"><td class="line-number">2</td><td class="line-number"></td>', html)
        self.assertIn('class="added"><td class="line-number"></td><td class="line-number">2</td>', html)
        self.assertIn("-old", CodeCells(html).cells)
        self.assertIn("+new", CodeCells(html).cells)
        self.assertIn("@@ -1,2 +1,2 @@", html)

    def test_unified_diff_handles_additions_deletions_and_header_like_source(self):
        for before, after, expected in (
            (None, "++ text\n<script>\n", "+<script>"),
            ("-- text\n", None, "--- text"),
        ):
            with self.subTest(before=before, after=after):
                html = render_diff(before, after, "file.py", layout="unified")
                self.assertIn(expected, CodeCells(html).cells)
                self.assertNotIn("<script>", html)

    def test_full_context_toggle_reveals_omitted_unchanged_lines_in_both_layouts(self):
        before = "".join(f"context-{i}\n" for i in range(30)) + "old\n"
        after = "".join(f"context-{i}\n" for i in range(30)) + "new\n"
        for layout in ("split", "unified"):
            with self.subTest(layout=layout):
                compact = CodeCells(render_diff(before, after, "file.py", layout=layout)).cells
                full = CodeCells(render_diff(before, after, "file.py", layout=layout, full_context=True)).cells
                self.assertFalse(any("context-0" in cell for cell in compact))
                self.assertTrue(any("context-0" in cell for cell in full))

    def test_absent_empty_and_unchanged_files_are_renderable(self):
        self.assertIn("(absent)", render_diff(None, "", "file.py"))
        self.assertIn("(empty)", render_diff(None, "", "file.py"))
        for before, after in ((None, ""), ("", None), ("", ""), ("same\n", "same\n")):
            for layout in ("split", "unified"):
                with self.subTest(before=before, after=after, layout=layout):
                    self.assertIn("fixture-diff", render_diff(before, after, "file.py", layout=layout))
        with self.assertRaises(ValueError):
            render_diff("", "", "file.py", layout="unknown")

    def test_both_layouts_highlight_syntax_without_losing_source_or_diff_markers(self):
        before = 'def render():\n\treturn "<script>old</script>"  # comment\n'
        after = before.replace("old", "new")
        for layout in ("split", "unified"):
            with self.subTest(layout=layout):
                html = render_diff(before, after, "src/render.py", layout=layout, full_context=True)
                self.assertIn('<span class="k">def</span>', html)
                self.assertIn('<span class="nf">render</span>', html)
                self.assertIn('<span class="c1"># comment</span>', html)
                self.assertNotIn("<script>", html)
                cells = CodeCells(html).cells
                for source in (before, after):
                    displayed = source.expandtabs(4) if layout == "split" else source
                    for line in displayed.splitlines():
                        self.assertTrue(any(line in cell for cell in cells), line)
                if layout == "split":
                    self.assertIn('<span class="diff_chg"><span class="s2">old</span></span>', html)
                    self.assertIn('<span class="diff_chg"><span class="s2">new</span></span>', html)
                else:
                    self.assertIn('class="added"', html)
                    self.assertIn('class="removed"', html)

    def test_long_lines_wrap_in_both_layouts_without_changing_source_lines(self):
        before = '    value = "' + "long_identifier_" * 40 + 'old"\n'
        after = before.replace('old"', 'new"')
        for layout in ("split", "unified"):
            with self.subTest(layout=layout):
                html = render_diff(before, after, "src/file.py", layout=layout)
                self.assertIn("table-layout: fixed", html)
                self.assertIn("white-space: pre-wrap", html)
                self.assertIn("overflow-wrap: anywhere", html)
                cells = CodeCells(html).cells
                for source in (before, after):
                    self.assertTrue(any(source.rstrip("\n") in cell for cell in cells))
                self.assertEqual(line_counts(before, after), (1, 1))

    def test_multiline_syntax_is_preserved_when_opening_delimiter_is_outside_hunk(self):
        before = 'text = """\n' + "unchanged\n" * 10 + 'old text\n"""\n'
        after = before.replace("old text", "new text")
        for layout in ("split", "unified"):
            with self.subTest(layout=layout):
                html = render_diff(before, after, "src/render.py", layout=layout)
                self.assertIn('<span class="s2">unchanged</span>', html)
                self.assertNotIn('<span class="n">unchanged</span>', html)

    def test_unknown_file_type_renders_escaped_plain_text(self):
        for layout in ("split", "unified"):
            with self.subTest(layout=layout):
                html = render_diff(None, "<script>\n", "file.unknown-extension", layout=layout)
                self.assertIn("&lt;script&gt;", html)
                self.assertNotIn("<script>", html)
                self.assertTrue(any("<script>" in cell for cell in CodeCells(html).cells))

    def test_snapshot_read_checks_integrity_and_never_executes_the_source(self):
        source = b"raise AssertionError('must not execute')\n"
        digest = hashlib.sha256(source).hexdigest()
        public = {"snapshots": {"head": {"files": [{"path": "file.py", "sha256": digest}]}}}
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            blob = directory / "environment/blobs" / digest
            blob.parent.mkdir(parents=True)
            blob.write_bytes(source)
            self.assertEqual(read_snapshot_text(directory, public, "head", "file.py"), source.decode())
            self.assertIsNone(read_snapshot_text(directory, public, "head", "missing.py"))
            blob.write_bytes(b"tampered\n")
            with self.assertRaisesRegex(FixtureError, "blob hash mismatch"):
                read_snapshot_text(directory, public, "head", "file.py")
            blob.unlink()
            target = directory / "source.py"
            target.write_bytes(source)
            blob.symlink_to(target)
            with self.assertRaisesRegex(FixtureError, "symlink artifact"):
                read_snapshot_text(directory, public, "head", "file.py")

    def test_snapshot_read_rejects_non_digest_blob_names(self):
        public = {"snapshots": {"head": {"files": [{"path": "file.py", "sha256": "../../private/expectations.json"}]}}}
        with self.assertRaisesRegex(FixtureError, "invalid blob digest"):
            read_snapshot_text(Path("."), public, "head", "file.py")


if __name__ == "__main__":
    unittest.main()
