from __future__ import annotations

import pathlib

import pytest

from iklab import sandbox
from iklab.tools.execution import edit_file


@pytest.fixture(autouse=True)
def _set_workdir(tmp_path: pathlib.Path):
    sandbox.set_workdir(tmp_path)
    yield


def _make_file(tmp_path: pathlib.Path, name: str, content: str) -> pathlib.Path:
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


def test_edit_single_replacement(tmp_path: pathlib.Path):
    _make_file(tmp_path, "app.py", "print('hello')\nprint('world')\n")
    result = edit_file("app.py", "print('hello')", "print('hi')")
    assert "1 replacement" in result
    assert (tmp_path / "app.py").read_text() == "print('hi')\nprint('world')\n"


def test_edit_not_found(tmp_path: pathlib.Path):
    _make_file(tmp_path, "app.py", "x = 1\n")
    result = edit_file("app.py", "y = 2", "y = 3")
    assert "not found" in result


def test_edit_ambiguous_without_replace_all(tmp_path: pathlib.Path):
    _make_file(tmp_path, "app.py", "foo\nfoo\n")
    result = edit_file("app.py", "foo", "bar")
    assert "appears 2 times" in result
    # File should be unchanged
    assert (tmp_path / "app.py").read_text() == "foo\nfoo\n"


def test_edit_replace_all(tmp_path: pathlib.Path):
    _make_file(tmp_path, "app.py", "foo\nfoo\n")
    result = edit_file("app.py", "foo", "bar", replace_all=True)
    assert "2 replacements" in result
    assert (tmp_path / "app.py").read_text() == "bar\nbar\n"


def test_edit_delete_text(tmp_path: pathlib.Path):
    _make_file(tmp_path, "app.py", "# TODO: remove this\nx = 1\n")
    result = edit_file("app.py", "# TODO: remove this\n", "")
    assert "1 replacement" in result
    assert (tmp_path / "app.py").read_text() == "x = 1\n"


def test_edit_preserves_indentation(tmp_path: pathlib.Path):
    content = "def foo():\n    return 1\n"
    _make_file(tmp_path, "app.py", content)
    result = edit_file("app.py", "    return 1", "    return 2")
    assert "1 replacement" in result
    assert (tmp_path / "app.py").read_text() == "def foo():\n    return 2\n"


def test_edit_invalid_path(tmp_path: pathlib.Path):
    result = edit_file("nonexistent.py", "a", "b")
    assert "not a valid file" in result
