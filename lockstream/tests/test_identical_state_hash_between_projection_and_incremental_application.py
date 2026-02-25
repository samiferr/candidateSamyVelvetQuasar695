from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from starlette.testclient import TestClient

from lockstream.infrastructure.database import SessionLocal
from lockstream.main import app
from lockstream.services.lockstream_service import rebuild_projection_service


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


def _post_event(client: TestClient, *, locker_id: str, event_type: str, payload: dict) -> int:
    res = client.post("/events",
        json={"event_id": str(uuid4()), "occurred_at": _now_iso(), "locker_id": locker_id, "type": event_type,
            "payload": payload, }, )
    return res.status_code


def test_projection_equivalence_incremental_vs_full_rebuild_state_hash_matches() -> None:
    client = TestClient(app)

    locker_id = f"LOCKER-{uuid4()}"
    compartment_id = "C0001"
    reservation_id = "R001"

    # Incremental application
    assert _post_event(client, locker_id=locker_id, event_type="CompartmentRegistered",
        payload={"compartment_id": compartment_id}, ) == 202

    assert _post_event(client, locker_id=locker_id, event_type="ReservationCreated",
        payload={"reservation_id": reservation_id, "compartment_id": compartment_id}, ) == 202

    assert _post_event(client, locker_id=locker_id, event_type="ParcelDeposited",
        payload={"reservation_id": reservation_id, "compartment_id": compartment_id}, ) == 202

    assert _post_event(client, locker_id=locker_id, event_type="ParcelPickedUp",
        payload={"reservation_id": reservation_id, "compartment_id": compartment_id}, ) == 202

    # Hash after incremental projection
    res_before = client.get(f"/lockers/{locker_id}")
    assert res_before.status_code == 200
    hash_incremental = res_before.json()["state_hash"]
    assert isinstance(hash_incremental, str) and hash_incremental

    # Full rebuild from JSONL event log into the in-memory DB projection
    db = SessionLocal()
    try:
        rebuild_projection_service(db)
    finally:
        db.close()

    # Hash after full rebuild
    res_after = client.get(f"/lockers/{locker_id}")
    assert res_after.status_code == 200
    hash_rebuild = res_after.json()["state_hash"]
    assert isinstance(hash_rebuild, str) and hash_rebuild

    assert hash_rebuild == hash_incremental
