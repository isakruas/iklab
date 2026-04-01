from __future__ import annotations

import pathlib

import pytest

from iklab import sandbox
from iklab.tools.execution import _UNDO_STACK, write_lines


@pytest.fixture(autouse=True)
def _set_workdir(tmp_path: pathlib.Path):
    sandbox.set_workdir(tmp_path)
    _UNDO_STACK.clear()
    yield


def _make(tmp_path: pathlib.Path, name: str, content: str) -> pathlib.Path:
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


def test_insert_at_beginning(tmp_path: pathlib.Path):
    _make(tmp_path, "f.py", "line1\nline2\n")
    result = write_lines("f.py", 1, "new\n")
    assert "inserted 1 line at line 1" in result
    assert (tmp_path / "f.py").read_text() == "new\nline1\nline2\n"


def test_insert_in_middle(tmp_path: pathlib.Path):
    _make(tmp_path, "f.py", "line1\nline2\nline3\n")
    result = write_lines("f.py", 2, "inserted\n")
    assert "inserted 1 line at line 2" in result
    assert (tmp_path / "f.py").read_text() == "line1\ninserted\nline2\nline3\n"


def test_insert_multiple_lines(tmp_path: pathlib.Path):
    _make(tmp_path, "f.py", "a\nb\n")
    result = write_lines("f.py", 2, "x\ny\nz\n")
    assert "inserted 3 lines" in result
    assert (tmp_path / "f.py").read_text() == "a\nx\ny\nz\nb\n"


def test_append_past_end(tmp_path: pathlib.Path):
    _make(tmp_path, "f.py", "line1\n")
    result = write_lines("f.py", 999, "appended\n")
    assert "appended" in result
    assert (tmp_path / "f.py").read_text() == "line1\nappended\n"


def test_append_line_zero(tmp_path: pathlib.Path):
    _make(tmp_path, "f.py", "line1\n")
    result = write_lines("f.py", 0, "appended\n")
    assert "appended" in result
    assert (tmp_path / "f.py").read_text() == "line1\nappended\n"


def test_overwrite_lines(tmp_path: pathlib.Path):
    _make(tmp_path, "f.py", "old1\nold2\nold3\n")
    result = write_lines("f.py", 2, "new2\n", overwrite=True)
    assert "overwrote" in result
    assert (tmp_path / "f.py").read_text() == "old1\nnew2\nold3\n"


def test_overwrite_multiple(tmp_path: pathlib.Path):
    _make(tmp_path, "f.py", "a\nb\nc\nd\n")
    result = write_lines("f.py", 2, "X\nY\n", overwrite=True)
    assert "overwrote" in result
    assert (tmp_path / "f.py").read_text() == "a\nX\nY\nd\n"


def test_adds_trailing_newline(tmp_path: pathlib.Path):
    _make(tmp_path, "f.py", "line1\n")
    write_lines("f.py", 1, "no newline")
    content = (tmp_path / "f.py").read_text()
    assert content == "no newline\nline1\n"


def test_supports_undo(tmp_path: pathlib.Path):
    _make(tmp_path, "f.py", "original\n")
    write_lines("f.py", 1, "inserted\n")
    assert len(_UNDO_STACK) == 1


def test_invalid_path(tmp_path: pathlib.Path):
    result = write_lines("nope.py", 1, "x")
    assert "not a valid file" in result
