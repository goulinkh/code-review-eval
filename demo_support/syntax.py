"""Offline syntax highlighting shared by the evaluator's source and diff views."""

from html import escape

from pygments import lex
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name, get_lexer_for_filename
from pygments.lexers.special import TextLexer
from pygments.token import STANDARD_TYPES
from pygments.util import ClassNotFound


def _theme_css(style: str, selector: str) -> str:
    formatter = HtmlFormatter(style=style)
    # Omit Pygments' global pre/line-number rules: every rule must stay scoped.
    return "\n".join(
        formatter.get_background_style_defs(selector)
        + formatter.get_token_style_defs(selector)
    )


SYNTAX_STYLE = "<style>\n" + _theme_css("friendly", "body:not(.dark) .fixture-code") + "\n" + _theme_css(
    "github-dark", ".dark .fixture-code",
) + """
.fixture-source { border: 1px solid #8885; border-radius: 8px; padding: 12px; overflow: auto; }
.fixture-code code { font: inherit; color: inherit; background: transparent; }
.fixture-code pre, pre.fixture-code { font: 13px/1.65 ui-monospace, monospace; tab-size: 4; }
</style>
"""


def syntax_lines(content: str, *, path: str = "", language: str | None = None) -> list[list[tuple[str, str]]]:
    """Lex the whole document so multiline strings/comments retain their context."""
    options = {"stripnl": False, "ensurenl": False}
    try:
        lexer = get_lexer_by_name(language, **options) if language else get_lexer_for_filename(path, **options)
    except ClassNotFound:
        lexer = TextLexer(**options)
    lines: list[list[tuple[str, str]]] = [[]]
    for token, value in lex(content, lexer):
        while token not in STANDARD_TYPES:
            token = token.parent
        css_class = STANDARD_TYPES[token]
        for index, fragment in enumerate(value.split("\n")):
            if index:
                lines.append([])
            if fragment:
                lines[-1].append((css_class, fragment))
    return lines


def render_tokens(tokens: list[tuple[str, str]], start: int = 0, end: int | None = None) -> str:
    """Escape a character range, keeping syntax spans inside any diff markers."""
    parts = []
    offset = 0
    for css_class, value in tokens:
        stop = offset + len(value)
        fragment = value[max(0, start - offset):None if end is None else max(0, end - offset)]
        if fragment:
            escaped = escape(fragment)
            parts.append(f'<span class="{css_class}">{escaped}</span>' if css_class else escaped)
        offset = stop
        if end is not None and offset >= end:
            break
    return "".join(parts)
