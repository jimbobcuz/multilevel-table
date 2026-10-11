# Running in molab

[molab](https://molab.marimo.io) is marimo's hosted notebook service. It runs a
real Python kernel, so the widget works fully there: merge, split, selection
and downstream cells.

molab can only open notebooks from **public** GitHub URLs, and it can't install
packages from a private repo. So the repo ships **`demo_standalone.py`**: one
self-contained notebook with the whole package inlined. It needs only `marimo`
and `anywidget`, which molab installs itself.

## Opening it

molab opens a GitHub-hosted notebook from a URL of this form:

```
https://molab.marimo.io/github/<owner>/<repo>/blob/<branch>/demo_standalone.py
```

That only works if the repo holding the file is **public**. Options:

| Option | Effect |
| --- | --- |
| A public demo repo holding only `demo_standalone.py` | One link opens it in molab; the widget code becomes public, the main repo stays private |
| Make this repo public | Same link pattern works for every notebook here |
| Keep everything private | Run `demo_standalone.py` (or `demo.py`) on your own machine instead |

## Privacy

molab notebooks are public but undiscoverable by default: anyone with the link
can see them. Use molab for the widget and demo data only, never for real or
sensitive data.

## Keeping it current

`demo_standalone.py` is generated. After changing the package:

```bash
python scripts/build_standalone.py
```

`tests/test_standalone.py` fails if the file is stale, so the build can't
silently drift from the package.
