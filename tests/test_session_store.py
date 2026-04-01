from __future__ import annotations

import pathlib

import pytest

from iklab.models import SessionInfo
from iklab.session_store import load_session, save_session


def test_save_and_load(tmp_path: pathlib.Path):
    session = SessionInfo(
        session_id="test123",
        messages=({"role": "user", "content": "hello"},),
        input_tokens=10,
        output_tokens=5,
    )
    path = save_session(session, directory=tmp_path)
    assert path.exists()

    loaded = load_session("test123", directory=tmp_path)
    assert loaded.session_id == "test123"
    assert len(loaded.messages) == 1
    assert loaded.input_tokens == 10
    assert loaded.output_tokens == 5


def test_load_nonexistent(tmp_path: pathlib.Path):
    with pytest.raises(FileNotFoundError):
        load_session("nonexistent", directory=tmp_path)
