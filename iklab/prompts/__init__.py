from __future__ import annotations

"""Prompt loader — reads .txt prompt files so they can be edited without touching code."""

import pathlib

_DIR = pathlib.Path(__file__).parent


def load(name: str) -> str:
    """Load a prompt by name (without .txt extension)."""
    path = _DIR / f"{name}.txt"
    return path.read_text(encoding="utf-8").strip()
