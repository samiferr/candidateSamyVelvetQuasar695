from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from lockstream.core.entities.fault_reported import FaultReported
from lockstream.core.repositories.fault_repository import FaultRepository
from lockstream.infrastructure.models.models import FaultModel


class FaultRepositoryImpl(FaultRepository):
    def __init__(self, db: Session) -> None:
        self._db = db

    def get(self, fault_event_id: str) -> FaultReported | None:
        row = self._db.get(FaultModel, fault_event_id)
        if row is None:
            return None

        return FaultReported(
            event_id=row.fault_event_id,
            locker_id=row.locker_id,
            compartment_id=row.compartment_id,
            severity=row.severity,
            cleared=row.cleared,
            cleared_by_event_id=row.cleared_by_event_id,
        )

    def upsert(self, fault: FaultReported) -> None:
        row = self._db.get(FaultModel, fault.event_id)
        if row is None:
            row = FaultModel(fault_event_id=fault.event_id)

        row.locker_id = fault.locker_id
        row.compartment_id = fault.compartment_id
        row.severity = fault.severity
        row.cleared = fault.cleared
        row.cleared_by_event_id = fault.cleared_by_event_id

        self._db.add(row)
        self._db.commit()

    def active_summary(self, *, locker_id: str, compartment_id: str) -> tuple[int, bool]:
        q = (
            self._db.query(
                func.count(FaultModel.fault_event_id),
                func.max(FaultModel.severity),
            )
            .filter(FaultModel.locker_id == locker_id)
            .filter(FaultModel.compartment_id == compartment_id)
            .filter(FaultModel.cleared.is_(False))
        )

        count, max_sev = q.one()
        count_i = int(count or 0)
        any_ge_threshold = (max_sev is not None) and int(max_sev) >= 3
        return count_i, any_ge_threshold