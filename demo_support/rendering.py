"""Marimo display helpers, imported only by the optional demo."""

from demo_support.syntax import SYNTAX_STYLE, render_tokens, syntax_lines


def source_block(content: str, *, path: str = "", language: str | None = None):
    """Display syntax-colored, escaped data; never interpret or execute source."""
    import marimo as mo

    code = "\n".join(render_tokens(line) for line in syntax_lines(content, path=path, language=language))
    return mo.Html(SYNTAX_STYLE + f'<pre class="fixture-source fixture-code"><code>{code}</code></pre>')
