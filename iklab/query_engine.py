"""Query engine — controls budget, turn limits, and transcript compaction."""

from __future__ import annotations

from dataclasses import dataclass

from .cost_tracker import CostTracker
from .history import HistoryLog
from .models import TurnResult
from .transcript import Transcript


@dataclass(frozen=True)
class QueryEngineConfig:
    """Thresholds that govern the conversation loop."""

    max_turns: int = 200
    max_budget_tokens: int = 1_000_000
    compact_after_entries: int = 60


@dataclass
class QueryEngine:
    """Runtime monitor wired into the agent chat loop."""

    config: QueryEngineConfig
    transcript: Transcript
    cost_tracker: CostTracker
    history: HistoryLog
    turns: int = 0

    def should_stop(self) -> tuple[bool, str]:
        """Return ``(True, reason)`` if the loop should break."""
        if self.turns >= self.config.max_turns:
            return True, f"max_turns ({self.config.max_turns}) reached"
        total = self.cost_tracker.summary().total_tokens
        if total >= self.config.max_budget_tokens:
            return True, f"budget ({self.config.max_budget_tokens} tokens) exhausted"
        return False, ""

    def should_compact(self) -> bool:
        """Return True when the transcript is long enough to compact."""
        return len(self.transcript) >= self.config.compact_after_entries

    def reset(self) -> None:
        """Reset turn counter (used by /reset command)."""
        self.turns = 0

    def record_turn(self, result: TurnResult) -> None:
        """Record a completed turn and its token usage."""
        self.turns += 1
        if result.input_tokens or result.output_tokens:
            self.cost_tracker.record_usage(result.input_tokens, result.output_tokens)
        self.history.add(
            "turn",
            f"#{self.turns} in={result.input_tokens} out={result.output_tokens}",
        )
