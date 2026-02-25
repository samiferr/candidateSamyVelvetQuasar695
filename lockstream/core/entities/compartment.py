from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class Compartment:
    locker_id: str
    compartment_id: str
    degraded: bool = False
    faulty: bool = False
    active_reservation_id: str | None = None

    def assign_reservation(self, reservation_id: str) -> None:
        if self.degraded:
            raise ValueError("Cannot assign reservation to a degraded compartment")
        if self.active_reservation_id is not None:
            raise ValueError("Compartment already has an active reservation")
        self.active_reservation_id = reservation_id

    def clear_reservation(self) -> None:
        self.active_reservation_id = None

    def mark_faulty(self) -> None:
        self.faulty = True

    def mark_degraded(self) -> None:
        self.degraded = True

    def clear_degraded(self) -> None:
        self.degraded = False