// MultilevelTable v2 renderer — a single CSS Grid.
//
// Python sends: col_grid, row_grid (span cells), row_paths, col_paths,
// data (R x C values), cell_width, cell_height.
// The browser sets only two traits: col_merged (merge/split) and selected.
//
// Grid layout (1-indexed lines):
//   columns: [rowDepth header cols, max-content] [C data cols, cell_width]
//   rows:    [colDepth header rows, auto]        [R data rows, cell_height]

const SVG_NS = "http://www.w3.org/2000/svg";

function el(tag, cls) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  return e;
}

function place(node, col, colspan, row, rowspan) {
  node.style.gridColumn = `${col} / span ${colspan}`;
  node.style.gridRow = `${row} / span ${rowspan}`;
}

function samePath(a, b) {
  return Array.isArray(a) && Array.isArray(b) && a.length === b.length && a.every((k, i) => k === b[i]);
}

// ---------------------------------------------------------------------------
// Cell content
// ---------------------------------------------------------------------------

function fillCell(td, value) {
  if (value === null || value === undefined || value === "") {
    td.classList.add("mlt-empty");
    return;
  }
  if (typeof value === "string" && value.trimStart().startsWith("<svg")) {
    // The XML parser needs the SVG namespace; add it if the author left it off.
    let markup = value.trim();
    if (!/^<svg[^>]*\sxmlns=/.test(markup)) markup = markup.replace(/^<svg/, `<svg xmlns="${SVG_NS}"`);
    const doc = new DOMParser().parseFromString(markup, "image/svg+xml");
    const root = doc.documentElement;
    if (root && root.namespaceURI === SVG_NS && !doc.querySelector("parsererror")) {
      td.appendChild(document.importNode(root, true));
      return;
    }
    td.classList.add("mlt-bad");
    td.title = "Invalid SVG";
    td.textContent = "!";
    return;
  }
  const span = el("span", "mlt-text");
  span.textContent = String(value);
  td.appendChild(span);
}

// ---------------------------------------------------------------------------
// Headers
// ---------------------------------------------------------------------------

function headerCell(cell, axis) {
  const level = Math.min(axis === "col" ? cell.row : cell.col, 3);
  const h = el("div", `mlt-h mlt-h-${axis} mlt-lvl-${level}`);
  h.dataset.key = cell.key;
  if (cell.isLeaf) h.classList.add("mlt-leaf");

  const label = el("span", "mlt-label");
  label.textContent = cell.label;
  h.appendChild(label);

  if (axis === "col" && (cell.canMerge || cell.canSplit)) {
    h.classList.add(cell.canSplit ? "mlt-splittable" : "mlt-mergeable");
    const glyph = el("span", "mlt-glyph");
    glyph.textContent = cell.canSplit ? "+" : "–";
    glyph.setAttribute("aria-hidden", "true");
    h.appendChild(glyph);
    h.title = cell.canSplit ? `Split ${cell.label}` : `Merge ${cell.label}`;
  }
  return h;
}

// ---------------------------------------------------------------------------
// Render
// ---------------------------------------------------------------------------

function render({ model, el: root }) {
  root.classList.add("mlt-root");
  const scroll = el("div", "mlt-scroll");
  root.appendChild(scroll);

  let cellNodes = [];   // [r][c] -> div, for cheap selection updates

  function applySize() {
    root.style.setProperty("--mlt-cell-w", `${model.get("cell_width")}px`);
    root.style.setProperty("--mlt-cell-h", `${model.get("cell_height")}px`);
  }

  function toggleMerge(cell) {
    const merged = new Set(model.get("col_merged") || []);
    if (cell.canSplit) merged.delete(cell.key);
    else if (cell.canMerge) merged.add(cell.key);
    else return;
    model.set("col_merged", [...merged]);
    model.save_changes();
  }

  function selectCell(r, c) {
    const rowPath = model.get("row_paths")[r];
    const colPath = model.get("col_paths")[c];
    const cur = model.get("selected");
    const next = cur && samePath(cur.row, rowPath) && samePath(cur.col, colPath)
      ? null
      : { row: rowPath, col: colPath };
    model.set("selected", next);
    model.save_changes();
  }

  function paintSelection() {
    const sel = model.get("selected");
    const rowPaths = model.get("row_paths");
    const colPaths = model.get("col_paths");
    for (let r = 0; r < cellNodes.length; r++) {
      const isRow = !!sel && samePath(sel.row, rowPaths[r]);
      for (let c = 0; c < cellNodes[r].length; c++) {
        cellNodes[r][c].classList.toggle("mlt-selected", isRow && samePath(sel.col, colPaths[c]));
      }
    }
  }

  // Sticky header rows/columns need cumulative offsets, otherwise every
  // header row would stick at top:0 on top of the one above it.
  function pinHeaders(grid) {
    for (const h of grid.querySelectorAll(".mlt-h-col")) h.style.top = `${h.offsetTop}px`;
    for (const h of grid.querySelectorAll(".mlt-h-row")) h.style.left = `${h.offsetLeft}px`;
  }

  function draw() {
    applySize();
    const colGrid = model.get("col_grid");
    const rowGrid = model.get("row_grid");
    const data = model.get("data") || [];
    if (!colGrid || !colGrid.cells || !rowGrid || !rowGrid.cells) return;

    const colDepth = colGrid.depth, C = colGrid.leafCount;
    const rowDepth = rowGrid.depth, R = rowGrid.leafCount;

    const grid = el("div", "mlt-grid");
    grid.style.gridTemplateColumns =
      `repeat(${rowDepth}, max-content) repeat(${C}, var(--mlt-cell-w))`;
    grid.style.gridTemplateRows =
      `repeat(${colDepth}, auto) repeat(${R}, var(--mlt-cell-h))`;

    const frag = document.createDocumentFragment();

    const corner = el("div", "mlt-corner");
    place(corner, 1, rowDepth, 1, colDepth);
    frag.appendChild(corner);

    for (const cell of colGrid.cells) {
      const h = headerCell(cell, "col");
      place(h, rowDepth + cell.col + 1, cell.colspan, cell.row + 1, cell.rowspan);
      if (cell.canMerge || cell.canSplit) h.addEventListener("click", () => toggleMerge(cell));
      frag.appendChild(h);
    }

    for (const cell of rowGrid.cells) {
      const h = headerCell(cell, "row");
      place(h, cell.col + 1, cell.colspan, colDepth + cell.row + 1, cell.rowspan);
      frag.appendChild(h);
    }

    cellNodes = [];
    for (let r = 0; r < R; r++) {
      const rowNodes = [];
      for (let c = 0; c < C; c++) {
        const d = el("div", "mlt-cell");
        d.style.gridColumn = `${rowDepth + c + 1}`;
        d.style.gridRow = `${colDepth + r + 1}`;
        fillCell(d, data[r] ? data[r][c] : null);
        d.addEventListener("click", () => selectCell(r, c));
        rowNodes.push(d);
        frag.appendChild(d);
      }
      cellNodes.push(rowNodes);
    }

    grid.appendChild(frag);
    scroll.replaceChildren(grid);
    paintSelection();
    requestAnimationFrame(() => pinHeaders(grid));
  }

  // One sync changes several traits at once; coalesce them into one redraw.
  let drawQueued = false;
  function scheduleDraw() {
    if (drawQueued) return;
    drawQueued = true;
    queueMicrotask(() => { drawQueued = false; draw(); });
  }

  // One event name per model.on call: marimo's model does not accept the
  // space-separated list that Backbone does.
  const resize = () => {
    applySize();
    const grid = scroll.firstChild;
    if (grid) requestAnimationFrame(() => pinHeaders(grid));
  };
  for (const k of ["col_grid", "row_grid", "data", "row_paths", "col_paths"]) model.on(`change:${k}`, scheduleDraw);
  for (const k of ["cell_width", "cell_height"]) model.on(`change:${k}`, resize);
  model.on("change:selected", paintSelection);
  draw();
}

export default { render };
