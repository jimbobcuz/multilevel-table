# Design notes: grid rendering, uniform cells, SVG content, field selector

Notes on the four new requirements, what I prototyped, and the trade-offs. There
are three runnable prototypes in your outputs alongside this doc:

- `multilevel_table_grid_demo.html` — the CSS-Grid renderer with uniform cells
  and SVG content (merge/split works; headers are sticky).
- `multilevel_table_field_selector_demo.html` — drag-and-drop field zones wired
  to the grid renderer; rebuilds live.
- `multilevel_table_demo.html` — the original `<table>` renderer, for comparison.

And a new Python module, `multilevel_table/fields.py` (14 tests), which builds
the cross-product hierarchy a field selector produces.

---

## 1. DIVs in a CSS Grid vs. an HTML `<table>`

**Recommendation: switch to CSS Grid.** Your three other requirements
(uniform sizing, SVG-filled cells, and to a lesser extent the selector) all push
the same direction, and the prototype confirms it works cleanly.

### Why Grid fits these requirements better

**Uniform sizing is native.** In Grid you declare the track sizes once:

```css
grid-template-columns: repeat(<rowDepth>, auto) repeat(<colLeaves>, var(--cell));
grid-template-rows:    repeat(<colDepth>, auto) repeat(<rowLeaves>, var(--cell));
```

The row-header columns are content-sized (`auto`); every data column is exactly
`var(--cell)`. Same for rows. Uniformity is guaranteed by construction. In a
`<table>`, cell sizes are content-driven; forcing exact equal heights *and*
widths means `table-layout: fixed` plus fighting the row-height algorithm, and
it's still fragile.

**SVG filling is clean.** A Grid data cell has a *definite* size (the track is a
fixed length), so an SVG child with `width:100%; height:100%` fills it reliably.
In a `<table>`, percentage heights inside `<td>` are famously unreliable across
browsers — you end up with absolute-positioning hacks. The prototype drops an
SVG straight into each cell div and it fills perfectly.

**The span maths transfer unchanged.** This is the key reassurance: the
`SpanCell` output we already compute (`row`, `col`, `rowspan`, `colspan`) maps
one-to-one onto Grid placement, just with 1-indexed lines:

```js
// column header cell
gridColumn = `${rowDepth + col + 1} / span ${colspan}`;
gridRow    = `${row + 1} / span ${rowspan}`;
// row header cell
gridColumn = `${col + 1} / span ${colspan}`;
gridRow    = `${colDepth + row + 1} / span ${rowspan}`;
// data cell (dr, dc)
gridColumn = `${rowDepth + dc + 1}`;
gridRow    = `${colDepth + dr + 1}`;
```

Grid places items by explicit line number, so there's none of the "next free
slot" implicitness the table relies on. All of `spans.py` and its area-coverage
invariant stay exactly as they are. **Only the renderer changes; the Python is
untouched.**

**A property worth highlighting:** only *header* cells ever span. Merging a
header reduces the leaf count — there's one fewer data column/row — but the data
cells themselves are always 1×1 in the leaf grid. So **data cells stay perfectly
uniform squares no matter what's merged**; only headers grow to span tracks. The
merged-state screenshot makes this obvious. That's ideal for a grid of uniform
SVG tiles.

**Sticky headers come almost for free.** `position: sticky` on the header items
within the scroll container keeps them in view; the corner sticks to both edges.
Done in the prototype, lightly tested.

### What you give up

**Accessibility.** This is the real cost. A `<table>` is semantically a table —
screen readers announce headers, navigate cells, associate row/column headers
with data automatically. A grid of divs is, semantically, nothing. To recover
it you add ARIA roles (`role="table"`, `role="row"`, `role="columnheader"`,
`role="gridcell"`, plus `aria-rowspan`/`aria-colspan`). Those ARIA span
attributes have **patchier screen-reader support** than real `<table>` spans, so
even done carefully it's not fully equivalent. If this widget needs to be
accessible to assistive tech, that's a genuine ongoing burden the table gave you
for nothing.

**Semantic/export niceties.** Copy-paste into a spreadsheet, "save as HTML
table", and similar conveniences work out of the box with `<table>` and need
explicit handling with divs.

**You're hand-rolling layout the table did for you.** Not much — the placement
maths is already done — but it is more code you own.

### Verdict

For a dense grid of equal-sized SVG tiles, Grid is the right tool and the
prototype proves the migration is low-risk (Python unchanged, only `widget.js`
rewritten). The decision really comes down to **how much you need
screen-reader accessibility**. If it matters, budget for the ARIA work or
reconsider; if this is an internal/analytical tool where that's not a hard
requirement, Grid is clearly better here.

---

## 2. Uniform row/column sizing — one consequence to decide

With fixed-width data columns, a leaf **column header** sits above a single
narrow cell. "Revenue" above a 60px column doesn't fit horizontally. This is
inherent to "uniform narrow columns + text headers" — it's true for the table
too, it just surfaces immediately once widths are fixed. Options, in rough order
of effort:

- **Truncate with ellipsis + tooltip** (what the prototype does) — simplest.
- **Rotate leaf column-header text 90°** — common in dense matrices; readable,
  costs vertical header height.
- **Abbreviate** member labels (the demo uses "Rev"/"Units").
- **Let the header band wrap** to a taller fixed height.

Worth picking deliberately. Rotation tends to look best for matrix-style tables
with many equal columns; the demo used abbreviation + truncation to keep it
simple.

(Row headers don't have this problem — they're in content-sized columns on the
left, so labels have horizontal room.)

---

## 3. SVG content

The prototype gives each data cell a `<svg viewBox="0 0 100 100">` that fills the
cell. Two `preserveAspectRatio` choices show the trade:

- `preserveAspectRatio="none"` — the SVG stretches to the cell. Fine for things
  like bars/fills; distorts circles if the cell isn't square.
- `preserveAspectRatio="xMidYMid meet"` (default-ish) — keeps aspect ratio,
  letterboxing if needed. Best when the glyph has a fixed aspect (a dial, an
  icon).

Since your cells are square and uniform, either works; for non-square cells
you'd want `meet`. The integration point in the real widget is one function,
`calculate(row_path, col_path) -> svg_string` (or a structured spec the front
end turns into SVG). That slots into the existing `calculate` callback — the
widget already calls it per leaf pair; it would just return SVG markup instead
of a scalar. **No engine change needed**, only:

- the renderer injects the returned markup as the cell's innerHTML (with the
  usual caution: sanitise if the SVG isn't fully under your control), and
- you'd likely want the value passed to JS as a string and set via a parsed SVG
  node rather than raw innerHTML if untrusted.

One performance note: at large grids (say 50×50 = 2,500 cells) that's 2,500
inline SVGs. DOM-heavy but generally fine; if it ever isn't, the escape hatches
are `<canvas>` per cell or virtualisation (render only visible cells). Not worth
doing pre-emptively.

---

## 4. Drag-and-drop field selector

The prototype has three zones (Available / Rows / Columns), draggable field
chips, a **merged** checkbox per assigned field, and removal back to the pool.
Any change rebuilds the table live.

### The important modelling point

A field selector implies a **cross-product** hierarchy: pick fields, and their
members combine regularly — every parent at a level has the same children. That
is *different* from the hand-built dev example, where UK/Germany sit under EMEA
but Japan/Australia under APAC (members differ per parent — an *irregular*
tree).

So the field selector and the explicit `H()` API serve different cases:

- **`fields.build_forest([...])`** — regular cross-products from declared
  fields. What the selector produces. New module, tested.
- **`H(...)` trees** — arbitrary/irregular hierarchies, members differing per
  parent. The original API, still needed for cases the selector can't express.

`build_forest` already feeds `spans.py` and the widget unchanged (there's a test
asserting the area-coverage invariant still holds on a field-built forest), so
this is additive, not a rewrite.

### "Start merged" per field

Each field has a `start_merged` flag. If set, nodes at that level are created
already merged (collapsed but splittable). Because a merged node hides its
children, marking field *k* merged effectively makes *k* the initial visible
leaf level — you then split individual nodes to drill in. The flag is ignored on
the deepest field (nothing beneath to collapse). All covered by tests in
`test_fields.py`.

### What's solid vs. what's shaky here

- **Solid:** the `fields.build_forest` logic (Python, 14 tests) and the
  rebuild-on-change wiring.
- **Shaky:** the **native HTML5 drag-and-drop** itself. It's notoriously
  inconsistent (touch devices barely support it; reorder-vs-reparent drop
  targets are finicky). The prototype implements dragstart/dragover/drop and
  works in desktop Chromium, but I couldn't meaningfully verify the drag gestures
  via screenshot. For production I'd seriously consider a small DnD library
  (e.g. a sortable/dnd-kit-style approach) rather than raw HTML5 DnD, especially
  if touch/mobile matters — which, given you're often on a phone, it probably
  does. HTML5 DnD essentially doesn't work on touch without a polyfill.

---

## Net recommendation

1. **Adopt CSS Grid for rendering.** The migration is contained to `widget.js`;
   `header.py`, `spans.py`, and `widget.py` are unchanged. Decide the
   accessibility question explicitly — that's the one real trade.
2. **Keep both hierarchy-construction paths:** `fields.build_forest` for the
   selector's cross-products, `H()` for irregular trees.
3. **Pick a header-label strategy** for narrow columns (rotation or
   abbreviation).
4. **Treat the drag-and-drop layer as UI you'll likely want a library for**,
   particularly for touch. The field→forest logic underneath is done and tested;
   the gesture layer is the part to harden.

None of the new requirements disturb the core engine — the span maths and the
merge/split model carry over intact. The work is all in the rendering and
configuration layers, which is exactly where you'd want the churn to be.
