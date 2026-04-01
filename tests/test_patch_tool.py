from __future__ import annotations

import json
import pathlib

import pytest

from iklab import sandbox
from iklab.tools.execution import patch_file


@pytest.fixture(autouse=True)
def _set_workdir(tmp_path: pathlib.Path):
    sandbox.set_workdir(tmp_path)
    yield


def _make(tmp_path: pathlib.Path, name: str, content: str) -> pathlib.Path:
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


def test_patch_single_edit(tmp_path: pathlib.Path):
    _make(tmp_path, "f.py", "x = 1\ny = 2\n")
    patches = json.dumps([{"old": "x = 1", "new": "x = 10"}])
    result = patch_file("f.py", patches)
    assert "1 edit" in result
    assert (tmp_path / "f.py").read_text() == "x = 10\ny = 2\n"


def test_patch_multiple_edits(tmp_path: pathlib.Path):
    _make(tmp_path, "f.py", "def foo():\n    return 1\n\ndef bar():\n    return 2\n")
    patches = json.dumps(
        [
            {"old": "return 1", "new": "return 10"},
            {"old": "return 2", "new": "return 20"},
        ]
    )
    result = patch_file("f.py", patches)
    assert "2 edits" in result
    assert (tmp_path / "f.py").read_text() == "def foo():\n    return 10\n\ndef bar():\n    return 20\n"


def test_patch_not_found(tmp_path: pathlib.Path):
    _make(tmp_path, "f.py", "x = 1\n")
    patches = json.dumps([{"old": "y = 2", "new": "y = 3"}])
    result = patch_file("f.py", patches)
    assert "not found" in result


def test_patch_ambiguous(tmp_path: pathlib.Path):
    _make(tmp_path, "f.py", "a\na\n")
    patches = json.dumps([{"old": "a", "new": "b"}])
    result = patch_file("f.py", patches)
    assert "appears 2 times" in result
    # File unchanged
    assert (tmp_path / "f.py").read_text() == "a\na\n"


def test_patch_invalid_json(tmp_path: pathlib.Path):
    _make(tmp_path, "f.py", "x\n")
    result = patch_file("f.py", "not json")
    assert "invalid JSON" in result


def test_patch_missing_keys(tmp_path: pathlib.Path):
    _make(tmp_path, "f.py", "x\n")
    patches = json.dumps([{"old": "x"}])
    result = patch_file("f.py", patches)
    assert "must have" in result


def test_patch_invalid_path(tmp_path: pathlib.Path):
    patches = json.dumps([{"old": "a", "new": "b"}])
    result = patch_file("nope.py", patches)
    assert "not a valid file" in result
