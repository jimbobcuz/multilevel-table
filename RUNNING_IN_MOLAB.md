# Running the widget in molab (cloud marimo)

[molab](https://molab.marimo.io) is marimo's free cloud-hosted notebook service —
Colab, but for marimo. Unlike the WebAssembly playground at marimo.app, molab
runs on a **real backend with a live Python kernel**, which is exactly what this
widget's merge/split round trip needs. You drive it from any browser, including a
tablet or phone.

The key idea: molab is notebook-centric, and your code is a multi-file *package*.
So instead of uploading all the files, you **publish the package to GitHub** and
let molab's `uv` install it straight from git when the notebook runs. Your project
is already set up for this — the root `pyproject.toml` makes it git-installable,
and the JS/CSS ship inside the wheel.

---

## Contents

- [The overall picture](#the-overall-picture)
- [Step 1 — Put the repo on GitHub](#step-1--put-the-repo-on-github)
- [Step 2 — Point the notebook at your repo](#step-2--point-the-notebook-at-your-repo)
- [Step 3 — Open it in molab](#step-3--open-it-in-molab)
- [Editing with Claude Code](#editing-with-claude-code)
- [Getting molab to pick up new commits](#getting-molab-to-pick-up-new-commits)
- [Sharing caveat](#sharing-caveat)
- [Troubleshooting](#troubleshooting)

---

## The overall picture

```
        edit code                       run interactively
   ┌──────────────────┐            ┌────────────────────────┐
   │   Claude Code     │  push      │        molab           │
   │  (via GitHub)     │ ───────▶   │  uv installs package   │
   │                   │   GitHub   │  from git, live kernel │
   └──────────────────┘            └────────────────────────┘
            ▲                                   │
            │              you, from a browser  │
            └───────────────────────────────────┘
```

GitHub is the hub. Claude Code edits the repo and pushes; molab installs the
package from that repo and runs it. The two never talk directly — they meet at
the repo.

---

## Step 1 — Put the repo on GitHub

This is the one step that's easiest with a terminal, but GitHub's web upload
works too if you have no terminal at all.

1. Create a new repository on github.com named `multilevel-table`. Leave it empty
   (no README/license from the wizard — the project already has files).

2. Push the project (from the folder containing `pyproject.toml`):

   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git branch -M main
   git remote add origin https://github.com/YOUR_USERNAME/multilevel-table.git
   git push -u origin main
   ```

   No terminal at all? On the empty repo's page, use **"uploading an existing
   file"** and drag in the whole project folder. Make sure the structure is
   preserved (`pyproject.toml` at the root, `multilevel_table/` package beside it).

The repo can be **public or private** — molab can install from private repos if
you authorise it, but public is simplest to start.

---

## Step 2 — Point the notebook at your repo

Use **`demo_molab.py`** (not `demo.py` — that one uses a local editable path for
Codespaces/local work). Open `demo_molab.py` and edit the one marked line in the
dependency block at the top:

```python
# /// script
# requires-python = ">=3.11"
# dependencies = ["marimo", "anywidget", "multilevel-table"]
#
# [tool.uv.sources]
# multilevel-table = { git = "https://github.com/YOUR_USERNAME/multilevel-table.git", branch = "main" }
# ///
```

Replace `YOUR_USERNAME` with your GitHub username. Commit and push that change so
the version on GitHub is correct too.

This is PEP 723 inline script metadata: molab reads it and `uv` installs marimo,
anywidget, and your package (pulled from git) before running the notebook.

---

## Step 3 — Open it in molab

You have two routes.

**Route A — open the GitHub-hosted notebook directly.** molab can open any
notebook hosted on GitHub by URL substitution: take the GitHub URL of
`demo_molab.py` and replace `github.com` with `molab.marimo.io/github`. For
example:

```
https://github.com/YOUR_USERNAME/multilevel-table/blob/main/demo_molab.py
→
https://molab.marimo.io/github/YOUR_USERNAME/multilevel-table/blob/main/demo_molab.py
```

This opens a preview; click to **fork it into your workspace** so it runs on a
live backend (the raw preview may be static — forking gives you the kernel).

**Route B — create a notebook in molab and paste.** Go to
[molab.marimo.io](https://molab.marimo.io), create a new notebook, and paste the
contents of `demo_molab.py` (including the `# /// script ... # ///` header — molab
honours it). Run the first cell; `uv` installs your package from git, and the
widget renders with a live kernel.

Either way, once it's running in your workspace you get the real interactive
table — click the `–` / `+` glyphs to merge and split, ✎ to rename. This is the
full Python round trip, not the in-browser stand-in from the static demo.

---

## Editing with Claude Code

Claude Code edits your **GitHub repo**; molab runs what's on GitHub. So the loop
is edit-and-push in Claude Code, then refresh in molab. Because you're working
without your own machine, use Claude Code through its GitHub integration rather
than a local clone.

**Connect Claude Code to the repo:**

1. In the Claude app (or claude.ai), start Claude Code and grant it access to your
   GitHub account / the `multilevel-table` repo when prompted. This uses the
   GitHub connector, so Claude Code can read the repo, make commits, and open
   pull requests on a remote runner — no local checkout needed.

2. Ask it to make a change, e.g. *"in `multilevel_table/spans.py`, add a helper
   that returns the deepest visible level, with a test."* Claude Code edits on a
   branch and can commit/push or open a PR.

3. Merge the change into `main` (Claude Code can open the PR; you approve/merge
   from the GitHub UI, which works fine on a phone).

**What Claude Code is good for here:** all the logic work — editing
`header.py` / `spans.py` / `widget.py`, writing and running the 117 headless
tests (`pytest multilevel_table/tests/`), refactoring, fixing bugs it finds from
test output. It runs the tests in its own environment, so you get green/red
feedback without molab involved at all.

**What it can't do:** show you the *rendered, interactive* widget. There's no
browser session it controls. That's molab's job. So the division of labour is:
**Claude Code for editing + tests, molab for seeing and clicking the result.**

---

## Getting molab to pick up new commits

This is the one genuine friction point. `uv` caches git dependencies, so after
Claude Code pushes a change, molab won't automatically have it. To force the new
version:

- **Simplest:** in molab, restart the notebook's runtime / kernel (or re-fork the
  notebook). On a fresh runtime `uv` re-resolves and pulls the latest `main`.
- **Most reliable:** pin to a specific commit so the dependency string itself
  changes each time, which defeats the cache:

  ```python
  # multilevel-table = { git = "https://github.com/YOU/multilevel-table.git", rev = "COMMIT_SHA" }
  ```

  Paste the new commit SHA after each push. More typing, but unambiguous about
  which version is running — worth it when you're debugging and need certainty
  that molab has your latest code.

- **Version bumps** also help: bump `version` in `pyproject.toml` each meaningful
  change, so it's obvious in molab which build loaded.

If you ever see molab running stale code, assume the cache — restart the runtime
or pin the SHA.

---

## Sharing caveat

molab sharing works by generating a **WebAssembly preview** of your notebook.
WASM previews are **static (read-only) by default**, and interactive only "when
compatible." Whether your anywidget's live comm survives a WASM preview is the
same untested seam noted elsewhere — it may degrade to a static snapshot for
viewers.

So: **you, in your own molab workspace → fully interactive** (real backend).
**A link you send someone else → possibly static.** If interactive sharing
matters, that's the thing to test explicitly before relying on it.

---

## Troubleshooting

- **`uv` can't install the package / "failed to resolve"** — check the git URL in
  the script header is exactly your repo, the branch exists, and (if private) molab
  is authorised for it. Test the same install locally if you can:
  `uvx --with "multilevel-table @ git+https://github.com/YOU/multilevel-table.git" python -c "import multilevel_table"`.
- **Widget area is blank** — the package installed but the front-end assets didn't
  load. Confirm the wheel includes `static/` (it does in a clean build; if you
  changed `pyproject.toml`, rebuild and re-push).
- **Widget renders but clicks do nothing** — the live comm path. Check the browser
  console and the molab kernel logs for a traceback from `widget.py`'s message
  handler. Remember invalid ops are ignored by design, so confirm the node is
  actually mergeable/splittable in its current state.
- **molab shows old behaviour after a push** — cache. Restart the runtime or pin
  the commit SHA (see above).
- **Fonts look plain** — IBM Plex is pulled from Google Fonts; if blocked you get
  system fallbacks. Cosmetic only.

---

## Why molab over Codespaces for you

molab needs no port forwarding, no devcontainer, no "remember to stop the
machine" — you open a URL and it runs. The trade is that it expects your code as
an installable package (hence the GitHub + git-dependency setup above), whereas
Codespaces would run your raw multi-file repo directly. Since the package is now
git-installable, that trade is paid once and then molab is the lower-friction way
to run interactively from any device.
