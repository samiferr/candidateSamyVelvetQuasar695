from __future__ import annotations

from sqlalchemy.orm import Session

from lockstream.core.entities.reservation import Reservation, ReservationStatus
from lockstream.core.repositories.reservation_repository import ReservationRepository
from lockstream.infrastructure.models.models import ReservationModel


class ReservationRepositoryImpl(ReservationRepository):
    def __init__(self, db: Session):
        self.db = db

    def get(self, reservation_id: str) -> Reservation | None:
        row = self.db.get(ReservationModel, reservation_id)
        if row is None:
            return None
        return Reservation(
            compartment_id=row.compartment_id,
            reservation_id=row.reservation_id,
            locker_id=row.locker_id,
            status=ReservationStatus(row.status) if not isinstance(row.status, ReservationStatus) else row.status,
        )

    def upsert(self, reservation: Reservation) -> None:
        row = self.db.get(ReservationModel, reservation.reservation_id)
        if row is None:
            row = ReservationModel(reservation_id=reservation.reservation_id)

        row.locker_id = reservation.locker_id
        row.compartment_id = reservation.compartment_id
        row.status = reservation.status

        self.db.add(row)
        self.db.commit()