from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Transcript:
    """Mutable store for conversation messages with compaction support."""

    entries: list[dict] = field(default_factory=list)
    flushed: bool = False

    def append(self, entry: dict) -> None:
        self.entries.append(entry)
        self.flushed = False

    def compact(self, keep_last: int = 10) -> None:
        """Keep only the most recent *keep_last* entries."""
        if len(self.entries) > keep_last:
            self.entries[:] = self.entries[-keep_last:]

    def replay(self) -> tuple[dict, ...]:
        """Return an immutable snapshot of all entries."""
        return tuple(self.entries)

    def flush(self) -> None:
        """Mark transcript as flushed (persisted)."""
        self.flushed = True

    def __len__(self) -> int:
        return len(self.entries)
