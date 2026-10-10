# /// script
# requires-python = ">=3.11"
# dependencies = ["marimo", "anywidget", "multilevel-table"]
#
# [tool.uv.sources]
# # ▼▼▼ EDIT THIS: point at YOUR GitHub repo (and optionally pin a branch/rev) ▼▼▼
# multilevel-table = { git = "https://github.com/YOUR_USERNAME/multilevel-table.git", branch = "main" }
# ///

import marimo

__generated_with = "0.18.4"
app = marimo.App()

with app.setup:
    import marimo as mo
    from multilevel_table import H, MultilevelTable


@app.cell
def _():
    col_headers = H("Region", [
        H("EMEA", [
            H("UK", [H("Revenue", key="uk_rev"), H("Units", key="uk_units")], key="uk"),
            H("Germany", [H("Revenue", key="de_rev"), H("Units", key="de_units")], key="germany"),
        ], key="emea"),
        H("APAC", [
            H("Japan", [H("Revenue", key="jp_rev"), H("Units", key="jp_units")], key="japan"),
            H("Australia", [H("Revenue", key="au_rev"), H("Units", key="au_units")], key="australia"),
        ], key="apac"),
    ], key="region")

    row_headers = H("Division", [
        H("Hardware", [
            H("Laptops", [
                H("Pro 13in", key="pro_13"),
                H("Pro 15in", key="pro_15"),
                H("Air", key="air"),
            ], key="laptops"),
            H("Tablets", [H("Standard", key="tab_std"), H("Plus", key="tab_plus")], key="tablets"),
        ], key="hardware"),
        H("Software", [
            H("Productivity", [H("Basic", key="prod_basic"), H("Pro", key="prod_pro")], key="productivity"),
            H("Security", [H("Shield", key="shield")], key="security"),
        ], key="software"),
    ], key="division")
    return col_headers, row_headers


@app.cell
def _():
    def calculate(row_path, col_path):
        seed = sum(len(k) for k in row_path) * 7 + sum(len(k) for k in col_path) * 3
        metric = col_path[-1]
        if "units" in metric:
            return seed % 90 + 10
        return f"${(seed * 137) % 9000 + 1000:,}"
    return (calculate,)


@app.cell
def _(calculate, col_headers, row_headers):
    table = MultilevelTable(row_headers=row_headers, col_headers=col_headers, calculate=calculate)
    widget = mo.ui.anywidget(table)
    widget
    return (widget,)


@app.cell
def _(widget):
    mo.md(f"""
    **Current structure**

    - Row leaves: `{widget.value['row_leaves']}`
    - Column leaves: `{widget.value['col_leaves']}`
    - Grid: {len(widget.value['row_leaves'])} × {len(widget.value['col_leaves'])}
    """)
    return


if __name__ == "__main__":
    app.run()
