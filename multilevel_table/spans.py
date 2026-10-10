"""
Span computation for multilevel header rendering.

Given a forest of HeaderNodes, this module computes the colspan and rowspan
that each visible node needs as an HTML <th> element.

Two orientations are supported:

  compute_col_header_grid  —  column headers rendered as rows above the data.
                              Depth maps to rows; leaf position maps to columns.

  compute_row_header_grid  —  row headers rendered as columns to the left.
                              Depth maps to columns; leaf position maps to rows.

The algorithms are identical in structure; only which axis carries depth and
which carries leaf position differs.

Invariant
---------
For any valid grid, the sum of (rowspan × colspan) across all cells equals
exactly (grid.depth × grid.leaf_count).  Every cell in the header area is
covered by exactly one span — no gaps, no overlaps.
"""

from __future__ import annotations

from dataclasses import dataclass

from .header import HeaderNode, all_leaves, forest_visible_depth


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class SpanCell:
    """
    A single rendered header cell with its grid position and span values.

    row, col    — zero-indexed position in the full header grid.
    rowspan     — number of grid rows this cell occupies.
    colspan     — number of grid columns this cell occupies.

    For column headers  the grid has `depth` rows and `leaf_count` columns.
    For row headers     the grid has `leaf_count` rows and `depth` columns.
    """
    key: str
    label: str
    row: int
    col: int
    rowspan: int
    colspan: int
    is_leaf: bool
    can_merge: bool
    can_split: bool

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "label": self.label,
            "row": self.row,
            "col": self.col,
            "rowspan": self.rowspan,
            "colspan": self.colspan,
            "isLeaf": self.is_leaf,
            "canMerge": self.can_merge,
            "canSplit": self.can_split,
        }


@dataclass
class HeaderGrid:
    """
    The complete set of span cells for one header axis, plus dimensions.

    depth       — number of header rows (col axis) or header columns (row axis).
    leaf_count  — number of data columns (col axis) or data rows (row axis).
    """
    cells: list[SpanCell]
    depth: int
    leaf_count: int

    # --- Lookup helpers ---

    def find_cell(self, key: str) -> SpanCell | None:
        """Return the cell for *key*, or None."""
        for cell in self.cells:
            if cell.key == key:
                return cell
        return None

    def cells_at_row(self, row: int) -> list[SpanCell]:
        """All cells whose top edge is at *row*."""
        return [c for c in self.cells if c.row == row]

    def cells_at_col(self, col: int) -> list[SpanCell]:
        """All cells whose left edge is at *col*."""
        return [c for c in self.cells if c.col == col]

    @property
    def total_area(self) -> int:
        """Expected sum of rowspan × colspan — equals depth × leaf_count."""
        return self.depth * self.leaf_count

    @property
    def covered_area(self) -> int:
        """Actual sum of rowspan × colspan across all cells."""
        return sum(c.rowspan * c.colspan for c in self.cells)

    def to_dict(self) -> dict:
        return {
            "cells": [c.to_dict() for c in self.cells],
            "depth": self.depth,
            "leafCount": self.leaf_count,
        }


# ---------------------------------------------------------------------------
# Core algorithms
# ---------------------------------------------------------------------------

def compute_col_header_grid(roots: list[HeaderNode]) -> HeaderGrid:
    """
    Column headers — rendered as horizontal rows above the data table.

    Each node sits in the row corresponding to its depth.  Its colspan is the
    number of leaves beneath it.  If it is a leaf it receives rowspan equal to
    the remaining depth below it (so it stretches down to the bottom of the
    header band), otherwise rowspan is 1.

    Example — initial col_roots (D=4, 8 leaves):

        row 0  Region  ·············· colspan=8
        row 1  EMEA ···· colspan=4   APAC ···· colspan=4
        row 2  UK·· Germany··        Japan·· Australia··
        row 3  Rev Units Rev Units   Rev Units Rev  Units
    """
    D = forest_visible_depth(roots)
    cells: list[SpanCell] = []

    def walk(node: HeaderNode, depth: int, col_offset: int) -> None:
        colspan = node.leaf_count()
        rowspan = D - depth + 1 if node.is_leaf else 1

        cells.append(SpanCell(
            key=node.key,
            label=node.label,
            row=depth - 1,
            col=col_offset,
            rowspan=rowspan,
            colspan=colspan,
            is_leaf=node.is_leaf,
            can_merge=node.can_merge,
            can_split=node.can_split,
        ))

        if not node.is_leaf:
            child_col = col_offset
            for child in node.children:
                walk(child, depth + 1, child_col)
                child_col += child.leaf_count()

    col_offset = 0
    for root in roots:
        walk(root, 1, col_offset)
        col_offset += root.leaf_count()

    return HeaderGrid(
        cells=cells,
        depth=D,
        leaf_count=len(all_leaves(roots)),
    )


def compute_row_header_grid(roots: list[HeaderNode]) -> HeaderGrid:
    """
    Row headers — rendered as vertical columns to the left of the data table.

    Depth maps to columns; leaf position maps to rows.  A node's rowspan is
    the number of leaves beneath it.  If it is a leaf its colspan stretches
    right to the last header column (D - depth + 1), otherwise colspan is 1.

    Example — initial row_roots (D=4, 8 leaves):

        col 0       col 1       col 2         col 3
        Division    Hardware    Laptops       Pro 13in   rowspan=1
                                              Pro 15in   rowspan=1
                                              Air        rowspan=1
                                Tablets       Standard   rowspan=1
                                              Plus       rowspan=1
                    Software    Productivity  Basic      rowspan=1
                                              Pro        rowspan=1
                                Security      Shield     rowspan=1 colspan=2
    """
    D = forest_visible_depth(roots)
    cells: list[SpanCell] = []

    def walk(node: HeaderNode, depth: int, row_offset: int) -> None:
        rowspan = node.leaf_count()
        colspan = D - depth + 1 if node.is_leaf else 1

        cells.append(SpanCell(
            key=node.key,
            label=node.label,
            row=row_offset,
            col=depth - 1,
            rowspan=rowspan,
            colspan=colspan,
            is_leaf=node.is_leaf,
            can_merge=node.can_merge,
            can_split=node.can_split,
        ))

        if not node.is_leaf:
            child_row = row_offset
            for child in node.children:
                walk(child, depth + 1, child_row)
                child_row += child.leaf_count()

    row_offset = 0
    for root in roots:
        walk(root, 1, row_offset)
        row_offset += root.leaf_count()

    return HeaderGrid(
        cells=cells,
        depth=D,
        leaf_count=len(all_leaves(roots)),
    )
