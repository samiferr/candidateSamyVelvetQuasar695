from __future__ import annotations

from dataclasses import dataclass

from lockstream.core.entities.reservation import Reservation, ReservationStatus
from lockstream.core.repositories.reservation_repository import ReservationRepository


class NotFoundError(Exception):
    """Raise to map to HTTP 404."""


@dataclass(frozen=True, slots=True)
class ReservationStatusDTO:
    """
    Use-case return type for GET /reservations/{reservation_id}
    """
    reservation_id: str
    status: ReservationStatus


class GetReservationStatusUseCase:
    def __init__(self, *, reservation_repo: ReservationRepository) -> None:
        self._reservation_repo = reservation_repo

    def execute(self, *, reservation_id: str) -> ReservationStatusDTO:
        reservation: Reservation | None = self._reservation_repo.get(reservation_id)
        if reservation is None:
            raise NotFoundError("Reservation not found")

        return ReservationStatusDTO(
            reservation_id=reservation.reservation_id,
            status=reservation.status,
        )