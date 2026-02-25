from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
import yaml
from fastapi.routing import APIRoute
from starlette.testclient import TestClient

from lockstream.main import app


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def openapi_path() -> Path:
    from lockstream.infrastructure.config import settings
    return settings.openapi_path

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


def _load_openapi_yaml() -> dict[str, Any]:
    path = openapi_path()
    print(path)
    with path.open("r", encoding="utf-8") as f:
        doc = yaml.safe_load(f)
    assert isinstance(doc, dict)
    return doc


def _normalize_http_methods(methods: Iterable[str]) -> set[str]:
    return {m.lower() for m in methods}


def _is_public_api_route(route: APIRoute) -> bool:
    # Exclude docs/openapi endpoints if they exist
    return not route.path.startswith(("/docs", "/redoc", "/openapi"))


def test_openapi_is_exactly_the_yaml_contract() -> None:
    """
    Contract test: the app's OpenAPI must match the committed YAML contract.
    """
    expected = _load_openapi_yaml()
    actual = app.openapi()

    assert actual == expected


def test_all_fastapi_routes_are_declared_in_openapi_paths() -> None:
    """
    Contract test: every public APIRoute must exist in the OpenAPI `paths`.
    """
    spec = app.openapi()
    paths: dict[str, Any] = spec.get("paths", {})
    assert isinstance(paths, dict)

    api_routes = [r for r in app.routes if isinstance(r, APIRoute) and _is_public_api_route(r)]
    assert api_routes, "No API routes found; is the router included in the app?"

    missing: list[str] = []
    for route in api_routes:
        if route.path not in paths:
            missing.append(route.path)

    assert not missing, f"Routes missing from OpenAPI paths: {missing}"


def test_openapi_methods_match_fastapi_methods() -> None:
    """
    Contract test: for each path, the HTTP methods in FastAPI and in OpenAPI must match.
    """
    spec = app.openapi()
    paths: dict[str, Any] = spec.get("paths", {})
    assert isinstance(paths, dict)

    api_routes = [r for r in app.routes if isinstance(r, APIRoute) and _is_public_api_route(r)]

    mismatches: list[str] = []
    for route in api_routes:
        path_item = paths.get(route.path)
        if not isinstance(path_item, dict):
            mismatches.append(f"{route.path}: not found or not a dict in OpenAPI")
            continue

        openapi_methods = {k for k in path_item.keys() if
                           k in {"get", "post", "put", "patch", "delete", "options", "head"}}
        fastapi_methods = _normalize_http_methods(route.methods or set())

        # FastAPI automatically includes HEAD for GET routes; OpenAPI often omits it.
        fastapi_methods.discard("head")

        if openapi_methods != fastapi_methods:
            mismatches.append(f"{route.path}: fastapi={sorted(fastapi_methods)} openapi={sorted(openapi_methods)}")

    assert not mismatches, "Method mismatches:\n" + "\n".join(mismatches)


@pytest.mark.parametrize("schema_name", ["Event", "LockerSummary", "CompartmentStatus", "ReservationStatus", ], )
def test_openapi_declares_expected_component_schemas(schema_name: str) -> None:
    """
    Ensure commonly used response/request schemas exist in the contract.
    """
    spec = app.openapi()
    components = spec.get("components", {})
    assert isinstance(components, dict)

    schemas = components.get("schemas", {})
    assert isinstance(schemas, dict)

    assert schema_name in schemas, f"Missing components.schemas.{schema_name} in OpenAPI"


def _valid_event_body() -> dict:
    return {"event_id": str(uuid4()), "occurred_at": datetime.now(timezone.utc).isoformat(),
            "locker_id": f"LOCKER-{uuid4()}", "type": "CompartmentRegistered", "payload": {"compartment_id": "C0001"}, }


@pytest.mark.parametrize("invalid_body", [  # Missing required fields
    lambda: {k: v for k, v in _valid_event_body().items() if k != "event_id"},
    lambda: {k: v for k, v in _valid_event_body().items() if k != "occurred_at"},
    lambda: {k: v for k, v in _valid_event_body().items() if k != "locker_id"},
    lambda: {k: v for k, v in _valid_event_body().items() if k != "type"},
    lambda: {k: v for k, v in _valid_event_body().items() if k != "payload"},

    # Wrong formats / types
    lambda: {**_valid_event_body(), "event_id": "not-a-uuid"},
    lambda: {**_valid_event_body(), "occurred_at": "not-a-datetime"},
    lambda: {**_valid_event_body(), "payload": "not-an-object"},

    # Enum violation
    lambda: {**_valid_event_body(), "type": "NotARealEventType"}, ], )
def test_post_events_request_schema_violations_return_422(invalid_body) -> None:
    client = TestClient(app)

    res = client.post("/events", json=invalid_body())
    assert res.status_code == 422

    body = res.json()
    assert "detail" in body
    assert isinstance(body["detail"], list)
    assert body["detail"], "Expected at least one validation error"
    assert any(err.get("loc", [None])[0] == "body" for err in body["detail"])


def _post_event(client: TestClient, *, locker_id: str, event_type: str, payload: dict) -> int:
    res = client.post("/events", json={"event_id": str(uuid4()), "occurred_at": _now_iso(), "locker_id": locker_id,
                                       "type": event_type, "payload": payload, }, )
    return res.status_code


def test_get_locker_summary_not_found_returns_404() -> None:
    client = TestClient(app)

    res = client.get(f"/lockers/LOCKER-{uuid4()}")
    assert res.status_code == 404
    body = res.json()
    assert "detail" in body


def test_get_compartment_status_unknown_locker_returns_404() -> None:
    client = TestClient(app)

    res = client.get(f"/lockers/LOCKER-{uuid4()}/compartments/C0001")
    assert res.status_code == 404
    body = res.json()
    assert "detail" in body


def test_get_compartment_status_unknown_compartment_returns_404() -> None:
    client = TestClient(app)

    locker_id = f"LOCKER-{uuid4()}"
    assert _post_event(client, locker_id=locker_id, event_type="CompartmentRegistered",
                       payload={"compartment_id": "C0001"}, ) == 202

    res = client.get(f"/lockers/{locker_id}/compartments/C9999")
    assert res.status_code == 404
    body = res.json()
    assert "detail" in body


def test_get_reservation_status_not_found_returns_404() -> None:
    client = TestClient(app)

    res = client.get(f"/reservations/R-{uuid4()}")
    assert res.status_code == 404
    body = res.json()
    assert "detail" in body


def test_get_routes_happy_path_returns_200_and_expected_shapes() -> None:
    client = TestClient(app)

    locker_id = f"LOCKER-{uuid4()}"
    compartment_id = "C0001"
    reservation_id = f"R-{uuid4()}"

    # Build minimal state for GETs
    assert _post_event(client, locker_id=locker_id, event_type="CompartmentRegistered",
                       payload={"compartment_id": compartment_id}, ) == 202

    assert _post_event(client, locker_id=locker_id, event_type="ReservationCreated",
                       payload={"reservation_id": reservation_id, "compartment_id": compartment_id}, ) == 202

    # GET /lockers/{locker_id}
    res_summary = client.get(f"/lockers/{locker_id}")
    assert res_summary.status_code == 200
    summary = res_summary.json()

    assert summary["locker_id"] == locker_id
    assert isinstance(summary["compartments"], int) and summary["compartments"] >= 1
    assert isinstance(summary["active_reservations"], int) and summary["active_reservations"] >= 1
    assert isinstance(summary["degraded_compartments"], int) and summary["degraded_compartments"] >= 0
    assert isinstance(summary["state_hash"], str) and summary["state_hash"]

    # GET /lockers/{locker_id}/compartments/{compartment_id}
    res_comp = client.get(f"/lockers/{locker_id}/compartments/{compartment_id}")
    assert res_comp.status_code == 200
    comp = res_comp.json()

    assert comp["compartment_id"] == compartment_id
    assert isinstance(comp["degraded"], bool)
    assert ("active_reservation" in comp) and (comp["active_reservation"] in (None, reservation_id))

    # GET /reservations/{reservation_id}
    res_reservation = client.get(f"/reservations/{reservation_id}")
    assert res_reservation.status_code == 200
    reservation = res_reservation.json()

    assert reservation["reservation_id"] == reservation_id
    assert reservation["status"] in {"CREATED", "DEPOSITED", "PICKED_UP", "EXPIRED"}
    assert reservation["status"] == "CREATED"
