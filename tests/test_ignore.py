from __future__ import annotations

import pathlib

from iklab import ignore


def test_is_binary_known_extension():
    assert ignore.is_binary(pathlib.Path("image.png")) is True
    assert ignore.is_binary(pathlib.Path("image.PNG")) is True


def test_is_binary_text_extension():
    assert ignore.is_binary(pathlib.Path("file.py")) is False
    assert ignore.is_binary(pathlib.Path("file.txt")) is False


def test_is_ignored_always_dirs(tmp_path: pathlib.Path):
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    assert ignore.is_ignored(git_dir, tmp_path, []) is True


def test_is_ignored_pattern_match(tmp_path: pathlib.Path):
    log = tmp_path / "app.log"
    log.write_text("")
    assert ignore.is_ignored(log, tmp_path, ["*.log"]) is True


def test_is_ignored_negation(tmp_path: pathlib.Path):
    log = tmp_path / "important.log"
    log.write_text("")
    patterns = ["*.log", "!important.log"]
    assert ignore.is_ignored(log, tmp_path, patterns) is False


def test_is_ignored_no_match(tmp_path: pathlib.Path):
    py = tmp_path / "main.py"
    py.write_text("")
    assert ignore.is_ignored(py, tmp_path, ["*.log"]) is False


def test_safe_read_binary(tmp_path: pathlib.Path):
    f = tmp_path / "pic.png"
    f.write_bytes(b"\x89PNG")
    result = ignore.safe_read(f)
    assert "[binary:" in result


def test_safe_read_text(tmp_path: pathlib.Path):
    f = tmp_path / "hello.txt"
    f.write_text("hello world")
    assert ignore.safe_read(f) == "hello world"


def test_safe_read_truncates(tmp_path: pathlib.Path):
    f = tmp_path / "big.txt"
    f.write_text("x" * 100_000)
    result = ignore.safe_read(f, max_bytes=100)
    assert "truncated" in result
