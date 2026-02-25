from __future__ import annotations

from abc import ABC, abstractmethod

from lockstream.core.entities.event import Event


class EventRepository(ABC):
    @abstractmethod
    def add_if_absent(self, event: Event) -> bool:
        """Return True if inserted, False if duplicate (same event_id)."""
        raise NotImplementedError
