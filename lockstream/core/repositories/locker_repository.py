from __future__ import annotations

from abc import ABC, abstractmethod

from lockstream.core.entities.locker import Locker


class LockerRepository(ABC):
    @abstractmethod
    def get(self, locker_id: str) -> Locker | None:
        """Aggregate load: locker + compartments only (no reservations)."""
        raise NotImplementedError

    @abstractmethod
    def upsert(self, locker: Locker) -> None:
        """Create or update a locker aggregate (summary + compartments) as one unit."""
        raise NotImplementedError
