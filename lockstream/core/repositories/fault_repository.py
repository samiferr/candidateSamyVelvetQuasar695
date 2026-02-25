from __future__ import annotations

from abc import ABC, abstractmethod

from lockstream.core.entities.fault_reported import FaultReported


class FaultRepository(ABC):
    @abstractmethod
    def get(self, fault_event_id: str) -> FaultReported | None:
        raise NotImplementedError

    @abstractmethod
    def upsert(self, fault: FaultReported) -> None:
        raise NotImplementedError

    @abstractmethod
    def active_summary(self, *, locker_id: str, compartment_id: str) -> tuple[int, bool]:
        """
        Returns (active_faults_count, any_active_fault_ge_threshold)
        """
        raise NotImplementedError