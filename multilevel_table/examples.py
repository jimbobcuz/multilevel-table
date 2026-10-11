"""
The development hierarchy and an example SVG `calculate`, shared by the demo
notebooks and the browser check.

    from multilevel_table.examples import example_headers, example_calculate
    rows, cols = example_headers()
    table = MultilevelTable(rows, cols, example_calculate)
"""

from __future__ import annotations

import zlib

from .header import H, HeaderNode

TILE_W, TILE_H = 96, 48


def example_headers() -> tuple[HeaderNode, HeaderNode]:
    """Rows: Division > Category > Product > Variant (8 leaves).
    Columns: Region > Country > Metric (8 leaves)."""
    rows = H("Division", [
        H("Hardware", [
            H("Laptops", [
                H("Pro 13in", key="pro_13"),
                H("Pro 15in", key="pro_15"),
                H("Air", key="air"),
            ], key="laptops"),
            H("Tablets", [
                H("Standard", key="tab_std"),
                H("Plus", key="tab_plus"),
            ], key="tablets"),
        ], key="hardware"),
        H("Software", [
            H("Productivity", [
                H("Basic", key="prod_basic"),
                H("Pro", key="prod_pro"),
            ], key="productivity"),
            H("Security", [H("Shield", key="shield")], key="security"),
        ], key="software"),
    ], key="division")

    cols = H("Region", [
        H("EMEA", [
            H("United Kingdom", [H("Revenue", key="uk_rev"), H("Units", key="uk_units")], key="uk"),
            H("Germany", [H("Revenue", key="de_rev"), H("Units", key="de_units")], key="germany"),
        ], key="emea"),
        H("APAC", [
            H("Japan", [H("Revenue", key="jp_rev"), H("Units", key="jp_units")], key="japan"),
            H("Australia", [H("Revenue", key="au_rev"), H("Units", key="au_units")], key="australia"),
        ], key="apac"),
    ], key="region")
    return rows, cols


def _score(*parts: str) -> float:
    """Deterministic pseudo-value in [0, 1) from a set of keys."""
    return (zlib.crc32("/".join(parts).encode()) % 1000) / 1000


def example_calculate(row_path: list[str], col_path: list[str]) -> str:
    """
    A tile per cell, drawn in a viewBox the same shape as the tile (96 x 48)
    so it fills the cell edge to edge.

    - Revenue leaves: a horizontal bar.
    - Units leaves:   five small columns.
    - Merged columns (the path stops above the metric level): a summary bar
      in a second colour, showing the cell really is recalculated on merge.
    """
    leaf = col_path[-1]
    v = _score(row_path[-1], leaf)
    w, h = TILE_W, TILE_H

    if leaf.endswith("_rev"):
        bar = 8 + v * (w - 16)
        return (
            f"<svg viewBox='0 0 {w} {h}' preserveAspectRatio='none'>"
            f"<rect width='{w}' height='{h}' fill='#eef3f2'/>"
            f"<rect x='8' y='18' width='{bar:.1f}' height='12' rx='2' fill='#16706b'/>"
            f"</svg>"
        )

    if leaf.endswith("_units"):
        cols = []
        for i in range(5):
            ch = 6 + _score(row_path[-1], leaf, str(i)) * (h - 14)
            cols.append(f"<rect x='{12 + i * 15}' y='{h - 4 - ch:.1f}' width='10' height='{ch:.1f}' fill='#5b6fb3'/>")
        return (
            f"<svg viewBox='0 0 {w} {h}' preserveAspectRatio='none'>"
            f"<rect width='{w}' height='{h}' fill='#f0f1f7'/>{''.join(cols)}</svg>"
        )

    # A merged column: one summary bar plus the name of what was merged.
    bar = 8 + v * (w - 16)
    return (
        f"<svg viewBox='0 0 {w} {h}' preserveAspectRatio='none'>"
        f"<rect width='{w}' height='{h}' fill='#f7efe6'/>"
        f"<rect x='8' y='20' width='{bar:.1f}' height='16' rx='2' fill='#b0602a'/>"
        f"<text x='8' y='14' font-size='9' font-family='sans-serif' fill='#6b4a2e'>Σ {leaf}</text>"
        f"</svg>"
    )
