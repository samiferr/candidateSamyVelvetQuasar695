# lockstream/tests/test_severity_threshold.py
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


def _post_event(client: TestClient, *, locker_id: str, event_type: str, payload: dict) -> tuple[int, str]:
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
    return res.status_code, event_id


def test_fault_reported_below_threshold_does_not_degrade_compartment_or_locker_count() -> None:
    client = TestClient(app)

    locker_id = f"LOCKER-{uuid4()}"
    compartment_id = "C0001"

    status, _ = _post_event(
        client,
        locker_id=locker_id,
        event_type="CompartmentRegistered",
        payload={"compartment_id": compartment_id},
    )
    assert status == 202

    status, _fault_reported_event_id = _post_event(
        client,
        locker_id=locker_id,
        event_type="FaultReported",
        payload={"compartment_id": compartment_id, "severity": 2},
    )
    assert status == 202

    res_comp = client.get(f"/lockers/{locker_id}/compartments/{compartment_id}")
    assert res_comp.status_code == 200
    comp = res_comp.json()
    assert comp["compartment_id"] == compartment_id
    assert comp["degraded"] is False

    res_summary = client.get(f"/lockers/{locker_id}")
    assert res_summary.status_code == 200
    summary = res_summary.json()
    assert summary["degraded_compartments"] == 0


def test_fault_reported_at_or_above_threshold_degrades_and_increments_locker_count() -> None:
    client = TestClient(app)

    locker_id = f"LOCKER-{uuid4()}"
    compartment_id = "C0001"

    status, _ = _post_event(
        client,
        locker_id=locker_id,
        event_type="CompartmentRegistered",
        payload={"compartment_id": compartment_id},
    )
    assert status == 202

    status, _fault_reported_event_id = _post_event(
        client,
        locker_id=locker_id,
        event_type="FaultReported",
        payload={"compartment_id": compartment_id, "severity": 3},
    )
    assert status == 202

    res_comp = client.get(f"/lockers/{locker_id}/compartments/{compartment_id}")
    assert res_comp.status_code == 200
    comp = res_comp.json()
    assert comp["degraded"] is True

    res_summary = client.get(f"/lockers/{locker_id}")
    assert res_summary.status_code == 200
    summary = res_summary.json()
    assert summary["degraded_compartments"] == 1


def test_fault_cleared_only_decrements_when_previously_degraded() -> None:
    client = TestClient(app)

    locker_id = f"LOCKER-{uuid4()}"
    compartment_id = "C0001"

    status, _ = _post_event(
        client,
        locker_id=locker_id,
        event_type="CompartmentRegistered",
        payload={"compartment_id": compartment_id},
    )
    assert status == 202

    # Below threshold: should not degrade
    status, fault1_event_id = _post_event(
        client,
        locker_id=locker_id,
        event_type="FaultReported",
        payload={"compartment_id": compartment_id, "severity": 1},
    )
    assert status == 202

    # Clearing now should not change degraded count (still 0)
    status, _ = _post_event(
        client,
        locker_id=locker_id,
        event_type="FaultCleared",
        payload={"compartment_id": compartment_id, "fault_event_id": fault1_event_id},
    )
    assert status == 202

    res_summary_0 = client.get(f"/lockers/{locker_id}")
    assert res_summary_0.status_code == 200
    assert res_summary_0.json()["degraded_compartments"] == 0

    # Now degrade (>= threshold) and verify count increments
    status, fault2_event_id = _post_event(
        client,
        locker_id=locker_id,
        event_type="FaultReported",
        payload={"compartment_id": compartment_id, "severity": 5},
    )
    assert status == 202

    res_summary_1 = client.get(f"/lockers/{locker_id}")
    assert res_summary_1.status_code == 200
    assert res_summary_1.json()["degraded_compartments"] == 1

    # Clearing should decrement back to 0
    status, _ = _post_event(
        client,
        locker_id=locker_id,
        event_type="FaultCleared",
        payload={"compartment_id": compartment_id, "fault_event_id": fault2_event_id},
    )
    assert status == 202

    res_comp = client.get(f"/lockers/{locker_id}/compartments/{compartment_id}")
    assert res_comp.status_code == 200
    assert res_comp.json()["degraded"] is False

    res_summary_2 = client.get(f"/lockers/{locker_id}")
    assert res_summary_2.status_code == 200
    assert res_summary_2.json()["degraded_compartments"] == 0