from __future__ import annotations

from iklab.cost_tracker import CostTracker
from iklab.history import HistoryLog
from iklab.models import TurnResult
from iklab.query_engine import QueryEngine, QueryEngineConfig
from iklab.transcript import Transcript


def _engine(
    max_turns: int = 3, max_budget: int = 1000, compact_after: int = 5
) -> QueryEngine:
    return QueryEngine(
        config=QueryEngineConfig(
            max_turns=max_turns,
            max_budget_tokens=max_budget,
            compact_after_turns=compact_after,
        ),
        transcript=Transcript(),
        cost_tracker=CostTracker(),
        history=HistoryLog(),
    )


def test_initial_state():
    eng = _engine()
    assert eng.turns == 0
    stop, reason = eng.should_stop()
    assert not stop
    assert reason == ""


def test_should_stop_after_max_turns():
    eng = _engine(max_turns=2)
    eng.record_turn(TurnResult(content="a", input_tokens=10, output_tokens=10))
    eng.record_turn(TurnResult(content="b", input_tokens=10, output_tokens=10))
    stop, reason = eng.should_stop()
    assert stop
    assert "max_turns" in reason


def test_should_stop_budget_exhausted():
    eng = _engine(max_turns=100, max_budget=50)
    eng.record_turn(TurnResult(content="a", input_tokens=30, output_tokens=25))
    stop, reason = eng.should_stop()
    assert stop
    assert "budget" in reason


def test_should_not_stop_within_limits():
    eng = _engine(max_turns=5, max_budget=10_000)
    eng.record_turn(TurnResult(content="a", input_tokens=10, output_tokens=10))
    stop, _ = eng.should_stop()
    assert not stop


def test_should_compact():
    eng = _engine(compact_after=3)
    for _ in range(3):
        eng.transcript.append({"role": "user", "content": "hi"})
    assert eng.should_compact()


def test_should_not_compact():
    eng = _engine(compact_after=10)
    eng.transcript.append({"role": "user", "content": "hi"})
    assert not eng.should_compact()


def test_record_turn_increments():
    eng = _engine()
    eng.record_turn(TurnResult(content="x", input_tokens=100, output_tokens=50))
    assert eng.turns == 1
    assert eng.cost_tracker.total_input_tokens == 100
    assert eng.cost_tracker.total_output_tokens == 50


def test_record_turn_history():
    eng = _engine()
    eng.record_turn(TurnResult(content="x", input_tokens=5, output_tokens=3))
    assert len(eng.history.events) == 1
    assert "in=5" in eng.history.events[0].detail


def test_config_defaults():
    cfg = QueryEngineConfig()
    assert cfg.max_turns == 50_000
    assert cfg.max_budget_tokens == 50_000 * 4
    assert cfg.compact_after_turns == 12
