# /// script
# requires-python = ">=3.11"
# dependencies = ["marimo", "anywidget", "multilevel-table"]
#
# [tool.uv.sources]
# # EDIT: point at your GitHub repo; pin a commit with rev = "<sha>" to avoid stale caches.
# multilevel-table = { git = "https://github.com/YOUR_USERNAME/multilevel-table.git", branch = "main" }
# ///

import marimo

__generated_with = "0.18.4"
app = marimo.App(width="full")

with app.setup:
    import marimo as mo
    from multilevel_table import MultilevelTable
    from multilevel_table.examples import example_calculate, example_headers


@app.cell
def _():
    mo.md("""
    # MultilevelTable

    Click a column header marked **–** to merge its children into it, or **+** to split it
    again. Merged columns are recalculated. Click a tile to select it.
    """)
    return


@app.cell
def _():
    # Replace example_headers / example_calculate with your own:
    #   row_headers, col_headers = H(...), H(...)
    #   def calculate(row_path, col_path) -> "<svg ...>...</svg>" | number | text
    row_headers, col_headers = example_headers()
    table = MultilevelTable(
        row_headers,
        col_headers,
        example_calculate,
        cell_width=96,
        cell_height=48,
    )
    widget = mo.ui.anywidget(table)
    widget
    return (widget,)


@app.cell
def _(widget):
    # Re-runs whenever the table changes. widget.value holds every synced trait.
    _sel = widget.value["selected"]
    mo.md(f"""
    **Merged columns:** {", ".join(widget.value["col_merged"]) or "none"}

    **Grid:** {len(widget.value["row_paths"])} rows × {len(widget.value["col_paths"])} columns

    **Selected cell:** {" › ".join(_sel["row"]) + "  ×  " + " › ".join(_sel["col"]) if _sel else "none"}
    """)
    return


if __name__ == "__main__":
    app.run()
