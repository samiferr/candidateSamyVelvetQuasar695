from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict
from uuid import UUID

from pydantic import BaseModel


class Type(Enum):
    CompartmentRegistered = 'CompartmentRegistered'
    ReservationCreated = 'ReservationCreated'
    ParcelDeposited = 'ParcelDeposited'
    ParcelPickedUp = 'ParcelPickedUp'
    ReservationExpired = 'ReservationExpired'
    FaultReported = 'FaultReported'
    FaultCleared = 'FaultCleared'


class Event(BaseModel):
    event_id: UUID
    occurred_at: datetime
    locker_id: str
    type: Type
    payload: Dict[str, Any]


class LockerSummary(BaseModel):
    locker_id: str
    compartments: int
    active_reservations: int
    degraded_compartments: int
    state_hash: str


class CompartmentStatus(BaseModel):
    compartment_id: str
    degraded: bool
    active_reservation: str | None


class Status(Enum):
    CREATED = 'CREATED'
    DEPOSITED = 'DEPOSITED'
    PICKED_UP = 'PICKED_UP'
    EXPIRED = 'EXPIRED'


class ReservationStatus(BaseModel):
    reservation_id: str
    status: Status
