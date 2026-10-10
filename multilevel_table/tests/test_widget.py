"""
Tests for the MultilevelTable widget (v2) — Python side.

Browser actions are simulated by assigning the two-way traits
(`col_merged`, `selected`) exactly as `model.set` + `save_changes` would.
"""

import pytest
from multilevel_table.header import H
from multilevel_table.widget import MultilevelTable


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
            H("Security", [H("Shield", key="shield")], key="security"),
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


def label_calc(row_path, col_path):
    return f"{row_path[-1]}|{col_path[-1]}"


@pytest.fixture
def table():
    return MultilevelTable(make_row_headers(), make_col_headers(), label_calc)


# ---------------------------------------------------------------------------
# Initial state
# ---------------------------------------------------------------------------

class TestInit:

    def test_grids_and_shape(self, table):
        assert table.col_grid["leafCount"] == 8
        assert table.row_grid["leafCount"] == 8
        assert len(table.data) == 8 and all(len(r) == 8 for r in table.data)

    def test_paths(self, table):
        assert table.row_paths[0] == ["division", "hardware", "laptops", "pro_13"]
        assert table.col_paths[0] == ["region", "emea", "uk", "uk_rev"]

    def test_data_from_calculate(self, table):
        assert table.data[0][0] == "pro_13|uk_rev"
        assert table.data[7][7] == "shield|au_units"

    def test_default_cell_size(self, table):
        assert (table.cell_width, table.cell_height) == (96, 48)

    def test_custom_cell_size(self):
        t = MultilevelTable(make_row_headers(), make_col_headers(), cell_width=120, cell_height=60)
        assert (t.cell_width, t.cell_height) == (120, 60)

    def test_nothing_merged_or_selected(self, table):
        assert table.col_merged == []
        assert table.selected is None

    def test_row_cells_never_offer_merge(self, table):
        assert all(not c["canMerge"] and not c["canSplit"] for c in table.row_grid["cells"])

    def test_col_cells_offer_merge(self, table):
        uk = next(c for c in table.col_grid["cells"] if c["key"] == "uk")
        assert uk["canMerge"]

    def test_calculate_optional(self):
        t = MultilevelTable(make_row_headers(), make_col_headers())
        assert t.data[0][0] is None

    def test_premerged_columns_reflected(self):
        cols = make_col_headers()
        cols.find("uk").merge()
        t = MultilevelTable(make_row_headers(), cols)
        assert t.col_merged == ["uk"]
        assert t.col_grid["leafCount"] == 7


# ---------------------------------------------------------------------------
# Cell values
# ---------------------------------------------------------------------------

class TestCellValues:

    def test_svg_strings_pass_through(self):
        svg = "<svg viewBox='0 0 10 10'><rect width='10' height='10'/></svg>"
        t = MultilevelTable(make_row_headers(), make_col_headers(), lambda r, c: svg)
        assert t.data[0][0] == svg

    def test_numbers_pass_through(self):
        t = MultilevelTable(make_row_headers(), make_col_headers(), lambda r, c: 3.5)
        assert t.data[0][0] == 3.5

    def test_other_objects_stringified(self):
        class Thing:
            def __str__(self):
                return "thing"
        t = MultilevelTable(make_row_headers(), make_col_headers(), lambda r, c: Thing())
        assert t.data[0][0] == "thing"


# ---------------------------------------------------------------------------
# Programmatic API
# ---------------------------------------------------------------------------

class TestProgrammaticAPI:

    def test_merge_column(self, table):
        table.merge("uk")
        assert table.col_merged == ["uk"]
        assert table.col_grid["leafCount"] == 7
        assert table.data[0][0] == "pro_13|uk"

    def test_split_column(self, table):
        table.merge("uk")
        table.split("uk")
        assert table.col_merged == []
        assert table.data[0][0] == "pro_13|uk_rev"

    def test_merge_row_raises(self, table):
        with pytest.raises(ValueError, match="row header"):
            table.merge("laptops")

    def test_split_row_raises(self, table):
        with pytest.raises(ValueError, match="row header"):
            table.split("laptops")

    def test_rows_unchanged_by_column_merge(self, table):
        table.merge("uk")
        assert table.row_grid["leafCount"] == 8

    def test_invalid_merge_raises(self, table):
        with pytest.raises(ValueError):
            table.merge("emea")

    def test_unknown_key_raises(self, table):
        with pytest.raises(KeyError):
            table.merge("ghost")

    def test_relabel_column(self, table):
        table.relabel("uk", "United Kingdom")
        uk = next(c for c in table.col_grid["cells"] if c["key"] == "uk")
        assert uk["label"] == "United Kingdom"

    def test_relabel_row(self, table):
        table.relabel("laptops", "Notebooks")
        cell = next(c for c in table.row_grid["cells"] if c["key"] == "laptops")
        assert cell["label"] == "Notebooks"


# ---------------------------------------------------------------------------
# Browser-driven merges (col_merged trait)
# ---------------------------------------------------------------------------

class TestBrowserMerges:

    def test_browser_merge(self, table):
        table.col_merged = ["uk"]
        assert table.col_grid["leafCount"] == 7
        assert table.data[0][0] == "pro_13|uk"

    def test_browser_split(self, table):
        table.col_merged = ["uk"]
        table.col_merged = []
        assert table.col_grid["leafCount"] == 8

    def test_invalid_merge_dropped_and_written_back(self, table):
        table.col_merged = ["emea"]          # children not leaves yet
        assert table.col_merged == []
        assert table.col_grid["leafCount"] == 8

    def test_unknown_key_dropped(self, table):
        table.col_merged = ["ghost"]
        assert table.col_merged == []

    def test_row_key_dropped(self, table):
        table.col_merged = ["laptops"]
        assert table.col_merged == []
        assert table.row_grid["leafCount"] == 8

    def test_nested_merge_in_one_request(self, table):
        # Deepest-first ordering lets a parent merge once its children have.
        table.col_merged = ["uk", "germany", "emea"]
        assert sorted(table.col_merged) == ["emea", "germany", "uk"]
        assert table.col_grid["leafCount"] == 5   # EMEA + 4 APAC leaves

    def test_split_parent_keeps_merged_children(self, table):
        table.col_merged = ["uk", "germany", "emea"]
        table.col_merged = ["uk", "germany"]
        assert table.col_grid["leafCount"] == 6   # UK, Germany, 4 APAC


# ---------------------------------------------------------------------------
# Selection
# ---------------------------------------------------------------------------

class TestSelection:

    def test_select_by_keys(self, table):
        table.select("air", "de_units")
        assert table.selected == {
            "row": ["division", "hardware", "laptops", "air"],
            "col": ["region", "emea", "germany", "de_units"],
        }

    def test_browser_select(self, table):
        sel = {"row": table.row_paths[2], "col": table.col_paths[3]}
        table.selected = sel
        assert table.selected == sel

    def test_clear(self, table):
        table.select("air", "de_units")
        table.clear_selection()
        assert table.selected is None

    def test_select_unknown_raises(self, table):
        with pytest.raises(KeyError):
            table.select("air", "ghost")

    def test_stale_browser_selection_cleared(self, table):
        table.selected = {"row": ["nope"], "col": ["nope"]}
        assert table.selected is None

    def test_selection_survives_unrelated_merge(self, table):
        table.select("air", "jp_rev")
        table.merge("uk")
        assert table.selected["col"][-1] == "jp_rev"

    def test_selection_cleared_when_its_column_merges(self, table):
        table.select("air", "uk_rev")
        table.merge("uk")
        assert table.selected is None
