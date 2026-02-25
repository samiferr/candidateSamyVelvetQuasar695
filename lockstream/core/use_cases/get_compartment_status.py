from __future__ import annotations

from dataclasses import dataclass

from lockstream.core.entities.compartment import Compartment
from lockstream.core.repositories.locker_repository import LockerRepository


class NotFoundError(Exception):
    """Raise to map to HTTP 404."""


@dataclass(frozen=True, slots=True)
class CompartmentStatusDTO:
    """
    Use-case return type for GET /lockers/{locker_id}/compartments/{compartment_id}

    Note: returns only active_reservation_id (nullable), not a reservation object.
    """
    compartment_id: str
    degraded: bool
    active_reservation: str | None


class GetCompartmentStatusUseCase:
    def __init__(self, *, locker_repo: LockerRepository) -> None:
        self._locker_repo = locker_repo

    def execute(self, *, locker_id: str, compartment_id: str) -> CompartmentStatusDTO:
        locker = self._locker_repo.get(locker_id)
        if locker is None:
            raise NotFoundError("Locker not found")

        compartment: Compartment | None = locker.compartment_index.get(compartment_id)
        if compartment is None:
            raise NotFoundError("Compartment not found")

        return CompartmentStatusDTO(
            compartment_id=compartment.compartment_id,
            degraded=compartment.degraded,
            active_reservation=compartment.active_reservation_id,
        )