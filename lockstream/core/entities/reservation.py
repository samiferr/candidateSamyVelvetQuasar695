from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ReservationStatus(str, Enum):
    CREATED = "CREATED"
    DEPOSITED = "DEPOSITED"
    PICKED_UP = "PICKED_UP"
    EXPIRED = "EXPIRED"


@dataclass(slots=True)
class Reservation:
    locker_id: str
    reservation_id: str
    compartment_id: str
    status: ReservationStatus

    def mark_deposited(self) -> None:
        self.status = ReservationStatus.DEPOSITED

    def mark_picked_up(self) -> None:
        self.status = ReservationStatus.PICKED_UP

    def mark_expired(self) -> None:
        self.status = ReservationStatus.EXPIRED

