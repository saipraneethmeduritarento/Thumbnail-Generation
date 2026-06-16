"""
Application-wide lifecycle and infrastructure checks.

Covers:
  S8401 — Router registration order (via OpenAPI schema completeness)
  S8400 — No phantom 204 bodies (no 204 routes exist)
  S8414 — CORSMiddleware wraps error responses

Route inventory source (Phase 1.2):
  - GET /v2/image/variations/course/{course_id} [app/routers/v2/course.py:11]

CORSMiddleware source: app/main.py:13-19
Router registration:   app/main.py:21, app/routers/__init__.py
"""

import pytest
from unittest.mock import patch


# ── S8401 — Router Registration Order ─────────────────────────────────────

def test_openapi_schema_returns_200(client):
    """GET /openapi.json must return 200.

    Confirms the app starts successfully and FastAPI can generate the schema.
    Source: app/main.py:9-21 (app definition + router inclusion).
    """
    response = client.get("/openapi.json")
    assert response.status_code == 200


def test_openapi_schema_contains_course_variations_route(client):
    """S8401: Course variations route must be present in OpenAPI schema.

    Missing path would indicate a router registration-order bug.
    Expected path from [app/routers/v2/course.py:12], mounted via
    app/routers/__init__.py → app/main.py:21.
    """
    response = client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/v2/image/variations/course/{course_id}" in paths, (
        "S8401: /v2/image/variations/course/{course_id} missing from OpenAPI schema — "
        "check router registration order in app/routers/__init__.py and app/main.py"
    )


def test_openapi_schema_all_routes_present(client):
    """S8401: Full route inventory from Phase 1.2 must appear in OpenAPI schema."""
    # All active routes
    expected_paths = [
        "/v2/image/variations/course/{course_id}",  # app/routers/v2/course.py:12
    ]
    response = client.get("/openapi.json")
    assert response.status_code == 200
    actual_paths = set(response.json()["paths"].keys())

    missing = [p for p in expected_paths if p not in actual_paths]
    assert not missing, (
        f"S8401: These routes are missing from OpenAPI schema: {missing}. "
        "Check router registration order."
    )


# ── S8400 — No Phantom 204 Bodies ─────────────────────────────────────────

def test_no_204_routes_exist(client):
    """S8400: Phase 1.2 inventory found zero routes with status_code=204.

    This test documents that finding and will catch any future 204 addition
    that is not paired with an explicit empty response body.
    """
    response = client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]

    routes_with_204 = []
    for path, methods in paths.items():
        for method, spec in methods.items():
            responses = spec.get("responses", {})
            if "204" in responses:
                routes_with_204.append(f"{method.upper()} {path}")

    assert not routes_with_204, (
        f"S8400: Unexpected 204 response found on: {routes_with_204}. "
        "Add explicit `assert response.content == b''` assertion if intentional."
    )


# ── S8414 — CORSMiddleware Wraps All Responses ─────────────────────────────

def test_cors_header_present_on_success_response(client):
    """S8414: CORSMiddleware [app/main.py:13-19] must add CORS headers to normal responses."""
    with patch(
        "app.routers.v2.course.generate_image_variations",
        return_value=(
            {"found": False, "warning": None},
            ["http://test-kb-host.example.test/test/proxy/do-0000000000001/t_0.jpg"],
        ),
    ):
        response = client.get(
            "/v2/image/variations/course/do-0000000000001",
            headers={"Origin": "http://test-origin.example.test"},
        )
    assert response.status_code == 200
    # CORSMiddleware should add Access-Control-Allow-Origin [app/main.py:15 — allow_origins=["*"]]
    assert "access-control-allow-origin" in response.headers, (
        "S8414: CORS header missing from success response — CORSMiddleware not active"
    )


def test_cors_header_present_on_error_response(client):
    """S8414: CORSMiddleware must be the outermost ASGI layer so that CORS headers
    are added to error responses too.

    Strategy: force a 500 on the course variations route by making the service
    raise; send Origin header; assert Access-Control-Allow-Origin is in the
    error response.

    CORSMiddleware is added via app.add_middleware [app/main.py:13-19] and
    app.include_router is called after [app/main.py:21] — correct ordering.
    """
    with patch(
        "app.routers.v2.course.generate_image_variations",
        side_effect=Exception("forced error for S8414 test"),
    ):
        response = client.get(
            "/v2/image/variations/course/do-0000000000001",
            headers={"Origin": "http://test-origin.example.test"},
        )

    assert response.status_code == 500
    assert "access-control-allow-origin" in response.headers, (
        "S8414: CORS header missing from error (500) response — "
        "CORSMiddleware may not be the outermost layer. "
        "Check middleware registration order in app/main.py:13-19."
    )


def test_cors_preflight_request(client):
    """CORS preflight (OPTIONS) must be handled by CORSMiddleware [app/main.py:13-19]."""
    response = client.options(
        "/v2/image/variations/course/do-0000000000001",
        headers={
            "Origin": "http://test-origin.example.test",
            "Access-Control-Request-Method": "GET",
        },
    )
    # CORSMiddleware handles OPTIONS — should return 200 with CORS headers
    assert response.status_code == 200
    assert "access-control-allow-origin" in response.headers


# ── S8396 — LogoDetection.warning missing default ──────────────────────────

def test_logo_detection_warning_field_accepts_none(client):
    """S8396: LogoDetection.warning is typed `str | None` with no `= None` default
    [app/models.py:7]. The server must always provide this field.

    This test verifies that when the service returns warning=None, the response
    serialises correctly (no ValidationError on the server side).
    """
    with patch(
        "app.routers.v2.course.generate_image_variations",
        return_value=(
            {"found": False, "warning": None},  # warning explicitly None
            ["http://test-kb-host.example.test/test/proxy/do-0000000000001/t_0.jpg"],
        ),
    ):
        response = client.get("/v2/image/variations/course/do-0000000000001")

    assert response.status_code == 200
    assert response.json()["logo"]["warning"] is None


def test_logo_detection_warning_field_accepts_string(client):
    """S8396: LogoDetection.warning must also accept a non-None string value."""
    warning_text = "This image contains a logo."
    with patch(
        "app.routers.v2.course.generate_image_variations",
        return_value=(
            {"found": True, "warning": warning_text},
            ["http://test-kb-host.example.test/test/proxy/do-0000000000002/t_0.jpg"],
        ),
    ):
        response = client.get("/v2/image/variations/course/do-0000000000002")

    assert response.status_code == 200
    assert response.json()["logo"]["warning"] == warning_text
