from __future__ import annotations

import pathlib

import pytest

from iklab import sandbox
from iklab.tools.execution import copy_path


@pytest.fixture(autouse=True)
def _set_workdir(tmp_path: pathlib.Path):
    sandbox.set_workdir(tmp_path)
    yield


def test_copy_file(tmp_path: pathlib.Path):
    (tmp_path / "a.txt").write_text("hello")
    result = copy_path("a.txt", "b.txt")
    assert "→" in result
    assert (tmp_path / "a.txt").read_text() == "hello"  # original intact
    assert (tmp_path / "b.txt").read_text() == "hello"


def test_copy_into_new_dir(tmp_path: pathlib.Path):
    (tmp_path / "a.txt").write_text("data")
    result = copy_path("a.txt", "sub/deep/a.txt")
    assert "→" in result
    assert (tmp_path / "sub" / "deep" / "a.txt").read_text() == "data"


def test_copy_directory(tmp_path: pathlib.Path):
    d = tmp_path / "src"
    d.mkdir()
    (d / "f.py").write_text("code")
    result = copy_path("src", "src_backup")
    assert "→" in result
    assert (tmp_path / "src" / "f.py").read_text() == "code"  # original intact
    assert (tmp_path / "src_backup" / "f.py").read_text() == "code"


def test_copy_nonexistent(tmp_path: pathlib.Path):
    result = copy_path("nope.txt", "dest.txt")
    assert "does not exist" in result
