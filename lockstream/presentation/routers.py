from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from lockstream.infrastructure.database import SessionLocal
from lockstream.services.lockstream_service import (
    get_compartment_status_service,
    get_locker_summary_service,
    get_reservation_status_service,
    ingest_event_service,
)
from lockstream.schemas.models import CompartmentStatus, Event, LockerSummary, ReservationStatus
from lockstream.core.use_cases.get_compartment_status import NotFoundError as CompartmentNotFoundError
from lockstream.core.use_cases.get_locker_summary import NotFoundError as LockerNotFoundError
from lockstream.core.use_cases.get_reservation_status import NotFoundError as ReservationNotFoundError
from lockstream.core.use_cases.ingest_event import DomainRuleViolation, ValidationError

router = APIRouter()


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/events", response_model=None)
def post_events(body: Event, db: Session = Depends(get_db)) -> Response:
    """
    Ingest a domain event

    Returns:
      - 202 if accepted (new event appended + projected)
      - 200 if duplicate (idempotent)
      - 409 on domain rule violation
      - 422 on validation error
    """
    try:
        result = ingest_event_service(body, db)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except DomainRuleViolation as e:
        raise HTTPException(status_code=409, detail=str(e))

    if result["created"]:
        return Response(status_code=202)
    return Response(status_code=200)


@router.get("/lockers/{locker_id}", response_model=LockerSummary)
def get_lockers_locker_id(locker_id: str, db: Session = Depends(get_db)) -> LockerSummary:
    """
    Get locker summary
    """
    try:
        return get_locker_summary_service(locker_id, db)
    except LockerNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/lockers/{locker_id}/compartments/{compartment_id}", response_model=CompartmentStatus)
def get_lockers_locker_id_compartments_compartment_id(
    locker_id: str,
    compartment_id: str,
    db: Session = Depends(get_db),
) -> CompartmentStatus:
    """
    Get compartment status
    """
    try:
        return get_compartment_status_service(locker_id, compartment_id, db)
    except CompartmentNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/reservations/{reservation_id}", response_model=ReservationStatus)
def get_reservations_reservation_id(reservation_id: str, db: Session = Depends(get_db)) -> ReservationStatus:
    """
    Get reservation status
    """
    try:
        return get_reservation_status_service(reservation_id, db)
    except ReservationNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
