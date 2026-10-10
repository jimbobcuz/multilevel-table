"""
Tests for HeaderNode using the 4-level development hierarchy.

Rows:  Division > Category > Product > Variant   (8 leaves)
Cols:  Region   > Territory > Quarter > Metric   (8 leaves)
"""

import pytest
from multilevel_table.header import (
    H,
    HeaderNode,
    all_leaves,
    find_node,
    forest_full_depth,
    forest_visible_depth,
    mergeable_nodes,
    splittable_nodes,
    serialize_forest,
    deserialize_forest,
)


# ---------------------------------------------------------------------------
# Fixtures — always use explicit keys for stable, readable test output
# ---------------------------------------------------------------------------

@pytest.fixture
def row_roots():
    """Division > Category > Product > Variant  (8 leaves)"""
    return [
        H("Division", [
            H("Hardware", [
                H("Laptops", [
                    H("Pro 13in", key="pro_13"),
                    H("Pro 15in", key="pro_15"),
                    H("Air",     key="air"),
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


@pytest.fixture
def col_roots():
    """Region > Territory > Quarter > Metric  (8 leaves)"""
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


# ---------------------------------------------------------------------------
# Initial state
# ---------------------------------------------------------------------------

class TestInitialState:

    def test_row_leaf_count(self, row_roots):
        assert len(all_leaves(row_roots)) == 8

    def test_col_leaf_count(self, col_roots):
        assert len(all_leaves(col_roots)) == 8

    def test_row_leaf_keys(self, row_roots):
        keys = [n.key for n in all_leaves(row_roots)]
        assert keys == ["pro_13", "pro_15", "air", "tab_std", "tab_plus",
                        "prod_basic", "prod_pro", "shield"]

    def test_col_leaf_keys(self, col_roots):
        keys = [n.key for n in all_leaves(col_roots)]
        assert keys == ["uk_rev", "uk_units", "de_rev", "de_units",
                        "jp_rev", "jp_units", "au_rev", "au_units"]

    def test_row_full_depth(self, row_roots):
        assert forest_full_depth(row_roots) == 4

    def test_col_full_depth(self, col_roots):
        assert forest_full_depth(col_roots) == 4

    def test_row_visible_depth_equals_full_initially(self, row_roots):
        assert forest_visible_depth(row_roots) == 4

    def test_initial_mergeable_rows(self, row_roots):
        # Only L3 nodes (whose children are all original leaves) are mergeable
        keys = {n.key for n in mergeable_nodes(row_roots)}
        assert keys == {"laptops", "tablets", "productivity", "security"}

    def test_initial_mergeable_cols(self, col_roots):
        keys = {n.key for n in mergeable_nodes(col_roots)}
        assert keys == {"uk", "germany", "japan", "australia"}

    def test_no_splittable_nodes_initially(self, row_roots, col_roots):
        assert splittable_nodes(row_roots) == []
        assert splittable_nodes(col_roots) == []

    def test_original_leaves_cannot_split(self, row_roots):
        pro_13 = find_node(row_roots, "pro_13")
        assert pro_13.is_original_leaf
        assert not pro_13.can_split

    def test_internal_nodes_not_leaves(self, row_roots):
        for key in ("division", "hardware", "software", "laptops", "tablets",
                    "productivity", "security"):
            node = find_node(row_roots, key)
            assert not node.is_leaf, f"{key} should not be a leaf initially"


# ---------------------------------------------------------------------------
# Merge — valid cases
# ---------------------------------------------------------------------------

class TestMerge:

    def test_merge_laptops_reduces_leaf_count(self, row_roots):
        laptops = find_node(row_roots, "laptops")
        laptops.merge()
        assert len(all_leaves(row_roots)) == 6  # 8 − 3 children + 1 merged node

    def test_merge_laptops_becomes_leaf(self, row_roots):
        laptops = find_node(row_roots, "laptops")
        laptops.merge()
        assert laptops.is_leaf
        assert laptops.merged

    def test_merge_laptops_leaf_order(self, row_roots):
        find_node(row_roots, "laptops").merge()
        keys = [n.key for n in all_leaves(row_roots)]
        assert keys == ["laptops", "tab_std", "tab_plus",
                        "prod_basic", "prod_pro", "shield"]

    def test_merge_single_child_node(self, row_roots):
        # Security has only one child (Shield) — still a valid merge.
        # Leaf count stays at 8: Shield (1 leaf) is replaced by Security (1 leaf).
        security = find_node(row_roots, "security")
        assert security.can_merge
        security.merge()
        assert security.is_leaf
        assert len(all_leaves(row_roots)) == 8
        assert "shield" not in [n.key for n in all_leaves(row_roots)]
        assert "security" in [n.key for n in all_leaves(row_roots)]

    def test_merge_unlocks_parent(self, row_roots):
        # Hardware can only be merged after both Laptops and Tablets are leaves
        hardware = find_node(row_roots, "hardware")
        assert not hardware.can_merge

        find_node(row_roots, "laptops").merge()
        assert not hardware.can_merge  # Tablets still internal

        find_node(row_roots, "tablets").merge()
        assert hardware.can_merge     # now both children are leaves

    def test_full_bottom_up_merge_sequence(self, row_roots):
        for key in ("laptops", "tablets"):
            find_node(row_roots, key).merge()
        find_node(row_roots, "hardware").merge()

        for key in ("productivity", "security"):
            find_node(row_roots, key).merge()
        find_node(row_roots, "software").merge()

        find_node(row_roots, "division").merge()

        assert len(all_leaves(row_roots)) == 1
        assert all_leaves(row_roots)[0].key == "division"

    def test_merge_col_territory(self, col_roots):
        find_node(col_roots, "uk").merge()
        keys = [n.key for n in all_leaves(col_roots)]
        assert "uk" in keys
        assert "uk_rev" not in keys
        assert "uk_units" not in keys
        assert len(keys) == 7


# ---------------------------------------------------------------------------
# Merge — invalid cases
# ---------------------------------------------------------------------------

class TestMergeInvalid:

    def test_cannot_merge_internal_node_with_internal_children(self, row_roots):
        hardware = find_node(row_roots, "hardware")
        assert not hardware.can_merge
        with pytest.raises(ValueError, match="not yet leaves"):
            hardware.merge()

    def test_cannot_merge_original_leaf(self, row_roots):
        pro_13 = find_node(row_roots, "pro_13")
        assert not pro_13.can_merge
        with pytest.raises(ValueError, match="already a leaf"):
            pro_13.merge()

    def test_cannot_merge_already_merged_node(self, row_roots):
        laptops = find_node(row_roots, "laptops")
        laptops.merge()
        assert not laptops.can_merge
        with pytest.raises(ValueError, match="already a leaf"):
            laptops.merge()

    def test_cannot_merge_root_with_internal_children(self, row_roots):
        division = find_node(row_roots, "division")
        assert not division.can_merge


# ---------------------------------------------------------------------------
# Split
# ---------------------------------------------------------------------------

class TestSplit:

    def test_split_restores_leaves(self, row_roots):
        laptops = find_node(row_roots, "laptops")
        laptops.merge()
        assert len(all_leaves(row_roots)) == 6

        laptops.split()
        assert len(all_leaves(row_roots)) == 8

    def test_split_restores_leaf_order(self, row_roots):
        find_node(row_roots, "laptops").merge()
        find_node(row_roots, "laptops").split()
        keys = [n.key for n in all_leaves(row_roots)]
        assert keys == ["pro_13", "pro_15", "air", "tab_std", "tab_plus",
                        "prod_basic", "prod_pro", "shield"]

    def test_split_makes_node_internal_again(self, row_roots):
        laptops = find_node(row_roots, "laptops")
        laptops.merge()
        laptops.split()
        assert not laptops.is_leaf
        assert not laptops.merged

    def test_split_mid_hierarchy(self, row_roots):
        # Merge Laptops → Tablets → Hardware, then split Hardware
        for key in ("laptops", "tablets"):
            find_node(row_roots, key).merge()
        find_node(row_roots, "hardware").merge()

        assert len(all_leaves(row_roots)) == 4  # hardware, prod_basic, prod_pro, shield

        find_node(row_roots, "hardware").split()
        # Hardware reverts to internal; Laptops and Tablets are still merged leaves.
        # 5 leaves: laptops(merged), tablets(merged), prod_basic, prod_pro, shield
        assert len(all_leaves(row_roots)) == 5
        keys = [n.key for n in all_leaves(row_roots)]
        assert keys == ["laptops", "tablets", "prod_basic", "prod_pro", "shield"]

    def test_split_then_merge_again(self, row_roots):
        laptops = find_node(row_roots, "laptops")
        laptops.merge()
        laptops.split()
        laptops.merge()
        assert laptops.is_leaf


# ---------------------------------------------------------------------------
# Relabel
# ---------------------------------------------------------------------------

class TestRelabel:

    def test_relabel_leaf(self, row_roots):
        pro_13 = find_node(row_roots, "pro_13")
        pro_13.relabel("Pro 13-inch")
        assert pro_13.label == "Pro 13-inch"

    def test_relabel_internal_node(self, row_roots):
        hardware = find_node(row_roots, "hardware")
        hardware.relabel("Physical Products")
        assert hardware.label == "Physical Products"

    def test_relabel_merged_node(self, row_roots):
        laptops = find_node(row_roots, "laptops")
        laptops.merge()
        laptops.relabel("All Laptops")
        assert laptops.label == "All Laptops"

    def test_relabel_does_not_change_key(self, row_roots):
        laptops = find_node(row_roots, "laptops")
        laptops.relabel("All Laptops")
        assert laptops.key == "laptops"
        assert find_node(row_roots, "laptops") is laptops

    def test_relabel_appears_in_serialisation(self, row_roots):
        find_node(row_roots, "laptops").relabel("All Laptops")
        data = row_roots[0].to_dict()
        hardware = data["children"][0]
        laptops = hardware["children"][0]
        assert laptops["label"] == "All Laptops"

    def test_relabel_empty_string_raises(self, row_roots):
        with pytest.raises(ValueError, match="must not be empty"):
            find_node(row_roots, "pro_13").relabel("")

    def test_relabel_whitespace_only_raises(self, row_roots):
        with pytest.raises(ValueError, match="must not be empty"):
            find_node(row_roots, "pro_13").relabel("   ")

    def test_relabel_survives_round_trip(self, row_roots):
        find_node(row_roots, "laptops").relabel("All Laptops")
        restored = deserialize_forest(serialize_forest(row_roots))
        assert find_node(restored, "laptops").label == "All Laptops"


# ---------------------------------------------------------------------------
# Split — invalid cases
# ---------------------------------------------------------------------------

class TestSplitInvalid:

    def test_cannot_split_original_leaf(self, row_roots):
        pro_13 = find_node(row_roots, "pro_13")
        assert not pro_13.can_split
        with pytest.raises(ValueError, match="original leaf"):
            pro_13.split()

    def test_cannot_split_internal_node(self, row_roots):
        hardware = find_node(row_roots, "hardware")
        assert not hardware.can_split
        with pytest.raises(ValueError, match="not currently merged"):
            hardware.split()


# ---------------------------------------------------------------------------
# Visible depth after operations
# ---------------------------------------------------------------------------

class TestVisibleDepth:

    def test_depth_unchanged_after_leaf_merge(self, row_roots):
        # Merging Laptops removes L4 nodes, but Tablets still reaches L4
        find_node(row_roots, "laptops").merge()
        assert forest_visible_depth(row_roots) == 4

    def test_depth_reduces_when_all_l3_merged(self, row_roots):
        for key in ("laptops", "tablets", "productivity", "security"):
            find_node(row_roots, key).merge()
        # Deepest visible path is now Division > Hardware/Software (depth 3... wait)
        # Actually: Division(1) > Hardware(2) > Laptops(3, leaf) — depth 3
        assert forest_visible_depth(row_roots) == 3

    def test_full_merge_gives_depth_one(self, row_roots):
        for key in ("laptops", "tablets"):
            find_node(row_roots, key).merge()
        find_node(row_roots, "hardware").merge()
        for key in ("productivity", "security"):
            find_node(row_roots, key).merge()
        find_node(row_roots, "software").merge()
        find_node(row_roots, "division").merge()
        assert forest_visible_depth(row_roots) == 1

    def test_full_depth_never_changes(self, row_roots):
        # Merge everything; full depth still reflects original structure
        for key in ("laptops", "tablets"):
            find_node(row_roots, key).merge()
        find_node(row_roots, "hardware").merge()
        assert forest_full_depth(row_roots) == 4


# ---------------------------------------------------------------------------
# Serialisation round-trip
# ---------------------------------------------------------------------------

class TestSerialisation:

    def test_round_trip_preserves_structure(self, row_roots):
        restored = deserialize_forest(serialize_forest(row_roots))
        assert [n.key for n in all_leaves(restored)] == \
               [n.key for n in all_leaves(row_roots)]

    def test_round_trip_preserves_merged_state(self, row_roots):
        find_node(row_roots, "laptops").merge()
        restored = deserialize_forest(serialize_forest(row_roots))
        laptops = find_node(restored, "laptops")
        assert laptops.merged
        assert laptops.is_leaf
        assert len(all_leaves(restored)) == 6

    def test_to_dict_includes_can_merge_flag(self, row_roots):
        data = row_roots[0].to_dict()
        # Division itself cannot merge (children are internal)
        assert data["canMerge"] is False
        # Laptops can merge — find it in the nested dict
        hardware = data["children"][0]
        laptops = hardware["children"][0]
        assert laptops["canMerge"] is True

    def test_to_dict_always_includes_children(self, row_roots):
        # Even after merge, children are serialised (JS needs them for split)
        find_node(row_roots, "laptops").merge()
        data = row_roots[0].to_dict()
        hardware = data["children"][0]
        laptops = hardware["children"][0]
        assert laptops["merged"] is True
        assert len(laptops["children"]) == 3  # Pro 13, Pro 15, Air still present
