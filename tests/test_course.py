"""
Tests for GET /v1/image/variations/course/{course_id}

Route source:   app/routers/course.py:30-40
Response model: app/models.py:9-12  (ImageVariationResponse)
Pydantic models read: app/models.py:5-12

S8405 compliance: all client calls use keyword arguments matching the actual
content-type (no JSON string passed to data=).
"""

import pytest
from unittest.mock import patch

# Patch target: generate_image_variations is imported by name into the router
# module [app/routers/course.py:5], so we patch it there.
_SERVICE_PATCH = "app.routers.course.generate_image_variations"

_COURSE_URL = "/v1/image/variations/course/{course_id}"


# ── Helpers ────────────────────────────────────────────────────────────────

def _no_logo_result(urls=None):
    """Minimal valid return value for generate_image_variations with no logo.
    Matches the dict shape built in app/services/image_variation.py:313-316.
    """
    return (
        {"found": False, "warning": None},  # LogoDetection fields [app/models.py:5-7]
        urls or ["http://test-kb-host.example.test/test/proxy/do-0000000000001/thumb_0.jpg"],
    )


def _logo_result(urls=None):
    """Minimal valid return value when a logo is detected.
    warning text from app/services/image_variation.py:315.
    """
    return (
        {
            "found": True,
            "warning": (
                "This image contains a logo. AI may not accurately generate "
                "changes to logos. This feature is currently in beta testing."
            ),
        },
        urls or ["http://test-kb-host.example.test/test/proxy/do-0000000000002/thumb_0.jpg"],
    )


# ── 3.1 Functional Correctness ─────────────────────────────────────────────

def test_get_course_variations_happy_path_no_logo(client):
    """Happy path: service returns no logo + image URLs.

    Status:  200 [app/routers/course.py:37]
    Returns: ImageVariationResponse [app/models.py:9-12]
    """
    logo, urls = _no_logo_result()
    with patch(_SERVICE_PATCH, return_value=(logo, urls)):
        response = client.get("/v1/image/variations/course/do-0000000000001")

    assert response.status_code == 200  # [app/routers/course.py:37]
    body = response.json()
    # ImageVariationResponse fields [app/models.py:10-11]
    assert "images" in body
    assert "logo" in body
    assert body["images"] == urls
    # LogoDetection fields [app/models.py:5-7]
    assert body["logo"]["found"] is False
    assert body["logo"]["warning"] is None


def test_get_course_variations_happy_path_with_logo(client):
    """Happy path: logo detected — found=True and warning text populated.

    Status: 200 [app/routers/course.py:37]
    """
    logo, urls = _logo_result([
        "http://test-kb-host.example.test/test/proxy/do-0000000000002/thumb_0.jpg",
        "http://test-kb-host.example.test/test/proxy/do-0000000000002/thumb_1.jpg",
    ])
    with patch(_SERVICE_PATCH, return_value=(logo, urls)):
        response = client.get("/v1/image/variations/course/do-0000000000002")

    assert response.status_code == 200
    body = response.json()
    assert body["logo"]["found"] is True
    assert body["logo"]["warning"] is not None
    assert len(body["images"]) == 2


def test_get_course_variations_empty_image_list(client):
    """Edge case: service returns zero image URLs.

    No special handling for empty list in [app/routers/course.py:37] —
    200 with images=[] is the expected response.
    """
    with patch(_SERVICE_PATCH, return_value=({"found": False, "warning": None}, [])):
        response = client.get("/v1/image/variations/course/do-0000000000003")

    assert response.status_code == 200  # [app/routers/course.py:37]
    assert response.json()["images"] == []


def test_get_course_variations_multiple_image_urls(client):
    """Multiple image URLs returned — all should appear in response images list."""
    urls = [
        f"http://test-kb-host.example.test/test/proxy/do-0000000000004/thumb_{i}.jpg"
        for i in range(4)
    ]
    with patch(_SERVICE_PATCH, return_value=({"found": False, "warning": None}, urls)):
        response = client.get("/v1/image/variations/course/do-0000000000004")

    assert response.status_code == 200
    assert len(response.json()["images"]) == 4


# ── 3.2 Pydantic Validation ────────────────────────────────────────────────

def test_get_course_variations_course_id_accepts_any_string(client):
    """course_id is a str path param [app/routers/course.py:31].
    FastAPI accepts any non-empty string — no 422 for string path params.
    """
    with patch(_SERVICE_PATCH, return_value=_no_logo_result()):
        response = client.get("/v1/image/variations/course/arbitrary-string-id-123")

    assert response.status_code == 200  # no validation rejection


# ── 3.3 Security — Injection Attacks ──────────────────────────────────────

def test_get_course_variations_sql_injection_in_course_id(client):
    """SQL injection in course_id path param.

    course_id is passed to generate_image_variations() [app/routers/course.py:34]
    which makes HTTP requests — no SQL queries in this code path.
    With service mocked: assert no 500, assert payload not reflected in response.
    """
    sql_payload = "' OR '1'='1"
    with patch(_SERVICE_PATCH, return_value=_no_logo_result()):
        response = client.get(f"/v1/image/variations/course/{sql_payload}")

    assert response.status_code == 200
    assert "OR '1'='1" not in response.text


def test_get_course_variations_sql_injection_drop_table(client):
    """SQL injection: DROP TABLE payload in course_id."""
    with patch(_SERVICE_PATCH, return_value=_no_logo_result()):
        response = client.get(
            "/v1/image/variations/course/'; DROP TABLE users;--"
        )

    assert response.status_code in (200, 404, 422)  # must not be 500
    assert "DROP TABLE" not in response.text


def test_get_course_variations_xss_in_course_id(client):
    """XSS payload in course_id.

    Assert the raw <script> tag is not reflected unescaped in the response body.
    FastAPI's JSON serialisation escapes HTML characters by default.
    """
    xss_payload = "<script>alert(1)</script>"
    with patch(_SERVICE_PATCH, return_value=_no_logo_result()):
        response = client.get(f"/v1/image/variations/course/{xss_payload}")

    # Raw unescaped script must not appear in response [OWASP A03]
    assert "<script>alert(1)</script>" not in response.text


def test_get_course_variations_xss_img_onerror_in_course_id(client):
    """XSS via img onerror in course_id."""
    with patch(_SERVICE_PATCH, return_value=_no_logo_result()):
        response = client.get(
            '/v1/image/variations/course/"><img src=x onerror=alert(1)>'
        )

    assert '"><img src=x onerror=alert(1)>' not in response.text


def test_get_course_variations_path_traversal_in_course_id(client):
    """Path traversal payload in course_id.

    course_id is not used as a direct filesystem path in the route handler
    [app/routers/course.py:31-40]. Assert no /etc/passwd content in response.
    """
    traversal_payload = "../../etc/passwd"
    with patch(_SERVICE_PATCH, return_value=_no_logo_result()):
        response = client.get(f"/v1/image/variations/course/{traversal_payload}")

    # FastAPI/Starlette normalizes path separators in URL params — 404 is safe (route not matched).
    # 200 is also safe (service is mocked). 500 is NOT acceptable [app/routers/course.py:38-39].
    assert response.status_code in (200, 404)
    assert "/etc/passwd" not in response.text
    assert "root:" not in response.text


def test_get_course_variations_mass_assignment_ignored(client):
    """GET endpoint with path param only — no request body to mass-assign.
    Confirm the service mock is called with course_id only; no extra fields.
    This is a structural check given the route signature [app/routers/course.py:31].
    """
    with patch(_SERVICE_PATCH, return_value=_no_logo_result()) as mock_svc:
        response = client.get("/v1/image/variations/course/do-0000000000001")

    assert response.status_code == 200
    # Service called with exactly the course_id string
    mock_svc.assert_called_once_with("do-0000000000001")


# ── 3.4 Authentication & Authorisation ────────────────────────────────────

def test_get_course_variations_no_auth_required(client):
    """Route has no auth dependency [app/routers/course.py:31 — no Depends(...)].
    Unauthenticated request must succeed (not return 401 or 403).
    """
    with patch(_SERVICE_PATCH, return_value=_no_logo_result()):
        response = client.get("/v1/image/variations/course/do-0000000000001")

    assert response.status_code not in (401, 403)


def test_get_course_variations_no_auth_header_accepted(client):
    """Confirm no Authorization header is required [app/routers/course.py:31]."""
    with patch(_SERVICE_PATCH, return_value=_no_logo_result()):
        response = client.get(
            "/v1/image/variations/course/do-0000000000001",
            headers={},  # explicitly no Authorization header
        )

    assert response.status_code == 200


# ── 3.5 Error Handling & Resilience ───────────────────────────────────────

def test_get_course_variations_service_raises_exception_returns_500(client):
    """Service exception → HTTPException(status_code=500) [app/routers/course.py:38-39].

    S8415: 500 is raised [app/routers/course.py:39] but NOT documented in
           responses={} on the route decorator [app/routers/course.py:30].
           This test verifies the behavior; the S8415 gap is a documentation issue.
    """
    with patch(_SERVICE_PATCH, side_effect=Exception("upstream failure")):
        response = client.get("/v1/image/variations/course/do-0000000000001")

    # Status code from [app/routers/course.py:39]
    assert response.status_code == 500
    body = response.json()
    # Safe detail message from [app/routers/course.py:39]
    assert body["detail"] == "Something went wrong, please try again later..."


def test_get_course_variations_error_response_no_stack_trace(client):
    """Error response must not leak internal details [OWASP A05].

    Confirms the except clause [app/routers/course.py:38-39] returns a sanitized
    message and does not echo the original exception message.
    """
    with patch(
        _SERVICE_PATCH,
        side_effect=RuntimeError("db://secret:pass@internal-db-host/prod"),
    ):
        response = client.get("/v1/image/variations/course/do-0000000000001")

    assert response.status_code == 500
    # Original exception detail must not appear in response
    assert "Traceback" not in response.text
    assert "secret" not in response.text
    assert "internal-db-host" not in response.text
    assert "db://" not in response.text


def test_get_course_variations_error_detail_is_safe_string(client):
    """Exact safe error detail string from [app/routers/course.py:39]."""
    with patch(_SERVICE_PATCH, side_effect=ValueError("any internal message")):
        response = client.get("/v1/image/variations/course/do-0000000000001")

    assert response.json()["detail"] == "Something went wrong, please try again later..."


# ── 3.6 Response Model & Field Leakage ────────────────────────────────────

def test_get_course_variations_response_model_exact_fields(client):
    """Response contains exactly the fields declared in ImageVariationResponse
    [app/models.py:9-12] and LogoDetection [app/models.py:5-7].
    No extra fields leaked.
    """
    with patch(_SERVICE_PATCH, return_value=_no_logo_result()):
        response = client.get("/v1/image/variations/course/do-0000000000001")

    body = response.json()
    # Top-level: only 'images' and 'logo' [app/models.py:10-11]
    assert set(body.keys()) == {"images", "logo"}
    # logo sub-object: only 'found' and 'warning' [app/models.py:5-7]
    assert set(body["logo"].keys()) == {"found", "warning"}


def test_get_course_variations_no_sensitive_fields_in_response(client):
    """Response must not contain any sensitive field names [OWASP A05]."""
    with patch(_SERVICE_PATCH, return_value=_no_logo_result()):
        response = client.get("/v1/image/variations/course/do-0000000000001")

    assert "password" not in response.text
    assert "token" not in response.text
    assert "secret" not in response.text
    assert "api_key" not in response.text
    assert "credential" not in response.text


# ── 3.7 FastAPI-Specific: S8415 Ghost Exception ────────────────────────────

def test_get_course_variations_openapi_does_not_document_500(client):
    """S8415: GET /v1/image/variations/course/{course_id} raises HTTPException(500)
    [app/routers/course.py:39] but the decorator has no responses={500: ...}
    [app/routers/course.py:30].

    This test asserts the S8415 finding is present (500 not in documented responses).
    If this test starts FAILING, the S8415 gap has been fixed — remove this test
    and update CODEBASE_SUMMARY.md accordingly.
    """
    response = client.get("/openapi.json")
    course_path = response.json()["paths"].get(
        "/v1/image/variations/course/{course_id}", {}
    )
    documented_responses = set(course_path.get("get", {}).get("responses", {}).keys())
    # S8415 finding: 500 is NOT documented [app/routers/course.py:30]
    assert "500" not in documented_responses, (
        "500 is now documented on this route — S8415 finding resolved. "
        "Remove this test and update CODEBASE_SUMMARY.md."
    )
