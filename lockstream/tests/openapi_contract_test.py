from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

import pytest
import yaml
from fastapi.routing import APIRoute

from lockstream.main import app


def _project_root() -> Path:
    # lockstream/tests/ -> lockstream/ -> project root
    return Path(__file__).resolve().parents[2]


def _load_openapi_yaml() -> dict[str, Any]:
    path = _project_root() / "lockstream" / "openapi" / "openapi.yaml"
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

    This protects you from accidental spec drift (e.g. changing response codes,
    response models, parameter names) without updating the contract.
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

        openapi_methods = {k for k in path_item.keys() if k in {"get", "post", "put", "patch", "delete", "options", "head"}}
        fastapi_methods = _normalize_http_methods(route.methods or set())

        # FastAPI automatically includes HEAD for GET routes; OpenAPI often omits it.
        fastapi_methods.discard("head")

        if openapi_methods != fastapi_methods:
            mismatches.append(
                f"{route.path}: fastapi={sorted(fastapi_methods)} openapi={sorted(openapi_methods)}"
            )

    assert not mismatches, "Method mismatches:\n" + "\n".join(mismatches)


@pytest.mark.parametrize(
    "schema_name",
    [
        "Event",
        "LockerSummary",
        "CompartmentStatus",
        "ReservationStatus",
    ],
)
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
