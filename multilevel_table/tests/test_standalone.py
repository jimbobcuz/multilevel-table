"""demo_standalone.py must be an up-to-date build of the package."""

import importlib.util
import pathlib
import sys
import types

ROOT = pathlib.Path(__file__).resolve().parents[2]


def _builder():
    spec = importlib.util.spec_from_file_location("build_standalone", ROOT / "scripts" / "build_standalone.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_standalone_notebook_is_current():
    expected = _builder().build()
    actual = (ROOT / "demo_standalone.py").read_text()
    assert actual == expected, "demo_standalone.py is stale: run python scripts/build_standalone.py"


def test_inlined_package_works(monkeypatch):
    # As in the notebook: dataclasses need the module registered in sys.modules.
    mod = types.ModuleType("mlt_inlined")
    monkeypatch.setitem(sys.modules, "mlt_inlined", mod)
    exec(compile(_builder().combined_source(), "inlined", "exec"), mod.__dict__)
    rows, cols = mod.example_headers()
    table = mod.MultilevelTable(rows, cols, mod.example_calculate)
    assert len(table.data) == 8 and len(table.data[0]) == 8
    assert table.data[0][0].startswith("<svg")
    table.col_merged = ["uk"]
    assert len(table.col_paths) == 7
