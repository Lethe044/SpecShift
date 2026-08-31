"""Data models representing diff results."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class Severity(str, Enum):
    """Severity level of a detected change."""

    BREAKING = "breaking"
    WARNING = "warning"
    INFO = "info"

    @property
    def rank(self) -> int:
        return {"breaking": 2, "warning": 1, "info": 0}[self.value]

    @property
    def icon(self) -> str:
        return {"breaking": "[BREAKING]", "warning": "[WARNING]", "info": "[INFO]"}[self.value]


class ChangeType(str, Enum):
    """The type of change that occurred."""

    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"


@dataclass
class Change:
    """Represents a single change between the old and new specification."""

    severity: Severity
    change_type: ChangeType
    location: str
    message: str
    old_value: Optional[Any] = None
    new_value: Optional[Any] = None
    category: str = "general"

    def to_dict(self) -> dict:
        return {
            "severity": self.severity.value,
            "change_type": self.change_type.value,
            "location": self.location,
            "message": self.message,
            "old_value": _safe_repr(self.old_value),
            "new_value": _safe_repr(self.new_value),
            "category": self.category,
        }


def _safe_repr(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (list, tuple, set)):
        return [str(v) for v in value]
    return str(value)


@dataclass
class DiffResult:
    """The aggregated result of all changes between two specifications."""

    changes: list[Change] = field(default_factory=list)
    old_title: str = ""
    new_title: str = ""
    old_version: str = ""
    new_version: str = ""

    def add(self, change: Change) -> None:
        self.changes.append(change)

    @property
    def breaking_changes(self) -> list[Change]:
        return [c for c in self.changes if c.severity == Severity.BREAKING]

    @property
    def warnings(self) -> list[Change]:
        return [c for c in self.changes if c.severity == Severity.WARNING]

    @property
    def info_changes(self) -> list[Change]:
        return [c for c in self.changes if c.severity == Severity.INFO]

    @property
    def has_breaking_changes(self) -> bool:
        return len(self.breaking_changes) > 0

    @property
    def is_empty(self) -> bool:
        return len(self.changes) == 0

    def sorted_changes(self) -> list[Change]:
        return sorted(self.changes, key=lambda c: (-c.severity.rank, c.location))

    def summary_counts(self) -> dict:
        return {
            "breaking": len(self.breaking_changes),
            "warning": len(self.warnings),
            "info": len(self.info_changes),
            "total": len(self.changes),
        }
