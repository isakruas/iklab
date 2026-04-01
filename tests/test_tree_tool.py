from __future__ import annotations

import pathlib

import pytest

from iklab import sandbox
from iklab.tools.context import tree


@pytest.fixture(autouse=True)
def _set_workdir(tmp_path: pathlib.Path):
    sandbox.set_workdir(tmp_path)
    yield


def _make_project(tmp_path: pathlib.Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("x = 1")
    (tmp_path / "src" / "utils").mkdir()
    (tmp_path / "src" / "utils" / "helpers.py").write_text("y = 2")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_main.py").write_text("z = 3")
    (tmp_path / "README.md").write_text("# Hi")


def test_tree_shows_structure(tmp_path: pathlib.Path):
    _make_project(tmp_path)
    result = tree(".")
    assert "src/" in result
    assert "main.py" in result
    assert "utils/" in result
    assert "helpers.py" in result
    assert "tests/" in result
    assert "README.md" in result


def test_tree_uses_connectors(tmp_path: pathlib.Path):
    _make_project(tmp_path)
    result = tree(".")
    assert "├── " in result or "└── " in result


def test_tree_max_depth(tmp_path: pathlib.Path):
    _make_project(tmp_path)
    result = tree(".", max_depth=1)
    assert "src/" in result
    # helpers.py is at depth 3, should not appear with max_depth=1
    assert "helpers.py" not in result


def test_tree_subdirectory(tmp_path: pathlib.Path):
    _make_project(tmp_path)
    result = tree("src")
    assert "main.py" in result
    assert "README.md" not in result


def test_tree_invalid_path(tmp_path: pathlib.Path):
    result = tree("nonexistent")
    assert "Error" in result


def test_tree_empty_dir(tmp_path: pathlib.Path):
    (tmp_path / "empty").mkdir()
    result = tree("empty")
    # Should just show the directory name, no entries
    assert "empty/" in result
