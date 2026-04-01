from __future__ import annotations

from dataclasses import dataclass, field

from .models import UsageSummary


@dataclass
class CostTracker:
    """Tracks token usage across an agent session."""

    total_input_tokens: int = 0
    total_output_tokens: int = 0
    events: list[str] = field(default_factory=list)

    def record_usage(self, input_tokens: int, output_tokens: int) -> None:
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.events.append(f"in={input_tokens},out={output_tokens}")

    def summary(self) -> UsageSummary:
        return UsageSummary(
            input_tokens=self.total_input_tokens,
            output_tokens=self.total_output_tokens,
        )
