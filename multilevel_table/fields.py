"""
Field-based hierarchy construction (the model behind a pivot-style
drag-and-drop field selector).

A `Field` is a dimension with a name and a list of members. `build_forest`
takes an ordered list of fields and produces the cross-product header forest:
the first field's members are the top-level nodes, the next field's members
nest under each, and so on. Each field may start collapsed (`start_merged`),
producing nodes that are pre-merged but still splittable.

This is a convenience layer over the explicit HeaderNode trees. It generates
*regular* cross-product hierarchies — every parent at a given level has the
same child members. Irregular hierarchies (different members under different
parents, like the hand-built dev example) still need explicit H() trees.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .header import HeaderNode


@dataclass
class Field:
    name: str                 # dimension name, e.g. "Region" (shown as an axis caption)
    members: list[str]        # member labels, e.g. ["EMEA", "APAC"]
    key: str | None = None    # stable key prefix; defaults to a slug of name
    start_merged: bool = False  # nodes at this level start collapsed (but splittable)

    def resolved_key(self) -> str:
        return self.key or _slug(self.name)


def _slug(s: str) -> str:
    return re.sub(r"[^\w]+", "_", s.lower()).strip("_")


def build_forest(fields: list[Field]) -> list[HeaderNode]:
    """
    Build a cross-product header forest from an ordered list of fields.

    Example::

        build_forest([
            Field("Region", ["EMEA", "APAC"]),
            Field("Metric", ["Revenue", "Units"]),
        ])

    yields two roots (EMEA, APAC), each with two children (Revenue, Units) —
    four leaves total.

    `start_merged` only takes effect on fields that have a level beneath them
    (a deepest-level field has nothing to merge, so the flag is ignored there).
    """
    if not fields:
        return []

    field_keys = [f.resolved_key() for f in fields]

    def build(level: int, parent_key: str) -> list[HeaderNode]:
        f = fields[level]
        fkey = field_keys[level]
        nodes: list[HeaderNode] = []
        for member in f.members:
            mslug = _slug(member)
            key = f"{parent_key}.{fkey}_{mslug}" if parent_key else f"{fkey}_{mslug}"
            has_deeper = level + 1 < len(fields)
            children = build(level + 1, key) if has_deeper else []
            nodes.append(HeaderNode(
                key=key,
                label=member,
                children=children,
                merged=f.start_merged and has_deeper,
            ))
        return nodes

    return build(0, "")


def field_captions(fields: list[Field]) -> list[str]:
    """The ordered field names, for display as axis captions (pivot-style)."""
    return [f.name for f in fields]
