"""Execution tools — write files, run commands, think, search web."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from collections import deque
from pathlib import Path

import httpx

from .. import sandbox
from ..config import get_config
from . import mcp

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
        # Fix models that send literal \n \t instead of real newlines/tabs
        if "\\n" in content and "\n" not in content:
            content = content.replace("\\n", "\n").replace("\\t", "\t")
        _snapshot(p)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        rel = p.relative_to(sandbox.WORKDIR)
        return f"[Write] OK path={rel} ({len(content)} chars)"
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
    # Fix models that send literal \n \t instead of real newlines/tabs
    if "\\n" in content and "\n" not in content:
        content = content.replace("\\n", "\n").replace("\\t", "\t")
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
    new_total = len("".join(lines).splitlines())
    return f"[WriteLines] OK path={rel} — {action} (now {new_total} lines)"


@mcp.tool(name="Edit")
def edit_file(path: str, old_string: str, new_string: str, replace_all: bool = False) -> str:
    """Replace an exact string in a file. Use for surgical edits instead of rewriting the whole file.

    - old_string must match exactly (including indentation and newlines).
    - If old_string appears more than once and replace_all is False, the edit is rejected.
    - Set replace_all=True to replace every occurrence (useful for renames).
    - new_string can be empty to delete the matched text.
    """
    # Fix models that send literal \n \t instead of real newlines/tabs
    if "\\n" in old_string and "\n" not in old_string:
        old_string = old_string.replace("\\n", "\n").replace("\\t", "\t")
    if "\\n" in new_string and "\n" not in new_string:
        new_string = new_string.replace("\\n", "\n").replace("\\t", "\t")
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
    return f"[Edit] OK path={rel} ({replacements} replacement{'s' if replacements > 1 else ''})"


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

    # Fix models that send literal \n \t instead of real newlines/tabs
    for edit in edits:
        if isinstance(edit, dict):
            for key in ("old", "new"):
                if key in edit and isinstance(edit[key], str):
                    if "\\n" in edit[key] and "\n" not in edit[key]:
                        edit[key] = edit[key].replace("\\n", "\n").replace("\\t", "\t")

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
    return f"[Patch] OK path={rel} ({len(edits)} edit{'s' if len(edits) > 1 else ''})"


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
    return f"[Move] OK {rel_src} → {rel_dst}"


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
    return f"[Delete] OK {kind}={rel}"


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
    return f"[Copy] OK {rel_src} → {rel_dst}"


@mcp.tool(name="Undo")
def undo() -> str:
    """Undo the last file write, edit, or patch. Can be called multiple times (up to 50 levels)."""
    if not _UNDO_STACK:
        return "[Undo] Nothing to undo. Stack is empty."
    p, previous = _UNDO_STACK.pop()
    rel = p.relative_to(sandbox.WORKDIR)
    remaining = len(_UNDO_STACK)
    try:
        if previous is None:
            if p.exists():
                p.unlink()
            return f"[Undo] OK removed {rel} (was newly created). {remaining} undo steps remaining."
        else:
            p.write_text(previous, encoding="utf-8")
            return f"[Undo] OK restored {rel}. {remaining} undo steps remaining."
    except Exception as e:
        return f"[Undo] Error: {e}"


# Shell tool redirect rules: if the command matches, reject and suggest the right tool.
# Each entry: (pattern_keywords, redirect_message)
_SHELL_REDIRECTS: list[tuple[list[str], str]] = [
    (
        ["touch "],
        "WRONG TOOL: Use Write(path, content) to create files, not 'touch' via Shell.",
    ),
    (
        ["mkdir "],
        "WRONG TOOL: Use Write(path, content) to create files — it auto-creates parent directories.",
    ),
    (
        ["cat ", "head ", "tail "],
        "WRONG TOOL: Use Read(path) or ReadLines(path, start, end) to read files.",
    ),
    (
        ["cp "],
        "WRONG TOOL: Use Copy(source, destination) to copy files.",
    ),
    (
        ["mv "],
        "WRONG TOOL: Use Move(source, destination) to move/rename files.",
    ),
    (
        ["rm ", "rmdir "],
        "WRONG TOOL: Use Delete(path) to delete files or directories.",
    ),
    (
        ["ls "],
        "WRONG TOOL: Use List(path) to list directory contents, or Tree(path) for recursive view.",
    ),
    (
        ["find "],
        "WRONG TOOL: Use Glob(pattern) to find files by name, or Grep(text) to search contents.",
    ),
    (
        ["grep ", "rg "],
        "WRONG TOOL: Use Grep(text, directory, extensions) to search file contents.",
    ),
    (
        ["sed ", "awk "],
        "WRONG TOOL: Use Edit(path, old_string, new_string) to modify files.",
    ),
    (
        ["echo ", "printf "],
        "WRONG TOOL: Use Write(path, content) to create/overwrite files.",
    ),
]


def _check_shell_redirect(command: str) -> str | None:
    """Return redirect message if the command should use a dedicated tool, else None."""
    cmd = command.strip()
    # Allow piped/chained commands that are genuinely complex
    if "&&" in cmd or "||" in cmd or "|" in cmd:
        return None
    for keywords, message in _SHELL_REDIRECTS:
        for kw in keywords:
            if cmd.startswith(kw) or cmd.startswith("sudo " + kw):
                return f"[Shell] {message}"
    return None


@mcp.tool(name="Shell")
def bash(command: str, timeout: int = 30) -> str:
    """Execute a shell command. ONLY for commands without a dedicated tool (tests, git, pip, etc.).

    Do NOT use for: creating files (use Write), reading files (use Read),
    editing files (use Edit), finding files (use Glob/Grep),
    copying/moving/deleting (use Copy/Move/Delete).
    """
    # Check if a specialized tool should be used instead
    redirect = _check_shell_redirect(command)
    if redirect:
        return redirect

    cfg = get_config()
    cmd_lower = command.lower().strip()
    for blocked in cfg.blocked_commands:
        if blocked in cmd_lower:
            return f"[Shell] Blocked: dangerous command detected ({blocked})"

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=min(timeout, cfg.max_bash_timeout),
            cwd=str(sandbox.WORKDIR),
        )
        parts = [f"[Shell] command={command!r}"]
        parts.append(f"exit_code={result.returncode}")
        if result.stdout:
            parts.append(f"\n=== STDOUT ===\n{result.stdout.rstrip()}")
        if result.stderr:
            parts.append(f"\n=== STDERR ===\n{result.stderr.rstrip()}")
        if not result.stdout and not result.stderr:
            parts.append("(no output)")
        return "\n".join(parts)
    except subprocess.TimeoutExpired:
        return f"[Shell] Error: command timed out after {timeout}s."
    except Exception as e:
        return f"[Shell] Error: {e}"


@mcp.tool(name="Think")
def think(task: str, context: str = "") -> str:
    """Use as a scratchpad to organize your thoughts before acting.

    Write down your reasoning, constraints, and next steps.
    The content is returned back to you unchanged — use it to structure your thinking.
    Do NOT use for questions about files or state — use Read/Grep for that.
    """
    sections = [f"[Think] task={task!r}"]
    if context:
        sections.append(f"\nContext provided:\n{context}")
    sections.append("\nYour reasoning has been recorded. Now proceed with the next action.")
    return "\n".join(sections)


@mcp.tool(name="WebSearch")
async def web_search(query: str, max_results: int = 5) -> str:
    """Search the internet via DuckDuckGo and return structured results.

    Returns up to max_results (default 5) results, each with title, URL, and snippet.
    Use WebFetch to read the full content of a specific result URL.
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }
    url = "https://lite.duckduckgo.com/lite/"
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.post(url, data={"q": query}, headers=headers)
            resp.raise_for_status()
            html = resp.text
    except Exception as e:
        return f"Search error: {e}"

    # Parse DDG Lite format: <a ... class='result-link'>Title</a> followed by <td class='result-snippet'>
    results: list[dict[str, str]] = []
    limit = min(max_results, 10)

    # Split by result-link anchors (skip ads by filtering duckduckgo.com/y.js URLs)
    parts = html.split("class='result-link'>")
    for part in parts[1:]:
        if len(results) >= limit:
            break

        # Extract title (text before </a>)
        title_end = part.find("</a>")
        if title_end == -1:
            continue
        title = part[:title_end].strip()
        # Decode HTML entities
        title = title.replace("&#x27;", "'").replace("&amp;", "&").replace("&quot;", '"')

        # Extract URL from href before class='result-link'
        # Look backwards in the original html for the href
        chunk_before = html.split("class='result-link'>" + part[:title_end])[0]
        href = ""
        href_marker = 'href="'
        last_href = chunk_before.rfind(href_marker)
        if last_href != -1:
            href_start = last_href + len(href_marker)
            href_end = chunk_before.find('"', href_start)
            href = chunk_before[href_start:href_end]
            href = href.replace("&amp;", "&")

        # Skip ads (duckduckgo.com redirect URLs)
        if "duckduckgo.com/y.js" in href or not href:
            continue

        # Extract snippet (next result-snippet td)
        snippet = ""
        snippet_marker = "class='result-snippet'>"
        sm = part.find(snippet_marker)
        if sm != -1:
            ss = sm + len(snippet_marker)
            se = part.find("</td>", ss)
            if se != -1:
                snippet = part[ss:se].strip()
                snippet = re.sub(r"<[^>]+>", "", snippet)
                snippet = snippet.replace("&#x27;", "'").replace("&amp;", "&")

        if title:
            results.append({"title": title, "url": href, "snippet": snippet})

    if not results:
        return f"[WebSearch] query={query!r} — no results found."

    lines = [f"[WebSearch] query={query!r} ({len(results)} results)", ""]
    for i, r in enumerate(results, 1):
        lines.append(f"[{i}] {r['title']}")
        lines.append(f"    URL: {r['url']}")
        if r["snippet"]:
            lines.append(f"    {r['snippet']}")
        lines.append("")

    lines.append("TIP: Use WebFetch(url=<URL>) to read the full content of any result above.")
    return "\n".join(lines)


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
            resp = await client.get(
                url,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
                        " (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                    ),
                },
            )
            resp.raise_for_status()
    except Exception as e:
        return f"[WebFetch] Error fetching {url}: {e}"

    content_type = resp.headers.get("content-type", "")
    status = resp.status_code
    header = f"[WebFetch] url={url} status={status} type={content_type.split(';')[0]}"

    # JSON response — return formatted
    if "json" in content_type:
        try:
            data = resp.json()
            body = json.dumps(data, indent=2, ensure_ascii=False)[:40_000]
        except Exception:
            body = resp.text[:40_000]
        return f"{header}\n\n{body}"

    # Plain text
    if "text/plain" in content_type:
        return f"{header}\n\n{resp.text[:40_000]}"

    # HTML — convert to readable text
    if "html" in content_type or resp.text.strip().startswith("<"):
        body = _html_to_text(resp.text)
        return f"{header}\n\n{body}"

    # Anything else — return raw text or binary notice
    try:
        return f"{header}\n\n{resp.text[:40_000]}"
    except Exception:
        return f"{header}\nBinary content ({len(resp.content)} bytes)"


# ---------------------------------------------------------------------------
# Tool metadata for registry
# ---------------------------------------------------------------------------
TOOL_METADATA = [
    {
        "name": "Write",
        "category": "execution",
        "description": "Create or overwrite an entire file. Use Edit for small changes to existing files.",
        "source_module": "tools.execution",
    },
    {
        "name": "WriteLines",
        "category": "execution",
        "description": "Insert or overwrite text at a specific line number. Use with ReadLines to edit by line.",
        "source_module": "tools.execution",
    },
    {
        "name": "Edit",
        "category": "execution",
        "description": "Replace an exact string in a file. Use Patch for multiple edits at once.",
        "source_module": "tools.execution",
    },
    {
        "name": "Patch",
        "category": "execution",
        "description": "Apply multiple edits to a file in one call. More efficient than calling Edit several times.",
        "source_module": "tools.execution",
    },
    {
        "name": "Move",
        "category": "execution",
        "description": "Move or rename a file or directory. Use Copy to keep the original.",
        "source_module": "tools.execution",
    },
    {
        "name": "Delete",
        "category": "execution",
        "description": "Delete a file or directory permanently. Use Undo to revert file edits instead.",
        "source_module": "tools.execution",
    },
    {
        "name": "Copy",
        "category": "execution",
        "description": "Copy a file or directory to a new location. Original is kept intact.",
        "source_module": "tools.execution",
    },
    {
        "name": "Undo",
        "category": "execution",
        "description": "Revert the last Write, WriteLines, Edit, or Patch. Supports up to 50 undo levels.",
        "source_module": "tools.execution",
    },
    {
        "name": "Shell",
        "category": "execution",
        "description": "Execute a shell command in the working directory. Use for git, npm, pip, tests, etc.",
        "source_module": "tools.execution",
    },
    {
        "name": "Think",
        "category": "execution",
        "description": "Reason step-by-step about a problem before acting. Not for reading files — use Read for that.",
        "source_module": "tools.execution",
    },
    {
        "name": "WebSearch",
        "category": "execution",
        "description": "Search the web via DuckDuckGo. Use WebFetch to read a specific result URL.",
        "source_module": "tools.execution",
    },
    {
        "name": "WebFetch",
        "category": "execution",
        "description": "Fetch a URL and return readable text. Use to read docs, pages, or API responses.",
        "source_module": "tools.execution",
    },
]
