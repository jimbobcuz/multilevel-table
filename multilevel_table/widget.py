"""
The MultilevelTable anywidget.

State lives in Python.  The JavaScript layer is a pure renderer: it receives
the serialised header grids and the data matrix via synced traitlets, and it
emits merge / split / relabel *intents* as custom messages.  Python applies
each intent to the header trees, recomputes everything, and pushes the new
state back — a clean unidirectional loop.

    JS click  ──▶  custom message {op, key, ...}
                       │
                       ▼
              Python mutates tree, recomputes grids + data
                       │
                       ▼
            synced traitlets update  ──▶  JS re-renders
"""

from __future__ import annotations

import pathlib
from typing import Any, Callable

import anywidget
import traitlets

from .header import (
    HeaderNode,
    all_leaves,
    find_node,
    leaf_key_paths,
)
from .spans import compute_col_header_grid, compute_row_header_grid

_STATIC = pathlib.Path(__file__).parent / "static"

# A calculate callback maps (row_path, col_path) → cell value.
# Each path is a list of node keys from root to the current leaf.
CalculateFn = Callable[[list[str], list[str]], Any]


class MultilevelTable(anywidget.AnyWidget):
    _esm = _STATIC / "widget.js"
    _css = _STATIC / "widget.css"

    # --- Python → JS (render state, read-only on the JS side) ---
    row_grid = traitlets.Dict().tag(sync=True)
    col_grid = traitlets.Dict().tag(sync=True)
    data = traitlets.List().tag(sync=True)

    # --- Reactive snapshot for Marimo (synced so dependent cells re-run) ---
    value = traitlets.Dict().tag(sync=True)

    def __init__(
        self,
        row_headers: HeaderNode | list[HeaderNode],
        col_headers: HeaderNode | list[HeaderNode],
        calculate: CalculateFn | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)

        # Normalise a single root into a forest (list of roots).
        self._row_roots = _as_forest(row_headers)
        self._col_roots = _as_forest(col_headers)
        self._calculate = calculate or (lambda r, c: None)

        # Receive merge/split/relabel intents from the JS layer.
        self.on_msg(self._handle_msg)

        # Initial render.
        self._refresh()

    # ------------------------------------------------------------------
    # Message handling  (JS → Python)
    # ------------------------------------------------------------------

    def _handle_msg(self, _widget, content: dict, _buffers) -> None:
        """Dispatch an intent message coming from the JS layer."""
        op = content.get("op")
        key = content.get("key")

        if op in ("merge", "split", "relabel"):
            node = self._find(key)
            if node is None:
                return  # stale key — ignore rather than raise into the comm
            try:
                if op == "merge":
                    node.merge()
                elif op == "split":
                    node.split()
                elif op == "relabel":
                    node.relabel(content["label"])
            except ValueError:
                # Invalid op for the current state — ignore and let the JS
                # re-sync from the authoritative Python state on next refresh.
                return
            self._refresh()

    # ------------------------------------------------------------------
    # Programmatic API  (usable directly from a notebook cell)
    # ------------------------------------------------------------------

    def merge(self, key: str) -> None:
        self._find_or_raise(key).merge()
        self._refresh()

    def split(self, key: str) -> None:
        self._find_or_raise(key).split()
        self._refresh()

    def relabel(self, key: str, label: str) -> None:
        self._find_or_raise(key).relabel(label)
        self._refresh()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _find(self, key: str) -> HeaderNode | None:
        return find_node(self._row_roots, key) or find_node(self._col_roots, key)

    def _find_or_raise(self, key: str) -> HeaderNode:
        node = self._find(key)
        if node is None:
            raise KeyError(f"No header node with key {key!r}")
        return node

    def _compute_data(self) -> list[list[Any]]:
        row_paths = leaf_key_paths(self._row_roots)
        col_paths = leaf_key_paths(self._col_roots)
        return [
            [self._calculate(rp, cp) for cp in col_paths]
            for rp in row_paths
        ]

    def _refresh(self) -> None:
        """Recompute grids + data and push everything to the JS layer."""
        self.col_grid = compute_col_header_grid(self._col_roots).to_dict()
        self.row_grid = compute_row_header_grid(self._row_roots).to_dict()
        self.data = self._compute_data()
        self.value = {
            "row_leaves": [leaf.key for leaf in all_leaves(self._row_roots)],
            "col_leaves": [leaf.key for leaf in all_leaves(self._col_roots)],
            "data": self.data,
        }


def _as_forest(headers: HeaderNode | list[HeaderNode]) -> list[HeaderNode]:
    if isinstance(headers, HeaderNode):
        return [headers]
    return list(headers)
