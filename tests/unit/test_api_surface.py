"""The API must never expose task payloads, secrets or password hashes in its schemas."""

from collections.abc import Callable
from typing import Any

from pv_api.main import create_app
from pv_config import Settings

Make = Callable[..., Settings]
FORBIDDEN = {"payload", "secret", "password_hash", "token_hash", "code_hash", "idempotency_key"}


def _property_names(node: Any) -> set[str]:
    names: set[str] = set()
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "properties" and isinstance(value, dict):
                names |= set(value)
            names |= _property_names(value)
    elif isinstance(node, list):
        for item in node:
            names |= _property_names(item)
    return names


def test_no_schema_exposes_payloads_or_secret_columns(make_settings: Make) -> None:
    schema = create_app(make_settings()).openapi()
    response_schemas = schema["components"]["schemas"]
    exposed: set[str] = set()
    for schema_name, definition in response_schemas.items():
        if not schema_name.endswith(("Request", "Create")):
            exposed |= _property_names(definition)
    assert not (exposed & FORBIDDEN)


def test_every_admin_route_is_declared_under_the_admin_prefix(make_settings: Make) -> None:
    schema = create_app(make_settings()).openapi()
    admin = [path for path in schema["paths"] if "/admin/" in path]
    assert "/api/v1/admin/system" in admin
    assert "/api/v1/admin/users" in admin
    assert all(path.startswith("/api/v1/admin/") for path in admin)
