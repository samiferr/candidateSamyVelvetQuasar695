from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from lockstream.core.entities.event import Event as CoreEvent
from lockstream.core.entities.event import EventType as CoreEventType
from lockstream.core.use_cases.get_compartment_status import GetCompartmentStatusUseCase
from lockstream.core.use_cases.get_locker_summary import GetLockerSummaryUseCase
from lockstream.core.use_cases.get_reservation_status import GetReservationStatusUseCase
from lockstream.core.use_cases.ingest_event import IngestEventUseCase
from lockstream.core.use_cases.rebuild_locker_projection import RebuildLockerProjectionUseCase
from lockstream.infrastructure.repositories.compartment_repository_impl import CompartmentRepositoryImpl
from lockstream.infrastructure.repositories.event_repository_jsonl_impl import JsonlEventRepositoryImpl
from lockstream.infrastructure.repositories.fault_repository_impl import FaultRepositoryImpl
from lockstream.infrastructure.repositories.locker_repository_impl import LockerRepositoryImpl
from lockstream.infrastructure.repositories.reservation_repository_impl import ReservationRepositoryImpl
from lockstream.schemas.models import CompartmentStatus, Event, LockerSummary, ReservationStatus


def _default_event_log_path() -> Path:
    from lockstream.infrastructure.config import  settings
    return settings.event_log_path


def _to_core_event(body: Event) -> CoreEvent:
    """
    Translate API schema Event -> core Event entity.

    Supports:
      - Pydantic BaseModel with model_dump()
      - plain objects with attributes
    """
    if hasattr(body, "model_dump"):
        data = body.model_dump()
    elif hasattr(body, "dict"):
        data = body.dict()  # type: ignore[attr-defined]
    else:
        data = {
            "event_id": getattr(body, "event_id"),
            "type": getattr(body, "type"),
            "locker_id": getattr(body, "locker_id"),
            "occurred_at": getattr(body, "occurred_at"),
            "payload": getattr(body, "payload"),
        }

    occurred_at = data.get("occurred_at")
    if isinstance(occurred_at, str):
        occurred_at = datetime.fromisoformat(occurred_at)

    event_type = data.get("type")
    if isinstance(event_type, str):
        event_type = CoreEventType(event_type)
    else:
        event_type = CoreEventType(event_type.value)  # e.g. enum from schema

    return CoreEvent(
        event_id=data["event_id"],
        type=event_type,
        locker_id=data["locker_id"],
        occurred_at=occurred_at,
        payload=data.get("payload") or {},
    )


def get_compartment_status_service(locker_id: str, compartment_id: str, db: Session) -> CompartmentStatus:
    locker_repo = LockerRepositoryImpl(db)
    compartment_repo = CompartmentRepositoryImpl(db)
    use_case = GetCompartmentStatusUseCase(locker_repo=locker_repo, compartment_repo=compartment_repo)

    dto = use_case.execute(locker_id=locker_id, compartment_id=compartment_id)

    return CompartmentStatus(
        compartment_id=dto.compartment_id,
        degraded=dto.degraded,
        active_reservation=dto.active_reservation,
    )


def get_locker_summary_service(locker_id: str, db: Session) -> LockerSummary:
    locker_repo = LockerRepositoryImpl(db)
    use_case = GetLockerSummaryUseCase(locker_repo=locker_repo)

    dto = use_case.execute(locker_id=locker_id)

    return LockerSummary(
        locker_id=dto.locker_id,
        compartments=dto.compartments,
        active_reservations=dto.active_reservations,
        degraded_compartments=dto.degraded_compartments,
        state_hash=dto.state_hash,
    )


def get_reservation_status_service(reservation_id: str, db: Session) -> ReservationStatus:
    reservation_repo = ReservationRepositoryImpl(db)
    use_case = GetReservationStatusUseCase(reservation_repo=reservation_repo)

    dto = use_case.execute(reservation_id=reservation_id)

    return ReservationStatus(
        reservation_id=dto.reservation_id,
        status=dto.status,
    )


def ingest_event_service(body: Event, db: Session) -> dict[str, Any]:
    """
    Returns:
      {"created": True} if a new event appended or projected
      {"created": False} if duplicate event_id (idempotent)
    """
    event_repo = JsonlEventRepositoryImpl(file_path=_default_event_log_path())
    locker_repo = LockerRepositoryImpl(db)
    reservation_repo = ReservationRepositoryImpl(db)
    compartment_repo = CompartmentRepositoryImpl(db)
    fault_repo = FaultRepositoryImpl(db)

    use_case = IngestEventUseCase(
        event_repo=event_repo,
        locker_repo=locker_repo,
        reservation_repo=reservation_repo,
        compartment_repo=compartment_repo,
        fault_repo=fault_repo,
    )

    result = use_case.execute(_to_core_event(body))
    return {"created": result.accepted}


class _SqlProjectionResetter:
    def __init__(self, db: Session) -> None:
        self._db = db

    def reset(self) -> None:
        """
        Reset all projection tables to the initial state
        """
        self._db.execute(text("DELETE FROM compartments"))
        self._db.execute(text("DELETE FROM reservations"))
        self._db.execute(text("DELETE FROM lockers"))
        self._db.commit()


class _JsonlEventLogReader:
    def __init__(self, *, file_path: Path) -> None:
        self._path = Path(file_path)
        self._path.touch(exist_ok=True)

    def iter_events(self) -> list[CoreEvent]:
        events: list[CoreEvent] = []
        with self._path.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)

                occurred_at = record.get("occurred_at")
                if isinstance(occurred_at, str):
                    occurred_at = datetime.fromisoformat(occurred_at)

                events.append(
                    CoreEvent(
                        event_id=record["event_id"],
                        type=CoreEventType(record["type"]),
                        locker_id=record["locker_id"],
                        occurred_at=occurred_at,
                        payload=record.get("payload") or {},
                    )
                )
        return events


def rebuild_projection_service(db: Session) -> dict[str, Any]:
    """
    Build the in-memory DB projection from the append-only JSONL event log
    """
    event_log_path = _default_event_log_path()

    event_log = _JsonlEventLogReader(file_path=event_log_path)
    resetter = _SqlProjectionResetter(db)

    locker_repo = LockerRepositoryImpl(db)
    reservation_repo = ReservationRepositoryImpl(db)
    compartment_repo = CompartmentRepositoryImpl(db)
    fault_repo = FaultRepositoryImpl(db)
    event_repo = JsonlEventRepositoryImpl(file_path=event_log_path)

    projector = IngestEventUseCase(
        event_repo=event_repo,
        locker_repo=locker_repo,
        reservation_repo=reservation_repo,
        compartment_repo=compartment_repo,
        fault_repo=fault_repo,
    )

    use_case = RebuildLockerProjectionUseCase(
        event_log=event_log,
        projector=projector,
        resetter=resetter,
    )

    result = use_case.execute()
    return {"replayed_events": result.replayed_events}