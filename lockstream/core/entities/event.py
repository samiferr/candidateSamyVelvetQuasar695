from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any


class EventType(str, Enum):
    CompartmentRegistered = "CompartmentRegistered"
    ReservationCreated = "ReservationCreated"
    ParcelDeposited = "ParcelDeposited"
    ParcelPickedUp = "ParcelPickedUp"
    ReservationExpired = "ReservationExpired"
    FaultReported = "FaultReported"
    FaultCleared = "FaultCleared"


@dataclass(frozen=True, slots=True)
class Event:
    event_id: str
    occurred_at: datetime
    locker_id: str
    type: EventType
    payload: dict[str, Any]