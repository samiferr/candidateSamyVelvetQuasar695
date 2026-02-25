from __future__ import annotations

from sqlalchemy.orm import Session

from lockstream.core.entities.locker import Locker
from lockstream.core.repositories.locker_repository import LockerRepository
from lockstream.infrastructure.models.models import LockerModel


class LockerRepositoryImpl(LockerRepository):
    """
    Simple SQLAlchemy implementation for Locker.

    """

    def __init__(self, db: Session) -> None:
        self._db = db

    def get(self, locker_id: str) -> Locker | None:
        row = self._db.get(LockerModel, locker_id)
        if row is None:
            return None

        return Locker(
            locker_id=row.locker_id,
            compartments=row.compartments,
            active_reservations=row.active_reservations,
            degraded_compartments=row.degraded_compartments,
            state_hash=row.state_hash,
        )

    def upsert(self, locker: Locker) -> None:
        row = self._db.get(LockerModel, locker.locker_id)
        if row is None:
            row = LockerModel(locker_id=locker.locker_id)

        row.compartments = locker.compartments
        row.active_reservations = locker.active_reservations
        row.degraded_compartments = locker.degraded_compartments
        row.state_hash = locker.state_hash

        self._db.add(row)
        self._db.commit()