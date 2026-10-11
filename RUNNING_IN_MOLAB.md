# Running in molab

[molab](https://molab.marimo.io) is marimo's hosted notebook service. It runs a
real Python kernel, so the widget works fully there: merge, split, selection
and downstream cells.

molab installs packages from PyPI as a notebook imports them, and this package
isn't on PyPI. So the repo ships **`demo_standalone.py`**: one self-contained
notebook with the whole package inlined. It needs only `marimo` and
`anywidget`, which molab installs itself.

## Opening it

**[Open demo_standalone.py in molab](https://molab.marimo.io/github/jimbobcuz/multilevel-table/blob/main/demo_standalone.py)**

molab opens any notebook in a public GitHub repo with a URL of the form
`https://molab.marimo.io/github/<owner>/<repo>/blob/<branch>/<file>`. The
preview runs in the browser with WebAssembly, so the widget is fully
interactive there. Fork it into your molab workspace to edit it.

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
