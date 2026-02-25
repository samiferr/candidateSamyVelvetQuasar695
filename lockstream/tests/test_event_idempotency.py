from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from starlette.testclient import TestClient

from lockstream.main import app


def test_event_idempotency_resending_same_event_id_does_not_change_state() -> None:
    client = TestClient(app)

    locker_id = f"LOCKER-{uuid4()}"
    first_compartment_id = "C0001"
    second_compartment_id = "C9999"  # if wrongly applied, it would change state

    event_id = str(uuid4())
    occurred_at = datetime.now(timezone.utc).isoformat()

    # First send: creates locker + registers compartment => changes locker summary
    res1 = client.post(
        "/events",
        json={
            "event_id": event_id,
            "occurred_at": occurred_at,
            "locker_id": locker_id,
            "type": "CompartmentRegistered",
            "payload": {"compartment_id": first_compartment_id},
        },
    )
    assert res1.status_code == 202

    summary_after_first = client.get(f"/lockers/{locker_id}")
    assert summary_after_first.status_code == 200
    state1 = summary_after_first.json()

    # Re-send same event_id, but mutate payload to prove it must NOT be applied again
    res2 = client.post(
        "/events",
        json={
            "event_id": event_id,  # same ID => must be treated as duplicate
            "occurred_at": occurred_at,
            "locker_id": locker_id,
            "type": "CompartmentRegistered",
            "payload": {"compartment_id": second_compartment_id},
        },
    )
    assert res2.status_code == 200

    summary_after_second = client.get(f"/lockers/{locker_id}")
    assert summary_after_second.status_code == 200
    state2 = summary_after_second.json()

    # Idempotency assertion: state must not change at all (including hash)
    assert state2 == state1