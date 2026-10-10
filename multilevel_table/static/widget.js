// MultilevelTable frontend renderer.
//
// Pure renderer: consumes the serialised span grids (row_grid, col_grid) and
// the data matrix from synced traitlets, builds an HTML <table>, and emits
// merge / split / relabel intents via model.send(). All authoritative state
// lives in Python; whenever Python pushes new grids we rebuild from scratch.

function depthLevel(cell, axis) {
  // Hierarchy level (0 = root): grid row for col headers, grid col for row headers.
  return axis === "col" ? cell.row : cell.col;
}

function makeHeaderCell(cell, axis, model, rerender) {
  const th = document.createElement("th");
  th.rowSpan = cell.rowspan;
  th.colSpan = cell.colspan;

  const level = Math.min(depthLevel(cell, axis), 3);
  th.className = `mlt-h mlt-h-${axis} mlt-lvl-${level}`;
  if (cell.canMerge) th.classList.add("mlt-mergeable");
  if (cell.canSplit) th.classList.add("mlt-splittable");
  if (cell.isLeaf) th.classList.add("mlt-leaf");

  const label = document.createElement("span");
  label.className = "mlt-label";
  label.textContent = cell.label;
  th.appendChild(label);

  if (cell.canMerge || cell.canSplit) {
    const glyph = document.createElement("span");
    glyph.className = "mlt-glyph";
    glyph.textContent = cell.canSplit ? "+" : "\u2013";
    glyph.setAttribute("aria-hidden", "true");
    th.appendChild(glyph);
    th.title = cell.canSplit ? "Click to split" : "Click to merge";
  }

  const edit = document.createElement("button");
  edit.className = "mlt-edit";
  edit.type = "button";
  edit.textContent = "\u270E";
  edit.title = "Rename";
  edit.addEventListener("click", (e) => {
    e.stopPropagation();
    startRelabel(th, label, cell, model, rerender);
  });
  th.appendChild(edit);

  if (cell.canMerge || cell.canSplit) {
    th.addEventListener("click", () => {
      const op = cell.canSplit ? "split" : "merge";
      model.send({ op, key: cell.key });
    });
  }

  return th;
}

function startRelabel(th, labelEl, cell, model, rerender) {
  const current = cell.label;
  const input = document.createElement("input");
  input.className = "mlt-relabel";
  input.value = current;
  labelEl.replaceWith(input);
  input.focus();
  input.select();

  let done = false;
  const finish = (commit) => {
    if (done) return;
    done = true;
    const next = input.value.trim();
    if (commit && next && next !== current) {
      model.send({ op: "relabel", key: cell.key, label: next });
    } else {
      rerender();
    }
  };

  input.addEventListener("blur", () => finish(true));
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") { e.preventDefault(); finish(true); }
    else if (e.key === "Escape") { e.preventDefault(); finish(false); }
  });
  input.addEventListener("click", (e) => e.stopPropagation());
}

function buildTable(model, rerender) {
  const colGrid = model.get("col_grid");
  const rowGrid = model.get("row_grid");
  const data = model.get("data");

  const colDepth = colGrid.depth;
  const colLeaves = colGrid.leafCount;
  const rowDepth = rowGrid.depth;
  const rowLeaves = rowGrid.leafCount;

  const colByRow = Array.from({ length: colDepth }, () => []);
  for (const c of colGrid.cells) colByRow[c.row].push(c);
  colByRow.forEach((r) => r.sort((a, b) => a.col - b.col));

  const rowByRow = Array.from({ length: rowLeaves }, () => []);
  for (const c of rowGrid.cells) rowByRow[c.row].push(c);
  rowByRow.forEach((r) => r.sort((a, b) => a.col - b.col));

  const table = document.createElement("table");
  table.className = "mlt-table";

  const thead = document.createElement("thead");
  for (let r = 0; r < colDepth; r++) {
    const tr = document.createElement("tr");
    if (r === 0) {
      const corner = document.createElement("th");
      corner.className = "mlt-corner";
      corner.rowSpan = colDepth;
      corner.colSpan = rowDepth;
      tr.appendChild(corner);
    }
    for (const c of colByRow[r]) tr.appendChild(makeHeaderCell(c, "col", model, rerender));
    thead.appendChild(tr);
  }
  table.appendChild(thead);

  const tbody = document.createElement("tbody");
  for (let dr = 0; dr < rowLeaves; dr++) {
    const tr = document.createElement("tr");
    for (const c of rowByRow[dr]) tr.appendChild(makeHeaderCell(c, "row", model, rerender));
    for (let dc = 0; dc < colLeaves; dc++) {
      const td = document.createElement("td");
      td.className = "mlt-cell";
      const v = data[dr] ? data[dr][dc] : null;
      if (v === null || v === undefined || v === "") {
        td.classList.add("mlt-empty");
        td.textContent = "\u00B7";
      } else {
        td.textContent = String(v);
      }
      tr.appendChild(td);
    }
    tbody.appendChild(tr);
  }
  table.appendChild(tbody);

  return table;
}

function render({ model, el }) {
  el.classList.add("mlt-root");

  function rerender() {
    el.replaceChildren();
    const scroll = document.createElement("div");
    scroll.className = "mlt-scroll";
    scroll.appendChild(buildTable(model, rerender));
    el.appendChild(scroll);
  }

  model.on("change:row_grid change:col_grid change:data", rerender);
  rerender();
}

export default { render };
