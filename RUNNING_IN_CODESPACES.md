# Running the widget in GitHub Codespaces

This lets you edit **and interactively run** the widget entirely in the browser —
no Python or Node installed on your own machine. A Codespace is a full Linux dev
box that GitHub hosts for you; you reach it from any browser, including a tablet
(a phone works but is cramped).

The repo already contains a `.devcontainer/` config, so a fresh Codespace boots
with everything installed and the marimo port pre-forwarded. You shouldn't need
to install anything by hand.

---

## One-time setup: get the code onto GitHub

If the project isn't on GitHub yet, do this once from any machine that has git
(or use GitHub's web "upload files" button if you have no terminal at all).

1. Create a new empty repository on github.com — call it `multilevel-table`.
   Don't add a README/license from the wizard (the repo already has files).

2. From the project root (the folder containing `pyproject.toml`):

   ```bash
   git init
   git add .
   git commit -m "Initial commit: multilevel table widget"
   git branch -M main
   git remote add origin https://github.com/YOUR_USERNAME/multilevel-table.git
   git push -u origin main
   ```

That's the only step that benefits from a real computer. Everything after this
happens in the browser.

---

## Launch a Codespace

1. Open your repo on github.com.
2. Click the green **`< > Code`** button.
3. Choose the **Codespaces** tab → **Create codespace on main**.

GitHub spins up the container. The first build takes a couple of minutes because
the `postCreateCommand` runs `pip install -e .` plus marimo and the test tools.
When it finishes you'll see VS Code running in your browser, with this project
open and the package already installed in editable mode.

---

## Run the interactive notebook

In the Codespace's terminal (Terminal → New Terminal, or `` Ctrl+` ``):

```bash
marimo edit demo.py --host 0.0.0.0 --port 2718
```

- `--host 0.0.0.0` is important — it tells marimo to accept connections from
  outside the container, which is how the forwarded port reaches your browser.
- Port `2718` is marimo's default and is already declared in the devcontainer,
  so GitHub forwards it automatically.

A **"Open in Browser"** toast usually appears. If it doesn't:

1. Open the **Ports** tab (next to Terminal at the bottom).
2. Find port **2718** (labelled "marimo").
3. Click the globe icon to open the forwarded URL in a new tab.

You'll get the marimo editor with the live widget. Click the `–` / `+` glyphs on
the headers to merge and split, and use the ✎ to rename — the same interaction
you saw in the demo, but now backed by the real Python kernel rather than the
in-browser stand-in. This is the part the static demo couldn't exercise.

If marimo prints a token in the URL, just use the full URL it gives you
(including `?access_token=...`); the forwarded link preserves it.

---

## Run the tests

No browser needed — the 117 tests are headless:

```bash
pytest multilevel_table/tests/ -v
```

Use this as your fast feedback loop while editing logic. The interactive
notebook is for confirming the *rendering and interaction*; the tests confirm
the *model, spans, and message handling*.

---

## Edit, then see your changes

Editable install means source edits are picked up without reinstalling.

- **Python changes** (`header.py`, `spans.py`, `widget.py`): re-run the affected
  cell in marimo, or restart the notebook (marimo's "restart" button) to be safe.
- **Front-end changes** (`static/widget.js`, `static/widget.css`): re-run the
  cell that creates the widget so anywidget reloads the assets, then
  hard-refresh the browser tab (Ctrl/Cmd+Shift+R) to clear cached JS/CSS.

You can edit files three ways, all in the browser:
- VS Code's editor in the Codespace (best for multi-file work).
- Directly in the marimo editor for notebook cells.
- Via **Claude Code**, which can operate inside the Codespace terminal if you
  want it making edits and running tests for you.

---

## Stopping and costs

- A Codespace keeps running (and billing) until you stop it. Close the tab is
  **not** enough — it idles out eventually, but to be deliberate:
  github.com → your avatar → **Codespaces** → `...` → **Stop codespace**.
- Free accounts include a monthly quota of Codespaces core-hours and storage,
  which is plenty for this kind of work. Stopping when you're done keeps you
  well inside it.
- Stopping preserves your files and state; you can resume the same Codespace
  later. Deleting it frees the storage but discards anything not pushed to git,
  so **push your commits** before deleting.

---

## If something doesn't work

- **Port 2718 not forwarding / blank page** — confirm you launched marimo with
  `--host 0.0.0.0`. Without it the server only listens inside the container and
  the forwarded port shows nothing.
- **Widget renders but clicks do nothing** — this is the live comm path. Check
  the browser console (F12) for errors, and the marimo terminal for a traceback
  from the message handler in `widget.py`. The handler swallows *invalid* ops
  silently by design, so also confirm the node you're clicking is actually
  mergeable/splittable in its current state.
- **Fonts look plain** — the CSS pulls IBM Plex from Google Fonts; if the
  Codespace blocks that, you get system fallbacks. Cosmetic only.
- **`marimo: command not found`** — the post-create step didn't finish or you
  opened the terminal too early. Run `pip install marimo` manually.

---

## What this gives you vs. the other options

| | Edit code | Run tests | Interactive widget |
|---|---|---|---|
| Claude Code on GitHub (phone) | ✅ | ✅ | ❌ (no browser session) |
| **Codespaces (this doc)** | ✅ | ✅ | ✅ |
| marimo WASM hosting | ❌ | ❌ | ✅ *if* anywidget works in WASM |

Codespaces is the option that does all three, which is why it's the
recommended path for actually using the widget end to end without your own
machine.
