from __future__ import annotations

import pathlib

import pytest

from iklab import sandbox
from iklab.tools.context import read_lines


@pytest.fixture(autouse=True)
def _set_workdir(tmp_path: pathlib.Path):
    sandbox.set_workdir(tmp_path)
    yield


def _make(tmp_path: pathlib.Path, name: str, lines: int) -> pathlib.Path:
    content = "\n".join(f"line {i}" for i in range(1, lines + 1)) + "\n"
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


def test_read_first_lines(tmp_path: pathlib.Path):
    _make(tmp_path, "big.py", 100)
    result = read_lines("big.py", 1, 5)
    assert "lines 1-5 of 100" in result
    assert "line 1" in result
    assert "line 5" in result
    assert "line 6" not in result


def test_read_middle(tmp_path: pathlib.Path):
    _make(tmp_path, "big.py", 100)
    result = read_lines("big.py", 50, 55)
    assert "lines 50-55 of 100" in result
    assert "line 50" in result
    assert "line 55" in result


def test_end_clamped_to_total(tmp_path: pathlib.Path):
    _make(tmp_path, "small.py", 10)
    result = read_lines("small.py", 8, 999)
    assert "lines 8-10 of 10" in result


def test_start_out_of_range(tmp_path: pathlib.Path):
    _make(tmp_path, "small.py", 5)
    result = read_lines("small.py", 20, 30)
    assert "out of range" in result


def test_end_less_than_start(tmp_path: pathlib.Path):
    _make(tmp_path, "f.py", 10)
    result = read_lines("f.py", 5, 3)
    assert "Error" in result


def test_invalid_path(tmp_path: pathlib.Path):
    result = read_lines("nope.py")
    assert "not a valid file" in result


def test_line_numbers_shown(tmp_path: pathlib.Path):
    _make(tmp_path, "f.py", 10)
    result = read_lines("f.py", 3, 3)
    assert "3\t" in result
