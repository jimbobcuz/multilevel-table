"""
Header tree model for the multilevel table widget.

Hierarchy rules
---------------
- A node is a **leaf** if it was defined with no children (original leaf)
  OR if it has been merged (children hidden).
- A node **can be merged** if it is currently internal and every one of its
  direct children is currently a leaf.  Merges therefore proceed bottom-up.
- A node **can be split** only if it was previously merged (not an original
  leaf — those have nothing to restore).
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from typing import Iterator


# ---------------------------------------------------------------------------
# Core node
# ---------------------------------------------------------------------------

@dataclass
class HeaderNode:
    key: str
    label: str
    children: list[HeaderNode] = field(default_factory=list)
    merged: bool = False

    # --- State ---

    @property
    def is_leaf(self) -> bool:
        """Leaf when originally childless or currently merged."""
        return self.merged or not self.children

    @property
    def is_original_leaf(self) -> bool:
        """True if the node was defined without children at creation."""
        return not self.children

    @property
    def can_merge(self) -> bool:
        """
        True when every direct child is currently a leaf.
        (An original leaf and already-merged nodes both satisfy this.)
        """
        return not self.is_leaf and all(c.is_leaf for c in self.children)

    @property
    def can_split(self) -> bool:
        """Only nodes that were explicitly merged can be split."""
        return self.merged  # original leaves have nothing to restore

    # --- Mutations ---

    def merge(self) -> None:
        """Collapse all direct children; this node becomes a leaf."""
        if not self.can_merge:
            if self.is_leaf:
                reason = "already a leaf"
            else:
                non_leaves = [c.key for c in self.children if not c.is_leaf]
                reason = f"children that are not yet leaves: {non_leaves}"
            raise ValueError(f"Cannot merge '{self.key}': {reason}")
        self.merged = True

    def split(self) -> None:
        """Re-expose direct children; this node becomes internal again."""
        if not self.can_split:
            raise ValueError(
                f"Cannot split '{self.key}': "
                + ("original leaf — no children to restore"
                   if self.is_original_leaf else "not currently merged")
            )
        self.merged = False

    def relabel(self, new_label: str) -> None:
        """
        Change the display label of this node.

        Valid on any node at any time — no tree-state constraints.
        The key is unaffected; it remains the stable identifier used by
        JavaScript and the rest of the Python model.
        """
        if not new_label.strip():
            raise ValueError(f"Cannot relabel '{self.key}': label must not be empty")
        self.label = new_label

    # --- Traversal ---

    def leaves(self) -> Iterator[HeaderNode]:
        """Yield current leaf nodes in display order."""
        if self.is_leaf:
            yield self
        else:
            for child in self.children:
                yield from child.leaves()

    def all_nodes(self) -> Iterator[HeaderNode]:
        """Yield every node in the full subtree, ignoring merged state."""
        yield self
        for child in self.children:
            yield from child.all_nodes()

    def find(self, key: str) -> HeaderNode | None:
        """Return the first node matching *key* in this subtree, or None."""
        for node in self.all_nodes():
            if node.key == key:
                return node
        return None

    # --- Metrics ---

    def leaf_count(self) -> int:
        return sum(1 for _ in self.leaves())

    def visible_depth(self) -> int:
        """
        Depth of the *currently visible* tree.
        A merged or original leaf has depth 1.
        """
        if self.is_leaf:
            return 1
        return 1 + max(c.visible_depth() for c in self.children)

    def full_depth(self) -> int:
        """Depth of the complete tree, ignoring merged state."""
        if not self.children:
            return 1
        return 1 + max(c.full_depth() for c in self.children)

    # --- Serialisation ---

    def to_dict(self) -> dict:
        """
        Serialise for JS transport.
        Children are always included (the JS needs them to handle splits),
        but the JS must respect `merged` when deciding what to render.
        """
        return {
            "key": self.key,
            "label": self.label,
            "merged": self.merged,
            "isLeaf": self.is_leaf,
            "canMerge": self.can_merge,
            "canSplit": self.can_split,
            "children": [c.to_dict() for c in self.children],
        }

    @classmethod
    def from_dict(cls, data: dict) -> HeaderNode:
        return cls(
            key=data["key"],
            label=data["label"],
            merged=data.get("merged", False),
            children=[cls.from_dict(c) for c in data.get("children", [])],
        )

    def __repr__(self) -> str:
        state = " [merged]" if self.merged else (" [leaf]" if self.is_original_leaf else "")
        return f"HeaderNode({self.key!r}{state}, children={len(self.children)})"


# ---------------------------------------------------------------------------
# Builder shorthand
# ---------------------------------------------------------------------------

def H(
    label: str,
    children: list[HeaderNode] | None = None,
    *,
    key: str | None = None,
) -> HeaderNode:
    """
    Fluent HeaderNode constructor.

    Usage::

        H("Hardware", [
            H("Laptops", [H("Pro 13in", key="pro_13"), H("Air", key="air")],
              key="laptops"),
        ], key="hardware")

    Keys default to a label-derived slug + short UUID suffix to guarantee
    uniqueness across siblings with identical labels (e.g. two "Q1" nodes).
    Supply an explicit *key* wherever stable, human-readable identifiers matter
    (tests, serialisation round-trips, etc.).
    """
    return HeaderNode(
        key=key if key is not None else _make_key(label),
        label=label,
        children=children or [],
    )


def _make_key(label: str) -> str:
    slug = re.sub(r"[^\w]+", "_", label.lower()).strip("_")
    return f"{slug}_{uuid.uuid4().hex[:4]}"


# ---------------------------------------------------------------------------
# Forest utilities  (a "forest" is a list[HeaderNode] of root nodes)
# ---------------------------------------------------------------------------

def find_node(roots: list[HeaderNode], key: str) -> HeaderNode | None:
    """Search across all roots for *key*."""
    for root in roots:
        result = root.find(key)
        if result is not None:
            return result
    return None


def all_leaves(roots: list[HeaderNode]) -> list[HeaderNode]:
    """Ordered list of current leaves across the forest."""
    return [leaf for root in roots for leaf in root.leaves()]


def leaf_key_paths(roots: list[HeaderNode]) -> list[list[str]]:
    """
    Root-to-leaf key path for each current leaf, in display order.

    For the initial column tree this yields e.g.::

        ["region", "emea", "uk", "uk_rev"]
        ["region", "emea", "uk", "uk_units"]
        ...

    After merging UK, its path stops at the merged node::

        ["region", "emea", "uk"]

    The widget hands these paths to the user's calculate callback, so the
    callback always sees the current structure — a merged leaf is identified
    by the path ending at the merged node.
    """
    paths: list[list[str]] = []

    def walk(node: HeaderNode, prefix: list[str]) -> None:
        path = prefix + [node.key]
        if node.is_leaf:
            paths.append(path)
        else:
            for child in node.children:
                walk(child, path)

    for root in roots:
        walk(root, [])
    return paths


def mergeable_nodes(roots: list[HeaderNode]) -> list[HeaderNode]:
    """All nodes that are currently valid merge targets."""
    return [n for root in roots for n in root.all_nodes() if n.can_merge]


def splittable_nodes(roots: list[HeaderNode]) -> list[HeaderNode]:
    """All nodes that are currently valid split targets."""
    return [n for root in roots for n in root.all_nodes() if n.can_split]


def forest_visible_depth(roots: list[HeaderNode]) -> int:
    """
    Maximum visible depth across all roots.
    This determines how many header rows (or columns) the rendered table needs.
    """
    return max((r.visible_depth() for r in roots), default=0)


def forest_full_depth(roots: list[HeaderNode]) -> int:
    """Maximum full depth — useful for pre-allocating render space."""
    return max((r.full_depth() for r in roots), default=0)


def serialize_forest(roots: list[HeaderNode]) -> list[dict]:
    return [r.to_dict() for r in roots]


def deserialize_forest(data: list[dict]) -> list[HeaderNode]:
    return [HeaderNode.from_dict(d) for d in data]
