"""Syntax rendering stays escaped, offline, and independent of marimo."""

import re
import unittest
from html import unescape

from demo_support.syntax import SYNTAX_STYLE, render_tokens, syntax_lines


def displayed_text(markup):
    return unescape(re.sub(r"<[^>]*>", "", markup))


class SyntaxTests(unittest.TestCase):
    def test_lexing_and_rendering_preserve_source_whitespace_and_unicode(self):
        for source in ("", "\n\n", "# café\n", '\n\ndef f():\n\treturn "<>&"  \n\n'):
            for path in ("src/file.py", "file.unknown-extension"):
                with self.subTest(source=source, path=path):
                    html = "\n".join(render_tokens(line) for line in syntax_lines(source, path=path))
                    self.assertEqual(displayed_text(html), source)

    def test_character_ranges_can_split_tokens_without_losing_syntax_or_escaping(self):
        tokens = [("k", "return"), ("", " "), ("s2", '"<value>"')]
        source = 'return "<value>"'
        for start in range(len(source) + 1):
            for end in range(start, len(source) + 1):
                with self.subTest(start=start, end=end):
                    html = render_tokens(tokens, start, end)
                    self.assertEqual(displayed_text(html), source[start:end])
                    self.assertNotIn("<value>", html)

    def test_explicit_language_and_unknown_language_fallback(self):
        json = syntax_lines('{"count": 42}', language="json")
        self.assertIn('<span class="nt">&quot;count&quot;</span>', render_tokens(json[0]))
        plain = syntax_lines("<script>", language="unknown-language")
        self.assertEqual(render_tokens(plain[0]), "&lt;script&gt;")

    def test_light_and_dark_styles_are_scoped_and_mutually_exclusive(self):
        self.assertIn("body:not(.dark) .fixture-code", SYNTAX_STYLE)
        self.assertIn(".dark .fixture-code", SYNTAX_STYLE)
        selectors = re.findall(r"(?:^|\n)([^{}\n]+)\{", SYNTAX_STYLE)
        self.assertTrue(selectors)
        self.assertTrue(all(".fixture-code" in selector or ".fixture-source" in selector for selector in selectors))


if __name__ == "__main__":
    unittest.main()
