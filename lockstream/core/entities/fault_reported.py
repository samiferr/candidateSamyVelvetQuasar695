from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class FaultReported:
    """
    Projection of a reported fault, keyed by the FaultReported domain event_id.
    """
    event_id: str
    locker_id: str
    compartment_id: str
    severity: int
    cleared: bool = False
    cleared_by_event_id: str | None = None

    def clear(self, *, cleared_by_event_id: str) -> None:
        if self.cleared:
            raise ValueError("Fault is already cleared")
        self.cleared = True
        self.cleared_by_event_id = cleared_by_event_id