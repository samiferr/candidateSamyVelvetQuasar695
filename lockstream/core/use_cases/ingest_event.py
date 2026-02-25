from __future__ import annotations

from dataclasses import dataclass

from lockstream.core.entities.compartment import Compartment
from lockstream.core.entities.event import Event, EventType
from lockstream.core.entities.locker import Locker
from lockstream.core.entities.reservation import Reservation, ReservationStatus
from lockstream.core.repositories.compartment_repository import CompartmentRepository
from lockstream.core.repositories.event_repository import EventRepository
from lockstream.core.repositories.locker_repository import LockerRepository
from lockstream.core.repositories.reservation_repository import ReservationRepository


class DomainRuleViolation(Exception):
    """Raise to map to HTTP 409 (domain rule violation)."""


class ValidationError(Exception):
    """Raise to map to HTTP 422 (validation error)."""


@dataclass(frozen=True, slots=True)
class IngestEventResult:
    accepted: bool


class IngestEventUseCase:
    """
    Ingests an event into the append-only event store (idempotent) and projects it
    into the read-model repositories (lockers/compartments/reservations)
    """

    def __init__(
        self,
        *,
        event_repo: EventRepository,
        locker_repo: LockerRepository,
        reservation_repo: ReservationRepository,
        compartment_repo: CompartmentRepository,
    ) -> None:
        self._event_repo = event_repo
        self._locker_repo = locker_repo
        self._reservation_repo = reservation_repo
        self._compartment_repo = compartment_repo

        self._handlers: dict[EventType, callable[[Event], None]] = {
            EventType.CompartmentRegistered: self._on_compartment_registered,
            EventType.ReservationCreated: self._on_reservation_created,
            EventType.ParcelDeposited: self._on_parcel_deposited,
            EventType.ParcelPickedUp: self._on_parcel_picked_up,
            EventType.ReservationExpired: self._on_reservation_expired,
            EventType.FaultReported: self._on_fault_reported,
            EventType.FaultCleared: self._on_fault_cleared,
        }

    def execute(self, event: Event) -> IngestEventResult:
        accepted = self._event_repo.add_if_absent(event)
        if not accepted:
            return IngestEventResult(accepted=False)

        self.project(event)
        return IngestEventResult(accepted=True)

    def project(self, event: Event) -> None:
        handler = self._handlers.get(event.type)
        if handler is None:
            raise ValueError(f"Unsupported event type: {event.type}")
        handler(event)

    # -----------------------------
    # Internal helpers
    # -----------------------------
    def _get_or_create_locker(self, locker_id: str) -> Locker:
        locker = self._locker_repo.get(locker_id)
        if locker is None:
            locker = Locker(locker_id=locker_id)
        return locker

    def _upsert_locker_with_state_hash(self, locker: Locker) -> None:
        locker.set_state_hash()
        self._locker_repo.upsert(locker)

    @staticmethod
    def _require_str(payload: dict, key: str) -> str:
        """Raises ValueError if payload[key] is not a non-empty string"""

        value = payload.get(key)
        if not isinstance(value, str) or not value:
            raise ValueError(f"payload[{key!r}] must be a non-empty string")
        return value

    @staticmethod
    def _require_int(payload: dict, key: str) -> int:
        value = payload.get(key)
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"payload[{key!r}] must be an int")
        return value

    # -----------------------------
    # Event handlers (projection)
    # -----------------------------
    def _on_compartment_registered(self, event: Event) -> None:
        compartment_id = self._require_str(event.payload, "compartment_id")

        locker = self._get_or_create_locker(event.locker_id)
        locker.compartments += 1
        self._upsert_locker_with_state_hash(locker)

        self._compartment_repo.upsert(
            Compartment(
                locker_id=event.locker_id,
                compartment_id=compartment_id,
                degraded=False,
                active_reservation_id=None,
            )
        )

    def _on_reservation_created(self, event: Event) -> None:
        reservation_id = self._require_str(event.payload, "reservation_id")
        compartment_id = self._require_str(event.payload, "compartment_id")

        compartment = self._compartment_repo.get(event.locker_id, compartment_id)
        if compartment is None:
            raise ValidationError(
                f"Cannot create reservation for unregistered compartment: locker_id={event.locker_id!r}, "
                f"compartment_id={compartment_id!r}"
            )

        try:
            compartment.assign_reservation(reservation_id)
        except ValueError as e:
            raise DomainRuleViolation(str(e)) from e

        locker = self._get_or_create_locker(event.locker_id)
        locker.active_reservations += 1
        self._upsert_locker_with_state_hash(locker)

        self._reservation_repo.upsert(
            Reservation(
                locker_id=event.locker_id,
                reservation_id=reservation_id,
                compartment_id=compartment_id,
                status=ReservationStatus.CREATED,
            )
        )

        compartment = self._compartment_repo.get(event.locker_id, compartment_id) or Compartment(
            locker_id=event.locker_id,
            compartment_id=compartment_id,
        )
        compartment.active_reservation_id = reservation_id
        self._compartment_repo.upsert(compartment)

    def _on_parcel_deposited(self, event: Event) -> None:
        reservation_id = self._require_str(event.payload, "reservation_id")

        reservation = self._reservation_repo.get(reservation_id)
        if reservation is None:
            raise ValidationError(f"Cannot deposit parcel: reservation not found: {reservation_id!r}")

        payload_compartment_id = event.payload.get("compartment_id")
        if payload_compartment_id is not None and payload_compartment_id != reservation.compartment_id:
            raise ValidationError(
                "Cannot deposit parcel: compartment mismatch for reservation "
                f"{reservation_id!r} (event compartment_id={payload_compartment_id!r}, "
                f"reservation compartment_id={reservation.compartment_id!r})"
            )

        if reservation.status is not ReservationStatus.CREATED:
            raise DomainRuleViolation(
                f"Cannot deposit parcel for reservation {reservation_id!r} in status {reservation.status.value!r}"
            )

        reservation.mark_deposited()
        self._reservation_repo.upsert(reservation)

    def _on_parcel_picked_up(self, event: Event) -> None:
        reservation_id = self._require_str(event.payload, "reservation_id")

        reservation = self._reservation_repo.get(reservation_id)
        if reservation is None:
            raise ValidationError(f"Cannot pick up parcel: reservation not found: {reservation_id!r}")

        payload_compartment_id = event.payload.get("compartment_id")
        if payload_compartment_id is not None and payload_compartment_id != reservation.compartment_id:
            raise ValidationError(
                "Cannot pick up parcel: compartment mismatch for reservation "
                f"{reservation_id!r} (event compartment_id={payload_compartment_id!r}, "
                f"reservation compartment_id={reservation.compartment_id!r})"
            )

        if reservation.status is ReservationStatus.EXPIRED:
            raise DomainRuleViolation(f"Cannot pick up parcel: reservation {reservation_id!r} is expired")

        if reservation.status is not ReservationStatus.DEPOSITED:
            raise DomainRuleViolation(
                f"Cannot pick up parcel for reservation {reservation_id!r} in status {reservation.status.value!r}"
            )

        reservation.mark_picked_up()
        self._reservation_repo.upsert(reservation)

        compartment = self._compartment_repo.get(event.locker_id, reservation.compartment_id)
        if compartment is not None and compartment.active_reservation_id == reservation_id:
            compartment.clear_reservation()
            self._compartment_repo.upsert(compartment)

        locker = self._get_or_create_locker(event.locker_id)
        locker.active_reservations = max(0, locker.active_reservations - 1)
        self._upsert_locker_with_state_hash(locker)


    def _on_reservation_expired(self, event: Event) -> None:
        reservation_id = self._require_str(event.payload, "reservation_id")

        reservation = self._reservation_repo.get(reservation_id)
        if reservation is not None:
            reservation.mark_expired()
            self._reservation_repo.upsert(reservation)

            compartment = self._compartment_repo.get(event.locker_id, reservation.compartment_id)
            if compartment is not None and compartment.active_reservation_id == reservation_id:
                compartment.clear_reservation()
                self._compartment_repo.upsert(compartment)

        locker = self._get_or_create_locker(event.locker_id)
        locker.active_reservations = max(0, locker.active_reservations - 1)
        self._upsert_locker_with_state_hash(locker)

    def _on_fault_reported(self, event: Event) -> None:
        compartment_id = self._require_str(event.payload, "compartment_id")
        severity = self._require_int(event.payload, "severity")

        compartment = self._compartment_repo.get(event.locker_id, compartment_id) or Compartment(
            locker_id=event.locker_id,
            compartment_id=compartment_id,
        )

        if int(severity) >= 3:
            compartment.mark_degraded()

            locker = self._get_or_create_locker(event.locker_id)
            locker.degraded_compartments += 1
            self._upsert_locker_with_state_hash(locker)

        compartment.mark_faulty()
        self._compartment_repo.upsert(compartment)

    def _on_fault_cleared(self, event: Event) -> None:
        compartment_id = self._require_str(event.payload, "compartment_id")

        compartment = self._compartment_repo.get(event.locker_id, compartment_id)
        if compartment is None or not compartment.degraded:
            return

        compartment.clear_degraded()
        self._compartment_repo.upsert(compartment)

        locker = self._get_or_create_locker(event.locker_id)
        locker.degraded_compartments = max(0, locker.degraded_compartments - 1)
        self._upsert_locker_with_state_hash(locker)