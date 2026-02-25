from __future__ import annotations

from dataclasses import dataclass

from lockstream.core.entities.locker import Locker
from lockstream.core.repositories.locker_repository import LockerRepository


class NotFoundError(Exception):
    """Raise to map to HTTP 404."""


@dataclass(frozen=True, slots=True)
class LockerSummaryDTO:
    """
    Use-case return type for GET /lockers/{locker_id}
    """
    locker_id: str
    compartments: int
    active_reservations: int
    degraded_compartments: int
    state_hash: str


class GetLockerSummaryUseCase:
    def __init__(self, *, locker_repo: LockerRepository) -> None:
        self._locker_repo = locker_repo

    def execute(self, *, locker_id: str) -> LockerSummaryDTO:
        locker: Locker | None = self._locker_repo.get(locker_id)
        if locker is None:
            raise NotFoundError("Locker not found")

        return LockerSummaryDTO(
            locker_id=locker.locker_id,
            compartments=locker.compartments,
            active_reservations=locker.active_reservations,
            degraded_compartments=locker.degraded_compartments,
            state_hash=locker.state_hash,
        )