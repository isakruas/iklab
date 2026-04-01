from __future__ import annotations

from iklab.cost_tracker import CostTracker


def test_record_and_summary():
    ct = CostTracker()
    ct.record_usage(100, 50)
    ct.record_usage(200, 100)
    s = ct.summary()
    assert s.input_tokens == 300
    assert s.output_tokens == 150
    assert s.total_tokens == 450


def test_events_logged():
    ct = CostTracker()
    ct.record_usage(10, 5)
    assert len(ct.events) == 1
    assert "in=10" in ct.events[0]
