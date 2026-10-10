"""
The MultilevelTable anywidget (v2).

Columns carry a mergeable hierarchy; rows carry a fixed hierarchy with one
data row per row leaf.  Every data cell is the output of a user-supplied
``calculate(row_path, col_path)`` callback — normally an SVG string.

State flow
----------
Python owns the header trees and computes everything the browser draws.
The browser changes exactly two pieces of state, both as ordinary synced
traits (``model.set`` + ``save_changes``), which is the path marimo watches
for reactivity:

    col_merged   list of column keys the user wants merged
    selected     {"row": [...keys], "col": [...keys]} or None

Python observes those traits, validates them against the tree, recomputes,
and writes back the corrected state.

    browser click ──▶ model.set("col_merged" | "selected")
                           │
                           ▼
          Python observer: apply merges/splits, recompute grids + data
                           │
                           ▼
            synced traits update ──▶ browser re-renders

In marimo, wrap the widget with ``mo.ui.anywidget(table)``; ``widget.value``
is then a dict of every synced trait, e.g. ``widget.value["selected"]``.
"""

from __future__ import annotations

import pathlib
from typing import Any, Callable

import anywidget
import traitlets

from .header import HeaderNode, find_node, leaf_key_paths
from .spans import compute_col_header_grid, compute_row_header_grid

_STATIC = pathlib.Path(__file__).parent / "static"

# (row_path, col_path) -> SVG string, number, text or None.
CalculateFn = Callable[[list[str], list[str]], Any]


class MultilevelTable(anywidget.AnyWidget):
    _esm = _STATIC / "widget.js"
    _css = _STATIC / "widget.css"

    # --- Python -> browser (render state) ---
    col_grid = traitlets.Dict().tag(sync=True)
    row_grid = traitlets.Dict().tag(sync=True)
    col_paths = traitlets.List().tag(sync=True)
    row_paths = traitlets.List().tag(sync=True)
    data = traitlets.List().tag(sync=True)
    cell_width = traitlets.Int(96).tag(sync=True)
    cell_height = traitlets.Int(48).tag(sync=True)

    # --- Two-way (the browser sets these) ---
    col_merged = traitlets.List(traitlets.Unicode()).tag(sync=True)
    selected = traitlets.Dict(allow_none=True, default_value=None).tag(sync=True)

    def __init__(
        self,
        row_headers: HeaderNode | list[HeaderNode],
        col_headers: HeaderNode | list[HeaderNode],
        calculate: CalculateFn | None = None,
        *,
        cell_width: int = 96,
        cell_height: int = 48,
        **kwargs,
    ):
        self._row_roots = _as_forest(row_headers)
        self._col_roots = _as_forest(col_headers)
        self._calculate = calculate or (lambda r, c: None)
        super().__init__(cell_width=cell_width, cell_height=cell_height, **kwargs)
        self._refresh()

    # ------------------------------------------------------------------
    # Programmatic API
    # ------------------------------------------------------------------

    def merge(self, key: str) -> None:
        """Merge a column header. Raises if the key is unknown, is a row
        header, or the node can't be merged in its current state."""
        self._col_node_or_raise(key).merge()
        self._refresh()

    def split(self, key: str) -> None:
        """Split a merged column header."""
        self._col_node_or_raise(key).split()
        self._refresh()

    def relabel(self, key: str, label: str) -> None:
        """Rename any header (row or column). Python-only in v2."""
        node = find_node(self._col_roots, key) or find_node(self._row_roots, key)
        if node is None:
            raise KeyError(f"No header node with key {key!r}")
        node.relabel(label)
        self._refresh()

    def select(self, row_key: str, col_key: str) -> None:
        """Select the cell at a row leaf and a column leaf."""
        row = _path_ending(self.row_paths, row_key)
        col = _path_ending(self.col_paths, col_key)
        if row is None or col is None:
            raise KeyError(f"No current cell at ({row_key!r}, {col_key!r})")
        self.selected = {"row": row, "col": col}

    def clear_selection(self) -> None:
        self.selected = None

    # ------------------------------------------------------------------
    # Browser-driven changes
    # ------------------------------------------------------------------

    @traitlets.observe("col_merged")
    def _on_col_merged(self, change) -> None:
        if getattr(self, "_syncing", False):
            return
        wanted = set(change["new"])
        current = set(self._merged_keys())
        if wanted == current:
            return

        # Splits first, shallowest first, so children reappear before any
        # further decisions about them.
        for key in self._ordered(current - wanted, deepest_first=False):
            node = find_node(self._col_roots, key)
            if node is not None and node.can_split:
                node.split()
        # Then merges, deepest first, so a parent only merges once its
        # children are leaves.
        for key in self._ordered(wanted - current, deepest_first=True):
            node = find_node(self._col_roots, key)
            if node is not None and node.can_merge:
                node.merge()
        # Invalid requests are dropped; _refresh writes back the true state.
        self._refresh()

    @traitlets.observe("selected")
    def _on_selected(self, change) -> None:
        sel = change["new"]
        if sel is not None and not self._selection_is_current(sel):
            self.selected = None

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _col_node_or_raise(self, key: str) -> HeaderNode:
        node = find_node(self._col_roots, key)
        if node is None:
            if find_node(self._row_roots, key) is not None:
                raise ValueError(f"{key!r} is a row header; only column headers can be merged or split")
            raise KeyError(f"No column header with key {key!r}")
        return node

    def _merged_keys(self) -> list[str]:
        return [n.key for r in self._col_roots for n in r.all_nodes() if n.merged]

    def _ordered(self, keys: set[str], *, deepest_first: bool) -> list[str]:
        depth = {}

        def walk(node: HeaderNode, d: int) -> None:
            depth[node.key] = d
            for c in node.children:
                walk(c, d + 1)

        for r in self._col_roots:
            walk(r, 0)
        known = [k for k in keys if k in depth]
        return sorted(known, key=lambda k: depth[k], reverse=deepest_first)

    def _selection_is_current(self, sel: dict) -> bool:
        return (
            isinstance(sel, dict)
            and sel.get("row") in self.row_paths
            and sel.get("col") in self.col_paths
        )

    def _refresh(self) -> None:
        """Recompute everything the browser draws and push it."""
        row_paths = leaf_key_paths(self._row_roots)
        col_paths = leaf_key_paths(self._col_roots)

        row_grid = compute_row_header_grid(self._row_roots).to_dict()
        for cell in row_grid["cells"]:          # rows are never mergeable
            cell["canMerge"] = False
            cell["canSplit"] = False

        data = [[_cell_value(self._calculate(rp, cp)) for cp in col_paths] for rp in row_paths]

        with self.hold_sync():
            self._syncing = True
            try:
                self.col_grid = compute_col_header_grid(self._col_roots).to_dict()
                self.row_grid = row_grid
                self.row_paths = row_paths
                self.col_paths = col_paths
                self.data = data
                self.col_merged = self._merged_keys()
            finally:
                self._syncing = False
            if self.selected is not None and not self._selection_is_current(self.selected):
                self.selected = None


def _cell_value(v: Any) -> Any:
    """Keep JSON-native values; stringify anything else."""
    if v is None or isinstance(v, (str, int, float, bool)):
        return v
    return str(v)


def _path_ending(paths: list[list[str]], key: str) -> list[str] | None:
    for p in paths:
        if p and p[-1] == key:
            return p
    return None


def _as_forest(headers: HeaderNode | list[HeaderNode]) -> list[HeaderNode]:
    if isinstance(headers, HeaderNode):
        return [headers]
    return list(headers)
