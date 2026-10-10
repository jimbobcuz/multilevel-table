# header.py — Code Walkthrough

A plain-language explanation of every part of the file, top to bottom.

---

## Imports

```python
from __future__ import annotations
```

Allows a class to reference itself in type hints (e.g. `list[HeaderNode]`
inside the `HeaderNode` class) without Python complaining that the class
isn't defined yet.

```python
import re
import uuid
from dataclasses import dataclass, field
from typing import Iterator
```

`re` — regular expressions, used in the key-generator to strip punctuation
from labels.

`uuid` — generates random unique IDs, also used in the key-generator.

`dataclass` / `field` — Python's built-in way to define a data-holding
class without writing a lot of boilerplate. `field(default_factory=list)`
means "default value is a fresh empty list" — if we just wrote `= []` we'd
get one shared list between all instances, which is a classic Python trap.

`Iterator` — a type hint meaning "something you can loop over with `for`",
used as the return type of the generator methods.

---

## HeaderNode — the dataclass

```python
@dataclass
class HeaderNode:
    key:      str
    label:    str
    children: list[HeaderNode] = field(default_factory=list)
    merged:   bool = False
```

The `@dataclass` decorator auto-generates `__init__`, `__eq__`, and a few
other methods from these four field declarations, saving a lot of boilerplate.

**`key`** — a stable unique identifier used to find and reference this node
from JavaScript and from tests. Never changes after creation.

**`label`** — the human-readable display text shown in the table header.

**`children`** — the node's child nodes. Crucially, this list is **never
cleared**, even when the node is merged. Merge just hides the children; they
remain here so a split can restore them exactly.

**`merged`** — the single boolean that controls whether the node is
currently acting as a leaf. `False` by default.

---

## Properties — computed state

Properties in Python look like method calls but are accessed as plain
attributes (no parentheses). They recompute their value each time they are
read.

### `is_leaf`

```python
@property
def is_leaf(self) -> bool:
    return self.merged or not self.children
```

A node is a leaf in two situations: it was merged (`self.merged` is True),
or it was defined with no children (`not self.children`). The `or` means
either condition is sufficient.

### `is_original_leaf`

```python
@property
def is_original_leaf(self) -> bool:
    return not self.children
```

Only True when the children list is empty — i.e. the node was always a
leaf, never had children to merge. This distinguishes "was merged" from
"was always a leaf", which matters for deciding whether split is allowed.

### `can_merge`

```python
@property
def can_merge(self) -> bool:
    return not self.is_leaf and all(c.is_leaf for c in self.children)
```

Two conditions must both be true:

`not self.is_leaf` — the node must currently be internal (it can't already
be a leaf).

`all(c.is_leaf for c in self.children)` — every direct child must currently
be a leaf. `all()` returns True if the condition holds for every item; it
short-circuits and returns False as soon as it finds one that doesn't.
This is what enforces the bottom-up merge order.

### `can_split`

```python
@property
def can_split(self) -> bool:
    return self.merged
```

Only nodes where `merged` is True can be split. Original leaves have
`merged == False` and empty children, so they correctly return False — there
is nothing to restore.

---

## Mutations — methods that change state

### `merge()`

```python
def merge(self) -> None:
    if not self.can_merge:
        if self.is_leaf:
            reason = "already a leaf"
        else:
            non_leaves = [c.key for c in self.children if not c.is_leaf]
            reason = f"children that are not yet leaves: {non_leaves}"
        raise ValueError(f"Cannot merge '{self.key}': {reason}")
    self.merged = True
```

Checks validity first; raises a descriptive `ValueError` if the merge is
not allowed. The error message tells you exactly which children are blocking
the merge (useful for debugging). If valid, the only thing that actually
changes is setting `self.merged = True`. That single flag flip is all it
takes — `is_leaf` immediately returns True on the next read.

### `split()`

```python
def split(self) -> None:
    if not self.can_split:
        raise ValueError(
            f"Cannot split '{self.key}': "
            + ("original leaf — no children to restore"
               if self.is_original_leaf else "not currently merged")
        )
    self.merged = False
```

Mirror of `merge()`. Sets `merged = False`, which is the only change
needed. Because `children` was never cleared, the children just reappear
in whatever state they were last in.

---

## Traversal — methods that walk the tree

These are **generator methods**, using Python's `yield` and `yield from`.
A generator is lazy — it produces values one at a time as the caller
iterates, rather than building a full list up front.

### `leaves()`

```python
def leaves(self) -> Iterator[HeaderNode]:
    if self.is_leaf:
        yield self
    else:
        for child in self.children:
            yield from child.leaves()
```

Recursive tree walk. If this node is a leaf, yield itself and stop — don't
descend into children (even if children exist but are hidden by `merged`).
If it's internal, hand off to each child's `leaves()` in turn.

`yield from` is shorthand for "yield everything that the right-hand
generator produces". Without it you'd write a nested for loop.

The result is a depth-first, left-to-right ordering — which matches the
left-to-right display order in the rendered table.

### `all_nodes()`

```python
def all_nodes(self) -> Iterator[HeaderNode]:
    yield self
    for child in self.children:
        yield from child.all_nodes()
```

Similar structure but ignores `merged` completely — it visits every node in
the full stored tree. Used by `find()` (you want to be able to locate a
merged node by key) and by the forest utilities that check `can_merge` and
`can_split` across the whole tree.

### `find()`

```python
def find(self, key: str) -> HeaderNode | None:
    for node in self.all_nodes():
        if node.key == key:
            return node
    return None
```

Linear scan using `all_nodes()`. Returns the first match or None. Simple
and correct; performance is not a concern at the scale of a table header
(tens of nodes at most).

---

## Metrics

### `leaf_count()`

```python
def leaf_count(self) -> int:
    return sum(1 for _ in self.leaves())
```

Counts leaves by summing 1 for each item the `leaves()` generator yields.

### `visible_depth()`

```python
def visible_depth(self) -> int:
    if self.is_leaf:
        return 1
    return 1 + max(c.visible_depth() for c in self.children)
```

Recursive. A leaf is depth 1. An internal node is 1 plus the deepest child.
`max()` with a generator expression picks the deepest branch.

Because merged nodes report `is_leaf == True`, they stop the recursion and
count as depth 1, which is correct — they occupy a single header row even
though they have hidden children.

### `full_depth()`

```python
def full_depth(self) -> int:
    if not self.children:
        return 1
    return 1 + max(c.full_depth() for c in self.children)
```

Same logic but checks `not self.children` (the raw structural fact) instead
of `is_leaf` (which is affected by `merged`). This always reflects the
original tree depth regardless of any merges that have happened.

---

## Serialisation

### `to_dict()`

```python
def to_dict(self) -> dict:
    return {
        "key": self.key,
        "label": self.label,
        "merged": self.merged,
        "isLeaf": self.is_leaf,
        "canMerge": self.can_merge,
        "canSplit": self.can_split,
        "children": [c.to_dict() for c in self.children],
    }
```

Converts the node to a plain Python dict for sending to JavaScript via
anywidget's traitlet system.

Note that `children` is always included — even when `merged` is True. The
JS needs the full tree in order to know what to restore on a split. The JS
is responsible for not rendering the children of merged nodes.

`isLeaf`, `canMerge`, and `canSplit` are pre-computed here so the JS
doesn't have to re-derive them. The camelCase names match JavaScript
conventions.

`[c.to_dict() for c in self.children]` is a **list comprehension** —
compact Python for "call `to_dict()` on every child and collect the results
into a list". This recurses down the full tree.

### `from_dict()`

```python
@classmethod
def from_dict(cls, data: dict) -> HeaderNode:
    return cls(
        key=data["key"],
        label=data["label"],
        merged=data.get("merged", False),
        children=[cls.from_dict(c) for c in data.get("children", [])],
    )
```

`@classmethod` means this method belongs to the class rather than an
instance — you call it as `HeaderNode.from_dict(data)`. `cls` refers to the
class itself, so `cls(...)` is the same as `HeaderNode(...)`.

`data.get("merged", False)` reads the key if it exists, defaulting to
False if it doesn't — safer than `data["merged"]` when deserialising data
that might be missing optional fields.

The list comprehension on `children` recurses, rebuilding the full nested
tree from nested dicts.

### `__repr__()`

```python
def __repr__(self) -> str:
    state = " [merged]" if self.merged else (" [leaf]" if self.is_original_leaf else "")
    return f"HeaderNode({self.key!r}{state}, children={len(self.children)})"
```

Controls how the node appears in the Python REPL and in test failure output.
The `!r` format spec wraps the key in quotes. The state suffix makes it
immediately obvious whether you're looking at a merged node, an original
leaf, or an internal node.

---

## H() — the builder shorthand

```python
def H(
    label: str,
    children: list[HeaderNode] | None = None,
    *,
    key: str | None = None,
) -> HeaderNode:
```

The `*` in the parameter list makes `key` a **keyword-only argument** —
it must be passed as `key="laptops"`, never positionally. This prevents
accidentally passing a key as the second argument when you meant to pass
children.

`children or []` converts `None` to an empty list. This lets callers omit
the children argument for leaf nodes rather than writing `H("Air", [])`.

### `_make_key()`

```python
def _make_key(label: str) -> str:
    slug = re.sub(r"[^\w]+", "_", label.lower()).strip("_")
    return f"{slug}_{uuid.uuid4().hex[:4]}"
```

The leading underscore is a Python convention for "private — not part of
the public API".

`re.sub(r"[^\w]+", "_", label.lower())` replaces any run of
non-word characters (spaces, hyphens, quotes, etc.) with a single
underscore, after lower-casing. `"Pro 13in"` becomes `"pro_13in"`.

`.strip("_")` removes any leading or trailing underscores that result from
punctuation at the edges.

`uuid.uuid4().hex[:4]` generates a random 4-character hex suffix
(e.g. `"3a9f"`). This guarantees uniqueness even when two siblings share
the same label — both "Q1" nodes will get different suffixes.

---

## Forest utilities

A **forest** is simply a `list[HeaderNode]`. Most tables will have one root
node, but the model supports multiple. All the forest functions are thin
wrappers that apply a node-level operation across every root.

### `find_node()`

```python
def find_node(roots: list[HeaderNode], key: str) -> HeaderNode | None:
    for root in roots:
        result = root.find(key)
        if result is not None:
            return result
    return None
```

Searches each root in turn and returns the first match. The `is not None`
check is intentional — a node with a falsy key (unlikely but possible)
would be skipped by a plain `if result:` check.

### `all_leaves()`

```python
def all_leaves(roots: list[HeaderNode]) -> list[HeaderNode]:
    return [leaf for root in roots for leaf in root.leaves()]
```

A nested list comprehension: for each root, for each leaf in that root,
collect it. Equivalent to a nested for loop but more concise.

### `mergeable_nodes()` and `splittable_nodes()`

```python
def mergeable_nodes(roots: list[HeaderNode]) -> list[HeaderNode]:
    return [n for root in roots for n in root.all_nodes() if n.can_merge]
```

Same nested comprehension pattern, with an `if` filter on the end. These
are what the widget will call to decide which nodes to offer as interactive
merge/split targets in the UI.

### `forest_visible_depth()` and `forest_full_depth()`

```python
def forest_visible_depth(roots: list[HeaderNode]) -> int:
    return max((r.visible_depth() for r in roots), default=0)
```

`max()` with `default=0` handles the edge case of an empty roots list
without raising an error. The renderer uses visible depth to know how many
header rows to draw.

---

## `relabel()` — added after initial build

```python
def relabel(self, new_label: str) -> None:
    if not new_label.strip():
        raise ValueError(f"Cannot relabel '{self.key}': label must not be empty")
    self.label = new_label
```

Unlike `merge()` and `split()`, relabelling has no tree-state constraints
— it is valid on any node at any time, whether it is a leaf, internal, or
merged. The only guard is against an empty or whitespace-only string, which
would produce a blank header cell in the rendered table.

The `key` is deliberately left alone. The key is the stable identifier that
JavaScript, tests, and the rest of the Python model use to reference a node.
Changing the label is a display concern only.

### How label changes reach JavaScript

This is the important architectural point. anywidget only watches
**traitlets** for changes, not individual Python object attributes. So
calling `node.relabel("New Name")` changes the Python object immediately,
but JavaScript will not know about it until the widget layer (not yet built)
re-serialises the forest and writes the result back to the traitlet.

The reason all mutations go through methods (`merge`, `split`, `relabel`)
rather than direct attribute assignment is precisely to give the widget
layer a clean place to hook that re-serialisation — either by wrapping the
method calls or by having the widget check for changes after each user
interaction.

Direct assignment (`node.label = "New Name"`) would work on the Python
object but would silently bypass the JavaScript update. Treating the methods
as the only public mutation interface keeps that from being a hidden trap.
