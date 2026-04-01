from __future__ import annotations

from iklab.history import HistoryEvent, HistoryLog


def test_history_event_frozen():
    import pytest

    e = HistoryEvent(title="test", detail="detail")
    with pytest.raises(AttributeError):
        e.title = "other"


def test_history_log_add():
    log = HistoryLog()
    log.add("tool_call", "Read -> ok")
    assert len(log.events) == 1
    assert log.events[0].title == "tool_call"


def test_as_markdown():
    log = HistoryLog()
    log.add("start", "Session started")
    log.add("end", "Session ended")
    md = log.as_markdown()
    assert "# Session History" in md
    assert "- start: Session started" in md
