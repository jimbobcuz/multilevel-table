# Header Model — Design & Implementation Notes

This document explains the data model behind the multilevel table widget's
header system. It covers the core concepts, the rules that govern merge and
split operations, and the key behaviours confirmed by the test suite.

---

## What problem does this solve?

A multilevel table has headers that form a tree rather than a flat list.
The user can **merge** a node (collapsing its children into it, making it a
leaf) or **split** it back out. After any such change the table's content is
recalculated for the new leaf structure.

This module models that tree and enforces the rules about what operations
are valid at any point in time.

---

## The development example hierarchy

All tests and examples use this fixed hierarchy so edge cases stay concrete.

### Rows — Division › Category › Product › Variant (8 leaves)

```
Division
├── Hardware
│   ├── Laptops
│   │   ├── Pro 13in   ← leaf
│   │   ├── Pro 15in   ← leaf
│   │   └── Air        ← leaf
│   └── Tablets
│       ├── Standard   ← leaf
│       └── Plus       ← leaf
└── Software
    ├── Productivity
    │   ├── Basic      ← leaf
    │   └── Pro        ← leaf
    └── Security
        └── Shield     ← leaf   (sole child — valid but count-neutral merge)
```

### Columns — Region › Territory › Country › Metric (8 leaves)

```
Region
├── EMEA
│   ├── UK
│   │   ├── Revenue    ← leaf
│   │   └── Units      ← leaf
│   └── Germany
│       ├── Revenue    ← leaf
│       └── Units      ← leaf
└── APAC
    ├── Japan
    │   ├── Revenue    ← leaf
    │   └── Units      ← leaf
    └── Australia
        ├── Revenue    ← leaf
        └── Units      ← leaf
```

The initial data grid is **8 × 8 = 64 calculated cells**.

---

## HeaderNode

Every node in the tree — whether a root, an internal group, or a leaf — is
a `HeaderNode`.

```python
@dataclass
class HeaderNode:
    key:      str              # stable unique identifier
    label:    str              # display text
    children: list[HeaderNode] # always stored, even when merged
    merged:   bool             # True when this node has been collapsed
```

### The `children` list is never cleared

This is the central design decision. When a node is merged its children are
**not removed** — `merged` is simply set to `True`. This means a split can
always restore the exact previous state without any extra bookkeeping.

---

## Leaf vs internal

A node is a **leaf** when either condition holds:

| Condition | Meaning |
|---|---|
| `children == []` | Original leaf — was defined without children |
| `merged == True` | Merged leaf — children exist but are hidden |

```python
@property
def is_leaf(self) -> bool:
    return self.merged or not self.children
```

An **original leaf** (`children == []`) can never be split because there is
nothing to restore. This is enforced by `can_split`.

---

## Merge rules

A node **can be merged** when:
- It is currently internal (not a leaf), AND
- Every one of its direct children is currently a leaf.

This enforces a strict **bottom-up** order. You cannot merge Hardware until
both Laptops and Tablets have been merged first.

```
Laptops.can_merge  → True   (Pro 13, Pro 15, Air are original leaves)
Hardware.can_merge → False  (Laptops and Tablets are still internal)

# After merging Laptops and Tablets:
Hardware.can_merge → True
```

### What merge does to the leaf count

Merging a node with *n* leaf children replaces those *n* leaves with 1 (the
node itself). The count changes by `1 - n`.

| Children before merge | Leaf count change |
|---|---|
| 1 (e.g. Security → Shield) | 0  (count-neutral) |
| 2 (e.g. Tablets) | −1 |
| 3 (e.g. Laptops) | −2 |

Content is always recalculated after a merge, even when the leaf count
does not change, because the node identity at that position has changed.

---

## Split rules

A node **can be split** when `merged == True`. Original leaves (`merged ==
False`, `children == []`) cannot be split.

Split is the exact inverse of merge: `merged` is set back to `False` and the
previously hidden children re-appear in their current state.

### Splitting mid-hierarchy exposes children as-is

If Laptops and Tablets were both merged before Hardware was merged, then
splitting Hardware re-exposes two merged leaves — not the original four
variant leaves. The tree remembers each node's state independently.

```
After: merge(Laptops), merge(Tablets), merge(Hardware)
Leaves: [Hardware, prod_basic, prod_pro, shield]  — 4 leaves

After: split(Hardware)
Leaves: [Laptops, Tablets, prod_basic, prod_pro, shield]  — 5 leaves
         ↑ still merged    ↑ still merged
```

This is intentional. The user can then split Laptops and Tablets
individually if they want to go deeper.

---

## Forest utilities

A **forest** is a `list[HeaderNode]` — the top-level roots of the header
axis. Most real tables have a single root, but the model supports multiple.

| Function | Returns |
|---|---|
| `all_leaves(roots)` | Ordered list of current leaf nodes |
| `find_node(roots, key)` | First node matching key, or None |
| `mergeable_nodes(roots)` | All nodes where `can_merge` is True |
| `splittable_nodes(roots)` | All nodes where `can_split` is True |
| `forest_visible_depth(roots)` | Max depth of the current visible tree |
| `forest_full_depth(roots)` | Max depth ignoring merged state |

`forest_visible_depth` is important for rendering: it determines how many
header rows (or columns) the `<table>` needs to allocate.

---

## Visible depth after operations

Depth is measured from root to the deepest current leaf.

```
Initial:                               depth = 4
After merging Laptops only:            depth = 4  (Tablets still reaches L4)
After merging all L3 nodes:            depth = 3  (Hardware → Laptops is now L3 leaf)
After merging all L2 and L3 nodes:     depth = 2
After merging everything:              depth = 1
```

`forest_full_depth` never changes — it always reflects the original
structure and is used to pre-allocate rendering space.

---

## Serialisation

`to_dict()` produces a plain dict for sending to JavaScript. Key points:

- Children are **always included**, even when `merged == True`. The JS layer
  needs them to know what to render when the user triggers a split.
- `isLeaf`, `canMerge`, and `canSplit` are pre-computed and included so the
  JS does not need to re-derive them.
- `from_dict()` / `deserialize_forest()` restore the full tree including
  merged state, ready for further operations on the Python side.

```python
{
  "key": "laptops",
  "label": "Laptops",
  "merged": true,
  "isLeaf": true,
  "canMerge": false,
  "canSplit": true,
  "children": [          # ← always present, JS respects `merged` flag
    {"key": "pro_13", ...},
    {"key": "pro_15", ...},
    {"key": "air",    ...}
  ]
}
```

---

## The H() builder

`H` is a shorthand for constructing `HeaderNode` instances cleanly:

```python
H("Laptops", [
    H("Pro 13in", key="pro_13"),
    H("Pro 15in", key="pro_15"),
    H("Air",      key="air"),
], key="laptops")
```

If no `key` is provided, one is auto-generated from the label plus a short
random suffix (e.g. `laptops_3a9f`). This guarantees uniqueness even when
sibling nodes share the same label (two nodes both labelled "Q1" under
different parents will get different keys).

For tests and any context where key stability matters, always supply an
explicit `key`.

---

## What comes next

The header model is complete and fully tested. The next layer to build is
**span computation** — the algorithm that walks the current visible tree and
produces the `colspan` / `rowspan` values needed to render each `<th>` cell
in the HTML table.

After that: the anywidget Python class (traitlets, operation handling) and
the JavaScript ESM frontend (rendering + click interactions).
