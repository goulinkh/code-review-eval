"""Virtual snapshot navigation using native marimo controls, never filesystem browsing."""

from html import escape


# Marimo copies stylesheets titled "marimo..." into native controls' shadow DOM.
_STYLE = """
<style title="marimo-fixture-file-tree-v1">
.fixture-file-tree { font: 13px/1.5 ui-monospace, monospace; color: var(--gray-12); overflow: auto; }
.fixture-file-tree details > summary { color: var(--gray-11); cursor: pointer; padding: 5px 0; white-space: nowrap; }
.fixture-file-tree .file-children { margin-left: 7px; padding-left: 12px; border-left: 1px solid var(--gray-6); }
.fixture-file-tree .file-leaf { margin: 2px 0; }
.fixture-file-tree .file-leaf button { color: var(--gray-12); border: 0; background: transparent; box-shadow: none; padding: 5px 8px; justify-content: start; }
.fixture-file-tree .file-leaf button:hover { background: var(--gray-3); }
.fixture-file-tree .file-leaf button:focus-visible { outline: 2px solid var(--gray-9); outline-offset: -2px; }
.fixture-file-tree .file-label { display: flex; align-items: center; gap: 6px; width: 100%; min-width: 0; }
.fixture-file-tree .file-label code { font: inherit; color: inherit; background: transparent; padding: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.fixture-file-tree .file-status { margin-left: auto; padding: 0 4px; border: 1px solid var(--gray-6); border-radius: 4px; background: var(--gray-3); color: var(--gray-11); font-size: 11px; font-weight: 500; }
.dark .fixture-file-tree .file-leaf button { color: var(--gray-12) !important; background: transparent !important; }
.dark .fixture-file-tree .file-leaf button :is(.markdown, .paragraph, .file-label, code) { color: inherit !important; background: transparent !important; }
.dark .fixture-file-tree .file-leaf button:hover { background: var(--gray-3) !important; }
/* Target the native control itself, including labels rendered by marimo. */
.dark button[data-testid="marimo-plugin-button"]:has(.file-label) { background: #161b22 !important; color: #e6edf3 !important; border-color: #30363d !important; }
.dark button[data-testid="marimo-plugin-button"]:has(.file-label):hover { background: #21262d !important; }
.dark button[data-testid="marimo-plugin-button"]:has(.file-label) :is(.markdown, .paragraph, .file-label, code) { background: transparent !important; color: #e6edf3 !important; }
.dark button[data-testid="marimo-plugin-button"]:has(.file-label) .file-status { background: #30363d !important; color: #b1bac4 !important; border-color: #484f58 !important; }
</style>
"""

_STATUS = {"added": "A", "deleted": "D", "modified": "M", "unchanged": "·"}


def file_tree(inventory: list[dict[str, str]], on_select):
    """Build a collapsible tree from public snapshot paths; clicks select exact paths."""
    import marimo as mo

    buttons = {}
    for index, item in enumerate(inventory):
        path, status = item["path"], item["status"]
        name = path.rsplit("/", 1)[-1]
        buttons[f"file_{index}"] = mo.ui.button(
            value=path, on_change=on_select, full_width=True,
            tooltip=f"{path} · {status}",
            label=(
                f'<span class="file-label" data-file-index="{index}"><code>{escape(name)}</code>'
                f'<span class="file-status status-{status}" aria-label="{status}">{_STATUS[status]}</span></span>'
            ),
        )

    def branch(entries):
        directories = {}
        leaves = []
        for index, parts in entries:
            if len(parts) == 1:
                leaves.append((parts[0], index))
            else:
                directories.setdefault(parts[0], []).append((index, parts[1:]))
        fragments = []
        for directory, children in sorted(directories.items()):
            # Braces must not be mistaken for batch's widget placeholders.
            label = escape(directory).replace("{", "&#123;").replace("}", "&#125;")
            fragments.append(
                f'<details open><summary>{label}</summary><div class="file-children">'
                + branch(children) + "</div></details>"
            )
        for _, index in sorted(leaves):
            fragments.append(f'<div class="file-leaf" data-file-index="{index}">{{file_{index}}}</div>')
        return "".join(fragments)

    content = branch([(index, item["path"].split("/")) for index, item in enumerate(inventory)])
    if not content:
        content = "<p>No snapshot files.</p>"
    template = _STYLE.replace("{", "{{").replace("}", "}}") + (
        '<nav class="fixture-file-tree" aria-label="Snapshot files">' + content + "</nav>"
    )
    # batch retains the native buttons and forwards their callbacks. The control
    # is built only when the fixture changes, independently of the selected path.
    return mo.Html(template).batch(**buttons)


def file_tree_selection_style(inventory: list[dict[str, str]], selected_file: str | None):
    """Highlight the active row using the notebook theme, not fixed colors."""
    import marimo as mo

    index = next((index for index, item in enumerate(inventory) if item["path"] == selected_file), None)
    if index is None:
        return mo.Html("")
    return mo.Html(
        f'<style title="marimo-fixture-file-selection-{index}">'
        f'.fixture-file-tree .file-leaf[data-file-index="{index}"] button '
        '{ background: var(--gray-4); color: var(--gray-12); '
        'box-shadow: inset 2px 0 var(--gray-9); font-weight: 600; }'
        f'.dark .fixture-file-tree .file-leaf[data-file-index="{index}"] button '
        '{ background: var(--gray-4) !important; color: var(--gray-12) !important; }'
        f'.dark button[data-testid="marimo-plugin-button"]:has(.file-label[data-file-index="{index}"]) '
        '{ background: #30363d !important; color: #e6edf3 !important; }</style>'
    )


def file_tree_layout(tree, viewer):
    """Nest file navigation and the viewer in one bordered, side-by-side panel."""
    import marimo as mo

    navigation = mo.vstack([mo.md("**Files**"), tree]).style({
        "width": "clamp(170px, 20vw, 260px)",
        "max-height": "720px",
        "overflow": "auto",
        "padding": "12px",
        "background": "var(--gray-2)",
        "border-right": "1px solid var(--gray-6)",
    })
    content = mo.vstack([viewer.style({"padding": "12px", "min-width": "0"})])
    panel = mo.hstack(
        [navigation, content], widths=[0, 1], align="stretch", justify="start", gap=0,
    ).style({
        "border": "1px solid var(--gray-6)",
        "border-radius": "8px",
        "overflow": "hidden",
    })
    # Install the titled stylesheet before the batch mounts, so marimo adopts it
    # inside the shadow DOM where native buttons are actually rendered.
    return mo.vstack([mo.Html(_STYLE), panel], gap=0)
