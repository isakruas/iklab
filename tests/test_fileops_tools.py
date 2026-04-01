from __future__ import annotations

import pathlib

import pytest

from iklab import sandbox
from iklab.tools.execution import delete_path, move_path


@pytest.fixture(autouse=True)
def _set_workdir(tmp_path: pathlib.Path):
    sandbox.set_workdir(tmp_path)
    yield


# --- Move ---


def test_move_file(tmp_path: pathlib.Path):
    (tmp_path / "a.txt").write_text("hello")
    result = move_path("a.txt", "b.txt")
    assert "→" in result
    assert not (tmp_path / "a.txt").exists()
    assert (tmp_path / "b.txt").read_text() == "hello"


def test_move_into_new_dir(tmp_path: pathlib.Path):
    (tmp_path / "a.txt").write_text("data")
    result = move_path("a.txt", "sub/deep/a.txt")
    assert "→" in result
    assert (tmp_path / "sub" / "deep" / "a.txt").read_text() == "data"


def test_move_directory(tmp_path: pathlib.Path):
    d = tmp_path / "src"
    d.mkdir()
    (d / "f.py").write_text("code")
    result = move_path("src", "lib")
    assert "→" in result
    assert (tmp_path / "lib" / "f.py").read_text() == "code"
    assert not d.exists()


def test_move_nonexistent(tmp_path: pathlib.Path):
    result = move_path("nope.txt", "dest.txt")
    assert "does not exist" in result


# --- Delete ---


def test_delete_file(tmp_path: pathlib.Path):
    (tmp_path / "a.txt").write_text("bye")
    result = delete_path("a.txt")
    assert "Deleted file" in result
    assert not (tmp_path / "a.txt").exists()


def test_delete_directory(tmp_path: pathlib.Path):
    d = tmp_path / "stuff"
    d.mkdir()
    (d / "f.txt").write_text("x")
    result = delete_path("stuff")
    assert "Deleted directory" in result
    assert not d.exists()


def test_delete_nonexistent(tmp_path: pathlib.Path):
    result = delete_path("ghost.txt")
    assert "does not exist" in result
