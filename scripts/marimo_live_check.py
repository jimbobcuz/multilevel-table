"""
Live round-trip check against a running marimo server.

    marimo run demo.py --headless --port 2799 --no-token &
    python scripts/marimo_live_check.py http://localhost:2799 OUT_DIR

Clicks through the real widget in a real marimo app and checks that the
downstream markdown cell reacts (merged columns, grid size, selection).
Playwright CSS locators pierce open shadow roots, so this works whether or
not marimo mounts the widget in a shadow DOM.
"""

from __future__ import annotations

import json
import pathlib
import sys

from playwright.sync_api import sync_playwright


def main(url: str, out: pathlib.Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    res: dict = {}
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={"width": 1400, "height": 1000}, device_scale_factor=1.5)
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(url)
        page.locator(".mlt-cell").first.wait_for(timeout=60_000)
        page.wait_for_timeout(800)

        def status():
            text = page.inner_text("body")
            i = text.find("Merged columns")
            return " ".join(text[i:i + 400].split()) if i >= 0 else ""

        def count(sel):
            return page.locator(sel).count()

        res["initial"] = {"cells": count(".mlt-cell"), "svgs": count(".mlt-cell > svg"), "status": status()}
        page.screenshot(path=str(out / "live_1_initial.png"), full_page=True)

        page.locator(".mlt-h-col", has_text="United Kingdom").first.click()
        page.wait_for_function(
            "() => document.body.innerText.includes('Merged columns: uk') "
            "|| [...document.querySelectorAll('*')].some(e => e.shadowRoot && e.shadowRoot.textContent.includes('Merged columns: uk'))",
            timeout=20_000,
        )
        page.wait_for_timeout(500)
        res["after_merge_uk"] = {"cells": count(".mlt-cell"), "status": status()}

        page.locator(".mlt-cell").nth(2).click()
        page.wait_for_timeout(1500)
        # The outline must be visible on top of a full-bleed SVG: sample the
        # pixel colour at the tile's left edge.
        box = page.locator(".mlt-selected").first.bounding_box()
        edge = page.evaluate(
            "([x, y]) => { const e = document.elementFromPoint(x, y); return e ? e.className : null; }",
            [box["x"] + 1, box["y"] + box["height"] / 2],
        ) if box else None
        outline = page.locator(".mlt-selected").first.evaluate(
            "e => getComputedStyle(e, '::after').borderTopWidth")
        res["after_select"] = {"selected_tiles": count(".mlt-selected"), "outline_width": outline,
                               "edge_element": edge, "status": status()}
        page.locator(".mlt-selected").first.screenshot(path=str(out / "live_selected_tile.png"))
        page.screenshot(path=str(out / "live_2_merged_selected.png"), full_page=True)

        page.locator(".mlt-h-col", has_text="United Kingdom").first.click()
        page.wait_for_timeout(1500)
        res["after_split_uk"] = {"cells": count(".mlt-cell"), "status": status()}

        res["page_errors"] = errors
        b.close()
    (out / "live_results.json").write_text(json.dumps(res, indent=2))
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main(sys.argv[1], pathlib.Path(sys.argv[2]))
