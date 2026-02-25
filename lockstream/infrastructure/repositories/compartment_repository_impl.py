from __future__ import annotations

from sqlalchemy.orm import Session

from lockstream.core.entities.compartment import Compartment
from lockstream.core.repositories.compartment_repository import CompartmentRepository
from lockstream.infrastructure.models.models import CompartmentModel


class CompartmentRepositoryImpl(CompartmentRepository):
    """SQLAlchemy implementation for Compartment projection persistence."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def get(self, locker_id: str, compartment_id: str) -> Compartment | None:
        row = self._db.get(CompartmentModel, (locker_id, compartment_id))
        if row is None:
            return None

        return Compartment(
            locker_id=row.locker_id,
            compartment_id=row.compartment_id,
            degraded=row.degraded,
            faulty=row.faulty,
            active_reservation_id=row.active_reservation_id,
        )

    def upsert(self, compartment: Compartment) -> None:
        row = self._db.get(
            CompartmentModel,
            (compartment.locker_id, compartment.compartment_id),
        )
        if row is None:
            row = CompartmentModel(
                locker_id=compartment.locker_id,
                compartment_id=compartment.compartment_id,
            )

        row.degraded = compartment.degraded
        row.faulty = compartment.faulty
        row.active_reservation_id = compartment.active_reservation_id

        self._db.add(row)
        self._db.commit()