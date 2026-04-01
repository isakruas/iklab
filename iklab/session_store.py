from __future__ import annotations

import json
from pathlib import Path

from .models import SessionInfo

DEFAULT_SESSION_DIR = Path(".iklab/sessions")


def save_session(session: SessionInfo, directory: Path | None = None) -> Path:
    """Persist a SessionInfo to disk as JSON."""
    target_dir = directory or DEFAULT_SESSION_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / f"{session.session_id}.json"
    data = {
        "session_id": session.session_id,
        "messages": list(session.messages),
        "input_tokens": session.input_tokens,
        "output_tokens": session.output_tokens,
    }
    path.write_text(json.dumps(data, indent=2))
    return path


def load_session(session_id: str, directory: Path | None = None) -> SessionInfo:
    """Load a SessionInfo from disk."""
    target_dir = directory or DEFAULT_SESSION_DIR
    data = json.loads((target_dir / f"{session_id}.json").read_text())
    return SessionInfo(
        session_id=data["session_id"],
        messages=tuple(data["messages"]),
        input_tokens=data["input_tokens"],
        output_tokens=data["output_tokens"],
    )
