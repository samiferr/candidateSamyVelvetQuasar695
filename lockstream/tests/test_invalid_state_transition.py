from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from starlette.testclient import TestClient

from lockstream.main import app


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _event_log_path() -> Path:
    from lockstream.tests.config_tests import settings
    return settings.event_log_path


@pytest.fixture(autouse=True)
def _clear_event_log_jsonl_before_each_test() -> None:
    """
    Ensure tests don't leak events into each other via the append-only JSONL event log.
    """
    path = _event_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("", encoding="utf-8")


def test_deposit_before_reservation_returns_422() -> None:
    client = TestClient(app)

    locker_id = f"LOCKER-{uuid4()}"
    compartment_id = "C0001"
    reservation_id = "R-DOES-NOT-EXIST"

    res_reg = client.post("/events", json={"event_id": str(uuid4()), "occurred_at": _now_iso(), "locker_id": locker_id,
        "type": "CompartmentRegistered", "payload": {"compartment_id": compartment_id}, }, )
    assert res_reg.status_code == 202

    # Deposit before reservation exists returns a ValidationError (code 422)

    res_deposit = client.post("/events",
        json={"event_id": str(uuid4()), "occurred_at": _now_iso(), "locker_id": locker_id, "type": "ParcelDeposited",
            "payload": {"reservation_id": reservation_id, "compartment_id": compartment_id}, }, )
    assert res_deposit.status_code == 422
    body = res_deposit.json()
    assert "detail" in body


def test_pickup_before_deposit_returns_409() -> None:
    client = TestClient(app)

    locker_id = f"LOCKER-{uuid4()}"
    compartment_id = "C0001"
    reservation_id = "R001"

    # Register compartment
    res_reg = client.post("/events", json={"event_id": str(uuid4()), "occurred_at": _now_iso(), "locker_id": locker_id,
        "type": "CompartmentRegistered", "payload": {"compartment_id": compartment_id}, }, )
    assert res_reg.status_code == 202

    # Create a reservation (status = CREATED)
    res_create = client.post("/events",
        json={"event_id": str(uuid4()), "occurred_at": _now_iso(), "locker_id": locker_id, "type": "ReservationCreated",
            "payload": {"reservation_id": reservation_id, "compartment_id": compartment_id}, }, )
    assert res_create.status_code == 202

    # Pickup before deposit returns a DomainRuleViolation (code 409)

    res_pickup = client.post("/events",
        json={"event_id": str(uuid4()), "occurred_at": _now_iso(), "locker_id": locker_id, "type": "ParcelPickedUp",
            "payload": {"reservation_id": reservation_id, "compartment_id": compartment_id}, }, )
    assert res_pickup.status_code == 409
    body = res_pickup.json()
    assert "detail" in body


def test_pickup_after_expiration_returns_409() -> None:
    client = TestClient(app)

    locker_id = f"LOCKER-{uuid4()}"
    compartment_id = "C0001"
    reservation_id = "RT002"

    # Register compartment
    res_reg = client.post("/events", json={"event_id": str(uuid4()), "occurred_at": _now_iso(), "locker_id": locker_id,
        "type": "CompartmentRegistered", "payload": {"compartment_id": compartment_id}, }, )
    assert res_reg.status_code == 202

    # Create reservation
    res_create = client.post("/events",
        json={"event_id": str(uuid4()), "occurred_at": _now_iso(), "locker_id": locker_id, "type": "ReservationCreated",
            "payload": {"reservation_id": reservation_id, "compartment_id": compartment_id}, }, )
    assert res_create.status_code == 202

    # Expire reservation (status = EXPIRED)
    res_expire = client.post("/events",
        json={"event_id": str(uuid4()), "occurred_at": _now_iso(), "locker_id": locker_id, "type": "ReservationExpired",
            "payload": {"reservation_id": reservation_id, "compartment_id": compartment_id}, }, )
    assert res_expire.status_code == 202

    # Pickup after expiration returns a DomainRuleViolation (code 409)
    res_pickup = client.post("/events",
        json={"event_id": str(uuid4()), "occurred_at": _now_iso(), "locker_id": locker_id, "type": "ParcelPickedUp",
            "payload": {"reservation_id": reservation_id, "compartment_id": compartment_id}, }, )
    assert res_pickup.status_code == 409
    body = res_pickup.json()
    assert "detail" in body
