"""Execution tools — write files, run commands, think, search web."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from collections import deque
from pathlib import Path

import httpx

from .. import model, sandbox
from ..config import get_config
from ..prompts import load
from . import mcp

AGENT_SYSTEM = load("system")

# Undo stack: stores (path, previous_content_or_None) for file mutations.
# None means the file did not exist before (was created).
_UNDO_STACK: deque[tuple[Path, str | None]] = deque(maxlen=50)


def _snapshot(p: Path) -> None:
    """Save current file state to undo stack before mutating."""
    if p.is_file():
        try:
            _UNDO_STACK.append((p, p.read_text(encoding="utf-8")))
        except Exception:
            pass
    else:
        _UNDO_STACK.append((p, None))


@mcp.tool(name="Write")
def write_file(path: str, content: str) -> str:
    """Create or overwrite a file."""
    p = sandbox.resolve(path)
    try:
        _snapshot(p)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"Written: {p.relative_to(sandbox.WORKDIR)} ({len(content)} chars)"
    except Exception as e:
        return f"Error: {e}"


@mcp.tool(name="WriteLines")
def write_lines(path: str, line: int, content: str, overwrite: bool = False) -> str:
    """Insert or overwrite text at a specific line number. Lines are 1-indexed.

    - By default, inserts content BEFORE the given line (existing lines shift down).
    - Set overwrite=True to replace lines starting at the given position.
    - Use line=0 or line past end-of-file to append at the end.
    - content can be multiple lines (separated by newlines).
    """
    p = sandbox.resolve(path)
    if not p.is_file():
        return f"Error: '{path}' is not a valid file."
    try:
        original = p.read_text(encoding="utf-8")
    except Exception as e:
        return f"Error reading file: {e}"

    _snapshot(p)

    lines = original.splitlines(keepends=True)
    new_lines = content.splitlines(keepends=True)
    # Ensure each new line ends with \n
    if new_lines and not new_lines[-1].endswith("\n"):
        new_lines[-1] += "\n"

    total = len(lines)

    # Append mode
    if line <= 0 or line > total:
        lines.extend(new_lines)
        action = "appended"
    elif overwrite:
        # Replace len(new_lines) lines starting at position
        idx = line - 1
        end_idx = min(idx + len(new_lines), total)
        lines[idx:end_idx] = new_lines
        action = f"overwrote lines {line}-{min(line + len(new_lines) - 1, total)}"
    else:
        # Insert before line
        idx = line - 1
        lines[idx:idx] = new_lines
        action = f"inserted {len(new_lines)} line{'s' if len(new_lines) > 1 else ''} at line {line}"

    try:
        p.write_text("".join(lines), encoding="utf-8")
    except Exception as e:
        return f"Error writing file: {e}"

    rel = p.relative_to(sandbox.WORKDIR)
    return f"WriteLines: {rel} — {action}"


@mcp.tool(name="Edit")
def edit_file(path: str, old_string: str, new_string: str, replace_all: bool = False) -> str:
    """Replace an exact string in a file. Use for surgical edits instead of rewriting the whole file.

    - old_string must match exactly (including indentation and newlines).
    - If old_string appears more than once and replace_all is False, the edit is rejected.
    - Set replace_all=True to replace every occurrence (useful for renames).
    - new_string can be empty to delete the matched text.
    """
    p = sandbox.resolve(path)
    if not p.is_file():
        return f"Error: '{path}' is not a valid file."
    try:
        content = p.read_text(encoding="utf-8")
    except Exception as e:
        return f"Error reading file: {e}"

    count = content.count(old_string)
    if count == 0:
        return "Error: old_string not found in file. Make sure it matches exactly (including whitespace)."
    if count > 1 and not replace_all:
        return (
            f"Error: old_string appears {count} times. Provide more context to make it unique, or set replace_all=True."
        )

    _snapshot(p)

    if replace_all:
        new_content = content.replace(old_string, new_string)
    else:
        new_content = content.replace(old_string, new_string, 1)

    try:
        p.write_text(new_content, encoding="utf-8")
    except Exception as e:
        return f"Error writing file: {e}"

    rel = p.relative_to(sandbox.WORKDIR)
    replacements = count if replace_all else 1
    return f"Edited: {rel} ({replacements} replacement{'s' if replacements > 1 else ''})"


@mcp.tool(name="Patch")
def patch_file(path: str, patches: str) -> str:
    """Apply multiple edits to a file in one call. More efficient than multiple Edit calls.

    patches is a JSON array of objects, each with "old" and "new" keys:
      [{"old": "original text", "new": "replacement"}, ...]

    All patches are validated before any is applied. Fails if any "old" is not found
    or is ambiguous (appears more than once).
    """
    p = sandbox.resolve(path)
    if not p.is_file():
        return f"Error: '{path}' is not a valid file."
    try:
        content = p.read_text(encoding="utf-8")
    except Exception as e:
        return f"Error reading file: {e}"

    try:
        edits = json.loads(patches)
    except json.JSONDecodeError as e:
        return f"Error: invalid JSON in patches — {e}"

    if not isinstance(edits, list) or not edits:
        return "Error: patches must be a non-empty JSON array."

    # Validate all patches before applying
    for i, edit in enumerate(edits):
        if not isinstance(edit, dict) or "old" not in edit or "new" not in edit:
            return f"Error: patch {i} must have 'old' and 'new' keys."
        count = content.count(edit["old"])
        if count == 0:
            preview = edit["old"][:60]
            return f"Error: patch {i} old text not found: {preview!r}"
        if count > 1:
            return f"Error: patch {i} old text appears {count} times. Add more context to make it unique."

    _snapshot(p)

    # Apply patches sequentially
    for edit in edits:
        content = content.replace(edit["old"], edit["new"], 1)

    try:
        p.write_text(content, encoding="utf-8")
    except Exception as e:
        return f"Error writing file: {e}"

    rel = p.relative_to(sandbox.WORKDIR)
    return f"Patched: {rel} ({len(edits)} edit{'s' if len(edits) > 1 else ''})"


@mcp.tool(name="Move")
def move_path(source: str, destination: str) -> str:
    """Move or rename a file or directory. Creates parent directories as needed."""
    src = sandbox.resolve(source)
    dst = sandbox.resolve(destination)
    if not src.exists():
        return f"Error: '{source}' does not exist."
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
    except Exception as e:
        return f"Error: {e}"
    rel_src = src.relative_to(sandbox.WORKDIR)
    rel_dst = dst.relative_to(sandbox.WORKDIR)
    return f"Moved: {rel_src} → {rel_dst}"


@mcp.tool(name="Delete")
def delete_path(path: str) -> str:
    """Delete a file or directory (recursively). Use with caution."""
    p = sandbox.resolve(path)
    if not p.exists():
        return f"Error: '{path}' does not exist."
    try:
        if p.is_dir():
            shutil.rmtree(p)
            kind = "directory"
        else:
            p.unlink()
            kind = "file"
    except Exception as e:
        return f"Error: {e}"
    rel = p.relative_to(sandbox.WORKDIR)
    return f"Deleted {kind}: {rel}"


@mcp.tool(name="Copy")
def copy_path(source: str, destination: str) -> str:
    """Copy a file or directory. Creates parent directories as needed."""
    src = sandbox.resolve(source)
    dst = sandbox.resolve(destination)
    if not src.exists():
        return f"Error: '{source}' does not exist."
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(str(src), str(dst))
        else:
            shutil.copy2(str(src), str(dst))
    except Exception as e:
        return f"Error: {e}"
    rel_src = src.relative_to(sandbox.WORKDIR)
    rel_dst = dst.relative_to(sandbox.WORKDIR)
    return f"Copied: {rel_src} → {rel_dst}"


@mcp.tool(name="Undo")
def undo() -> str:
    """Undo the last file write, edit, or patch. Can be called multiple times (up to 50 levels)."""
    if not _UNDO_STACK:
        return "Nothing to undo."
    p, previous = _UNDO_STACK.pop()
    rel = p.relative_to(sandbox.WORKDIR)
    try:
        if previous is None:
            # File was created — remove it
            if p.exists():
                p.unlink()
            return f"Undo: removed {rel} (was newly created)"
        else:
            p.write_text(previous, encoding="utf-8")
            return f"Undo: restored {rel}"
    except Exception as e:
        return f"Error during undo: {e}"


@mcp.tool(name="Shell")
def bash(command: str, timeout: int = 30) -> str:
    """Execute a shell command (sandboxed to working directory)."""
    cfg = get_config()
    cmd_lower = command.lower().strip()
    for blocked in cfg.blocked_commands:
        if blocked in cmd_lower:
            return f"Blocked: dangerous command detected ({blocked})"

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=min(timeout, cfg.max_bash_timeout),
            cwd=str(sandbox.WORKDIR),
        )
        output = ""
        if result.stdout:
            output += result.stdout
        if result.stderr:
            output += "\n[STDERR]\n" + result.stderr
        output += f"\n[exit code: {result.returncode}]"
        return output.strip()
    except subprocess.TimeoutExpired:
        return f"Error: timed out after {timeout}s."
    except Exception as e:
        return f"Error: {e}"


@mcp.tool(name="Think")
async def think(task: str, context: str = "") -> str:
    """Reason about HOW to solve a problem or make a technical decision.

    Do NOT use for questions about files or state.
    """
    prompt = f"Task:\n{task}"
    if context:
        prompt += f"\n\nContext:\n{context}"
    return await model.ask(AGENT_SYSTEM, prompt)


@mcp.tool(name="WebSearch")
async def web_search(query: str) -> str:
    """Search the internet via DuckDuckGo."""
    url = "https://html.duckduckgo.com/html/"
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.post(url, data={"q": query})
            resp.raise_for_status()
            html = resp.text
    except Exception as e:
        return f"Search error: {e}"

    results = []
    parts = html.split('class="result__a"')
    for part in parts[1:11]:
        title_end = part.find("</a>")
        if title_end == -1:
            continue
        chunk = part[:title_end]
        ts = chunk.rfind(">")
        title = chunk[ts + 1 :].strip() if ts != -1 else ""

        hs = part.find('href="')
        href = ""
        if hs != -1:
            he = part.find('"', hs + 6)
            href = part[hs + 6 : he]

        snippet = ""
        sm = part.find('class="result__snippet"')
        if sm != -1:
            ss = part.find(">", sm) + 1
            se = part.find("</", ss)
            snippet = part[ss:se].strip().replace("<b>", "").replace("</b>", "")

        if title:
            results.append(f"- {title}\n  {href}\n  {snippet}")

    return "\n\n".join(results) if results else "No results found."


def _html_to_text(html: str, max_chars: int = 40_000) -> str:
    """Minimal HTML-to-text converter. Strips tags and collapses whitespace."""
    # Remove script and style blocks
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE)
    # Convert common block elements to newlines
    text = re.sub(r"<(br|hr|/p|/div|/li|/tr|/h[1-6])[^>]*>", "\n", text, flags=re.IGNORECASE)
    # Strip all remaining tags
    text = re.sub(r"<[^>]+>", "", text)
    # Decode common entities
    entities = [("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"'), ("&#39;", "'"), ("&nbsp;", " ")]
    for entity, char in entities:
        text = text.replace(entity, char)
    # Collapse whitespace
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()
    if len(text) > max_chars:
        text = text[:max_chars] + f"\n\n[Truncated at {max_chars} chars]"
    return text


@mcp.tool(name="WebFetch")
async def web_fetch(url: str) -> str:
    """Fetch a URL and return its content as readable text.

    Use for reading documentation, API responses, error pages, blog posts, etc.
    HTML is converted to plain text. JSON is returned formatted.
    """
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": "iklab/0.1"})
            resp.raise_for_status()
    except Exception as e:
        return f"Fetch error: {e}"

    content_type = resp.headers.get("content-type", "")

    # JSON response — return formatted
    if "json" in content_type:
        try:
            data = resp.json()
            return json.dumps(data, indent=2, ensure_ascii=False)[:40_000]
        except Exception:
            return resp.text[:40_000]

    # Plain text
    if "text/plain" in content_type:
        return resp.text[:40_000]

    # HTML — convert to readable text
    if "html" in content_type or resp.text.strip().startswith("<"):
        return _html_to_text(resp.text)

    # Anything else — return raw text or binary notice
    try:
        return resp.text[:40_000]
    except Exception:
        return f"Binary content ({content_type}, {len(resp.content)} bytes)"


# ---------------------------------------------------------------------------
# Tool metadata for registry
# ---------------------------------------------------------------------------
TOOL_METADATA = [
    {
        "name": "Write",
        "category": "execution",
        "description": "Create or overwrite a file.",
        "source_module": "tools.execution",
    },
    {
        "name": "WriteLines",
        "category": "execution",
        "description": "Insert or overwrite text at a specific line number.",
        "source_module": "tools.execution",
    },
    {
        "name": "Edit",
        "category": "execution",
        "description": "Replace an exact string in a file. Surgical edits without rewriting the whole file.",
        "source_module": "tools.execution",
    },
    {
        "name": "Patch",
        "category": "execution",
        "description": "Apply multiple edits to a file in one call.",
        "source_module": "tools.execution",
    },
    {
        "name": "Move",
        "category": "execution",
        "description": "Move or rename a file or directory.",
        "source_module": "tools.execution",
    },
    {
        "name": "Delete",
        "category": "execution",
        "description": "Delete a file or directory recursively.",
        "source_module": "tools.execution",
    },
    {
        "name": "Copy",
        "category": "execution",
        "description": "Copy a file or directory.",
        "source_module": "tools.execution",
    },
    {
        "name": "Undo",
        "category": "execution",
        "description": "Undo the last file write, edit, or patch.",
        "source_module": "tools.execution",
    },
    {
        "name": "Shell",
        "category": "execution",
        "description": "Execute a shell command (sandboxed to working directory).",
        "source_module": "tools.execution",
    },
    {
        "name": "Think",
        "category": "execution",
        "description": "Reason about HOW to solve a problem or make a technical decision.",
        "source_module": "tools.execution",
    },
    {
        "name": "WebSearch",
        "category": "execution",
        "description": "Search the internet via DuckDuckGo.",
        "source_module": "tools.execution",
    },
    {
        "name": "WebFetch",
        "category": "execution",
        "description": "Fetch a URL and return its content as readable text.",
        "source_module": "tools.execution",
    },
]
