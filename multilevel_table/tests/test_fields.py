"""Tests for field-based cross-product hierarchy construction."""

import pytest
from multilevel_table.fields import Field, build_forest, field_captions
from multilevel_table.header import all_leaves, find_node, forest_full_depth
from multilevel_table.spans import compute_col_header_grid


@pytest.fixture
def two_fields():
    return [
        Field("Region", ["EMEA", "APAC"]),
        Field("Metric", ["Revenue", "Units"]),
    ]


@pytest.fixture
def three_fields():
    return [
        Field("Region", ["EMEA", "APAC"]),
        Field("Quarter", ["Q1", "Q2"]),
        Field("Metric", ["Revenue", "Units"]),
    ]


class TestStructure:

    def test_root_count_is_first_field_member_count(self, two_fields):
        roots = build_forest(two_fields)
        assert len(roots) == 2
        assert [r.label for r in roots] == ["EMEA", "APAC"]

    def test_leaf_count_is_product(self, two_fields):
        assert len(all_leaves(build_forest(two_fields))) == 4

    def test_three_field_leaf_count(self, three_fields):
        # 2 * 2 * 2
        assert len(all_leaves(build_forest(three_fields))) == 8

    def test_depth_equals_field_count(self, three_fields):
        assert forest_full_depth(build_forest(three_fields)) == 3

    def test_cross_product_is_regular(self, two_fields):
        roots = build_forest(two_fields)
        for root in roots:
            assert [c.label for c in root.children] == ["Revenue", "Units"]

    def test_keys_unique(self, three_fields):
        roots = build_forest(three_fields)
        keys = [n.key for r in roots for n in r.all_nodes()]
        assert len(keys) == len(set(keys))

    def test_leaf_order(self, two_fields):
        roots = build_forest(two_fields)
        labels = [leaf.label for leaf in all_leaves(roots)]
        assert labels == ["Revenue", "Units", "Revenue", "Units"]

    def test_empty_fields(self):
        assert build_forest([]) == []


class TestStartMerged:

    def test_merged_field_collapses_its_level(self):
        roots = build_forest([
            Field("Region", ["EMEA", "APAC"]),
            Field("Metric", ["Revenue", "Units"], start_merged=True),
        ])
        # Metric is the deepest field — start_merged has nothing to collapse there
        assert len(all_leaves(roots)) == 4

    def test_merged_middle_field(self):
        roots = build_forest([
            Field("Region", ["EMEA", "APAC"]),
            Field("Quarter", ["Q1", "Q2"], start_merged=True),
            Field("Metric", ["Revenue", "Units"]),
        ])
        # Quarter nodes start merged → their Metric children hidden
        # Visible leaves = Region(2) × Quarter(2) = 4 merged-leaf Quarter nodes
        assert len(all_leaves(roots)) == 4
        for leaf in all_leaves(roots):
            assert leaf.label in ("Q1", "Q2")
            assert leaf.merged
            assert leaf.can_split   # pre-merged but splittable

    def test_merged_node_splits_open(self):
        roots = build_forest([
            Field("Region", ["EMEA", "APAC"]),
            Field("Quarter", ["Q1", "Q2"], start_merged=True),
            Field("Metric", ["Revenue", "Units"]),
        ])
        # Split one Quarter node open → its two Metrics appear, leaf count +1
        before = len(all_leaves(roots))
        q = next(leaf for leaf in all_leaves(roots))
        q.split()
        assert len(all_leaves(roots)) == before + 1

    def test_top_field_merged(self):
        roots = build_forest([
            Field("Region", ["EMEA", "APAC"], start_merged=True),
            Field("Metric", ["Revenue", "Units"]),
        ])
        # Region nodes start merged → only 2 visible leaves (EMEA, APAC)
        assert len(all_leaves(roots)) == 2
        assert all(leaf.merged and leaf.can_split for leaf in all_leaves(roots))


class TestIntegration:

    def test_feeds_span_computation(self, three_fields):
        roots = build_forest(three_fields)
        grid = compute_col_header_grid(roots)
        assert grid.depth == 3
        assert grid.leaf_count == 8
        # area-coverage invariant still holds
        assert sum(c.rowspan * c.colspan for c in grid.cells) == grid.depth * grid.leaf_count

    def test_captions(self, three_fields):
        assert field_captions(three_fields) == ["Region", "Quarter", "Metric"]
