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


def _post_event(client: TestClient, *, locker_id: str, event_type: str, payload: dict) -> tuple[int, str, dict]:
    event_id = str(uuid4())
    res = client.post(
        "/events",
        json={
            "event_id": event_id,
            "occurred_at": _now_iso(),
            "locker_id": locker_id,
            "type": event_type,
            "payload": payload,
        },
    )
    body = res.json() if res.headers.get("content-type", "").startswith("application/json") else {}
    return res.status_code, event_id, body


def test_fault_cleared_referencing_nonexistent_fault_event_id_returns_409() -> None:
    client = TestClient(app)

    locker_id = f"LOCKER-{uuid4()}"
    compartment_id = "C0001"

    status, _event_id, _ = _post_event(
        client,
        locker_id=locker_id,
        event_type="CompartmentRegistered",
        payload={"compartment_id": compartment_id},
    )
    assert status == 202

    status, _event_id, body = _post_event(
        client,
        locker_id=locker_id,
        event_type="FaultCleared",
        payload={"compartment_id": compartment_id, "fault_event_id": str(uuid4())},
    )
    assert status == 409
    assert "detail" in body


def test_fault_cleared_referencing_fault_from_different_compartment_returns_409() -> None:
    client = TestClient(app)

    locker_id = f"LOCKER-{uuid4()}"
    comp_a = "C0001"
    comp_b = "C0002"

    status, _event_id, _ = _post_event(
        client,
        locker_id=locker_id,
        event_type="CompartmentRegistered",
        payload={"compartment_id": comp_a},
    )
    assert status == 202

    status, _event_id, _ = _post_event(
        client,
        locker_id=locker_id,
        event_type="CompartmentRegistered",
        payload={"compartment_id": comp_b},
    )
    assert status == 202

    # Report fault on comp_a
    status, fault_event_id, _ = _post_event(
        client,
        locker_id=locker_id,
        event_type="FaultReported",
        payload={"compartment_id": comp_a, "severity": 3},
    )
    assert status == 202

    # Try to clear that fault but claim it's for comp_b
    status, _event_id, body = _post_event(
        client,
        locker_id=locker_id,
        event_type="FaultCleared",
        payload={"compartment_id": comp_b, "fault_event_id": fault_event_id},
    )
    assert status == 409
    assert "detail" in body


def test_fault_cleared_double_clear_same_fault_returns_409() -> None:
    client = TestClient(app)

    locker_id = f"LOCKER-{uuid4()}"
    compartment_id = "C0001"

    status, _event_id, _ = _post_event(
        client,
        locker_id=locker_id,
        event_type="CompartmentRegistered",
        payload={"compartment_id": compartment_id},
    )
    assert status == 202

    status, fault_event_id, _ = _post_event(
        client,
        locker_id=locker_id,
        event_type="FaultReported",
        payload={"compartment_id": compartment_id, "severity": 3},
    )
    assert status == 202

    # First clear is valid
    status, _event_id, _ = _post_event(
        client,
        locker_id=locker_id,
        event_type="FaultCleared",
        payload={"compartment_id": compartment_id, "fault_event_id": fault_event_id},
    )
    assert status == 202

    # Second clear of the same referenced fault returns an invalid (already cleared)
    status, _event_id, body = _post_event(
        client,
        locker_id=locker_id,
        event_type="FaultCleared",
        payload={"compartment_id": compartment_id, "fault_event_id": fault_event_id},
    )
    assert status == 409
    assert "detail" in body