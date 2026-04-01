from __future__ import annotations

"""Sandbox: all filesystem access is restricted to WORKDIR."""

import os
import pathlib

# Set once at startup by the CLI or server entry point.
WORKDIR: pathlib.Path = pathlib.Path.cwd().resolve()


def set_workdir(path: str | pathlib.Path) -> None:
    global WORKDIR
    WORKDIR = pathlib.Path(path).resolve()


def resolve(path: str) -> pathlib.Path:
    """Resolve a path relative to WORKDIR. Raises if it escapes.

    Handles: relative paths, .., symlinks, absolute paths.
    """
    # Build candidate path
    candidate = pathlib.Path(path)
    if candidate.is_absolute():
        p = candidate.resolve()
    else:
        p = (WORKDIR / candidate).resolve()

    # Strict check: must be WORKDIR itself or inside it
    try:
        p.relative_to(WORKDIR)
    except ValueError:
        raise PermissionError(f"Access denied: '{path}' resolves to '{p}' which is outside '{WORKDIR}'.")

    # Block symlinks that point outside WORKDIR
    if p.is_symlink():
        real = p.resolve()
        try:
            real.relative_to(WORKDIR)
        except ValueError:
            raise PermissionError(f"Access denied: symlink '{path}' points to '{real}' outside '{WORKDIR}'.")

    return p


def is_inside(path: pathlib.Path) -> bool:
    """Check if a resolved path is inside WORKDIR without raising."""
    try:
        path.resolve().relative_to(WORKDIR)
        return True
    except ValueError:
        return False
