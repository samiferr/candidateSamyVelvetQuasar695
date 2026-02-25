from __future__ import annotations
import json
from pathlib import Path
from typing import Iterable, Dict, Any

import enum
from sqlalchemy import (
    Boolean,
    Enum,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from lockstream.infrastructure.database import Base


class EventStore:
    def __init__(self, path: Path):
        self._path = path
        self._path.touch(exist_ok=True)

    def append(self, event: Dict[str, Any]) -> bool:
        if self._exists(event["event_id"]):
            return False

        with self._path.open("a") as f:
            f.write(json.dumps(event) + "\n")
        return True

    def _exists(self, event_id: str) -> bool:
        with self._path.open() as f:
            for line in f:
                if json.loads(line)["event_id"] == event_id:
                    return True
        return False

    def load_all(self) -> Iterable[Dict[str, Any]]:
        with self._path.open() as f:
            for line in f:
                yield json.loads(line)

    def load_by_locker(self, locker_id: str):
        return (e for e in self.load_all() if e["locker_id"] == locker_id)


class EventType(str, enum.Enum):
    CompartmentRegistered = "CompartmentRegistered"
    ReservationCreated = "ReservationCreated"
    ParcelDeposited = "ParcelDeposited"
    ParcelPickedUp = "ParcelPickedUp"
    ReservationExpired = "ReservationExpired"
    FaultReported = "FaultReported"
    FaultCleared = "FaultCleared"


class ReservationStatus(str, enum.Enum):
    CREATED = "CREATED"
    DEPOSITED = "DEPOSITED"
    PICKED_UP = "PICKED_UP"
    EXPIRED = "EXPIRED"


class LockerModel(Base):
    __tablename__ = "lockers"

    locker_id: Mapped[str] = mapped_column(String, primary_key=True)
    compartments: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    active_reservations: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    degraded_compartments: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    state_hash: Mapped[str] = mapped_column(String, nullable=False, default="")

    compartments_rel = relationship("CompartmentModel", back_populates="locker", cascade="all, delete-orphan")


class ReservationModel(Base):
    __tablename__ = "reservations"

    reservation_id: Mapped[str] = mapped_column(String, primary_key=True)
    locker_id: Mapped[str] = mapped_column(ForeignKey("lockers.locker_id"), nullable=False, index=True)
    compartment_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    status: Mapped[ReservationStatus] = mapped_column(Enum(ReservationStatus), nullable=False)

    locker = relationship("LockerModel")
    compartment = relationship("CompartmentModel", back_populates="active_reservation", uselist=False)

class CompartmentModel(Base):
    __tablename__ = "compartments"

    locker_id: Mapped[str] = mapped_column(ForeignKey("lockers.locker_id"), primary_key=True)
    compartment_id: Mapped[str] = mapped_column(String, primary_key=True)
    degraded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    faulty: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    active_reservation_id: Mapped[str | None] = mapped_column(
        ForeignKey("reservations.reservation_id"),
        nullable=True,
        index=True,
        unique=True,
    )

    locker = relationship("LockerModel", back_populates="compartments_rel")
    active_reservation = relationship("ReservationModel", back_populates="compartment",
                                      foreign_keys=[active_reservation_id])
