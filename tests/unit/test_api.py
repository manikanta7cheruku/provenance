import json
import logging
from collections.abc import Callable, Iterator

import pytest
from fastapi.testclient import TestClient

from pv_api.logging_config import JsonFormatter
from pv_api.main import create_app
from pv_config import Settings

Make = Callable[..., Settings]


@pytest.fixture
def client(make_settings: Make) -> Iterator[TestClient]:
    # The database URL points at a closed port, so readiness must report failure.
    with TestClient(create_app(make_settings())) as test_client:
        yield test_client


def test_liveness_does_not_need_the_database(client: TestClient) -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_fails_when_database_is_down(client: TestClient) -> None:
    response = client.get("/readyz")
    assert response.status_code == 503
    body = response.json()
    assert body["ready"] is False
    assert body["checks"]["database"] == "fail"


def test_status_endpoint_reports_without_leaking_details(client: TestClient) -> None:
    response = client.get("/api/v1/status")
    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "provenance-api"
    assert body["ready"] is False
    assert "apppw" not in response.text


def test_every_response_has_a_request_id(client: TestClient) -> None:
    response = client.get("/healthz")
    assert len(response.headers["x-request-id"]) == 32


def test_docs_are_hidden_in_production(make_settings: Make) -> None:
    settings = make_settings(
        environment="production",
        cors_origins="https://app.example.com",
        public_base_url="https://app.example.com",
        smtp_host="smtp.example.com",
    )
    with TestClient(create_app(settings)) as prod_client:
        assert prod_client.get("/api/docs").status_code == 404
        assert prod_client.get("/api/openapi.json").status_code == 404


def test_unhandled_error_is_classified_and_hides_internals(make_settings: Make) -> None:
    app = create_app(make_settings())

    @app.get("/boom")
    def boom() -> None:
        raise RuntimeError("secret internal detail")

    with TestClient(app, raise_server_exceptions=False) as test_client:
        response = test_client.get("/boom")
    assert response.status_code == 500
    body = response.json()
    assert body["failure_class"] == "INTERNAL_ERROR"
    assert "secret internal detail" not in response.text
    assert body["request_id"] == response.headers["x-request-id"]


def test_json_log_formatter_emits_allowlisted_fields_only() -> None:
    record = logging.LogRecord("t", logging.INFO, __file__, 1, "request", None, None)
    record.request_id = "abc"
    record.password = "should-not-appear"
    payload = json.loads(JsonFormatter().format(record))
    assert payload["request_id"] == "abc"
    assert "password" not in payload
    assert "should-not-appear" not in json.dumps(payload)


def test_security_headers_are_set(client: TestClient) -> None:
    response = client.get("/healthz")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"


def test_api_responses_are_not_cached(client: TestClient) -> None:
    assert client.get("/api/v1/status").headers["cache-control"] == "no-store"


def test_oversized_request_body_is_rejected_before_any_work(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login",
        content=b"x" * 1_200_000,
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 413
    assert response.json()["code"] == "PAYLOAD_TOO_LARGE"


def test_validation_errors_use_the_shared_error_shape(client: TestClient) -> None:
    response = client.post("/api/v1/auth/login", json={"email": "a@example.com"})
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "VALIDATION_FAILED"
    assert "password" in body["fields"]
