from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

import lockstream.presentation.routers as routers


class _DummyDB:
    """A minimal stand-in for a SQLAlchemy Session (we never call it in router tests)."""


@pytest.fixture()
def app(monkeypatch: pytest.MonkeyPatch) -> FastAPI:
    """
    Build a tiny FastAPI app with ONLY the router under test.

    We override the DB dependency so tests don't touch the real SessionLocal / SQLite.
    """
    test_app = FastAPI()
    test_app.include_router(routers.router)

    def _override_get_db():
        yield _DummyDB()

    test_app.dependency_overrides[routers.get_db] = _override_get_db
    return test_app


@pytest.fixture()
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


def _event_payload(**overrides: Any) -> dict[str, Any]:
    base = {
        "event_id": "evt-1",
        "type": "CompartmentRegistered",
        "locker_id": "locker-1",
        "occurred_at": datetime.now(tz=timezone.utc).isoformat(),
        "payload": {"compartment_id": "c-1"},
    }
    base.update(overrides)
    return base


def test_post_events_accepted_returns_202(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_ingest_event_service(body, db):
        return {"accepted": True}

    monkeypatch.setattr(routers, "ingest_event_service", _fake_ingest_event_service)

    r = client.post("/events", json=_event_payload(event_id="evt-accepted"))
    assert r.status_code == 202
    assert r.text in ("", "null")


def test_post_events_duplicate_returns_200(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_ingest_event_service(body, db):
        return {"accepted": False}

    monkeypatch.setattr(routers, "ingest_event_service", _fake_ingest_event_service)

    r = client.post("/events", json=_event_payload(event_id="evt-dup"))
    assert r.status_code == 200
    assert r.text in ("", "null")


def test_post_events_validation_error_returns_422(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_ingest_event_service(body, db):
        raise routers.ValidationError("bad event")

    monkeypatch.setattr(routers, "ingest_event_service", _fake_ingest_event_service)

    r = client.post("/events", json=_event_payload(event_id="evt-bad"))
    assert r.status_code == 422
    assert r.json()["detail"] == "bad event"


def test_post_events_domain_rule_violation_returns_409(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_ingest_event_service(body, db):
        raise routers.DomainRuleViolation("rule broken")

    monkeypatch.setattr(routers, "ingest_event_service", _fake_ingest_event_service)

    r = client.post("/events", json=_event_payload(event_id="evt-rule"))
    assert r.status_code == 409
    assert r.json()["detail"] == "rule broken"


def test_get_locker_summary_200(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_get_locker_summary_service(locker_id: str, db):
        return {
            "locker_id": locker_id,
            "compartments": 2,
            "active_reservations": 1,
            "degraded_compartments": 0,
            "state_hash": "hash",
        }

    monkeypatch.setattr(routers, "get_locker_summary_service", _fake_get_locker_summary_service)

    r = client.get("/lockers/locker-xyz")
    assert r.status_code == 200
    assert r.json()["locker_id"] == "locker-xyz"


def test_get_locker_summary_not_found_maps_to_404(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_get_locker_summary_service(locker_id: str, db):
        raise routers.LockerNotFoundError("Locker not found")

    monkeypatch.setattr(routers, "get_locker_summary_service", _fake_get_locker_summary_service)

    r = client.get("/lockers/missing")
    assert r.status_code == 404
    assert r.json()["detail"] == "Locker not found"


def test_get_compartment_status_200(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_get_compartment_status_service(locker_id: str, compartment_id: str, db):
        return {
            "compartment_id": compartment_id,
            "degraded": False,
            "active_reservation": None,
        }

    monkeypatch.setattr(routers, "get_compartment_status_service", _fake_get_compartment_status_service)

    r = client.get("/lockers/locker-1/compartments/c-9")
    assert r.status_code == 200
    assert r.json()["compartment_id"] == "c-9"


def test_get_compartment_status_not_found_maps_to_404(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_get_compartment_status_service(locker_id: str, compartment_id: str, db):
        raise routers.CompartmentNotFoundError("Compartment not found")

    monkeypatch.setattr(routers, "get_compartment_status_service", _fake_get_compartment_status_service)

    r = client.get("/lockers/locker-1/compartments/missing")
    assert r.status_code == 404
    assert r.json()["detail"] == "Compartment not found"


def test_get_reservation_status_200(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_get_reservation_status_service(reservation_id: str, db):
        # status is an enum in the real schema; a string is fine for router-level tests
        return {"reservation_id": reservation_id, "status": "CREATED"}

    monkeypatch.setattr(routers, "get_reservation_status_service", _fake_get_reservation_status_service)

    r = client.get("/reservations/r-1")
    assert r.status_code == 200
    assert r.json()["reservation_id"] == "r-1"


def test_get_reservation_status_not_found_maps_to_404(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_get_reservation_status_service(reservation_id: str, db):
        raise routers.ReservationNotFoundError("Reservation not found")

    monkeypatch.setattr(routers, "get_reservation_status_service", _fake_get_reservation_status_service)

    r = client.get("/reservations/missing")
    assert r.status_code == 404
    assert r.json()["detail"] == "Reservation not found"