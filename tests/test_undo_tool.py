from __future__ import annotations

import pathlib

import pytest

from iklab import sandbox
from iklab.tools.execution import _UNDO_STACK, edit_file, undo, write_file


@pytest.fixture(autouse=True)
def _set_workdir(tmp_path: pathlib.Path):
    sandbox.set_workdir(tmp_path)
    _UNDO_STACK.clear()
    yield


def test_undo_write_existing_file(tmp_path: pathlib.Path):
    (tmp_path / "f.py").write_text("original")
    write_file("f.py", "changed")
    assert (tmp_path / "f.py").read_text() == "changed"

    result = undo()
    assert "restored" in result
    assert (tmp_path / "f.py").read_text() == "original"


def test_undo_write_new_file(tmp_path: pathlib.Path):
    write_file("new.py", "content")
    assert (tmp_path / "new.py").exists()

    result = undo()
    assert "removed" in result
    assert not (tmp_path / "new.py").exists()


def test_undo_edit(tmp_path: pathlib.Path):
    (tmp_path / "f.py").write_text("x = 1\n")
    edit_file("f.py", "x = 1", "x = 2")
    assert "x = 2" in (tmp_path / "f.py").read_text()

    result = undo()
    assert "restored" in result
    assert (tmp_path / "f.py").read_text() == "x = 1\n"


def test_undo_multiple(tmp_path: pathlib.Path):
    (tmp_path / "f.py").write_text("v1")
    write_file("f.py", "v2")
    write_file("f.py", "v3")

    undo()
    assert (tmp_path / "f.py").read_text() == "v2"
    undo()
    assert (tmp_path / "f.py").read_text() == "v1"


def test_undo_empty_stack(tmp_path: pathlib.Path):
    result = undo()
    assert "Nothing to undo" in result
