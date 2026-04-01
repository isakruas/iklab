from __future__ import annotations

"""Ignore system: respects .gitignore, .dockerignore, .llmignore, etc."""

import fnmatch
import os
import pathlib
import re

IGNORE_FILES = (
    ".gitignore",
    ".dockerignore",
    ".llmignore",
    ".hgignore",
    ".eslintignore",
)

ALWAYS_IGNORE_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    ".next",
    ".nuxt",
    "dist",
    "build",
    ".cache",
    ".eggs",
}

BINARY_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".bmp",
    ".ico",
    ".webp",
    ".svg",
    ".mp3",
    ".mp4",
    ".avi",
    ".mov",
    ".wav",
    ".flac",
    ".zip",
    ".tar",
    ".gz",
    ".bz2",
    ".xz",
    ".rar",
    ".7z",
    ".exe",
    ".dll",
    ".so",
    ".dylib",
    ".bin",
    ".o",
    ".a",
    ".pdf",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
    ".pyc",
    ".pyo",
    ".class",
    ".jar",
    ".db",
    ".sqlite",
    ".sqlite3",
}


def load_ignore_patterns(directory: pathlib.Path) -> list[str]:
    """Load ignore patterns from all known ignore files in the tree.

    Supports:
    - Standard glob patterns (*.log, build/)
    - Negation patterns (!important.log) — these UN-ignore a file
    - Directory-only patterns (logs/) — only match directories
    """
    patterns = []
    for root, dirs, files in os.walk(directory):
        for name in IGNORE_FILES:
            fp = pathlib.Path(root) / name
            if fp.is_file():
                try:
                    for line in fp.read_text(errors="replace").splitlines():
                        line = line.strip()
                        if line and not line.startswith("#"):
                            patterns.append(line)
                except Exception:
                    pass
        dirs[:] = [d for d in dirs if d not in ALWAYS_IGNORE_DIRS]
    return patterns


def _match_pattern(rel: str, name: str, pattern: str, is_dir: bool) -> bool:
    """Match a single gitignore-style pattern against a relative path.

    Handles:
    - Simple names: *.log matches any .log file
    - Directory patterns: logs/ only matches directories
    - Rooted patterns: /build matches only at root
    - Double star: **/*.py matches at any depth
    """
    # Directory-only pattern
    if pattern.endswith("/"):
        if not is_dir:
            return False
        pattern = pattern.rstrip("/")

    # Rooted pattern (starts with /)
    if pattern.startswith("/"):
        pattern = pattern.lstrip("/")
        return fnmatch.fnmatch(rel, pattern)

    # Pattern with path separator — match against full relative path
    if "/" in pattern:
        # Handle ** (any number of directories)
        regex = _glob_to_regex(pattern)
        return bool(re.match(regex, rel))

    # Simple name pattern — match against filename only
    return fnmatch.fnmatch(name, pattern)


def _glob_to_regex(pattern: str) -> str:
    """Convert a gitignore glob pattern to a regex, with ** support."""
    parts = pattern.split("**")
    regex_parts = []
    for i, part in enumerate(parts):
        if part:
            # Convert fnmatch-style to regex for each segment
            # Escape special chars then convert glob wildcards
            segment = re.escape(part)
            segment = segment.replace(r"\*", "[^/]*")
            segment = segment.replace(r"\?", "[^/]")
            regex_parts.append(segment)
        if i < len(parts) - 1:
            regex_parts.append(".*")  # ** = any path depth
    return "^" + "".join(regex_parts) + "$"


def is_ignored(path: pathlib.Path, base: pathlib.Path, patterns: list[str]) -> bool:
    """Check if a path should be ignored based on patterns.

    Handles negation: !pattern un-ignores a previously ignored path.
    Later patterns override earlier ones (last match wins).
    """
    try:
        rel = str(path.relative_to(base))
    except ValueError:
        return False
    name = path.name
    is_dir = path.is_dir()

    # Always-ignore directories
    for part in path.relative_to(base).parts:
        if part in ALWAYS_IGNORE_DIRS:
            return True

    # Process patterns in order — last match wins (gitignore semantics)
    ignored = False
    for pattern in patterns:
        if pattern.startswith("!"):
            # Negation: un-ignore
            if _match_pattern(rel, name, pattern[1:], is_dir):
                ignored = False
        else:
            if _match_pattern(rel, name, pattern, is_dir):
                ignored = True

    return ignored


def is_binary(path: pathlib.Path) -> bool:
    return path.suffix.lower() in BINARY_EXTENSIONS


def walk_project(directory: pathlib.Path) -> list[pathlib.Path]:
    """Walk project tree respecting ignore rules. Skips symlinks pointing outside directory."""
    patterns = load_ignore_patterns(directory)
    results = []
    for root, dirs, files in os.walk(directory, followlinks=False):
        root_path = pathlib.Path(root)

        # Filter dirs: ignored + symlinks escaping sandbox
        filtered_dirs = []
        for d in sorted(dirs):
            dpath = root_path / d
            if is_ignored(dpath, directory, patterns):
                continue
            # Skip symlinks pointing outside project
            if dpath.is_symlink():
                try:
                    dpath.resolve().relative_to(directory.resolve())
                except ValueError:
                    continue
            filtered_dirs.append(d)
        dirs[:] = filtered_dirs

        for fname in sorted(files):
            fpath = root_path / fname
            # Skip symlinks pointing outside project
            if fpath.is_symlink():
                try:
                    fpath.resolve().relative_to(directory.resolve())
                except ValueError:
                    continue
            if not is_ignored(fpath, directory, patterns):
                results.append(fpath)
    return results


def safe_read(path: pathlib.Path, max_bytes: int = 50_000) -> str:
    if is_binary(path):
        try:
            size = path.stat().st_size
        except Exception:
            size = 0
        return f"[binary: {path.suffix}, {size} bytes]"
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        if len(text) > max_bytes:
            return text[:max_bytes] + f"\n... [truncated, {len(text)} chars total]"
        return text
    except Exception as e:
        return f"[error: {e}]"
