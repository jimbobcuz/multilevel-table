"""
Tests for span computation using the 4-level development hierarchy.

The key invariant checked throughout:
    sum(cell.rowspan * cell.colspan for cell in grid.cells) == grid.depth * grid.leaf_count

Every cell in the header area must be covered by exactly one span.
"""

import pytest
from multilevel_table.header import H, find_node
from multilevel_table.spans import SpanCell, HeaderGrid, compute_col_header_grid, compute_row_header_grid


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def col_roots():
    """Region > Territory > Country > Metric  (8 leaves, depth 4)"""
    return [
        H("Region", [
            H("EMEA", [
                H("UK", [
                    H("Revenue", key="uk_rev"),
                    H("Units",   key="uk_units"),
                ], key="uk"),
                H("Germany", [
                    H("Revenue", key="de_rev"),
                    H("Units",   key="de_units"),
                ], key="germany"),
            ], key="emea"),
            H("APAC", [
                H("Japan", [
                    H("Revenue", key="jp_rev"),
                    H("Units",   key="jp_units"),
                ], key="japan"),
                H("Australia", [
                    H("Revenue", key="au_rev"),
                    H("Units",   key="au_units"),
                ], key="australia"),
            ], key="apac"),
        ], key="region"),
    ]


@pytest.fixture
def row_roots():
    """Division > Category > Product > Variant  (8 leaves, depth 4)"""
    return [
        H("Division", [
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
        ], key="division"),
    ]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def area_coverage(grid: HeaderGrid) -> int:
    return sum(c.rowspan * c.colspan for c in grid.cells)


def cell(grid: HeaderGrid, key: str) -> SpanCell:
    result = grid.find_cell(key)
    assert result is not None, f"Cell '{key}' not found in grid"
    return result


# ---------------------------------------------------------------------------
# Col headers — initial state
# ---------------------------------------------------------------------------

class TestColHeaderInitial:

    def test_grid_dimensions(self, col_roots):
        grid = compute_col_header_grid(col_roots)
        assert grid.depth == 4
        assert grid.leaf_count == 8

    def test_total_cell_count(self, col_roots):
        # One SpanCell per node in the tree (15 total: 1+2+4+8)
        grid = compute_col_header_grid(col_roots)
        assert len(grid.cells) == 15

    def test_area_coverage_invariant(self, col_roots):
        grid = compute_col_header_grid(col_roots)
        assert area_coverage(grid) == grid.total_area  # 4 × 8 = 32

    def test_root_spans_all_columns(self, col_roots):
        grid = compute_col_header_grid(col_roots)
        c = cell(grid, "region")
        assert c.row == 0
        assert c.col == 0
        assert c.rowspan == 1
        assert c.colspan == 8

    def test_internal_nodes_have_rowspan_one(self, col_roots):
        grid = compute_col_header_grid(col_roots)
        for key in ("region", "emea", "apac", "uk", "germany", "japan", "australia"):
            assert cell(grid, key).rowspan == 1, f"{key} should have rowspan=1"

    def test_emea_position_and_span(self, col_roots):
        c = cell(compute_col_header_grid(col_roots), "emea")
        assert c.row == 1 and c.col == 0
        assert c.rowspan == 1 and c.colspan == 4

    def test_apac_position_and_span(self, col_roots):
        c = cell(compute_col_header_grid(col_roots), "apac")
        assert c.row == 1 and c.col == 4
        assert c.rowspan == 1 and c.colspan == 4

    def test_uk_position_and_span(self, col_roots):
        c = cell(compute_col_header_grid(col_roots), "uk")
        assert c.row == 2 and c.col == 0
        assert c.rowspan == 1 and c.colspan == 2

    def test_germany_position_and_span(self, col_roots):
        c = cell(compute_col_header_grid(col_roots), "germany")
        assert c.row == 2 and c.col == 2
        assert c.rowspan == 1 and c.colspan == 2

    def test_leaf_cells_are_unit_spans(self, col_roots):
        grid = compute_col_header_grid(col_roots)
        for key in ("uk_rev", "uk_units", "de_rev", "de_units",
                    "jp_rev", "jp_units", "au_rev", "au_units"):
            c = cell(grid, key)
            assert c.rowspan == 1 and c.colspan == 1, f"{key} should be 1×1"

    def test_leaf_cells_occupy_bottom_row(self, col_roots):
        grid = compute_col_header_grid(col_roots)
        for key in ("uk_rev", "uk_units", "de_rev", "de_units",
                    "jp_rev", "jp_units", "au_rev", "au_units"):
            assert cell(grid, key).row == 3

    def test_leaf_column_positions(self, col_roots):
        grid = compute_col_header_grid(col_roots)
        expected_cols = {
            "uk_rev": 0, "uk_units": 1,
            "de_rev": 2, "de_units": 3,
            "jp_rev": 4, "jp_units": 5,
            "au_rev": 6, "au_units": 7,
        }
        for key, expected_col in expected_cols.items():
            assert cell(grid, key).col == expected_col, f"{key} col mismatch"

    def test_can_merge_flags(self, col_roots):
        grid = compute_col_header_grid(col_roots)
        # L3 nodes (UK, Germany, Japan, Australia) can be merged
        for key in ("uk", "germany", "japan", "australia"):
            assert cell(grid, key).can_merge
        # Others cannot
        for key in ("region", "emea", "apac"):
            assert not cell(grid, key).can_merge
        for key in ("uk_rev", "uk_units"):
            assert not cell(grid, key).can_merge

    def test_can_split_flags_all_false_initially(self, col_roots):
        grid = compute_col_header_grid(col_roots)
        assert all(not c.can_split for c in grid.cells)


# ---------------------------------------------------------------------------
# Col headers — after merging UK
# ---------------------------------------------------------------------------

class TestColHeaderAfterUKMerge:

    @pytest.fixture
    def grid(self, col_roots):
        find_node(col_roots, "uk").merge()
        return compute_col_header_grid(col_roots)

    def test_grid_dimensions(self, grid):
        # Depth stays 4 (Germany still reaches depth 4)
        # Leaf count drops from 8 to 7
        assert grid.depth == 4
        assert grid.leaf_count == 7

    def test_area_coverage_invariant(self, grid):
        assert area_coverage(grid) == grid.total_area  # 4 × 7 = 28

    def test_uk_becomes_merged_leaf_spanning_two_rows(self, grid):
        c = cell(grid, "uk")
        assert c.row == 2 and c.col == 0
        assert c.rowspan == 2  # D - depth + 1 = 4 - 3 + 1 = 2
        assert c.colspan == 1
        assert c.is_leaf and c.can_split

    def test_emea_colspan_reduces(self, grid):
        c = cell(grid, "emea")
        assert c.colspan == 3  # UK(1) + Germany(2)

    def test_germany_shifts_left(self, grid):
        c = cell(grid, "germany")
        assert c.col == 1  # was 2, now 1

    def test_de_rev_and_de_units_shift_left(self, grid):
        assert cell(grid, "de_rev").col == 1
        assert cell(grid, "de_units").col == 2

    def test_apac_shifts_left(self, grid):
        # APAC was at col=4, now at col=3
        assert cell(grid, "apac").col == 3

    def test_uk_rev_and_uk_units_absent(self, grid):
        assert grid.find_cell("uk_rev") is None
        assert grid.find_cell("uk_units") is None


# ---------------------------------------------------------------------------
# Col headers — after merging EMEA (requires UK and Germany merged first)
# ---------------------------------------------------------------------------

class TestColHeaderAfterEMEAMerge:

    @pytest.fixture
    def grid(self, col_roots):
        find_node(col_roots, "uk").merge()
        find_node(col_roots, "germany").merge()
        find_node(col_roots, "emea").merge()
        return compute_col_header_grid(col_roots)

    def test_grid_dimensions(self, grid):
        # EMEA (1 leaf) + APAC (4 leaves) = 5 leaves; depth still 4 (APAC)
        assert grid.depth == 4
        assert grid.leaf_count == 5

    def test_area_coverage_invariant(self, grid):
        assert area_coverage(grid) == grid.total_area  # 4 × 5 = 20

    def test_emea_spans_three_header_rows(self, grid):
        c = cell(grid, "emea")
        # At depth 2, D=4: rowspan = 4 - 2 + 1 = 3
        assert c.rowspan == 3
        assert c.colspan == 1
        assert c.col == 0 and c.row == 1

    def test_apac_starts_at_col_one(self, grid):
        assert cell(grid, "apac").col == 1


# ---------------------------------------------------------------------------
# Row headers — initial state
# ---------------------------------------------------------------------------

class TestRowHeaderInitial:

    def test_grid_dimensions(self, row_roots):
        grid = compute_row_header_grid(row_roots)
        assert grid.depth == 4
        assert grid.leaf_count == 8

    def test_area_coverage_invariant(self, row_roots):
        grid = compute_row_header_grid(row_roots)
        assert area_coverage(grid) == grid.total_area  # 4 × 8 = 32

    def test_root_spans_all_rows(self, row_roots):
        c = cell(compute_row_header_grid(row_roots), "division")
        assert c.row == 0 and c.col == 0
        assert c.rowspan == 8 and c.colspan == 1

    def test_hardware_position_and_span(self, row_roots):
        c = cell(compute_row_header_grid(row_roots), "hardware")
        assert c.row == 0 and c.col == 1
        assert c.rowspan == 5 and c.colspan == 1

    def test_software_position_and_span(self, row_roots):
        c = cell(compute_row_header_grid(row_roots), "software")
        assert c.row == 5 and c.col == 1
        assert c.rowspan == 3 and c.colspan == 1

    def test_laptops_position_and_span(self, row_roots):
        c = cell(compute_row_header_grid(row_roots), "laptops")
        assert c.row == 0 and c.col == 2
        assert c.rowspan == 3 and c.colspan == 1

    def test_leaf_positions(self, row_roots):
        grid = compute_row_header_grid(row_roots)
        expected_rows = {
            "pro_13": 0, "pro_15": 1, "air": 2,
            "tab_std": 3, "tab_plus": 4,
            "prod_basic": 5, "prod_pro": 6,
            "shield": 7,
        }
        for key, expected_row in expected_rows.items():
            assert cell(grid, key).row == expected_row, f"{key} row mismatch"

    def test_all_leaves_in_rightmost_col(self, row_roots):
        grid = compute_row_header_grid(row_roots)
        for key in ("pro_13", "pro_15", "air", "tab_std", "tab_plus",
                    "prod_basic", "prod_pro", "shield"):
            assert cell(grid, key).col == 3

    def test_leaf_cells_are_unit_spans(self, row_roots):
        grid = compute_row_header_grid(row_roots)
        for key in ("pro_13", "pro_15", "air", "tab_std", "tab_plus",
                    "prod_basic", "prod_pro"):
            c = cell(grid, key)
            assert c.rowspan == 1 and c.colspan == 1

    def test_security_single_child_span(self, row_roots):
        # Security is internal with one child (Shield) — rowspan=1, colspan=1
        c = cell(compute_row_header_grid(row_roots), "security")
        assert c.row == 7 and c.col == 2
        assert c.rowspan == 1 and c.colspan == 1

    def test_shield_position(self, row_roots):
        c = cell(compute_row_header_grid(row_roots), "shield")
        assert c.row == 7 and c.col == 3
        assert c.rowspan == 1 and c.colspan == 1


# ---------------------------------------------------------------------------
# Row headers — after merging Laptops
# ---------------------------------------------------------------------------

class TestRowHeaderAfterLaptopsMerge:

    @pytest.fixture
    def grid(self, row_roots):
        find_node(row_roots, "laptops").merge()
        return compute_row_header_grid(row_roots)

    def test_grid_dimensions(self, grid):
        # 8 leaves - 3 children + 1 merged node = 6 leaves; depth stays 4
        assert grid.depth == 4
        assert grid.leaf_count == 6

    def test_area_coverage_invariant(self, grid):
        assert area_coverage(grid) == grid.total_area  # 4 × 6 = 24

    def test_laptops_becomes_leaf_spanning_two_cols(self, grid):
        c = cell(grid, "laptops")
        # Leaf at depth 3, D=4: colspan = D - depth + 1 = 2
        assert c.row == 0 and c.col == 2
        assert c.rowspan == 1 and c.colspan == 2
        assert c.is_leaf and c.can_split

    def test_hardware_rowspan_reduces(self, grid):
        # Hardware now has 3 leaves: Laptops(merged), Standard, Plus
        assert cell(grid, "hardware").rowspan == 3

    def test_tablets_shifts_up(self, grid):
        # Laptops took 1 row instead of 3, so Tablets is now at row=1
        c = cell(grid, "tablets")
        assert c.row == 1
        assert c.rowspan == 2 and c.colspan == 1

    def test_software_shifts_up(self, grid):
        # Hardware went from 5 rows to 3, so Software is now at row=3
        assert cell(grid, "software").row == 3

    def test_original_laptop_leaves_absent(self, grid):
        for key in ("pro_13", "pro_15", "air"):
            assert grid.find_cell(key) is None


# ---------------------------------------------------------------------------
# Row headers — after merging Security (single-child — count-neutral)
# ---------------------------------------------------------------------------

class TestRowHeaderAfterSecurityMerge:

    @pytest.fixture
    def grid(self, row_roots):
        find_node(row_roots, "security").merge()
        return compute_row_header_grid(row_roots)

    def test_leaf_count_unchanged(self, grid):
        # Shield (1 leaf) is replaced by Security (1 leaf) — count neutral
        assert grid.leaf_count == 8

    def test_area_coverage_invariant(self, grid):
        assert area_coverage(grid) == grid.total_area  # 4 × 8 = 32

    def test_security_becomes_leaf_spanning_two_cols(self, grid):
        c = cell(grid, "security")
        assert c.row == 7 and c.col == 2
        assert c.rowspan == 1 and c.colspan == 2  # D - depth + 1 = 4 - 3 + 1 = 2
        assert c.is_leaf

    def test_shield_absent(self, grid):
        assert grid.find_cell("shield") is None


# ---------------------------------------------------------------------------
# Mixed depth — leaf at a shallower level than the forest maximum
# ---------------------------------------------------------------------------

class TestMixedDepth:
    """
    After merging UK, the col header tree has mixed depths:
    UK is a leaf at depth 3 while Germany's children are at depth 4.
    The rowspan of UK must fill down to row 3 (the bottom of the header band).
    """

    def test_shallow_leaf_rowspan_fills_to_bottom(self, col_roots):
        find_node(col_roots, "uk").merge()
        grid = compute_col_header_grid(col_roots)
        c = cell(grid, "uk")
        # UK is at depth 3 in a D=4 grid → rowspan should be 2
        assert c.rowspan == 2
        # Its bottom edge (row + rowspan) reaches row 4 — the grid bottom
        assert c.row + c.rowspan == grid.depth

    def test_area_coverage_still_valid(self, col_roots):
        find_node(col_roots, "uk").merge()
        grid = compute_col_header_grid(col_roots)
        assert area_coverage(grid) == grid.total_area
