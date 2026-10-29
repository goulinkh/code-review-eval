"""Nested file navigation; no disk browsing or snapshot execution."""

import importlib.util
import json
import unittest
from html.parser import HTMLParser
from unittest.mock import patch


class TreeMarkup(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.folders = []
        self.rows = []
        self.labels = []
        self.open_folders = 0
        self.in_summary = False
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "details" and "open" in attrs:
            self.open_folders += 1
        if tag == "summary":
            self.in_summary = True
        if tag == "div" and attrs.get("class") == "file-leaf":
            self.rows.append(int(attrs["data-file-index"]))
        if tag == "marimo-button":
            self.labels.append(json.loads(attrs["data-label"]))

    def handle_endtag(self, tag):
        if tag == "summary":
            self.in_summary = False

    def handle_data(self, data):
        if self.in_summary:
            self.folders.append(data)


@unittest.skipUnless(importlib.util.find_spec("marimo"), "install the demo dependency group")
class FileTreeTests(unittest.TestCase):
    def test_folders_nest_and_sort_before_files_with_all_change_statuses(self):
        from demo_support.file_tree import file_tree

        inventory = [
            {"path": "src/z.py", "status": "modified"},
            {"path": "README.md", "status": "unchanged"},
            {"path": "src/nested/new.py", "status": "added"},
            {"path": "src/old.py", "status": "deleted"},
        ]
        with patch("marimo.ui.file_browser", side_effect=AssertionError("filesystem browser used")):
            tree = file_tree(inventory, lambda _: None)
        markup = TreeMarkup(tree.text)
        self.assertEqual(markup.folders, ["src", "nested"])
        self.assertEqual(markup.open_folders, 2)
        self.assertEqual(markup.rows, [2, 3, 0, 1])
        self.assertEqual(len(tree.elements), len(inventory))
        for status in ("added", "deleted", "modified", "unchanged"):
            self.assertTrue(any(f"status-{status}" in label for label in markup.labels))

    def test_buttons_select_exact_paths_including_repeated_basenames(self):
        from demo_support.file_tree import file_tree

        inventory = [{"path": path, "status": "modified"} for path in ("a/main.py", "b/main.py")]
        selected = []
        tree = file_tree(inventory, selected.append)
        # Exercise marimo's real batch/button event conversion, not just a callback.
        tree._update({"file_1": 1})
        tree._update({"file_0": 1})
        tree._update({"file_1": 2})
        self.assertEqual(selected, ["b/main.py", "a/main.py", "b/main.py"])

    def test_untrusted_names_are_escaped_and_cannot_expand_batch_placeholders(self):
        from demo_support.file_tree import file_tree

        path = '<img src=x>/{file_0}/<script>"{name}".py'
        selected = []
        tree = file_tree([{"path": path, "status": "added"}], selected.append)
        markup = TreeMarkup(tree.text)
        self.assertEqual(markup.folders, ["<img src=x>", "{file_0}"])
        self.assertIn('&lt;script&gt;&quot;{name}&quot;.py', markup.labels[0])
        self.assertNotIn("<script>", tree.text)
        self.assertNotIn("<img src=x>", tree.text)
        tree._update({"file_0": 1})
        self.assertEqual(selected, [path])

    def test_file_and_folder_with_same_name_in_snapshot_union_are_both_kept(self):
        from demo_support.file_tree import file_tree

        tree = file_tree([
            {"path": "src", "status": "deleted"},
            {"path": "src/new.py", "status": "added"},
        ], lambda _: None)
        markup = TreeMarkup(tree.text)
        self.assertEqual(markup.folders, ["src"])
        self.assertEqual(markup.rows, [1, 0])

    def test_layout_nests_the_existing_tree_next_to_the_viewer(self):
        import marimo as mo
        from demo_support.file_tree import file_tree, file_tree_layout

        tree = file_tree([{"path": "src/main.py", "status": "modified"}], lambda _: None)
        layout = file_tree_layout(tree, mo.Html('<div class="test-viewer">Diff</div>')).text
        self.assertIn(tree.text, layout)
        self.assertLess(layout.index('<nav class="fixture-file-tree"'), layout.index('class="test-viewer"'))
        self.assertNotIn("marimo-sidebar", layout)
        self.assertRegex(layout, r"flex-direction:\s*row")

    def test_tree_uses_neutral_theme_colors(self):
        from demo_support.file_tree import file_tree, file_tree_selection_style

        inventory = [{"path": "src/main.py", "status": "modified"}]
        tree = file_tree(inventory, lambda _: None)
        style = tree.text + file_tree_selection_style(inventory, "src/main.py").text
        self.assertIn("color: var(--gray-12)", style)
        self.assertIn("background: var(--gray-4)", style)
        self.assertIn("color: var(--gray-11)", style)
        self.assertIn('button[data-testid="marimo-plugin-button"]:has(.file-label)', style)
        self.assertIn("color: #e6edf3 !important", style)

    def test_empty_tree_and_active_row_style(self):
        from demo_support.file_tree import file_tree, file_tree_selection_style

        empty = file_tree([], lambda _: self.fail("empty tree selected a file"))
        self.assertIn("No snapshot files.", empty.text)
        self.assertEqual(len(empty.elements), 0)
        inventory = [{"path": "<unsafe>.py", "status": "modified"}]
        style = file_tree_selection_style(inventory, "<unsafe>.py").text
        self.assertIn('[data-file-index="0"]', style)
        self.assertNotIn("<unsafe>", style)
        self.assertEqual(file_tree_selection_style(inventory, None).text, "")


if __name__ == "__main__":
    unittest.main()
