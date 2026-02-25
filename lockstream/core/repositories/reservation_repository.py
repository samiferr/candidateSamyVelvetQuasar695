from __future__ import annotations

from abc import ABC, abstractmethod

from lockstream.core.entities.reservation import Reservation


class ReservationRepository(ABC):
    @abstractmethod
    def get(self, reservation_id: str) -> Reservation | None:
        raise NotImplementedError

    @abstractmethod
    def upsert(self, reservation: Reservation) -> None:
        raise NotImplementedError


