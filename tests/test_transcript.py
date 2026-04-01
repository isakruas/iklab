from __future__ import annotations

from iklab.transcript import Transcript


def test_append_and_replay():
    t = Transcript()
    t.append({"role": "user", "content": "hello"})
    t.append({"role": "assistant", "content": "hi"})
    assert len(t) == 2
    assert t.replay() == (
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi"},
    )


def test_compact():
    t = Transcript()
    for i in range(20):
        t.append({"role": "user", "content": str(i)})
    assert len(t) == 20
    t.compact(keep_last=5)
    assert len(t) == 5
    assert t.entries[0]["content"] == "15"


def test_flush():
    t = Transcript()
    t.append({"role": "user", "content": "x"})
    assert t.flushed is False
    t.flush()
    assert t.flushed is True
    t.append({"role": "user", "content": "y"})
    assert t.flushed is False
