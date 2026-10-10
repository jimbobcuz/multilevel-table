"""
End-to-end check of the real widget.js against the real Python widget.

Loads static/widget.js + widget.css into headless Chromium with a small
anywidget-style `model` shim. Every `save_changes()` in the browser is
forwarded to Python (Playwright expose_function), applied to a live
MultilevelTable, and the recomputed traits are pushed back — the same loop
anywidget runs, minus the Jupyter/marimo comm transport.

Usage:  python scripts/browser_check.py OUT_DIR
"""

from __future__ import annotations

import json
import pathlib
import sys

from playwright.sync_api import sync_playwright

from multilevel_table import MultilevelTable
from multilevel_table.examples import example_calculate, example_headers

STATIC = pathlib.Path(__file__).resolve().parents[1] / "multilevel_table" / "static"
SYNCED = ["col_grid", "row_grid", "col_paths", "row_paths", "data",
          "cell_width", "cell_height", "col_merged", "selected"]


def demo_table() -> MultilevelTable:
    rows, cols = example_headers()
    cols.find("jp_units").relabel("Units sold (thousands)")   # exercise label wrapping

    def calculate(row_path, col_path):
        if row_path[-1] == "shield":
            return 42                                          # exercise the text fallback
        return example_calculate(row_path, col_path)

    return MultilevelTable(rows, cols, calculate)


HARNESS = """<!doctype html><html><head><meta charset="utf-8"><style>%CSS%</style>
<style>body{margin:24px;background:#e8e6df}</style></head><body><div id="app"></div>
<script type="module">
const state = %STATE%;
const handlers = {};
const pending = {};
window.__model = {
  get: k => state[k],
  set: (k, v) => { pending[k] = v; },
  // Strict like marimo's model: one event name per call, no space-separated lists.
  on: (evt, cb) => {
    if (/\\s/.test(evt)) throw new Error("model.on takes a single event name: " + evt);
    (handlers[evt] ||= []).push(cb);
  },
  save_changes: async () => {
    const changes = Object.assign({}, pending);
    for (const k in pending) delete pending[k];
    const next = JSON.parse(await window.pySync(JSON.stringify(changes)));
    // Like Backbone: apply every attribute first, then fire change events.
    const changed = Object.keys(next).filter(k => JSON.stringify(state[k]) !== JSON.stringify(next[k]));
    for (const k of changed) state[k] = next[k];
    for (const k of changed) for (const cb of handlers["change:" + k] || []) cb();
    await new Promise(r => setTimeout(r, 0));
    window.__syncs = (window.__syncs || 0) + 1;
  },
};
const mod = await import(URL.createObjectURL(new Blob([%JS%], {type: "text/javascript"})));
mod.default.render({ model: window.__model, el: document.getElementById("app") });
window.__ready = true;
</script></body></html>"""


def snapshot(t: MultilevelTable) -> dict:
    return {k: getattr(t, k) for k in SYNCED}


def main(out: pathlib.Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    table = demo_table()
    log: list[dict] = []

    def py_sync(payload: str) -> str:
        changes = json.loads(payload)
        log.append(changes)
        for k, v in changes.items():
            setattr(table, k, v)
        return json.dumps(snapshot(table))

    html = (HARNESS
            .replace("%CSS%", (STATIC / "widget.css").read_text())
            .replace("%STATE%", json.dumps(snapshot(table)))
            .replace("%JS%", json.dumps((STATIC / "widget.js").read_text())))
    page_path = out / "harness.html"
    page_path.write_text(html)

    results = {}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1300, "height": 900}, device_scale_factor=2)
        errors: list[str] = []
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.expose_function("pySync", py_sync)
        page.goto(page_path.as_uri())
        page.wait_for_function("window.__ready === true")
        page.wait_for_timeout(300)

        def counts():
            return page.evaluate("""() => ({
              headers: document.querySelectorAll('.mlt-h').length,
              colHeaders: document.querySelectorAll('.mlt-h-col').length,
              rowHeaders: document.querySelectorAll('.mlt-h-row').length,
              cells: document.querySelectorAll('.mlt-cell').length,
              svgs: document.querySelectorAll('.mlt-cell > svg').length,
              text: document.querySelectorAll('.mlt-cell .mlt-text').length,
              badSvg: document.querySelectorAll('.mlt-bad').length,
              rowControls: document.querySelectorAll('.mlt-h-row .mlt-glyph').length,
              selected: document.querySelectorAll('.mlt-selected').length,
            })""")

        def cell_sizes():
            return page.evaluate("""() => {
              const s = new Set();
              document.querySelectorAll('.mlt-cell').forEach(c => {
                const r = c.getBoundingClientRect(); s.add(`${Math.round(r.width)}x${Math.round(r.height)}`);
              });
              return [...s];
            }""")

        def click_header(label):
            page.locator(".mlt-h-col", has_text=label).first.click()
            page.wait_for_timeout(250)

        results["initial"] = {**counts(), "sizes": cell_sizes()}
        page.screenshot(path=str(out / "1_initial.png"), full_page=True)

        click_header("United Kingdom")
        click_header("Germany")
        results["after_merge_uk_germany"] = {**counts(), "sizes": cell_sizes(),
                                             "py_col_merged": sorted(table.col_merged)}
        click_header("EMEA")
        results["after_merge_emea"] = {**counts(), "sizes": cell_sizes(),
                                       "py_col_merged": sorted(table.col_merged)}
        page.locator(".mlt-cell").nth(2 * 5 + 1).click()     # row 2 ("Air"), col 1
        page.wait_for_timeout(250)
        results["after_select"] = {**counts(), "py_selected": table.selected}
        page.screenshot(path=str(out / "2_merged_selected.png"), full_page=True)

        click_header("EMEA")                                   # split EMEA again
        results["after_split_emea"] = {**counts(), "py_col_merged": sorted(table.col_merged),
                                       "py_selected": table.selected}

        # Rows must ignore clicks entirely.
        before = len(log)
        page.locator(".mlt-h-row", has_text="Laptops").first.click()
        page.wait_for_timeout(200)
        results["row_click_sent_changes"] = len(log) - before

        # Sticky headers: scroll and confirm the header band stays in view.
        page.set_viewport_size({"width": 700, "height": 420})
        page.evaluate("document.querySelector('.mlt-scroll').style.maxHeight='300px'")
        page.wait_for_timeout(100)
        page.evaluate("document.querySelector('.mlt-scroll').scrollTo(400, 200)")
        page.wait_for_timeout(200)
        results["sticky"] = page.evaluate("""() => {
          const sc = document.querySelector('.mlt-scroll').getBoundingClientRect();
          const top = [...document.querySelectorAll('.mlt-h-col')].map(h => h.getBoundingClientRect().top - sc.top);
          const left = [...document.querySelectorAll('.mlt-h-row')].map(h => h.getBoundingClientRect().left - sc.left);
          return {minColHeaderTop: Math.min(...top), minRowHeaderLeft: Math.min(...left)};
        }""")
        page.screenshot(path=str(out / "3_scrolled_sticky.png"))

        results["browser_errors"] = errors
        results["sync_log"] = log
        browser.close()

    (out / "results.json").write_text(json.dumps(results, indent=2))
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main(pathlib.Path(sys.argv[1]))
