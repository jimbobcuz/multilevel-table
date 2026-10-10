# MultilevelTable

An interactive table widget for [Marimo](https://marimo.io) (built on
[anywidget](https://anywidget.dev)) with **multilevel row and column headers**.
The defining feature is structural editing: you click a header to **merge** its
children up into it, or **split** it back out, and the table's contents are
recalculated for whatever structure results.

![demo](demo-screenshot.png)

---

## Contents

- [What it does](#what-it-does)
- [Quick look (no install)](#quick-look-no-install)
- [Install](#install)
- [Run the Marimo demo](#run-the-marimo-demo)
- [Use it in your own notebook](#use-it-in-your-own-notebook)
- [The merge / split model](#the-merge--split-model)
- [API reference](#api-reference)
- [Architecture](#architecture)
- [Running the tests](#running-the-tests)
- [Project layout](#project-layout)
- [Deeper documentation](#deeper-documentation)
- [What's not built yet](#whats-not-built-yet)

---

## What it does

A normal table has one row of column headers and one column of row headers.
This widget has **trees** of headers on both axes. Leaf nodes line up with the
actual data cells; interior nodes are groups that span their descendants.

You interact with the structure directly:

- **Merge** — click a group whose children are all leaves. It absorbs them and
  becomes a single leaf. The grid loses rows/columns and recalculates.
- **Split** — click a previously merged cell. Its children reappear. The grid
  grows back and recalculates.
- **Rename** — hover any header and click the ✎ to edit its label inline.

Every cell value is produced by a function you supply, called with the
root-to-leaf path of each cell. Because the path reflects the *current*
structure, merged cells get recalculated automatically.

---

## Quick look (no install)

Open **`multilevel_table_demo.html`** in any browser — phone or desktop. It's a
single self-contained file with no dependencies and no kernel. Click headers
marked `–` to merge and `+` to split; hover and use ✎ to rename.

This demo runs the real renderer (`widget.js` / `widget.css`) against a small
in-browser stand-in for the Python backend, so what you see and click is the
genuine front end.

---

## Install

You need Python 3.11+ and [`anywidget`](https://anywidget.dev) (installed
automatically as a dependency).

From the project root (the folder containing `pyproject.toml`):

```bash
pip install -e .
```

The `-e` (editable) install is recommended during development: changes to the
Python or the `static/` files take effect without reinstalling.

Verify it:

```bash
python -c "from multilevel_table import MultilevelTable; print('ok')"
```

---

## Run the Marimo demo

`demo.py` is a runnable Marimo notebook wired to the development hierarchy. It
declares its own dependencies inline (via the script metadata block) and points
at this package as a local editable source, so [`uv`](https://docs.astral.sh/uv/)
handles everything:

```bash
chmod +x demo.py
./demo.py
```

That launches the Marimo editor in your browser. Cells do not auto-run — run the
first cell (`cell_1`) and the rest follow. The notebook is launched with
`--watch`, so edits to the package are picked up automatically; just re-run the
affected cells.

If you prefer to invoke it explicitly rather than via the shebang:

```bash
uvx marimo edit --sandbox demo.py
```

---

## Use it in your own notebook

```python
from multilevel_table import H, MultilevelTable
import marimo as mo

# Build header trees with the H() shorthand: H(label, [children], key=...)
col_headers = H("Region", [
    H("EMEA", [
        H("UK", [H("Revenue", key="uk_rev"), H("Units", key="uk_units")], key="uk"),
        H("Germany", [H("Revenue", key="de_rev"), H("Units", key="de_units")], key="germany"),
    ], key="emea"),
    H("APAC", [
        H("Japan", [H("Revenue", key="jp_rev"), H("Units", key="jp_units")], key="japan"),
    ], key="apac"),
], key="region")

row_headers = H("Division", [
    H("Hardware", [
        H("Laptops", [H("Pro", key="pro"), H("Air", key="air")], key="laptops"),
    ], key="hardware"),
], key="division")

# Cell values are computed from the root-to-leaf key paths.
def calculate(row_path, col_path):
    # row_path / col_path are lists of node keys, e.g.
    #   ["division", "hardware", "laptops", "pro"]
    #   ["region", "emea", "uk", "uk_rev"]
    return f"{row_path[-1]}·{col_path[-1]}"

table = MultilevelTable(row_headers, col_headers, calculate=calculate)

# Wrap for Marimo so it's reactive, then display it.
widget = mo.ui.anywidget(table)
widget
```

In a later cell, read `widget.value` — it re-runs whenever the user merges,
splits, or renames:

```python
widget.value   # {"row_leaves": [...], "col_leaves": [...], "data": [[...]]}
```

You can also drive the structure programmatically:

```python
table.merge("laptops")        # collapse Laptops' children into it
table.split("laptops")        # expand them back
table.relabel("laptops", "Notebooks")
```

---

## The merge / split model

Headers form a tree. A node is a **leaf** if it was created without children
*or* if it has been merged.

**Merge** is only valid on a node whose direct children are *all currently
leaves*. This makes merges proceed **bottom-up**: you can't merge `Hardware`
until both `Laptops` and `Tablets` beneath it are themselves leaves.

```
Division                          Division
├── Hardware                      ├── Hardware  ← now mergeable
│   ├── Laptops  ← merge these    │   ├── Laptops  (leaf)
│   │   ├── Pro       first ──▶   │   └── Tablets  (leaf)
│   │   └── Air                   └── Software
│   └── Tablets (leaf)
```

**Split** reverses a merge exactly. A node remembers its children even while
merged, so splitting restores them in whatever state they were last in (a split
can reveal children that are themselves still merged).

**Rename** has no structural constraints — any header, any time. It changes only
the display label; the node's stable `key` never changes.

A single-child merge is **count-neutral**: merging `Security → Shield` replaces
one leaf (Shield) with another (Security), so the grid size is unchanged — but
the contents still recalculate because the leaf identity changed.

---

## API reference

### `H(label, children=None, *, key=None)`

Shorthand builder for a header node.

- `label` — display text.
- `children` — list of child `H(...)` nodes; omit for a leaf.
- `key` — stable identifier (keyword-only). If omitted, one is generated from
  the label plus a short random suffix. **Supply explicit keys** wherever you
  need to reference nodes later (in `calculate`, `merge`, etc.) or where two
  siblings share a label.

### `MultilevelTable(row_headers, col_headers, calculate=None)`

- `row_headers`, `col_headers` — a single `H(...)` root or a list of roots.
- `calculate(row_path, col_path) -> value` — called for every cell. Each path
  is a list of node keys from root to the current leaf. If omitted, all cells
  are `None`.

Methods (also usable from a notebook cell):

| Method | Effect |
|---|---|
| `table.merge(key)` | Merge the node (raises if invalid). |
| `table.split(key)` | Split the node (raises if invalid). |
| `table.relabel(key, label)` | Rename the node. |

Synced state (read these; Marimo observes them):

| Attribute | Contents |
|---|---|
| `table.value` | `{row_leaves, col_leaves, data}` snapshot of current structure. |
| `table.data` | The 2-D list of computed cell values. |
| `table.row_grid` / `table.col_grid` | Serialised span grids (used by the front end). |

---

## Architecture

State lives in **Python**. The JavaScript layer is a pure renderer. The loop:

```
User clicks a header in the browser
        │
        ▼
JS sends an intent  ──▶  {op: "merge", key: "laptops"}
        │
        ▼
Python mutates the header tree, recomputes the span grids and the data matrix
        │
        ▼
Synced traitlets update  ──▶  JS rebuilds the <table> from the new grids
```

Because JS never holds authoritative state, it can't drift out of sync — every
change is a full rebuild from the Python-computed grids. Invalid or stale
intents from the browser are ignored quietly; the next refresh re-aligns the
view with Python's truth.

The four code modules, in dependency order:

1. **`header.py`** — the `HeaderNode` tree, the `merge` / `split` / `relabel`
   operations and their validity rules, and forest-level helpers.
2. **`spans.py`** — walks the current visible tree and computes the
   `rowspan` / `colspan` and grid position of every header cell. Guarantees the
   header area tiles perfectly (no gaps, no overlaps).
3. **`widget.py`** — the anywidget class: traitlets, the JS→Python message
   handler, the programmatic API, and the content-calculation pass.
4. **`static/widget.js` + `static/widget.css`** — the renderer and styling.

---

## Running the tests

```bash
pip install pytest
python -m pytest multilevel_table/tests/ -v
```

117 tests cover the tree model, the span computation (including an
area-coverage invariant that proves the grid tiles correctly), and the widget's
message handling and data computation.

---

## Project layout

```
.
├── pyproject.toml                  # installable package definition
├── demo.py                         # runnable Marimo notebook
├── README.md                       # this file
├── HEADER_MODEL.md                 # design notes for the header model
├── HEADER_CODE_WALKTHROUGH.md      # line-by-line walkthrough of header.py
└── multilevel_table/
    ├── __init__.py                 # exports H, HeaderNode, MultilevelTable
    ├── header.py                   # tree model + operations
    ├── spans.py                    # colspan/rowspan computation
    ├── widget.py                   # anywidget class
    ├── static/
    │   ├── widget.js               # front-end renderer
    │   └── widget.css              # styling
    └── tests/
        ├── test_header.py
        ├── test_spans.py
        └── test_widget.py
```

---

## Deeper documentation

- **`HEADER_MODEL.md`** — the concepts and rules behind the header tree, with
  worked examples of every operation and edge case.
- **`HEADER_CODE_WALKTHROUGH.md`** — a plain-language, section-by-section
  explanation of `header.py`, including the Python idioms used.

---

## What's not built yet

- **Group / ungroup** — adding/removing an interior header level without
  changing the leaf set. Deliberately parked as a secondary feature.
- **Live-kernel round trip** — the renderer is verified in a browser against a
  mock model, and the Python message handler is unit-tested directly, but the
  full browser-to-Marimo-kernel comm loop is best confirmed by running
  `demo.py` on a desktop. The logic on both sides is identical and tested; the
  one seam not exercised by the screenshots is the live transport itself.
