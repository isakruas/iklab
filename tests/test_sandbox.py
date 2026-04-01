from __future__ import annotations

import pathlib

import pytest

from iklab import sandbox


@pytest.fixture(autouse=True)
def _set_workdir(tmp_path: pathlib.Path):
    sandbox.set_workdir(tmp_path)
    yield


def test_resolve_relative(tmp_path: pathlib.Path):
    (tmp_path / "hello.txt").write_text("hi")
    result = sandbox.resolve("hello.txt")
    assert result == tmp_path / "hello.txt"


def test_resolve_blocks_escape(tmp_path: pathlib.Path):
    with pytest.raises(PermissionError):
        sandbox.resolve("../../etc/passwd")


def test_resolve_absolute_inside(tmp_path: pathlib.Path):
    target = tmp_path / "sub" / "file.txt"
    target.parent.mkdir()
    target.write_text("data")
    result = sandbox.resolve(str(target))
    assert result == target


def test_resolve_absolute_outside():
    with pytest.raises(PermissionError):
        sandbox.resolve("/etc/passwd")


def test_is_inside_true(tmp_path: pathlib.Path):
    p = tmp_path / "a.txt"
    p.write_text("x")
    assert sandbox.is_inside(p) is True


def test_is_inside_false():
    assert sandbox.is_inside(pathlib.Path("/etc/passwd")) is False
