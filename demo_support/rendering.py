"""Marimo display helpers, imported only by the optional demo."""

from html import escape


def source_block(content: str):
    """Display reviewed text as escaped data, never raw HTML or executable code."""
    import marimo as mo

    return mo.Html(f"<pre style='overflow-x: auto'><code>{escape(content)}</code></pre>")
