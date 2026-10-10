"""
Tests for the MultilevelTable widget — Python side only.

These exercise initialisation, content calculation, the JS→Python message
handler (called directly, since there's no live comm in tests), and the
programmatic merge/split/relabel API.
"""

import pytest
from multilevel_table.header import H
from multilevel_table.widget import MultilevelTable


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def make_row_headers():
    return H("Division", [
        H("Hardware", [
            H("Laptops", [
                H("Pro 13in", key="pro_13"),
                H("Pro 15in", key="pro_15"),
                H("Air",      key="air"),
            ], key="laptops"),
            H("Tablets", [
                H("Standard", key="tab_std"),
                H("Plus",     key="tab_plus"),
            ], key="tablets"),
        ], key="hardware"),
        H("Software", [
            H("Productivity", [
                H("Basic", key="prod_basic"),
                H("Pro",   key="prod_pro"),
            ], key="productivity"),
            H("Security", [
                H("Shield", key="shield"),
            ], key="security"),
        ], key="software"),
    ], key="division")


def make_col_headers():
    return H("Region", [
        H("EMEA", [
            H("UK", [H("Revenue", key="uk_rev"), H("Units", key="uk_units")], key="uk"),
            H("Germany", [H("Revenue", key="de_rev"), H("Units", key="de_units")], key="germany"),
        ], key="emea"),
        H("APAC", [
            H("Japan", [H("Revenue", key="jp_rev"), H("Units", key="jp_units")], key="japan"),
            H("Australia", [H("Revenue", key="au_rev"), H("Units", key="au_units")], key="australia"),
        ], key="apac"),
    ], key="region")


def count_calc(row_path, col_path):
    """Deterministic value from the leaf keys — easy to assert against."""
    return f"{row_path[-1]}|{col_path[-1]}"


@pytest.fixture
def widget():
    return MultilevelTable(
        row_headers=make_row_headers(),
        col_headers=make_col_headers(),
        calculate=count_calc,
    )


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------

class TestInit:

    def test_grids_populated(self, widget):
        assert widget.col_grid["depth"] == 4
        assert widget.col_grid["leafCount"] == 8
        assert widget.row_grid["depth"] == 4
        assert widget.row_grid["leafCount"] == 8

    def test_data_shape(self, widget):
        # 8 row-leaves × 8 col-leaves
        assert len(widget.data) == 8
        assert all(len(row) == 8 for row in widget.data)

    def test_data_values_from_calculate(self, widget):
        # First row leaf is pro_13; first col leaf is uk_rev
        assert widget.data[0][0] == "pro_13|uk_rev"
        # Last row leaf is shield; last col leaf is au_units
        assert widget.data[7][7] == "shield|au_units"

    def test_value_snapshot(self, widget):
        assert widget.value["row_leaves"][0] == "pro_13"
        assert widget.value["col_leaves"][-1] == "au_units"
        assert widget.value["data"] == widget.data

    def test_accepts_forest_list(self):
        w = MultilevelTable(
            row_headers=[make_row_headers()],   # list form
            col_headers=make_col_headers(),     # single root form
            calculate=count_calc,
        )
        assert w.row_grid["leafCount"] == 8

    def test_calculate_optional(self):
        w = MultilevelTable(
            row_headers=make_row_headers(),
            col_headers=make_col_headers(),
        )
        assert w.data[0][0] is None


# ---------------------------------------------------------------------------
# Programmatic API
# ---------------------------------------------------------------------------

class TestProgrammaticAPI:

    def test_merge_updates_grid_and_data(self, widget):
        widget.merge("laptops")
        assert widget.col_grid["leafCount"] == 8   # cols unchanged
        assert widget.row_grid["leafCount"] == 6   # rows: 8 - 3 + 1
        assert len(widget.data) == 6

    def test_merge_recalculates_for_merged_leaf(self, widget):
        widget.merge("laptops")
        # First row leaf is now 'laptops'; its path ends at the merged node
        assert widget.data[0][0] == "laptops|uk_rev"

    def test_split_restores(self, widget):
        widget.merge("laptops")
        widget.split("laptops")
        assert widget.row_grid["leafCount"] == 8
        assert widget.data[0][0] == "pro_13|uk_rev"

    def test_relabel_updates_grid(self, widget):
        widget.relabel("laptops", "All Laptops")
        laptops = next(c for c in widget.row_grid["cells"] if c["key"] == "laptops")
        assert laptops["label"] == "All Laptops"

    def test_merge_col_side(self, widget):
        widget.merge("uk")
        assert widget.col_grid["leafCount"] == 7
        assert all(len(row) == 7 for row in widget.data)

    def test_merge_invalid_raises(self, widget):
        with pytest.raises(ValueError):
            widget.merge("hardware")   # children not yet leaves

    def test_unknown_key_raises(self, widget):
        with pytest.raises(KeyError):
            widget.merge("nonexistent")


# ---------------------------------------------------------------------------
# Message handling  (simulating JS → Python)
# ---------------------------------------------------------------------------

class TestMessageHandling:

    def test_merge_message(self, widget):
        widget._handle_msg(widget, {"op": "merge", "key": "laptops"}, [])
        assert widget.row_grid["leafCount"] == 6

    def test_split_message(self, widget):
        widget._handle_msg(widget, {"op": "merge", "key": "laptops"}, [])
        widget._handle_msg(widget, {"op": "split", "key": "laptops"}, [])
        assert widget.row_grid["leafCount"] == 8

    def test_relabel_message(self, widget):
        widget._handle_msg(widget, {"op": "relabel", "key": "laptops", "label": "Notebooks"}, [])
        laptops = next(c for c in widget.row_grid["cells"] if c["key"] == "laptops")
        assert laptops["label"] == "Notebooks"

    def test_invalid_merge_message_ignored(self, widget):
        # Merging hardware (invalid) should not raise out of the handler
        before = widget.row_grid["leafCount"]
        widget._handle_msg(widget, {"op": "merge", "key": "hardware"}, [])
        assert widget.row_grid["leafCount"] == before  # unchanged

    def test_stale_key_message_ignored(self, widget):
        before = widget.row_grid["leafCount"]
        widget._handle_msg(widget, {"op": "merge", "key": "ghost"}, [])
        assert widget.row_grid["leafCount"] == before

    def test_value_updates_after_message(self, widget):
        widget._handle_msg(widget, {"op": "merge", "key": "laptops"}, [])
        assert widget.value["row_leaves"][0] == "laptops"
        assert len(widget.value["data"]) == 6


# ---------------------------------------------------------------------------
# Full interaction sequence
# ---------------------------------------------------------------------------

class TestSequence:

    def test_bottom_up_merge_to_single_cell(self, widget):
        for key in ("laptops", "tablets"):
            widget.merge(key)
        widget.merge("hardware")
        for key in ("productivity", "security"):
            widget.merge(key)
        widget.merge("software")
        widget.merge("division")

        assert widget.row_grid["leafCount"] == 1
        assert len(widget.data) == 1
        assert widget.data[0][0] == "division|uk_rev"

    def test_merge_then_relabel_then_split(self, widget):
        widget.merge("uk")
        widget.relabel("uk", "United Kingdom")
        uk = next(c for c in widget.col_grid["cells"] if c["key"] == "uk")
        assert uk["label"] == "United Kingdom"
        assert uk["canSplit"] is True

        widget.split("uk")
        assert widget.col_grid["leafCount"] == 8
        # Relabel persists on the node even after split
        uk = next(c for c in widget.col_grid["cells"] if c["key"] == "uk")
        assert uk["label"] == "United Kingdom"
