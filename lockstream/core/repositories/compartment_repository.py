from __future__ import annotations

from abc import ABC, abstractmethod

from lockstream.core.entities.compartment import Compartment


class CompartmentRepository(ABC):
    """
    Repository interface for Compartment projection persistence.
    """

    @abstractmethod
    def get(self, locker_id: str, compartment_id: str) -> Compartment | None:
        """Return a single compartment by (locker_id, compartment_id), or None if missing."""
        raise NotImplementedError

    @abstractmethod
    def upsert(self, compartment: Compartment) -> None:
        """Insert or update a compartment record in the projection store."""
        raise NotImplementedError